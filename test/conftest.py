"""
Pytest configuration file for work orders tests.

This file contains shared fixtures and configuration for all tests.
"""

import pytest
import sys
import tempfile
import os
from unittest.mock import Mock, patch
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

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


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    # Import your app
    try:
        from app import app as flask_app

        # Override configuration for testing
        flask_app.config.update(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # Use in-memory SQLite for tests
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
            }
        )

    except ImportError:
        # Fallback: create minimal Flask app if your app structure is different
        flask_app = Flask(__name__)
        flask_app.config.from_object(TestingConfig)

        # Initialize extensions
        db.init_app(flask_app)
        login_manager.init_app(flask_app)

    with flask_app.app_context():
        # Create all tables for testing
        db.create_all()
        yield flask_app
        # Clean up
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner for CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """Create application context."""
    with app.app_context():
        yield app


@pytest.fixture
def request_context(app):
    """Create request context."""
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

    # Mock flask_login's current_user
    monkeypatch.setattr("flask_login.current_user", mock_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: mock_user)

    return mock_user


@pytest.fixture
def sample_work_order():
    """Create a sample work order for testing."""
    return WorkOrder(
        WorkOrderNo="TEST001",
        CustID="123",
        WOName="Test Work Order",
        DateIn="2024-01-15",
        RackNo="A1",
        SpecialInstructions="Test instructions",
        RepairsNeeded="Minor repairs",
        RushOrder="0",
        DateRequired="2024-01-30",
        ShipTo="TEST_SOURCE",
    )


@pytest.fixture
def sample_customer():
    """Create a sample customer for testing."""
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
    """Create a sample source for testing."""
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
    """Create sample inventory items for testing."""
    return [
        Inventory(
            InventoryKey="INV_TEST001",
            CustID="123",
            Description="Test Awning",
            Material="Canvas",
            Color="Red",
            Condition="Good",
            SizeWgt="10x12",
            Price="150.00",
            Qty="5",
        ),
        Inventory(
            InventoryKey="INV_TEST002",
            CustID="123",
            Description="Test Umbrella",
            Material="Polyester",
            Color="Blue",
            Condition="Excellent",
            SizeWgt="8x8",
            Price="75.00",
            Qty="3",
        ),
    ]


@pytest.fixture
def sample_work_order_items():
    """Create sample work order items for testing."""
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
    """Set up database with sample data."""
    # Add sample data to database
    db.session.add(sample_customer)
    db.session.add(sample_source)

    for item in sample_inventory:
        db.session.add(item)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        pytest.skip(f"Database setup failed: {e}")

    yield

    # Cleanup after test
    try:
        db.session.rollback()
        db.session.query(Inventory).delete()
        db.session.query(WorkOrderItem).delete()
        db.session.query(WorkOrder).delete()
        db.session.query(Source).delete()
        db.session.query(Customer).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.fixture
def mock_pdf_generator():
    """Mock PDF generation functionality."""
    from io import BytesIO

    def fake_pdf_content():
        return BytesIO(b"%PDF-1.4 fake pdf content")

    with patch(
        "work_order_pdf.generate_work_order_pdf", return_value=fake_pdf_content()
    ):
        yield


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    with patch("extensions.db.session") as mock_session:
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        mock_session.flush = Mock()
        mock_session.delete = Mock()
        mock_session.query = Mock()
        yield mock_session


# Custom markers for different test types
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (slower, with database)",
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running tests")
    config.addinivalue_line("markers", "auth: marks tests that require authentication")
    config.addinivalue_line("markers", "postgres: marks tests that require PostgreSQL")


# Pytest hooks for test execution
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add 'unit' marker to tests with 'unit' in the name
        if "unit" in item.nodeid.lower():
            item.add_marker(pytest.mark.unit)

        # Add 'integration' marker to integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)

        # Add 'auth' marker to tests that use auth_user fixture
        if "auth_user" in item.fixturenames:
            item.add_marker(pytest.mark.auth)


# Test data factories
class WorkOrderFactory:
    """Factory for creating test work orders."""

    @staticmethod
    def create(**kwargs):
        """Create a work order with default values."""
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
        """Create multiple work orders."""
        return [
            WorkOrderFactory.create(WorkOrderNo=f"WO{str(i).zfill(3)}", **kwargs)
            for i in range(1, count + 1)
        ]


class CustomerFactory:
    """Factory for creating test customers."""

    @staticmethod
    def create(**kwargs):
        """Create a customer with default values."""
        defaults = {
            "CustID": "123",
            "Name": "Factory Test Customer",
            "Source": "TEST_SOURCE",
            "Phone": "555-0123",
        }
        defaults.update(kwargs)
        return Customer(**defaults)


class InventoryFactory:
    """Factory for creating test inventory items."""

    @staticmethod
    def create(**kwargs):
        """Create an inventory item with default values."""
        defaults = {
            "InventoryKey": "INV_FACTORY001",
            "CustID": "123",
            "Description": "Factory Test Item",
            "Material": "Canvas",
            "Qty": "10",
        }
        defaults.update(kwargs)
        return Inventory(**defaults)


# Make factories available to tests
@pytest.fixture
def work_order_factory():
    """Provide WorkOrderFactory to tests."""
    return WorkOrderFactory


