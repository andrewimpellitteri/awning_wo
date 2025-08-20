from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from config import Config
from extensions import db, login_manager
import os


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.customers import customers_bp
    from routes.work_orders import work_orders_bp
    from routes.repair_orders import repair_orders_bp
    from routes.reports import reports_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(work_orders_bp, url_prefix="/work-orders")
    app.register_blueprint(repair_orders_bp, url_prefix="/repair-orders")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Register routes
    @app.route("/")
    @login_required
    def dashboard():
        """Main dashboard view"""
        return render_template("dashboard.html")

    @app.route("/health")
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "healthy"})

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User

        return User.query.get(int(user_id))

    return app


# Create app instance
app = create_app()

# # Create tables
# with app.app_context():
#     db.create_all()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
