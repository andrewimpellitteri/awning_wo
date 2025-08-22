from flask import Blueprint, render_template, request
from extensions import db
from models.work_order import WorkOrder
from sqlalchemy import or_

work_orders_bp = Blueprint("work_orders", __name__, url_prefix="/work_orders")


@work_orders_bp.route("/")
def list_work_orders():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query

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
        "work_orders/list.html",
        work_orders=work_orders,
        pagination=pagination,
        search=search,
    )


@work_orders_bp.route("/<work_order_no>")
def view_work_order(work_order_no):
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()
    return render_template("work_orders/detail.html", work_order=work_order)


@work_orders_bp.route("/status/<status>")
def list_by_status(status):
    """Filter work orders by completion status using DateCompleted"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Pending = DateCompleted is NULL or empty string
    if status.upper() == "PENDING":
        query = WorkOrder.query.filter(
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
        )
    # Completed = DateCompleted has a value
    elif status.upper() == "COMPLETED":
        query = WorkOrder.query.filter(
            WorkOrder.DateCompleted.isnot(None), WorkOrder.DateCompleted != ""
        )
    else:
        query = WorkOrder.query  # fallback if unknown status

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
                WorkOrder.ShipTo.like(search_term),
            )
        )

    pagination = query.order_by(
        WorkOrder.DateIn.desc().nullslast(), WorkOrder.WorkOrderNo.desc()
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "work_orders/list.html",
        work_orders=pagination.items,
        pagination=pagination,
        search=search,
        current_status=status,
    )


@work_orders_bp.route("/pending")
def pending_work_orders():
    """Show work orders that are not completed"""
    return list_by_status("PENDING")


@work_orders_bp.route("/completed")
def completed_work_orders():
    """Show completed work orders"""
    return list_by_status("COMPLETED")


@work_orders_bp.route("/rush")
def rush_work_orders():
    """Show open rush work orders"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(
        or_(WorkOrder.RushOrder == "1", WorkOrder.FirmRush == "1"),
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
            )
        )

    pagination = query.order_by(
        WorkOrder.DateRequired.asc().nullslast(),
        WorkOrder.DateIn.desc().nullslast(),
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "work_orders/list.html",
        work_orders=pagination.items,
        pagination=pagination,
        search=search,
        is_rush_view=True,
    )
