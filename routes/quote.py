from flask import Blueprint, render_template
from flask_login import login_required
from decorators import role_required

quote_bp = Blueprint("quote", __name__, url_prefix="/quotes")


@quote_bp.route("/")
@login_required
@role_required(["admin", "manager"])
def list_quotes():
    """Display list of quotes - placeholder for future implementation"""
    return render_template("quotes/list.html")


@quote_bp.route("/create")
@login_required
@role_required(["admin", "manager"])
def create_quote():
    """Create a new quote - placeholder for future implementation"""
    return render_template("quotes/create.html")
