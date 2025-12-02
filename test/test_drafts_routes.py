"""
Tests for draft routes (auto-save functionality).

Tests the draft API endpoints for saving, loading, listing, and deleting work order drafts.
"""

import pytest
from flask import url_for
from datetime import datetime
from models.work_order_draft import WorkOrderDraft
from models.user import User
from extensions import db


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
def authenticated_client(client, auth_user):
    """Create an authenticated test client using the auth_user fixture from conftest."""
    # Set the user ID on the mock user
    auth_user.id = 12345
    return client


@pytest.fixture
def sample_draft_data():
    """Sample draft form data."""
    return {
        "CustID": "12345",
        "WOName": "Test Draft Order",
        "DateIn": "2024-01-15",
        "RackNo": "A-5",
        "SpecialInstructions": "Handle with care",
        "RushOrder": "1",
        "new_item_description[]": ["Awning 1", "Awning 2"],
        "new_item_material[]": ["Canvas", "Vinyl"],
        "new_item_color[]": ["Blue", "Red"],
        "new_item_qty[]": ["2", "3"],
        "new_item_sizewgt[]": ["10x12", "8x10"],
        "new_item_price[]": ["150.00", "120.00"],
        "new_item_condition[]": ["Good", "Excellent"],
        "selected_items[]": ["INV001", "INV002"]
    }


