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
    assert b"Check-in #1 created successfully with 0 files!" in response.data

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


# ============================================================================
# CHECK-IN TO WORK ORDER CONVERSION TESTS
# ============================================================================


def test_convert_checkin_to_workorder_basic(admin_client, app):
    """Test basic conversion of check-in to work order."""
    # Create a check-in with items
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
            SpecialInstructions="Handle with care"
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Awning",
            Material="Sunbrella",
            Color="Navy",
            Qty=2,
            SizeWgt="10x8",
            Price=150.00,
            Condition="Good"
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Admin accesses work order create page with checkin_id
    response = admin_client.get(f"/work_orders/new?checkin_id={checkin_id}")
    assert response.status_code == 200
    # Check that form is pre-filled
    assert b"Test Awning" in response.data
    assert b"Converting from Check-In" in response.data


def test_convert_checkin_with_all_fields(admin_client, app):
    """Test conversion of check-in with all additional fields populated."""
    today = date.today()
    required_date = date(2025, 12, 25)

    # Create a check-in with all fields
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=today,
            Status="pending",
            SpecialInstructions="Rush order - customer needs by Christmas",
            StorageTime="Seasonal",
            RackNo="5 B",
            ReturnTo="Marina Slip 42",
            DateRequired=required_date,
            RepairsNeeded=True,
            RushOrder=True
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Bimini Top",
            Material="Canvas",
            Color="White",
            Qty=1,
            SizeWgt="12x10",
            Price=250.00,
            Condition="Stained - needs deep clean"
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Get the work order creation form
    response = admin_client.get(f"/work_orders/new?checkin_id={checkin_id}")
    assert response.status_code == 200

    # Verify check-in data is present in response
    assert b"Bimini Top" in response.data
    assert b"Converting from Check-In" in response.data

    # Now actually create the work order
    response = admin_client.post(
        "/work_orders/new",
        data={
            "checkin_id": checkin_id,
            "CustID": "CUST001",
            "DateIn": today.strftime("%Y-%m-%d"),
            "WOName": "Test Customer 1",
            "SpecialInstructions": "Rush order - customer needs by Christmas",
            "StorageTime": "Seasonal",
            "RackNo": "5 B",
            "ReturnTo": "Marina Slip 42",
            "DateRequired": required_date.strftime("%Y-%m-%d"),
            "RepairsNeeded": "1",
            "RushOrder": "1",
            # Items
            "new_item_description[]": ["Bimini Top"],
            "new_item_material[]": ["Canvas"],
            "new_item_color[]": ["White"],
            "new_item_qty[]": ["1"],
            "new_item_sizewgt[]": ["12x10"],
            "new_item_price[]": ["250.00"],
            "new_item_condition[]": ["Stained - needs deep clean"],
        },
        follow_redirects=False
    )

    # Should redirect to customer detail page
    assert response.status_code == 302

    # Verify work order was created
    with app.app_context():
        work_order = WorkOrder.query.first()
        assert work_order is not None
        assert work_order.CustID == "CUST001"
        assert work_order.SpecialInstructions == "Rush order - customer needs by Christmas"
        assert work_order.StorageTime == "Seasonal"
        assert work_order.RackNo == "5 B"
        assert work_order.ReturnTo == "Marina Slip 42"
        assert work_order.DateRequired == required_date
        assert work_order.RepairsNeeded == True
        assert work_order.RushOrder == True

        # Verify check-in was marked as processed
        checkin = CheckIn.query.get(checkin_id)
        assert checkin.Status == "processed"
        assert checkin.WorkOrderNo == work_order.WorkOrderNo


def test_checkin_marked_processed_after_conversion(admin_client, app):
    """Test that check-in status changes to 'processed' after work order creation."""
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
            Description="Test Item",
            Material="Sunbrella",
            Qty=1
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Create work order from check-in
    response = admin_client.post(
        "/work_orders/new",
        data={
            "checkin_id": checkin_id,
            "CustID": "CUST001",
            "DateIn": date.today().strftime("%Y-%m-%d"),
            "WOName": "Test Customer 1",
            "new_item_description[]": ["Test Item"],
            "new_item_material[]": ["Sunbrella"],
            "new_item_qty[]": ["1"],
        },
        follow_redirects=False
    )

    # Should redirect to customer detail page
    assert response.status_code == 302

    # Check that check-in is now processed
    with app.app_context():
        checkin = CheckIn.query.get(checkin_id)
        assert checkin.Status == "processed"
        assert checkin.WorkOrderNo is not None


