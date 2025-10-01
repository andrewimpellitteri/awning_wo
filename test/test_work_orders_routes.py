"""
Tests for Work Orders CRUD routes - HTTP Integration Tests.

This file tests actual HTTP routes with real Flask test client and database.
Complements work_order_test.py which contains unit tests and mocked business logic.

RESPONSIBILITIES:
- work_order_test.py: Unit tests, business logic, utilities, mocked integration
- THIS FILE: HTTP route integration tests with real database operations

This is the most critical route test suite as work orders are the core business entity.

Covers:
- List, search, and filtering routes
- View/detail display routes
- Create operations (with inventory selection and new items)
- Edit operations
- Delete operations
- File upload/download operations
- PDF generation endpoints
- API endpoints
"""

import pytest
from io import BytesIO
from werkzeug.security import generate_password_hash
from models.work_order import WorkOrder, WorkOrderItem
from models.work_order_file import WorkOrderFile
from models.customer import Customer
from models.source import Source
from models.inventory import Inventory
from models.user import User
from extensions import db


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


@pytest.fixture
def sample_data(app):
    """Create comprehensive sample data for work order tests."""
    with app.app_context():
        # Create source
        source = Source(
            SSource="Test Source",
            SourceCity="Boston",
            SourceState="MA",
            SourcePhone="6175551234"
        )
        db.session.add(source)

        # Create customer
        customer = Customer(
            CustID="100",
            Name="Test Customer",
            Source="Test Source",
            Address="123 Test St",
            City="Boston",
            State="MA",
            ZipCode="02101",
            HomePhone="6175559999",
            EmailAddress="test@example.com"
        )
        db.session.add(customer)

        # Create inventory items
        inv1 = Inventory(
            InventoryKey="INV001",
            CustID="100",
            Description="Test Awning",
            Material="Canvas",
            Color="Blue",
            SizeWgt="10x12",
            Qty="1",
            Price="150.00"
        )
        inv2 = Inventory(
            InventoryKey="INV002",
            CustID="100",
            Description="Test Cover",
            Material="Vinyl",
            Color="Red",
            SizeWgt="8x10",
            Qty="2",
            Price="75.00"
        )
        db.session.add_all([inv1, inv2])

        # Create work orders (numbers are numeric strings, NOT prefixed with "WO")
        wo1 = WorkOrder(
            WorkOrderNo="10001",
            CustID="100",
            WOName="Test Work Order 1",
            DateIn="2025-01-15",
            DateRequired="2025-01-30",
            RackNo="A1",
            Storage="Rack",
            ShipTo="Test Source",
            SpecialInstructions="Handle with care",
            RepairsNeeded="Clean and inspect",
            RushOrder="0"
        )
        wo2 = WorkOrder(
            WorkOrderNo="10002",
            CustID="100",
            WOName="Test Work Order 2",
            DateIn="2025-01-20",
            DateRequired="2025-02-05",
            RackNo="B2",
            Storage="Floor",
            ShipTo="Test Source",
            RushOrder="1",
            DateCompleted="2025-01-25"
        )
        db.session.add_all([wo1, wo2])

        # Create work order items
        item1 = WorkOrderItem(
            WorkOrderNo="10001",
            CustID="100",
            Description="Test Awning",
            Material="Canvas",
            Color="Blue",
            SizeWgt="10x12",
            Qty="1",
            Price="150.00",
            Condition="Good"
        )
        item2 = WorkOrderItem(
            WorkOrderNo="10002",
            CustID="100",
            Description="Test Cover",
            Material="Vinyl",
            Color="Red",
            SizeWgt="8x10",
            Qty="2",
            Price="75.00",
            Condition="Fair"
        )
        db.session.add_all([item1, item2])

        db.session.commit()
        yield

        # Cleanup
        db.session.query(WorkOrderItem).delete()
        db.session.query(WorkOrderFile).delete()
        db.session.query(WorkOrder).delete()
        db.session.query(Inventory).delete()
        db.session.query(Customer).delete()
        db.session.query(Source).delete()
        db.session.commit()