class TestDraftSaveEndpoint:
    """Tests for POST /api/drafts/save"""

    def test_save_new_draft(self, authenticated_client, test_user, sample_draft_data, app_context):
        """Test saving a new draft."""
        response = authenticated_client.post(
            '/api/drafts/save',
            json={
                "form_type": "work_order",
                "form_data": sample_draft_data
            }
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert 'draft_id' in data
        assert data['message'] == 'Draft saved successfully'
        assert 'updated_at' in data

        # Verify draft was saved to database
        draft = WorkOrderDraft.query.filter_by(
            id=data['draft_id'],
            user_id=test_user.id
        ).first()

        assert draft is not None
        assert draft.form_type == 'work_order'
        assert draft.form_data['CustID'] == '12345'
        assert draft.form_data['WOName'] == 'Test Draft Order'

    def test_update_existing_draft(self, authenticated_client, test_user, sample_draft_data, app_context):
        """Test updating an existing draft."""
        # Create initial draft
        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data={'CustID': '99999', 'WOName': 'Original'}
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

        # Update the draft
        response = authenticated_client.post(
            '/api/drafts/save',
            json={
                "form_type": "work_order",
                "form_data": sample_draft_data,
                "draft_id": draft_id
            }
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert data['draft_id'] == draft_id

        # Verify draft was updated
        updated_draft = WorkOrderDraft.query.get(draft_id)
        assert updated_draft.form_data['CustID'] == '12345'
        assert updated_draft.form_data['WOName'] == 'Test Draft Order'

    def test_save_draft_missing_form_data(self, authenticated_client, app_context):
        """Test saving draft without form_data returns error."""
        response = authenticated_client.post(
            '/api/drafts/save',
            json={"form_type": "work_order"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert data['error'] == 'Missing form_data'

    def test_save_draft_cleanup_old_drafts(self, authenticated_client, test_user, sample_draft_data, app_context):
        """Test that old drafts are cleaned up (keeps only 5 most recent)."""
        # Create 6 old drafts
        for i in range(6):
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data={'CustID': f'OLD{i}'}
            )
            db.session.add(draft)
        db.session.commit()

        # Save a new draft (should trigger cleanup)
        response = authenticated_client.post(
            '/api/drafts/save',
            json={
                "form_type": "work_order",
                "form_data": sample_draft_data
            }
        )

        assert response.status_code == 200

        # Verify only 5 drafts remain (cleanup happened)
        remaining_drafts = WorkOrderDraft.query.filter_by(user_id=test_user.id).count()
        assert remaining_drafts == 5


class TestDraftListEndpoint:
    """Tests for GET /api/drafts/list"""

    def test_list_drafts_for_user(self, authenticated_client, test_user, app_context):
        """Test listing all drafts for a user."""
        # Create multiple drafts
        drafts_data = [
            {'CustID': '111', 'WOName': 'Draft 1'},
            {'CustID': '222', 'WOName': 'Draft 2'},
            {'CustID': '333', 'WOName': 'Draft 3'},
        ]

        for data in drafts_data:
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data=data
            )
            db.session.add(draft)
        db.session.commit()

        response = authenticated_client.get('/api/drafts/list')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert len(data['drafts']) == 3

    def test_list_drafts_filter_by_form_type(self, authenticated_client, test_user, app_context):
        """Test filtering drafts by form type."""
        # Create drafts with different form types
        draft1 = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data={'CustID': '111'}
        )
        db.session.add(draft1)

        draft2 = WorkOrderDraft(
            user_id=test_user.id,
            form_type='repair_order',
            form_data={'CustID': '222'}
        )
        db.session.add(draft2)

        db.session.commit()

        response = authenticated_client.get('/api/drafts/list?form_type=work_order')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert len(data['drafts']) == 1
        assert data['drafts'][0]['form_type'] == 'work_order'

    def test_list_drafts_limit(self, authenticated_client, test_user, app_context):
        """Test limiting the number of drafts returned."""
        # Create 15 drafts
        for i in range(15):
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data={'CustID': f'{i}'}
            )
            db.session.add(draft)
        db.session.commit()

        response = authenticated_client.get('/api/drafts/list?limit=5')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert len(data['drafts']) == 5

    def test_list_drafts_ordered_by_updated_at(self, authenticated_client, test_user, app_context):
        """Test that drafts are ordered by updated_at descending (most recent first)."""
        # Create drafts with different timestamps
        import time
        from datetime import datetime, timedelta

        # Create first draft with older timestamp
        draft1 = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data={'CustID': '111', 'order': 'first'}
        )
        db.session.add(draft1)
        db.session.flush()  # Flush to get the auto-generated timestamp

        # Manually set an older timestamp to ensure ordering
        draft1.updated_at = datetime.utcnow() - timedelta(seconds=10)
        db.session.commit()

        # Create second draft with newer timestamp
        draft2 = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data={'CustID': '222', 'order': 'second'}
        )
        db.session.add(draft2)
        db.session.commit()

        response = authenticated_client.get('/api/drafts/list')

        assert response.status_code == 200
        data = response.get_json()

        # Most recent draft should be first
        assert len(data['drafts']) >= 2
        assert data['drafts'][0]['form_data']['order'] == 'second'
        assert data['drafts'][1]['form_data']['order'] == 'first'


