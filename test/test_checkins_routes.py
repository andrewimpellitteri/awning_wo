"""
Tests for Check-in CRUD routes and conversion to work orders.
"""

import pytest
from datetime import date, datetime
from models.checkin import CheckIn, CheckInItem
from models.customer import Customer
from models.source import Source
from models.user import User
from models.work_order import WorkOrder
from extensions import db
from werkzeug.security import generate_password_hash


@pytest.fixture
def manager_client(client, app):
    """Provide a logged-in client with a manager user and sample data."""
    with app.app_context():
        # Create sources first (required for foreign key constraint)
        sources = [Source(SSource=s) for s in ["TestSource1", "TestSource2"]]
        db.session.add_all(sources)

        # Create manager user
        manager = User(
            username="manager",
            email="manager@example.com",
            role="manager",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(manager)

        # Create sample customers
        customers = [
            Customer(
                CustID="CUST001",
                Name="Test Customer 1",
                Source="TestSource1",
                Contact="John Doe",
                Address="123 Main St",
                City="Test City",
                State="CA",
            ),
            Customer(
                CustID="CUST002",
                Name="Test Customer 2",
                Source="TestSource2",
                Contact="Jane Smith",
            ),
        ]
        db.session.add_all(customers)
        db.session.commit()

        # Log in as manager
        client.post("/login", data={"username": "manager", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with an admin user and sample data."""
    with app.app_context():
        # Create sources first
        sources = [Source(SSource=s) for s in ["TestSource1", "TestSource2"]]
        db.session.add_all(sources)

        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(admin)

        # Create sample customers
        customers = [
            Customer(
                CustID="CUST001",
                Name="Test Customer 1",
                Source="TestSource1",
                Contact="John Doe",
            ),
            Customer(
                CustID="CUST002",
                Name="Test Customer 2",
                Source="TestSource2",
            ),
        ]
        db.session.add_all(customers)
        db.session.commit()

        # Log in as admin
        client.post("/login", data={"username": "admin", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def user_client(client, app):
    """Provide a logged-in client with a regular user (should not have access)."""
    with app.app_context():
        user = User(
            username="regularuser",
            email="user@example.com",
            role="user",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)
        db.session.commit()

        client.post("/login", data={"username": "regularuser", "password": "password"})
        yield client
        client.get("/logout")


# ============================================================================
# PERMISSION TESTS
# ============================================================================


def test_user_cannot_access_checkins_new(user_client):
    """Regular users should not be able to access check-in creation."""
    response = user_client.get("/checkins/new")
    assert response.status_code == 403  # Forbidden


def test_user_cannot_access_checkins_pending(user_client):
    """Regular users should not be able to access pending check-ins."""
    response = user_client.get("/checkins/pending")
    assert response.status_code == 403  # Forbidden


def test_manager_can_access_checkins_new(manager_client):
    """Managers should be able to access check-in creation."""
    response = manager_client.get("/checkins/new")
    assert response.status_code == 200
    assert b"New Check-In" in response.data


def test_admin_can_access_checkins_new(admin_client):
    """Admins should be able to access check-in creation."""
    response = admin_client.get("/checkins/new")
    assert response.status_code == 200
    assert b"New Check-In" in response.data


# ============================================================================
# CHECK-IN CRUD TESTS
# ============================================================================


def test_create_checkin_success(manager_client, app):
    """Test successfully creating a check-in with items."""
    today = date.today().strftime("%Y-%m-%d")

    response = manager_client.post(
        "/checkins/new",
        data={
            "CustID": "CUST001",
            "DateIn": today,
            "item_description[]": ["Awning", "Bimini Top"],
            "item_material[]": ["Sunbrella", "Canvas"],
            "item_color[]": ["Navy Blue", "White"],
            "item_qty[]": ["2", "1"],
            "item_sizewgt[]": ["10x8", "12x10"],
            "item_price[]": ["150.00", "200.00"],
            "item_condition[]": ["Good", "Stained"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Check-in #1 created successfully!" in response.data

    # Verify in database
    with app.app_context():
        checkin = CheckIn.query.first()
        assert checkin is not None
        assert checkin.CustID == "CUST001"
        assert checkin.Status == "pending"
        assert len(checkin.items) == 2
        assert checkin.items[0].Description == "Awning"
        assert checkin.items[1].Description == "Bimini Top"


def test_create_checkin_missing_customer(manager_client):
    """Test creating a check-in without a customer (should fail)."""
    today = date.today().strftime("%Y-%m-%d")

    response = manager_client.post(
        "/checkins/new",
        data={
            "DateIn": today,
            "item_description[]": ["Awning"],
            "item_material[]": ["Sunbrella"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Customer is required" in response.data


def test_view_pending_checkins_empty(manager_client):
    """Test viewing pending check-ins when there are none."""
    response = manager_client.get("/checkins/pending")
    assert response.status_code == 200
    assert b"No Pending Check-Ins" in response.data or b"0 pending check-in(s)" in response.data


def test_view_pending_checkins_with_data(manager_client, app):
    """Test viewing pending check-ins with existing data."""
    # Create a check-in first
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Awning",
            Material="Sunbrella",
            Qty=1
        )
        db.session.add(item)
        db.session.commit()

    response = manager_client.get("/checkins/pending")
    assert response.status_code == 200
    assert b"Test Customer 1" in response.data
    assert b"1 item(s)" in response.data


def test_view_checkin_detail(manager_client, app):
    """Test viewing a specific check-in's details."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Awning",
            Material="Sunbrella",
            Color="Navy",
            Qty=2,
            Price=150.00
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = manager_client.get(f"/checkins/{checkin_id}")
    assert response.status_code == 200
    assert b"Check-In #1" in response.data
    assert b"Test Awning" in response.data
    assert b"Sunbrella" in response.data
    assert b"Navy" in response.data


def test_delete_pending_checkin(manager_client, app):
    """Test deleting a pending check-in."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = manager_client.post(
        f"/checkins/{checkin_id}/delete",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"deleted successfully" in response.data

    # Verify deleted from database
    with app.app_context():
        checkin = CheckIn.query.get(checkin_id)
        assert checkin is None


def test_cannot_delete_processed_checkin(manager_client, app):
    """Test that processed check-ins cannot be deleted."""
    # Create a processed check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="processed",
            WorkOrderNo="WO123"
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = manager_client.post(
        f"/checkins/{checkin_id}/delete",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Cannot delete a processed check-in" in response.data

    # Verify still in database
    with app.app_context():
        checkin = CheckIn.query.get(checkin_id)
        assert checkin is not None


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


def test_customer_search_api(manager_client):
    """Test customer search API for Selectize.js."""
    response = manager_client.get("/checkins/api/customer_search?q=Test")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["value"] in ["CUST001", "CUST002"]
    assert "Test Customer" in data[0]["text"]
    # Check that source information is included
    assert "source" in data[0]
    assert "name" in data[0]
    assert "contact" in data[0]


def test_customer_search_api_min_length(manager_client):
    """Test customer search API requires at least 2 characters."""
    response = manager_client.get("/checkins/api/customer_search?q=T")
    assert response.status_code == 200
    data = response.get_json()
    assert data == []


def test_pending_count_api(manager_client, app):
    """Test pending check-ins count API."""
    # Create 2 pending and 1 processed check-in
    with app.app_context():
        checkin1 = CheckIn(CustID="CUST001", DateIn=date.today(), Status="pending")
        checkin2 = CheckIn(CustID="CUST002", DateIn=date.today(), Status="pending")
        checkin3 = CheckIn(CustID="CUST001", DateIn=date.today(), Status="processed")
        db.session.add_all([checkin1, checkin2, checkin3])
        db.session.commit()

    response = manager_client.get("/checkins/api/pending_count")
    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 2


# ============================================================================
# ROLE-BASED CONVERSION TESTS
# ============================================================================


def test_manager_cannot_see_convert_button(manager_client, app):
    """Test that managers cannot see the 'Edit as Work Order' button."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = manager_client.get(f"/checkins/{checkin_id}")
    assert response.status_code == 200
    # Should show manager warning, not the convert button
    assert b"Only admins can convert check-ins to work orders" in response.data
    assert b"Edit as Work Order" not in response.data


def test_admin_can_see_convert_button(admin_client, app):
    """Test that admins can see the 'Edit as Work Order' button."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = admin_client.get(f"/checkins/{checkin_id}")
    assert response.status_code == 200
    assert b"Edit as Work Order" in response.data


# ============================================================================
# CHECK-IN MODEL TESTS
# ============================================================================


def test_checkin_model_to_dict(app):
    """Test CheckIn model to_dict method."""
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date(2025, 1, 15),
            Status="pending"
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Item",
            Material="Sunbrella",
            Qty=1,
            Price=100.00
        )
        db.session.add(item)
        db.session.commit()

        data = checkin.to_dict()
        assert data["CustID"] == "CUST001"
        assert data["DateIn"] == "01/15/2025"
        assert data["Status"] == "pending"
        assert len(data["items"]) == 1
        assert data["items"][0]["Description"] == "Test Item"


def test_checkinitem_model_to_dict(app):
    """Test CheckInItem model to_dict method."""
    with app.app_context():
        checkin = CheckIn(CustID="CUST001", DateIn=date.today(), Status="pending")
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Awning",
            Material="Sunbrella",
            Color="Navy",
            Qty=2,
            SizeWgt="10x8",
            Price=150.00,
            Condition="Good"
        )
        db.session.add(item)
        db.session.commit()

        data = item.to_dict()
        assert data["Description"] == "Awning"
        assert data["Material"] == "Sunbrella"
        assert data["Color"] == "Navy"
        assert data["Qty"] == 2
        assert data["SizeWgt"] == "10x8"
        assert data["Price"] == 150.00
        assert data["Condition"] == "Good"
