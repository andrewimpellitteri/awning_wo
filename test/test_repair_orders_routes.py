"""
Tests for Repair Order CRUD routes.
"""

import pytest
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.customer import Customer
from models.source import Source
from extensions import db
from werkzeug.security import generate_password_hash
from models.user import User


@pytest.fixture
def logged_in_client(client, app):
    """Provide a logged-in client with a regular user."""
    with app.app_context():
        user = User(
            username="testuser",
            email="testuser@example.com",  # <-- Add email
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)
        db.session.commit()

        client.post("/login", data={"username": "testuser", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def sample_repair_order_with_items(app):
    """Create a sample repair order with items for detail view testing."""
    with app.app_context():
        cust = Customer(CustID="123", Name="Test Customer")
        ro = RepairWorkOrder(
            RepairOrderNo="2001", CustID="123", ROName="Order with Items"
        )
        item1 = RepairWorkOrderItem(
            RepairOrderNo="2001",
            CustID="123",
            Description="Test Item 1",
            Price=10,
            Material="A",
        )
        item2 = RepairWorkOrderItem(
            RepairOrderNo="2001",
            CustID="123",
            Description="Test Item 2",
            Price=20,
            Material="A",
        )

        db.session.add_all([cust, ro, item1, item2])
        db.session.commit()
        yield
        db.session.query(RepairWorkOrderItem).delete()
        db.session.query(RepairWorkOrder).delete()
        db.session.query(Customer).delete()
        db.session.commit()


@pytest.fixture
def sample_repair_orders(app):
    """Create sample repair orders for testing filtering."""
    with app.app_context():
        # Sources
        source1 = Source(SSource="SRC1")
        source2 = Source(SSource="SRC2")

        # Customers
        cust1 = Customer(CustID="123", Name="Customer 1", Source="SRC1")
        cust2 = Customer(CustID="124", Name="Customer 2", Source="SRC2")
        cust3 = Customer(CustID="125", Name="Customer 3", Source="SRC1")

        # Repair Orders
        ro1 = RepairWorkOrder(
            RepairOrderNo="1001",
            CustID="123",
            ROName="Completed Order",
            DateCompleted="2024-01-01",
        )
        ro2 = RepairWorkOrder(
            RepairOrderNo="1002",
            CustID="124",
            ROName="Pending Order",
            DateCompleted=None,
        )
        ro3 = RepairWorkOrder(
            RepairOrderNo="1003", CustID="125", ROName="Rush Order", RushOrder="YES"
        )

        db.session.add_all([source1, source2, cust1, cust2, cust3, ro1, ro2, ro3])
        db.session.commit()
        yield
        db.session.query(RepairWorkOrder).delete()
        db.session.query(Customer).delete()
        db.session.query(Source).delete()
        db.session.commit()


@pytest.mark.wip
class TestRepairOrderRoutes:
    def test_repair_orders_list_page_renders(self, logged_in_client):
        """GET /repair_work_orders/ should render the list page."""
        response = logged_in_client.get("/repair_work_orders/")
        assert response.status_code == 200
        assert b"Repair Work Orders" in response.data

    def test_repair_orders_api_endpoint_works(self, logged_in_client):
        """GET /repair_work_orders/api/repair_work_orders should return JSON."""
        response = logged_in_client.get("/repair_work_orders/api/repair_work_orders")
        assert response.status_code == 200
        assert response.is_json

    def test_filter_by_status(self, logged_in_client, sample_repair_orders):
        """Test filtering repair orders by status."""
        # Test for completed
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?status=completed"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["RepairOrderNo"] == "1001"

        # Test for pending
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?status=pending"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 2  # Pending and Rush are both pending

        # Test for rush
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?status=rush"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["RepairOrderNo"] == "1003"

    def test_filter_by_global_search(self, logged_in_client, sample_repair_orders):
        """Test global search functionality."""
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?search=Completed"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["ROName"] == "Completed Order"

    def test_filter_by_repair_order_no(self, logged_in_client, sample_repair_orders):
        """Test filtering by RepairOrderNo."""
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?filter_RepairOrderNo=1002"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["RepairOrderNo"] == "1002"

    def test_filter_by_cust_id(self, logged_in_client, sample_repair_orders):
        """Test filtering by CustID."""
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?filter_CustID=125"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["CustID"] == "125"

    def test_filter_by_ro_name(self, logged_in_client, sample_repair_orders):
        """Test filtering by ROName."""
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?filter_ROName=Rush"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["ROName"] == "Rush Order"

    def test_filter_by_source(self, logged_in_client, sample_repair_orders):
        """Test filtering by Source."""
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?filter_Source=SRC2"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["RepairOrderNo"] == "1002"

    def test_sort_by_repair_order_no(self, logged_in_client, sample_repair_orders):
        """Test sorting by RepairOrderNo."""
        # Test ascending
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?sort=RepairOrderNo&dir=asc"  # FIX: Use simplified sort params
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"][0]["RepairOrderNo"] == "1001"

        # Test descending
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?sort=RepairOrderNo&dir=desc"  # FIX: Use simplified sort params
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"][0]["RepairOrderNo"] == "1003"

    def test_pagination(self, logged_in_client, sample_repair_orders):
        """Test pagination functionality."""
        # Test page 1
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?page=1&size=1"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["last_page"] == 3
        assert len(data["data"]) == 1

        # Test page 2
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?page=2&size=1"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 1

    def test_view_repair_order_detail(self, logged_in_client, sample_repair_orders):
        """Test viewing a repair order's detail page."""
        response = logged_in_client.get("/repair_work_orders/1001")
        assert response.status_code == 200
        assert b"1001" in response.data
        assert b"Completed Order" in response.data
        assert b"Customer 1" in response.data

    def test_view_missing_repair_order_detail(
        self, logged_in_client, sample_repair_orders
    ):
        """Test viewing a missing repair order's detail page results in a 404."""
        response = logged_in_client.get("/repair_work_orders/9999")
        assert response.status_code == 404

    def test_view_repair_order_detail_includes_items(
        self, logged_in_client, sample_repair_order_with_items
    ):
        """Test that the detail page includes all repair items."""
        response = logged_in_client.get("/repair_work_orders/2001")
        assert response.status_code == 200
        assert b"Test Item 1" in response.data
        assert b"Test Item 2" in response.data

    def test_update_repair_item(self, logged_in_client, sample_repair_order_with_items):
        """Test updating a repair item."""
        response = logged_in_client.post(
            "/repair_work_orders/2001/edit",
            data={
                "CustID": "123",
                "ROName": "Order with Items",
                "existing_description[]": ["Updated Test Item 1", "Test Item 2"],
                "existing_material[]": ["A", "A"],
                "existing_qty[]": ["1", "1"],
                "existing_condition[]": ["", ""],
                "existing_color[]": ["", ""],
                "existing_size[]": ["", ""],
                "existing_price[]": ["10", "20"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Updated Test Item 1" in response.data

        # Query by composite key (RepairOrderNo, Description, Material)
        updated_item = RepairWorkOrderItem.query.get(
            ("2001", "Updated Test Item 1", "A")
        )
        assert updated_item is not None
        assert updated_item.Description == "Updated Test Item 1"

    def test_add_repair_item_on_edit(
        self, logged_in_client, sample_repair_order_with_items
    ):
        """Test adding a new repair item on edit."""
        response = logged_in_client.post(
            "/repair_work_orders/2001/edit",
            data={
                "CustID": "123",
                "ROName": "Order with Items",
                "existing_description[]": ["Test Item 1", "Test Item 2"],
                "existing_material[]": ["A", "A"],
                "existing_qty[]": ["1", "1"],
                "existing_condition[]": ["", ""],
                "existing_color[]": ["", ""],
                "existing_size[]": ["", ""],
                "existing_price[]": ["10", "20"],
                "new_description[]": ["Newly Added Item"],
                "new_material[]": ["B"],
                "new_qty[]": ["1"],
                "new_condition[]": [""],
                "new_color[]": [""],
                "new_size[]": [""],
                "new_price[]": ["30"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Newly Added Item" in response.data

        new_item = RepairWorkOrderItem.query.filter_by(
            Description="Newly Added Item"
        ).first()
        assert new_item is not None

    def test_delete_repair_item_on_edit(
        self, logged_in_client, sample_repair_order_with_items
    ):
        """Test deleting a repair item by not including it in the form submission."""
        # Only submit Test Item 1, omitting Test Item 2 effectively deletes it
        response = logged_in_client.post(
            "/repair_work_orders/2001/edit",
            data={
                "CustID": "123",
                "ROName": "Order with Items",
                "existing_description[]": ["Test Item 1"],
                "existing_material[]": ["A"],
                "existing_qty[]": ["1"],
                "existing_condition[]": [""],
                "existing_color[]": [""],
                "existing_size[]": [""],
                "existing_price[]": ["10"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Test Item 1" in response.data
        assert b"Test Item 2" not in response.data

        # Verify Test Item 2 was deleted by checking it doesn't exist
        deleted_item = RepairWorkOrderItem.query.get(("2001", "Test Item 2", "A"))
        assert deleted_item is None

    def test_generate_repair_order_pdf(
        self, logged_in_client, sample_repair_order_with_items
    ):
        """Test generating a repair order PDF."""
        response = logged_in_client.get("/repair_work_orders/2001/pdf")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert (
            response.headers["Content-Disposition"]
            == "attachment; filename=WorkOrder_2001.pdf"  # FIX: Correct filename from route
        )

    def test_create_repair_order_page_renders(self, logged_in_client):
        """GET /repair_work_orders/create should render the create page."""
        # FIX: Use logged_in_client to bypass authentication redirect
        response = logged_in_client.get("/repair_work_orders/new")
        assert response.status_code == 200
        assert (
            b"Create New Repair Work Order" in response.data
        )  # FIX: Correct title from template

    def test_create_repair_order(self, logged_in_client, sample_repair_orders):
        """Test creating a new repair order."""
        # Get the last RepairOrderNo to check for sequential generation
        last_ro = RepairWorkOrder.query.order_by(
            RepairWorkOrder.RepairOrderNo.desc()
        ).first()
        next_ro_num = int(last_ro.RepairOrderNo) + 1

        response = logged_in_client.post(
            "/repair_work_orders/new",
            data={
                "CustID": "123",
                "ROName": "New Test Order",
                "items-0-Description": "Test Item",
                "items-0-Price": "100",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200  # After redirect
        assert f"/repair_work_orders/{next_ro_num}" in response.request.path

        new_ro = RepairWorkOrder.query.get(str(next_ro_num))
        assert new_ro is not None
        assert new_ro.ROName == "New Test Order"

    def test_create_repair_order_invalid_data(
        self, logged_in_client, sample_repair_orders
    ):
        """Test creating a repair order with invalid data."""
        response = logged_in_client.post(
            "/repair_work_orders/new",
            data={
                "ROName": "New Test Order",
                "items-0-Description": "Test Item",
                "items-0-Price": "100",
            },
        )
        assert response.status_code == 200
        assert b"Customer is required." in response.data

    def test_edit_repair_order_page_renders(
        self, logged_in_client, sample_repair_orders
    ):
        """GET /repair_work_orders/<no>/edit should render the edit page."""
        response = logged_in_client.get("/repair_work_orders/1001/edit")
        assert response.status_code == 200
        assert b"Edit Repair Work Order" in response.data

    def test_update_repair_order(self, logged_in_client, sample_repair_orders):
        """Test updating a repair order."""
        response = logged_in_client.post(
            "/repair_work_orders/1001/edit",
            data={
                "CustID": "123",
                "ROName": "Updated Order Name",
                "items-0-Description": "Test Item",
                "items-0-Price": "100",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200  # After redirect
        assert b"Updated Order Name" in response.data

        updated_ro = RepairWorkOrder.query.get(1001)
        assert updated_ro.ROName == "Updated Order Name"

    def test_update_repair_order_invalid_data(
        self, logged_in_client, sample_repair_orders
    ):
        """Test updating a repair order with invalid data."""
        response = logged_in_client.post(
            "/repair_work_orders/1001/edit",
            data={
                "CustID": "123",
                "ROName": "",
                "items-0-Description": "Test Item",
                "items-0-Price": "100",
            },
        )
        assert response.status_code == 200
        assert b"Name is required." in response.data

    def test_delete_repair_order(self, logged_in_client, sample_repair_orders):
        """Test deleting a repair order."""
        response = logged_in_client.post(
            "/repair_work_orders/1001/delete", follow_redirects=True
        )
        assert response.status_code == 200
        assert (
            b"Repair Work Order #1001 has been deleted successfully" in response.data
        )  # FIX: Match actual flash message

        deleted_ro = RepairWorkOrder.query.get(1001)
        assert deleted_ro is None


@pytest.fixture
def sample_repair_orders_for_date_sort(app):
    """Create sample repair orders for testing date sorting."""
    with app.app_context():
        # Need a customer for the repair orders
        cust = Customer(CustID="999", Name="Test Customer")
        ro1 = RepairWorkOrder(RepairOrderNo="1001", CustID="999", DateIn="2024-01-15")
        ro2 = RepairWorkOrder(RepairOrderNo="1002", CustID="999", DateIn="2024-01-20")
        ro3 = RepairWorkOrder(RepairOrderNo="1003", CustID="999", DateIn=None)

        db.session.add_all([cust, ro1, ro2, ro3])
        db.session.commit()
        yield
        db.session.query(RepairWorkOrder).delete()
        db.session.query(Customer).delete()
        db.session.commit()


class TestRepairOrderDateSorting:
    def test_sort_by_date(self, logged_in_client, sample_repair_orders_for_date_sort):
        """Test sorting by DateIn."""
        # Test ascending
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?sort=DateIn&dir=asc"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"][0]["RepairOrderNo"] == "1003"  # None dates first

        # Test descending
        response = logged_in_client.get(
            "/repair_work_orders/api/repair_work_orders?sort=DateIn&dir=desc"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"][0]["RepairOrderNo"] == "1002"

    def test_delete_missing_repair_order(self, logged_in_client, sample_repair_orders):
        """Test deleting a missing repair order results in a 404."""
        response = logged_in_client.post("/repair_work_orders/9999/delete")
        assert response.status_code == 404
