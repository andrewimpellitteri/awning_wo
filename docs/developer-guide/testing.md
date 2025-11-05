# Testing Guide

## Overview

The Awning Management System uses **pytest** as the testing framework with comprehensive fixtures, factories, and mocking patterns. This guide covers how to write, run, and organize tests effectively.

## Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing

# Run specific test file
pytest test/test_work_orders_routes.py

# Run specific test function
pytest test/test_work_orders_routes.py::test_create_work_order

# Run with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "work_order"

# Run tests with specific marker
pytest -m unit
pytest -m integration
```

## Test Organization

### File Structure

```
test/
├── conftest.py                              # Shared fixtures and configuration
├── test_auth.py                             # Authentication tests
├── test_work_orders_routes.py               # Work order HTTP route tests
├── test_repair_orders_routes.py             # Repair order HTTP route tests
├── test_customers_routes.py                 # Customer HTTP route tests
├── test_source_routes.py                    # Source HTTP route tests
├── test_inventory_routes.py                 # Inventory HTTP route tests
├── test_queue_routes.py                     # Queue management tests
├── test_admin_routes.py                     # Admin route tests
├── test_models.py                           # Model unit tests
├── test_utils_helpers.py                    # Utility function tests
├── test_data_processing.py                  # Data processing tests
├── test_decorators.py                       # Decorator tests
├── test_config.py                           # Configuration tests
├── test_basic_setup.py                      # Basic application setup tests
├── test_analytics_parsing.py                # Analytics parsing tests
├── test_ml_cache.py                         # ML caching tests
├── test_item_exclusion_feature.py           # Item exclusion feature tests
├── test_customer_email_bug.py               # Bug-specific tests
├── test_return_status_issue.py              # Bug-specific tests
├── test_inventory_ordering_issue_165.py     # Bug-specific tests
└── test_fuzzing.py                          # Fuzz testing
```

### Test Categories

#### Unit Tests
- Test individual functions in isolation
- Fast execution
- Mock external dependencies
- Located in: `test_utils_helpers.py`, `test_models.py`, `test_decorators.py`

#### Integration Tests
- Test routes with database operations
- Slower execution
- Use real database (in-memory SQLite)
- Located in: `test_*_routes.py` files

#### Bug Regression Tests
- Test specific bugs to prevent regression
- Named with issue numbers where applicable
- Examples: `test_customer_email_bug.py`, `test_inventory_ordering_issue_165.py`

---

## Test Fixtures

### Core Fixtures (conftest.py)

#### Application Fixtures

##### `app`
Creates a fresh Flask application for each test function.

**Scope:** Function (new app for each test)

**Configuration:**
- Uses in-memory SQLite database
- CSRF protection disabled
- Testing mode enabled
- Database tables created automatically

**Usage:**
```python
def test_something(app):
    with app.app_context():
        # Test code here
        assert app.config['TESTING'] is True
```

##### `client`
Flask test client for making HTTP requests.

**Dependencies:** `app` fixture

**Usage:**
```python
def test_list_customers(client):
    response = client.get('/customers/')
    assert response.status_code == 200
```

##### `runner`
Flask CLI runner for testing CLI commands.

**Usage:**
```python
def test_cli_command(runner):
    result = runner.invoke(args=['db', 'migrate'])
    assert result.exit_code == 0
```

##### `app_context`
Application context for testing code that needs app context.

**Usage:**
```python
def test_with_app_context(app_context):
    from flask import current_app
    assert current_app.config['TESTING'] is True
```

##### `request_context`
Request context for testing code that needs request context.

**Usage:**
```python
def test_with_request_context(request_context):
    from flask import request
    # Test request-dependent code
```

---

#### Authentication Fixtures

##### `auth_user`
Mock authenticated user for testing login_required routes.

**Usage:**
```python
def test_protected_route(client, auth_user):
    # Mocks flask_login.current_user
    response = client.get('/dashboard')
    assert response.status_code == 200
```

**Mock User Attributes:**
- `is_authenticated = True`
- `is_active = True`
- `is_anonymous = False`
- `get_id() = "test_user_id"`

##### `admin_client`
Logged-in client with admin privileges (used in route tests).

**Usage:**
```python
def test_admin_route(admin_client):
    response = admin_client.get('/admin/users')
    assert response.status_code == 200
