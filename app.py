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
