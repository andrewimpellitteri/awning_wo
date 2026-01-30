"""
Tests for In-Progress routes.
"""

import pytest
from datetime import date
from models.work_order import WorkOrder
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

    def test_treated_excludes_empty_final_location(self, logged_in_client, app):
        """Treated tab should show WO with treat date but empty final_location."""
        from models.customer import Customer
        with app.app_context():
            c1 = Customer(CustID="C002", Name="Test Customer 2")
            db.session.add(c1)
            db.session.commit()

            # Create WO with clean, treat, and empty final_location (like 56365)
            wo_treated = WorkOrder(
                WorkOrderNo="2001",
                WOName="Treated with Empty Location",
                Clean=date(2024, 1, 12),
                Treat=date(2024, 1, 13),
                final_location="",  # Empty string, not NULL
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            db.session.add(wo_treated)
            db.session.commit()

            # Check treated tab - should include this WO
            response = logged_in_client.get("/in_progress/list_treated")
            assert response.status_code == 200
            assert b"Treated with Empty Location" in response.data

            # Check packaged tab - should NOT include this WO
            response = logged_in_client.get("/in_progress/list_packaged")
            assert response.status_code == 200
            assert b"Treated with Empty Location" not in response.data

            db.session.query(WorkOrder).filter_by(WorkOrderNo="2001").delete()
            db.session.query(Customer).filter_by(CustID="C002").delete()
            db.session.commit()

    def test_cleaned_excludes_empty_final_location(self, logged_in_client, app):
        """Cleaned tab should show WO with clean date but no treat and empty final_location."""
        from models.customer import Customer
        with app.app_context():
            c1 = Customer(CustID="C003", Name="Test Customer 3")
            db.session.add(c1)
            db.session.commit()

            # Create WO with clean only and empty final_location (like 56376)
            wo_cleaned = WorkOrder(
                WorkOrderNo="3001",
                WOName="Cleaned with Empty Location",
                Clean=date(2024, 1, 12),
                Treat=None,
                final_location="",  # Empty string, not NULL
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            db.session.add(wo_cleaned)
            db.session.commit()

            # Check cleaned tab - should include this WO
            response = logged_in_client.get("/in_progress/list_cleaned")
            assert response.status_code == 200
            assert b"Cleaned with Empty Location" in response.data

            # Check packaged tab - should NOT include this WO
            response = logged_in_client.get("/in_progress/list_packaged")
            assert response.status_code == 200
            assert b"Cleaned with Empty Location" not in response.data

            # Check treated tab - should NOT include this WO
            response = logged_in_client.get("/in_progress/list_treated")
            assert response.status_code == 200
            assert b"Cleaned with Empty Location" not in response.data

            db.session.query(WorkOrder).filter_by(WorkOrderNo="3001").delete()
            db.session.query(Customer).filter_by(CustID="C003").delete()
            db.session.commit()

    def test_packaged_requires_non_empty_final_location(self, logged_in_client, app):
        """Packaged tab should only show WOs with actual (non-empty) final_location."""
        from models.customer import Customer
        with app.app_context():
            c1 = Customer(CustID="C004", Name="Test Customer 4")
            db.session.add(c1)
            db.session.commit()

            # Create WO with actual final_location
            wo_packaged = WorkOrder(
                WorkOrderNo="4001",
                WOName="Actually Packaged",
                Clean=date(2024, 1, 12),
                Treat=date(2024, 1, 13),
                final_location="Shelf C",  # Non-empty location
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            # Create WO with empty final_location
            wo_not_packaged = WorkOrder(
                WorkOrderNo="4002",
                WOName="Not Actually Packaged",
                Clean=date(2024, 1, 12),
                Treat=date(2024, 1, 13),
                final_location="",  # Empty string
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            db.session.add_all([wo_packaged, wo_not_packaged])
            db.session.commit()

            # Check packaged tab
            response = logged_in_client.get("/in_progress/list_packaged")
            assert response.status_code == 200
            assert b"Actually Packaged" in response.data
            assert b"Not Actually Packaged" not in response.data

            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["4001", "4002"])
            ).delete()
            db.session.query(Customer).filter_by(CustID="C004").delete()
            db.session.commit()

    def test_all_recent_excludes_empty_untouched_orders(self, logged_in_client, app):
        """All Recent should NOT show work orders with empty final_location and no progress (Issue #144)."""
        from models.customer import Customer
        with app.app_context():
            c1 = Customer(CustID="C005", Name="Test Customer 5")
            db.session.add(c1)
            db.session.commit()

            # Create WO like 56390 - has empty final_location but NO progress
            wo_untouched = WorkOrder(
                WorkOrderNo="5001",
                WOName="Untouched Order",
                ProcessingStatus=False,
                Clean=None,
                Treat=None,
                final_location="",  # Empty string (database default)
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            # Create WO that SHOULD appear - has Clean date
            wo_cleaned = WorkOrder(
                WorkOrderNo="5002",
                WOName="Has Progress",
                ProcessingStatus=False,
                Clean=date(2024, 1, 12),
                Treat=None,
                final_location="",
                DateIn=date(2024, 1, 11),
                CustID=c1.CustID,
            )
            db.session.add_all([wo_untouched, wo_cleaned])
            db.session.commit()

            # Check all_recent tab
            response = logged_in_client.get("/in_progress/all_recent")
            assert response.status_code == 200
            # Should NOT show untouched order
            assert b"Untouched Order" not in response.data
            # Should show order with progress
            assert b"Has Progress" in response.data

            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["5001", "5002"])
            ).delete()
            db.session.query(Customer).filter_by(CustID="C005").delete()
            db.session.commit()

    def test_treat_work_order_clears_queue_position(self, logged_in_client, sample_work_orders, app):
        """POST /in_progress/treat_work_order should clear QueuePosition when treating."""
        with app.app_context():
            # Set a queue position on the work order
            work_order = WorkOrder.query.get("1002")
            work_order.QueuePosition = 5
            db.session.commit()

            # Verify queue position is set
            assert work_order.QueuePosition == 5

            # Treat the work order
            response = logged_in_client.post("/in_progress/treat_work_order/1002",
                                           json={"treatDate": "2024-01-15"})
            assert response.status_code == 200
            assert response.get_json()["success"] is True

            # Verify queue position is cleared
            work_order = WorkOrder.query.get("1002")
            assert work_order.Treat == date(2024, 1, 15)
            assert work_order.QueuePosition is None

    def test_package_work_order_clears_queue_position(self, logged_in_client, sample_work_orders, app):
        """POST /in_progress/package_work_order should clear QueuePosition when packaging."""
        with app.app_context():
            # Set a queue position on the work order
            work_order = WorkOrder.query.get("1003")
            work_order.QueuePosition = 3
            db.session.commit()

            # Verify queue position is set
            assert work_order.QueuePosition == 3

            # Package the work order
            response = logged_in_client.post("/in_progress/package_work_order/1003",
                                           json={"finalLocation": "Shelf B"})
            assert response.status_code == 200
            assert response.get_json()["success"] is True

            # Verify queue position is cleared
            work_order = WorkOrder.query.get("1003")
            assert work_order.final_location == "Shelf B"
            assert work_order.QueuePosition is None

    def test_complete_work_order_clears_queue_position(self, logged_in_client, sample_work_orders, app):
        """POST /in_progress/complete_work_order should clear QueuePosition when completing."""
        with app.app_context():
            # Set a queue position on the work order
            work_order = WorkOrder.query.get("1004")
            work_order.QueuePosition = 1
            db.session.commit()

            # Verify queue position is set
            assert work_order.QueuePosition == 1

            # Complete the work order
            response = logged_in_client.post("/in_progress/complete_work_order/1004",
                                           json={"dateCompleted": "2024-01-16"})
            assert response.status_code == 200
            assert response.get_json()["success"] is True

            # Verify queue position is cleared
            work_order = WorkOrder.query.get("1004")
            assert work_order.DateCompleted.date() == date(2024, 1, 16)
            assert work_order.QueuePosition is None


@pytest.fixture
def search_test_data(app):
    """Create sample data for testing search functionality."""
    with app.app_context():
        # Create sources
        source1 = Source(SSource="ABC Sail Loft")
        source2 = Source(SSource="XYZ Marine")
        db.session.add_all([source1, source2])
        db.session.commit()

        # Create customers with sources
        c1 = Customer(CustID="SEARCH001", Name="Customer One", Source="ABC Sail Loft")
        c2 = Customer(CustID="SEARCH002", Name="Customer Two", Source="XYZ Marine")
        c3 = Customer(CustID="SEARCH003", Name="Customer Three", Source="ABC Sail Loft")
        db.session.add_all([c1, c2, c3])
        db.session.commit()

        # Create work orders with different names and source_name (denormalized)
        wo1 = WorkOrder(
            WorkOrderNo="SEARCH1001",
            WOName="Alpha Umbrella Cleaning",
            ProcessingStatus=True,
            DateIn=date(2024, 1, 10),
            CustID="SEARCH001",
            source_name="ABC Sail Loft",
        )
        wo2 = WorkOrder(
            WorkOrderNo="SEARCH1002",
            WOName="Beta Awning Repair",
            Clean=date(2024, 1, 12),
            DateIn=date(2024, 1, 11),
            CustID="SEARCH002",
            source_name="XYZ Marine",
        )
        wo3 = WorkOrder(
            WorkOrderNo="SEARCH1003",
            WOName="Gamma Canvas Treatment",
            Clean=date(2024, 1, 12),
            Treat=date(2024, 1, 13),
            DateIn=date(2024, 1, 12),
            CustID="SEARCH003",
            source_name="ABC Sail Loft",
        )
        wo4 = WorkOrder(
            WorkOrderNo="SEARCH1004",
            WOName="Delta Cushion Storage",
            Clean=date(2024, 1, 12),
            Treat=date(2024, 1, 13),
            final_location="Shelf D",
            DateIn=date(2024, 1, 13),
            CustID="SEARCH001",
            source_name="ABC Sail Loft",
        )

        db.session.add_all([wo1, wo2, wo3, wo4])
        db.session.commit()
        yield
        db.session.query(WorkOrder).filter(
            WorkOrder.WorkOrderNo.like("SEARCH%")
        ).delete(synchronize_session=False)
        db.session.query(Customer).filter(
            Customer.CustID.like("SEARCH%")
        ).delete(synchronize_session=False)
        db.session.query(Source).filter(
            Source.SSource.in_(["ABC Sail Loft", "XYZ Marine"])
        ).delete(synchronize_session=False)
        db.session.commit()


class TestInProgressSearch:
    """Tests for search functionality on In Progress pages (Issue #203)."""

    def test_search_by_name_all_recent(self, logged_in_client, search_test_data):
        """Search by WOName should filter results on all_recent tab."""
        response = logged_in_client.get("/in_progress/all_recent?search=Alpha")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data
        assert b"Beta Awning Repair" not in response.data
        assert b"Gamma Canvas Treatment" not in response.data

    def test_search_by_source_all_recent(self, logged_in_client, search_test_data):
        """Search by source_name should filter results on all_recent tab."""
        response = logged_in_client.get("/in_progress/all_recent?search=XYZ%20Marine")
        assert response.status_code == 200
        assert b"Beta Awning Repair" in response.data
        assert b"Alpha Umbrella Cleaning" not in response.data

    def test_search_case_insensitive(self, logged_in_client, search_test_data):
        """Search should be case-insensitive."""
        response = logged_in_client.get("/in_progress/all_recent?search=alpha")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data

        response = logged_in_client.get("/in_progress/all_recent?search=ALPHA")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data

    def test_search_partial_match(self, logged_in_client, search_test_data):
        """Search should match partial strings."""
        response = logged_in_client.get("/in_progress/all_recent?search=Umbrella")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data

    def test_search_by_source_partial(self, logged_in_client, search_test_data):
        """Search should match partial source names."""
        response = logged_in_client.get("/in_progress/all_recent?search=Sail")
        assert response.status_code == 200
        # Should match multiple work orders from ABC Sail Loft
        assert b"Alpha Umbrella Cleaning" in response.data
        assert b"Gamma Canvas Treatment" in response.data
        assert b"Delta Cushion Storage" in response.data
        # Should NOT match XYZ Marine
        assert b"Beta Awning Repair" not in response.data

    def test_search_empty_returns_all(self, logged_in_client, search_test_data):
        """Empty search should return all results."""
        response = logged_in_client.get("/in_progress/all_recent?search=")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data
        assert b"Beta Awning Repair" in response.data

    def test_search_no_results(self, logged_in_client, search_test_data):
        """Search with no matches should return empty results gracefully."""
        response = logged_in_client.get("/in_progress/all_recent?search=NonExistentOrder12345")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" not in response.data
        assert b"no recent work orders" in response.data.lower() or b"0 items" in response.data.lower()

    def test_search_on_in_progress_tab(self, logged_in_client, search_test_data):
        """Search should work on in_progress tab."""
        response = logged_in_client.get("/in_progress/list_in_progress?search=Alpha")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data

    def test_search_on_cleaned_tab(self, logged_in_client, search_test_data):
        """Search should work on cleaned tab."""
        response = logged_in_client.get("/in_progress/list_cleaned?search=Beta")
        assert response.status_code == 200
        assert b"Beta Awning Repair" in response.data

    def test_search_on_treated_tab(self, logged_in_client, search_test_data):
        """Search should work on treated tab."""
        response = logged_in_client.get("/in_progress/list_treated?search=Gamma")
        assert response.status_code == 200
        assert b"Gamma Canvas Treatment" in response.data

    def test_search_on_packaged_tab(self, logged_in_client, search_test_data):
        """Search should work on packaged tab."""
        response = logged_in_client.get("/in_progress/list_packaged?search=Delta")
        assert response.status_code == 200
        assert b"Delta Cushion Storage" in response.data

    def test_search_preserved_with_sort(self, logged_in_client, search_test_data):
        """Search should be preserved when combined with sort."""
        response = logged_in_client.get("/in_progress/all_recent?search=Sail&sort_by=source")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data
        assert b"Beta Awning Repair" not in response.data

    def test_search_preserved_with_per_page(self, logged_in_client, search_test_data):
        """Search should be preserved when combined with per_page."""
        response = logged_in_client.get("/in_progress/all_recent?search=ABC&per_page=25")
        assert response.status_code == 200
        assert b"Alpha Umbrella Cleaning" in response.data

    def test_search_input_rendered(self, logged_in_client, search_test_data):
        """Search input should be rendered in the template."""
        response = logged_in_client.get("/in_progress/all_recent")
        assert response.status_code == 200
        assert b'name="search"' in response.data
        assert b'placeholder="Search by name or source..."' in response.data

    def test_search_value_preserved_in_input(self, logged_in_client, search_test_data):
        """Search value should be preserved in the input field."""
        response = logged_in_client.get("/in_progress/all_recent?search=TestSearch")
        assert response.status_code == 200
        assert b'value="TestSearch"' in response.data
