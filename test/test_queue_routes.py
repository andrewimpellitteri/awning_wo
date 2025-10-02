"""
Tests for Queue Management routes.
"""

import pytest
from models.work_order import WorkOrder
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
def sample_customers_and_work_orders(app):
    """Create sample customers and work orders for testing queue management."""
    from models.customer import Customer
    from models.work_order import WorkOrder

    with app.app_context():
        # Create sample customers
        c1 = Customer(CustID="C001", Name="Customer 1")
        c2 = Customer(CustID="C002", Name="Customer 2")
        c3 = Customer(CustID="C003", Name="Customer 3")
        db.session.add_all([c1, c2, c3])
        db.session.commit()

        # Create sample work orders linked to customers
        wo1 = WorkOrder(
            WorkOrderNo="1001",
            WOName="Regular Order",
            DateIn="2024-01-10",
            CustID=c1.CustID,
        )
        wo2 = WorkOrder(
            WorkOrderNo="1002",
            WOName="Rush Order",
            RushOrder="1",
            DateIn="2024-01-12",
            CustID=c2.CustID,
        )
        wo3 = WorkOrder(
            WorkOrderNo="1003",
            WOName="Firm Rush Order",
            FirmRush="1",
            DateIn="2024-01-11",
            CustID=c3.CustID,
        )

        db.session.add_all([wo1, wo2, wo3])
        db.session.commit()
        yield
        db.session.query(WorkOrder).delete()
        db.session.query(Customer).delete()
        db.session.commit()


class TestQueueRoutes:
    def test_queue_page_renders(self, logged_in_client):
        """GET /cleaning_queue/cleaning-queue should render the queue page."""
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Cleaning Queue" in response.data

    def test_queue_sorting_by_priority(
        self, logged_in_client, sample_customers_and_work_orders
    ):
        """Test that the queue is sorted by priority according to queue_position."""
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200

        # Parse the displayed work order numbers
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.data, "html.parser")
        displayed_orders = [el.text.strip() for el in soup.select(".work-order-name")]

        expected_order = ["Firm Rush Order", "Rush Order", "Regular Order"]
        assert displayed_orders == expected_order

    def test_queue_search(self, logged_in_client, sample_customers_and_work_orders):
        """Test the search functionality on the queue page."""
        response = logged_in_client.get(
            "/cleaning_queue/cleaning-queue?search=Rush Order"
        )
        assert response.status_code == 200
        assert b"Rush Order" in response.data
        assert b"Regular Order" not in response.data

    def test_queue_reorder_api(
        self, logged_in_client, sample_customers_and_work_orders
    ):
        """Test the queue reorder API."""
        # Get the initial order
        wo1 = WorkOrder.query.get("1001")
        wo2 = WorkOrder.query.get("1002")
        wo3 = WorkOrder.query.get("1003")

        # Reorder
        new_order = [wo2.WorkOrderNo, wo1.WorkOrderNo, wo3.WorkOrderNo]
        response = logged_in_client.post(
            "/cleaning_queue/api/cleaning-queue/reorder",
            json={"work_order_ids": new_order},
        )

        assert response.status_code == 200
        assert response.get_json()["success"] is True

        assert WorkOrder.query.get("1002").QueuePosition == 1
        assert WorkOrder.query.get("1001").QueuePosition == 2
        assert WorkOrder.query.get("1003").QueuePosition == 3

    def test_queue_summary_api(
        self, logged_in_client, sample_customers_and_work_orders
    ):
        """Test the queue summary API."""
        response = logged_in_client.get("/cleaning_queue/api/cleaning-queue/summary")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()["counts"]
        assert data["total"] == 3
        assert data["rush"] == 1
        assert data["firm_rush"] == 1
