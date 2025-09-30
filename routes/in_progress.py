from flask import Blueprint, render_template, request
from flask_login import login_required
from models.work_order import WorkOrder

in_progress_bp = Blueprint("in_progress", __name__)


@in_progress_bp.route("/")
@login_required
def list_in_progress():
    """List all work orders set to in progress"""
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(WorkOrder.ProcessingStatus == True)

    pagination = query.order_by(WorkOrder.DateIn.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
    )