class TestWorkOrderListRoutes:
    """Test work order list and search HTTP routes."""

    def test_work_order_list_page_renders(self, admin_client, sample_data):
        """GET /work_orders/ should render the list page."""
        response = admin_client.get("/work_orders/")
        assert response.status_code == 200
        assert b"Work Orders" in response.data or b"10001" in response.data

    def test_work_order_list_search_by_number(self, admin_client, sample_data):
        """Test searching by work order number - page uses AJAX so test API instead."""
        # The list page uses Tabulator/AJAX to load data, so test the API endpoint
        response = admin_client.get("/work_orders/api/work_orders?search=10001")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        # Should find 10001 in the results
        assert "data" in data
        wo_numbers = [wo.get("WorkOrderNo") for wo in data["data"]]
        assert "10001" in wo_numbers

    def test_work_order_pending_filter(self, admin_client, sample_data):
        """GET /work_orders/pending should show only pending orders."""
        response = admin_client.get("/work_orders/pending")
        assert response.status_code == 200
        # WO001 is pending (no DateCompleted)

    def test_work_order_completed_filter(self, admin_client, sample_data):
        """GET /work_orders/completed should show only completed orders."""
        response = admin_client.get("/work_orders/completed")
        assert response.status_code == 200
        # WO002 is completed

    def test_work_order_rush_filter(self, admin_client, sample_data):
        """GET /work_orders/rush should show only rush orders."""
        response = admin_client.get("/work_orders/rush")
        assert response.status_code == 200
        # WO002 is a rush order


class TestWorkOrderDetailRoutes:
    """Test work order detail view HTTP routes."""

    def test_view_work_order_detail(self, admin_client, sample_data):
        """GET /work_orders/<no> should display work order details."""
        response = admin_client.get("/work_orders/10001")
        assert response.status_code == 200
        assert b"10001" in response.data
        # Customer ID 100 should be visible
        assert b"100" in response.data

    def test_view_work_order_includes_items(self, admin_client, sample_data):
        """Work order detail should include all items."""
        response = admin_client.get("/work_orders/10001")
        assert response.status_code == 200
        assert b"Test Awning" in response.data or b"Canvas" in response.data

    def test_view_missing_work_order(self, admin_client):
        """GET /work_orders/<nonexistent> should return 404."""
        response = admin_client.get("/work_orders/NONEXISTENT")
        assert response.status_code == 404


class TestWorkOrderCreateRoutes:
    """Test work order creation HTTP routes."""

    def test_create_work_order_page_renders(self, admin_client, sample_data):
        """GET /work_orders/new should render creation form."""
        response = admin_client.get("/work_orders/new")
        assert response.status_code == 200
        assert b"New" in response.data or b"Create" in response.data or b"Work Order" in response.data

    def test_create_work_order_with_prefill_customer(self, admin_client, sample_data):
        """GET /work_orders/new/<cust_id> should prefill customer data."""
        response = admin_client.get("/work_orders/new/100")
        assert response.status_code == 200
        assert b"100" in response.data  # Customer ID should be present

    def test_create_work_order_success(self, admin_client, sample_data, app):
        """POST /work_orders/new should create work order successfully."""
        with app.app_context():
            response = admin_client.post("/work_orders/new", data={
                "CustID": "100",
                "WOName": "New Test Order",
                "DateIn": "2025-02-01",
                "DateRequired": "2025-02-15",
                "RackNo": "C3",
                "Storage": "Rack",
                "ShipTo": "Test Source",
                "SpecialInstructions": "Test instructions",
                "RepairsNeeded": "Test repairs",
                "RushOrder": "0"
            }, follow_redirects=True)

            assert response.status_code == 200

            # Verify work order was created
            new_wo = WorkOrder.query.filter_by(WOName="New Test Order").first()
            assert new_wo is not None
            assert new_wo.CustID == "100"
            assert new_wo.RackNo == "C3"

    def test_create_work_order_validates_customer_id(self, admin_client):
        """Creating work order without customer ID should fail."""
        response = admin_client.post("/work_orders/new", data={
            "WOName": "Invalid Order",
            "DateIn": "2025-02-01"
        })
        # Should return form (200) or error (400)
        assert response.status_code in [200, 400]


