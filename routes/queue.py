from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import login_required
from models.work_order import WorkOrder
from .work_orders import format_date_from_str
from sqlalchemy import or_
from extensions import db


queue_bp = Blueprint("cleaning_queue", __name__)


@queue_bp.route("/cleaning-queue")
@login_required
def cleaning_queue():
    """Show work orders in cleaning queue with priority ordering"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)

    # Base query for uncompleted work orders that need cleaning
    base_query = WorkOrder.query.filter(
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
    )

    if search:
        search_term = f"%{search}%"
        base_query = base_query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
                WorkOrder.ShipTo.like(search_term),
            )
        )

    # Create separate queries for each priority level
    # Priority 1: Firm Rush orders (sorted by DateRequired)
    firm_rush_query = base_query.filter(WorkOrder.FirmRush == "1").order_by(
        WorkOrder.DateRequired.asc().nullslast(), WorkOrder.DateIn.asc().nullslast()
    )

    # Priority 2: Regular Rush orders (sorted by DateIn)
    rush_query = base_query.filter(
        WorkOrder.RushOrder == "1",
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
    ).order_by(WorkOrder.DateIn.asc().nullslast(), WorkOrder.WorkOrderNo.asc())

    # Priority 3: Regular orders (FIFO by DateIn)
    regular_query = base_query.filter(
        or_(WorkOrder.RushOrder.is_(None), WorkOrder.RushOrder != "1"),
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
    ).order_by(WorkOrder.DateIn.asc().nullslast(), WorkOrder.WorkOrderNo.asc())

    # Get all work orders in priority order
    firm_rush_orders = firm_rush_query.all()
    rush_orders = rush_query.all()
    regular_orders = regular_query.all()

    # Combine in priority order
    all_orders = firm_rush_orders + rush_orders + regular_orders

    # Manual pagination since we combined queries
    total = len(all_orders)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_orders = all_orders[start:end]

    # Create pagination object manually
    class ManualPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None

    pagination = ManualPagination(paginated_orders, page, per_page, total)

    # Add priority labels to each work order for display
    for wo in paginated_orders:
        if wo.FirmRush == "1":
            wo.priority_label = "FIRM RUSH"
            wo.priority_class = "priority-firm-rush"
        elif wo.RushOrder == "1":
            wo.priority_label = "RUSH"
            wo.priority_class = "priority-rush"
        else:
            wo.priority_label = "REGULAR"
            wo.priority_class = "priority-regular"

    return render_template(
        "queue/list.html",
        work_orders=paginated_orders,
        pagination=pagination,
        search=search,
        per_page=per_page,
        queue_counts={
            "firm_rush": len(firm_rush_orders),
            "rush": len(rush_orders),
            "regular": len(regular_orders),
            "total": total,
        },
    )


@queue_bp.route("/api/cleaning-queue/reorder", methods=["POST"])
@login_required
def reorder_cleaning_queue():
    """Allow manual reordering of work orders in cleaning queue"""
    data = request.get_json()
    work_order_ids = data.get("work_order_ids", [])

    if not work_order_ids:
        return jsonify({"success": False, "message": "No work orders provided"})

    try:
        # Update the queue position for each work order
        for index, wo_id in enumerate(work_order_ids):
            work_order = WorkOrder.query.filter_by(WorkOrderNo=wo_id).first()
            if work_order:
                # Add a QueuePosition field or use an existing field to track manual order
                # For now, we'll use a simple approach with a custom field
                work_order.QueuePosition = index + 1

        db.session.commit()
        return jsonify({"success": True, "message": "Queue order updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error updating queue: {str(e)}"})


@queue_bp.route("/api/cleaning-queue/summary")
@login_required
def cleaning_queue_summary():
    """API endpoint for dashboard summary of cleaning queue"""
    # Count work orders in cleaning queue by priority
    firm_rush_count = WorkOrder.query.filter(
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
        WorkOrder.FirmRush == "1",
    ).count()

    rush_count = WorkOrder.query.filter(
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
        WorkOrder.RushOrder == "1",
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
    ).count()

    regular_count = WorkOrder.query.filter(
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
        or_(WorkOrder.RushOrder.is_(None), WorkOrder.RushOrder != "1"),
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
    ).count()

    total_count = firm_rush_count + rush_count + regular_count

    # Get next 5 work orders in queue for preview
    base_query = WorkOrder.query.filter(
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
    )

    # Get in priority order (same logic as main queue)
    firm_rush_orders = (
        base_query.filter(WorkOrder.FirmRush == "1")
        .order_by(
            WorkOrder.DateRequired.asc().nullslast(), WorkOrder.DateIn.asc().nullslast()
        )
        .limit(5)
        .all()
    )

    remaining_slots = 5 - len(firm_rush_orders)
    rush_orders = []
    regular_orders = []

    if remaining_slots > 0:
        rush_orders = (
            base_query.filter(
                WorkOrder.RushOrder == "1",
                or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
            )
            .order_by(WorkOrder.DateIn.asc().nullslast(), WorkOrder.WorkOrderNo.asc())
            .limit(remaining_slots)
            .all()
        )

        remaining_slots = remaining_slots - len(rush_orders)

        if remaining_slots > 0:
            regular_orders = (
                base_query.filter(
                    or_(WorkOrder.RushOrder.is_(None), WorkOrder.RushOrder != "1"),
                    or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != "1"),
                )
                .order_by(
                    WorkOrder.DateIn.asc().nullslast(), WorkOrder.WorkOrderNo.asc()
                )
                .limit(remaining_slots)
                .all()
            )

    next_orders = firm_rush_orders + rush_orders + regular_orders

    return jsonify(
        {
            "counts": {
                "firm_rush": firm_rush_count,
                "rush": rush_count,
                "regular": regular_count,
                "total": total_count,
            },
            "next_orders": [
                {
                    "WorkOrderNo": wo.WorkOrderNo,
                    "WOName": wo.WOName,
                    "CustID": wo.CustID,
                    "DateIn": format_date_from_str(wo.DateIn),
                    "DateRequired": format_date_from_str(wo.DateRequired),
                    "priority": "FIRM RUSH"
                    if wo.FirmRush == "1"
                    else ("RUSH" if wo.RushOrder == "1" else "REGULAR"),
                    "detail_url": url_for(
                        "work_orders.view_work_order", work_order_no=wo.WorkOrderNo
                    ),
                }
                for wo in next_orders[:5]
            ],
        }
    )
