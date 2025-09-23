import os
from werkzeug.utils import secure_filename
from models.work_order_file import WorkOrderFile
from extensions import db
import boto3
import pickle
import json
from io import BytesIO
from datetime import datetime

UPLOAD_FOLDER = "uploads/work_orders"  # local fallback
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "txt", "csv"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


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


def save_work_order_file(work_order_no, file, to_s3=True):
    filename = secure_filename(file.filename)

    if to_s3:
        s3_key = f"work_orders/{work_order_no}/{filename}"
        s3_client.upload_fileobj(file, AWS_S3_BUCKET, s3_key)
        file_path = f"s3://{AWS_S3_BUCKET}/{s3_key}"
    else:
        wo_folder = os.path.join(UPLOAD_FOLDER, str(work_order_no))
        os.makedirs(wo_folder, exist_ok=True)
        file_path = os.path.join(wo_folder, filename)
        file.save(file_path)

    # Save record to DB
    wo_file = WorkOrderFile(
        WorkOrderNo=work_order_no, filename=filename, file_path=file_path
    )
    db.session.add(wo_file)
    db.session.commit()
    return wo_file


def generate_presigned_url(file_path: str, expires_in: int = 3600) -> str:
    """
    Given a full s3://bucket/key path, generate a pre-signed URL.
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
