
import pytest
from flask import url_for
from models.user import User
from models.invite_token import InviteToken
from extensions import db
from werkzeug.security import generate_password_hash

class TestAdminRoutes:
    @pytest.fixture(autouse=True)
    def admin_user(self, app):
        with app.app_context():
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("adminpassword"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()
            yield admin
            db.session.delete(admin)
            db.session.commit()

    def test_manage_users_page_renders(self, client, admin_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.get(url_for("admin.manage_users"))
        assert response.status_code == 200
        assert b"User Management" in response.data

    def test_generate_invite_token(self, client, admin_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.post(
            url_for("admin.manage_users"),
            data={"role": "user"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Generated invite token" in response.data
        with client.application.app_context():
            assert InviteToken.query.count() == 1
            assert InviteToken.query.first().role == "user"

    @pytest.fixture(autouse=True)
    def test_user(self, app):
        with app.app_context():
            user = User(
                username="testuser",
                email="test@example.com",
                password_hash=generate_password_hash("testpassword"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()
            yield user
            db.session.delete(user)
            db.session.commit()

    def test_delete_user(self, client, admin_user, test_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.post(
            url_for("admin.delete_user", user_id=test_user.id),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"User deleted successfully." in response.data
        with client.application.app_context():
            assert User.query.get(test_user.id) is None

    def test_cannot_delete_self(self, client, admin_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.post(
            url_for("admin.delete_user", user_id=admin_user.id),
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"You cannot delete yourself!" in response.data
        with client.application.app_context():
            assert User.query.get(admin_user.id) is not None

    def test_update_user_role(self, client, admin_user, test_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.post(
            url_for("admin.update_user_role", user_id=test_user.id),
            data={"role": "manager"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Updated testuser&#39;s role to manager" in response.data
        with client.application.app_context():
            updated_user = User.query.get(test_user.id)
            assert updated_user.role == "manager"

    def test_update_user_role_invalid_role(self, client, admin_user, test_user):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpassword"},
            follow_redirects=True,
        )
        response = client.post(
            url_for("admin.update_user_role", user_id=test_user.id),
            data={"role": "invalid_role"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        with client.session_transaction() as session:
            flashed_messages = session.get('_flashes', [])
        assert len(flashed_messages) == 1
        assert flashed_messages[0][0] == 'error'
        assert "Invalid role selected." in flashed_messages[0][1]
        with client.application.app_context():
            updated_user = User.query.get(test_user.id)
            assert updated_user.role == "user" # Role should not have changed
