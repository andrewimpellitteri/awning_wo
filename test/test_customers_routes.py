"""
Tests for Customer CRUD routes.
"""

import pytest
from models.customer import Customer
from models.source import Source
from models.user import User
from extensions import db


@pytest.fixture
def logged_in_client(client, app):
    """Provide a logged-in client with a regular user."""
    with app.app_context():
        user = User(username="testuser", password="password", role="user")
        db.session.add(user)
        db.session.commit()

    client.post("/login", data={"username": "testuser", "password": "password"})
    yield client
    client.get("/logout")


@pytest.fixture
def sample_customers(app):
    """Create sample customers for testing."""
    with app.app_context():
        source1 = Source(SSource="SRC1", SName="Source 1")
        source2 = Source(SSource="SRC2", SName="Source 2")

        cust1 = Customer(CustID="123", Name="Customer 1", Source="SRC1", State="CA")
        cust2 = Customer(CustID="124", Name="Customer 2", Source="SRC2", State="NY")
        cust3 = Customer(CustID="125", Name="Customer 3", Source="SRC1", State="CA")

        db.session.add_all([source1, source2, cust1, cust2, cust3])
        db.session.commit()
        yield
        db.session.query(Customer).delete()
        db.session.query(Source).delete()
        db.session.commit()


class TestCustomerRoutes:
    def test_customers_list_page_renders(self, client):
        """GET /customers/ should render the list page."""
        response = client.get("/customers/")
        assert response.status_code == 200
        assert b"Customers" in response.data

    def test_customers_api_endpoint_works(self, client):
        """GET /customers/api/customers should return JSON."""
        response = client.get("/customers/api/customers")
        assert response.status_code == 200
        assert response.is_json

    def test_global_search(self, client, sample_customers):
        """Test global search functionality."""
        response = client.get("/customers/api/customers?search=Customer 1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 1"

    def test_filter_by_source(self, client, sample_customers):
        """Test filtering by Source."""
        response = client.get("/customers/api/customers?filter_Source=SRC2")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 2"

    def test_filter_by_state(self, client, sample_customers):
        """Test filtering by State."""
        response = client.get("/customers/api/customers?filter_State=CA")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 2

    def test_column_filter_by_cust_id(self, client, sample_customers):
        """Test column-specific filtering by CustID."""
        response = client.get("/customers/api/customers?filter_CustID=125")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["Name"] == "Customer 3"

    def test_sorting(self, client, sample_customers):
        """Test sorting functionality."""
        response = client.get("/customers/api/customers?sorters[0][field]=Name&sorters[0][dir]=desc")
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"][0]["Name"] == "Customer 3"

    def test_pagination(self, client, sample_customers):
        """Test pagination functionality."""
        response = client.get("/customers/api/customers?page=2&size=1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["last_page"] == 3
        assert len(data["data"]) == 1

    def test_view_customer_detail(self, client, sample_customers):
        """Test viewing a customer's detail page."""
        response = client.get("/customers/view/123")
        assert response.status_code == 200
        assert b"Customer 1" in response.data

    def test_view_missing_customer_detail(self, client, sample_customers):
        """Test viewing a missing customer's detail page results in a 404."""
        response = client.get("/customers/view/9999")
        assert response.status_code == 404

    def test_create_customer_page_renders(self, client):
        """GET /customers/new should render the create page."""
        response = client.get("/customers/new")
        assert response.status_code == 200
        assert b"Create Customer" in response.data

    def test_create_customer(self, client, sample_customers):
        """Test creating a new customer."""
        # Get the last CustID to check for sequential generation
        last_cust = Customer.query.order_by(Customer.CustID.desc()).first()
        next_cust_id = int(last_cust.CustID) + 1

        response = client.post("/customers/new", data={
            "Name": "New Customer",
            "Source": "SRC1"
        }, follow_redirects=True)
        assert response.status_code == 200 # After redirect
        assert f"/customers/view/{next_cust_id}" in response.request.path

        new_cust = Customer.query.get(next_cust_id)
        assert new_cust is not None
        assert new_cust.Name == "New Customer"

    def test_create_customer_invalid_data(self, client, sample_customers):
        """Test creating a customer with invalid data."""
        response = client.post("/customers/new", data={
            "Source": "SRC1"
        })
        assert response.status_code == 200
        assert b"Name is required." in response.data

    def test_edit_customer_page_renders(self, client, sample_customers):
        """GET /customers/edit/<id> should render the edit page."""
        response = client.get("/customers/edit/123")
        assert response.status_code == 200
        assert b"Edit Customer" in response.data

    def test_update_customer(self, client, sample_customers):
        """Test updating a customer."""
        response = client.post("/customers/edit/123", data={
            "Name": "Updated Customer Name",
            "Source": "SRC1"
        }, follow_redirects=True)
        assert response.status_code == 200 # After redirect
        assert b"Updated Customer Name" in response.data

        updated_cust = Customer.query.get("123")
        assert updated_cust.Name == "Updated Customer Name"

    def test_delete_customer(self, client, sample_customers):
        """Test deleting a customer."""
        response = client.post("/customers/delete/123", follow_redirects=True)
        assert response.status_code == 200
        assert b"Customer 123 deleted." in response.data

        deleted_cust = Customer.query.get("123")
        assert deleted_cust is None

    def test_get_source_info_api(self, client, sample_customers):
        """Test the API endpoint for getting source info."""
        response = client.get("/customers/api/source_info/SRC1")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["SName"] == "Source 1"


class TestCustomerRoutesAuth:
    def test_regular_user_cannot_create_customer(self, logged_in_client, sample_customers):
        """Test that a regular user cannot create a customer."""
        response = logged_in_client.post("/customers/new", data={
            "Name": "New Customer",
            "Source": "SRC1"
        })
        assert response.status_code == 403

    def test_regular_user_cannot_edit_customer(self, logged_in_client, sample_customers):
        """Test that a regular user cannot edit a customer."""
        response = logged_in_client.post("/customers/edit/123", data={
            "Name": "Updated Customer Name",
            "Source": "SRC1"
        })
        assert response.status_code == 403

    def test_regular_user_cannot_delete_customer(self, logged_in_client, sample_customers):
        """Test that a regular user cannot delete a customer."""
        response = logged_in_client.post("/customers/delete/123")
        assert response.status_code == 403
