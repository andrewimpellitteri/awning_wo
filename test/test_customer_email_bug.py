"""
Test for customer email rendering bug.
This test would have caught the bug where customer.clean_email()
returns None and Jinja renders it as "None" string.
"""

import pytest
from models.customer import Customer
from models.source import Source
from models.user import User
from extensions import db
from werkzeug.security import generate_password_hash


@pytest.fixture
def admin_client_with_sources(client, app):
    """Provide a logged-in admin client with sources."""
    with app.app_context():
        # Create sources first
        sources = [Source(SSource=s) for s in ["SRC1", "SRC2"]]
        db.session.add_all(sources)

        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(admin)
        db.session.commit()

        client.post("/login", data={"username": "admin", "password": "password"})
        yield client
        client.get("/logout")


class TestCustomerEmailRendering:
    """Tests for customer email field rendering in edit form."""

    def test_edit_form_renders_with_null_email(self, admin_client_with_sources):
        """Test that edit form renders correctly when customer has no email."""
        with admin_client_with_sources.application.app_context():
            # Create customer with NO email address
            customer = Customer(
                CustID="999",
                Name="Test Customer",
                Source="SRC1",
                EmailAddress=None  # Explicitly None
            )
            db.session.add(customer)
            db.session.commit()

        # GET the edit form
        response = admin_client_with_sources.get("/customers/edit/999")
        assert response.status_code == 200

        # Check that the email input field doesn't contain the string "None"
        response_html = response.get_data(as_text=True)

        # This would fail with the bug:
        # The bug renders: <input ... value="None" ...>
        # After fix it renders: <input ... value="" ...>
        assert 'value="None"' not in response_html, (
            "Email field should not render 'None' string when EmailAddress is None"
        )

        # Verify the email input exists and is empty or has placeholder
        assert 'id="EmailAddress"' in response_html
        assert 'name="EmailAddress"' in response_html

    def test_edit_form_renders_with_valid_email(self, admin_client_with_sources):
        """Test that edit form renders correctly with a valid email."""
        with admin_client_with_sources.application.app_context():
            customer = Customer(
                CustID="998",
                Name="Customer With Email",
                Source="SRC1",
                EmailAddress="test@example.com"
            )
            db.session.add(customer)
            db.session.commit()

        response = admin_client_with_sources.get("/customers/edit/998")
        assert response.status_code == 200

        response_html = response.get_data(as_text=True)
        assert 'value="test@example.com"' in response_html

    def test_edit_form_renders_with_mailto_email(self, admin_client_with_sources):
        """Test that edit form cleans emails with #mailto: suffix."""
        with admin_client_with_sources.application.app_context():
            # Create customer with legacy email format
            customer = Customer(
                CustID="997",
                Name="Customer With Legacy Email",
                Source="SRC1",
                EmailAddress="test@example.com#mailto:test@example.com#"
            )
            db.session.add(customer)
            db.session.commit()

        response = admin_client_with_sources.get("/customers/edit/997")
        assert response.status_code == 200

        response_html = response.get_data(as_text=True)

        # Should show cleaned email
        assert 'value="test@example.com"' in response_html

        # Should NOT show the raw email with mailto
        assert '#mailto:' not in response_html

    def test_edit_form_renders_with_empty_string_email(self, admin_client_with_sources):
        """Test that edit form renders correctly with empty string email."""
        with admin_client_with_sources.application.app_context():
            customer = Customer(
                CustID="996",
                Name="Customer With Empty Email",
                Source="SRC1",
                EmailAddress=""  # Empty string
            )
            db.session.add(customer)
            db.session.commit()

        response = admin_client_with_sources.get("/customers/edit/996")
        assert response.status_code == 200

        response_html = response.get_data(as_text=True)

        # Should render empty value
        assert 'id="EmailAddress"' in response_html
        # Should not contain "None"
        assert 'value="None"' not in response_html

    def test_update_customer_without_email_succeeds(self, admin_client_with_sources):
        """Test that updating a customer without email works."""
        with admin_client_with_sources.application.app_context():
            customer = Customer(
                CustID="995",
                Name="Customer No Email",
                Source="SRC1",
                EmailAddress=None
            )
            db.session.add(customer)
            db.session.commit()

        # Update customer (without providing email)
        response = admin_client_with_sources.post(
            "/customers/edit/995",
            data={
                "Name": "Updated Name",
                "Source": "SRC1",
                "EmailAddress": ""  # Empty email should be fine
            },
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b"Customer updated successfully" in response.data

        # Verify update worked
        with admin_client_with_sources.application.app_context():
            updated = Customer.query.get("995")
            assert updated.Name == "Updated Name"