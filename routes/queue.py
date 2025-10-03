from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import login_required
from models.work_order import WorkOrder
from .work_orders import format_date_from_str
from sqlalchemy import or_, func
from extensions import db
from decorators import role_required
from flask import current_app

queue_bp = Blueprint("cleaning_queue", __name__)


# Sort firm rush orders by DateRequired (closest date first), then DateIn, then WorkOrderNo
def safe_date_sort_key(date_value):
    """Convert date object to a sortable format - now handles proper date types"""
    from datetime import date

    # Handle None or empty
    if not date_value:
        return date.max  # Put empty dates at the end

    # Already a date object - return as-is
    if isinstance(date_value, date):
        return date_value

    # Legacy string handling (for backward compatibility during migration)
    if isinstance(date_value, str):
        if date_value.strip() == "":
            return date.max

        # If it's already in YYYY-MM-DD format, parse it
        if len(date_value) == 10 and date_value[4] == "-" and date_value[7] == "-":
            try:
                from datetime import datetime
                return datetime.strptime(date_value, "%Y-%m-%d").date()
            except:
                return date.max

        # Try other formats
        try:
            from datetime import datetime
            if "/" in date_value:
                parsed_date = datetime.strptime(date_value, "%m/%d/%Y")
                return parsed_date.date()
        except:
            pass

    # Fallback
    return date.max


def initialize_queue_positions_for_unassigned():
    """Initialize queue positions for work orders that don't have them (preserves existing manual ordering)"""
    try:
        base_filter = WorkOrder.DateCompleted.is_(None)

        # Only get work orders without queue positions
        unassigned_orders = WorkOrder.query.filter(
            base_filter, WorkOrder.QueuePosition.is_(None)
        ).all()

        if not unassigned_orders:
            return 0

        # Sort unassigned orders by priority and date
        def priority_sort_key(wo):
            if wo.FirmRush:
                return (
                    1,
                    safe_date_sort_key(wo.DateRequired),
                    safe_date_sort_key(wo.DateIn),
                    wo.WorkOrderNo,
                )
            elif wo.RushOrder:
                return (2, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)
            else:
                return (3, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)

        sorted_unassigned = sorted(unassigned_orders, key=priority_sort_key)

        # Separate by priority for proper insertion and sort each group appropriately
        firm_rush_orders = [wo for wo in sorted_unassigned if wo.FirmRush]
        rush_orders = [
            wo for wo in sorted_unassigned if wo.RushOrder and not wo.FirmRush
        ]
        regular_orders = [
            wo for wo in sorted_unassigned if not wo.RushOrder and not wo.FirmRush
        ]

        firm_rush_orders.sort(
            key=lambda wo: (
                safe_date_sort_key(wo.DateRequired),
                safe_date_sort_key(wo.DateIn),
                wo.WorkOrderNo,
            )
        )

        # Sort rush orders by DateIn, then WorkOrderNo
        rush_orders.sort(key=lambda wo: (safe_date_sort_key(wo.DateIn), wo.WorkOrderNo))

        # Sort regular orders by DateIn, then WorkOrderNo
        regular_orders.sort(
            key=lambda wo: (safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)
        )

        position_counter = 0

        # Handle Firm Rush orders - insert at the very beginning
        if firm_rush_orders:
            # Shift all existing orders down by the number of firm rush orders
            existing_orders = WorkOrder.query.filter(
                base_filter, WorkOrder.QueuePosition.isnot(None)
            ).all()

            for existing_wo in existing_orders:
                existing_wo.QueuePosition += len(firm_rush_orders)

            # Assign positions to firm rush orders at the top
            for i, wo in enumerate(firm_rush_orders):
                wo.QueuePosition = i + 1
                position_counter += 1

        # Handle Rush orders - insert after firm rush but before regular
        if rush_orders:
            # Find where rush orders should start (after last firm rush)
            last_firm_rush_position = 0
            if firm_rush_orders:
                last_firm_rush_position = len(firm_rush_orders)
            else:
                # Check existing firm rush orders
                existing_firm_rush = (
                    WorkOrder.query.filter(
                        base_filter,
                        WorkOrder.FirmRush == True,
                        WorkOrder.QueuePosition.isnot(None),
                    )
                    .order_by(WorkOrder.QueuePosition.desc())
                    .first()
                )

                if existing_firm_rush:
                    last_firm_rush_position = existing_firm_rush.QueuePosition

            # Shift existing rush and regular orders down
            existing_non_firm_rush = WorkOrder.query.filter(
                base_filter,
                WorkOrder.QueuePosition > last_firm_rush_position,
                WorkOrder.QueuePosition.isnot(None),
            ).all()

            for existing_wo in existing_non_firm_rush:
                existing_wo.QueuePosition += len(rush_orders)

            # Assign positions to rush orders
            for i, wo in enumerate(rush_orders):
                wo.QueuePosition = last_firm_rush_position + i + 1
                position_counter += 1

        # Handle Regular orders - add at the end
        if regular_orders:
            # Get the current highest position
            max_position = (
                db.session.query(func.max(WorkOrder.QueuePosition))
                .filter(base_filter)
                .scalar()
                or 0
            )

            for i, wo in enumerate(regular_orders):
                wo.QueuePosition = max_position + i + 1
                position_counter += 1

        db.session.commit()
        return len(sorted_unassigned)

    except Exception as e:
        db.session.rollback()
        print(f"Error initializing queue positions: {e}")
        return 0


