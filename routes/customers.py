from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.customer import Customer
from models.source import Source
from models.inventory import Inventory
from models.work_order import WorkOrder
from models.repair_order import RepairWorkOrder
from extensions import db
from sqlalchemy import or_, func, cast, Integer, desc, asc
import json
from decorators import role_required


customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/")
@login_required
def list_customers():
    """Render the customer list page with filters"""
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "").strip()
    state_filter = request.args.get("state", "").strip()

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
        search_query=search_query,
        source_filter=source_filter,
        state_filter=state_filter,
        unique_sources=unique_sources,
        unique_states=unique_states,
    )


@customers_bp.route("/api/customers")
@login_required
def api_customers():
    """API endpoint for the customers table with server-side filtering, sorting, and pagination"""

    # Get pagination parameters
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)

    # Start with base query
    query = Customer.query

    # Apply global filters
    search = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "").strip()
    state_filter = request.args.get("state", "").strip()

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Customer.Name.ilike(search_term),
                Customer.CustID.ilike(search_term),
                Customer.Contact.ilike(search_term),
                Customer.City.ilike(search_term),
                Customer.State.ilike(search_term),
                Customer.HomePhone.ilike(search_term),
                Customer.EmailAddress.ilike(search_term),
                Customer.Source.ilike(search_term),
            )
        )

    if source_filter:
        query = query.filter(Customer.Source == source_filter)

    if state_filter:
        query = query.filter(Customer.State == state_filter)

    # Apply column-specific filters
    filter_mapping = {
        "filter_CustID": cast(Customer.CustID, Integer),
        "filter_Name": Customer.Name,
        "filter_Contact": Customer.Contact,
        "filter_Location": Customer.City,  # Assuming Location maps to City
        "filter_Phone": Customer.HomePhone,
        "filter_EmailAddress": Customer.EmailAddress,
        "filter_Source": Customer.Source,
    }

    for filter_key, column in filter_mapping.items():
        filter_value = request.args.get(filter_key, "").strip()
        if filter_value:
            if filter_key == "filter_CustID":
                query = query.filter(column == filter_value)
            else:
                filter_term = f"%{filter_value}%"
                query = query.filter(column.ilike(filter_term))

    # Handle Tabulator's sorting format: sort[0][field]=Location&sort[0][dir]=asc
    field_mapping = {
        "CustID": Customer.CustID,
        "Name": Customer.Name,
        "Contact": Customer.Contact,
        "Location": Customer.City,
        "Phone": Customer.HomePhone,
        "EmailAddress": Customer.EmailAddress,
        "Source": Customer.Source,
    }

    # Look for sort parameters in the format sort[0][field], sort[0][dir], etc.
    sort_applied = False
    i = 0
    while True:
        field_param = f"sort[{i}][field]"
        dir_param = f"sort[{i}][dir]"

        field = request.args.get(field_param)
        direction = request.args.get(dir_param, "asc")

        if not field:
            break

        if field in field_mapping:
            column = field_mapping[field]
            if direction == "desc":
                query = query.order_by(desc(column))
            else:
                query = query.order_by(asc(column))
            sort_applied = True
            print(f"Applied sort: {field} {direction}")  # Debug log

        i += 1

    # Default sorting if no sort was applied
    if not sort_applied:
        query = query.order_by(Customer.CustID)

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    customers = query.paginate(page=page, per_page=size, error_out=False)

    # Format data for response
    data = []
    for customer in customers.items:
        # Build location string
        location_parts = []
        if customer.City:
            location_parts.append(customer.City)
        if customer.State:
            location_parts.append(customer.State)
        location = ", ".join(location_parts) if location_parts else None

        data.append(
            {
                "CustID": customer.CustID,
                "Name": customer.Name,
                "Contact": customer.Contact,
                "Location": location,
                "Phone": customer.get_primary_phone()
                if hasattr(customer, "get_primary_phone")
                else customer.Phone,
                "EmailAddress": customer.EmailAddress,
                "Source": customer.Source,
                "detail_url": url_for(
                    "customers.customer_detail", customer_id=customer.CustID
                ),
                "edit_url": url_for(
                    "customers.edit_customer", customer_id=customer.CustID
                ),
            }
        )

    # Calculate pagination info
    last_page = customers.pages

    # Debug log
    print(f"Query executed: {query}")
    print(f"Total results: {total}")

    return jsonify(
        {
            "data": data,
            "total": total,
            "page": page,
            "size": size,
            "last_page": last_page,
            "has_next": customers.has_next,
            "has_prev": customers.has_prev,
        }
    )


@customers_bp.route("/view/<customer_id>")
@login_required
def customer_detail(customer_id):
    """Display detailed view of a customer"""
    customer = Customer.query.get_or_404(customer_id)
    inventory_items = Inventory.query.filter_by(CustID=customer_id).all()

    # Work Orders: newest first by date
    work_orders = (
        WorkOrder.query.filter_by(CustID=customer_id)
        .order_by(desc(cast(WorkOrder.WorkOrderNo, Integer)))
        .all()
    )

    # Repair Orders: newest first by numeric RepairOrderNo
    repair_orders = (
        RepairWorkOrder.query.filter_by(CustID=customer_id)
        .order_by(desc(cast(RepairWorkOrder.RepairOrderNo, Integer)))
        .all()
    )
    return render_template(
        "customers/detail.html",
        customer=customer,
        inventory_items=inventory_items,
        work_orders=work_orders,
        repair_work_orders=repair_orders,
    )


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("manager", "admin")
def create_customer():
    """Create a new customer"""
    if request.method == "POST":
        data = request.form

        if not data.get("Name"):
            flash("Customer name is required", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

        try:
            # Auto-generate the new customer ID
            max_cust_id = db.session.query(
                func.max(cast(Customer.CustID, Integer))
            ).scalar()
            new_cust_id = str(max_cust_id + 1) if max_cust_id else "1"

            customer = Customer(
                CustID=new_cust_id,
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
@role_required("admin", "manager")
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


@customers_bp.route("/api/source_info/<source_name>")
@login_required
def api_source_info(source_name):
    source = Source.query.filter_by(SSource=source_name).first_or_404()
    return jsonify(
        {
            "address": source.SourceAddress,
            "city": source.SourceCity,
            "state": source.SourceState,
            "zip": source.SourceZip,
        }
    )


@customers_bp.route("/delete/<customer_id>", methods=["POST"])
@login_required
@role_required("admin", "manager")
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
