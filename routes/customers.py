from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.customer import Customer
from models.source import Source
from extensions import db
from sqlalchemy import or_

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/")
@login_required
def list_customers():
    """Display all customers with search functionality"""
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "").strip()
    state_filter = request.args.get("state", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Customer.query

    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Customer.Name.contains(search_query),
                Customer.CustID.contains(search_query),
                Customer.Contact.contains(search_query),
                Customer.City.contains(search_query),
                Customer.EmailAddress.contains(search_query),
            )
        )

    # Apply source filter
    if source_filter:
        query = query.filter(Customer.Source.ilike(f"%{source_filter}%"))

    # Apply state filter
    if state_filter:
        query = query.filter(Customer.State.ilike(f"%{state_filter}%"))

    customers = query.order_by(Customer.Name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Get unique sources and states for filter dropdowns
    sources = (
        db.session.query(Customer.Source)
        .filter(Customer.Source.isnot(None), Customer.Source != "")
        .distinct()
        .order_by(Customer.Source)
        .all()
    )
    unique_sources = [source[0] for source in sources]

    states = (
        db.session.query(Customer.State)
        .filter(Customer.State.isnot(None), Customer.State != "")
        .distinct()
        .order_by(Customer.State)
        .all()
    )
    unique_states = [state[0] for state in states]

    return render_template(
        "customers/list.html",
        customers=customers,
        search_query=search_query,
        source_filter=source_filter,
        state_filter=state_filter,
        unique_sources=unique_sources,
        unique_states=unique_states,
    )


@customers_bp.route("/view/<customer_id>")
@login_required
def customer_detail(customer_id):
    """Display detailed view of a customer"""
    customer = Customer.query.get_or_404(customer_id)
    return render_template("customers/detail.html", customer=customer)


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_customer():
    """Create a new customer"""
    if request.method == "POST":
        data = request.form

        if not data.get("CustID"):
            flash("Customer ID is required", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

        if not data.get("Name"):
            flash("Customer name is required", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

        # Check if customer already exists
        if Customer.query.get(data["CustID"]):
            flash("Customer ID already exists", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

        try:
            customer = Customer(
                CustID=data["CustID"],
                Name=data.get("Name"),
                Contact=data.get("Contact"),
                Address=data.get("Address"),
                Address2=data.get("Address2"),
                City=data.get("City"),
                State=data.get("State"),
                ZipCode=data.get("ZipCode"),
                HomePhone=data.get("HomePhone"),
                WorkPhone=data.get("WorkPhone"),
                CellPhone=data.get("CellPhone"),
                EmailAddress=data.get("EmailAddress"),
                MailAddress=data.get("MailAddress"),
                MailCity=data.get("MailCity"),
                MailState=data.get("MailState"),
                MailZip=data.get("MailZip"),
                Source=data.get("Source"),
                SourceOld=data.get("SourceOld"),
            )

            # Auto-populate source address fields if source is selected
            if customer.Source:
                source = Source.query.get(customer.Source)
                if source:
                    customer.SourceAddress = source.SourceAddress
                    customer.SourceCity = source.SourceCity
                    customer.SourceState = source.SourceState
                    customer.SourceZip = source.SourceZip

            db.session.add(customer)
            db.session.commit()

            flash("Customer created successfully", "success")
            return redirect(
                url_for("customers.customer_detail", customer_id=customer.CustID)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating customer: {str(e)}", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

    sources = Source.query.order_by(Source.SSource).all()
    return render_template("customers/form.html", sources=sources)


@customers_bp.route("/edit/<customer_id>", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    """Edit an existing customer"""
    customer = Customer.query.get_or_404(customer_id)

    if request.method == "POST":
        data = request.form

        if not data.get("Name"):
            flash("Customer name is required", "error")
            return render_template(
                "customers/form.html",
                customer=customer,
                sources=Source.query.all(),
                edit_mode=True,
            )

        try:
            # Update fields
            customer.Name = data.get("Name")
            customer.Contact = data.get("Contact")
            customer.Address = data.get("Address")
            customer.Address2 = data.get("Address2")
            customer.City = data.get("City")
            customer.State = data.get("State")
            customer.ZipCode = data.get("ZipCode")
            customer.HomePhone = data.get("HomePhone")
            customer.WorkPhone = data.get("WorkPhone")
            customer.CellPhone = data.get("CellPhone")
            customer.EmailAddress = data.get("EmailAddress")
            customer.MailAddress = data.get("MailAddress")
            customer.MailCity = data.get("MailCity")
            customer.MailState = data.get("MailState")
            customer.MailZip = data.get("MailZip")
            customer.Source = data.get("Source")
            customer.SourceOld = data.get("SourceOld")

            # Update source address fields if source changed
            if customer.Source:
                source = Source.query.get(customer.Source)
                if source:
                    customer.SourceAddress = source.SourceAddress
                    customer.SourceCity = source.SourceCity
                    customer.SourceState = source.SourceState
                    customer.SourceZip = source.SourceZip

            db.session.commit()
            flash("Customer updated successfully", "success")
            return redirect(
                url_for("customers.customer_detail", customer_id=customer.CustID)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating customer: {str(e)}", "error")

    sources = Source.query.order_by(Source.SSource).all()
    return render_template(
        "customers/form.html", customer=customer, sources=sources, edit_mode=True
    )


@customers_bp.route("/delete/<customer_id>", methods=["POST"])
@login_required
def delete_customer(customer_id):
    """Delete a customer"""
    customer = Customer.query.get_or_404(customer_id)

    try:
        db.session.delete(customer)
        db.session.commit()
        flash("Customer deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting customer: {str(e)}", "error")

    return redirect(url_for("customers.list_customers"))


# API endpoints
@customers_bp.route("/api/search")
@login_required
def api_search():
    """API endpoint for searching customers"""
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    customers = (
        Customer.query.filter(
            or_(
                Customer.Name.contains(query),
                Customer.CustID.contains(query),
                Customer.Contact.contains(query),
                Customer.City.contains(query),
            )
        )
        .limit(10)
        .all()
    )

    return jsonify(
        [
            {
                "id": customer.CustID,
                "name": customer.Name,
                "contact": customer.Contact,
                "city": customer.City,
                "state": customer.State,
                "phone": customer.get_primary_phone(),
                "source": customer.Source,
            }
            for customer in customers
        ]
    )


@customers_bp.route("/api/source-info/<source_name>")
@login_required
def api_source_info(source_name):
    """API endpoint to get source information for auto-population"""
    source = Source.query.get(source_name)
    if source:
        return jsonify(
            {
                "address": source.SourceAddress,
                "city": source.SourceCity,
                "state": source.SourceState,
                "zip": source.SourceZip,
            }
        )
    return jsonify({})
