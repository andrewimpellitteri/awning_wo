"""
Tests for In-Progress routes.
"""

import pytest
from datetime import date
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
            email="testuser@example.com",
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)
        db.session.commit()

        client.post("/login", data={"username": "testuser", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def sample_work_orders(app):
    """Create sample work orders for testing in-progress views."""
    from models.customer import Customer
    with app.app_context():
        c1 = Customer(CustID="C001", Name="Test Customer")
        db.session.add(c1)
        db.session.commit()

        wo1 = WorkOrder(
            WorkOrderNo="1001",
            WOName="In-Progress Order",
            ProcessingStatus=True,
            DateIn=date(2024, 1, 10),
            CustID=c1.CustID,
        )
        wo2 = WorkOrder(
            WorkOrderNo="1002",
            WOName="Cleaned Order",
            Clean=date(2024, 1, 12),
            DateIn=date(2024, 1, 11),
            CustID=c1.CustID,
        )
        wo3 = WorkOrder(
            WorkOrderNo="1003",
            WOName="Treated Order",
            Treat=date(2024, 1, 13),
            DateIn=date(2024, 1, 12),
            CustID=c1.CustID,
        )
        wo4 = WorkOrder(
            WorkOrderNo="1004",
            WOName="Packaged Order",
            final_location="Shelf A",
            DateIn=date(2024, 1, 13),
            CustID=c1.CustID,
        )
        wo5 = WorkOrder(
            WorkOrderNo="1005",
            WOName="Completed Order",
            DateCompleted=date(2024, 1, 14),
            DateIn=date(2024, 1, 14),
            CustID=c1.CustID,
        )

        db.session.add_all([wo1, wo2, wo3, wo4, wo5])
        db.session.commit()
        yield
        db.session.query(WorkOrder).delete()
        db.session.query(Customer).delete()
        db.session.commit()


class TestInProgressRoutes:
    def test_all_recent_page_renders(self, logged_in_client, sample_work_orders):
        """GET /in_progress/all_recent should render the page with all recent orders."""
        response = logged_in_client.get("/in_progress/all_recent")
        assert response.status_code == 200
        assert b"All Recent Work Orders" in response.data
        assert b"In-Progress Order" in response.data
        assert b"Cleaned Order" in response.data
        assert b"Treated Order" in response.data
        assert b"Packaged Order" in response.data
        assert b"Completed Order" not in response.data

    def test_in_progress_page_renders(self, logged_in_client, sample_work_orders):
        """GET /in_progress/list_in_progress should render the page with in-progress orders."""
        response = logged_in_client.get("/in_progress/list_in_progress")
        assert response.status_code == 200
        assert b"Work Orders Currently Being Processed" in response.data
        assert b"In-Progress Order" in response.data
        assert b"Cleaned Order" not in response.data

    def test_cleaned_page_renders(self, logged_in_client, sample_work_orders):
        """GET /in_progress/list_cleaned should render the page with cleaned orders."""
        response = logged_in_client.get("/in_progress/list_cleaned")
        assert response.status_code == 200
        assert b"Work Orders Recently Cleaned" in response.data
        assert b"Cleaned Order" in response.data
        assert b"In-Progress Order" not in response.data

    def test_treated_page_renders(self, logged_in_client, sample_work_orders):
        """GET /in_progress/list_treated should render the page with treated orders."""
        response = logged_in_client.get("/in_progress/list_treated")
        assert response.status_code == 200
        assert b"Work Orders Recently Treated" in response.data
        assert b"Treated Order" in response.data
        assert b"In-Progress Order" not in response.data

    def test_packaged_page_renders(self, logged_in_client, sample_work_orders):
        """GET /in_progress/list_packaged should render the page with packaged orders."""
        response = logged_in_client.get("/in_progress/list_packaged")
        assert response.status_code == 200
        assert b"Work Orders Recently Packaged" in response.data
        assert b"Packaged Order" in response.data
        assert b"In-Progress Order" not in response.data

    def test_treat_work_order(self, logged_in_client, sample_work_orders):
        """POST /in_progress/treat_work_order/<work_order_no> should update the treat date."""
        response = logged_in_client.post("/in_progress/treat_work_order/1002",
                                       json={"treatDate": "2024-01-15"})
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        work_order = WorkOrder.query.get("1002")
        assert work_order.Treat == date(2024, 1, 15)

    def test_package_work_order(self, logged_in_client, sample_work_orders):
        """POST /in_progress/package_work_order/<work_order_no> should update the final location."""
        response = logged_in_client.post("/in_progress/package_work_order/1003",
                                       json={"finalLocation": "Shelf B"})
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        work_order = WorkOrder.query.get("1003")
        assert work_order.final_location == "Shelf B"

    def test_complete_work_order(self, logged_in_client, sample_work_orders):
        """POST /in_progress/complete_work_order/<work_order_no> should update the date completed."""
        response = logged_in_client.post("/in_progress/complete_work_order/1004",
                                       json={"dateCompleted": "2024-01-16"})
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        work_order = WorkOrder.query.get("1004")
        assert work_order.DateCompleted.date() == date(2024, 1, 16)
