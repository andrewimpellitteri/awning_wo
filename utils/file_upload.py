import os
from werkzeug.utils import secure_filename
from models.work_order_file import WorkOrderFile
from extensions import db
import boto3
import pickle
import json
from io import BytesIO
from datetime import datetime
from .thumbnail_generator import (
    generate_thumbnail,
    save_thumbnail_to_s3,
    save_thumbnail_locally,
)


UPLOAD_FOLDER = "uploads/work_orders"  # local fallback
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "txt", "csv"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not AWS_S3_BUCKET:
    raise ValueError("AWS_S3_BUCKET environment variable is required")


def is_running_on_aws():
    """Better detection for AWS environment"""
    # Check multiple indicators that we're running on AWS
    aws_indicators = [
        os.getenv("AWS_EXECUTION_ENV"),  # Set by AWS services
        os.getenv("AWS_LAMBDA_FUNCTION_NAME"),  # Lambda
        os.getenv("AWS_REGION"),  # Usually set in AWS environments
        os.path.exists("/var/app/current"),  # EB directory structure
        os.path.exists("/opt/elasticbeanstalk"),  # EB specific path
    ]

    # If any AWS indicator is present, assume we're on AWS
    return any(aws_indicators)


# Detect environment
is_aws_environment = is_running_on_aws()

if is_aws_environment:
    # Use IAM role (no credentials needed)
    print("Detected AWS environment - using IAM role for S3 access")
    s3_client = boto3.client("s3", region_name=AWS_REGION)
