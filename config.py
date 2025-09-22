import os
from datetime import timedelta

TEST_MIGRATION = True


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-key-change-in-production"
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    CSV_DATA_PATH = os.environ.get("CSV_DATA_PATH", "data")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    SESSION_COOKIE_HTTPONLY = True

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,  # Keep 10 persistent connections
        "max_overflow": 20,  # Allow up to 20 extra connections if needed
        "connect_args": {"connect_timeout": 10},
    }

    # Compute database URI immediately
    if TEST_MIGRATION:
        SQLALCHEMY_DATABASE_URI = (
            os.environ.get("RDS_HOSTNAME")
            and f"postgresql://{os.environ.get('RDS_USERNAME')}:{os.environ.get('RDS_PASSWORD')}@"
            f"{os.environ.get('RDS_HOSTNAME')}:{os.environ.get('RDS_PORT', 5432)}/"
            f"{os.environ.get('RDS_DB_NAME')}"
            or os.environ.get("DATABASE_URL")
            or f"postgresql://{os.environ.get('POSTGRES_USER', 'postgres')}:"
            f"{os.environ.get('POSTGRES_PASSWORD', 'password')}@"
            f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
            f"{os.environ.get('POSTGRES_PORT', '5432')}/"
            f"{os.environ.get('POSTGRES_DB', 'migrated_db')}"
        )

    else:
        SQLALCHEMY_DATABASE_URI = (
            os.environ.get("RDS_HOSTNAME")
            and f"postgresql://{os.environ.get('RDS_USERNAME')}:{os.environ.get('RDS_PASSWORD')}@"
            f"{os.environ.get('RDS_HOSTNAME')}:{os.environ.get('RDS_PORT', 5432)}/"
            f"{os.environ.get('RDS_DB_NAME')}"
            or os.environ.get("DATABASE_URL")
            or f"postgresql://{os.environ.get('POSTGRES_USER', 'postgres')}:"
            f"{os.environ.get('POSTGRES_PASSWORD', 'password')}@"
            f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
            f"{os.environ.get('POSTGRES_PORT', '5432')}/"
            f"{os.environ.get('POSTGRES_DB', 'Clean_Repair')}"
        )

    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = "development"


class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = "production"


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig,
}
