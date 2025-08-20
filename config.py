import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        basedir, "Clean_Repair.sqlite"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or "uploads"
    CSV_DATA_PATH = os.environ.get("CSV_DATA_PATH") or "data"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Pagination
    ITEMS_PER_PAGE = 50

    # Photo settings
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
