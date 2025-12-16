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
from datetime import date, datetime
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
            DateIn=date(2025, 1, 15),
            DateRequired=date(2025, 1, 30),
            RackNo="A1",
            Storage="Rack",
            ShipTo="Test Source",
            SpecialInstructions="Handle with care",
            RepairsNeeded=True,
            RushOrder=False
        )
        wo2 = WorkOrder(
            WorkOrderNo="10002",
            CustID="100",
            WOName="Test Work Order 2",
            DateIn=date(2025, 1, 20),
            DateRequired=date(2025, 2, 5),
            RackNo="B2",
            Storage="Floor",
            ShipTo="Test Source",
            RushOrder=True,
            DateCompleted=datetime(2025, 1, 25)
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


    def test_update_work_order_adds_item_from_history(self, admin_client, sample_data, app):
        """
        Tests that editing a work order and selecting an item from customer history
        correctly adds the item to the work order.
        """
        with app.app_context():
            # Work order 10001 starts with one item
            wo = WorkOrder.query.get("10001")
            assert len(wo.items) == 1
            original_item_id = wo.items[0].id

            # We will add INV002 from the customer's inventory
            inventory_item_to_add = Inventory.query.get("INV002")
            assert inventory_item_to_add is not None

            response = admin_client.post("/work_orders/edit/10001", data={
                "CustID": "100",
                "WOName": "Adding from history",
                "DateIn": "2025-01-15",
                # Keep the original item
                "existing_item_id[]": [str(original_item_id)],
                f"existing_item_qty_{original_item_id}": "1",
                # Add the new item from inventory history
                "selected_items[]": ["INV002"],
                "item_qty_INV002": "3", # Specify a quantity for the new item
            }, follow_redirects=True)

            assert response.status_code == 200

            # Verify the work order now has two items
            updated_wo = WorkOrder.query.get("10001")
            assert len(updated_wo.items) == 2

            # Check that the newly added item is correct
            newly_added_item = next((item for item in updated_wo.items if item.Description == "Test Cover"), None)
            assert newly_added_item is not None
            assert newly_added_item.Qty == 3
            assert newly_added_item.Material == "Vinyl"


    def test_update_work_order_preserves_and_updates_items(self, admin_client, sample_data, app):
        """
        CRITICAL TEST: Ensures editing a work order does not drop its items.
        This test simulates the form submission to preserve existing items,
        update their quantities, and remove a specific item.
        """
        with app.app_context():
            # --- Setup: Create a work order with multiple items ---
            wo = WorkOrder.query.get("10001")
            item1 = WorkOrderItem(WorkOrderNo="10001", CustID="100", Description="Item A", Qty=1)
            item2 = WorkOrderItem(WorkOrderNo="10001", CustID="100", Description="Item B", Qty=2)
            db.session.add_all([item1, item2])
            db.session.commit()

            # Get the IDs of the newly created items
            item1_id = item1.id
            item2_id = item2.id
            
            # There should be 3 items now (1 from fixture, 2 new)
            assert len(wo.items) == 3

            # --- Test 1: Preserve existing items and update a quantity ---
            # Simulate a POST request that keeps both items and changes the quantity of item1
            response = admin_client.post("/work_orders/edit/10001", data={
                "CustID": "100",
                "WOName": "Updated Name",
                "DateIn": "2025-01-15",
                # IMPORTANT: Submit the IDs of the items to keep
                "existing_item_id[]": [str(item1_id), str(item2_id)],
                # Update the quantity of item1
                f"existing_item_qty_{item1_id}": "5",
                # The price field for item1
                f"existing_item_price_{item1_id}": "10.00",
            }, follow_redirects=True)

            assert response.status_code == 200

            # Verify that the items are still there and the quantity was updated
            wo_after_update = WorkOrder.query.get("10001")
            assert len(wo_after_update.items) == 2 # The original item from the fixture is not included
            
            updated_item1 = WorkOrderItem.query.get(item1_id)
            assert updated_item1 is not None
            assert updated_item1.Qty == 5
            assert updated_item1.Price == 10.00

            updated_item2 = WorkOrderItem.query.get(item2_id)
            assert updated_item2 is not None
            assert updated_item2.Qty == 2 # Should be unchanged

            # --- Test 2: Remove one item ---
            # Simulate a POST that only includes item2's ID, effectively removing item1
            response_remove = admin_client.post("/work_orders/edit/10001", data={
                "CustID": "100",
                "WOName": "Updated Name Again",
                "DateIn": "2025-01-15",
                # IMPORTANT: Only submit the ID of the item to keep
                "existing_item_id[]": [str(item2_id)],
            }, follow_redirects=True)

            assert response_remove.status_code == 200

            # Verify that item1 is gone and item2 remains
            wo_after_removal = WorkOrder.query.get("10001")
            assert len(wo_after_removal.items) == 1
            
            assert WorkOrderItem.query.get(item1_id) is None
            assert WorkOrderItem.query.get(item2_id) is not None


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

    def test_api_work_orders_sort_by_datein_asc(self, admin_client, sample_data):
        """GET /work_orders/api/work_orders with DateIn sort ascending should work."""
        response = admin_client.get("/work_orders/api/work_orders?sort[0][field]=DateIn&sort[0][dir]=asc")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "data" in data
        # Should have work orders sorted by DateIn ascending
        work_orders = data["data"]
        if len(work_orders) >= 2:
            # 10001 has DateIn=2025-01-15, 10002 has DateIn=2025-01-20
            # Ascending sort should show 10001 before 10002
            dates = [wo["DateIn"] for wo in work_orders if wo["DateIn"]]
            # Dates should be in ascending order
            assert dates == sorted(dates)

    def test_api_work_orders_sort_by_datein_desc(self, admin_client, sample_data):
        """GET /work_orders/api/work_orders with DateIn sort descending should work."""
        response = admin_client.get("/work_orders/api/work_orders?sort[0][field]=DateIn&sort[0][dir]=desc")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "data" in data
        # Should have work orders sorted by DateIn descending
        work_orders = data["data"]
        if len(work_orders) >= 2:
            dates = [wo["DateIn"] for wo in work_orders if wo["DateIn"]]
            # Dates should be in descending order
            assert dates == sorted(dates, reverse=True)

    def test_api_work_orders_sort_by_daterequired(self, admin_client, sample_data):
        """GET /work_orders/api/work_orders with DateRequired sort should work."""
        response = admin_client.get("/work_orders/api/work_orders?sort[0][field]=DateRequired&sort[0][dir]=asc")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "data" in data
        # Should not crash - DATE type columns should be sortable


class TestWorkOrderFileRoutes:
    """Test work order file upload/download HTTP routes."""

    def test_upload_file_to_work_order(self, admin_client, sample_data, app, mocker):
        """POST /work_orders/<no>/files/upload should upload file."""
        # Mock the file upload utility functions
        mock_save_file = mocker.patch("routes.work_orders.save_work_order_file")
        mock_commit_uploads = mocker.patch("routes.work_orders.commit_deferred_uploads")
        mock_cleanup = mocker.patch("routes.work_orders.cleanup_deferred_files")

        # Create a mock file object to return
        from models.work_order_file import WorkOrderFile
        mock_file_obj = WorkOrderFile(
            WorkOrderNo="10001",
            filename="test.pdf",
            file_path="s3://bucket/test.pdf"
        )
        mock_file_obj.id = 123

        mock_save_file.return_value = mock_file_obj
        # Mock commit_deferred_uploads to return success
        mock_commit_uploads.return_value = (True, [mock_file_obj], [])

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

            # Verify the functions were called correctly
            assert mock_save_file.called
            assert mock_commit_uploads.called

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
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4 fake pdf content")

        response = admin_client.get("/work_orders/10001/pdf/view")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"

    def test_download_work_order_pdf(self, admin_client, sample_data, mocker):
        """GET /work_orders/<no>/pdf/download should download PDF."""
        # Mock PDF generation
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4 fake pdf content")

        response = admin_client.get("/work_orders/10001/pdf/download")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        # Should have download headers
        assert "attachment" in response.headers.get("Content-Disposition", "").lower()


class TestWorkOrderBulkPDFRoutes:
    """Test bulk PDF generation for filtered work orders (Issue #29)."""

    def test_bulk_pdf_with_single_work_order(self, admin_client, sample_data, mocker):
        """POST /work_orders/api/bulk_pdf should generate PDF for single work order."""
        # Mock PDF generation
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4\nfake pdf content")

        # Mock PyMuPDF operations
        mock_fitz_doc = mocker.MagicMock()
        mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
        mock_fitz_open.return_value = mock_fitz_doc

        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001"]},
            content_type="application/json"
        )

        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert "attachment" in response.headers.get("Content-Disposition", "").lower()
        assert "WorkOrders_Bulk_" in response.headers.get("Content-Disposition", "")

    def test_bulk_pdf_with_multiple_work_orders(self, admin_client, sample_data, mocker):
        """POST /work_orders/api/bulk_pdf should generate concatenated PDF for multiple work orders."""
        # Mock PDF generation - use side_effect to return fresh BytesIO each time
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.side_effect = lambda *args, **kwargs: BytesIO(b"%PDF-1.4\nfake pdf content")

        # Mock PyMuPDF operations
        mock_fitz_doc = mocker.MagicMock()
        mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
        mock_fitz_open.return_value = mock_fitz_doc

        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001", "10002"]},
            content_type="application/json"
        )

        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert "attachment" in response.headers.get("Content-Disposition", "").lower()
        # Should have called PDF generation twice (once per work order)
        assert mock_pdf.call_count == 2

    def test_bulk_pdf_with_no_work_orders(self, admin_client, sample_data):
        """POST /work_orders/api/bulk_pdf with empty list should return 400."""
        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": []},
            content_type="application/json"
        )

        assert response.status_code == 400
        assert response.is_json
        data = response.get_json()
        assert "error" in data
        assert "No work orders provided" in data["error"]

    def test_bulk_pdf_without_json_data(self, admin_client, sample_data):
        """POST /work_orders/api/bulk_pdf without JSON should handle gracefully."""
        response = admin_client.post("/work_orders/api/bulk_pdf")

        # Should return 400 or 500 depending on error handling
        assert response.status_code in [400, 500]

    def test_bulk_pdf_skips_nonexistent_work_orders(self, admin_client, sample_data, mocker):
        """POST /work_orders/api/bulk_pdf should skip non-existent work orders gracefully."""
        # Mock PDF generation - use side_effect to return fresh BytesIO each time
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.side_effect = lambda *args, **kwargs: BytesIO(b"%PDF-1.4\nfake pdf content")

        # Mock PyMuPDF operations
        mock_fitz_doc = mocker.MagicMock()
        mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
        mock_fitz_open.return_value = mock_fitz_doc

        # Request includes one valid and one invalid work order number
        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001", "99999"]},
            content_type="application/json"
        )

        # Should still succeed and generate PDF for valid work order
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        # Should only generate PDF for the one valid work order
        assert mock_pdf.call_count == 1

    def test_bulk_pdf_with_large_batch(self, admin_client, sample_data, app, mocker):
        """POST /work_orders/api/bulk_pdf should handle large batches."""
        with app.app_context():
            # Create additional work orders for testing
            for i in range(10003, 10013):  # Create 10 more work orders
                wo = WorkOrder(
                    WorkOrderNo=str(i),
                    CustID="100",
                    WOName=f"Test WO {i}",
                    DateIn=date(2025, 1, 15),
                    RackNo="A1"
                )
                db.session.add(wo)
            db.session.commit()

            # Mock PDF generation - use side_effect to return fresh BytesIO each time
            mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
            mock_pdf.side_effect = lambda *args, **kwargs: BytesIO(b"%PDF-1.4\nfake pdf content")

            # Mock PyMuPDF operations
            mock_fitz_doc = mocker.MagicMock()
            mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
            mock_fitz_open.return_value = mock_fitz_doc

            # Request 12 work orders (10001, 10002, and 10003-10012)
            work_order_numbers = ["10001", "10002"] + [str(i) for i in range(10003, 10013)]

            response = admin_client.post(
                "/work_orders/api/bulk_pdf",
                json={"work_order_numbers": work_order_numbers},
                content_type="application/json"
            )

            assert response.status_code == 200
            assert response.content_type == "application/pdf"
            # Should have called PDF generation 12 times
            assert mock_pdf.call_count == 12

    def test_bulk_pdf_preserves_work_order_data(self, admin_client, sample_data, app, mocker):
        """POST /work_orders/api/bulk_pdf should include all work order data in PDFs."""
        # Don't mock generate_work_order_pdf, but mock the prepare function to verify data
        mock_prepare = mocker.patch("routes.work_orders.prepare_order_data_for_pdf")
        mock_prepare.return_value = {
            "WorkOrderNo": "10001",
            "CustID": "100",
            "items": [],
            "customer": {}
        }

        # Mock the actual PDF generation
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4\nfake pdf content")

        # Mock PyMuPDF operations
        mock_fitz_doc = mocker.MagicMock()
        mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
        mock_fitz_open.return_value = mock_fitz_doc

        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001", "10002"]},
            content_type="application/json"
        )

        assert response.status_code == 200
        # Verify prepare_order_data_for_pdf was called with correct parameters
        assert mock_prepare.call_count == 2
        # Each call should specify order_type="work_order"
        for call in mock_prepare.call_args_list:
            assert call[1]["order_type"] == "work_order"

    def test_bulk_pdf_includes_timestamp_in_filename(self, admin_client, sample_data, mocker):
        """POST /work_orders/api/bulk_pdf should include timestamp in filename."""
        # Mock PDF generation
        mock_pdf = mocker.patch("routes.work_orders.generate_work_order_pdf")
        mock_pdf.return_value = BytesIO(b"%PDF-1.4\nfake pdf content")

        # Mock PyMuPDF operations
        mock_fitz_doc = mocker.MagicMock()
        mock_fitz_open = mocker.patch("routes.work_orders.fitz.open")
        mock_fitz_open.return_value = mock_fitz_doc

        response = admin_client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001"]},
            content_type="application/json"
        )

        assert response.status_code == 200
        disposition = response.headers.get("Content-Disposition", "")
        # Filename should be like: WorkOrders_Bulk_20250111_123456.pdf
        assert "WorkOrders_Bulk_" in disposition
        assert ".pdf" in disposition

    def test_bulk_pdf_requires_authentication(self, client, sample_data):
        """POST /work_orders/api/bulk_pdf should require login."""
        # Try to access without logging in
        response = client.post(
            "/work_orders/api/bulk_pdf",
            json={"work_order_numbers": ["10001"]},
            content_type="application/json"
        )

        # Should redirect to login or return 401
        assert response.status_code in [302, 401]


