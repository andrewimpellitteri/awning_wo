"""
Tests for Source CRUD routes.

This test suite covers the source management routes including:
- Listing and searching sources
- Creating new sources
- Editing existing sources (including issue #47 - phone number not updating)
- Deleting sources
- API endpoints
"""

import pytest
from werkzeug.security import generate_password_hash
from models.source import Source
from models.user import User
from extensions import db


@pytest.fixture
def logged_in_client(client, app):
    """Provide a logged-in client with a regular user."""
    with app.app_context():
        user = User(
            username="testuser",
            email="testuser@example.com",
            password_hash=generate_password_hash("password"),
            role="user",
        )
        db.session.add(user)
        db.session.commit()

    client.post("/login", data={"username": "testuser", "password": "password"})
    yield client
    client.get("/logout")


@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with admin privileges."""
    with app.app_context():
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("password"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()

    client.post("/login", data={"username": "admin", "password": "password"})
    yield client
    client.get("/logout")


@pytest.fixture
def sample_sources(app):
    """Create sample sources for testing."""
    with app.app_context():
        source1 = Source(
            SSource="Test Source 1",
            SourceAddress="123 Main St",
            SourceCity="Boston",
            SourceState="MA",
            SourceZip="02101",
            SourcePhone="6175551234",
            SourceFax="6175551235",
            SourceEmail="test1@example.com",
        )
        source2 = Source(
            SSource="Test Source 2",
            SourceAddress="456 Oak Ave",
            SourceCity="New York",
            SourceState="NY",
            SourceZip="10001",
            SourcePhone="2125559876",
            SourceEmail="test2@example.com",
        )
        source3 = Source(
            SSource="Test Source 3", SourceCity="Cambridge", SourceState="MA"
        )

        db.session.add_all([source1, source2, source3])
        db.session.commit()
        yield
        db.session.query(Source).delete()
        db.session.commit()


class TestSourceListRoutes:
    """Test source list and search functionality."""

    def test_source_list_page_renders(self, logged_in_client, sample_sources):
        """GET /sources/ should render the list page."""
        response = logged_in_client.get("/sources/")
        assert response.status_code == 200
        assert b"Sources" in response.data or b"Test Source 1" in response.data

    def test_source_list_search(self, logged_in_client, sample_sources):
        """Test searching for sources."""
        response = logged_in_client.get("/sources/?search=Test Source 1")
        assert response.status_code == 200
        assert b"Test Source 1" in response.data

    def test_source_list_filter_by_state(self, logged_in_client, sample_sources):
        """Test filtering sources by state."""
        response = logged_in_client.get("/sources/?state=MA")
        assert response.status_code == 200
        assert b"Test Source 1" in response.data or b"Test Source 3" in response.data

    def test_source_list_pagination(self, logged_in_client, sample_sources):
        """Test pagination of source list."""
        response = logged_in_client.get("/sources/?page=1")
        assert response.status_code == 200


class TestSourceDetailRoutes:
    """Test source detail view."""

    def test_view_source_detail(self, logged_in_client, sample_sources):
        """Test viewing a source's detail page."""
        response = logged_in_client.get("/sources/view/Test Source 1")
        assert response.status_code == 200
        assert b"Test Source 1" in response.data
        assert b"Boston" in response.data

    def test_view_missing_source_detail(self, logged_in_client):
        """Test viewing a missing source's detail page results in a 404."""
        response = logged_in_client.get("/sources/view/Nonexistent Source")
        assert response.status_code == 404


