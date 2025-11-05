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
            print(f"[REGISTER] Received token: '{token_str}'")

            invite = InviteToken.query.filter_by(token=token_str, used=False).first()
            print(f"[REGISTER] Token lookup result: {invite}")

            if not invite:
                print(f"[REGISTER] Token validation failed - token not found or already used")
                flash("Invalid or already used invitation token. Please check the token and try again.", "error")
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
            print(f"[REGISTER] Successfully registered user: {username} with role: {user.role}")

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            # Log the error for debugging
            import traceback
            error_msg = str(e)
            print(f"Registration error: {error_msg}")
            print(traceback.format_exc())

            # Provide user-friendly error message
            if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
                flash("Username or email already exists. Please try different credentials.", "error")
            else:
                flash(f"Registration failed: {error_msg}", "error")
            return redirect(url_for("auth.register"))

    return render_template("auth/register.html")
