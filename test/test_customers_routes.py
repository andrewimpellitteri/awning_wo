"""
Tests for Customer CRUD routes.
"""

# Tests not passing!

# Possible fix?

# The Definitive Solution: A Better Fixture Pattern 🛠️
# The most reliable way to handle this is to structure your fixtures to ensure the app, the database, and the test client are all set up within the same application context. You also need to explicitly create a user and log them in for the admin_client.

# Here is a completely revised and more robust set of fixtures for your test_customers_routes.py file. Replace all your existing fixtures (logged_in_client, admin_client, and sample_customers) with this new code.

# # This replaces your logged_in_client and admin_client fixtures
# @pytest.fixture
# def admin_client(client, app):
#     """
#     Provides a logged-in admin client and populates the database
#     with sample data within the same application context.
#     """
#     with app.app_context():
#         # Clean up any old data
#         db.session.remove()
#         db.drop_all()
#         db.create_all()

#         # 1. Create and log in an admin user
#         admin = User(
#             username="admin",
#             email="admin@example.com",
#             role="admin",
#             password_hash=generate_password_hash("password"),
#         )
#         db.session.add(admin)
#         db.session.commit()

#         client.post("/login", data={"username": "admin", "password": "password"})

#         # 2. Create sample data needed for tests
#         sources = [Source(SSource=s) for s in ["SRC1", "SRC2", "SRC3"]]
#         db.session.add_all(sources)

#         customers = [
#             Customer(CustID="123", Name="Customer 1", Source="SRC1", State="CA"),
#             Customer(CustID="124", Name="Customer 2", Source="SRC2", State="NY"),
#             Customer(CustID="125", Name="Customer 3", Source="SRC1", State="CA"),
#         ]
#         db.session.add_all(customers)
#         db.session.commit()

#         yield client

#         # 3. Clean logout after tests are done
#         client.get("/logout")


# # Remove the separate sample_customers fixture entirely.
# # Also remove the logged_in_client fixture if it's not needed for other tests
# # in this file that require a non-admin user.


# # Update your tests to use the new fixture

import pytest
from models.customer import Customer
from models.source import Source
from models.user import User
from extensions import db
from werkzeug.security import generate_password_hash


