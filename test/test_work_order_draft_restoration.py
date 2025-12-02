"""
Tests for work order draft restoration functionality.

Tests the server-side draft restoration when accessing /work_orders/new?draft_id=123
"""

import pytest
from flask import url_for
from models.work_order_draft import WorkOrderDraft
from models.customer import Customer
from models.source import Source
from models.user import User
from extensions import db
from routes.work_orders import _restore_draft_data


@pytest.fixture
def test_user(app_context):
    """Create a test user for draft tests."""
    user = User(
        id=12345,
        username="testuser",
        email="testuser@example.com",
        password_hash="hashed_password_here"  # User model requires password_hash
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_customer(app_context):
    """Create a sample customer."""
    customer = Customer(
        CustID="12345",
        Name="Test Customer",
        Source="TEST_SOURCE",
        HomePhone="555-1234",
        EmailAddress="test@customer.com"
    )
    db.session.add(customer)
    db.session.commit()
    return customer


# Use the sample_source fixture from conftest.py which has the correct fields


class TestRestoreDraftDataHelper:
    """Tests for _restore_draft_data helper function"""

    def test_restore_draft_simple_fields(self, test_user, app_context):
        """Test restoring draft with simple form fields."""
        draft_data = {
            "CustID": "12345",
            "WOName": "Restored Draft",
            "DateIn": "2024-01-15",
            "RackNo": "A-5",
            "SpecialInstructions": "Handle with care",
            "RushOrder": "1",
            "StorageTime": "Seasonal",
            "ReturnTo": "Customer"
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        # Call the helper function
        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert form_data['CustID'] == '12345'
        assert form_data['WOName'] == 'Restored Draft'
        assert form_data['RackNo'] == 'A-5'
        assert form_data['RushOrder'] == '1'
        assert checkin_items == []

    def test_restore_draft_with_new_items_single(self, test_user, app_context):
        """Test restoring draft with single new item (string, not array)."""
        draft_data = {
            "CustID": "12345",
            "new_item_description[]": "Awning 1",
            "new_item_material[]": "Canvas",
            "new_item_color[]": "Blue",
            "new_item_qty[]": "2",
            "new_item_sizewgt[]": "10x12",
            "new_item_price[]": "150.00",
            "new_item_condition[]": "Good"
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert len(checkin_items) == 1
        assert checkin_items[0]['description'] == 'Awning 1'
        assert checkin_items[0]['material'] == 'Canvas'
        assert checkin_items[0]['color'] == 'Blue'
        assert checkin_items[0]['qty'] == '2'
        assert checkin_items[0]['price'] == 150.00

    def test_restore_draft_with_new_items_multiple(self, test_user, app_context):
        """Test restoring draft with multiple new items (arrays)."""
        draft_data = {
            "CustID": "12345",
            "new_item_description[]": ["Awning 1", "Awning 2", "Awning 3"],
            "new_item_material[]": ["Canvas", "Vinyl", "Polyester"],
            "new_item_color[]": ["Blue", "Red", "Green"],
            "new_item_qty[]": ["2", "3", "1"],
            "new_item_sizewgt[]": ["10x12", "8x10", "6x8"],
            "new_item_price[]": ["150.00", "120.00", "90.00"],
            "new_item_condition[]": ["Good", "Excellent", "Fair"]
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert len(checkin_items) == 3

        # Check first item
        assert checkin_items[0]['description'] == 'Awning 1'
        assert checkin_items[0]['material'] == 'Canvas'
        assert checkin_items[0]['qty'] == '2'
        assert checkin_items[0]['price'] == 150.00

        # Check second item
        assert checkin_items[1]['description'] == 'Awning 2'
        assert checkin_items[1]['material'] == 'Vinyl'
        assert checkin_items[1]['color'] == 'Red'

        # Check third item
        assert checkin_items[2]['description'] == 'Awning 3'
        assert checkin_items[2]['price'] == 90.00

    def test_restore_draft_with_selected_inventory_items(self, test_user, app_context):
        """Test restoring draft with selected inventory items."""
        draft_data = {
            "CustID": "12345",
            "selected_items[]": ["INV001", "INV002", "INV003"]
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert "selected_inventory_keys" in form_data
        assert form_data["selected_inventory_keys"] == ["INV001", "INV002", "INV003"]

    def test_restore_draft_with_single_selected_item(self, test_user, app_context):
        """Test restoring draft with single selected inventory item (string)."""
        draft_data = {
            "CustID": "12345",
            "selected_items[]": "INV001"
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert "selected_inventory_keys" in form_data
        assert form_data["selected_inventory_keys"] == ["INV001"]

    def test_restore_draft_not_found(self, test_user, app_context):
        """Test restoring non-existent draft returns empty data."""
        form_data, checkin_items = _restore_draft_data(99999, test_user)

        assert form_data == {}
        assert checkin_items == []

    def test_restore_draft_wrong_user(self, test_user, app_context):
        """Test user can't restore another user's draft."""
        other_user_id = 99999
        draft = WorkOrderDraft(
            user_id=other_user_id,
            form_type='work_order',
            form_data={'CustID': '111'}
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        assert form_data == {}
        assert checkin_items == []

    def test_restore_draft_empty_new_items(self, test_user, app_context):
        """Test restoring draft with empty new item descriptions (should be skipped)."""
        draft_data = {
            "CustID": "12345",
            "new_item_description[]": ["Awning 1", "", "Awning 3"],
            "new_item_material[]": ["Canvas", "Vinyl", "Polyester"],
            "new_item_qty[]": ["2", "3", "1"]
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        # Only 2 items should be restored (empty description skipped)
        assert len(checkin_items) == 2
        assert checkin_items[0]['description'] == 'Awning 1'
        assert checkin_items[1]['description'] == 'Awning 3'

    def test_restore_draft_mixed_form_data(self, test_user, app_context):
        """Test restoring draft with both simple fields and complex items."""
        draft_data = {
            "CustID": "12345",
            "WOName": "Complex Draft",
            "RackNo": "B-3",
            "RushOrder": "1",
            "new_item_description[]": ["Awning 1", "Awning 2"],
            "new_item_material[]": ["Canvas", "Vinyl"],
            "new_item_qty[]": ["2", "3"],
            "new_item_price[]": ["150", "120"],
            "selected_items[]": ["INV001", "INV002"]
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        form_data, checkin_items = _restore_draft_data(draft.id, test_user)

        # Check simple fields
        assert form_data['CustID'] == '12345'
        assert form_data['WOName'] == 'Complex Draft'
        assert form_data['RackNo'] == 'B-3'

        # Check new items
        assert len(checkin_items) == 2

        # Check selected inventory
        assert form_data['selected_inventory_keys'] == ["INV001", "INV002"]


class TestWorkOrderCreateWithDraft:
    """Tests for creating work order with draft_id URL parameter"""

    def test_create_work_order_page_with_draft_id(
        self, client, test_user, sample_customer, sample_source, app_context, mocker
    ):
        """Test accessing /work_orders/new?draft_id=123 pre-fills form."""
        # Mock authentication
        mock_user = type('MockUser', (), {
            'id': test_user.id,
            'is_authenticated': True,
            'is_active': True,
            'is_anonymous': False,
            'get_id': lambda: str(test_user.id)
        })()

        mocker.patch('flask_login.utils._get_user', return_value=mock_user)

        # Create a draft
        draft_data = {
            "CustID": "12345",
            "WOName": "Draft Work Order",
            "RackNo": "A-5",
            "SpecialInstructions": "Test instructions"
        }

        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=draft_data
        )
        db.session.add(draft)
        db.session.commit()

        # Access the create page with draft_id
        with client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(test_user.id)
                sess['_fresh'] = True

            response = client.get(f'/work_orders/new?draft_id={draft.id}')

            assert response.status_code == 200

            # Check that flash message was set
            # Note: Flash messages are stored in session, would need to check session

            # Check that form_data was passed to template
            # This would require checking response.data for the values
            assert b'Draft Work Order' in response.data or b'12345' in response.data

    def test_create_work_order_with_invalid_draft_id(
        self, client, test_user, sample_customer, sample_source, app_context, mocker
    ):
        """Test accessing with invalid draft_id shows warning."""
        mock_user = type('MockUser', (), {
            'id': test_user.id,
            'is_authenticated': True,
            'is_active': True,
            'is_anonymous': False,
            'get_id': lambda: str(test_user.id)
        })()

        mocker.patch('flask_login.utils._get_user', return_value=mock_user)

        with client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(test_user.id)
                sess['_fresh'] = True

            response = client.get('/work_orders/new?draft_id=99999')

            assert response.status_code == 200
            # Should show warning message (would need to check flash messages)


class TestDraftIntegration:
    """Integration tests for full draft workflow"""

    def test_full_draft_workflow(self, client, test_user, sample_customer, app_context, mocker):
        """Test complete workflow: save draft -> list drafts -> restore draft."""
        mock_user = type('MockUser', (), {
            'id': test_user.id,
            'is_authenticated': True,
            'is_active': True,
            'is_anonymous': False,
            'get_id': lambda: str(test_user.id)
        })()

        mocker.patch('flask_login.utils._get_user', return_value=mock_user)

        with client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(test_user.id)
                sess['_fresh'] = True

            # Step 1: Save a draft
            draft_data = {
                "CustID": "12345",
                "WOName": "Integration Test Draft",
                "new_item_description[]": ["Test Item"],
                "new_item_qty[]": ["5"]
            }

            save_response = client.post(
                '/api/drafts/save',
                json={
                    "form_type": "work_order",
                    "form_data": draft_data
                }
            )

            assert save_response.status_code == 200
            draft_id = save_response.get_json()['draft_id']

            # Step 2: List drafts and verify it appears
            list_response = client.get('/api/drafts/list')
            assert list_response.status_code == 200

            drafts = list_response.get_json()['drafts']
            assert len(drafts) >= 1
            assert any(d['id'] == draft_id for d in drafts)

            # Step 3: Get specific draft
            get_response = client.get(f'/api/drafts/{draft_id}')
            assert get_response.status_code == 200

            draft = get_response.get_json()['draft']
            assert draft['form_data']['WOName'] == 'Integration Test Draft'

            # Step 4: Delete draft
            delete_response = client.delete(f'/api/drafts/{draft_id}')
            assert delete_response.status_code == 200

            # Step 5: Verify draft is gone
            verify_response = client.get(f'/api/drafts/{draft_id}')
            assert verify_response.status_code == 404
