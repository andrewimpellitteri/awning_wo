from flask import Blueprint, render_template
from extensions import db
from models.work_order import WorkOrder  # Adjust import path as needed
from sqlalchemy import func, nullslast
from datetime import datetime

# Create blueprint (adjust name as needed)
dashboard_bp = Blueprint("dashboard", __name__)


def get_recent_orders(limit=10):
    recent_orders = (
        db.session.query(
            WorkOrder,
            func.greatest(WorkOrder.created_at, WorkOrder.updated_at).label(
                "activity_time"
            ),
        )
        .outerjoin(WorkOrder.files)
        .outerjoin(WorkOrder.ship_to_source)
        .order_by(
            nullslast(func.greatest(WorkOrder.created_at, WorkOrder.updated_at).desc())
        )
        .limit(limit)
        .all()
    )

    # In your Flask route
    recent_orders = [
        wo
        for wo, _ in recent_orders  # just keep the WorkOrder objects
    ]

    return recent_orders


@dashboard_bp.route("/")
def dashboard():
    print("Dashboard route hit")

    try:
        recent_orders = get_recent_orders()

        print("Recent orders:", recent_orders)
        print("Number of recent orders:", len(recent_orders))

        total_recent = len(recent_orders)
        sail_orders_count = sum(1 for wo in recent_orders if wo.is_sail_order)
        rush_orders_count = sum(1 for wo in recent_orders if wo.RushOrder == "Y")

        return render_template(
            "dashboard.html",
            recent_work_orders=recent_orders,
            stats={
                "total_recent": total_recent,
                "sail_orders": sail_orders_count,
                "rush_orders": rush_orders_count,
            },
            last_updated=datetime.now().strftime("%H:%M"),
        )

    except Exception as e:
        db.session.rollback()
        print(f"Error fetching recent work orders: {e}")
        return render_template(
            "dashboard.html",
            recent_work_orders=[],
            stats={"total_recent": 0, "sail_orders": 0, "rush_orders": 0},
            error="Error loading recent work orders",
            last_updated=datetime.now().strftime("%H:%M"),
        )
