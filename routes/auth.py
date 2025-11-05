from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models.user import User
from models.invite_token import InviteToken
from extensions import db  # instead of from app import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            token_str = request.form.get("token")
            invite = InviteToken.query.filter_by(token=token_str, used=False).first()

            if not invite:
                flash("Invalid or already used invitation token", "error")
                return redirect(url_for("auth.register"))

            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")

            if not all([username, email, password]):
                flash("All fields are required.", "error")
                return redirect(url_for("auth.register"))

            if User.query.filter_by(username=username).first():
                flash("Username already exists", "error")
                return redirect(url_for("auth.register"))
            if User.query.filter_by(email=email).first():
                flash("Email already registered", "error")
                return redirect(url_for("auth.register"))

            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=invite.role,
            )
            db.session.add(user)

            # Mark invite as used
            invite.used = True
            db.session.add(invite)

            db.session.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            # Log the error for debugging
            import traceback
            print(f"Registration error: {str(e)}")
            print(traceback.format_exc())
            flash(f"Registration failed: {str(e)}", "error")
            return redirect(url_for("auth.register"))

    return render_template("auth/register.html")