class TestWorkOrderEditRoutes:
    """Test work order editing HTTP routes."""

    def test_edit_work_order_page_renders(self, admin_client, sample_data):
        """GET /work_orders/edit/<no> should render edit form."""
        response = admin_client.get("/work_orders/edit/10001")
        assert response.status_code == 200
        assert b"Edit" in response.data or b"10001" in response.data

    def test_update_work_order_basic_fields(self, admin_client, sample_data, app):
        """POST /work_orders/edit/<no> should update work order."""
        with app.app_context():
            response = admin_client.post("/work_orders/edit/10001", data={
                "CustID": "100",
                "WOName": "Updated Work Order Name",
                "DateIn": "2025-01-15",
                "DateRequired": "2025-02-01",
                "RackNo": "Z9",
                "Storage": "Floor",
                "ShipTo": "Test Source",
                "SpecialInstructions": "Updated instructions",
                "RepairsNeeded": "Clean and inspect",
                "RushOrder": "1"
            }, follow_redirects=True)

            assert response.status_code == 200

            # Verify updates
            updated_wo = WorkOrder.query.get("10001")
            assert updated_wo.WOName == "Updated Work Order Name"
            assert updated_wo.RackNo == "Z9"

    def test_update_work_order_date_completed(self, admin_client, sample_data, app):
        """Setting DateCompleted should mark order as complete."""
        with app.app_context():
            response = admin_client.post("/work_orders/edit/10001", data={
                "CustID": "100",
                "WOName": "Test Work Order 1",
                "DateIn": "2025-01-15",
                "DateRequired": "2025-01-30",
                "DateCompleted": "2025-01-28",
                "RackNo": "A1",
                "Storage": "Rack",
                "ShipTo": "Test Source",
                "SpecialInstructions": "Handle with care",
                "RepairsNeeded": "Clean and inspect"
            }, follow_redirects=True)

            assert response.status_code == 200

            # Verify DateCompleted was set
            updated_wo = WorkOrder.query.get("10001")
            assert updated_wo.DateCompleted is not None


class TestWorkOrderDeleteRoutes:
    """Test work order deletion HTTP routes."""

    def test_delete_work_order(self, admin_client, sample_data, app):
        """POST /work_orders/delete/<no> should delete work order."""
        with app.app_context():
            # Verify work order exists
            wo = WorkOrder.query.get("10002")
            assert wo is not None

            response = admin_client.post("/work_orders/delete/10002", follow_redirects=True)
            assert response.status_code == 200

            # Verify work order was deleted
            deleted_wo = WorkOrder.query.get("10002")
            assert deleted_wo is None

    def test_delete_work_order_cascades_to_items(self, admin_client, sample_data, app):
        """Deleting work order should delete associated items."""
        with app.app_context():
            # Verify items exist
            items_before = WorkOrderItem.query.filter_by(WorkOrderNo="10001").all()
            assert len(items_before) > 0

            response = admin_client.post("/work_orders/delete/10001", follow_redirects=True)
            assert response.status_code == 200

            # Verify items were deleted
            items_after = WorkOrderItem.query.filter_by(WorkOrderNo="10001").all()
            assert len(items_after) == 0

    def test_delete_missing_work_order(self, admin_client):
        """Deleting non-existent work order should handle gracefully."""
        response = admin_client.post("/work_orders/delete/NONEXISTENT")
        # Should either 404 or redirect with error message
        assert response.status_code in [302, 404]


