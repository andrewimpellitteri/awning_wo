from flask import Flask, render_template, jsonify
from flask_login import login_required, current_user
from config import Config
from extensions import db, login_manager, cache
from sqlalchemy import inspect
from datetime import datetime, date
import os
import re
from markupsafe import Markup


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    cache.init_app(app)

    @app.template_filter("nl2br")
    def nl2br_filter(s):
        if not s:
            return ""
        # Normalize Windows CRLF and old Mac CR to LF
        text = s.replace("\r\n", "\n").replace("\r", "\n")
        # Replace newlines with <br> and mark as safe HTML
        return Markup(text.replace("\n", "<br>"))

    @app.template_filter("price_format")
    def format_price(price):
        """
        Formats a number to a price string with a dollar sign and two decimal places.
        Returns None if the price is None, empty string, or zero.
        Returns formatted string for valid numbers.
        """
        if price is None or price == "" or price == 0:
            return None
        try:
            return f"${float(price):.2f}"
        except (ValueError, TypeError):
            # Return None for invalid values instead of printing error
            return None

    @app.template_filter("format_phone")
    def format_phone(phone) -> str:
        """Format a phone number (int or str) into (XXX) XXX-XXXX."""
        if phone is None or phone == "":
            return ""

        # Convert to string and extract only digits
        phone_str = str(phone)

        # Handle legacy floats with .0 suffix by removing decimal part
        if "." in phone_str:
            phone_str = phone_str.split(".")[0]

        digits = re.sub(r"\D", "", phone_str)

        # Return empty string if no digits
        if not digits or digits == "0":
            return ""

        # Handle 10-digit US numbers
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

        # Handle 11-digit starting with '1' (US country code)
        if len(digits) == 11 and digits.startswith("1"):
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

        # Fallback: return digits as-is
        return digits

    @app.template_filter("yesdash")
    def yesdash(value):
        """Render truthy values as 'Yes' or '-'. Now handles proper booleans."""
        # Handle boolean True/False directly
        if isinstance(value, bool):
            return "Yes" if value else "-"
        # Legacy string handling (for backward compatibility during migration)
        if str(value).upper() in ("1", "YES", "TRUE"):
            return "Yes"
        return "-"

    @app.template_filter("date_format")
    def format_date(value, show_time=False):
        """Formats datetime/date objects to MM/DD/YYYY, optionally with time."""
        if not value:
            return "-"

        try:
            # Case 1: datetime
            if isinstance(value, datetime):
                fmt = "%m/%d/%Y %H:%M:%S" if show_time else "%m/%d/%Y"
                return value.strftime(fmt)

            # Case 2: date
            if isinstance(value, date):
                return value.strftime("%m/%d/%Y")

            # Case 3: legacy strings
            try:
                dt_object = datetime.strptime(str(value), "%m/%d/%y %H:%M:%S")
                return dt_object.strftime("%m/%d/%Y")
            except ValueError:
                pass

            dt_object = datetime.fromisoformat(str(value))
            return dt_object.strftime("%m/%d/%Y")

        except Exception:
            return str(value) if value else "-"

    if os.environ.get("RUN_PROFILER") == "True":
        from werkzeug.middleware.profiler import ProfilerMiddleware

        os.makedirs("profiles", exist_ok=True)  # Create dir if needed
        app.wsgi_app = ProfilerMiddleware(
            app.wsgi_app,
            profile_dir="profiles",
            filename_format="{method}.{path}.{elapsed:2.4f}ms.{time}.prof",
            restrictions=[
                30
            ],  # Limit output to top 30 functions (optional, adjust as needed)
        )

    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.source import source_bp
    from routes.customers import customers_bp
    from routes.work_orders import work_orders_bp
    from routes.repair_order import repair_work_orders_bp
    from routes.admin import admin_bp
    from routes.analytics import analytics_bp
    from routes.inventory import inventory_bp
    from routes.queue import queue_bp
    from routes.ml import ml_bp
    from routes.dashboard import dashboard_bp
    from routes.in_progress import in_progress_bp
    from routes.quote import quote_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(source_bp, url_prefix="/sources")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(work_orders_bp, url_prefix="/work_orders")
    app.register_blueprint(repair_work_orders_bp, url_prefix="/repair_work_orders")
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(queue_bp, url_prefix="/cleaning_queue")
    app.register_blueprint(ml_bp)
    app.register_blueprint(dashboard_bp, url_prefix="/")
    app.register_blueprint(in_progress_bp, url_prefix="/in_progress")
    app.register_blueprint(quote_bp, url_prefix="/quotes")

    # Register routes
    @app.route("/")
    @login_required
    def dashboard():
        """Main dashboard view"""
        return render_template("dashboard.html")

    @app.route("/health")
    def health_check():
        """Health check endpoint for AWS"""
        return jsonify(
            {
                "status": "healthy",
                "environment": os.environ.get("FLASK_ENV", "production"),
            }
        )

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User

        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        try:
            # Print the DB URI being used
            print(
                "[DEBUG] SQLALCHEMY_DATABASE_URI:",
                app.config.get("SQLALCHEMY_DATABASE_URI"),
            )
        except Exception as e:
            print("[DEBUG] Database connection error:", e)

    return app


# Create app instance (skip during test collection to avoid DB connection errors)
if os.environ.get("TESTING") != "True":
    app = create_app()
else:
    # Create a placeholder for imports during testing
    app = None

# Debug info (only show in development)
if os.environ.get("FLASK_ENV") == "development" and app is not None:
    with app.app_context():
        from models.work_order_file import WorkOrderFile

        db.create_all()
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # List all tables visible to this DB connection
            tables = db.engine.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public';"
            )
            print([t[0] for t in tables])

            print("Database URL:", db.engine.url)
            print(f"Available tables: {tables}")

            print("\nAvailable routes:")
            for rule in app.url_map.iter_rules():
                methods = ", ".join(rule.methods - {"HEAD", "OPTIONS"})
                print(f"  {rule.endpoint:30} {rule.rule:30} [{methods}]")
        except Exception as e:
            print(f"Database connection error: {e}")

if __name__ == "__main__":
    # Local development server
    if app is not None:
        app.run(
            debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true",
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 5000)),
        )
