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
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(WorkOrder.ProcessingStatus == True)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
                WorkOrder.Storage.like(search_term),
                WorkOrder.RackNo.like(search_term),
                WorkOrder.ShipTo.like(search_term),
                WorkOrder.SpecialInstructions.like(search_term),
                WorkOrder.RepairsNeeded.like(search_term),
            )
        )

    pagination = query.order_by(WorkOrder.DateIn.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        search=search,
    )
