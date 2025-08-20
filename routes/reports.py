from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models.work_order import WorkOrder
from models.repair_order import RepairOrder
from models.customer import Customer
from sqlalchemy import func
from datetime import datetime, timedelta

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
@login_required
def reports_dashboard():
    return render_template('reports/dashboard.html')

@reports_bp.route('/incomplete')
@login_required
def incomplete_orders():
    incomplete_work_orders = WorkOrder.query.filter(
        WorkOrder.date_completed.is_(None)
    ).all()
    
    return render_template('reports/incomplete.html', work_orders=incomplete_work_orders)

@reports_bp.route('/completed')
@login_required
def completed_orders():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = WorkOrder.query.filter(WorkOrder.date_completed.isnot(None))
    
    if start_date:
        query = query.filter(WorkOrder.date_completed >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(WorkOrder.date_completed <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    completed_orders = query.all()
    
    return render_template('reports/completed.html', 
                         work_orders=completed_orders,
                         start_date=start_date,
                         end_date=end_date)

@reports_bp.route('/summary')
@login_required
def summary_report():
    # Get counts for dashboard
    total_customers = Customer.query.count()
    active_work_orders = WorkOrder.query.filter(WorkOrder.date_completed.is_(None)).count()
    active_repair_orders = RepairOrder.query.filter(RepairOrder.date_completed.is_(None)).count()
    
    # Recent completed orders
    recent_completed = WorkOrder.query.filter(
        WorkOrder.date_completed >= (datetime.now().date() - timedelta(days=30))
    ).count()
    
    stats = {
        'total_customers': total_customers,
        'active_work_orders': active_work_orders,
        'active_repair_orders': active_repair_orders,
        'recent_completed': recent_completed
    }
    
    return render_template('reports/summary.html', stats=stats)