@pytest.fixture
def logged_in_client(client, app):
    """Provide a logged-in client with a regular user."""
    with app.app_context():
        user = User(
            username="testuser",
            email="testuser@example.com",  # <-- Add email
            role="user",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)
        db.session.commit()

        client.post("/login", data={"username": "testuser", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with an admin user and sample data."""
    with app.app_context():
        # Create sources first (required for foreign key constraint)
        sources = [Source(SSource=s) for s in ["SRC1", "SRC2", "SRC3"]]
        db.session.add_all(sources)

        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(admin)
        db.session.commit()

        client.post("/login", data={"username": "admin", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def sample_customers(app):
    """Fixture to create sample customers for testing (assumes sources already exist)."""
    with app.app_context():
        # Create sample sources if they don't exist
        if not Source.query.filter_by(SSource="SRC1").first():
            sources = [Source(SSource=s) for s in ["SRC1", "SRC2", "SRC3"]]
            db.session.add_all(sources)
            db.session.commit()

        # Create sample customers
        customers = [
            Customer(CustID="123", Name="Customer 1", Source="SRC1", State="CA"),
            Customer(CustID="124", Name="Customer 2", Source="SRC2", State="NY"),
            Customer(CustID="125", Name="Customer 3", Source="SRC1", State="CA"),
        ]
        db.session.add_all(customers)
        db.session.commit()

        yield

        # Teardown: Clean up the database (leave sources for other tests)
        db.session.query(Customer).delete()
        db.session.commit()


class TestCustomerRoutes:
    def test_customers_list_page_renders(self, admin_client):
        """GET /customers/ should render the list page (admin/manager only)."""
        response = admin_client.get("/customers/")
        assert response.status_code == 200
        assert b"Customers" in response.data

    def test_customers_api_endpoint_works(self, admin_client):
        """GET /customers/api/customers should return JSON."""
        response = admin_client.get("/customers/api/customers")
        assert response.status_code == 200
        assert response.is_json

    def test_global_search(self, logged_in_client, sample_customers):
        """Test global search functionality."""
        response = logged_in_client.get("/customers/api/customers?search=Customer 1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 1"

    def test_filter_by_source(self, logged_in_client, sample_customers):
        """Test filtering by Source."""
        response = logged_in_client.get("/customers/api/customers?filter_Source=SRC2")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 2"



    def test_column_filter_by_cust_id(self, logged_in_client, sample_customers):
        """Test column-specific filtering by CustID."""
        response = logged_in_client.get("/customers/api/customers?filter_CustID=125")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 3"

    def test_sorting(self, logged_in_client, sample_customers):
        """Test sorting functionality."""
        response = logged_in_client.get(
            "/customers/api/customers?sort[0][field]=Name&sort[0][dir]=desc"
        )
        assert response.status_code == 200
        data = response.get_json()
        # Verify the first customer is the one with the last name alphabetically
        assert data["data"][0]["Name"] == "Customer 3"

    def test_pagination(self, logged_in_client, sample_customers):
        """Test pagination functionality."""
        response = logged_in_client.get("/customers/api/customers?page=2&size=1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["last_page"] == 3
        assert len(data["data"]) == 1

    def test_view_customer_detail(self, logged_in_client, sample_customers):
        """Test viewing a customer's detail page."""
        response = logged_in_client.get("/customers/view/123")
        assert response.status_code == 200
        assert b"Customer 1" in response.data

    def test_view_missing_customer_detail(self, logged_in_client, sample_customers):
        """Test viewing a missing customer's detail page results in a 404."""
        response = logged_in_client.get("/customers/view/9999")
        assert response.status_code == 404

    def test_create_customer_page_renders(self, admin_client):
        """GET /customers/new should render the create page."""
        response = admin_client.get("/customers/new")
        assert response.status_code == 200
        assert b"Create Customer" in response.data

    def test_create_customer(self, admin_client):
        """Test creating a new customer."""
        response = admin_client.post(
            "/customers/new",
            data={"Name": "New Customer", "Source": "SRC1"},
            follow_redirects=True,
        )
        assert response.status_code == 200  # After redirect

        # CORRECTED: Check the content of the final page, not the original request path.
        assert b"Customer created successfully" in response.data
        assert b"New Customer" in response.data

        # Verify the customer was actually added to the database
        new_cust = Customer.query.filter_by(Name="New Customer").first()
        assert new_cust is not None

    def test_create_customer_with_source_preselected(self, admin_client):
        """Test that source is pre-selected when passed as query parameter."""
        response = admin_client.get("/customers/new?source=SRC1")
        assert response.status_code == 200
        assert b"Create Customer" in response.data
        # Check that the source is pre-selected in the dropdown
        assert b'<option value="SRC1"' in response.data
        assert b'selected' in response.data

    def test_create_customer_invalid_data(self, admin_client, sample_customers):
        """Test creating a customer with invalid data."""
        response = admin_client.post("/customers/new", data={"Source": "SRC1"})
        assert response.status_code == 200
        assert b"Name is required." in response.data

    def test_edit_customer_page_renders(self, admin_client, sample_customers):
        """GET /customers/edit/<id> should render the edit page."""
        response = admin_client.get("/customers/edit/123")
        assert response.status_code == 200
        assert b"Edit Customer" in response.data

    def test_update_customer(self, admin_client, sample_customers):
        """Test updating a customer."""
        response = admin_client.post(
            "/customers/edit/123",
            data={"Name": "Updated Customer Name", "Source": "SRC1"},
            follow_redirects=True,
        )
        assert response.status_code == 200  # After redirect
        assert b"Updated Customer Name" in response.data

        updated_cust = Customer.query.get("123")
        assert updated_cust.Name == "Updated Customer Name"

    def test_delete_customer(self, admin_client, sample_customers):
        """Test deleting a customer."""
        response = admin_client.post("/customers/delete/123", follow_redirects=True)
        assert response.status_code == 200
        assert b"Customer 123 deleted." in response.data

        # Verify customer is removed from the database
        deleted_cust = Customer.query.get("123")
        assert deleted_cust is None

    def test_get_source_info_api(self, logged_in_client, sample_customers):
        """Test the API endpoint for getting source info."""
        response = logged_in_client.get("/customers/api/source_info/SRC1")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["SSource"] == "SRC1"


class TestCustomerRoutesAuth:
    def test_regular_user_cannot_access_customer_list(
        self, logged_in_client, sample_customers
    ):
        """Test that a regular user cannot access the customer list page."""
        response = logged_in_client.get("/customers/")
        assert response.status_code == 403

    def test_regular_user_cannot_create_customer(
        self, logged_in_client, sample_customers
    ):
        """Test that a regular user cannot create a customer."""
        response = logged_in_client.post(
            "/customers/new", data={"Name": "New Customer", "Source": "SRC1"}
        )
        assert response.status_code == 403

    def test_regular_user_cannot_edit_customer(
        self, logged_in_client, sample_customers
    ):
        """Test that a regular user cannot edit a customer."""
        response = logged_in_client.post(
            "/customers/edit/123",
            data={"Name": "Updated Customer Name", "Source": "SRC1"},
        )
        assert response.status_code == 403

    def test_regular_user_cannot_delete_customer(
        self, logged_in_client, sample_customers
    ):
        """Test that a regular user cannot delete a customer."""
        response = logged_in_client.post("/customers/delete/123")
        assert response.status_code == 403

import re
from models.work_order import WorkOrder
from models.repair_order import RepairWorkOrder
from datetime import datetime

def test_rush_badge_on_customer_detail_page(admin_client, sample_customers):
    """Test that the 'RUSH' badge appears only for open orders."""
    with admin_client.application.app_context():
        # Create a customer
        customer = Customer.query.get("123")

        # Create an open work order with RushOrder
        open_work_order = WorkOrder(
            WorkOrderNo="1002",
            CustID=customer.CustID,
            RushOrder=True,
            DateIn=datetime.utcnow().date()
        )
        db.session.add(open_work_order)

        # Create a closed work order with RushOrder
        closed_work_order = WorkOrder(
            WorkOrderNo="1001",
            CustID=customer.CustID,
            RushOrder=True,
            DateIn=datetime.utcnow().date(),
            DateCompleted=datetime.utcnow()
        )
        db.session.add(closed_work_order)

        # Create an open repair order with RushOrder
        open_repair_order = RepairWorkOrder(
            RepairOrderNo="2002",
            CustID=customer.CustID,
            RushOrder=True,
            DateIn=datetime.utcnow().date()
        )
        db.session.add(open_repair_order)

        # Create a closed repair order with RushOrder
        closed_repair_order = RepairWorkOrder(
            RepairOrderNo="2001",
            CustID=customer.CustID,
            RushOrder=True,
            DateIn=datetime.utcnow().date(),
            DateCompleted=datetime.utcnow()
        )
        db.session.add(closed_repair_order)

        db.session.commit()

        response = admin_client.get(f"/customers/view/{customer.CustID}")
        assert response.status_code == 200
        response_data = response.get_data(as_text=True)

        # Work Orders
        wo_items = re.findall(r'<li class="list-group-item.*?">.*?</li>', response_data, re.DOTALL)
        
        open_wo_item = next((item for item in wo_items if "1002" in item), None)
        assert open_wo_item is not None
        assert '<span class="badge bg-danger me-2">RUSH</span>' in open_wo_item

        closed_wo_item = next((item for item in wo_items if "1001" in item), None)
        assert closed_wo_item is not None
        assert '<span class="badge bg-danger me-2">RUSH</span>' not in closed_wo_item

        # Repair Orders
        ro_items = re.findall(r'<li class="list-group-item.*?">.*?</li>', response_data, re.DOTALL)

        open_ro_item = next((item for item in ro_items if "2002" in item), None)
        assert open_ro_item is not None
        assert '<span class="badge bg-danger me-2">RUSH</span>' in open_ro_item

        closed_ro_item = next((item for item in ro_items if "2001" in item), None)
        assert closed_ro_item is not None
        assert '<span class="badge bg-danger me-2">RUSH</span>' not in closed_ro_item