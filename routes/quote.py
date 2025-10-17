from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from decorators import role_required
from models.work_order import WorkOrder
from models.customer import Customer
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from extensions import db

quote_bp = Blueprint("quote", __name__, url_prefix="/quotes")


@quote_bp.route("/")
@login_required
@role_required("admin", "manager")
def list_quotes():
    """Display list of work orders where Quote is not 'Approved'"""
    return render_template("quotes/list.html")


@quote_bp.route("/data")
@login_required
@role_required("admin", "manager")
def quotes_data():
    """API endpoint for quote work orders data (Tabulator)"""
    # Get work orders where Quote is not 'Approved' and not completed
    query = WorkOrder.query.filter(
        and_(
            # Quote is not 'Approved'
            or_(
                WorkOrder.Quote.is_(None),
                WorkOrder.Quote == '',
                and_(WorkOrder.Quote.isnot(None), WorkOrder.Quote != 'Approved')
            ),
            # Work order is not completed
            WorkOrder.DateCompleted.is_(None)
        )
    ).options(joinedload(WorkOrder.customer).joinedload(Customer.source_info))

    # Apply ordering
    work_orders = query.order_by(WorkOrder.DateIn.desc()).all()

    # Convert to JSON format for Tabulator
    data = []
    for wo in work_orders:
        data.append({
            'WorkOrderNo': wo.WorkOrderNo,
            'CustID': wo.CustID,
            'WOName': wo.WOName,
            'Quote': wo.Quote or '',
            'DateIn': wo.DateIn.strftime('%Y-%m-%d') if wo.DateIn else '',
            'DateRequired': wo.DateRequired.strftime('%Y-%m-%d') if wo.DateRequired else '',
            'RushOrder': wo.RushOrder,
            'source': wo.customer.source_info.SSource if wo.customer and wo.customer.source_info else '',
            'customer_name': wo.customer.Name if wo.customer else '',
        })

    return jsonify(data)


@quote_bp.route("/create")
@login_required
@role_required("admin", "manager")
def create_quote():
    """Create a new quote - placeholder for future implementation"""
    return render_template("quotes/create.html")
