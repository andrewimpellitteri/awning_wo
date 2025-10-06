from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from models.work_order import WorkOrder
from sqlalchemy import or_

in_progress_bp = Blueprint("in_progress", __name__)


@in_progress_bp.route("/")
@login_required
def in_progress_home():
    return redirect(url_for("in_progress.list_in_progress"))


# Route for in-progress work orders
@in_progress_bp.route("/list_in_progress")
@login_required
def list_in_progress():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(WorkOrder.ProcessingStatus == True)

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="in_progress",
    )


# Route for recently cleaned or treated work orders
@in_progress_bp.route("/list_recently_cleaned")
@login_required
def list_recently_cleaned():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(
        or_(WorkOrder.Clean.isnot(None), WorkOrder.Treat.isnot(None)),
        WorkOrder.DateCompleted.is_(None),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="recently_cleaned",
    )
