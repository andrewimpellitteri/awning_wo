from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.user import User
from models.invite_token import InviteToken
from extensions import db
from decorators import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


VALID_ROLES = {"user", "manager", "admin"}


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_users():
    if request.method == "POST" and "role" in request.form:
        role = request.form.get("role", "user")
        invite = InviteToken.generate_token(role=role)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("An error occurred. Please try again.", "error")
            print(f"Error during database commit: {e}")

        flash(f"Generated invite token: {invite.token}", "success")

    users = User.query.all()
    tokens = InviteToken.query.order_by(InviteToken.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=users, tokens=tokens)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete yourself!", "error")
        return redirect(url_for("admin.manage_users"))

    db.session.delete(user)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while deleting the user. Please try again.", "error")
        print(f"Error during database commit: {e}")
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/<int:user_id>/update_role", methods=["POST"])
@login_required
@role_required("admin")
def update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = (request.form.get("role") or "").strip().lower()

    if new_role not in VALID_ROLES:
        flash("Invalid role selected.", "error")
        return redirect(url_for("admin.manage_users"))

    if user.id == current_user.id and new_role != user.role:
        flash("You cannot change your own role.", "error")
        return redirect(url_for("admin.manage_users"))

    user.role = new_role

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while updating the role. Please try again.", "error")
        print(f"Error during database commit: {e}")

    flash(f"Updated {user.username}'s role to {new_role}", "success")
    return redirect(url_for("admin.manage_users"))
