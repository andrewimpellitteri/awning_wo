from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.user import User
from models.invite_token import InviteToken
from extensions import db
from decorators import role_required  # from the decorator I showed earlier

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@role_required("admin")
def manage_users():
    users = User.query.all()
    return render_template("admin/manage_users.html", users=users)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete yourself!", "error")
        return redirect(url_for("admin.manage_users"))

    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/<int:user_id>/update_role", methods=["POST"])
@login_required
@role_required("admin")
def update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role")
    if new_role not in ["user", "manager", "admin"]:
        flash("Invalid role selected.", "error")
    else:
        user.role = new_role
        db.session.commit()
        flash(f"Updated {user.username}'s role to {new_role}", "success")

    return redirect(url_for("admin.manage_users"))


# admin blueprint


@admin_bp.route("/invite_tokens", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_invite_tokens():
    if request.method == "POST":
        role = request.form.get("role", "user")
        invite = InviteToken.generate(role=role)
        flash(f"Generated invite token: {invite.token}", "success")

    tokens = InviteToken.query.order_by(InviteToken.created_at.desc()).all()
    return render_template("admin/manage_invite_tokens.html", tokens=tokens)