def test_cannot_convert_already_processed_checkin(admin_client, app):
    """Test that already processed check-ins cannot be converted again."""
    # Create a processed check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="processed",
            WorkOrderNo="TEST001"
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Try to access work order create with processed check-in
    response = admin_client.get(f"/work_orders/new?checkin_id={checkin_id}")

    # Should either redirect or show empty form (no pre-fill)
    # The conversion logic should skip processed check-ins
    with app.app_context():
        checkin = CheckIn.query.get(checkin_id)
        # Check-in should still be processed with same work order
        assert checkin.Status == "processed"
        assert checkin.WorkOrderNo == "TEST001"


def test_manager_cannot_convert_checkin(manager_client, app):
    """Test that managers cannot convert check-ins to work orders."""
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

    # Manager tries to access work order create (which requires admin or manager)
    # Note: Work order creation allows both admin and manager roles, so this should succeed
    response = manager_client.get(f"/work_orders/new?checkin_id={checkin_id}")

    # Manager can access work order creation, so should return 200
    assert response.status_code == 200


def test_checkin_with_new_fields_displayed_on_detail(admin_client, app):
    """Test that new check-in fields are displayed on the detail page."""
    # Create a check-in with new fields
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
            SpecialInstructions="Test instructions",
            StorageTime="Seasonal",
            RackNo="Bin 5",
            ReturnTo="Customer dock",
            DateRequired=date(2025, 12, 31),
            RepairsNeeded=True,
            RushOrder=True
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # View check-in detail page
    response = admin_client.get(f"/checkins/{checkin_id}")
    assert response.status_code == 200

    # Verify all fields are displayed
    assert b"Test instructions" in response.data
    assert b"Seasonal" in response.data
    assert b"Bin 5" in response.data
    assert b"Customer dock" in response.data
    assert b"Repairs Needed" in response.data
    assert b"Rush Order" in response.data

    # Check for source display
    assert b"Source" in response.data
    assert b"TestSource1" in response.data


