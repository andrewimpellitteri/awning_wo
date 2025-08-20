from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.inventory import InventoryItem
from app import db
from datetime import datetime

work_orders_bp = Blueprint('work_orders', __name__)

@work_orders_bp.route('/')
@login_required
def list_work_orders():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = WorkOrder.query
    if status:
        query = query.filter(WorkOrder.return_status == status)
    
    work_orders = query.order_by(WorkOrder.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('work_orders/list.html', work_orders=work_orders, status=status)

@work_orders_bp.route('/new')
@work_orders_bp.route('/new/<int:customer_id>')
@login_required
def new_work_order(customer_id=None):
    customer = None
    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
    
    customers = Customer.query.all()
    return render_template('work_orders/form.html', customer=customer, customers=customers)

@work_orders_bp.route('/create', methods=['POST'])
@login_required
def create_work_order():
    # Generate work order number
    last_wo = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    wo_number = f"WO{(last_wo.id + 1) if last_wo else 1:06d}"
    
    work_order = WorkOrder(
        work_order_no=wo_number,
        customer_id=request.form.get('customer_id'),
        wo_name=request.form.get('wo_name'),
        date_in=datetime.strptime(request.form.get('date_in'), '%Y-%m-%d').date() if request.form.get('date_in') else None,
        date_required=datetime.strptime(request.form.get('date_required'), '%Y-%m-%d').date() if request.form.get('date_required') else None,
        special_instructions=request.form.get('special_instructions'),
        clean=bool(request.form.get('clean')),
        treat=bool(request.form.get('treat')),
        rush_order=bool(request.form.get('rush_order')),
        quote=request.form.get('quote') if request.form.get('quote') else None
    )
    
    db.session.add(work_order)
    db.session.commit()
    
    flash('Work order created successfully!', 'success')
    return redirect(url_for('work_orders.view_work_order', id=work_order.id))

@work_orders_bp.route('/<int:id>')
@login_required
def view_work_order(id):
    work_order = WorkOrder.query.get_or_404(id)
    return render_template('work_orders/view.html', work_order=work_order)
