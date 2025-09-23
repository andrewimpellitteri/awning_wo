import os
from werkzeug.utils import secure_filename
from models.work_order_file import WorkOrderFile
from extensions import db
import boto3

UPLOAD_FOLDER = "uploads/work_orders"  # local fallback
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "txt", "csv"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Use environment variables (works both locally and on EB)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


def save_work_order_file(work_order_no, file, to_s3=True):
    print("AWS_ACCESS_KEY_ID:", AWS_ACCESS_KEY_ID)
    print("AWS_SECRET_ACCESS_KEY:", AWS_SECRET_ACCESS_KEY)
    print("AWS_S3_BUCKET:", AWS_S3_BUCKET)

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
