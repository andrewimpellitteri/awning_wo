#!/bin/bash

# Awning Management System Setup Script
# This script creates the complete Flask application structure

set -e  # Exit on any error

mkdir -p {models,routes,templates,static/{css,js,images},utils,migrations,data,uploads/photos}

# Create main application files
echo "📄 Creating main application files..."

# requirements.txt
cat > requirements.txt << 'EOF'
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.3
Flask-WTF==1.1.1
WTForms==3.0.1
pandas==2.1.1
python-dotenv==1.0.0
Werkzeug==2.3.7
Jinja2==3.1.2
psycopg2-binary==2.9.7
gunicorn==21.2.0
Pillow==10.0.1
EOF

# .env file
cat > .env << 'EOF'
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-change-this-in-production
DATABASE_URL=sqlite:///awning_management.db
UPLOAD_FOLDER=uploads
CSV_DATA_PATH=data
EOF

# .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Application specific
uploads/
data/*.csv
*.db
EOF

# config.py
cat > config.py << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///awning_management.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    CSV_DATA_PATH = os.environ.get('CSV_DATA_PATH') or 'data'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Pagination
    ITEMS_PER_PAGE = 50
    
    # Photo settings
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EOF

# app.py
cat > app.py << 'EOF'
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from config import Config
import os

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Import models (after db initialization)
from models import *

# Import routes
from routes.auth import auth_bp
from routes.customers import customers_bp
from routes.work_orders import work_orders_bp
from routes.repair_orders import repair_orders_bp
from routes.reports import reports_bp
from routes.api import api_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(customers_bp, url_prefix='/customers')
app.register_blueprint(work_orders_bp, url_prefix='/work-orders')
app.register_blueprint(repair_orders_bp, url_prefix='/repair-orders')
app.register_blueprint(reports_bp, url_prefix='/reports')
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/')
@login_required
def dashboard():
    """Main dashboard view"""
    return render_template('dashboard.html')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
EOF

# Models
echo "🗃️  Creating model files..."

# models/__init__.py
cat > models/__init__.py << 'EOF'
from .user import User
from .customer import Customer
from .source import Source
from .work_order import WorkOrder
from .repair_order import RepairOrder
from .inventory import InventoryItem
from .progress import ProgressTracking
from .photo import Photo
from .reference import Material, Color, Condition

__all__ = [
    'User', 'Customer', 'Source', 'WorkOrder', 'RepairOrder', 
    'InventoryItem', 'ProgressTracking', 'Photo', 
    'Material', 'Color', 'Condition'
]
EOF

# models/user.py
cat > models/user.py << 'EOF'
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<User {self.username}>'
EOF

# models/customer.py
cat > models/customer.py << 'EOF'
from app import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)  # CustID
    name = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(100))
    address = db.Column(db.String(255))
    address2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    home_phone = db.Column(db.String(20))
    work_phone = db.Column(db.String(20))
    cell_phone = db.Column(db.String(20))
    email_address = db.Column(db.String(150))
    
    # Mailing address
    mail_address = db.Column(db.String(255))
    mail_city = db.Column(db.String(100))
    mail_state = db.Column(db.String(50))
    mail_zip = db.Column(db.String(20))
    
    # Source information
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'))
    source = db.relationship('Source', backref='customers')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    work_orders = db.relationship('WorkOrder', backref='customer', lazy='dynamic')
    repair_orders = db.relationship('RepairOrder', backref='customer', lazy='dynamic')
    inventory_items = db.relationship('InventoryItem', backref='customer', lazy='dynamic')
    photos = db.relationship('Photo', backref='customer', lazy='dynamic')
    
    def __repr__(self):
        return f'<Customer {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact': self.contact,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'email_address': self.email_address,
            'phone': self.home_phone or self.work_phone or self.cell_phone
        }
EOF

# models/source.py
cat > models/source.py << 'EOF'
from app import db
from datetime import datetime

class Source(db.Model):
    __tablename__ = 'sources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # SSource
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    fax = db.Column(db.String(20))
    email = db.Column(db.String(150))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Source {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'phone': self.phone,
            'email': self.email
        }
EOF

# models/work_order.py
cat > models/work_order.py << 'EOF'
from app import db
from datetime import datetime

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    wo_name = db.Column(db.String(200))
    
    # Storage and handling
    storage = db.Column(db.String(100))
    storage_time = db.Column(db.String(50))
    rack_number = db.Column(db.String(20))
    
    # Instructions and requirements
    special_instructions = db.Column(db.Text)
    repairs_needed = db.Column(db.Text)
    see_repair = db.Column(db.Boolean, default=False)
    
    # Status and timing
    return_status = db.Column(db.String(50))
    date_completed = db.Column(db.Date)
    date_in = db.Column(db.Date)
    date_required = db.Column(db.Date)
    
    # Services
    quote = db.Column(db.Numeric(10, 2))
    clean = db.Column(db.Boolean, default=False)
    treat = db.Column(db.Boolean, default=False)
    rush_order = db.Column(db.Boolean, default=False)
    firm_rush = db.Column(db.Boolean, default=False)
    clean_first_wo = db.Column(db.Boolean, default=False)
    
    # Shipping
    ship_to = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('WorkOrderItem', backref='work_order', lazy='dynamic', cascade='all, delete-orphan')
    progress_records = db.relationship('ProgressTracking', backref='work_order', lazy='dynamic')
    
    def __repr__(self):
        return f'<WorkOrder {self.work_order_no}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'work_order_no': self.work_order_no,
            'customer_id': self.customer_id,
            'wo_name': self.wo_name,
            'date_in': self.date_in.isoformat() if self.date_in else None,
            'date_required': self.date_required.isoformat() if self.date_required else None,
            'rush_order': self.rush_order,
            'quote': float(self.quote) if self.quote else None,
            'return_status': self.return_status
        }

class WorkOrderItem(db.Model):
    __tablename__ = 'work_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    qty = db.Column(db.Integer, default=1)
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    
    def __repr__(self):
        return f'<WorkOrderItem {self.description}>'
EOF

# models/repair_order.py
cat > models/repair_order.py << 'EOF'
from app import db
from datetime import datetime

class RepairOrder(db.Model):
    __tablename__ = 'repair_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    repair_order_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    ro_name = db.Column(db.String(200))
    
    # Source and dates
    source = db.Column(db.String(200))
    wo_date = db.Column(db.Date)
    date_to_sub = db.Column(db.Date)
    date_required = db.Column(db.Date)
    date_in = db.Column(db.Date)
    date_completed = db.Column(db.Date)
    date_out = db.Column(db.Date)
    return_date = db.Column(db.Date)
    
    # Order details
    rush_order = db.Column(db.Boolean, default=False)
    firm_rush = db.Column(db.Boolean, default=False)
    quote = db.Column(db.Numeric(10, 2))
    quote_by = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    
    # Storage and location
    rack_number = db.Column(db.String(20))
    storage = db.Column(db.String(100))
    location = db.Column(db.String(100))
    
    # Repair details
    item_type = db.Column(db.String(100))
    type_of_repair = db.Column(db.String(200))
    special_instructions = db.Column(db.Text)
    repairs_done_by = db.Column(db.String(100))
    material_list = db.Column(db.Text)
    customer_price = db.Column(db.Numeric(10, 2))
    
    # Services
    clean = db.Column(db.Boolean, default=False)
    see_clean = db.Column(db.Boolean, default=False)
    clean_first = db.Column(db.Boolean, default=False)
    
    # Status
    return_status = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('RepairOrderItem', backref='repair_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<RepairOrder {self.repair_order_no}>'

class RepairOrderItem(db.Model):
    __tablename__ = 'repair_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    qty = db.Column(db.Integer, default=1)
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    
    def __repr__(self):
        return f'<RepairOrderItem {self.description}>'
EOF

# models/inventory.py
cat > models/inventory.py << 'EOF'
from app import db
from datetime import datetime

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    qty = db.Column(db.Integer, default=1)
    inventory_key = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventoryItem {self.description}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'description': self.description,
            'material': self.material,
            'condition': self.condition,
            'color': self.color,
            'size_weight': self.size_weight,
            'price': float(self.price) if self.price else None,
            'qty': self.qty
        }
EOF

# models/progress.py
cat > models/progress.py << 'EOF'
from app import db
from datetime import datetime

class ProgressTracking(db.Model):
    __tablename__ = 'progress_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'))
    
    # Progress details
    pgrs_work_order_no = db.Column(db.String(50))
    pgrs_name = db.Column(db.String(200))
    pgrs_date_in = db.Column(db.Date)
    pgrs_date_updated = db.Column(db.Date)
    pgrs_source = db.Column(db.String(200))
    
    # Work order progress
    wo_quote = db.Column(db.Numeric(10, 2))
    on_deck_clean = db.Column(db.Boolean, default=False)
    tub = db.Column(db.Boolean, default=False)
    clean = db.Column(db.Boolean, default=False)
    treat = db.Column(db.Boolean, default=False)
    wrap_clean = db.Column(db.Boolean, default=False)
    notes_clean = db.Column(db.Text)
    
    # Repair order progress
    pgrs_repair_order_no = db.Column(db.String(50))
    repair_quote = db.Column(db.Numeric(10, 2))
    on_deck_repair = db.Column(db.Boolean, default=False)
    in_process = db.Column(db.Boolean, default=False)
    wrap_repair = db.Column(db.Boolean, default=False)
    repair_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProgressTracking {self.pgrs_work_order_no}>'
EOF

# models/photo.py
cat > models/photo.py << 'EOF'
from app import db
from datetime import datetime

class Photo(db.Model):
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))  # Local file path
    photo_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Photo {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'photo_date': self.photo_date.isoformat() if self.photo_date else None,
            'notes': self.notes,
            'file_size': self.file_size
        }
EOF

# models/reference.py
cat > models/reference.py << 'EOF'
from app import db

class Material(db.Model):
    __tablename__ = 'materials'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<Material {self.name}>'

class Color(db.Model):
    __tablename__ = 'colors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<Color {self.name}>'

class Condition(db.Model):
    __tablename__ = 'conditions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<Condition {self.name}>'
EOF

# Routes
echo "🛣️  Creating route files..."

# routes/__init__.py
touch routes/__init__.py

# routes/auth.py
cat > routes/auth.py << 'EOF'
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models.user import User
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.register'))
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')
EOF

# routes/customers.py
cat > routes/customers.py << 'EOF'
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
EOF

# routes/work_orders.py
cat > routes/work_orders.py << 'EOF'
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
EOF

# routes/repair_orders.py
cat > routes/repair_orders.py << 'EOF'
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
EOF

# routes/reports.py
cat > routes/reports.py << 'EOF'
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
EOF

# routes/api.py
cat > routes/api.py << 'EOF'
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
EOF

# Templates
echo "📄 Creating template files..."

# templates/base.html
cat > templates/base.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Awning Management System{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <!-- Navigation -->
    {% if current_user.is_authenticated %}
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                <i class="fas fa-umbrella"></i> Awning Management
            </a>
            
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('dashboard') }}">Dashboard</a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            Work Orders
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('work_orders.new_work_order') }}">New Work Order</a></li>
                            <li><a class="dropdown-item" href="{{ url_for('work_orders.list_work_orders') }}">Search Work Orders</a></li>
                        </ul>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            Repair Orders
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('repair_orders.new_repair_order') }}">New Repair Order</a></li>
                            <li><a class="dropdown-item" href="{{ url_for('repair_orders.list_repair_orders') }}">Search Repair Orders</a></li>
                        </ul>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            Customers
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('customers.new_customer') }}">New Customer</a></li>
                            <li><a class="dropdown-item" href="{{ url_for('customers.list_customers') }}">Search Customers</a></li>
                        </ul>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            Reports
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('reports.incomplete_orders') }}">Incomplete Orders</a></li>
                            <li><a class="dropdown-item" href="{{ url_for('reports.completed_orders') }}">Completed Orders</a></li>
                            <li><a class="dropdown-item" href="{{ url_for('reports.summary_report') }}">Summary Report</a></li>
                        </ul>
                    </li>
                </ul>
                
                <ul class="navbar-nav">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user"></i> {{ current_user.username }}
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">Logout</a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    {% endif %}

    <!-- Flash Messages -->
    <div class="container-fluid mt-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <!-- Main Content -->
    <div class="container-fluid">
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
EOF

# templates/dashboard.html
cat > templates/dashboard.html << 'EOF'
{% extends "base.html" %}

{% block title %}Dashboard - Awning Management{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <h1>Dashboard</h1>
        <p class="lead">Welcome to the Awning Management System</p>
    </div>
</div>

<div class="row">
    <!-- Quick Actions -->
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Quick Actions</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="{{ url_for('work_orders.new_work_order') }}" class="btn btn-primary">
                        <i class="fas fa-plus"></i> New Work Order
                    </a>
                    <a href="{{ url_for('repair_orders.new_repair_order') }}" class="btn btn-warning">
                        <i class="fas fa-tools"></i> New Repair Order
                    </a>
                    <a href="{{ url_for('customers.new_customer') }}" class="btn btn-success">
                        <i class="fas fa-user-plus"></i> New Customer
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- Recent Activity -->
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">System Status</h5>
            </div>
            <div class="card-body">
                <div class="row text-center">
                    <div class="col-4">
                        <h3 class="text-primary">-</h3>
                        <small>Active Work Orders</small>
                    </div>
                    <div class="col-4">
                        <h3 class="text-warning">-</h3>
                        <small>Active Repairs</small>
                    </div>
                    <div class="col-4">
                        <h3 class="text-success">-</h3>
                        <small>Total Customers</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Recent Orders</h5>
            </div>
            <div class="card-body">
                <p class="text-muted">Recent order activity will appear here...</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# Create auth templates directory and login template
mkdir -p templates/auth

cat > templates/auth/login.html << 'EOF'
{% extends "base.html" %}

{% block title %}Login - Awning Management{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6 col-lg-4">
        <div class="card">
            <div class="card-header text-center">
                <h4><i class="fas fa-umbrella"></i> Awning Management</h4>
                <p class="text-muted">Please sign in to continue</p>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">Username</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Sign In</button>
                    </div>
                </form>
            </div>
            <div class="card-footer text-center">
                <small class="text-muted">
                    Need an account? <a href="{{ url_for('auth.register') }}">Register here</a>
                </small>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

cat > templates/auth/register.html << 'EOF'
{% extends "base.html" %}

{% block title %}Register - Awning Management{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6 col-lg-4">
        <div class="card">
            <div class="card-header text-center">
                <h4>Create Account</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">Username</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="email" class="form-label">Email</label>
                        <input type="email" class="form-control" id="email" name="email" required>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-success">Register</button>
                    </div>
                </form>
            </div>
            <div class="card-footer text-center">
                <small class="text-muted">
                    Already have an account? <a href="{{ url_for('auth.login') }}">Sign in here</a>
                </small>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# Create other template directories
mkdir -p templates/{customers,work_orders,repair_orders,reports}

# Basic customer list template
cat > templates/customers/list.html << 'EOF'
{% extends "base.html" %}

{% block title %}Customers - Awning Management{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1>Customers</h1>
    <a href="{{ url_for('customers.new_customer') }}" class="btn btn-primary">
        <i class="fas fa-plus"></i> New Customer
    </a>
</div>

<div class="card">
    <div class="card-body">
        <!-- Search Form -->
        <form method="GET" class="mb-3">
            <div class="row">
                <div class="col-md-8">
                    <input type="text" class="form-control" name="search" 
                           placeholder="Search customers..." value="{{ search }}">
                </div>
                <div class="col-md-4">
                    <button type="submit" class="btn btn-outline-primary">Search</button>
                    <a href="{{ url_for('customers.list_customers') }}" class="btn btn-outline-secondary">Clear</a>
                </div>
            </div>
        </form>

        <!-- Customer Table -->
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Contact</th>
                        <th>City, State</th>
                        <th>Phone</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for customer in customers.items %}
                    <tr>
                        <td>{{ customer.id }}</td>
                        <td>
                            <a href="{{ url_for('customers.view_customer', id=customer.id) }}">
                                {{ customer.name }}
                            </a>
                        </td>
                        <td>{{ customer.contact or '-' }}</td>
                        <td>{{ customer.city }}{% if customer.city and customer.state %}, {% endif %}{{ customer.state }}</td>
                        <td>{{ customer.home_phone or customer.work_phone or customer.cell_phone or '-' }}</td>
                        <td>
                            <a href="{{ url_for('customers.view_customer', id=customer.id) }}" 
                               class="btn btn-sm btn-outline-primary">View</a>
                            <a href="{{ url_for('customers.edit_customer', id=customer.id) }}" 
                               class="btn btn-sm btn-outline-secondary">Edit</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        {% if customers.pages > 1 %}
        <nav aria-label="Page navigation">
            <ul class="pagination">
                {% if customers.has_prev %}
                <li class="page-item">
                    <a class="page-link" href="{{ url_for('customers.list_customers', page=customers.prev_num, search=search) }}">Previous</a>
                </li>
                {% endif %}
                
                {% for page in customers.iter_pages() %}
                    {% if page %}
                        {% if page != customers.page %}
                        <li class="page-item">
                            <a class="page-link" href="{{ url_for('customers.list_customers', page=page, search=search) }}">{{ page }}</a>
                        </li>
                        {% else %}
                        <li class="page-item active">
                            <span class="page-link">{{ page }}</span>
                        </li>
                        {% endif %}
                    {% else %}
                    <li class="page-item disabled">
                        <span class="page-link">...</span>
                    </li>
                    {% endif %}
                {% endfor %}
                
                {% if customers.has_next %}
                <li class="page-item">
                    <a class="page-link" href="{{ url_for('customers.list_customers', page=customers.next_num, search=search) }}">Next</a>
                </li>
                {% endif %}
            </ul>
        </nav>
        {% endif %}
    </div>
</div>
{% endblock %}
EOF

# Static files
echo "🎨 Creating static files..."

# static/css/style.css
cat > static/css/style.css << 'EOF'
/* Custom styles for Awning Management System */

