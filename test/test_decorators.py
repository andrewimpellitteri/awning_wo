"""
Authorization decorator tests for role-based access control.

Tests cover:
- @role_required decorator with various roles
- Unauthenticated user redirects
- Unauthorized user gets 403
- Multiple role permissions
"""

import pytest
from flask import Blueprint
from werkzeug.security import generate_password_hash
from models.user import User
from decorators import role_required
from extensions import db


# Create a test blueprint with protected routes
test_bp = Blueprint("test_protected", __name__)


@test_bp.route("/admin-only")
@role_required("admin")
def admin_only_route():
    return "Admin access granted"


@test_bp.route("/manager-only")
@role_required("manager")
def manager_only_route():
    return "Manager access granted"


@test_bp.route("/admin-or-manager")
@role_required("admin", "manager")
def admin_or_manager_route():
    return "Admin or Manager access granted"


@test_bp.route("/user-route")
@role_required("user", "manager", "admin")
def user_route():
    return "User access granted"


@pytest.fixture(autouse=True)
def register_test_blueprint(app):
    """Auto-register the test blueprint for all tests in this module."""
    app.register_blueprint(test_bp)


@pytest.mark.unit
class TestRoleRequiredDecorator:
    """Test @role_required decorator functionality."""

    def test_unauthenticated_user_redirected_to_login(
        self, app, client
    ):
        """Unauthenticated users should be redirected to login."""
        response = client.get("/admin-only", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_admin_can_access_admin_route(self, app, client):
        """Admin users should access admin-only routes."""
        with app.app_context():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

            # Login as admin
            client.post(
                "/login", data={"username": "admin", "password": "adminpass"}
            )

            # Access admin route
            response = client.get("/admin-only")
            assert response.status_code == 200
            assert b"Admin access granted" in response.data

    def test_regular_user_blocked_from_admin_route(
        self, app, client
    ):
        """Regular users should get 403 on admin-only routes."""
        with app.app_context():
            # Create regular user
            user = User(
                username="user",
                email="user@example.com",
                password_hash=generate_password_hash("userpass"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Login as user
            client.post("/login", data={"username": "user", "password": "userpass"})

            # Try to access admin route
            response = client.get("/admin-only")
            assert response.status_code == 403

    def test_manager_can_access_manager_route(self, app, client):
        """Manager users should access manager-only routes."""
        with app.app_context():
            # Create manager user
            manager = User(
                username="manager",
                email="manager@example.com",
                password_hash=generate_password_hash("managerpass"),
                role="manager",
            )
            db.session.add(manager)
            db.session.commit()

            # Login as manager
            client.post(
                "/login", data={"username": "manager", "password": "managerpass"}
            )

            # Access manager route
            response = client.get("/manager-only")
            assert response.status_code == 200
            assert b"Manager access granted" in response.data

    def test_manager_blocked_from_admin_route(self, app, client):
        """Manager users should be blocked from admin-only routes."""
        with app.app_context():
            # Create manager user
            manager = User(
                username="manager",
                email="manager@example.com",
                password_hash=generate_password_hash("managerpass"),
                role="manager",
            )
            db.session.add(manager)
            db.session.commit()

            # Login as manager
            client.post(
                "/login", data={"username": "manager", "password": "managerpass"}
            )

            # Try to access admin route
            response = client.get("/admin-only")
            assert response.status_code == 403

    def test_admin_can_access_manager_route(self, app, client):
        """Admin users should NOT access manager-only routes (unless explicitly allowed)."""
        with app.app_context():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

            # Login as admin
            client.post(
                "/login", data={"username": "admin", "password": "adminpass"}
            )

            # Try to access manager-only route
            response = client.get("/manager-only")
            # Admin should get 403 because decorator is @role_required("manager")
            assert response.status_code == 403

    def test_multiple_roles_admin_access(self, app, client):
        """Admin should access routes requiring admin OR manager."""
        with app.app_context():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

            # Login as admin
            client.post(
                "/login", data={"username": "admin", "password": "adminpass"}
            )

            # Access route requiring admin OR manager
            response = client.get("/admin-or-manager")
            assert response.status_code == 200
            assert b"Admin or Manager access granted" in response.data

    def test_multiple_roles_manager_access(self, app, client):
        """Manager should access routes requiring admin OR manager."""
        with app.app_context():
            # Create manager user
            manager = User(
                username="manager",
                email="manager@example.com",
                password_hash=generate_password_hash("managerpass"),
                role="manager",
            )
            db.session.add(manager)
            db.session.commit()

            # Login as manager
            client.post(
                "/login", data={"username": "manager", "password": "managerpass"}
            )

            # Access route requiring admin OR manager
            response = client.get("/admin-or-manager")
            assert response.status_code == 200
            assert b"Admin or Manager access granted" in response.data

    def test_multiple_roles_user_blocked(self, app, client):
        """Regular user should be blocked from admin OR manager routes."""
        with app.app_context():
            # Create regular user
            user = User(
                username="user",
                email="user@example.com",
                password_hash=generate_password_hash("userpass"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Login as user
            client.post("/login", data={"username": "user", "password": "userpass"})

            # Try to access admin OR manager route
            response = client.get("/admin-or-manager")
            assert response.status_code == 403

    def test_any_authenticated_user_with_all_roles(
        self, app, client
    ):
        """Routes allowing all roles should allow any authenticated user."""
        with app.app_context():
            # Create regular user
            user = User(
                username="user",
                email="user@example.com",
                password_hash=generate_password_hash("userpass"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Login as user
            client.post("/login", data={"username": "user", "password": "userpass"})

            # Access route allowing user, manager, admin
            response = client.get("/user-route")
            assert response.status_code == 200
            assert b"User access granted" in response.data


@pytest.mark.integration
class TestRoleBasedAccessControl:
    """Integration tests for role-based access control across different scenarios."""

    def test_role_escalation_prevention(self, app, client):
        """User cannot escalate privileges to access admin routes."""
        with app.app_context():
            # Create regular user
            user = User(
                username="user",
                email="user@example.com",
                password_hash=generate_password_hash("userpass"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()

            # Login as user
            client.post("/login", data={"username": "user", "password": "userpass"})

            # Attempt to access admin route
            response = client.get("/admin-only")
            assert response.status_code == 403

            # Attempt to access manager route
            response = client.get("/manager-only")
            assert response.status_code == 403

    def test_logout_prevents_access(self, app, client):
        """After logout, user cannot access protected routes."""
        with app.app_context():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

            # Login as admin
            client.post(
                "/login", data={"username": "admin", "password": "adminpass"}
            )

            # Access admin route (should work)
            response = client.get("/admin-only")
            assert response.status_code == 200

            # Logout
            client.get("/logout")

            # Try to access admin route again (should redirect to login)
            response = client.get("/admin-only", follow_redirects=False)
            assert response.status_code == 302
            assert "/login" in response.location

    def test_session_persistence_across_requests(
        self, app, client
    ):
        """User session should persist across multiple requests."""
        with app.app_context():
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpass"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

            # Login
            client.post(
                "/login", data={"username": "admin", "password": "adminpass"}
            )

            # Make multiple requests to protected route
            for _ in range(3):
                response = client.get("/admin-only")
                assert response.status_code == 200
                assert b"Admin access granted" in response.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])