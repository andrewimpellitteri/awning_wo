from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from config import Config
from extensions import db, login_manager
import os
from sqlalchemy import inspect
from datetime import datetime, date


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @app.template_filter("price_format")
    def format_price(price):
        """
        Formats a number to a price string with a dollar sign and two decimal places.

        Args:
            price: A number (integer or float).

        Returns:
            A string formatted as a price (e.g., "$123.45").
        """
        try:
            # Use an f-string to format the number to two decimal places.
            return f"${float(price):.2f}"
        except (ValueError, TypeError) as e:
            # Handle cases where the input is not a valid number.
            print(f"Error: Invalid input '{price}'. Please provide a number.")
            return None

    @app.template_filter("yesdash")
    def yesdash(value):
        """Render truthy values as 'Yes' or '-'."""
        if str(value).upper() in ("1", "YES", "TRUE"):
            return "Yes"
        return "-"

    @app.template_filter("date_format")
    def format_date(value):
        """Formats datetime/date/custom string to MM/DD/YYYY."""
        print("\n[DEBUG] date_format called with:", repr(value), "of type", type(value))

        if not value:
            return "-"

        try:
            # Case 1: Already a datetime or date
            if isinstance(value, (datetime, date)):
                formatted = value.strftime("%m/%d/%Y")
                print("[DEBUG] Parsed as datetime/date ->", formatted)
                return formatted

            # Case 2: String already in MM/DD/YY HH:MM:SS format
            try:
                dt_object = datetime.strptime(value, "%m/%d/%y %H:%M:%S")
                formatted = dt_object.strftime("%m/%d/%Y")
                print("[DEBUG] Parsed as custom string ->", formatted)
                return formatted
            except ValueError:
                pass  # not that format, fall through

            # Case 3: Try ISO string
            dt_object = datetime.fromisoformat(value)
            formatted = dt_object.strftime("%m/%d/%Y")
            print("[DEBUG] Parsed as ISO string ->", formatted)
            return formatted

        except Exception as e:
            print("[DEBUG] Exception in date_format:", e)
            return str(value)

    # Import and register ONLY working blueprints
    from routes.auth import auth_bp
    from routes.source import source_bp

    # Comment out all the problematic ones for now
    from routes.customers import customers_bp
    from routes.work_orders import work_orders_bp
    from routes.repair_order import repair_work_orders_bp

    # from routes.repair_orders import repair_orders_bp
    # from routes.reports import reports_bp
    # from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(source_bp, url_prefix="/sources")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(work_orders_bp, url_prefix="/work_orders")
    app.register_blueprint(repair_work_orders_bp, url_prefix="/repair_work_orders")

    # Comment out all the problematic registrations
    # app.register_blueprint(customers_bp, url_prefix="/customers")
    # app.register_blueprint(work_orders_bp, url_prefix="/work-orders")
    # app.register_blueprint(repair_orders_bp, url_prefix="/repair-orders")
    # app.register_blueprint(reports_bp, url_prefix="/reports")
    # app.register_blueprint(api_bp, url_prefix="/api")

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

# Debug routes - should only show auth, source, dashboard, and health_check
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Available tables: {tables}")

    print(f"\nAvailable routes:")
    for rule in app.url_map.iter_rules():
        methods = ", ".join(rule.methods - {"HEAD", "OPTIONS"})
        print(f"  {rule.endpoint:30} {rule.rule:30} [{methods}]")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