body {
    background-color: #f8f9fa;
}

.navbar-brand {
    font-weight: bold;
}

.card {
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    border: 1px solid rgba(0, 0, 0, 0.125);
}

.card-header {
    background-color: #fff;
    border-bottom: 1px solid rgba(0, 0, 0, 0.125);
}

.table th {
    border-top: none;
    font-weight: 600;
    color: #495057;
}

.btn {
    border-radius: 0.375rem;
}

.alert {
    border-radius: 0.5rem;
}

/* Dashboard specific styles */
.dashboard-card {
    transition: transform 0.2s;
}

.dashboard-card:hover {
    transform: translateY(-2px);
}

/* Form styles */
.form-label {
    font-weight: 500;
}

.form-control:focus {
    border-color: #80bdff;
    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

/* Table styles */
.table-responsive {
    border-radius: 0.5rem;
}

/* Loading spinner */
.spinner-border-sm {
    width: 1rem;
    height: 1rem;
}

/* Custom utilities */
.text-truncate {
    max-width: 200px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .container-fluid {
        padding-left: 15px;
        padding-right: 15px;
    }
    
    .table-responsive {
        font-size: 0.875rem;
    }
}
EOF

# static/js/app.js
cat > static/js/app.js << 'EOF'
// Main JavaScript for Awning Management System

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Utility functions
const Utils = {
    // Format currency
    formatCurrency: function(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    },

    // Format date
    formatDate: function(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleDateString();
    },

    // Show loading spinner
    showLoading: function(element) {
        element.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Loading...';
        element.disabled = true;
    },

    // Hide loading spinner
    hideLoading: function(element, originalText) {
        element.innerHTML = originalText;
        element.disabled = false;
    },

    // Show toast notification
    showToast: function(message, type = 'info') {
        // Create toast element if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl);
        toast.show();

        // Remove toast element after it's hidden
        toastEl.addEventListener('hidden.bs.toast', function () {
            toastEl.remove();
        });
    }
};

// Customer search functionality
function searchCustomers(query) {
    if (query.length < 2) return;
    
    fetch(`/api/customers/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            // Handle customer search results
            console.log('Customer search results:', data);
        })
        .catch(error => {
            console.error('Error searching customers:', error);
        });
}

// Work order management
const WorkOrder = {
    addItem: function(workOrderId, itemData) {
        fetch(`/api/work-orders/${workOrderId}/items`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(itemData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                Utils.showToast('Item added successfully', 'success');
                // Refresh items list
                location.reload();
            } else {
                Utils.showToast('Error adding item', 'danger');
            }
        })
        .catch(error => {
            console.error('Error adding item:', error);
            Utils.showToast('Error adding item', 'danger');
        });
    }
};

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;

    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });

    return isValid;
}

// Export functionality
const Export = {
    toCSV: function(data, filename) {
        const csv = this.convertToCSV(data);
        this.downloadCSV(csv, filename);
    },

    convertToCSV: function(data) {
        if (!data || data.length === 0) return '';

        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => 
                headers.map(header => 
                    JSON.stringify(row[header] || '')
                ).join(',')
            )
        ].join('\n');

        return csvContent;
    },

    downloadCSV: function(csv, filename) {
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', filename);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
};
EOF

# Utils directory
echo "🔧 Creating utility files..."

# utils/__init__.py
touch utils/__init__.py

# utils/csv_handler.py
cat > utils/csv_handler.py << 'EOF'
import pandas as pd
import os
from flask import current_app
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.repair_order import RepairOrder, RepairOrderItem
from models.inventory import InventoryItem
from models.source import Source
from models.reference import Material, Color, Condition
from models.progress import ProgressTracking
from models.photo import Photo
from app import db

class CSVHandler:
    """Handle CSV import/export operations"""
    
    def __init__(self):
        self.csv_path = current_app.config.get('CSV_DATA_PATH', 'data')
    
    def import_all_csvs(self):
        """Import all CSV files from the data directory"""
        try:
            # Import reference data first
            self.import_reference_data()
            
            # Import main data
            self.import_sources()
            self.import_customers()
            self.import_inventory()
            self.import_work_orders()
            self.import_repair_orders()
            self.import_progress()
            self.import_photos()
            
            db.session.commit()
            return True, "All CSV files imported successfully"
        
        except Exception as e:
            db.session.rollback()
            return False, f"Error importing CSV files: {str(e)}"
    
    def import_reference_data(self):
        """Import materials, colors, and conditions"""
        # Materials
        materials_file = os.path.join(self.csv_path, 'tblMaterial.csv')
        if os.path.exists(materials_file):
            df = pd.read_csv(materials_file)
            for _, row in df.iterrows():
                if not Material.query.filter_by(name=row['Material']).first():
                    material = Material(name=row['Material'])
                    db.session.add(material)
        
        # Colors
        colors_file = os.path.join(self.csv_path, 'tblColor.csv')
        if os.path.exists(colors_file):
            df = pd.read_csv(colors_file)
            for _, row in df.iterrows():
                if not Color.query.filter_by(name=row['Color']).first():
                    color = Color(name=row['Color'])
                    db.session.add(color)
        
        # Conditions
        conditions_file = os.path.join(self.csv_path, 'tblCondition.csv')
        if os.path.exists(conditions_file):
            df = pd.read_csv(conditions_file)
            for _, row in df.iterrows():
                if not Condition.query.filter_by(name=row['Condition']).first():
                    condition = Condition(name=row['Condition'])
                    db.session.add(condition)
    
    def import_sources(self):
        """Import source companies"""
        sources_file = os.path.join(self.csv_path, 'tblSource.csv')
        if not os.path.exists(sources_file):
            return
        
        df = pd.read_csv(sources_file)
        for _, row in df.iterrows():
            if not Source.query.filter_by(name=row.get('SSource', '')).first():
                source = Source(
                    name=row.get('SSource', ''),
                    address=row.get('SourceAddress', ''),
                    city=row.get('SourceCity', ''),
                    state=row.get('SourceState', ''),
                    zip_code=row.get('SourceZip', ''),
                    phone=row.get('SourcePhone', ''),
                    fax=row.get('SourceFax', ''),
                    email=row.get('SourceEmail', '')
                )
                db.session.add(source)
    
    def import_customers(self):
        """Import customers"""
        customers_file = os.path.join(self.csv_path, 'tblCustomers.csv')
        if not os.path.exists(customers_file):
            return
        
        df = pd.read_csv(customers_file)
        for _, row in df.iterrows():
            if not Customer.query.filter_by(id=row.get('CustID')).first():
                # Find source if exists
                source = None
                if row.get('Source'):
                    source = Source.query.filter_by(name=row.get('Source')).first()
                
                customer = Customer(
                    id=row.get('CustID'),
                    name=row.get('Name', ''),
                    contact=row.get('Contact', ''),
                    address=row.get('Address', ''),
                    address2=row.get('Address2', ''),
                    city=row.get('City', ''),
                    state=row.get('State', ''),
                    zip_code=row.get('ZipCode', ''),
                    home_phone=row.get('HomePhone', ''),
                    work_phone=row.get('WorkPhone', ''),
                    cell_phone=row.get('CellPhone', ''),
                    email_address=row.get('EmailAddress', ''),
                    mail_address=row.get('MailAddress', ''),
                    mail_city=row.get('MailCity', ''),
                    mail_state=row.get('MailState', ''),
                    mail_zip=row.get('MailZip', ''),
                    source_id=source.id if source else None
                )
                db.session.add(customer)
    
    def import_inventory(self):
        """Import customer inventory"""
        inventory_file = os.path.join(self.csv_path, 'tblCustAwngs.csv')
        if not os.path.exists(inventory_file):
            return
        
        df = pd.read_csv(inventory_file)
        for _, row in df.iterrows():
            inventory_item = InventoryItem(
                customer_id=row.get('CustID'),
                description=row.get('Description', ''),
                material=row.get('Material', ''),
                condition=row.get('Condition', ''),
                color=row.get('Color', ''),
                size_weight=row.get('SizeWgt', ''),
                price=row.get('Price'),
                qty=row.get('Qty', 1),
                inventory_key=row.get('InventoryKey', '')
            )
            db.session.add(inventory_item)
    
    def import_work_orders(self):
        """Import work orders"""
        wo_file = os.path.join(self.csv_path, 'tblCustWorkOrderDetail.csv')
        if not os.path.exists(wo_file):
            return
        
        df = pd.read_csv(wo_file)
        for _, row in df.iterrows():
            if not WorkOrder.query.filter_by(work_order_no=row.get('WorkOrderNo')).first():
                work_order = WorkOrder(
                    work_order_no=row.get('WorkOrderNo', ''),
                    customer_id=row.get('CustID'),
                    wo_name=row.get('WOName', ''),
                    storage=row.get('Storage', ''),
                    storage_time=row.get('StorageTime', ''),
                    rack_number=row.get('Rack#', ''),
                    special_instructions=row.get('SpecialInstructions', ''),
                    repairs_needed=row.get('RepairsNeeded', ''),
                    see_repair=bool(row.get('SeeRepair')),
                    return_status=row.get('ReturnStatus', ''),
                    date_completed=pd.to_datetime(row.get('DateCompleted'), errors='coerce'),
                    date_in=pd.to_datetime(row.get('DateIn'), errors='coerce'),
                    date_required=pd.to_datetime(row.get('DateRequired'), errors='coerce'),
                    quote=row.get('Quote'),
                    clean=bool(row.get('Clean')),
                    treat=bool(row.get('Treat')),
                    rush_order=bool(row.get('RushOrder')),
                    firm_rush=bool(row.get('FirmRush')),
                    clean_first_wo=bool(row.get('CleanFirstWO')),
                    ship_to=row.get('ShipTo', '')
                )
                db.session.add(work_order)
        
        # Import work order items
        wo_items_file = os.path.join(self.csv_path, 'tblOrdDetCustAwngs.csv')
        if os.path.exists(wo_items_file):
            df = pd.read_csv(wo_items_file)
            for _, row in df.iterrows():
                work_order = WorkOrder.query.filter_by(work_order_no=row.get('WorkOrderNo')).first()
                if work_order:
                    wo_item = WorkOrderItem(
                        work_order_id=work_order.id,
                        customer_id=row.get('CustID'),
                        qty=row.get('Qty', 1),
                        description=row.get('Description', ''),
                        material=row.get('Material', ''),
                        condition=row.get('Condition', ''),
                        color=row.get('Color', ''),
                        size_weight=row.get('SizeWgt', ''),
                        price=row.get('Price')
                    )
                    db.session.add(wo_item)
    
    def import_repair_orders(self):
        """Import repair orders"""
        ro_file = os.path.join(self.csv_path, 'tblRepairWorkOrderDetail.csv')
        if not os.path.exists(ro_file):
            return
        
        df = pd.read_csv(ro_file)
        for _, row in df.iterrows():
            if not RepairOrder.query.filter_by(repair_order_no=row.get('RepairOrderNo')).first():
                repair_order = RepairOrder(
                    repair_order_no=row.get('RepairOrderNo', ''),
                    customer_id=row.get('CustID'),
                    ro_name=row.get('ROName', ''),
                    source=row.get('SOURCE', ''),
                    wo_date=pd.to_datetime(row.get('WO DATE'), errors='coerce'),
                    date_to_sub=pd.to_datetime(row.get('DATE TO SUB'), errors='coerce'),
                    date_required=pd.to_datetime(row.get('DateRequired'), errors='coerce'),
                    date_in=pd.to_datetime(row.get('DateIn'), errors='coerce'),
                    date_completed=pd.to_datetime(row.get('DateCompleted'), errors='coerce'),
                    date_out=pd.to_datetime(row.get('DATEOUT'), errors='coerce'),
                    return_date=pd.to_datetime(row.get('RETURNDATE'), errors='coerce'),
                    rush_order=bool(row.get('RushOrder')),
                    firm_rush=bool(row.get('FirmRush')),
                    quote=row.get('QUOTE'),
                    quote_by=row.get('QUOTE  BY', ''),
                    approved=bool(row.get('APPROVED')),
                    rack_number=row.get('RACK#', ''),
                    storage=row.get('STORAGE', ''),
                    location=row.get('LOCATION', ''),
                    item_type=row.get('ITEM TYPE', ''),
                    type_of_repair=row.get('TYPE OF REPAIR', ''),
                    special_instructions=row.get('SPECIALINSTRUCTIONS', ''),
                    repairs_done_by=row.get('REPAIRSDONEBY', ''),
                    material_list=row.get('MaterialList', ''),
                    customer_price=row.get('CUSTOMERPRICE'),
                    clean=bool(row.get('CLEAN')),
                    see_clean=bool(row.get('SEECLEAN')),
                    clean_first=bool(row.get('CLEANFIRST')),
                    return_status=row.get('RETURNSTATUS', '')
                )
                db.session.add(repair_order)
        
        # Import repair order items
        ro_items_file = os.path.join(self.csv_path, 'tblRepOrdDetCustAwngs.csv')
        if os.path.exists(ro_items_file):
            df = pd.read_csv(ro_items_file)
            for _, row in df.iterrows():
                repair_order = RepairOrder.query.filter_by(repair_order_no=row.get('RepairOrderNo')).first()
                if repair_order:
                    ro_item = RepairOrderItem(
                        repair_order_id=repair_order.id,
                        customer_id=row.get('CustID'),
                        qty=row.get('Qty', 1),
                        description=row.get('Description', ''),
                        material=row.get('Material', ''),
                        condition=row.get('Condition', ''),
                        color=row.get('Color', ''),
                        size_weight=row.get('SizeWgt', ''),
                        price=row.get('Price')
                    )
                    db.session.add(ro_item)
    
    def import_progress(self):
        """Import progress tracking"""
        progress_file = os.path.join(self.csv_path, 'tblProgress.csv')
        if not os.path.exists(progress_file):
            return
        
        df = pd.read_csv(progress_file)
        for _, row in df.iterrows():
            work_order = WorkOrder.query.filter_by(work_order_no=row.get('PgrsWorkOrderNo')).first()
            
            progress = ProgressTracking(
                customer_id=row.get('CustID'),
                work_order_id=work_order.id if work_order else None,
                pgrs_work_order_no=row.get('PgrsWorkOrderNo', ''),
                pgrs_name=row.get('PgrsName', ''),
                pgrs_date_in=pd.to_datetime(row.get('PgrsDateIn'), errors='coerce'),
                pgrs_date_updated=pd.to_datetime(row.get('PgrsDateUptd'), errors='coerce'),
                pgrs_source=row.get('PgrsSource', ''),
                wo_quote=row.get('WO_Quote'),
                on_deck_clean=bool(row.get('OnDeckClean')),
                tub=bool(row.get('Tub')),
                clean=bool(row.get('Clean')),
                treat=bool(row.get('Treat')),
                wrap_clean=bool(row.get('WrapClean')),
                notes_clean=row.get('NotesClean', ''),
                pgrs_repair_order_no=row.get('PgrsRepairOrderNo', ''),
                repair_quote=row.get('Repair_Quote'),
                on_deck_repair=bool(row.get('OnDeckRepair')),
                in_process=bool(row.get('InProcess')),
                wrap_repair=bool(row.get('WrapRepair')),
                repair_notes=row.get('Repair_Notes', '')
            )
            db.session.add(progress)
    
    def import_photos(self):
        """Import photo records"""
        photos_file = os.path.join(self.csv_path, 'tblPhotos.csv')
        if not os.path.exists(photos_file):
            return
        
        df = pd.read_csv(photos_file)
        for _, row in df.iterrows():
            photo = Photo(
                customer_id=row.get('CustID'),
                filename=row.get('Link', ''),  # Using Link as filename
                original_filename=row.get('Link', ''),
                file_path=row.get('Link', ''),
                photo_date=pd.to_datetime(row.get('PhotoDate'), errors='coerce'),
                notes=row.get('Notes', '')
            )
            db.session.add(photo)
    
    def export_to_csv(self, model_class, filename):
        """Export model data to CSV"""
        try:
            # Get all records
            records = model_class.query.all()
            
            if not records:
                return False, "No data to export"
            
            # Convert to dict if method exists
            if hasattr(records[0], 'to_dict'):
                data = [record.to_dict() for record in records]
            else:
                # Fallback to basic conversion
                data = []
                for record in records:
                    record_dict = {}
                    for column in record.__table__.columns:
                        value = getattr(record, column.name)
                        if value is not None:
                            record_dict[column.name] = str(value)
                        else:
                            record_dict[column.name] = ''
                    data.append(record_dict)
            
            # Create DataFrame and save
            df = pd.DataFrame(data)
            export_path = os.path.join(self.csv_path, filename)
            df.to_csv(export_path, index=False)
            
            return True, f"Data exported to {export_path}"
        
        except Exception as e:
            return False, f"Error exporting data: {str(e)}"
EOF

# utils/helpers.py
cat > utils/helpers.py << 'EOF'
from datetime import datetime
import os
import secrets
from PIL import Image
from flask import current_app

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_photo(form_photo, customer_id):
    """Save uploaded photo and return filename"""
    if form_photo and allowed_file(form_photo.filename):
        # Generate secure filename
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_photo.filename)
        photo_filename = f"customer_{customer_id}_{random_hex}{f_ext}"
        
        # Create customer photo directory
        customer_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'photos', str(customer_id))
        os.makedirs(customer_dir, exist_ok=True)
        
        photo_path = os.path.join(customer_dir, photo_filename)
        
        # Resize image to save space
        img = Image.open(form_photo)
        img.thumbnail((1200, 1200))
        img.save(photo_path)
        
        return photo_filename, photo_path
    
    return None, None

def generate_work_order_number():
    """Generate next work order number"""
    from models.work_order import WorkOrder
    
    last_wo = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_wo.id + 1) if last_wo else 1
    return f"WO{next_id:06d}"

def generate_repair_order_number():
    """Generate next repair order number"""
    from models.repair_order import RepairOrder
    
    last_ro = RepairOrder.query.order_by(RepairOrder.id.desc()).first()
    next_id = (last_ro.id + 1) if last_ro else 1
    return f"RO{next_id:06d}"

def format_phone_number(phone):
    """Format phone number for display"""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone

def calculate_days_since(date):
    """Calculate days since a given date"""
    if not date:
        return None
    
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d').date()
    
    return (datetime.now().date() - date).days

def get_status_color(status):
    """Return Bootstrap color class for status"""
    status_colors = {
        'pending': 'warning',
        'in_progress': 'info',
        'completed': 'success',
        'cancelled': 'danger',
        'on_hold': 'secondary'
    }
    
    return status_colors.get(status.lower() if status else '', 'secondary')

def paginate_query(query, page, per_page=50):
    """Helper function for pagination"""
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
EOF

# Management script
echo "🚀 Creating management script..."

cat > manage.py << 'EOF'
#!/usr/bin/env python3
"""
Management script for Awning Management System
"""

import os
import sys
from flask import Flask
from flask.cli import with_appcontext
import click
from werkzeug.security import generate_password_hash

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.user import User
from utils.csv_handler import CSVHandler

@click.group()
def cli():
    """Awning Management System CLI"""
    pass

@cli.command()
@with_appcontext
def init_db():
    """Initialize the database"""
    click.echo('Initializing database...')
    db.create_all()
    click.echo('Database initialized successfully!')

@cli.command()
@with_appcontext
def drop_db():
    """Drop all database tables"""
    if click.confirm('This will delete all data. Are you sure?'):
        db.drop_all()
        click.echo('Database tables dropped.')

@cli.command()
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True)
@with_appcontext
def create_user(username, email, password):
    """Create a new user"""
    if User.query.filter_by(username=username).first():
        click.echo(f'User {username} already exists.')
        return
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )
    
    db.session.add(user)
    db.session.commit()
    
    click.echo(f'User {username} created successfully!')

@cli.command()
@with_appcontext
def import_csv():
    """Import data from CSV files"""
    click.echo('Importing CSV data...')
    
    csv_handler = CSVHandler()
    success, message = csv_handler.import_all_csvs()
    
    if success:
        click.echo(f'✅ {message}')
    else:
        click.echo(f'❌ {message}')

@cli.command()
@with_appcontext
def sample_data():
    """Create sample data for testing"""
    click.echo('Creating sample data...')
    
    # Create sample user if doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123')
        )
        db.session.add(admin_user)
    
    # Create sample reference data
    from models.reference import Material, Color, Condition
    
    materials = ['Canvas', 'Vinyl', 'Acrylic', 'Polyester']
    for material_name in materials:
        if not Material.query.filter_by(name=material_name).first():
            db.session.add(Material(name=material_name))
    
    colors = ['White', 'Green', 'Blue', 'Red', 'Yellow', 'Black']
    for color_name in colors:
        if not Color.query.filter_by(name=color_name).first():
            db.session.add(Color(name=color_name))
    
    conditions = ['New', 'Good', 'Fair', 'Poor', 'Damaged']
    for condition_name in conditions:
        if not Condition.query.filter_by(name=condition_name).first():
            db.session.add(Condition(name=condition_name))
    
    # Create sample customer
    from models.customer import Customer
    if not Customer.query.filter_by(name='Sample Customer').first():
        customer = Customer(
            name='Sample Customer',
            contact='John Doe',
            address='123 Main St',
            city='Anytown',
            state='NY',
            zip_code='12345',
            home_phone='(555) 123-4567',
            email_address='customer@example.com'
        )
        db.session.add(customer)
    
    db.session.commit()
    click.echo('Sample data created successfully!')

if __name__ == '__main__':
    with app.app_context():
        cli()
EOF

# Make manage.py executable
chmod +x manage.py

# README.md
cat > README.md << 'EOF'
# Awning Management System