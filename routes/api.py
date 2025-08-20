from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.customer import Customer
from models.work_order import WorkOrder
from models.repair_order import RepairOrder
from models.inventory import InventoryItem
from models.reference import Material, Color, Condition
from app import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/customers/search')
@login_required
def search_customers():
    query = request.args.get('q', '')
    customers = Customer.query.filter(
        Customer.name.contains(query)
    ).limit(20).all()
    
    return jsonify([customer.to_dict() for customer in customers])

@api_bp.route('/customers/<int:customer_id>/inventory')
@login_required
def get_customer_inventory(customer_id):
    inventory = InventoryItem.query.filter_by(customer_id=customer_id).all()
    return jsonify([item.to_dict() for item in inventory])

@api_bp.route('/reference/materials')
@login_required
def get_materials():
    materials = Material.query.all()
    return jsonify([{'id': m.id, 'name': m.name} for m in materials])

@api_bp.route('/reference/colors')
@login_required
def get_colors():
    colors = Color.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in colors])

@api_bp.route('/reference/conditions')
@login_required
def get_conditions():
    conditions = Condition.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in conditions])

@api_bp.route('/work-orders/<int:id>/items', methods=['POST'])
@login_required
def add_work_order_item(id):
    from models.work_order import WorkOrderItem
    
    work_order = WorkOrder.query.get_or_404(id)
    
    item = WorkOrderItem(
        work_order_id=work_order.id,
        customer_id=work_order.customer_id,
        qty=request.json.get('qty', 1),
        description=request.json.get('description'),
        material=request.json.get('material'),
        condition=request.json.get('condition'),
        color=request.json.get('color'),
        size_weight=request.json.get('size_weight'),
        price=request.json.get('price')
    )
    
    db.session.add(item)
    db.session.commit()
    
    return jsonify({'success': True, 'item_id': item.id})