class TestDraftGetEndpoint:
    """Tests for GET /api/drafts/<draft_id>"""

    def test_get_draft_by_id(self, authenticated_client, test_user, sample_draft_data, app_context):
        """Test retrieving a specific draft by ID."""
        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=sample_draft_data
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

        response = authenticated_client.get(f'/api/drafts/{draft_id}')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert data['draft']['id'] == draft_id
        assert data['draft']['form_data']['CustID'] == '12345'

    def test_get_draft_not_found(self, authenticated_client, app_context):
        """Test retrieving a non-existent draft returns 404."""
        response = authenticated_client.get('/api/drafts/99999')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert data['error'] == 'Draft not found'

    def test_get_draft_wrong_user(self, authenticated_client, app_context):
        """Test that users can't access other users' drafts."""
        # Create a draft for a different user
        other_user_id = 99999
        draft = WorkOrderDraft(
            user_id=other_user_id,
            form_type='work_order',
            form_data={'CustID': '111'}
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

        response = authenticated_client.get(f'/api/drafts/{draft_id}')

        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Draft not found'


class TestDraftDeleteEndpoint:
    """Tests for DELETE /api/drafts/<draft_id>"""

    def test_delete_draft(self, authenticated_client, test_user, app_context):
        """Test deleting a draft."""
        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data={'CustID': '111'}
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

        response = authenticated_client.delete(f'/api/drafts/{draft_id}')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert data['message'] == 'Draft deleted successfully'

        # Verify draft was deleted from database
        deleted_draft = WorkOrderDraft.query.get(draft_id)
        assert deleted_draft is None

    def test_delete_draft_not_found(self, authenticated_client, app_context):
        """Test deleting a non-existent draft returns 404."""
        response = authenticated_client.delete('/api/drafts/99999')

        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Draft not found'

    def test_delete_draft_wrong_user(self, authenticated_client, app_context):
        """Test that users can't delete other users' drafts."""
        other_user_id = 99999
        draft = WorkOrderDraft(
            user_id=other_user_id,
            form_type='work_order',
            form_data={'CustID': '111'}
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

        response = authenticated_client.delete(f'/api/drafts/{draft_id}')

        assert response.status_code == 404

        # Verify draft was NOT deleted
        draft = WorkOrderDraft.query.get(draft_id)
        assert draft is not None


class TestDraftCleanupEndpoint:
    """Tests for POST /api/drafts/cleanup"""

    def test_cleanup_old_drafts(self, authenticated_client, test_user, app_context):
        """Test manual cleanup of old drafts."""
        # Create 10 drafts
        for i in range(10):
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data={'CustID': f'{i}'}
            )
            db.session.add(draft)
        db.session.commit()

        response = authenticated_client.post('/api/drafts/cleanup')

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert data['deleted_count'] == 5  # Should delete 5 oldest (keep 5 most recent)

        # Verify only 5 drafts remain
        remaining = WorkOrderDraft.query.filter_by(user_id=test_user.id).count()
        assert remaining == 5

    def test_cleanup_with_fewer_than_5_drafts(self, authenticated_client, test_user, app_context):
        """Test cleanup when user has fewer than 5 drafts (should delete nothing)."""
        # Create only 3 drafts
        for i in range(3):
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data={'CustID': f'{i}'}
            )
            db.session.add(draft)
        db.session.commit()

        response = authenticated_client.post('/api/drafts/cleanup')

        assert response.status_code == 200
        data = response.get_json()

        assert data['deleted_count'] == 0

        # Verify all 3 drafts still exist
        remaining = WorkOrderDraft.query.filter_by(user_id=test_user.id).count()
        assert remaining == 3


class TestDraftModel:
    """Tests for WorkOrderDraft model methods"""

    def test_to_dict_method(self, test_user, sample_draft_data, app_context):
        """Test the to_dict() method returns correct format."""
        draft = WorkOrderDraft(
            user_id=test_user.id,
            form_type='work_order',
            form_data=sample_draft_data,
            draft_name='My Test Draft'
        )
        db.session.add(draft)
        db.session.commit()

        draft_dict = draft.to_dict()

        assert draft_dict['id'] == draft.id
        assert draft_dict['user_id'] == test_user.id
        assert draft_dict['form_type'] == 'work_order'
        assert draft_dict['draft_name'] == 'My Test Draft'
        assert draft_dict['form_data'] == sample_draft_data
        assert 'created_at' in draft_dict
        assert 'updated_at' in draft_dict

    def test_cleanup_old_drafts_static_method(self, test_user, app_context):
        """Test the static cleanup_old_drafts method."""
        # Create 8 drafts
        for i in range(8):
            draft = WorkOrderDraft(
                user_id=test_user.id,
                form_type='work_order',
                form_data={'CustID': f'{i}'}
            )
            db.session.add(draft)
        db.session.commit()

        # Cleanup, keeping only 3 most recent
        deleted_count = WorkOrderDraft.cleanup_old_drafts(test_user.id, keep_most_recent=3)

        assert deleted_count == 5  # Should delete 5 oldest

        # Verify only 3 remain
        remaining = WorkOrderDraft.query.filter_by(user_id=test_user.id).count()
        assert remaining == 3
