from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import login_required
from models.work_order import WorkOrder
from .work_orders import format_date_from_str
from sqlalchemy import or_, func
from extensions import db
from decorators import role_required
from flask import current_app

in_progress_bp = Blueprint("in_progress", __name__)


@in_progress_bp.route("/")
@login_required
def list_in_progress():
    """List all work orders set to in progress"""

    return render_template(
        "in_progress/list.html",
    )
