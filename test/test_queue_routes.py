"""
Tests for Queue Management routes.
"""

import pytest
from datetime import date, datetime
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

        # Create sample work orders linked to customers (with Approved quotes)
        wo1 = WorkOrder(
            WorkOrderNo="1001",
            WOName="Regular Order",
            DateIn=date(2024, 1, 10),
            CustID=c1.CustID,
            Quote="Approved",
        )
        wo2 = WorkOrder(
            WorkOrderNo="1002",
            WOName="Rush Order",
            RushOrder=True,
            DateIn=date(2024, 1, 12),
            CustID=c2.CustID,
            Quote="Approved",
        )
        wo3 = WorkOrder(
            WorkOrderNo="1003",
            WOName="Firm Rush Order",
            FirmRush=True,
            DateIn=date(2024, 1, 11),
            CustID=c3.CustID,
            Quote="Approved",
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

    def test_queue_reorder_concurrency_handling(
        self, app, logged_in_client, sample_customers_and_work_orders
    ):
        """Test that concurrent queue reordering is properly handled with SELECT FOR UPDATE."""
        import threading
        from sqlalchemy.exc import OperationalError

        # Track results from concurrent requests
        results = []
        errors = []

        def reorder_queue(order_list, delay=0):
            """Helper to simulate concurrent reorder requests"""
            import time

            if delay:
                time.sleep(delay)

            try:
                response = logged_in_client.post(
                    "/cleaning_queue/api/cleaning-queue/reorder",
                    json={"work_order_ids": order_list, "page": 1, "per_page": 25},
                )
                results.append(
                    {"status": response.status_code, "data": response.get_json()}
                )
            except Exception as e:
                errors.append(str(e))

        # Different reorder sequences
        order1 = ["1001", "1002", "1003"]
        order2 = ["1003", "1002", "1001"]

        # Create threads to simulate concurrent requests
        thread1 = threading.Thread(target=reorder_queue, args=(order1,))
        thread2 = threading.Thread(target=reorder_queue, args=(order2, 0.1))

        # Start both threads
        thread1.start()
        thread2.start()

        # Wait for both to complete
        thread1.join()
        thread2.join()

        # Verify at least one succeeded
        assert len(results) >= 1, "At least one request should complete"

        # Check that we got proper responses
        for result in results:
            assert "status" in result
            assert "data" in result
            # Either success (200) or conflict (409)
            assert result["status"] in [200, 409]

            if result["status"] == 409:
                # Verify proper error response for concurrency
                assert result["data"]["success"] is False
                assert "error_type" in result["data"]
                assert result["data"]["error_type"] == "concurrency"
                assert result["data"]["retry"] is True

        # Verify queue positions are consistent (no duplicates)
        with app.app_context():
            wo1 = WorkOrder.query.get("1001")
            wo2 = WorkOrder.query.get("1002")
            wo3 = WorkOrder.query.get("1003")

            positions = [wo1.QueuePosition, wo2.QueuePosition, wo3.QueuePosition]
            # Check that all positions are unique
            assert len(positions) == len(set(positions)), "Queue positions must be unique"

    def test_queue_reorder_with_missing_work_order(
        self, logged_in_client, sample_customers_and_work_orders
    ):
        """Test that reordering with non-existent work order is handled properly."""
        # Try to reorder with a non-existent work order
        response = logged_in_client.post(
            "/cleaning_queue/api/cleaning-queue/reorder",
            json={
                "work_order_ids": ["1001", "9999", "1003"],
                "page": 1,
                "per_page": 25,
            },
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert "9999" in data["message"]
        assert data["retry"] is False

    # ========== Queue Filter Logic Tests (Bug Fix) ==========

    def test_queue_excludes_cleaned_orders(self, logged_in_client, app):
        """Work orders with Clean date should NOT appear in queue"""
        from models.customer import Customer

        with app.app_context():
            # Create customer
            customer = Customer(CustID="C_CLEAN", Name="Clean Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create work order with Clean date set
            wo_cleaned = WorkOrder(
                WorkOrderNo="WO_CLEANED",
                WOName="Cleaned Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Clean=date(2024, 1, 15),  # Has Clean date
                Quote="Approved",
            )
            db.session.add(wo_cleaned)
            db.session.commit()

        # Check queue page
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Cleaned Order" not in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_CLEANED").delete()
            db.session.query(Customer).filter_by(CustID="C_CLEAN").delete()
            db.session.commit()

    def test_queue_excludes_treated_orders(self, logged_in_client, app):
        """Work orders with Treat date should NOT appear in queue"""
        from models.customer import Customer

        with app.app_context():
            # Create customer
            customer = Customer(CustID="C_TREAT", Name="Treat Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create work order with Treat date set
            wo_treated = WorkOrder(
                WorkOrderNo="WO_TREATED",
                WOName="Treated Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Treat=date(2024, 1, 20),  # Has Treat date
                Quote="Approved",
            )
            db.session.add(wo_treated)
            db.session.commit()

        # Check queue page
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Treated Order" not in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_TREATED").delete()
            db.session.query(Customer).filter_by(CustID="C_TREAT").delete()
            db.session.commit()

    def test_queue_excludes_completed_orders(self, logged_in_client, app):
        """Work orders with DateCompleted should NOT appear in queue"""
        from models.customer import Customer

        with app.app_context():
            # Create customer
            customer = Customer(CustID="C_COMPLETE", Name="Complete Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create completed work order
            wo_completed = WorkOrder(
                WorkOrderNo="WO_COMPLETED",
                WOName="Completed Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                DateCompleted=datetime(2024, 1, 25, 10, 0, 0),  # Has DateCompleted
                Quote="Approved",
            )
            db.session.add(wo_completed)
            db.session.commit()

        # Check queue page
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Completed Order" not in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_COMPLETED").delete()
            db.session.query(Customer).filter_by(CustID="C_COMPLETE").delete()
            db.session.commit()

    def test_queue_excludes_non_approved_quotes(self, logged_in_client, app):
        """Work orders with Quote != 'Approved' should NOT appear in queue"""
        from models.customer import Customer

        with app.app_context():
            # Create customer
            customer = Customer(CustID="C_QUOTE", Name="Quote Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create work orders with different quote values
            wo_done = WorkOrder(
                WorkOrderNo="WO_DONE",
                WOName="Done Quote Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Done",  # Not 'Approved'
            )
            wo_yes = WorkOrder(
                WorkOrderNo="WO_YES",
                WOName="Yes Quote Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 11),
                Quote="Yes",  # Not 'Approved'
            )
            db.session.add_all([wo_done, wo_yes])
            db.session.commit()

        # Check queue page
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Done Quote Order" not in response.data
        assert b"Yes Quote Order" not in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_DONE").delete()
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_YES").delete()
            db.session.query(Customer).filter_by(CustID="C_QUOTE").delete()
            db.session.commit()

    def test_queue_includes_only_approved_incomplete_orders(self, logged_in_client, app):
        """Only orders with Quote='Approved' and no Clean/Treat/DateCompleted should appear"""
        from models.customer import Customer

        with app.app_context():
            # Create customer
            customer = Customer(CustID="C_VALID", Name="Valid Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create a valid work order (should appear in queue)
            wo_valid = WorkOrder(
                WorkOrderNo="WO_VALID",
                WOName="Valid Queue Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                # No Clean, Treat, or DateCompleted
            )
            db.session.add(wo_valid)
            db.session.commit()

        # Check queue page
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Valid Queue Order" in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_VALID").delete()
            db.session.query(Customer).filter_by(CustID="C_VALID").delete()
            db.session.commit()

    # ========== Queue Position Update on Edit Tests (Issue #83) ==========

    def test_edit_work_order_clears_queue_position_when_rush_changes(
        self, logged_in_client, app
    ):
        """Changing RushOrder should clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            # Create customer and work order
            customer = Customer(CustID="90001", Name="Rush Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_RUSH_TEST",
                WOName="Rush Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=5,  # Has a queue position
            )
            db.session.add(wo)
            db.session.commit()

        # Edit work order to change RushOrder
        response = logged_in_client.post(
            "/work_orders/edit/WO_RUSH_TEST",
            data={
                "CustID": "90001",
                "WOName": "Rush Test Order",
                "DateIn": "2024-01-10",
                "Quote": "Approved",
                "RushOrder": "on",  # Change to rush
            },
            follow_redirects=False,
        )

        # Verify QueuePosition was cleared
        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(WorkOrderNo="WO_RUSH_TEST").first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.RushOrder is True

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_RUSH_TEST").delete()
            db.session.query(Customer).filter_by(CustID="90001").delete()
            db.session.commit()

    def test_edit_work_order_clears_queue_position_when_firm_rush_changes(
        self, logged_in_client, app
    ):
        """Changing FirmRush should clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90002", Name="Firm Rush Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_FIRM_TEST",
                WOName="Firm Rush Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=3,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit to add FirmRush
        response = logged_in_client.post(
            "/work_orders/edit/WO_FIRM_TEST",
            data={
                "CustID": "90002",
                "WOName": "Firm Rush Test Order",
                "DateIn": "2024-01-10",
                "Quote": "Approved",
                "FirmRush": "on",
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(WorkOrderNo="WO_FIRM_TEST").first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.FirmRush is True

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_FIRM_TEST").delete()
            db.session.query(Customer).filter_by(CustID="90002").delete()
            db.session.commit()

    def test_edit_work_order_clears_queue_position_when_date_required_changes(
        self, logged_in_client, app
    ):
        """Changing DateRequired should clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90003", Name="DateReq Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_DATEREQ_TEST",
                WOName="DateReq Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                DateRequired=date(2024, 2, 1),
                Quote="Approved",
                QueuePosition=7,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit to change DateRequired
        response = logged_in_client.post(
            "/work_orders/edit/WO_DATEREQ_TEST",
            data={
                "CustID": "90003",
                "WOName": "DateReq Test Order",
                "DateIn": "2024-01-10",
                "DateRequired": "2024-02-15",  # Changed date
                "Quote": "Approved",
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_DATEREQ_TEST"
            ).first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.DateRequired == date(2024, 2, 15)

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(
                WorkOrderNo="WO_DATEREQ_TEST"
            ).delete()
            db.session.query(Customer).filter_by(CustID="90003").delete()
            db.session.commit()

    def test_edit_work_order_clears_queue_position_when_clean_date_set(
        self, logged_in_client, app
    ):
        """Setting Clean date should clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90004", Name="Clean Set Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_CLEANSET_TEST",
                WOName="Clean Set Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=4,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit to set Clean date
        response = logged_in_client.post(
            "/work_orders/edit/WO_CLEANSET_TEST",
            data={
                "CustID": "90004",
                "WOName": "Clean Set Test Order",
                "DateIn": "2024-01-10",
                "Clean": "2024-01-15",  # Set Clean date
                "Quote": "Approved",
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_CLEANSET_TEST"
            ).first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.Clean == date(2024, 1, 15)

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(
                WorkOrderNo="WO_CLEANSET_TEST"
            ).delete()
            db.session.query(Customer).filter_by(CustID="90004").delete()
            db.session.commit()

    def test_edit_work_order_clears_queue_position_when_quote_changes(
        self, logged_in_client, app
    ):
        """Changing Quote should clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90005", Name="Quote Change Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_QUOTECHG_TEST",
                WOName="Quote Change Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=6,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit to change Quote
        response = logged_in_client.post(
            "/work_orders/edit/WO_QUOTECHG_TEST",
            data={
                "CustID": "90005",
                "WOName": "Quote Change Test Order",
                "DateIn": "2024-01-10",
                "Quote": "Done",  # Change from Approved
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_QUOTECHG_TEST"
            ).first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.Quote == "Done"

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(
                WorkOrderNo="WO_QUOTECHG_TEST"
            ).delete()
            db.session.query(Customer).filter_by(CustID="90005").delete()
            db.session.commit()

    def test_edit_work_order_preserves_queue_position_when_unrelated_fields_change(
        self, logged_in_client, app
    ):
        """Changing WOName, SpecialInstructions, etc. should NOT clear QueuePosition"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90006", Name="Preserve Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_PRESERVE_TEST",
                WOName="Original Name",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=8,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit to change only unrelated fields
        response = logged_in_client.post(
            "/work_orders/edit/WO_PRESERVE_TEST",
            data={
                "CustID": "90006",
                "WOName": "Changed Name",  # Change name
                "SpecialInstructions": "New instructions",  # Change instructions
                "DateIn": "2024-01-10",  # Keep same
                "Quote": "Approved",  # Keep same
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_PRESERVE_TEST"
            ).first()
            # Queue position should be preserved
            assert updated_wo.QueuePosition == 8
            assert updated_wo.WOName == "Changed Name"

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(
                WorkOrderNo="WO_PRESERVE_TEST"
            ).delete()
            db.session.query(Customer).filter_by(CustID="90006").delete()
            db.session.commit()

    def test_cleaning_room_edit_clears_queue_position_when_clean_set(
        self, logged_in_client, app
    ):
        """Cleaning room edit setting Clean date should clear QueuePosition"""
        from models.customer import Customer
        from models.user import User
        from werkzeug.security import generate_password_hash

        # Create a user with 'user' role for cleaning room access
        with app.app_context():
            # Create test user with 'user' role
            test_user = User(
                username="cleanroom_user",
                email="cleanroom@example.com",
                role="user",
                password_hash=generate_password_hash("password"),
            )
            db.session.add(test_user)

            customer = Customer(CustID="90007", Name="CR Clean Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_CRCLEAN_TEST",
                WOName="CR Clean Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=9,
            )
            db.session.add(wo)
            db.session.commit()

        # Log in as cleaning room user
        logged_in_client.get("/logout")
        logged_in_client.post(
            "/login", data={"username": "cleanroom_user", "password": "password"}
        )

        # Use cleaning room edit endpoint
        response = logged_in_client.post(
            "/work_orders/cleaning-room/edit/WO_CRCLEAN_TEST",
            data={"Clean": "2024-01-16"},
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_CRCLEAN_TEST"
            ).first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.Clean == date(2024, 1, 16)

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_CRCLEAN_TEST").delete()
            db.session.query(Customer).filter_by(CustID="90007").delete()
            db.session.query(User).filter_by(username="cleanroom_user").delete()
            db.session.commit()

    # ========== Edge Case and Integration Tests ==========

    def test_queue_handles_work_order_with_both_clean_and_treat_dates(
        self, logged_in_client, app
    ):
        """Work order with both Clean AND Treat should be excluded from queue"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90008", Name="Both Dates Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_BOTH_DATES",
                WOName="Both Dates Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Clean=date(2024, 1, 15),
                Treat=date(2024, 1, 20),
                Quote="Approved",
            )
            db.session.add(wo)
            db.session.commit()

        # Check queue page - should NOT appear
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Both Dates Order" not in response.data

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_BOTH_DATES").delete()
            db.session.query(Customer).filter_by(CustID="90008").delete()
            db.session.commit()

    def test_queue_auto_assigns_null_queue_position(self, logged_in_client, app):
        """Work orders with NULL QueuePosition should be auto-assigned"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90009", Name="Auto Assign Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create work order without QueuePosition
            wo = WorkOrder(
                WorkOrderNo="WO_AUTO_ASSIGN",
                WOName="Auto Assign Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                QueuePosition=None,  # Explicitly NULL
            )
            db.session.add(wo)
            db.session.commit()

        # Access queue page - should trigger auto-assignment
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200
        assert b"Auto Assign Order" in response.data

        # Verify QueuePosition was assigned
        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(WorkOrderNo="WO_AUTO_ASSIGN").first()
            assert updated_wo.QueuePosition is not None

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_AUTO_ASSIGN").delete()
            db.session.query(Customer).filter_by(CustID="90009").delete()
            db.session.commit()

    def test_queue_repositions_rush_order_after_edit(self, logged_in_client, app):
        """After edit changes to rush, queue should reposition correctly on next load"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90010", Name="Reposition Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create regular order with queue position
            wo_regular = WorkOrder(
                WorkOrderNo="WO_REPOSITION_TEST",
                WOName="Reposition Test Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                Quote="Approved",
                RushOrder=False,
                QueuePosition=10,
            )
            db.session.add(wo_regular)
            db.session.commit()

        # Edit to make it a rush order
        response = logged_in_client.post(
            "/work_orders/edit/WO_REPOSITION_TEST",
            data={
                "CustID": "90010",
                "WOName": "Reposition Test Order",
                "DateIn": "2024-01-10",
                "Quote": "Approved",
                "RushOrder": "on",  # Make it rush
            },
            follow_redirects=False,
        )

        # Verify QueuePosition was cleared
        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_REPOSITION_TEST"
            ).first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.RushOrder is True

        # Access queue page to trigger auto-repositioning
        response = logged_in_client.get("/cleaning_queue/cleaning-queue")
        assert response.status_code == 200

        # Verify work order was auto-assigned a new position
        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(
                WorkOrderNo="WO_REPOSITION_TEST"
            ).first()
            assert updated_wo.QueuePosition is not None

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(
                WorkOrderNo="WO_REPOSITION_TEST"
            ).delete()
            db.session.query(Customer).filter_by(CustID="90010").delete()
            db.session.commit()

    def test_edit_work_order_multiple_queue_fields_change(
        self, logged_in_client, app
    ):
        """Changing multiple queue-relevant fields at once should clear position"""
        from models.customer import Customer

        with app.app_context():
            customer = Customer(CustID="90011", Name="Multi Change Test Customer")
            db.session.add(customer)
            db.session.commit()

            wo = WorkOrder(
                WorkOrderNo="WO_MULTI_CHANGE",
                WOName="Multi Change Order",
                CustID=customer.CustID,
                DateIn=date(2024, 1, 10),
                DateRequired=date(2024, 2, 1),
                Quote="Approved",
                QueuePosition=12,
            )
            db.session.add(wo)
            db.session.commit()

        # Edit multiple queue-relevant fields at once
        response = logged_in_client.post(
            "/work_orders/edit/WO_MULTI_CHANGE",
            data={
                "CustID": "90011",
                "WOName": "Multi Change Order",
                "DateIn": "2024-01-10",  # Keep same (DateIn is typically not editable)
                "DateRequired": "2024-02-10",  # Changed
                "Quote": "Approved",
                "RushOrder": "on",  # Changed
            },
            follow_redirects=False,
        )

        with app.app_context():
            updated_wo = WorkOrder.query.filter_by(WorkOrderNo="WO_MULTI_CHANGE").first()
            assert updated_wo.QueuePosition is None
            assert updated_wo.RushOrder is True
            assert updated_wo.DateRequired == date(2024, 2, 10)

        # Clean up
        with app.app_context():
            db.session.query(WorkOrder).filter_by(WorkOrderNo="WO_MULTI_CHANGE").delete()
            db.session.query(Customer).filter_by(CustID="90011").delete()
            db.session.commit()


class TestQueueFIFOOrdering:
    """Tests for FIFO ordering within priority tiers.

    These tests verify that when new orders enter the queue, they are sorted
    correctly by DateIn (oldest first) within their priority tier, not just
    appended to the end.
    """

    def test_regular_order_fifo_ordering(self, logged_in_client, app):
        """New regular order with older DateIn should appear BEFORE existing newer orders."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO001", Name="FIFO Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create orders with positions already assigned (simulating existing queue)
            # December order - already in queue
            wo_dec = WorkOrder(
                WorkOrderNo="WO_DEC",
                WOName="December Order",
                CustID=customer.CustID,
                DateIn=date(2024, 12, 15),
                Quote="Approved",
                QueuePosition=1,  # Already has position
            )
            # January order - already in queue
            wo_jan = WorkOrder(
                WorkOrderNo="WO_JAN",
                WOName="January Order",
                CustID=customer.CustID,
                DateIn=date(2025, 1, 10),
                Quote="Approved",
                QueuePosition=2,  # Already has position
            )
            db.session.add_all([wo_dec, wo_jan])
            db.session.commit()

            # Now add a November order WITHOUT a position (simulating late approval)
            wo_nov = WorkOrder(
                WorkOrderNo="WO_NOV",
                WOName="November Order",
                CustID=customer.CustID,
                DateIn=date(2024, 11, 1),  # OLDEST - should be first!
                Quote="Approved",
                QueuePosition=None,  # No position yet
            )
            db.session.add(wo_nov)
            db.session.commit()

            # Run the queue initialization
            initialized = initialize_queue_positions_for_unassigned()
            assert initialized == 1  # Only the November order was unassigned

            # Verify the order: November (oldest) should be FIRST
            wo_nov = WorkOrder.query.get("WO_NOV")
            wo_dec = WorkOrder.query.get("WO_DEC")
            wo_jan = WorkOrder.query.get("WO_JAN")

            assert wo_nov.QueuePosition < wo_dec.QueuePosition, \
                f"November order (pos {wo_nov.QueuePosition}) should be before December (pos {wo_dec.QueuePosition})"
            assert wo_dec.QueuePosition < wo_jan.QueuePosition, \
                f"December order (pos {wo_dec.QueuePosition}) should be before January (pos {wo_jan.QueuePosition})"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_NOV", "WO_DEC", "WO_JAN"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO001").delete()
            db.session.commit()

    def test_rush_order_fifo_ordering(self, logged_in_client, app):
        """New rush order with older DateIn should appear BEFORE existing newer rush orders."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO002", Name="Rush FIFO Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create rush orders with positions already assigned
            wo_jan_rush = WorkOrder(
                WorkOrderNo="WO_JAN_RUSH",
                WOName="January Rush",
                CustID=customer.CustID,
                DateIn=date(2025, 1, 15),
                Quote="Approved",
                RushOrder=True,
                QueuePosition=1,
            )
            wo_feb_rush = WorkOrder(
                WorkOrderNo="WO_FEB_RUSH",
                WOName="February Rush",
                CustID=customer.CustID,
                DateIn=date(2025, 2, 1),
                Quote="Approved",
                RushOrder=True,
                QueuePosition=2,
            )
            db.session.add_all([wo_jan_rush, wo_feb_rush])
            db.session.commit()

            # Add a December rush order WITHOUT a position
            wo_dec_rush = WorkOrder(
                WorkOrderNo="WO_DEC_RUSH",
                WOName="December Rush",
                CustID=customer.CustID,
                DateIn=date(2024, 12, 1),  # OLDEST - should be first among rushes!
                Quote="Approved",
                RushOrder=True,
                QueuePosition=None,
            )
            db.session.add(wo_dec_rush)
            db.session.commit()

            # Run the queue initialization
            initialized = initialize_queue_positions_for_unassigned()
            assert initialized == 1

            # Verify FIFO order within rush tier
            wo_dec = WorkOrder.query.get("WO_DEC_RUSH")
            wo_jan = WorkOrder.query.get("WO_JAN_RUSH")
            wo_feb = WorkOrder.query.get("WO_FEB_RUSH")

            assert wo_dec.QueuePosition < wo_jan.QueuePosition, \
                f"December rush (pos {wo_dec.QueuePosition}) should be before January rush (pos {wo_jan.QueuePosition})"
            assert wo_jan.QueuePosition < wo_feb.QueuePosition, \
                f"January rush (pos {wo_jan.QueuePosition}) should be before February rush (pos {wo_feb.QueuePosition})"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_DEC_RUSH", "WO_JAN_RUSH", "WO_FEB_RUSH"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO002").delete()
            db.session.commit()

    def test_firm_rush_date_required_ordering(self, logged_in_client, app):
        """Firm rush orders should be sorted by DateRequired (closest first), not DateIn."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO003", Name="Firm Rush Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Firm rush with far future DateRequired - already positioned
            wo_far = WorkOrder(
                WorkOrderNo="WO_FR_FAR",
                WOName="Firm Rush Far",
                CustID=customer.CustID,
                DateIn=date(2024, 11, 1),  # Older DateIn
                DateRequired=date(2025, 3, 1),  # Far future
                Quote="Approved",
                FirmRush=True,
                QueuePosition=1,
            )
            db.session.add(wo_far)
            db.session.commit()

            # Firm rush with closer DateRequired - unpositioned
            wo_close = WorkOrder(
                WorkOrderNo="WO_FR_CLOSE",
                WOName="Firm Rush Close",
                CustID=customer.CustID,
                DateIn=date(2025, 1, 15),  # Newer DateIn, but...
                DateRequired=date(2025, 2, 1),  # CLOSER DateRequired - should be first!
                Quote="Approved",
                FirmRush=True,
                QueuePosition=None,
            )
            db.session.add(wo_close)
            db.session.commit()

            # Run the queue initialization
            initialize_queue_positions_for_unassigned()

            # Verify: closer DateRequired should come first
            wo_close = WorkOrder.query.get("WO_FR_CLOSE")
            wo_far = WorkOrder.query.get("WO_FR_FAR")

            assert wo_close.QueuePosition < wo_far.QueuePosition, \
                f"Closer DateRequired (pos {wo_close.QueuePosition}) should be before far DateRequired (pos {wo_far.QueuePosition})"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_FR_CLOSE", "WO_FR_FAR"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO003").delete()
            db.session.commit()

    def test_priority_tiers_maintained(self, logged_in_client, app):
        """All firm rush orders should come before all rush orders, which come before all regular orders."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO004", Name="Priority Tier Test Customer")
            db.session.add(customer)
            db.session.commit()

            # Create mix of orders - some positioned, some not
            wo_regular_old = WorkOrder(
                WorkOrderNo="WO_REG_OLD",
                WOName="Regular Old",
                CustID=customer.CustID,
                DateIn=date(2024, 10, 1),  # Very old
                Quote="Approved",
                QueuePosition=100,  # Has position
            )
            wo_rush_new = WorkOrder(
                WorkOrderNo="WO_RUSH_NEW",
                WOName="Rush New",
                CustID=customer.CustID,
                DateIn=date(2025, 2, 1),  # Newer than regular
                Quote="Approved",
                RushOrder=True,
                QueuePosition=None,  # Unpositioned
            )
            wo_firm_newest = WorkOrder(
                WorkOrderNo="WO_FR_NEWEST",
                WOName="Firm Rush Newest",
                CustID=customer.CustID,
                DateIn=date(2025, 2, 15),  # Newest of all
                DateRequired=date(2025, 3, 1),
                Quote="Approved",
                FirmRush=True,
                QueuePosition=None,  # Unpositioned
            )
            db.session.add_all([wo_regular_old, wo_rush_new, wo_firm_newest])
            db.session.commit()

            # Run the queue initialization
            initialize_queue_positions_for_unassigned()

            # Verify priority order: Firm Rush < Rush < Regular
            wo_fr = WorkOrder.query.get("WO_FR_NEWEST")
            wo_rush = WorkOrder.query.get("WO_RUSH_NEW")
            wo_reg = WorkOrder.query.get("WO_REG_OLD")

            assert wo_fr.QueuePosition < wo_rush.QueuePosition, \
                f"Firm Rush (pos {wo_fr.QueuePosition}) should be before Rush (pos {wo_rush.QueuePosition})"
            assert wo_rush.QueuePosition < wo_reg.QueuePosition, \
                f"Rush (pos {wo_rush.QueuePosition}) should be before Regular (pos {wo_reg.QueuePosition})"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_REG_OLD", "WO_RUSH_NEW", "WO_FR_NEWEST"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO004").delete()
            db.session.commit()

    def test_multiple_new_orders_sorted_correctly(self, logged_in_client, app):
        """Multiple new orders in same tier should be sorted by DateIn relative to each other and existing orders."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO005", Name="Multi New Orders Customer")
            db.session.add(customer)
            db.session.commit()

            # Existing order in queue
            wo_existing = WorkOrder(
                WorkOrderNo="WO_EXISTING",
                WOName="Existing March",
                CustID=customer.CustID,
                DateIn=date(2025, 3, 1),
                Quote="Approved",
                QueuePosition=5,
            )
            db.session.add(wo_existing)
            db.session.commit()

            # Add multiple new orders out of DateIn order
            wo_feb = WorkOrder(
                WorkOrderNo="WO_FEB",
                WOName="February Order",
                CustID=customer.CustID,
                DateIn=date(2025, 2, 1),
                Quote="Approved",
                QueuePosition=None,
            )
            wo_jan = WorkOrder(
                WorkOrderNo="WO_JAN",
                WOName="January Order",
                CustID=customer.CustID,
                DateIn=date(2025, 1, 1),
                Quote="Approved",
                QueuePosition=None,
            )
            wo_apr = WorkOrder(
                WorkOrderNo="WO_APR",
                WOName="April Order",
                CustID=customer.CustID,
                DateIn=date(2025, 4, 1),
                Quote="Approved",
                QueuePosition=None,
            )
            db.session.add_all([wo_feb, wo_jan, wo_apr])
            db.session.commit()

            # Run the queue initialization
            initialized = initialize_queue_positions_for_unassigned()
            assert initialized == 3

            # Verify FIFO order: Jan < Feb < March (existing) < April
            wo_jan = WorkOrder.query.get("WO_JAN")
            wo_feb = WorkOrder.query.get("WO_FEB")
            wo_mar = WorkOrder.query.get("WO_EXISTING")
            wo_apr = WorkOrder.query.get("WO_APR")

            positions = [
                (wo_jan.WOName, wo_jan.QueuePosition),
                (wo_feb.WOName, wo_feb.QueuePosition),
                (wo_mar.WOName, wo_mar.QueuePosition),
                (wo_apr.WOName, wo_apr.QueuePosition),
            ]
            sorted_by_pos = sorted(positions, key=lambda x: x[1])
            expected_order = ["January Order", "February Order", "Existing March", "April Order"]
            actual_order = [name for name, pos in sorted_by_pos]

            assert actual_order == expected_order, \
                f"Expected order {expected_order}, got {actual_order}"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_EXISTING", "WO_FEB", "WO_JAN", "WO_APR"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO005").delete()
            db.session.commit()

    def test_late_approved_order_positioned_correctly(self, logged_in_client, app):
        """An order from November that gets approved late should still be sorted by DateIn."""
        from models.customer import Customer
        from routes.queue import initialize_queue_positions_for_unassigned

        with app.app_context():
            customer = Customer(CustID="FIFO006", Name="Late Approval Customer")
            db.session.add(customer)
            db.session.commit()

            # Simulate existing queue with December and January orders
            wo_dec = WorkOrder(
                WorkOrderNo="WO_DEC_LATE",
                WOName="December Order",
                CustID=customer.CustID,
                DateIn=date(2024, 12, 15),
                Quote="Approved",
                QueuePosition=1,
            )
            wo_jan = WorkOrder(
                WorkOrderNo="WO_JAN_LATE",
                WOName="January Order",
                CustID=customer.CustID,
                DateIn=date(2025, 1, 20),
                Quote="Approved",
                QueuePosition=2,
            )
            wo_feb = WorkOrder(
                WorkOrderNo="WO_FEB_LATE",
                WOName="February Order",
                CustID=customer.CustID,
                DateIn=date(2025, 2, 5),
                Quote="Approved",
                QueuePosition=3,
            )
            db.session.add_all([wo_dec, wo_jan, wo_feb])
            db.session.commit()

            # Now "late approve" a November order (simulates Seafarer Harkness scenario)
            wo_nov = WorkOrder(
                WorkOrderNo="WO_NOV_LATE",
                WOName="November Late Approval",
                CustID=customer.CustID,
                DateIn=date(2024, 11, 10),  # OLDEST - should be FIRST!
                Quote="Approved",
                QueuePosition=None,  # Just got approved, no position yet
            )
            db.session.add(wo_nov)
            db.session.commit()

            # Run the queue initialization
            initialize_queue_positions_for_unassigned()

            # Verify: November should be FIRST, not last
            wo_nov = WorkOrder.query.get("WO_NOV_LATE")
            wo_dec = WorkOrder.query.get("WO_DEC_LATE")
            wo_jan = WorkOrder.query.get("WO_JAN_LATE")
            wo_feb = WorkOrder.query.get("WO_FEB_LATE")

            # Get all positions and sort
            orders = [
                ("November", wo_nov.QueuePosition),
                ("December", wo_dec.QueuePosition),
                ("January", wo_jan.QueuePosition),
                ("February", wo_feb.QueuePosition),
            ]
            sorted_orders = sorted(orders, key=lambda x: x[1])
            actual_order = [name for name, pos in sorted_orders]

            expected_order = ["November", "December", "January", "February"]
            assert actual_order == expected_order, \
                f"Expected order {expected_order}, got {actual_order}. " \
                f"November order (DateIn: Nov 10) should be FIRST, not at the end!"

            # Clean up
            db.session.query(WorkOrder).filter(
                WorkOrder.WorkOrderNo.in_(["WO_NOV_LATE", "WO_DEC_LATE", "WO_JAN_LATE", "WO_FEB_LATE"])
            ).delete(synchronize_session=False)
            db.session.query(Customer).filter_by(CustID="FIFO006").delete()
            db.session.commit()