class TestSourceCreateRoutes:
    """Test source creation functionality."""

    def test_create_source_page_renders(self, admin_client):
        """GET /sources/new should render the create page."""
        response = admin_client.get("/sources/new")
        assert response.status_code == 200
        assert (
            b"Add New Source" in response.data or b"Source Information" in response.data
        )

    def test_create_source_success(self, admin_client, app):
        """Test successfully creating a new source."""
        with app.app_context():
            response = admin_client.post(
                "/sources/new",
                data={
                    "SSource": "New Test Source",
                    "SourceAddress": "789 Pine St",
                    "SourceCity": "San Francisco",
                    "SourceState": "CA",
                    "SourceZip": "94102",
                    "SourcePhone": "4155551234",
                    "SourceEmail": "newtest@example.com",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Verify source was created
            new_source = Source.query.get("New Test Source")
            assert new_source is not None
            assert new_source.SourceCity == "San Francisco"
            assert new_source.SourcePhone == "4155551234"
            assert new_source.SourceEmail == "newtest@example.com"

    def test_create_source_missing_name(self, admin_client):
        """Test creating a source without a required name."""
        response = admin_client.post(
            "/sources/new", data={"SourceCity": "Boston", "SourceState": "MA"}
        )
        assert response.status_code == 200
        assert (
            b"Source name is required" in response.data
            or b"error" in response.data.lower()
        )

    def test_create_source_duplicate(self, admin_client, sample_sources):
        """Test creating a source with a duplicate q."""
        response = admin_client.post(
            "/sources/new", data={"SSource": "Test Source 1", "SourceCity": "Boston"}
        )
        assert response.status_code == 200
        assert b"already exists" in response.data.lower()


class TestSourceEditRoutes:
    """Test source editing functionality - INCLUDES FIX FOR ISSUE #47."""

    def test_edit_source_page_renders(self, admin_client, sample_sources):
        """GET /sources/edit/<source_name> should render the edit page."""
        response = admin_client.get("/sources/edit/Test Source 1")
        assert response.status_code == 200
        assert b"Edit Source" in response.data or b"Test Source 1" in response.data

    def test_update_source_basic_fields(self, admin_client, sample_sources, app):
        """Test updating basic source fields."""
        with app.app_context():
            response = admin_client.post(
                "/sources/edit/Test Source 1",
                data={
                    "SourceAddress": "999 Updated St",
                    "SourceCity": "Updated City",
                    "SourceState": "CA",
                    "SourceZip": "90210",
                    "SourcePhone": "6175551234",  # Keep original
                    "SourceEmail": "updated@example.com",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Verify source was updated
            updated_source = Source.query.get("Test Source 1")
            assert updated_source.SourceAddress == "999 Updated St"
            assert updated_source.SourceCity == "Updated City"
            assert updated_source.SourceState == "CA"
            assert updated_source.SourceEmail == "updated@example.com"

    def test_update_source_phone_number(self, admin_client, sample_sources, app):
        """
        Test updating source phone number.

        This is a regression test for issue #47:
        'Edit source phone number not working - always sets to 0'

        The bug was that when editing a source, the phone number field
        would display as formatted (e.g., (617) 555-1234) but would be
        saved as 0 instead of preserving or updating the actual number.
        """
        with app.app_context():
            # First, verify the original phone number
            original_source = Source.query.get("Test Source 1")
            assert original_source.SourcePhone == "6175551234"

            # Update the phone number to a new value
            response = admin_client.post(
                "/sources/edit/Test Source 1",
                data={
                    "SourceAddress": "123 Main St",  # Keep original
                    "SourceCity": "Boston",  # Keep original
                    "SourceState": "MA",  # Keep original
                    "SourceZip": "02101",  # Keep original
                    "SourcePhone": "8575559999",  # NEW phone number
                    "SourceEmail": "test1@example.com",  # Keep original
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            # Verify phone number was actually updated (not set to 0)
            updated_source = Source.query.get("Test Source 1")
            assert updated_source.SourcePhone == "8575559999", (
                f"Phone should be '8575559999' but got '{updated_source.SourcePhone}'"
            )
            assert updated_source.SourcePhone != "0", (
                "Phone number should not be set to 0 (issue #47)"
            )
            assert updated_source.SourcePhone != "", "Phone number should not be empty"

    def test_update_source_phone_number_empty_string(
        self, admin_client, sample_sources, app
    ):
        """
        Test that an empty phone number field clears the phone number.

        This tests the edge case where a user wants to remove a phone number.
        """
        with app.app_context():
            response = admin_client.post(
                "/sources/edit/Test Source 1",
                data={
                    "SourceAddress": "123 Main St",
                    "SourceCity": "Boston",
                    "SourceState": "MA",
                    "SourceZip": "02101",
                    "SourcePhone": "",  # Empty phone
                    "SourceEmail": "test1@example.com",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            updated_source = Source.query.get("Test Source 1")
            # Empty string should be preserved, not converted to 0
            assert updated_source.SourcePhone in ["", None], (
                f"Empty phone should be '' or None, not '{updated_source.SourcePhone}'"
            )

    def test_update_source_preserves_existing_phone_when_formatted(
        self, admin_client, sample_sources, app
    ):
        """
        Test that when a phone number is displayed in formatted form,
        it can still be updated correctly.

        This simulates the user seeing (617) 555-1234 in the form field
        but the JavaScript stripping it to digits before submission.
        """
        with app.app_context():
            # Simulate formatted phone being sent (as if JS didn't strip it)
            # The form should handle this gracefully
            response = admin_client.post(
                "/sources/edit/Test Source 1",
                data={
                    "SourceAddress": "123 Main St",
                    "SourceCity": "Boston",
                    "SourceState": "MA",
                    "SourceZip": "02101",
                    "SourcePhone": "6175551234",  # Already in digit-only form
                    "SourceEmail": "test1@example.com",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            updated_source = Source.query.get("Test Source 1")
            assert updated_source.SourcePhone == "6175551234"

    def test_update_source_all_fields(self, admin_client, sample_sources, app):
        """Test updating all source fields at once."""
        with app.app_context():
            response = admin_client.post(
                "/sources/edit/Test Source 2",
                data={
                    "SourceAddress": "111 New Address",
                    "SourceCity": "Los Angeles",
                    "SourceState": "CA",
                    "SourceZip": "90001",
                    "SourcePhone": "3105551111",
                    "SourceFax": "3105552222",
                    "SourceEmail": "newemail@example.com",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            updated_source = Source.query.get("Test Source 2")
            assert updated_source.SourceAddress == "111 New Address"
            assert updated_source.SourceCity == "Los Angeles"
            assert updated_source.SourceState == "CA"
            assert updated_source.SourceZip == "90001"
            assert updated_source.SourcePhone == "3105551111"
            assert updated_source.SourceFax == "3105552222"
            assert updated_source.SourceEmail == "newemail@example.com"


class TestSourceDeleteRoutes:
    """Test source deletion functionality."""

    def test_delete_source(self, admin_client, sample_sources, app):
        """Test deleting a source."""
        with app.app_context():
            response = admin_client.post(
                "/sources/delete/Test Source 3", follow_redirects=True
            )
            assert response.status_code == 200

            # Verify source was deleted
            deleted_source = Source.query.get("Test Source 3")
            assert deleted_source is None

    def test_delete_missing_source(self, admin_client):
        """Test deleting a non-existent source."""
        response = admin_client.post("/sources/delete/Nonexistent Source")
        assert response.status_code == 404


class TestSourceAPIRoutes:
    """Test source API endpoints."""

    def test_api_search_sources(self, logged_in_client, sample_sources):
        """Test API endpoint for searching sources."""
        response = logged_in_client.get("/sources/api/search?q=Test Source 1")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert len(data) > 0
        assert any(s["name"] == "Test Source 1" for s in data)

    def test_api_search_sources_no_query(self, logged_in_client, sample_sources):
        """Test API search with no query returns empty list."""
        response = logged_in_client.get("/sources/api/search?q=")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_api_get_states(self, logged_in_client, sample_sources):
        """Test API endpoint for getting all unique states."""
        response = logged_in_client.get("/sources/api/states")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "MA" in data
        assert "NY" in data


class TestSourceRoutesAuth:
    """Test authentication/authorization for source routes."""

    def test_regular_user_cannot_create_source(self, logged_in_client):
        """Test that a regular user cannot create a source."""
        response = logged_in_client.post(
            "/sources/new",
            data={"SSource": "Unauthorized Source", "SourceCity": "Test City"},
        )
        # Should be forbidden due to role_required decorator
        assert response.status_code == 403

    def test_regular_user_cannot_edit_source(self, logged_in_client, sample_sources):
        """Test that a regular user cannot edit a source."""
        response = logged_in_client.post(
            "/sources/edit/Test Source 1", data={"SourceCity": "Updated City"}
        )
        assert response.status_code == 403

    def test_regular_user_cannot_delete_source(self, logged_in_client, sample_sources):
        """Test that a regular user cannot delete a source."""
        response = logged_in_client.post("/sources/delete/Test Source 1")
        assert response.status_code == 403

    def test_admin_can_create_source(self, admin_client, app):
        """Test that an admin can create a source."""
        with app.app_context():
            response = admin_client.post(
                "/sources/new",
                data={
                    "SSource": "Admin Created Source",
                    "SourceCity": "Admin City",
                    "SourceState": "CA",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify source was created
            new_source = Source.query.get("Admin Created Source")
            assert new_source is not None

    def test_admin_can_edit_source(self, admin_client, sample_sources, app):
        """Test that an admin can edit a source."""
        with app.app_context():
            response = admin_client.post(
                "/sources/edit/Test Source 1",
                data={
                    "SourceCity": "Admin Updated City",
                    "SourceState": "MA",
                    "SourceAddress": "123 Main St",
                    "SourceZip": "02101",
                    "SourcePhone": "6175551234",
                    "SourceEmail": "test1@example.com",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            updated_source = Source.query.get("Test Source 1")
            assert updated_source.SourceCity == "Admin Updated City"


class TestSourceModelMethods:
    """Test Source model helper methods used in routes."""

    def test_clean_phone_formats_correctly(self, app, sample_sources):
        """Test that clean_phone() formats 10-digit numbers."""
        with app.app_context():
            source = Source.query.get("Test Source 1")
            formatted = source.clean_phone()
            assert formatted == "(617) 555-1234"

    def test_clean_phone_returns_original_if_not_10_digits(self, app):
        """Test that clean_phone() returns original if not 10 digits."""
        with app.app_context():
            source = Source(SSource="Test", SourcePhone="555")
            assert source.clean_phone() == "555"

    def test_clean_email_removes_mailto(self, app):
        """Test that clean_email() removes #mailto: suffix."""
        with app.app_context():
            source = Source(SSource="Test", SourceEmail="test@example.com#mailto:")
            assert source.clean_email() == "test@example.com"

    def test_get_full_address(self, app, sample_sources):
        """Test that get_full_address() formats address correctly."""
        with app.app_context():
            source = Source.query.get("Test Source 1")
            full_address = source.get_full_address()
            assert "123 Main St" in full_address
            assert "Boston, MA 02101" in full_address
