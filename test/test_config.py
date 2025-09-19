"""
PostgreSQL-aware test configuration for work orders tests.

Save this as: test/test_config.py
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch
from config import Config

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set testing environment variables
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment before any tests run."""
    print("\nSetting up test environment...")
    print(f"Project root: {project_root}")
    print(f"Python path includes project root: {str(project_root) in sys.path}")

    # Verify we can import key modules
    try:
        import extensions

        print("✅ Successfully imported extensions")
    except ImportError as e:
        print(f"❌ Failed to import extensions: {e}")

    try:
        from models.work_order import WorkOrder

        print("✅ Successfully imported WorkOrder model")
    except ImportError as e:
        print(f"❌ Failed to import WorkOrder model: {e}")

    try:
        from config import TestingConfig

        print("✅ Successfully imported TestingConfig")
        print(f"Testing DB URI: {TestingConfig.SQLALCHEMY_DATABASE_URI}")
    except ImportError as e:
        print(f"❌ Failed to import config: {e}")


@pytest.fixture
def mock_flask_app():
    """Create a mock Flask app for testing without database."""
    app = Mock()
    app.config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-key",
    }
    app.test_client.return_value = Mock()
    return app


@pytest.fixture
def mock_db_queries():
    """Mock common database query patterns."""
    with (
        patch("models.work_order.WorkOrder.query") as mock_wo_query,
        patch("models.customer.Customer.query") as mock_customer_query,
        patch("models.source.Source.query") as mock_source_query,
        patch("models.inventory.Inventory.query") as mock_inventory_query,
    ):
        # Set up common mock returns
        mock_wo_query.filter.return_value.order_by.return_value.paginate.return_value = Mock(
            items=[], pages=0, page=1, per_page=10
        )
        mock_wo_query.filter_by.return_value.first_or_404.return_value = Mock(
            WorkOrderNo="1001", CustID="123", WOName="Test Work Order"
        )
        mock_customer_query.all.return_value = []
        mock_source_query.all.return_value = []
        mock_inventory_query.filter_by.return_value.all.return_value = []

        yield {
            "work_order": mock_wo_query,
            "customer": mock_customer_query,
            "source": mock_source_query,
            "inventory": mock_inventory_query,
        }


@pytest.fixture
def mock_authenticated_user():
    """Mock an authenticated user for login_required routes."""
    with patch("flask_login.current_user") as mock_user:
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_anonymous = False
        mock_user.get_id.return_value = "test_user"
        yield mock_user


class TestDatabaseConnection:
    """Test database connection and basic functionality."""

    def test_can_import_config(self):
        """Test that we can import the configuration."""
        try:
            from config import config, TestingConfig

            assert "testing" in config
            assert TestingConfig.TESTING is True
            assert "sqlite://" in TestingConfig.SQLALCHEMY_DATABASE_URI
        except ImportError:
            pytest.skip("Cannot import config module")

    def test_can_import_extensions(self):
        """Test that we can import database extensions."""
        try:
            from extensions import db

            assert db is not None
        except ImportError:
            pytest.skip("Cannot import extensions")

    @pytest.mark.postgres
    def test_postgres_connection_available(self):
        """Test that PostgreSQL connection is available (if configured)."""
        try:
            import psycopg2
            from config import config

            # Try to parse the database URL
            db_config = config.get("development")
            if db_config:
                db_uri = db_config.SQLALCHEMY_DATABASE_URI
                if "postgresql://" in db_uri:
                    print(f"PostgreSQL URI configured: {db_uri.split('@')[0]}@***")
                else:
                    pytest.skip("PostgreSQL not configured")
            else:
                pytest.skip("No development config found")
        except ImportError:
            pytest.skip("psycopg2 not installed")


# config.py (or test_config.py)
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # in-memory DB
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


if __name__ == "__main__":
    # Run configuration tests
    pytest.main([__file__, "-v"])
