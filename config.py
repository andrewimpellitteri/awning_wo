import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # PostgreSQL connection (use environment variables)
    POSTGRES_USER = os.environ.get("POSTGRES_USER", "pguser")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "Clean_Repair")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
    POSTGRES_SOCKET_DIR = os.environ.get(
        "POSTGRES_SOCKET_DIR"
    )  # optional unix socket path

    if POSTGRES_SOCKET_DIR:
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}/{POSTGRES_DB}?host={POSTGRES_SOCKET_DIR}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )

    # Fallback to SQLite if DATABASE_URL is not set or PostgreSQL fails
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    # if not SQLALCHEMY_DATABASE_URI:
    #     SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
    #         basedir, "Clean_Repair.sqlite"
    #     )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or "uploads"
    CSV_DATA_PATH = os.environ.get("CSV_DATA_PATH") or "data"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Pagination
    ITEMS_PER_PAGE = 50

    # Photo settings
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
