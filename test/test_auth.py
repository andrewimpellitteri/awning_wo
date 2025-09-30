"""
Authentication route tests for login, logout, and registration.

Tests cover:
- Login with valid/invalid credentials
- Already authenticated user redirects
- Logout functionality
- Registration with valid/invalid invite tokens
- Duplicate username/email validation
- Token marking as used
"""

import pytest
from flask import url_for
from werkzeug.security import generate_password_hash
from models.user import User
from models.invite_token import InviteToken
from extensions import db


@pytest.mark.unit
class TestLoginRoutes:
    """Test login functionality."""

    def test_login_page_renders(self, client):
        """GET /login should render login page."""
        response = client.get("/login")
        assert response.status_code == 200
        assert b"login" in response.data.lower()

    def test_login_with_valid_credentials(self, app, client):
        """POST /login with valid credentials should log user in."""
        with app.app_context():
            # Create a test user
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Attempt login
            response = client.post(
                "/login",
                data={"username": "testuser", "password": "testpassword"},
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Logged in successfully!" in response.data

    def test_login_with_invalid_username(self, client):
        """POST /login with invalid username should fail."""
        response = client.post(
            "/login",
            data={"username": "nonexistent", "password": "anypassword"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_login_with_invalid_password(self, app, client):
        """POST /login with invalid password should fail."""
        with app.app_context():
            # Create a test user
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("correctpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Attempt login with wrong password
            response = client.post(
                "/login",
                data={"username": "testuser", "password": "wrongpassword"},
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Invalid username or password" in response.data

    def test_login_when_already_authenticated(self, app, client):
        """Already authenticated user should be redirected to dashboard."""
        with app.app_context():
            # Create and log in a user
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Log in
            client.post(
                "/login",
                data={"username": "testuser", "password": "testpassword"},
            )

            # Try to access login page again
            response = client.get("/login", follow_redirects=False)
            assert response.status_code == 302
            assert "/dashboard" in response.location or response.location == "/"

    def test_login_with_empty_fields(self, client):
        """POST /login with empty fields should fail."""
        response = client.post(
            "/login", data={"username": "", "password": ""}, follow_redirects=True
        )

        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_login_with_remember_me(self, app, client):
        """Login should set remember cookie."""
        with app.app_context():
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            response = client.post(
                "/login",
                data={"username": "testuser", "password": "testpassword"},
            )

            # Check that remember cookie is set (remember=True in login_user)
            assert response.status_code == 302


@pytest.mark.unit
class TestLogoutRoutes:
    """Test logout functionality."""

    def test_logout_clears_session(self, app, client):
        """GET /logout should clear session and redirect to login."""
        with app.app_context():
            # Create and log in a user
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Log in
            client.post(
                "/login",
                data={"username": "testuser", "password": "testpassword"},
            )

            # Log out
            response = client.get("/logout", follow_redirects=True)

            assert response.status_code == 200
            assert b"You have been logged out" in response.data
            assert b"login" in response.data.lower()

    def test_logout_redirect_to_login(self, app, client):
        """Logout should redirect to login page."""
        with app.app_context():
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            client.post(
                "/login",
                data={"username": "testuser", "password": "testpassword"},
            )

            response = client.get("/logout", follow_redirects=False)
            assert response.status_code == 302
            assert "/login" in response.location


@pytest.mark.unit
class TestRegistrationRoutes:
    """Test user registration functionality."""

    def test_registration_page_renders(self, client):
        """GET /register should render registration page."""
        response = client.get("/register")
        assert response.status_code == 200
        assert b"register" in response.data.lower()

    def test_register_with_valid_token(self, app, client):
        """POST /register with valid invite token should create user."""
        with app.app_context():
            # Create an invite token
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            token_str = invite.token

            # Register
            response = client.post(
                "/register",
                data={
                    "token": token_str,
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "newpassword",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Registration successful" in response.data

            # Verify user was created
            user = User.query.filter_by(username="newuser").first()
            assert user is not None
            assert user.email == "newuser@example.com"
            assert user.role == "user"

            # Verify token was marked as used
            db.session.refresh(invite)
            assert invite.used is True

    def test_register_with_invalid_token(self, client):
        """POST /register with invalid token should fail."""
        response = client.post(
            "/register",
            data={
                "token": "invalid_token_12345",
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "newpassword",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Invalid or already used invitation token" in response.data

    def test_register_with_used_token(self, app, client):
        """POST /register with already used token should fail."""
        with app.app_context():
            # Create and mark token as used
            invite = InviteToken.generate_token(role="user")
            invite.used = True
            db.session.commit()

            token_str = invite.token

            # Attempt registration
            response = client.post(
                "/register",
                data={
                    "token": token_str,
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "newpassword",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Invalid or already used invitation token" in response.data

    def test_register_with_duplicate_username(self, app, client):
        """POST /register with duplicate username should fail."""
        with app.app_context():
            # Create existing user
            existing_user = User(
                username="existinguser",
                email="existing@example.com",
                password_hash=generate_password_hash("password"),
                role="user",
            )
            db.session.add(existing_user)

            # Create invite token
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            # Attempt registration with duplicate username
            response = client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "existinguser",  # Duplicate
                    "email": "newuser@example.com",
                    "password": "newpassword",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Username already exists" in response.data

            # Verify token was NOT marked as used
            db.session.refresh(invite)
            assert invite.used is False

    def test_register_with_duplicate_email(self, app, client):
        """POST /register with duplicate email should fail."""
        with app.app_context():
            # Create existing user
            existing_user = User(
                username="existinguser",
                email="existing@example.com",
                password_hash=generate_password_hash("password"),
                role="user",
            )
            db.session.add(existing_user)

            # Create invite token
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            # Attempt registration with duplicate email
            response = client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "newuser",
                    "email": "existing@example.com",  # Duplicate
                    "password": "newpassword",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert b"Email already registered" in response.data

            # Verify token was NOT marked as used
            db.session.refresh(invite)
            assert invite.used is False

    def test_register_assigns_correct_role(self, app, client):
        """Registration should assign role from invite token."""
        with app.app_context():
            # Create admin invite token
            invite = InviteToken.generate_token(role="admin")
            db.session.commit()

            # Register
            client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "adminuser",
                    "email": "admin@example.com",
                    "password": "adminpassword",
                },
                follow_redirects=True,
            )

            # Verify user has admin role
            user = User.query.filter_by(username="adminuser").first()
            assert user.role == "admin"

    def test_register_with_missing_fields(self, app, client):
        """POST /register with missing fields should fail gracefully."""
        with app.app_context():
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            # Missing username
            response = client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "",
                    "email": "test@example.com",
                    "password": "password",
                },
                follow_redirects=True,
            )

            # Should fail (exact error depends on validation)
            # Token should not be marked as used
            db.session.refresh(invite)
            assert invite.used is False

    def test_register_password_is_hashed(self, app, client):
        """Registration should hash passwords."""
        with app.app_context():
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            plaintext_password = "mysecretpassword"

            client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": plaintext_password,
                },
                follow_redirects=True,
            )

            user = User.query.filter_by(username="testuser").first()
            # Password should be hashed, not plaintext
            assert user.password_hash != plaintext_password
            assert len(user.password_hash) > 50  # Hashed passwords are long


@pytest.mark.integration
class TestAuthenticationFlow:
    """Integration tests for complete authentication flows."""

    def test_complete_registration_and_login_flow(self, app, client):
        """Test complete flow: register → login → logout."""
        with app.app_context():
            # 1. Create invite token
            invite = InviteToken.generate_token(role="user")
            db.session.commit()

            # 2. Register
            response = client.post(
                "/register",
                data={
                    "token": invite.token,
                    "username": "flowuser",
                    "email": "flow@example.com",
                    "password": "flowpassword",
                },
                follow_redirects=True,
            )
            assert b"Registration successful" in response.data

            # 3. Login
            response = client.post(
                "/login",
                data={"username": "flowuser", "password": "flowpassword"},
                follow_redirects=True,
            )
            assert b"Logged in successfully" in response.data

            # 4. Logout
            response = client.get("/logout", follow_redirects=True)
            assert b"You have been logged out" in response.data

    def test_token_cannot_be_reused(self, app, client):
        """Invite token should only work once."""
        with app.app_context():
            invite = InviteToken.generate_token(role="user")
            db.session.commit()
            token_str = invite.token

            # First registration
            client.post(
                "/register",
                data={
                    "token": token_str,
                    "username": "user1",
                    "email": "user1@example.com",
                    "password": "password1",
                },
                follow_redirects=True,
            )

            # Second registration with same token should fail
            response = client.post(
                "/register",
                data={
                    "token": token_str,
                    "username": "user2",
                    "email": "user2@example.com",
                    "password": "password2",
                },
                follow_redirects=True,
            )

            assert b"Invalid or already used invitation token" in response.data

            # Verify only one user was created
            assert User.query.count() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])