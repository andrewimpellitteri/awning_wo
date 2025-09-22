import os
from werkzeug.utils import secure_filename
from models.work_order_file import WorkOrderFile
from extensions import db
import boto3


UPLOAD_FOLDER = "uploads/work_orders"  # make sure this folder exists
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "txt", "csv"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


S3_BUCKET = "your-bucket-name"
s3_client = boto3.client("s3")


def save_work_order_file(work_order_no, file, to_s3=False):
    filename = secure_filename(file.filename)
    if to_s3:
        s3_key = f"work_orders/{work_order_no}/{filename}"
        s3_client.upload_fileobj(file, S3_BUCKET, s3_key)
        file_path = f"s3://{S3_BUCKET}/{s3_key}"
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
