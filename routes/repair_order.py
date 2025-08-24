from flask import Blueprint, render_template, request, jsonify, url_for
from models.repair_order import RepairWorkOrder
from models.customer import Customer  # Assuming you might need this for joins
from sqlalchemy import or_

repair_work_orders_bp = Blueprint(
    "repair_work_orders", __name__, url_prefix="/repair_work_orders"
)


def format_date_from_str(value):
    """Ensure dates are returned as YYYY-MM-DD strings to avoid object serialization issues."""
    if not value:
        return None
    # If it's already a string, assume correct format. Otherwise, format the date/datetime object.
    return value.strftime("%Y-%m-%d") if not isinstance(value, str) else value


@repair_work_orders_bp.route("/")
def list_repair_work_orders():
    """
    Renders the main page for repair work orders.
    The page will be populated with data by the Tabulator table via an API call.
    """
    return render_template("repair_orders/list.html")


@repair_work_orders_bp.route("/<repair_order_no>")
def view_repair_work_order(repair_order_no):
    """Displays the detail page for a single repair work order."""
    repair_work_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()
    return render_template(
        "repair_orders/detail.html", repair_work_order=repair_work_order
    )


@repair_work_orders_bp.route("/api/repair_work_orders")
def api_repair_work_orders():
    """
    API endpoint to provide repair work order data to the Tabulator table.
    Handles remote pagination, sorting, and filtering.
    """
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()
    search = request.args.get("search", "").strip()

    query = RepairWorkOrder.query

    # ✅ Status quick filters
    if status == "pending":
        query = query.filter(
            or_(
                RepairWorkOrder.DateCompleted.is_(None),
                RepairWorkOrder.DateCompleted == "",
            )
        )
    elif status == "completed":
        query = query.filter(
            RepairWorkOrder.DateCompleted.isnot(None),
            RepairWorkOrder.DateCompleted != "",
        )
    elif status == "rush":
        query = query.filter(
            or_(RepairWorkOrder.RushOrder == "YES", RepairWorkOrder.FirmRush == "YES"),
            or_(
                RepairWorkOrder.DateCompleted.is_(None),
                RepairWorkOrder.DateCompleted == "",
            ),
        )

    # 🔎 Global search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RepairWorkOrder.RepairOrderNo.ilike(search_term),
                RepairWorkOrder.CustID.ilike(search_term),
                RepairWorkOrder.ROName.ilike(search_term),
                RepairWorkOrder.ITEM_TYPE.ilike(search_term),
                RepairWorkOrder.TYPE_OF_REPAIR.ilike(search_term),
                RepairWorkOrder.LOCATION.ilike(search_term),
            )
        )

    # 📝 Per-column header filters from Tabulator
    filterable_columns = [
        "RepairOrderNo",
        "CustID",
        "ROName",
        "ITEM_TYPE",
        "TYPE_OF_REPAIR",
        "DateIn",
        "DateRequired",
        "LOCATION",
    ]
    for col in filterable_columns:
        filter_val = request.args.get(f"filter_{col}")
        if filter_val:
            query = query.filter(getattr(RepairWorkOrder, col).ilike(f"%{filter_val}%"))

    # ↕️ Sorting logic to handle Tabulator's 'sort' parameter
    order_by_clauses = []
    i = 0
    while True:
        field = request.args.get(f"sort[{i}][field]")
        if not field:
            break

        direction = request.args.get(f"sort[{i}][dir]", "asc")
        column = getattr(RepairWorkOrder, field, None)

        if column:
            order_by_clauses.append(
                column.desc() if direction == "desc" else column.asc()
            )
        i += 1

    if order_by_clauses:
        query = query.order_by(*order_by_clauses)
    else:
        # Default sort if none is provided
        query = query.order_by(
            RepairWorkOrder.DateIn.desc().nullslast(),
            RepairWorkOrder.RepairOrderNo.desc(),
        )

    # Get total count before pagination
    total = query.count()

    # Paginate the results
    pagination = query.paginate(page=page, per_page=size, error_out=False)

    # Format data for JSON response
    data = [
        {
            "RepairOrderNo": order.RepairOrderNo,
            "CustID": order.CustID,
            "ROName": order.ROName,
            "ITEM_TYPE": order.ITEM_TYPE,
            "TYPE_OF_REPAIR": order.TYPE_OF_REPAIR,
            "DateIn": format_date_from_str(order.DateIn),
            "DateRequired": format_date_from_str(order.DateRequired),
            "LOCATION": order.LOCATION,
            "is_rush": order.RushOrder == "YES" or order.FirmRush == "YES",
            "detail_url": url_for(
                "repair_work_orders.view_repair_work_order",
                repair_order_no=order.RepairOrderNo,
            ),
            "customer_url": url_for(
                "customers.customer_detail", customer_id=order.CustID
            )
            if order.customer
            else None,
        }
        for order in pagination.items
    ]

    return jsonify(
        {
            "data": data,
            "total": total,
            "last_page": pagination.pages,
        }
    )