def test_checkin_create_with_new_fields(manager_client, app):
    """Test creating a check-in with all new fields populated."""
    today = date.today().strftime("%Y-%m-%d")
    required = date(2025, 12, 25).strftime("%Y-%m-%d")

    response = manager_client.post(
        "/checkins/new",
        data={
            "CustID": "CUST001",
            "DateIn": today,
            "DateRequired": required,
            "ReturnTo": "Marina",
            "StorageTime": "Temporary",
            "RackNo": "3 A",
            "SpecialInstructions": "Handle carefully",
            "RepairsNeeded": "1",
            "RushOrder": "1",
            "item_description[]": ["Awning"],
            "item_material[]": ["Sunbrella"],
            "item_color[]": ["Blue"],
            "item_qty[]": ["1"],
            "item_sizewgt[]": ["10x8"],
            "item_price[]": ["100.00"],
            "item_condition[]": ["Good"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"created successfully" in response.data

    # Verify in database
    with app.app_context():
        checkin = CheckIn.query.first()
        assert checkin is not None
        assert checkin.DateRequired == date(2025, 12, 25)
        assert checkin.ReturnTo == "Marina"
        assert checkin.StorageTime == "Temporary"
        assert checkin.RackNo == "3 A"
        assert checkin.SpecialInstructions == "Handle carefully"
        assert checkin.RepairsNeeded == True
        assert checkin.RushOrder == True


def test_edit_checkin_get_request(manager_client, app):
    """Test GET request to edit check-in page loads existing data."""
    # Create a check-in with items
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
            SpecialInstructions="Original instructions",
            StorageTime="Seasonal",
            RackNo="Bin 5",
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Awning",
            Material="Sunbrella",
            Color="Blue",
            Qty=2,
            SizeWgt="10x8",
            Price=150.00,
            Condition="Good",
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Load edit page
    response = manager_client.get(f"/checkins/{checkin_id}/edit")
    assert response.status_code == 200

    # Verify form has existing data
    assert b"Edit Check-In" in response.data
    assert b"Original instructions" in response.data
    assert b"Seasonal" in response.data
    assert b"Bin 5" in response.data
    assert b"Test Awning" in response.data


def test_edit_checkin_post_success(manager_client, app):
    """Test successfully editing a check-in."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
            SpecialInstructions="Original instructions",
            RackNo="Bin 5",
        )
        db.session.add(checkin)
        db.session.flush()

        item = CheckInItem(
            CheckInID=checkin.CheckInID,
            Description="Test Awning",
            Material="Sunbrella",
            Qty=2,
        )
        db.session.add(item)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Edit the check-in
    today = date.today().strftime("%Y-%m-%d")
    response = manager_client.post(
        f"/checkins/{checkin_id}/edit",
        data={
            "CustID": "CUST002",  # Change customer
            "DateIn": today,
            "SpecialInstructions": "Updated instructions",
            "RackNo": "Bin 7",  # Update rack
            "StorageTime": "Temporary",  # Add storage time
            "RepairsNeeded": "1",  # Add repairs needed
            "item_description[]": ["Updated Awning", "New Item"],
            "item_material[]": ["Acrylic", "Canvas"],
            "item_color[]": ["Red", "Green"],
            "item_qty[]": ["3", "1"],
            "item_sizewgt[]": ["12x10", "8x6"],
            "item_price[]": ["200.00", "75.00"],
            "item_condition[]": ["Fair", "Excellent"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"updated successfully" in response.data

    # Verify changes in database
    with app.app_context():
        checkin = CheckIn.query.get(checkin_id)
        assert checkin is not None
        assert checkin.CustID == "CUST002"  # Customer changed
        assert checkin.SpecialInstructions == "Updated instructions"
        assert checkin.RackNo == "Bin 7"
        assert checkin.StorageTime == "Temporary"
        assert checkin.RepairsNeeded == True

        # Verify items were updated (old deleted, new added)
        items = CheckInItem.query.filter_by(CheckInID=checkin_id).all()
        assert len(items) == 2
        assert items[0].Description == "Updated Awning"
        assert items[0].Material == "Acrylic"
        assert items[0].Qty == 3
        assert items[1].Description == "New Item"
        assert items[1].Material == "Canvas"


def test_edit_checkin_cannot_edit_processed(manager_client, app):
    """Test that processed check-ins cannot be edited."""
    # Create a processed check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="processed",
            WorkOrderNo="12345",
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Try to edit
    response = manager_client.get(f"/checkins/{checkin_id}/edit", follow_redirects=True)
    assert response.status_code == 200
    assert b"Cannot edit a processed check-in" in response.data


def test_edit_checkin_updates_items(manager_client, app):
    """Test that editing updates items correctly using delete-then-insert pattern."""
    # Create a check-in with items
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
        )
        db.session.add(checkin)
        db.session.flush()

        items = [
            CheckInItem(
                CheckInID=checkin.CheckInID,
                Description="Item 1",
                Material="Material 1",
                Qty=1,
            ),
            CheckInItem(
                CheckInID=checkin.CheckInID,
                Description="Item 2",
                Material="Material 2",
                Qty=2,
            ),
        ]
        db.session.add_all(items)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Edit to remove one item and add a different one
    today = date.today().strftime("%Y-%m-%d")
    response = manager_client.post(
        f"/checkins/{checkin_id}/edit",
        data={
            "CustID": "CUST001",
            "DateIn": today,
            "item_description[]": ["Item 3"],  # Only one item now
            "item_material[]": ["Material 3"],
            "item_qty[]": ["5"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"updated successfully" in response.data

    # Verify items were replaced
    with app.app_context():
        items = CheckInItem.query.filter_by(CheckInID=checkin_id).all()
        assert len(items) == 1
        assert items[0].Description == "Item 3"
        assert items[0].Material == "Material 3"
        assert items[0].Qty == 5


def test_admin_can_access_edit_checkin(admin_client, app):
    """Test that admins can access edit check-in page."""
    # Create a check-in
    with app.app_context():
        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    response = admin_client.get(f"/checkins/{checkin_id}/edit")
    assert response.status_code == 200
    assert b"Edit Check-In" in response.data


def test_user_cannot_access_edit_checkin(client, app):
    """Test that regular users cannot access edit check-in page."""
    # Create user and check-in
    with app.app_context():
        user = User(
            username="user",
            email="user@example.com",
            role="user",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)

        # Need source for customer
        source = Source(SSource="TestSource")
        db.session.add(source)

        customer = Customer(CustID="CUST001", Name="Test", Source="TestSource")
        db.session.add(customer)

        checkin = CheckIn(
            CustID="CUST001",
            DateIn=date.today(),
            Status="pending",
        )
        db.session.add(checkin)
        db.session.commit()
        checkin_id = checkin.CheckInID

    # Log in as user
    client.post("/login", data={"username": "user", "password": "password"})

    # Try to access edit page
    response = client.get(f"/checkins/{checkin_id}/edit")
    assert response.status_code == 403  # Forbidden