@pytest.fixture
def customer_factory():
    """Provide CustomerFactory to tests."""
    return CustomerFactory


@pytest.fixture
def inventory_factory():
    """Provide InventoryFactory to tests."""
    return InventoryFactory


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()

    # Import your app factory
    try:
        from app import app as flask_app

        # Configure for testing
        flask_app.config.update(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
            }
        )

    except ImportError:
        # Fallback: create minimal Flask app if your app structure is different
        flask_app = Flask(__name__)
        flask_app.config.update(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
            }
        )

        # Initialize extensions
        db.init_app(flask_app)
        login_manager.init_app(flask_app)

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner for CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """Create application context."""
    with app.app_context():
        yield app


@pytest.fixture
def request_context(app):
    """Create request context."""
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

    def mock_current_user():
        return mock_user

    # Mock flask_login's current_user
    monkeypatch.setattr("flask_login.current_user", mock_user)
    monkeypatch.setattr("flask_login.utils._get_user", lambda: mock_user)

    return mock_user


@pytest.fixture
def sample_work_order():
    """Create a sample work order for testing."""
    return WorkOrder(
        WorkOrderNo="TEST001",
        CustID="123",
        WOName="Test Work Order",
        DateIn="2024-01-15",
        RackNo="A1",
        SpecialInstructions="Test instructions",
        RepairsNeeded="Minor repairs",
        RushOrder="0",
        DateRequired="2024-01-30",
        ShipTo="TEST_SOURCE",
    )


@pytest.fixture
def sample_customer():
    """Create a sample customer for testing."""
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
    """Create a sample source for testing."""
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
    """Create sample inventory items for testing."""
    return [
        Inventory(
            InventoryKey="INV_TEST001",
            CustID="123",
            Description="Test Awning",
            Material="Canvas",
            Color="Red",
            Condition="Good",
            SizeWgt="10x12",
            Price="150.00",
            Qty="5",
        ),
        Inventory(
            InventoryKey="INV_TEST002",
            CustID="123",
            Description="Test Umbrella",
            Material="Polyester",
            Color="Blue",
            Condition="Excellent",
            SizeWgt="8x8",
            Price="75.00",
            Qty="3",
        ),
    ]


@pytest.fixture
def sample_work_order_items():
    """Create sample work order items for testing."""
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
    """Set up database with sample data."""
    # Add sample data to database
    db.session.add(sample_customer)
    db.session.add(sample_source)

    for item in sample_inventory:
        db.session.add(item)

    db.session.commit()

    yield

    # Cleanup after test
    db.session.rollback()
    db.session.query(Inventory).delete()
    db.session.query(WorkOrderItem).delete()
    db.session.query(WorkOrder).delete()
    db.session.query(Source).delete()
    db.session.query(Customer).delete()
    db.session.commit()


@pytest.fixture
def mock_pdf_generator():
    """Mock PDF generation functionality."""
    from io import BytesIO

    def fake_pdf_content():
        return BytesIO(b"%PDF-1.4 fake pdf content")

    with patch(
        "work_order_pdf.generate_work_order_pdf", return_value=fake_pdf_content()
    ):
        yield


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    with patch("extensions.db.session") as mock_session:
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        mock_session.flush = Mock()
        mock_session.delete = Mock()
        mock_session.query = Mock()
        yield mock_session


# Custom markers for different test types
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (slower, with database)",
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running tests")
    config.addinivalue_line("markers", "auth: marks tests that require authentication")


# Pytest hooks for test execution
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add 'unit' marker to tests with 'unit' in the name
        if "unit" in item.nodeid.lower():
            item.add_marker(pytest.mark.unit)

        # Add 'integration' marker to integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)

        # Add 'auth' marker to tests that use auth_user fixture
        if "auth_user" in item.fixturenames:
            item.add_marker(pytest.mark.auth)


# Test data factories
class WorkOrderFactory:
    """Factory for creating test work orders."""

    @staticmethod
    def create(**kwargs):
        """Create a work order with default values."""
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
        """Create multiple work orders."""
        return [
            WorkOrderFactory.create(WorkOrderNo=f"WO{str(i).zfill(3)}", **kwargs)
            for i in range(1, count + 1)
        ]


class CustomerFactory:
    """Factory for creating test customers."""

    @staticmethod
    def create(**kwargs):
        """Create a customer with default values."""
        defaults = {
            "CustID": "123",
            "Name": "Factory Test Customer",
            "Source": "TEST_SOURCE",
            "Phone": "555-0123",
        }
        defaults.update(kwargs)
        return Customer(**defaults)


class InventoryFactory:
    """Factory for creating test inventory items."""

    @staticmethod
    def create(**kwargs):
        """Create an inventory item with default values."""
        defaults = {
            "InventoryKey": "INV_FACTORY001",
            "CustID": "123",
            "Description": "Factory Test Item",
            "Material": "Canvas",
            "Qty": "10",
        }
        defaults.update(kwargs)
        return Inventory(**defaults)


# Make factories available to tests
@pytest.fixture
def work_order_factory():
    """Provide WorkOrderFactory to tests."""
    return WorkOrderFactory


@pytest.fixture
def customer_factory():
    """Provide CustomerFactory to tests."""
    return CustomerFactory


@pytest.fixture
def inventory_factory():
    """Provide InventoryFactory to tests."""
    return InventoryFactory