class TestWorkOrderBusinessLogic:
    """Test business logic through HTTP routes."""

    def test_rush_order_flag(self, admin_client, sample_data, app):
        """Rush orders should be marked correctly."""
        with app.app_context():
            wo_rush = WorkOrder.query.get("10002")
            assert wo_rush.RushOrder == True

            wo_regular = WorkOrder.query.get("10001")
            assert wo_regular.RushOrder == False

    def test_work_order_status_via_date_completed(self, admin_client, sample_data, app):
        """Work order status determined by DateCompleted field."""
        with app.app_context():
            # 10001 is pending (no DateCompleted)
            wo_pending = WorkOrder.query.get("10001")
            assert wo_pending.DateCompleted is None or wo_pending.DateCompleted == ""

            # 10002 is completed (has DateCompleted)
            wo_completed = WorkOrder.query.get("10002")
            assert wo_completed.DateCompleted is not None and wo_completed.DateCompleted != ""
class TestCushionWorkOrderRoutes:
    """Test cushion work order specific routes."""

    def test_cushion_work_orders_page_renders(self, admin_client, sample_data):
        """GET /work_orders/cushion should render the list page."""
        response = admin_client.get("/work_orders/cushion")
        assert response.status_code == 200
        assert b"Open Cushion Work Orders" in response.data

    def test_cushion_work_orders_only_shows_cushion(self, admin_client, sample_data, app):
        """GET /work_orders/cushion should only show work orders where isCushion is True."""
        with app.app_context():
            # Create a cushion work order
            cushion_wo = WorkOrder(
                WorkOrderNo="10003",
                CustID="100",
                WOName="Cushion Work Order",
                DateIn=date(2025, 2, 1),
                isCushion=True,
            )
            db.session.add(cushion_wo)
            db.session.commit()

        response = admin_client.get("/work_orders/cushion")
        assert response.status_code == 200
        # The API is used to fetch data, so we check the API response
        api_response = admin_client.get("/work_orders/api/work_orders?is_cushion_view=True")
        assert api_response.status_code == 200
        data = api_response.get_json()
        wo_numbers = [wo.get("WorkOrderNo") for wo in data["data"]]
        assert "10003" in wo_numbers
        assert "10001" not in wo_numbers
        assert "10002" not in wo_numbers

    def test_create_work_order_with_cushion(self, admin_client, sample_data, app):
        """POST /work_orders/new with isCushion checked should create a cushion work order."""
        with app.app_context():
            response = admin_client.post(
                "/work_orders/new",
                data={
                    "CustID": "100",
                    "WOName": "New Cushion Order",
                    "DateIn": "2025-02-01",
                    "isCushion": "on",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            new_wo = WorkOrder.query.filter_by(WOName="New Cushion Order").first()
            assert new_wo is not None
            assert new_wo.isCushion is True

    def test_edit_work_order_with_cushion(self, admin_client, sample_data, app):
        """POST /work_orders/edit/<no> with isCushion achecked should update the work order."""
        with app.app_context():
            response = admin_client.post(
                "/work_orders/edit/10001",
                data={
                    "CustID": "100",
                    "WOName": "Updated to Cushion",
                    "DateIn": "2025-01-15",
                    "isCushion": "on",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            updated_wo = WorkOrder.query.get("10001")
            assert updated_wo.WOName == "Updated to Cushion"
            assert updated_wo.isCushion is True

    def test_work_order_detail_shows_cushion_status(self, admin_client, sample_data, app):
        """Work order detail page should show cushion status."""
        with app.app_context():
            cushion_wo = WorkOrder(
                WorkOrderNo="10004",
                CustID="100",
                WOName="Cushion WO",
                isCushion=True,
            )
            db.session.add(cushion_wo)
            db.session.commit()

        response = admin_client.get("/work_orders/10004")
        assert response.status_code == 200
        assert b"Cushion" in response.data
        assert b"Yes" in response.data
