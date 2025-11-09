from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
)
from flask_login import login_required
from models.checkin import CheckIn, CheckInItem
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.inventory import Inventory
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from extensions import db
from datetime import datetime, date
from decorators import role_required

checkins_bp = Blueprint("checkins", __name__, url_prefix="/checkins")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _parse_date_field(date_str):
    """
    Parse a date string to a date object.
    Returns None if empty or invalid.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ============================================================================
# CHECK-IN ROUTES
# ============================================================================


@checkins_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create_checkin():
    """Create a new check-in"""
    if request.method == "POST":
        try:
            # Get form data
            cust_id = request.form.get("CustID")
            date_in = _parse_date_field(request.form.get("DateIn"))
            date_required = _parse_date_field(request.form.get("DateRequired"))

            if not cust_id:
                flash("Customer is required", "error")
                return redirect(url_for("checkins.create_checkin"))

            if not date_in:
                date_in = date.today()

            # Create check-in
            checkin = CheckIn(
                CustID=cust_id,
                DateIn=date_in,
                Status="pending",
                DateRequired=date_required,
                ReturnTo=request.form.get("ReturnTo"),
                StorageTime=request.form.get("StorageTime"),
                RackNo=request.form.get("RackNo"),
                SpecialInstructions=request.form.get("SpecialInstructions"),
                RepairsNeeded=bool(request.form.get("RepairsNeeded")),
                RushOrder=bool(request.form.get("RushOrder"))
            )

            db.session.add(checkin)
            db.session.flush()  # Get the CheckInID

            # Process check-in items
            descriptions = request.form.getlist("item_description[]")
            materials = request.form.getlist("item_material[]")
            colors = request.form.getlist("item_color[]")
            qtys = request.form.getlist("item_qty[]")
            sizewgts = request.form.getlist("item_sizewgt[]")
            prices = request.form.getlist("item_price[]")
            conditions = request.form.getlist("item_condition[]")

            for i in range(len(descriptions)):
                if descriptions[i]:  # Only add if description is not empty
                    item = CheckInItem(
                        CheckInID=checkin.CheckInID,
                        Description=descriptions[i],
                        Material=materials[i] if i < len(materials) else "Unknown",
                        Color=colors[i] if i < len(colors) else None,
                        Qty=int(qtys[i]) if i < len(qtys) and qtys[i] else 0,
                        SizeWgt=sizewgts[i] if i < len(sizewgts) else None,
                        Price=float(prices[i]) if i < len(prices) and prices[i] else None,
                        Condition=conditions[i] if i < len(conditions) else None,
                    )
                    db.session.add(item)

            db.session.commit()
            flash(f"Check-in #{checkin.CheckInID} created successfully!", "success")
            return redirect(url_for("checkins.view_pending"))

        except IntegrityError as e:
            db.session.rollback()
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("checkins.create_checkin"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating check-in: {str(e)}", "error")
            return redirect(url_for("checkins.create_checkin"))

    # GET request - show form
    customers = Customer.query.order_by(Customer.Name).all()
    return render_template(
        "checkins/new.html",
        customers=customers,
        today=date.today().strftime("%Y-%m-%d")
    )


@checkins_bp.route("/pending")
@login_required
@role_required("admin", "manager")
def view_pending():
    """View all pending check-ins"""
    pending_checkins = (
        CheckIn.query
        .filter_by(Status="pending")
        .order_by(CheckIn.DateIn.desc(), CheckIn.created_at.desc())
        .all()
    )
    return render_template("checkins/pending.html", checkins=pending_checkins)


@checkins_bp.route("/<int:checkin_id>")
@login_required
@role_required("admin", "manager")
def view_checkin(checkin_id):
    """View a specific check-in"""
    checkin = CheckIn.query.get_or_404(checkin_id)
    return render_template("checkins/detail.html", checkin=checkin)


@checkins_bp.route("/<int:checkin_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "manager")
def delete_checkin(checkin_id):
    """Delete a check-in"""
    try:
        checkin = CheckIn.query.get_or_404(checkin_id)

        if checkin.Status == "processed":
            flash("Cannot delete a processed check-in", "error")
            return redirect(url_for("checkins.view_pending"))

        db.session.delete(checkin)
        db.session.commit()
        flash(f"Check-in #{checkin_id} deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting check-in: {str(e)}", "error")

    return redirect(url_for("checkins.view_pending"))


@checkins_bp.route("/api/customer_search")
@login_required
@role_required("admin", "manager")
def customer_search():
    """Search customers for Selectize.js autocomplete"""
    query = request.args.get("q", "").lower()

    if not query or len(query) < 2:
        return jsonify([])

    # Search by name, contact, or CustID
    customers = (
        Customer.query
        .filter(
            func.lower(Customer.Name).contains(query) |
            func.lower(Customer.Contact).contains(query) |
            func.lower(Customer.CustID).contains(query)
        )
        .order_by(Customer.Name)
        .limit(20)
        .all()
    )

    results = [
        {
            "value": c.CustID,
            "name": c.Name or "",
            "contact": c.Contact or "",
            "source": c.source_info.SSource if c.source_info else (c.Source or ""),
            "text": f"{c.Name}{' - ' + c.Contact if c.Contact else ''}",
            "address": c.Address or "",
            "city": c.City or "",
            "state": c.State or "",
        }
        for c in customers
    ]

    return jsonify(results)


@checkins_bp.route("/api/pending_count")
@login_required
def get_pending_count():
    """Get count of pending check-ins for navigation badge"""
    count = CheckIn.query.filter_by(Status="pending").count()
    return jsonify({"count": count})
