from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models.customer import Customer
from models.source import Source
from app import db

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/')
@login_required
def list_customers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Customer.query
    if search:
        query = query.filter(Customer.name.contains(search))
    
    customers = query.paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('customers/list.html', customers=customers, search=search)

@customers_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_customer():
    if request.method == 'POST':
        customer = Customer(
            name=request.form.get('name'),
            contact=request.form.get('contact'),
            address=request.form.get('address'),
            address2=request.form.get('address2'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            zip_code=request.form.get('zip_code'),
            home_phone=request.form.get('home_phone'),
            work_phone=request.form.get('work_phone'),
            cell_phone=request.form.get('cell_phone'),
            email_address=request.form.get('email_address')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash('Customer created successfully!', 'success')
        return redirect(url_for('customers.view_customer', id=customer.id))
    
    sources = Source.query.all()
    return render_template('customers/form.html', sources=sources)

@customers_bp.route('/<int:id>')
@login_required
def view_customer(id):
    customer = Customer.query.get_or_404(id)
    work_orders = customer.work_orders.limit(10).all()
    repair_orders = customer.repair_orders.limit(10).all()
    inventory_items = customer.inventory_items.limit(20).all()
    
    return render_template('customers/view.html', 
                         customer=customer,
                         work_orders=work_orders,
                         repair_orders=repair_orders,
                         inventory_items=inventory_items)

@customers_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.contact = request.form.get('contact')
        customer.address = request.form.get('address')
        customer.address2 = request.form.get('address2')
        customer.city = request.form.get('city')
        customer.state = request.form.get('state')
        customer.zip_code = request.form.get('zip_code')
        customer.home_phone = request.form.get('home_phone')
        customer.work_phone = request.form.get('work_phone')
        customer.cell_phone = request.form.get('cell_phone')
        customer.email_address = request.form.get('email_address')
        
        db.session.commit()
        
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('customers.view_customer', id=customer.id))
    
    sources = Source.query.all()
    return render_template('customers/form.html', customer=customer, sources=sources)