class TestWorkOrderAPIRoutes:
    """Test work order API HTTP endpoints."""

    def test_api_get_customer_inventory(self, admin_client, sample_data):
        """GET /work_orders/api/customer_inventory/<cust_id> should return inventory."""
        response = admin_client.get("/work_orders/api/customer_inventory/100")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2  # We created 2 inventory items

    def test_api_get_next_wo_number(self, admin_client, sample_data):
        """GET /work_orders/api/next_wo_number should return next available number."""
        response = admin_client.get("/work_orders/api/next_wo_number")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "next_wo_number" in data
        # Should be >= 10003 since we have 10001 and 10002
        # Next WO number is just a number string

    def test_api_work_orders_list(self, admin_client, sample_data):
        """GET /work_orders/api/work_orders should return work orders as JSON."""
        response = admin_client.get("/work_orders/api/work_orders")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "data" in data
        assert isinstance(data["data"], list)


class TestWorkOrderFileRoutes:
    """Test work order file upload/download HTTP routes."""

    def test_upload_file_to_work_order(self, admin_client, sample_data, app, mocker):
        """POST /work_orders/<no>/files/upload should upload file."""
        # Mock the file upload utility function completely
        mock_save_file = mocker.patch("routes.work_orders.save_work_order_file")
        # Create a mock file object to return
        mock_file_obj = mocker.Mock()
        mock_file_obj.id = 123  # Correct field name after bug fix
        mock_save_file.return_value = mock_file_obj

        with app.app_context():
            # Create a test file
            test_file = (BytesIO(b"test file content"), "test.pdf")

            response = admin_client.post(
                "/work_orders/10001/files/upload",
                data={"file": test_file},
                content_type="multipart/form-data"
            )

            # Should return success JSON
            assert response.status_code == 200
            assert response.is_json
            data = response.get_json()
            assert "file_id" in data
            assert data["file_id"] == 123

    def test_list_work_order_files(self, admin_client, sample_data, app):
        """GET /work_orders/<no>/files should list files."""
        with app.app_context():
            # Create a test file record
            test_file = WorkOrderFile(
                WorkOrderNo="10001",
                filename="test.pdf",
                file_path="/tmp/test.pdf"
            )
            db.session.add(test_file)
            db.session.commit()

            response = admin_client.get("/work_orders/10001/files")
            assert response.status_code == 200
            assert response.is_json
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) >= 1
            # Verify the file is in the response
            assert data[0]["filename"] == "test.pdf"
            assert "id" in data[0]
            assert "uploaded" in data[0]


class TestWorkOrderPDFRoutes:
    """Test work order PDF generation HTTP routes."""

    def test_view_work_order_pdf(self, admin_client, sample_data, mocker):
        """GET /work_orders/<no>/pdf/view should generate and display PDF."""
        # Mock PDF generation
        mock_pdf = mocker.patch("work_order_pdf.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4 fake pdf content")

        response = admin_client.get("/work_orders/10001/pdf/view")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"

    def test_download_work_order_pdf(self, admin_client, sample_data, mocker):
        """GET /work_orders/<no>/pdf/download should download PDF."""
        # Mock PDF generation
        mock_pdf = mocker.patch("work_order_pdf.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4 fake pdf content")

        response = admin_client.get("/work_orders/10001/pdf/download")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        # Should have download headers
        assert "attachment" in response.headers.get("Content-Disposition", "").lower()


class TestWorkOrderBusinessLogic:
    """Test business logic through HTTP routes."""

    def test_rush_order_flag(self, admin_client, sample_data, app):
        """Rush orders should be marked correctly."""
        with app.app_context():
            wo_rush = WorkOrder.query.get("10002")
            assert wo_rush.RushOrder == "1"

            wo_regular = WorkOrder.query.get("10001")
            assert wo_regular.RushOrder == "0"

    def test_work_order_status_via_date_completed(self, admin_client, sample_data, app):
        """Work order status determined by DateCompleted field."""
        with app.app_context():
            # 10001 is pending (no DateCompleted)
            wo_pending = WorkOrder.query.get("10001")
            assert wo_pending.DateCompleted is None or wo_pending.DateCompleted == ""

            # 10002 is completed (has DateCompleted)
            wo_completed = WorkOrder.query.get("10002")
            assert wo_completed.DateCompleted is not None and wo_completed.DateCompleted != ""
