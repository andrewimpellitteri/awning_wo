from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

# Commented out until models are recreated
# from models.tblCustomers import TblCustomer as Customer
# from models.tblCustWorkOrderDetail import Tblcustworkorderdetail as WorkOrder
# from models.tblCustAwngs import Tblcustawngs as InventoryItem
from extensions import db
from datetime import datetime

work_orders_bp = Blueprint("work_orders", __name__)


def parse_date_safe(date_str):
    """
    Safely parse a date string from the database or form.
    Returns a date object or None if invalid/empty.
    Supports formats like '12/31/22 00:00:00' and 'YYYY-MM-DD'.
    """
    if not date_str or date_str.strip() == "":
        return None
    for fmt in ("%m/%d/%y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


@work_orders_bp.route("/")
@login_required
def list_work_orders():
    """List all work orders - placeholder implementation"""
    # TODO: Implement when WorkOrder model is available
    flash("Work orders feature is currently unavailable", "info")
    return render_template(
        "placeholder.html",
        title="Work Orders",
        message="Work orders functionality will be available once models are restored.",
    )


@work_orders_bp.route("/new")
@work_orders_bp.route("/new/<int:customer_id>")
@login_required
def new_work_order(customer_id=None):
    """Create new work order form - placeholder implementation"""
    # TODO: Implement when Customer and WorkOrder models are available
    flash("New work order feature is currently unavailable", "info")
    return render_template(
        "placeholder.html",
        title="New Work Order",
        message="New work order functionality will be available once models are restored.",
    )


@work_orders_bp.route("/create", methods=["POST"])
@login_required
def create_work_order():
    """Create work order - placeholder implementation"""
    # TODO: Implement when WorkOrder model is available
    flash("Work order creation is currently unavailable", "warning")
    return redirect(url_for("work_orders.list_work_orders"))


@work_orders_bp.route("/<work_order_no>")
@login_required
def view_work_order(work_order_no):
    """View work order details - placeholder implementation"""
    # TODO: Implement when WorkOrder model is available
    flash(f"Cannot view work order {work_order_no} - feature unavailable", "info")
    return render_template(
        "placeholder.html",
        title=f"Work Order {work_order_no}",
        message="Work order viewing functionality will be available once models are restored.",
    )


# Additional placeholder routes that might be referenced elsewhere
@work_orders_bp.route("/edit/<work_order_no>")
@login_required
def edit_work_order(work_order_no):
    """Edit work order - placeholder implementation"""
    flash("Edit work order feature is currently unavailable", "info")
    return redirect(url_for("work_orders.list_work_orders"))


@work_orders_bp.route("/delete/<work_order_no>", methods=["POST"])
@login_required
def delete_work_order(work_order_no):
    """Delete work order - placeholder implementation"""
    flash("Delete work order feature is currently unavailable", "info")
    return redirect(url_for("work_orders.list_work_orders"))
