from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.customer import Customer
from models.source import Source
from models.inventory import Inventory
from models.work_order import WorkOrder
from models.repair_order import RepairWorkOrder
from extensions import db, cache
from sqlalchemy import or_, func, cast, Integer, desc, asc
from sqlalchemy.exc import IntegrityError
import json
import time
import random
from decorators import role_required
from flask_login import current_user
from utils.cache_helpers import invalidate_customer_cache


customers_bp = Blueprint("customers", __name__)


def user_can_edit():
    return current_user.role in ("admin", "manager")


@cache.memoize(timeout=600)  # Cache for 10 minutes
def get_customer_filter_options():
    """
    Get unique sources for customer filter dropdowns.
    Cached to avoid repeated queries on every page load.
    """
    sources = (
        db.session.query(Customer.Source)
        .filter(Customer.Source.isnot(None), Customer.Source != "")
        .distinct()
        .order_by(Customer.Source)
        .all()
    )
    unique_sources = [source[0] for source in sources]

    return unique_sources


@customers_bp.route("/")
@login_required
@role_required("admin", "manager")
def list_customers():
    """Render the customer list page with filters"""
    search_query = request.args.get("search", "").strip()
    source_filter = request.args.get("source", "").strip()

    # Get cached filter options (saves 2 queries on every page load)
    unique_sources = get_customer_filter_options()

    return render_template(
        "customers/list.html",
        search_query=search_query,
        source_filter=source_filter,
        unique_sources=unique_sources,
    )


@customers_bp.route("/api/customers")
@login_required
def api_customers():
    """API endpoint for the customers table with server-side filtering, sorting, and pagination"""

    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)

    query = Customer.query

    # Apply global search
    search = request.args.get("search", "").strip()
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Customer.Name.ilike(term),
                Customer.CustID.ilike(term),
                Customer.Contact.ilike(term),
                Customer.City.ilike(term),
                Customer.HomePhone.ilike(term),
                Customer.EmailAddress.ilike(term),
                Customer.Source.ilike(term),
            )
        )

    # Apply column-specific filters
    filter_mapping = {
        "filter_CustID": cast(Customer.CustID, Integer),
        "filter_Name": Customer.Name,
        "filter_Contact": Customer.Contact,
        "filter_Location": Customer.City,  # or City+State if needed
        "filter_Phone": Customer.HomePhone,
        "filter_EmailAddress": Customer.EmailAddress,
        "filter_Source": Customer.Source,
    }

    for key, column in filter_mapping.items():
        val = request.args.get(key, "").strip()
        if val:
            if key == "filter_CustID":
                query = query.filter(column == val)
            else:
                query = query.filter(column.ilike(f"%{val}%"))

    # Sorting
    sort_mapping = {
        "CustID": Customer.CustID,
        "Name": Customer.Name,
        "Contact": Customer.Contact,
        "Location": Customer.City,
        "Phone": Customer.HomePhone,
        "EmailAddress": Customer.EmailAddress,
        "Source": Customer.Source,
    }

    i = 0
    sort_applied = False
    while True:
        field = request.args.get(f"sort[{i}][field]")
        direction = request.args.get(f"sort[{i}][dir]", "asc")
        if not field:
            break
        if field in sort_mapping:
            col = sort_mapping[field]
            query = query.order_by(desc(col) if direction == "desc" else asc(col))
            sort_applied = True
        i += 1

    if not sort_applied:
        query = query.order_by(Customer.CustID)

    total = query.count()
    customers = query.paginate(page=page, per_page=size, error_out=False)

    data = []
    for c in customers.items:
        location = ", ".join(filter(None, [c.City, c.State]))
        data.append(
            {
                "CustID": c.CustID,
                "Name": c.Name,
                "Contact": c.Contact,
                "Location": location or None,
                "Phone": getattr(c, "get_primary_phone", lambda: c.HomePhone)(),
                "EmailAddress": c.EmailAddress,
                "Source": c.Source,
                "detail_url": url_for(
                    "customers.customer_detail", customer_id=c.CustID
                ),
                "edit_url": url_for("customers.edit_customer", customer_id=c.CustID)
                if user_can_edit()
                else None,
            }
        )

    return jsonify(
        {
            "data": data,
            "total": total,
            "page": page,
            "size": size,
            "last_page": customers.pages,
            "has_next": customers.has_next,
            "has_prev": customers.has_prev,
        }
    )


@customers_bp.route("/view/<customer_id>")
@login_required
def view_customer(customer_id):
    """Alias route for backwards compatibility with tests."""
    return customer_detail(customer_id)


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
            flash("Name is required.", "error")
            return render_template(
                "customers/form.html", form_data=data, sources=Source.query.all()
            )

        # Retry logic to handle race conditions in customer ID generation
        max_retries = 5
        retry_count = 0
        base_delay = 0.1  # 100ms base delay

        while retry_count < max_retries:
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

                # Invalidate cache since customer data changed
                invalidate_customer_cache()

                flash("Customer created successfully", "success")
                return redirect(
                    url_for("customers.view_customer", customer_id=customer.CustID)
                )

            except IntegrityError as ie:
                db.session.rollback()
                retry_count += 1

                # Check if it's a duplicate key error
                error_msg = str(ie.orig).lower() if hasattr(ie, 'orig') else str(ie).lower()
                is_duplicate = 'duplicate' in error_msg or 'unique' in error_msg

                if is_duplicate and retry_count < max_retries:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** retry_count) + (random.random() * 0.05)
                    print(f"Duplicate customer ID detected. Retry {retry_count}/{max_retries} after {delay:.3f}s")
                    time.sleep(delay)
                    continue  # Retry the loop
                else:
                    # Not a duplicate error or max retries exceeded
                    print(f"Error creating customer (IntegrityError): {str(ie)}")
                    flash(f"Error creating customer: {str(ie)}", "error")
                    return render_template(
                        "customers/form.html",
                        form_data=data,
                        sources=Source.query.all()
                    )

            except Exception as e:
                db.session.rollback()
                flash(f"Error creating customer: {str(e)}", "error")
                return render_template(
                    "customers/form.html", form_data=data, sources=Source.query.all()
                )

        # If we exhausted all retries
        flash("Error creating customer: Unable to generate unique customer ID after multiple attempts", "error")
        return render_template(
            "customers/form.html",
            form_data=data,
            sources=Source.query.all()
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

            # Invalidate cache since customer data changed
            invalidate_customer_cache()

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
            "SSource": source.SSource,
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

        # Invalidate cache since customer data changed
        invalidate_customer_cache()

        flash(f"Customer {customer_id} deleted.", "success")  # <-- match test
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting customer: {str(e)}", "error")

    return redirect(url_for("customers.list_customers"))
