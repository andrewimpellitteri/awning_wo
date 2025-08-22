from flask import Blueprint, render_template, request
from extensions import db
from models.repair_order import RepairWorkOrder
from sqlalchemy import or_

repair_work_orders_bp = Blueprint(
    "repair_work_orders", __name__, url_prefix="/repair_work_orders"
)


@repair_work_orders_bp.route("/")
def list_repair_work_orders():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = RepairWorkOrder.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RepairWorkOrder.RepairOrderNo.like(search_term),
                RepairWorkOrder.CustID.like(search_term),
                RepairWorkOrder.ROName.like(search_term),
                RepairWorkOrder.SOURCE.like(search_term),
                RepairWorkOrder.RackNo.like(search_term),
                RepairWorkOrder.ITEM_TYPE.like(search_term),
                RepairWorkOrder.TYPE_OF_REPAIR.like(search_term),
                RepairWorkOrder.SPECIALINSTRUCTIONS.like(search_term),
                RepairWorkOrder.REPAIRSDONEBY.like(search_term),
                RepairWorkOrder.LOCATION.like(search_term),
                RepairWorkOrder.RETURNSTATUS.like(search_term),
            )
        )

    pagination = query.order_by(
        RepairWorkOrder.DateIn.desc().nullslast(), RepairWorkOrder.RepairOrderNo.desc()
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "repair_orders/list.html",
        repair_work_orders=pagination.items,
        pagination=pagination,
        search=search,
    )


@repair_work_orders_bp.route("/<repair_order_no>")
def view_repair_work_order(repair_order_no):
    repair_work_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()
    return render_template(
        "repair_orders/detail.html", repair_work_order=repair_work_order
    )


@repair_work_orders_bp.route("/status/<status>")
def list_by_status(status):
    """Filter repair work orders by completion status using DateCompleted"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    if status.upper() == "COMPLETED":
        query = RepairWorkOrder.query.filter(
            RepairWorkOrder.DateCompleted.isnot(None),
            RepairWorkOrder.DateCompleted != "",
        )
    elif status.upper() == "PENDING":
        query = RepairWorkOrder.query.filter(
            or_(
                RepairWorkOrder.DateCompleted.is_(None),
                RepairWorkOrder.DateCompleted == "",
            )
        )
    else:
        query = RepairWorkOrder.query  # fallback

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RepairWorkOrder.RepairOrderNo.like(search_term),
                RepairWorkOrder.CustID.like(search_term),
                RepairWorkOrder.ROName.like(search_term),
                RepairWorkOrder.TYPE_OF_REPAIR.like(search_term),
            )
        )

    pagination = query.order_by(
        RepairWorkOrder.DateIn.desc().nullslast(), RepairWorkOrder.RepairOrderNo.desc()
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "repair_orders/list.html",
        repair_work_orders=pagination.items,
        pagination=pagination,
        search=search,
        current_status=status,
    )


@repair_work_orders_bp.route("/pending")
def pending_repairs():
    return list_by_status("PENDING")


@repair_work_orders_bp.route("/completed")
def completed_repairs():
    return list_by_status("COMPLETED")


@repair_work_orders_bp.route("/rush")
def rush_orders():
    """Show open rush repair work orders"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = RepairWorkOrder.query.filter(
        or_(RepairWorkOrder.RushOrder == "YES", RepairWorkOrder.FirmRush == "YES"),
        or_(
            RepairWorkOrder.DateCompleted.is_(None), RepairWorkOrder.DateCompleted == ""
        ),
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RepairWorkOrder.RepairOrderNo.like(search_term),
                RepairWorkOrder.CustID.like(search_term),
                RepairWorkOrder.ROName.like(search_term),
            )
        )

    pagination = query.order_by(
        RepairWorkOrder.DateRequired.asc().nullslast(),
        RepairWorkOrder.DateIn.desc().nullslast(),
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "repair_orders/list.html",
        repair_work_orders=pagination.items,
        pagination=pagination,
        search=search,
        is_rush_view=True,
    )
