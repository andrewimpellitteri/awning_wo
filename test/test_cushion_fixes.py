
import pytest
from models.work_order import WorkOrder
from datetime import date
from werkzeug.security import generate_password_hash
from models.user import User
from extensions import db

@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with admin privileges."""
    with app.app_context():
        # Ensure clean state for user
        existing_user = User.query.filter_by(username="admin").first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()

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

@pytest.mark.unit
def test_cushion_field_in_to_dict(app):
    """
    repro: Ensure isCushion field is included in to_dict serialization.
    """
    with app.app_context():
        # Create a work order with isCushion=True
        wo = WorkOrder(
            WorkOrderNo="TEST-REPRO",
            CustID="999",
            WOName="Cushion Repro",
            isCushion=True
        )
        
        # Serialize
        data = wo.to_dict()
        
        # Verify
        assert "isCushion" in data, "isCushion field is missing from to_dict"
        assert data["isCushion"] is True, "isCushion should be True"

@pytest.mark.unit
def test_cushion_field_in_api_response(admin_client, app):
    """
    Ensure isCushion field is included in API response.
    """
    with app.app_context():
        # Create a work order
        wo = WorkOrder(
            WorkOrderNo="TEST-API-CUSHION",
            CustID="999",
            WOName="API Cushion Test",
            isCushion=True
        )
        db.session.add(wo)
        db.session.commit()
        
        # Call API
        response = admin_client.get("/work_orders/api/work_orders?search=TEST-API-CUSHION")
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify
        found = False
        for item in data["data"]:
            if item["WorkOrderNo"] == "TEST-API-CUSHION":
                assert "isCushion" in item, "isCushion missing from API response item"
                assert item["isCushion"] is True
                found = True
                break
        assert found, "Test work order not found in API response"