else:
    # Use explicit credentials for local development
    print("Detected local environment - using explicit AWS credentials")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError(
            "Local development requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        )

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def save_order_file_generic(
    order_no,
    file,
    order_type="work_order",
    to_s3=True,
    generate_thumbnails=True,
    file_model_class=None,
):
    """
    Generic function to save order files (work orders or repair orders)

    Args:
        order_no: The order number
        file: The file object to save
        order_type: "work_order" or "repair_order"
        to_s3: Whether to save to S3 (True) or locally (False)
        generate_thumbnails: Whether to generate thumbnails
        file_model_class: The model class to use (WorkOrderFile or RepairOrderFile)

    Returns:
        File model instance (not committed to DB)
    """
    filename = secure_filename(file.filename)

    # Validate file type
    if not allowed_file(filename):
        return None

    # Read file content for thumbnail generation
    file_content = None
    if generate_thumbnails:
        file.seek(0)
        file_content = file.read()
        file.seek(0)  # Reset file pointer for upload

    # Determine folder prefix based on order type
    folder_prefix = "work_orders" if order_type == "work_order" else "repair_orders"

    if to_s3:
        s3_key = f"{folder_prefix}/{order_no}/{filename}"

        # Upload file to S3 with proper error handling
        try:
            s3_client.upload_fileobj(file, AWS_S3_BUCKET, s3_key)
            file_path = f"s3://{AWS_S3_BUCKET}/{s3_key}"
            print(f"Successfully uploaded file to S3: {s3_key}")
        except s3_client.exceptions.NoSuchBucket:
            error_msg = f"S3 bucket '{AWS_S3_BUCKET}' does not exist"
            print(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        except s3_client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = f"S3 client error ({error_code}) uploading {filename}: {e}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error uploading {filename} to S3: {e}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)

        # Generate and save thumbnail to S3
        thumbnail_path = None
        if generate_thumbnails and file_content:
            try:
                thumbnail_img = generate_thumbnail(file_content, filename)
                thumbnail_key = save_thumbnail_to_s3(
                    thumbnail_img, s3_client, AWS_S3_BUCKET, s3_key
                )
                thumbnail_path = f"s3://{AWS_S3_BUCKET}/{thumbnail_key}"
                print(f"Generated thumbnail: {thumbnail_path}")
            except Exception as e:
                # Thumbnail generation is not critical - log but don't fail
                print(f"WARNING: Error generating thumbnail for {filename}: {e}")
    else:
        order_folder = os.path.join(UPLOAD_FOLDER, folder_prefix, str(order_no))
        os.makedirs(order_folder, exist_ok=True)
        file_path = os.path.join(order_folder, filename)
        file.save(file_path)

        # Generate and save thumbnail locally
        thumbnail_path = None
        if generate_thumbnails and file_content:
            try:
                thumbnail_img = generate_thumbnail(file_content, filename)
                thumbnail_path = save_thumbnail_locally(thumbnail_img, file_path)
                print(f"Generated thumbnail: {thumbnail_path}")
            except Exception as e:
                print(f"Error generating thumbnail for {filename}: {e}")

    # Determine field name based on order type
    order_no_field = "WorkOrderNo" if order_type == "work_order" else "RepairOrderNo"

    # Create file object but don't commit yet
    if file_model_class is None:
        from models.work_order_file import WorkOrderFile
        file_model_class = WorkOrderFile

    file_obj = file_model_class(
        **{
            order_no_field: order_no,
            "filename": filename,
            "file_path": file_path,
            "thumbnail_path": thumbnail_path if generate_thumbnails else None,
        }
    )

    return file_obj


def save_work_order_file(work_order_no, file, to_s3=True, generate_thumbnails=True):
    """
    Save work order file and generate thumbnail but don't commit to DB
    Returns the WorkOrderFile object for batch processing

    This is a wrapper around save_order_file_generic for backward compatibility
    """
    from models.work_order_file import WorkOrderFile

    return save_order_file_generic(
        order_no=work_order_no,
        file=file,
        order_type="work_order",
        to_s3=to_s3,
        generate_thumbnails=generate_thumbnails,
        file_model_class=WorkOrderFile,
    )


def save_repair_order_file(repair_order_no, file, to_s3=True, generate_thumbnails=True):
    """
    Save repair order file and generate thumbnail but don't commit to DB
    Returns the RepairOrderFile object for batch processing
    """
    from models.repair_order_file import RepairOrderFile

    return save_order_file_generic(
        order_no=repair_order_no,
        file=file,
        order_type="repair_order",
        to_s3=to_s3,
        generate_thumbnails=generate_thumbnails,
        file_model_class=RepairOrderFile,
    )


def get_file_size(file_path):
    """Get human readable file size"""
    if file_path.startswith("s3://"):
        try:
            s3_key = file_path.replace(f"s3://{AWS_S3_BUCKET}/", "")
            response = s3_client.head_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
            size_bytes = response["ContentLength"]
        except s3_client.exceptions.NoSuchKey:
            print(f"S3 file not found: {file_path}")
            return None
        except s3_client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"S3 client error ({error_code}) getting file size for {file_path}: {e}")
            return None
        except Exception as e:
            print(f"Error getting S3 file size for {file_path}: {e}")
            return None
    else:
        try:
            size_bytes = os.path.getsize(file_path)
        except FileNotFoundError:
            print(f"Local file not found: {file_path}")
            return None
        except Exception as e:
            print(f"Error getting local file size for {file_path}: {e}")
            return None

    # Convert to human readable
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def generate_presigned_url(file_path: str, expires_in: int = 3600) -> str:
    """
    Given a full s3://bucket/key path, generate a pre-signed URL.
    Note: This only makes the URL expire, NOT the file itself.
    """
    if not file_path.startswith("s3://"):
        raise ValueError("File path must be an S3 path")

    # Remove "s3://bucket-name/"
    s3_key = file_path.replace(f"s3://{AWS_S3_BUCKET}/", "")

    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": AWS_S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def generate_thumbnail_presigned_url(
    thumbnail_path: str, expires_in: int = 3600
) -> str:
    """
    Generate presigned URL for thumbnail
    """
    if thumbnail_path and thumbnail_path.startswith("s3://"):
        return generate_presigned_url(thumbnail_path, expires_in)
    return None


def get_file_with_thumbnail_urls(wo_file, expires_in: int = 3600):
    """
    Get file URLs including thumbnail for a WorkOrderFile object
    """
    file_url = None
    thumbnail_url = None

    if wo_file.file_path.startswith("s3://"):
        file_url = generate_presigned_url(wo_file.file_path, expires_in)

    if wo_file.thumbnail_path and wo_file.thumbnail_path.startswith("s3://"):
        thumbnail_url = generate_presigned_url(wo_file.thumbnail_path, expires_in)
    elif wo_file.thumbnail_path and not wo_file.thumbnail_path.startswith("s3://"):
        # Local thumbnail path - you might want to serve this through your web server
        thumbnail_url = wo_file.thumbnail_path

    return {
        "file": wo_file,
        "file_url": file_url or wo_file.file_path,
        "thumbnail_url": thumbnail_url,
        "has_thumbnail": bool(thumbnail_url),
    }