def initialize_all_queue_positions(force_reset=False):
    """Initialize queue positions for all work orders that don't have them"""
    try:
        base_filter = WorkOrder.DateCompleted.is_(None)

        if force_reset:
            # Clear all existing positions first
            WorkOrder.query.filter(base_filter).update({WorkOrder.QueuePosition: None})
            db.session.flush()

        # Get all work orders without queue positions
        unpositioned_orders = WorkOrder.query.filter(
            base_filter, WorkOrder.QueuePosition.is_(None)
        ).all()

        if not unpositioned_orders:
            return 0

        # Sort by priority and date
        def priority_sort_key(wo):
            if wo.FirmRush:
                return (
                    1,
                    safe_date_sort_key(wo.DateRequired),
                    safe_date_sort_key(wo.DateIn),
                    wo.WorkOrderNo,
                )
            elif wo.RushOrder:
                return (2, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)
            else:
                return (3, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)

        sorted_orders = sorted(unpositioned_orders, key=priority_sort_key)

        # Get starting position
        max_position = (
            db.session.query(func.max(WorkOrder.QueuePosition))
            .filter(base_filter)
            .scalar()
            or 0
        )

        # Assign positions
        for i, wo in enumerate(sorted_orders):
            wo.QueuePosition = max_position + i + 1

        db.session.commit()
        return len(sorted_orders)

    except Exception as e:
        db.session.rollback()
        print(f"Error initializing queue positions: {e}")
        return 0

    """Initialize queue positions for work orders that don't have them (preserves existing manual ordering)"""
    try:
        base_filter = WorkOrder.DateCompleted.is_(None)

        # Only get work orders without queue positions
        unassigned_orders = WorkOrder.query.filter(
            base_filter, WorkOrder.QueuePosition.is_(None)
        ).all()

        if not unassigned_orders:
            return 0

        # Sort unassigned orders by priority and date
        def priority_sort_key(wo):
            if wo.FirmRush:
                return (
                    1,
                    safe_date_sort_key(wo.DateRequired),
                    safe_date_sort_key(wo.DateIn),
                    wo.WorkOrderNo,
                )
            elif wo.RushOrder:
                return (2, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)
            else:
                return (3, safe_date_sort_key(wo.DateIn), wo.WorkOrderNo)

        sorted_unassigned = sorted(unassigned_orders, key=priority_sort_key)

        # Get the highest existing queue position to continue from there
        max_position = (
            db.session.query(func.max(WorkOrder.QueuePosition))
            .filter(base_filter)
            .scalar()
            or 0
        )

        # Assign positions to unassigned orders
        for i, wo in enumerate(sorted_unassigned):
            wo.QueuePosition = max_position + i + 1

        db.session.commit()
        return len(sorted_unassigned)

    except Exception as e:
        db.session.rollback()
        print(f"Error initializing queue positions: {e}")
        return 0