```

**Implementation:**
```python
@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with admin privileges."""
    with app.app_context():
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("password"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()

    client.post("/login", data={"username": "admin", "password": "password"})
    yield client
    client.get("/logout")
```

---

#### Mock Fixtures

##### `mock_s3_client` (autouse)
Automatically mocks boto3 S3 client for all tests.

**Scope:** Function (automatic for all tests)

**Why Autouse?**
- Prevents tests from attempting real S3 connections
- No AWS credentials needed for tests
- Faster test execution

**Usage:**
```python
def test_file_upload(mock_s3_client):
    # S3 client is automatically mocked
    # mock_s3_client.upload_fileobj is already a MagicMock
    from utils.file_upload import save_work_order_file

    file = BytesIO(b"test content")
    file.filename = "test.pdf"
    save_work_order_file("WO000001", file)

    # Verify S3 was called
    assert mock_s3_client.upload_fileobj.called
```

##### `mock_pdf_generator`
Mocks PDF generation to return fake PDF content.

**Usage:**
```python
def test_pdf_generation(client, mock_pdf_generator):
    response = client.get('/work_orders/WO000001/pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
```

##### `mock_db_session`
Mocks SQLAlchemy session for unit tests.

**Usage:**
```python
def test_business_logic(mock_db_session):
    # db.session is mocked
    mock_db_session.add = Mock()
    mock_db_session.commit = Mock()

    # Test code
    db.session.add(work_order)
    db.session.commit()

    # Verify
    assert mock_db_session.add.called
    assert mock_db_session.commit.called
```

---

#### Model Fixtures

##### `sample_work_order`
Pre-configured WorkOrder instance for testing.

**Usage:**
```python
def test_work_order_logic(sample_work_order):
    assert sample_work_order.WorkOrderNo == "TEST001"
    assert sample_work_order.CustID == "123"
```

##### `sample_customer`
Pre-configured Customer instance.

##### `sample_source`
Pre-configured Source instance.

##### `sample_inventory`
List of pre-configured Inventory instances.

##### `sample_work_order_items`
List of pre-configured WorkOrderItem instances.

##### `database_setup`
Populates database with sample customer, source, and inventory data.

**Usage:**
```python
def test_with_data(app_context, database_setup):
    # Database is pre-populated
    customers = Customer.query.all()
    assert len(customers) > 0
```

**Cleanup:** Automatically rolls back and cleans up data after test.

---

#### Custom Sample Data Fixture

For route tests that need comprehensive data:

```python
@pytest.fixture
def sample_data(app):
    """Create comprehensive sample data for tests."""
    with app.app_context():
        # Create source
        source = Source(
            SSource="Test Source",
            SourceCity="Boston",
            SourceState="MA"
        )
        db.session.add(source)

        # Create customer
        customer = Customer(
            CustID="100",
            Name="Test Customer",
            Source="Test Source"
        )
        db.session.add(customer)

        # Create inventory
        inv = Inventory(
            InventoryKey="INV001",
            CustID="100",
            Description="Test Item"
        )
        db.session.add(inv)

        db.session.commit()
        yield

        # Cleanup
        db.session.query(Inventory).delete()
        db.session.query(Customer).delete()
        db.session.query(Source).delete()
        db.session.commit()
```

---

## Test Factories

Factories provide a flexible way to create test data with custom attributes.

### WorkOrderFactory

```python
@pytest.fixture
def work_order_factory():
    return WorkOrderFactory

def test_multiple_work_orders(work_order_factory):
    # Create single work order with defaults
    wo1 = work_order_factory.create()

    # Create work order with custom attributes
    wo2 = work_order_factory.create(
        WorkOrderNo="WO002",
        WOName="Custom Name"
    )

    # Create batch of work orders
    work_orders = work_order_factory.create_batch(count=5)
    assert len(work_orders) == 5
```

### CustomerFactory

```python
def test_customers(customer_factory):
    customer = customer_factory.create(
        CustID="200",
        Name="Custom Customer"
    )
    assert customer.CustID == "200"
```

### InventoryFactory

```python
def test_inventory(inventory_factory):
    item = inventory_factory.create(
        InventoryKey="INV_CUSTOM",
        Description="Custom Item"
    )
    assert item.InventoryKey == "INV_CUSTOM"
```

---

## Writing Tests

### Unit Test Example

Testing individual utility functions:

```python
"""test_utils_helpers.py"""
import pytest
from utils.helpers import format_phone_number, safe_bool_convert

class TestFormatPhoneNumber:
    def test_ten_digit_number(self):
        assert format_phone_number("5551234567") == "(555) 123-4567"

    def test_eleven_digit_with_one(self):
        assert format_phone_number("15551234567") == "(555) 123-4567"

    def test_already_formatted(self):
        assert format_phone_number("(555) 123-4567") == "(555) 123-4567"

    def test_empty_string(self):
        assert format_phone_number("") == ""

    def test_none(self):
        assert format_phone_number(None) == ""

class TestSafeBoolConvert:
    def test_true_values(self):
        assert safe_bool_convert(True) is True
        assert safe_bool_convert("1") is True
        assert safe_bool_convert("yes") is True
        assert safe_bool_convert(1) is True

    def test_false_values(self):
        assert safe_bool_convert(False) is False
        assert safe_bool_convert("0") is False
        assert safe_bool_convert(0) is False
        assert safe_bool_convert(None) is False

    def test_default_value(self):
        assert safe_bool_convert("invalid", default=True) is True
```

---

### Integration Test Example

Testing HTTP routes with database:

```python
"""test_work_orders_routes.py"""
import pytest
from models.work_order import WorkOrder
from extensions import db

def test_create_work_order(admin_client, sample_data):
    """Test creating a new work order via HTTP POST."""
    data = {
        'CustID': '100',
        'WOName': 'Test WO',
        'DateIn': '2024-01-15',
        'RackNo': 'A1',
        'ShipTo': 'Test Source'
    }

    response = admin_client.post('/work_orders/create', data=data, follow_redirects=True)

    # Check response
    assert response.status_code == 200
    assert b'Work order created' in response.data

    # Verify database
    wo = WorkOrder.query.filter_by(WOName='Test WO').first()
    assert wo is not None
    assert wo.CustID == '100'
    assert wo.RackNo == 'A1'

def test_list_work_orders(admin_client, app):
    """Test listing work orders."""
    with app.app_context():
        # Create test data
        wo = WorkOrder(
            WorkOrderNo="WO000001",
            CustID="100",
            WOName="Test WO"
        )
        db.session.add(wo)
        db.session.commit()

    response = admin_client.get('/work_orders/')
    assert response.status_code == 200
    assert b'WO000001' in response.data
    assert b'Test WO' in response.data

def test_delete_work_order(admin_client, app):
    """Test deleting a work order."""
    with app.app_context():
        wo = WorkOrder(
            WorkOrderNo="WO000001",
            CustID="100",
            WOName="Test WO"
        )
        db.session.add(wo)
        db.session.commit()

    response = admin_client.post('/work_orders/WO000001/delete', follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        wo = WorkOrder.query.get("WO000001")
        assert wo is None
```

---

### File Upload Test Example

```python
def test_file_upload(admin_client, mock_s3_client, app):
    """Test uploading files to work orders."""
    with app.app_context():
        # Create work order
        wo = WorkOrder(
            WorkOrderNo="WO000001",
            CustID="100",
            WOName="Test WO"
        )
        db.session.add(wo)
        db.session.commit()

    # Prepare file upload
    data = {
        'files': (BytesIO(b"test file content"), 'test.pdf')
    }

    response = admin_client.post(
        '/work_orders/WO000001/upload',
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b'File uploaded' in response.data

    # Verify S3 was called
    assert mock_s3_client.upload_fileobj.called
```

---

### Model Test Example

```python
"""test_models.py"""
import pytest
from models.work_order import WorkOrder
from datetime import date

class TestWorkOrderModel:
    def test_create_work_order(self):
        wo = WorkOrder(
            WorkOrderNo="WO000001",
            CustID="100",
            WOName="Test WO",
            DateIn=date(2024, 1, 15)
        )
        assert wo.WorkOrderNo == "WO000001"
        assert wo.CustID == "100"

    def test_work_order_repr(self):
        wo = WorkOrder(WorkOrderNo="WO000001")
        assert repr(wo) == "<WorkOrder WO000001>"

    def test_work_order_relationships(self, app):
        with app.app_context():
            # Test customer relationship
            customer = Customer(CustID="100", Name="Test")
            wo = WorkOrder(
                WorkOrderNo="WO000001",
                CustID="100",
                customer=customer
            )
            db.session.add_all([customer, wo])
            db.session.commit()

            assert wo.customer == customer
            assert customer.work_orders[0] == wo
```

---

## Mocking Patterns

### Mocking S3 Operations

```python
from unittest.mock import patch, MagicMock

def test_s3_upload():
    with patch('utils.file_upload.s3_client') as mock_s3:
        mock_s3.upload_fileobj = MagicMock()

        # Test code that uses S3
        from utils.file_upload import save_work_order_file
        file = BytesIO(b"content")
        file.filename = "test.pdf"
        save_work_order_file("WO000001", file, defer_s3_upload=False)

        # Verify S3 was called
        assert mock_s3.upload_fileobj.called
        call_args = mock_s3.upload_fileobj.call_args
        assert call_args[0][2] == "work_orders/WO000001/test.pdf"
```

### Mocking Database Queries

```python
from unittest.mock import Mock, patch

def test_query_mocking():
    with patch('models.work_order.WorkOrder.query') as mock_query:
        # Mock query results
        mock_wo = Mock()
        mock_wo.WorkOrderNo = "WO000001"
        mock_query.filter_by.return_value.first.return_value = mock_wo

        # Test code
        wo = WorkOrder.query.filter_by(WorkOrderNo="WO000001").first()
        assert wo.WorkOrderNo == "WO000001"
```

### Mocking Flask-Login

```python
from unittest.mock import patch

def test_login_required(client):
    with patch('flask_login.current_user') as mock_user:
        mock_user.is_authenticated = True
        mock_user.is_active = True

        response = client.get('/dashboard')
        assert response.status_code == 200
```

---

## Testing Best Practices

### 1. Test Independence
Each test should be completely independent of others.

**Good:**
```python
def test_create_customer(app):
    with app.app_context():
        customer = Customer(CustID="100", Name="Test")
        db.session.add(customer)
        db.session.commit()

        # Verify
        assert Customer.query.count() == 1

        # Cleanup
        db.session.delete(customer)
        db.session.commit()
```

**Bad:**
```python
# Don't rely on data from previous tests
def test_list_customers():
    # Assumes customers exist from previous test
    assert Customer.query.count() > 0  # Fragile!
```

### 2. Use Descriptive Test Names

**Good:**
```python
def test_create_work_order_with_missing_customer_id_returns_400():
    pass

def test_delete_work_order_cascades_to_items():
    pass
```

**Bad:**
```python
def test_1():
    pass

def test_stuff():
    pass
```

### 3. Test One Thing Per Test

**Good:**
```python
def test_work_order_creation():
    # Test creation only
    wo = WorkOrder(WorkOrderNo="WO000001", CustID="100")
    assert wo.WorkOrderNo == "WO000001"

def test_work_order_validation():
    # Test validation separately
    with pytest.raises(ValueError):
        wo = WorkOrder(WorkOrderNo=None)
```

**Bad:**
```python
def test_work_order():
    # Testing too many things
    wo = WorkOrder(WorkOrderNo="WO000001", CustID="100")
    assert wo.WorkOrderNo == "WO000001"

    db.session.add(wo)
    db.session.commit()

    retrieved = WorkOrder.query.get("WO000001")
    assert retrieved is not None

    db.session.delete(retrieved)
    db.session.commit()

    assert WorkOrder.query.get("WO000001") is None
```

### 4. Use Fixtures for Setup

**Good:**
```python
@pytest.fixture
def work_order_with_items(app):
    with app.app_context():
        wo = WorkOrder(WorkOrderNo="WO000001", CustID="100")
        item1 = WorkOrderItem(WorkOrderNo="WO000001", Description="Item 1")
        item2 = WorkOrderItem(WorkOrderNo="WO000001", Description="Item 2")
        db.session.add_all([wo, item1, item2])
        db.session.commit()
        yield wo
        db.session.delete(wo)
        db.session.commit()

def test_work_order_items(work_order_with_items):
    assert len(work_order_with_items.items) == 2
```

**Bad:**
```python
def test_work_order_items(app):
    with app.app_context():
        # Repeated setup in every test
        wo = WorkOrder(WorkOrderNo="WO000001", CustID="100")
        item1 = WorkOrderItem(WorkOrderNo="WO000001", Description="Item 1")
        item2 = WorkOrderItem(WorkOrderNo="WO000001", Description="Item 2")
        db.session.add_all([wo, item1, item2])
        db.session.commit()

        assert len(wo.items) == 2
```

### 5. Test Error Cases

```python
def test_create_work_order_missing_required_field(admin_client):
    """Test that missing required field returns error."""
    data = {'WOName': 'Test'}  # Missing CustID

    response = admin_client.post('/work_orders/create', data=data)
    assert response.status_code == 400
    assert b'Customer is required' in response.data

def test_delete_nonexistent_work_order(admin_client):
    """Test deleting non-existent work order returns 404."""
    response = admin_client.post('/work_orders/INVALID/delete')
    assert response.status_code == 404
```

### 6. Mock External Services

Always mock external services (S3, APIs, etc.) to:
- Make tests faster
- Make tests reliable
- Avoid dependencies on external systems
- Prevent accidental data modification

```python
@pytest.fixture(autouse=True)
def mock_s3_client(mocker):
    """Automatically mock S3 for all tests."""
    mock_s3 = MagicMock()
    mocker.patch("utils.file_upload.boto3.client", return_value=mock_s3)
    return mock_s3
```

---

## Pytest Markers

### Built-in Markers

```python
# Mark test as unit test
@pytest.mark.unit
def test_helper_function():
    pass

# Mark test as integration test
@pytest.mark.integration
def test_route():
    pass

# Mark test as slow
@pytest.mark.slow
def test_large_dataset():
    pass

# Mark test as requiring authentication
@pytest.mark.auth
def test_protected_route(auth_user):
    pass

# Skip test
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

# Expected to fail
@pytest.mark.xfail(reason="Known bug")
def test_known_issue():
    pass

# Parametrize test
@pytest.mark.parametrize("input,expected", [
    ("5551234567", "(555) 123-4567"),
    ("15551234567", "(555) 123-4567"),
    ("", ""),
])
def test_phone_format(input, expected):
    assert format_phone_number(input) == expected
```

### Running Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run everything except slow tests
pytest -m "not slow"

# Run auth tests
pytest -m auth
```

---

## Test Coverage

### Running with Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Show missing lines in terminal
pytest --cov=. --cov-report=term-missing
```

### Coverage Expectations

- **Utility functions:** 90%+ coverage
- **Routes:** 80%+ coverage
- **Models:** 80%+ coverage
- **Overall:** 75%+ coverage

### Checking Coverage for Specific Module

```bash
pytest --cov=utils.helpers --cov-report=term-missing
pytest --cov=routes.work_orders --cov-report=term-missing
```

---

## Common Testing Scenarios

### Testing Form Submissions

```python
def test_form_submission(admin_client):
    data = {
        'CustID': '100',
        'WOName': 'Test WO',
        'DateIn': '2024-01-15',
        'RushOrder': 'on',  # Checkbox
        'selected_items[]': ['INV001', 'INV002'],
        'item_qty_INV001': '2',
        'item_qty_INV002': '1',
    }

    response = admin_client.post('/work_orders/create', data=data, follow_redirects=True)
    assert response.status_code == 200
```

### Testing JSON APIs

```python
def test_api_endpoint(admin_client):
    response = admin_client.get('/api/work_orders/WO000001')
    assert response.status_code == 200

    data = response.get_json()
    assert data['WorkOrderNo'] == 'WO000001'
    assert 'CustID' in data
    assert 'WOName' in data
```

### Testing File Downloads

```python
def test_pdf_download(admin_client, app):
    with app.app_context():
        wo = WorkOrder(WorkOrderNo="WO000001", CustID="100")
        db.session.add(wo)
        db.session.commit()

    response = admin_client.get('/work_orders/WO000001/pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert 'attachment' in response.headers.get('Content-Disposition', '')
```

### Testing Flash Messages

```python
def test_flash_messages(admin_client):
    response = admin_client.post('/work_orders/create', data={}, follow_redirects=True)
    assert b'Customer is required' in response.data
```

### Testing Redirects

```python
def test_redirect(admin_client):
    response = admin_client.post('/work_orders/create', data=valid_data)
    assert response.status_code == 302
    assert '/work_orders/' in response.location

def test_redirect_follow(admin_client):
    response = admin_client.post('/work_orders/create', data=valid_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Work order created' in response.data
```

---

## Debugging Tests

### Print Debugging

```python
def test_something(app):
    with app.app_context():
        wo = WorkOrder.query.first()
        print(f"Work Order: {wo}")  # Will show in pytest output with -s flag
        assert wo is not None
```

```bash
# Run with print output
pytest -s test/test_work_orders_routes.py
```

### Using pytest.set_trace()

```python
def test_debug(app):
    with app.app_context():
        wo = WorkOrder.query.first()
        pytest.set_trace()  # Debugger breakpoint
        assert wo is not None
```

### Verbose Output

```bash
# Show test names as they run
pytest -v

# Show extra test summary
pytest -v --tb=short

# Show full error traceback
pytest -v --tb=long
```

### Failed Test Output

```bash
# Show only failed tests
pytest --lf

# Run failed tests first
pytest --ff

# Stop on first failure
pytest -x

# Stop after N failures
pytest --maxfail=3
```

---

## Continuous Integration

### Running Tests in CI

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run tests with coverage
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term-missing

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

---

## See Also

- [Utility Functions Reference](./utility-functions.md) - Functions to test
- [Database Schema](./database-schema.md) - Models to test
- [Error Handling](./error-handling.md) - Testing error cases
- [CLAUDE.md](../../CLAUDE.md) - Main project documentation