# Add this to your existing S3 setup (after your file upload functions)
def save_ml_model(model, metadata, model_name="latest_model"):
    """
    Save a trained ML model and its metadata to S3
    """
    try:
        # Serialize the model
        model_buffer = BytesIO()
        pickle.dump(model, model_buffer)
        model_buffer.seek(0)

        # Serialize metadata
        metadata_buffer = BytesIO()
        metadata_json = json.dumps(metadata, indent=2, default=str)
        metadata_buffer.write(metadata_json.encode("utf-8"))
        metadata_buffer.seek(0)

        # Upload model to S3
        model_s3_key = f"ml_models/{model_name}.pkl"
        s3_client.upload_fileobj(model_buffer, AWS_S3_BUCKET, model_s3_key)

        # Upload metadata to S3
        metadata_s3_key = f"ml_models/{model_name}_metadata.json"
        s3_client.upload_fileobj(metadata_buffer, AWS_S3_BUCKET, metadata_s3_key)

        return {
            "model_path": f"s3://{AWS_S3_BUCKET}/{model_s3_key}",
            "metadata_path": f"s3://{AWS_S3_BUCKET}/{metadata_s3_key}",
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception as e:
        print(f"Error saving model: {e}")
        raise


def load_ml_model(model_name="latest_model"):
    """
    Load a trained ML model and its metadata from S3
    """
    try:
        # Download model from S3
        model_s3_key = f"ml_models/{model_name}.pkl"
        model_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, model_s3_key, model_buffer)
        model_buffer.seek(0)
        model = pickle.load(model_buffer)

        # Download metadata from S3
        metadata_s3_key = f"ml_models/{model_name}_metadata.json"
        metadata_buffer = BytesIO()
        s3_client.download_fileobj(AWS_S3_BUCKET, metadata_s3_key, metadata_buffer)
        metadata_buffer.seek(0)
        metadata = json.loads(metadata_buffer.read().decode("utf-8"))

        return model, metadata

    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None


def list_saved_models():
    """
    List all saved models in S3
    """
    try:
        response = s3_client.list_objects_v2(
            Bucket=AWS_S3_BUCKET, Prefix="ml_models/", Delimiter="/"
        )

        models = []
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".pkl"):
                    model_name = (
                        obj["Key"].replace("ml_models/", "").replace(".pkl", "")
                    )
                    models.append(
                        {
                            "name": model_name,
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )

        return models

    except Exception as e:
        print(f"Error listing models: {e}")
        return []


def delete_ml_model(model_name):
    """
    Delete a model and its metadata from S3
    """
    try:
        # Delete model file
        model_s3_key = f"ml_models/{model_name}.pkl"
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=model_s3_key)

        # Delete metadata file
        metadata_s3_key = f"ml_models/{model_name}_metadata.json"
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=metadata_s3_key)

        return True

    except Exception as e:
        print(f"Error deleting model: {e}")
        return False


def delete_file_from_s3(file_path):
    """
    Delete a file from S3 given its full s3:// path
    Also handles thumbnail deletion if a thumbnail path is provided

    Args:
        file_path: Full S3 path (e.g., s3://bucket-name/path/to/file.jpg)

    Returns:
        bool: True on success, False on failure
    """
    if not file_path or not file_path.startswith("s3://"):
        print(f"Not an S3 path, skipping deletion: {file_path}")
        return False

    try:
        s3_key = file_path.replace(f"s3://{AWS_S3_BUCKET}/", "")
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        print(f"Successfully deleted S3 file: {s3_key}")
        return True
    except s3_client.exceptions.NoSuchKey:
        print(f"S3 file not found (may already be deleted): {s3_key}")
        return True  # Consider this a success since the file is gone
    except Exception as e:
        print(f"Error deleting S3 file {file_path}: {e}")
        return False
