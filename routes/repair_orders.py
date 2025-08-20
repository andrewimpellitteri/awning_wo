from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.customer import Customer
from models.repair_order import RepairOrder, RepairOrderItem
from app import db
from datetime import datetime

repair_orders_bp = Blueprint('repair_orders', __name__)

@repair_orders_bp.route('/')
@login_required
def list_repair_orders():
    page = request.args.get('page', 1, type=int)
    repair_orders = RepairOrder.query.order_by(RepairOrder.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('repair_orders/list.html', repair_orders=repair_orders)

@repair_orders_bp.route('/new')
@repair_orders_bp.route('/new/<int:customer_id>')
@login_required
def new_repair_order(customer_id=None):
    customer = None
    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
    
    customers = Customer.query.all()
    return render_template('repair_orders/form.html', customer=customer, customers=customers)

@repair_orders_bp.route('/<int:id>')
@login_required
def view_repair_order(id):
    repair_order = RepairOrder.query.get_or_404(id)
    return render_template('repair_orders/view.html', repair_order=repair_order)
