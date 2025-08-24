from flask import Flask, render_template, jsonify
from flask_login import login_required, current_user
from config import Config
from extensions import db, login_manager
from sqlalchemy import inspect
from datetime import datetime, date
import os


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
        """
        try:
            return f"${float(price):.2f}"
        except (ValueError, TypeError) as e:
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
                # print("[DEBUG] Parsed as datetime/date ->", formatted)
                return formatted

            # Case 2: String already in MM/DD/YY HH:MM:SS format
            try:
                dt_object = datetime.strptime(value, "%m/%d/%y %H:%M:%S")
                formatted = dt_object.strftime("%m/%d/%Y")
                # print("[DEBUG] Parsed as custom string ->", formatted)
                return formatted
            except ValueError:
                pass

            # Case 3: Try ISO string
            dt_object = datetime.fromisoformat(value)
            formatted = dt_object.strftime("%m/%d/%Y")
            print("[DEBUG] Parsed as ISO string ->", formatted)
            return formatted

        except Exception as e:
            print("[DEBUG] Exception in date_format:", e)
            return str(value)

    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.source import source_bp
    from routes.customers import customers_bp
    from routes.work_orders import work_orders_bp
    from routes.repair_order import repair_work_orders_bp
    from routes.admin import admin_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(source_bp, url_prefix="/sources")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(work_orders_bp, url_prefix="/work_orders")
    app.register_blueprint(repair_work_orders_bp, url_prefix="/repair_work_orders")
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp, url_prefix="/analytics")

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

    return app


# Create app instance
app = create_app()

# Debug info (only show in development)
if os.environ.get("FLASK_ENV") == "development":
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

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
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