@queue_bp.route("/cleaning-queue")
@login_required
def cleaning_queue():
    """Show work orders in cleaning queue with priority ordering and search"""

    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    show_sail_orders = (
        request.args.get("show_sail_orders", "true").lower() == "true"
    )  # Default to showing sail orders

    # Helper: build search filter if search term is provided
    def search_filter(query):
        if not search:
            return query
        term = f"%{search}%"
        return query.filter(
            or_(
                WorkOrder.WorkOrderNo.ilike(term),
                WorkOrder.CustID.ilike(term),
                WorkOrder.WOName.ilike(term),
                WorkOrder.ShipTo.ilike(term),
            )
        )

    # Base filters: incomplete work orders
    base_filter = WorkOrder.DateCompleted.is_(None)

    # Initialize queue positions for any work orders that don't have them
    initialized_count = initialize_queue_positions_for_unassigned()
    if initialized_count > 0:
        print(f"Auto-initialized {initialized_count} work orders with queue positions")

    # Build the main query with all filters
    all_orders_query = WorkOrder.query.filter(base_filter)

    # Apply search filter
    all_orders_query = search_filter(all_orders_query)

    # DEBUG: Check what's in the config
    sail_sources = current_app.config.get("SAIL_ORDER_SOURCES", [])
    print(f"DEBUG - Config SAIL_ORDER_SOURCES: {sail_sources}")
    print(f"DEBUG - show_sail_orders parameter: {show_sail_orders}")

    # Apply sail order filter if needed
    if not show_sail_orders:
        print(f"DEBUG - Applying sail order filter, excluding: {sail_sources}")
        all_orders_query = all_orders_query.filter(~WorkOrder.ShipTo.in_(sail_sources))

        # DEBUG: Print the SQL after adding sail filter
        if current_app.debug:
            print(
                f"DEBUG - Filtered query SQL: {str(all_orders_query.statement.compile(compile_kwargs={'literal_binds': True}))}"
            )
    else:
        print(
            "DEBUG - NOT applying sail order filter (showing all orders including sail orders)"
        )

    # Apply ordering
    all_orders_query = all_orders_query.order_by(
        WorkOrder.QueuePosition.asc().nullslast(),
        WorkOrder.DateRequired.asc().nullslast(),
        WorkOrder.DateIn.asc().nullslast(),
        WorkOrder.WorkOrderNo.asc(),
    )

    # Execute query
    all_orders = all_orders_query.all()

    # DEBUG: Check what we got back
    print(f"DEBUG - Total orders found: {len(all_orders)}")

    # Count sail orders in results
    sail_orders_in_results = [wo for wo in all_orders if wo.ShipTo in sail_sources]
    print(f"DEBUG - Sail orders in results: {len(sail_orders_in_results)}")
    if sail_orders_in_results:
        print(
            f"DEBUG - Sail order ShipTo values found: {[wo.ShipTo for wo in sail_orders_in_results]}"
        )

    # Show some ShipTo values for debugging
    ship_to_values = list(set([wo.ShipTo for wo in all_orders if wo.ShipTo]))[:10]
    print(f"DEBUG - Sample ShipTo values in results: {ship_to_values}")

    # Calculate counts for each priority (for the stats display)
    firm_rush_orders = [wo for wo in all_orders if wo.FirmRush]
    rush_orders = [
        wo for wo in all_orders if wo.RushOrder and not wo.FirmRush
    ]
    regular_orders = [
        wo for wo in all_orders if not wo.RushOrder and not wo.FirmRush
    ]

    # Manual pagination
    total = len(all_orders)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_orders = all_orders[start:end]

    # Manual pagination object
    class ManualPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if per_page > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None

    pagination = ManualPagination(paginated_orders, page, per_page, total)

    # Add display priority labels
    for wo in paginated_orders:
        if wo.FirmRush:
            wo.priority_label = "FIRM RUSH"
            wo.priority_class = "priority-firm-rush"
        elif wo.RushOrder:
            wo.priority_label = "RUSH"
            wo.priority_class = "priority-rush"
        else:
            wo.priority_label = "REGULAR"
            wo.priority_class = "priority-regular"

    # Queue counts
    queue_counts = {
        "firm_rush": len(firm_rush_orders),
        "rush": len(rush_orders),
        "regular": len(regular_orders),
        "total": total,
    }

    return render_template(
        "queue/list.html",
        work_orders=paginated_orders,
        pagination=pagination,
        search=search,
        per_page=per_page,
        show_sail_orders=show_sail_orders,
        queue_counts=queue_counts,
    )


