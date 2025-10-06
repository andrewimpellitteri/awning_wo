import os
from datetime import timedelta


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
        "pool_size": 10,
        "max_overflow": 20,
        "connect_args": {"connect_timeout": 10},
    }

    # Database URI logic
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or (
            os.environ.get("RDS_HOSTNAME")
            and f"postgresql://{os.environ.get('RDS_USERNAME')}:{os.environ.get('RDS_PASSWORD')}@"
            f"{os.environ.get('RDS_HOSTNAME')}:{os.environ.get('RDS_PORT', 5432)}/"
            f"{os.environ.get('RDS_DB_NAME')}"
        )
        or f"postgresql://{os.environ.get('POSTGRES_USER', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PASSWORD', 'password')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{os.environ.get('POSTGRES_DB', 'clean_repair')}"
    )

    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    SAIL_ORDER_SOURCES = [
        "Aaron's Canvas & Sails LLC",
        "ACE Sails",
        "Aurora Sails",
        "Bareboat Sailing Charters",
        "Bohndell Sails & Rigging",
        "Doyle",
        "Doyle/Island Nautical Canvas",
        "Fairclough",
        "Neil Pryde Sails",
        "NEKA",
        "Northeast Sail Loft",
        "NS CT",
        "NS LI",
        "NS RI",
        "NS TOLEDO",
        "Ocean Rigging",
        "OneSails/Doyle",
        "Port Niantic Marina",
        "QS CT (Shore)",
        "QS NY",
        "QS RI (Thurston)",
        "Sail Repair Co.",
        "Sperry Sails",
        "Thurston Sails",
        "Tim's Sail Loft",
        "Tomelia Sails & Canvas",
        "UK CI",
        "UK Clinton",
        "UK Cycle",
        "UK Essex",
        "UK Halsey",
        "UK Metro",
        "UK N",
        "UK RI",
        "Ullman Sails",
        "Wm. Mills & Co.",
        "Z Sails",
    ]

    # Cache configuration
    CACHE_TYPE = "SimpleCache"  # In-memory, thread-safe
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    CACHE_KEY_PREFIX = "awning_"


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
    SECRET_KEY = "test-secret-key-for-testing-only"

    # Disable caching in tests to avoid stale data
    CACHE_TYPE = "NullCache"  # No caching during tests
    CACHE_NO_NULL_WARNING = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig,
}
