"""
Pytest configuration file for work orders tests.

Contains shared fixtures, factories, mocks, and configuration for all tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import your app components
try:
    from extensions import db, login_manager
    from models.work_order import WorkOrder, WorkOrderItem
    from models.customer import Customer
    from models.source import Source
    from models.inventory import Inventory
    from config import TestingConfig
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path}")
    raise

# Set mock AWS credentials to prevent import errors
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_S3_BUCKET"] = "testing"


# --------------------
# Fixtures
# --------------------


@pytest.fixture(autouse=True)
def mock_s3_client(mocker):
    """Automatically mock boto3 S3 client for all tests."""
    mock_s3 = MagicMock()
    mocker.patch("utils.file_upload.boto3.client", return_value=mock_s3)
    return mock_s3


@pytest.fixture(scope="function")
def app():
    """Fixture for creating a new Flask app for each test function."""
    # Import the factory and config here to avoid circular dependencies
    from app import create_app
    from config import TestingConfig

    # Create the app with test config
    app = create_app(config_class=TestingConfig)
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # Ensure in-memory DB
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for tests
            "LOGIN_DISABLED": False,  # Ensure login is not disabled
        }
    )

    # Establish an application context before creating the database tables
    with app.app_context():
        # Create the database tables
        db.create_all()

        # Yield the app to the test
        yield app

        # Teardown: clean up the database
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Flask CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """Application context."""
    with app.app_context():
        yield app


@pytest.fixture
def request_context(app):
    """Request context."""
    with app.test_request_context():
        yield


@pytest.fixture
def auth_user(monkeypatch):
    """Mock authenticated user for login_required decorator."""
    mock_user = Mock()
    mock_user.is_authenticated = True
    mock_user.is_active = True
    mock_user.is_anonymous = False
    mock_user.get_id.return_value = "test_user_id"

    monkeypatch.setattr("flask_login.current_user", mock_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: mock_user)
    return mock_user


@pytest.fixture
def sample_work_order():
    return WorkOrder(
        WorkOrderNo="TEST001",
        CustID="123",
        WOName="Test Work Order",
        DateIn=date(2024, 1, 15),
        RackNo="A1",
        SpecialInstructions="Test instructions",
        RepairsNeeded="Minor repairs",
        RushOrder=False,
        DateRequired=date(2024, 1, 30),
        ShipTo="TEST_SOURCE",
    )


@pytest.fixture
def sample_customer():
    return Customer(
        CustID="123",
        Name="Test Customer Inc.",
        Source="TEST_SOURCE",
        Phone="555-0123",
        Email="test@example.com",
        Address="123 Test Street",
        City="Test City",
        State="TS",
        Zip="12345",
    )


@pytest.fixture
def sample_source():
    return Source(
        SSource="TEST_SOURCE",
        Name="Test Source Company",
        Address="456 Source Avenue",
        City="Source City",
        State="SC",
        Zip="67890",
        Phone="555-0456",
        Email="source@example.com",
    )


@pytest.fixture
def sample_inventory():
    return [
        Inventory(
            InventoryKey="INV_TEST001",
            CustID="123",
            Description="Test Awning",
            Material="Canvas",
            Color="Red",
            Condition="Good",
            SizeWgt="10x12",
            Price=150.00,
            Qty=5,
        ),
        Inventory(
            InventoryKey="INV_TEST002",
            CustID="123",
            Description="Test Umbrella",
            Material="Polyester",
            Color="Blue",
            Condition="Excellent",
            SizeWgt="8x8",
            Price=75.00,
            Qty=3,
        ),
    ]


@pytest.fixture
def sample_work_order_items():
    return [
        WorkOrderItem(
            WorkOrderNo="TEST001",
            CustID="123",
            Description="Test Awning",
            Material="Canvas",
            Qty="2",
            Condition="Good",
            Color="Red",
            SizeWgt="10x12",
            Price="150.00",
        ),
        WorkOrderItem(
            WorkOrderNo="TEST001",
            CustID="123",
            Description="Test Umbrella",
            Material="Polyester",
            Qty="1",
            Condition="Excellent",
            Color="Blue",
            SizeWgt="8x8",
            Price="75.00",
        ),
    ]


@pytest.fixture
def database_setup(app_context, sample_customer, sample_source, sample_inventory):
    """Populate database with sample data."""
    db.session.add(sample_customer)
    db.session.add(sample_source)
    for item in sample_inventory:
        db.session.add(item)
    db.session.commit()
    yield
    db.session.rollback()
    db.session.query(Inventory).delete()
    db.session.query(WorkOrderItem).delete()
    db.session.query(WorkOrder).delete()
    db.session.query(Source).delete()
    db.session.query(Customer).delete()
    db.session.commit()


@pytest.fixture
def mock_pdf_generator():
    """Mock PDF generation."""
    from io import BytesIO

    def fake_pdf_content():
        return BytesIO(b"%PDF-1.4 fake pdf content")

    with patch(
        "work_order_pdf.generate_work_order_pdf", return_value=fake_pdf_content()
    ):
        yield


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy session."""
    with patch("extensions.db.session") as mock_session:
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        mock_session.flush = Mock()
        mock_session.delete = Mock()
        mock_session.query = Mock()
        yield mock_session


# --------------------
# Factories
# --------------------
class WorkOrderFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "WorkOrderNo": "WO001",
            "CustID": "123",
            "WOName": "Factory Test Work Order",
            "DateIn": "2024-01-15",
            "RackNo": "A1",
            "ShipTo": "TEST_SOURCE",
        }
        defaults.update(kwargs)
        return WorkOrder(**defaults)

    @staticmethod
    def create_batch(count=5, **kwargs):
        return [
            WorkOrderFactory.create(WorkOrderNo=f"WO{str(i).zfill(3)}", **kwargs)
            for i in range(1, count + 1)
        ]


class CustomerFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "CustID": "123",
            "Name": "Factory Test Customer",
            "Source": "TEST_SOURCE",
            "Phone": "555-0123",
        }
        defaults.update(kwargs)
        return Customer(**defaults)


class InventoryFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "InventoryKey": "INV_FACTORY001",
            "CustID": "123",
            "Description": "Factory Test Item",
            "Material": "Canvas",
            "Qty": "10",
        }
        defaults.update(kwargs)
        return Inventory(**defaults)


@pytest.fixture
def work_order_factory():
    return WorkOrderFactory


@pytest.fixture
def customer_factory():
    return CustomerFactory


@pytest.fixture
def inventory_factory():
    return InventoryFactory


# --------------------
# Pytest markers and hooks
# --------------------
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast, isolated tests")
    config.addinivalue_line("markers", "integration: slower, database tests")
    config.addinivalue_line("markers", "slow: slow running tests")
    config.addinivalue_line("markers", "auth: tests that require authentication")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "unit" in item.nodeid.lower():
            item.add_marker(pytest.mark.unit)
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)
        if "auth_user" in item.fixturenames:
            item.add_marker(pytest.mark.auth)