@queue_bp.route("/api/cleaning-queue/reorder", methods=["POST"])
@login_required
@role_required("admin", "manager")
def reorder_cleaning_queue():
    """Allow manual reordering of work orders in cleaning queue"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data received"})

        work_order_ids = data.get("work_order_ids", [])

        if not work_order_ids:
            return jsonify({"success": False, "message": "No work orders provided"})

        print(f"Reorder request received: {len(work_order_ids)} work orders")
        print(f"Work order IDs: {work_order_ids}")

        # Get the current page info to only reorder visible items
        page = data.get("page", 1)
        per_page = data.get("per_page", 25)

        # Calculate the starting position for this page
        start_position = (page - 1) * per_page + 1

        print(f"Page: {page}, Per page: {per_page}, Start position: {start_position}")

        # Update queue positions for the reordered items
        success_count = 0
        failed_items = []

        for index, wo_id in enumerate(work_order_ids):
            work_order = WorkOrder.query.filter_by(WorkOrderNo=wo_id).first()
            if work_order:
                old_position = work_order.QueuePosition
                new_position = start_position + index
                work_order.QueuePosition = new_position
                success_count += 1
                print(f"Updated WO {wo_id}: {old_position} -> {new_position}")
            else:
                failed_items.append(wo_id)
                print(f"Work order {wo_id} not found")

        db.session.commit()

        result = {
            "success": True,
            "message": f"Queue order updated successfully for {success_count} work orders",
            "updated_count": success_count,
        }

        if failed_items:
            result["warning"] = f"Could not find work orders: {', '.join(failed_items)}"

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        error_msg = f"Error updating queue: {str(e)}"
        print(f"Reorder error: {error_msg}")
        return jsonify({"success": False, "message": error_msg}), 500


@queue_bp.route("/api/cleaning-queue/summary")
@login_required
def cleaning_queue_summary():
    """API endpoint for dashboard summary of cleaning queue"""
    # Count work orders in cleaning queue by priority
    base_filter = WorkOrder.DateCompleted.is_(None)

    firm_rush_count = WorkOrder.query.filter(
        base_filter,
        WorkOrder.FirmRush == True,
    ).count()

    rush_count = WorkOrder.query.filter(
        base_filter,
        WorkOrder.RushOrder == True,
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != True),
    ).count()

    regular_count = WorkOrder.query.filter(
        base_filter,
        or_(WorkOrder.RushOrder.is_(None), WorkOrder.RushOrder != True),
        or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != True),
    ).count()

    total_count = firm_rush_count + rush_count + regular_count

    # Get next 5 work orders in queue for preview (using queue position ordering)
    base_query = WorkOrder.query.filter(base_filter)

    # Get in priority order with queue position ordering
    firm_rush_orders = (
        base_query.filter(WorkOrder.FirmRush == True)
        .order_by(
            WorkOrder.QueuePosition.asc().nullslast(),
            WorkOrder.DateRequired.asc().nullslast(),
            WorkOrder.DateIn.asc().nullslast(),
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
                WorkOrder.RushOrder == True,
                or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != True),
            )
            .order_by(
                WorkOrder.QueuePosition.asc().nullslast(),
                WorkOrder.DateIn.asc().nullslast(),
                WorkOrder.WorkOrderNo.asc(),
            )
            .limit(remaining_slots)
            .all()
        )

        remaining_slots = remaining_slots - len(rush_orders)

        if remaining_slots > 0:
            regular_orders = (
                base_query.filter(
                    or_(WorkOrder.RushOrder.is_(None), WorkOrder.RushOrder != True),
                    or_(WorkOrder.FirmRush.is_(None), WorkOrder.FirmRush != True),
                )
                .order_by(
                    WorkOrder.QueuePosition.asc().nullslast(),
                    WorkOrder.DateIn.asc().nullslast(),
                    WorkOrder.WorkOrderNo.asc(),
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
                    if wo.FirmRush
                    else ("RUSH" if wo.RushOrder else "REGULAR"),
                    "detail_url": url_for(
                        "work_orders.view_work_order", work_order_no=wo.WorkOrderNo
                    ),
                    "queue_position": wo.QueuePosition,
                }
                for wo in next_orders[:5]
            ],
        }
    )


@queue_bp.route("/api/cleaning-queue/initialize", methods=["POST"])
@login_required
def initialize_queue_positions():
    """Manually initialize queue positions for all work orders that don't have them"""
    try:
        initialized_count = initialize_queue_positions_for_unassigned()

        if initialized_count == 0:
            return jsonify(
                {
                    "success": True,
                    "message": "All work orders already have queue positions assigned",
                    "initialized_count": 0,
                }
            )

        return jsonify(
            {
                "success": True,
                "message": f"Successfully initialized queue positions for {initialized_count} work orders",
                "initialized_count": initialized_count,
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Error initializing queue positions: {str(e)}",
                "initialized_count": 0,
            }
        )


@queue_bp.route("/api/cleaning-queue/reset", methods=["POST"])
@login_required
@role_required("admin", "manager")
def reset_all_queue_positions():
    """Reset all queue positions and reassign them from scratch (WARNING: destroys manual ordering)"""
    try:
        base_filter = WorkOrder.DateCompleted.is_(None)

        # Clear all existing queue positions
        cleared_count = WorkOrder.query.filter(base_filter).update(
            {WorkOrder.QueuePosition: None}
        )
        db.session.commit()

        # Reinitialize them
        initialized_count = initialize_queue_positions_for_unassigned()

        return jsonify(
            {
                "success": True,
                "message": f"Reset complete: cleared {cleared_count} positions, reassigned {initialized_count} work orders",
                "cleared_count": cleared_count,
                "initialized_count": initialized_count,
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify(
            {"success": False, "message": f"Error resetting queue positions: {str(e)}"}
        )
