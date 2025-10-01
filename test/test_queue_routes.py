"""
Tests for Queue Management routes.
"""

import pytest
from models.work_order import WorkOrder
from extensions import db


@pytest.fixture
def sample_work_orders(app):
    """Create sample work orders for testing queue management."""
    with app.app_context():
        wo1 = WorkOrder(WorkOrderNo="1001", WOName="Regular Order", DateIn="2024-01-10")
        wo2 = WorkOrder(WorkOrderNo="1002", WOName="Rush Order", RushOrder="YES", DateIn="2024-01-12")
        wo3 = WorkOrder(WorkOrderNo="1003", WOName="Firm Rush Order", FirmRush="YES", DateIn="2024-01-11")

        db.session.add_all([wo1, wo2, wo3])
        db.session.commit()
        yield
        db.session.query(WorkOrder).delete()
        db.session.commit()


class TestQueueRoutes:
    def test_queue_page_renders(self, client):
        """GET /cleaning_queue/cleaning-queue should render the queue page."""
        response = client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Cleaning Queue" in response.data

    def test_queue_sorting_by_priority(self, client, sample_work_orders):
        """Test that the queue is sorted by priority."""
        response = client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        firm_rush_index = response_data.find("Firm Rush Order")
        rush_index = response_data.find("Rush Order")
        regular_index = response_data.find("Regular Order")

        assert firm_rush_index < rush_index < regular_index

    def test_queue_search(self, client, sample_work_orders):
        """Test the search functionality on the queue page."""
        response = client.get("/cleaning_queue/cleaning-queue?search=Rush Order")
        assert response.status_code == 200
        assert b"Rush Order" in response.data
        assert b"Regular Order" not in response.data

    def test_queue_reorder_api(self, client, sample_work_orders):
        """Test the queue reorder API."""
        # Get the initial order
        wo1 = WorkOrder.query.get("1001")
        wo2 = WorkOrder.query.get("1002")
        wo3 = WorkOrder.query.get("1003")

        # Reorder
        new_order = [wo2.WorkOrderNo, wo1.WorkOrderNo, wo3.WorkOrderNo]
        response = client.post("/cleaning_queue/api/cleaning-queue/reorder", json={"new_order": new_order})
        assert response.status_code == 200
        assert response.get_json()["success"] is True

        # Check the new order in the database
        assert WorkOrder.query.get("1002").queue_position == 0
        assert WorkOrder.query.get("1001").queue_position == 1
        assert WorkOrder.query.get("1003").queue_position == 2

    def test_queue_summary_api(self, client, sample_work_orders):
        """Test the queue summary API."""
        response = client.get("/cleaning_queue/api/cleaning-queue/summary")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["total_orders"] == 3
        assert data["rush_orders"] == 1
        assert data["firm_rush_orders"] == 1
