from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.work_order import WorkOrder, WorkOrderItem
from models.customer import Customer
from models.source import Source
from models.inventory import Inventory  # Using your new Inventory model
from sqlalchemy import or_, func, desc, cast, Integer, case, literal
from extensions import db
from datetime import datetime, date
from sqlalchemy.types import Date
from sqlalchemy.dialects.postgresql import dialect as pg_dialect
import uuid

work_orders_bp = Blueprint("work_orders", __name__, url_prefix="/work_orders")


@work_orders_bp.route("/")
def list_work_orders():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
                WorkOrder.Storage.like(search_term),
                WorkOrder.RackNo.like(search_term),
                WorkOrder.ShipTo.like(search_term),
                WorkOrder.SpecialInstructions.like(search_term),
                WorkOrder.RepairsNeeded.like(search_term),
            )
        )

    pagination = query.order_by(WorkOrder.DateIn.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "work_orders/list.html",
        work_orders=work_orders,
        pagination=pagination,
        search=search,
    )


@work_orders_bp.route("/<work_order_no>")
def view_work_order(work_order_no):
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()
    return render_template("work_orders/detail.html", work_order=work_order)


@work_orders_bp.route("/status/<status>")
def list_by_status(status):
    """Filter work orders by completion status using DateCompleted"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Pending = DateCompleted is NULL or empty string
    if status.upper() == "PENDING":
        query = WorkOrder.query.filter(
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
        )
    # Completed = DateCompleted has a value
    elif status.upper() == "COMPLETED":
        query = WorkOrder.query.filter(
            WorkOrder.DateCompleted.isnot(None), WorkOrder.DateCompleted != ""
        )
    else:
        query = WorkOrder.query  # fallback if unknown status

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
                WorkOrder.ShipTo.like(search_term),
            )
        )

    pagination = query.order_by(
        WorkOrder.DateIn.desc().nullslast(), WorkOrder.WorkOrderNo.desc()
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "work_orders/list.html",
        work_orders=pagination.items,
        pagination=pagination,
        search=search,
        current_status=status,
    )


@work_orders_bp.route("/pending")
def pending_work_orders():
    """Show work orders that are not completed"""
    return list_by_status("PENDING")


@work_orders_bp.route("/completed")
def completed_work_orders():
    """Show completed work orders"""
    return list_by_status("COMPLETED")


@work_orders_bp.route("/rush")
def rush_work_orders():
    """Show open rush work orders"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.filter(
        or_(WorkOrder.RushOrder == "1", WorkOrder.FirmRush == "1"),
        or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                WorkOrder.WorkOrderNo.like(search_term),
                WorkOrder.CustID.like(search_term),
                WorkOrder.WOName.like(search_term),
            )
        )

    pagination = query.order_by(
        WorkOrder.DateRequired.asc().nullslast(),
        WorkOrder.DateIn.desc().nullslast(),
    ).paginate(page=page, per_page=per_page)

    return render_template(
        "work_orders/list.html",
        work_orders=pagination.items,
        pagination=pagination,
        search=search,
        is_rush_view=True,
    )


def safe_int_conversion(value, default=0):
    """Safely convert string to int"""
    try:
        return int(value or default)
    except (ValueError, TypeError):
        return default


# Corrected work order routes - Inventory as static catalog only:


@work_orders_bp.route("/api/customer_inventory/<cust_id>")
@login_required
def get_customer_inventory(cust_id):
    """Get all inventory items for a specific customer - static catalog"""
    items = Inventory.query.filter_by(CustID=cust_id).all()

    return jsonify(
        [
            {
                "id": item.InventoryKey,
                "description": item.Description or "",
                "material": item.Material or "",
                "color": item.Color or "",
                "condition": item.Condition or "",
                "size_wgt": item.SizeWgt or "",
                "price": item.Price or "",
                "qty": item.Qty or "0",  # This is just for reference, not deducted
            }
            for item in items
        ]
    )


@work_orders_bp.route("/new", methods=["GET", "POST"])
@work_orders_bp.route("/new/<int:prefill_cust_id>", methods=["GET", "POST"])
@login_required
def create_work_order(prefill_cust_id=None):
    """Create a new work order - inventory quantities never change"""
    if request.method == "POST":
        try:
            latest_num = db.session.query(
                func.max(cast(WorkOrder.WorkOrderNo, Integer))
            ).scalar()

            if latest_num is not None:
                next_wo_no = str(latest_num + 1)
            else:
                next_wo_no = "1"

            print("--- Form Data Received ---")
            print(f"Request Form Keys: {request.form.keys()}")
            print(f"Selected Items: {request.form.getlist('selected_items[]')}")
            print(
                f"New Item Descriptions: {request.form.getlist('new_item_description[]')}"
            )
            print("------------------------")

            # Create the work order
            work_order = WorkOrder(
                WorkOrderNo=next_wo_no,
                CustID=request.form.get("CustID"),
                WOName=request.form.get("WOName"),
                StorageTime=request.form.get("StorageTime"),
                RackNo=request.form.get("RackNo"),
                SpecialInstructions=request.form.get("SpecialInstructions"),
                RepairsNeeded=request.form.get("RepairsNeeded"),
                SeeRepair=request.form.get("SeeRepair"),
                ReturnStatus=request.form.get("ReturnStatus"),
                Quote=request.form.get("Quote"),
                Clean=request.form.get("Clean"),
                Treat=request.form.get("Treat"),
                RushOrder=request.form.get("RushOrder", "0"),
                DateRequired=request.form.get("DateRequired"),
                DateIn=datetime.now().strftime("%Y-%m-%d"),
                ShipTo=request.form.get("ShipTo"),
                FirmRush=request.form.get("FirmRush", "0"),
                CleanFirstWO=request.form.get("CleanFirstWO"),
            )

            db.session.add(work_order)
            db.session.flush()

            # Handle selected inventory items (REFERENCE ONLY - NO QUANTITY CHANGES)
            selected_items = request.form.getlist("selected_items[]")
            item_quantities = {}

            print(f"--- Debug: Selected Items from Form ---\n{selected_items}")

            # Parse quantities for selected items
            for key, value in request.form.items():
                print(f"{key}: {request.form[key]}")
                if key.startswith("item_qty_"):
                    item_id = key.replace("item_qty_", "")
                    if item_id in selected_items and value:
                        item_quantities[item_id] = safe_int_conversion(value)

            print(f"--- Debug: Parsed Item Quantities ---\n{item_quantities}")

            # Add selected inventory items to work order (NO INVENTORY MODIFICATION)
            for inventory_key in selected_items:
                requested_qty = item_quantities.get(
                    inventory_key, 1
                )  # default to 1 if not specified

                # Find the inventory item by InventoryKey (primary key must match type)
                inventory_item = Inventory.query.get(inventory_key)

                if inventory_item:
                    print(
                        f"Adding Inventory Item to Work Order: {inventory_item.Description} x {requested_qty}"
                    )

                    work_order_item = WorkOrderItem(
                        WorkOrderNo=next_wo_no,
                        CustID=request.form.get("CustID"),
                        Description=inventory_item.Description,
                        Material=inventory_item.Material,
                        Qty=str(requested_qty),
                        Condition=inventory_item.Condition,
                        Color=inventory_item.Color,
                        SizeWgt=inventory_item.SizeWgt,
                        Price=inventory_item.Price,
                    )
                    db.session.add(work_order_item)
                else:
                    print(
                        f"Warning: Inventory item with key '{inventory_key}' not found in catalog."
                    )

            # Handle new inventory items (items customer is bringing for first time)
            new_item_descriptions = request.form.getlist("new_item_description[]")
            new_item_materials = request.form.getlist("new_item_material[]")
            new_item_quantities = request.form.getlist("new_item_qty[]")
            new_item_conditions = request.form.getlist("new_item_condition[]")
            new_item_colors = request.form.getlist("new_item_color[]")
            new_item_sizes = request.form.getlist("new_item_size[]")
            new_item_prices = request.form.getlist("new_item_price[]")

            for i, description in enumerate(new_item_descriptions):
                if description and i < len(new_item_materials):
                    work_order_qty = safe_int_conversion(
                        new_item_quantities[i] if i < len(new_item_quantities) else "1"
                    )

                    # Add to work order items table
                    work_order_item = WorkOrderItem(
                        WorkOrderNo=next_wo_no,
                        CustID=request.form.get("CustID"),
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Qty=str(work_order_qty),
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                        Price=new_item_prices[i] if i < len(new_item_prices) else "",
                    )
                    db.session.add(work_order_item)

                    # Check if this exact item type already exists in catalog
                    existing_inventory = Inventory.query.filter_by(
                        CustID=request.form.get("CustID"),
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                    ).first()

                    if existing_inventory:
                        # Item type exists in catalog - UPDATE THE CATALOG QUANTITY
                        # This represents the new total they've ever brought of this type
                        current_catalog_qty = safe_int_conversion(
                            existing_inventory.Qty
                        )
                        new_catalog_qty = current_catalog_qty + work_order_qty
                        existing_inventory.Qty = str(new_catalog_qty)

                        flash(
                            f"Updated catalog: Customer now has brought {new_catalog_qty} total of '{description}'",
                            "info",
                        )
                    else:
                        # New item type - ADD TO CATALOG
                        inventory_key = f"INV_{uuid.uuid4().hex[:8].upper()}"

                        new_inventory_item = Inventory(
                            InventoryKey=inventory_key,
                            CustID=request.form.get("CustID"),
                            Description=description,
                            Material=new_item_materials[i]
                            if i < len(new_item_materials)
                            else "",
                            Condition=new_item_conditions[i]
                            if i < len(new_item_conditions)
                            else "",
                            Color=new_item_colors[i]
                            if i < len(new_item_colors)
                            else "",
                            SizeWgt=new_item_sizes[i]
                            if i < len(new_item_sizes)
                            else "",
                            Price=new_item_prices[i]
                            if i < len(new_item_prices)
                            else "",
                            Qty=str(
                                work_order_qty
                            ),  # Total quantity they've ever brought of this type
                        )
                        db.session.add(new_inventory_item)

                        flash(
                            f"New item type '{description}' added to catalog with quantity {work_order_qty}",
                            "success",
                        )

            db.session.commit()
            flash(f"Work Order {next_wo_no} created successfully!", "success")
            return redirect(
                url_for("work_orders.view_work_order", work_order_no=next_wo_no)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating work order: {str(e)}", "error")
            return render_template(
                "work_orders/create.html",
                customers=Customer.query.all(),
                sources=Source.query.all(),
                form_data=request.form,
            )

    # GET request - show the form (unchanged)
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    form_data = {}
    if prefill_cust_id:
        form_data["CustID"] = str(prefill_cust_id)
        customer = Customer.query.get(str(prefill_cust_id))
        if customer:
            form_data["CustID"] = str(prefill_cust_id)
            if customer.Source:
                form_data["ShipTo"] = customer.Source
            form_data["WOName"] = customer.Name

    return render_template(
        "work_orders/create.html",
        customers=customers,
        sources=sources,
        form_data=form_data,
    )


@work_orders_bp.route("/edit/<work_order_no>", methods=["GET", "POST"])
@login_required
def edit_work_order(work_order_no):
    """Edit an existing work order (NO INVENTORY ADJUSTMENTS EVER)"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()

    if request.method == "POST":
        try:
            # Update work order fields
            work_order.CustID = request.form.get("CustID")
            work_order.WOName = request.form.get("WOName")
            work_order.StorageTime = request.form.get("StorageTime")
            work_order.RackNo = request.form.get("RackNo")
            work_order.SpecialInstructions = request.form.get("SpecialInstructions")
            work_order.RepairsNeeded = request.form.get("RepairsNeeded")
            work_order.SeeRepair = request.form.get("SeeRepair")
            work_order.ReturnStatus = request.form.get("ReturnStatus")
            work_order.Quote = request.form.get("Quote")
            work_order.Clean = request.form.get("Clean")
            work_order.Treat = request.form.get("Treat")
            work_order.RushOrder = request.form.get("RushOrder", "0")
            work_order.DateRequired = request.form.get("DateRequired")
            work_order.ShipTo = request.form.get("ShipTo")
            work_order.FirmRush = request.form.get("FirmRush", "0")
            work_order.CleanFirstWO = request.form.get("CleanFirstWO")
            work_order.DateCompleted = request.form.get("DateCompleted")

            # Handle existing work order items (NO INVENTORY IMPACT)
            existing_items = WorkOrderItem.query.filter_by(
                WorkOrderNo=work_order_no
            ).all()

            # Get updated items from form
            updated_items = request.form.getlist("existing_item_key[]")
            updated_quantities = {}

            # Parse quantities for existing items
            for key, value in request.form.items():
                if key.startswith("existing_item_qty_"):
                    item_key = key.replace("existing_item_qty_", "")
                    if item_key in updated_items and value:
                        updated_quantities[item_key] = safe_int_conversion(value)

            # Update or remove existing items (NO INVENTORY CHANGES)
            for item in existing_items:
                item_key = f"{item.Description}_{item.Material}"
                if item_key in updated_items:
                    # Update quantity in work order only
                    if item_key in updated_quantities:
                        item.Qty = str(updated_quantities[item_key])
                else:
                    # Remove from work order only (catalog unchanged)
                    db.session.delete(item)

            # Handle new items being added to this work order
            new_item_descriptions = request.form.getlist("new_item_description[]")
            new_item_materials = request.form.getlist("new_item_material[]")
            new_item_quantities = request.form.getlist("new_item_qty[]")
            new_item_conditions = request.form.getlist("new_item_condition[]")
            new_item_colors = request.form.getlist("new_item_color[]")
            new_item_sizes = request.form.getlist("new_item_size[]")
            new_item_prices = request.form.getlist("new_item_price[]")

            for i, description in enumerate(new_item_descriptions):
                if description and i < len(new_item_materials):
                    work_order_qty = safe_int_conversion(
                        new_item_quantities[i] if i < len(new_item_quantities) else "1"
                    )

                    # Add to work order
                    work_order_item = WorkOrderItem(
                        WorkOrderNo=work_order_no,
                        CustID=work_order.CustID,
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Qty=str(work_order_qty),
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                        Price=new_item_prices[i] if i < len(new_item_prices) else "",
                    )
                    db.session.add(work_order_item)

                    # Add to catalog if new item type (same logic as create)
                    existing_inventory = Inventory.query.filter_by(
                        CustID=work_order.CustID,
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                    ).first()

                    if existing_inventory:
                        # Update catalog total
                        current_catalog_qty = safe_int_conversion(
                            existing_inventory.Qty
                        )
                        new_catalog_qty = current_catalog_qty + work_order_qty
                        existing_inventory.Qty = str(new_catalog_qty)
                    else:
                        # Add new to catalog
                        inventory_key = f"INV_{uuid.uuid4().hex[:8].upper()}"
                        new_inventory_item = Inventory(
                            InventoryKey=inventory_key,
                            CustID=work_order.CustID,
                            Description=description,
                            Material=new_item_materials[i]
                            if i < len(new_item_materials)
                            else "",
                            Condition=new_item_conditions[i]
                            if i < len(new_item_conditions)
                            else "",
                            Color=new_item_colors[i]
                            if i < len(new_item_colors)
                            else "",
                            SizeWgt=new_item_sizes[i]
                            if i < len(new_item_sizes)
                            else "",
                            Price=new_item_prices[i]
                            if i < len(new_item_prices)
                            else "",
                            Qty=str(work_order_qty),
                        )
                        db.session.add(new_inventory_item)

            db.session.commit()
            flash(f"Work Order {work_order_no} updated successfully!", "success")
            return redirect(
                url_for("work_orders.view_work_order", work_order_no=work_order_no)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating work order: {str(e)}", "error")

    # GET request - show the form with prefilled data
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()
    work_order_items = WorkOrderItem.query.filter_by(WorkOrderNo=work_order_no).all()

    return render_template(
        "work_orders/edit.html",
        work_order=work_order,
        work_order_items=work_order_items,
        customers=customers,
        sources=sources,
    )


@work_orders_bp.route("/api/next_wo_number")
@login_required
def get_next_wo_number():
    """Get the next work order number"""
    # Debug: see what's in your WorkOrderNo column
    sample_wos = db.session.query(WorkOrder.WorkOrderNo).limit(10).all()
    print("Sample WorkOrderNo values:", [wo.WorkOrderNo for wo in sample_wos])

    latest_num = db.session.query(
        func.max(cast(WorkOrder.WorkOrderNo, Integer))
    ).scalar()

    print("Latest num from query:", latest_num)

    if latest_num is not None:
        next_wo_no = str(latest_num + 1)
    else:
        next_wo_no = "1"

    print("Returning next_wo_no:", next_wo_no)
    return jsonify({"next_wo_number": next_wo_no})


def format_date_from_str(value):
    """
    Formats a datetime object or date string to YYYY-MM-DD format.
    Handles 'MM/DD/YY HH:MM:SS' strings from the database.
    """
    if not value:
        return None

    # Case 1: Value is already a datetime or date object.
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")

    # Case 2: Value is a string. We need to parse it first.
    if isinstance(value, str):
        try:
            # Try to parse the specific 'MM/DD/YY HH:MM:SS' format.
            dt_object = datetime.strptime(value, "%m/%d/%y %H:%M:%S")
            return dt_object.strftime("%Y-%m-%d")
        except ValueError:
            return value

    return None


@work_orders_bp.route("/api/work_orders")
@login_required
def api_work_orders():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()

    query = WorkOrder.query

    # Per-column filters
    for field in [
        "WorkOrderNo",
        "WOName",
        "CustID",
        "DateIn",
        "DateRequired",
        "Source",
    ]:
        filter_val = request.args.get(f"filter_{field}")
        if filter_val:
            if field in ["WorkOrderNo", "CustID"]:
                query = query.filter(getattr(WorkOrder, field) == filter_val)

            elif field == "Source":
                query = (
                    query.join(Customer)
                    .join(Source)
                    .filter(Source.SSource.ilike(f"%{filter_val}%"))
                )
            else:
                query = query.filter(getattr(WorkOrder, field).ilike(f"%{filter_val}%"))

    # Status quick filters
    if status == "pending":
        query = query.filter(
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
        )
    elif status == "completed":
        query = query.filter(
            WorkOrder.DateCompleted.isnot(None), WorkOrder.DateCompleted != ""
        )
    elif status == "rush":
        query = query.filter(
            or_(WorkOrder.RushOrder == "1", WorkOrder.FirmRush == "1"),
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
        )

    # Sorting
    order_by_clauses = []
    i = 0
    while True:
        field = request.args.get(f"sort[{i}][field]")
        if not field:
            break
        direction = request.args.get(f"sort[{i}][dir]", "asc")

        # Check for the special case of 'Source'
        if field == "Source":
            # Sort by the 'SSource' column on the 'Source' model via the 'Customer' model
            column_to_sort = Source.SSource
            if direction == "desc":
                order_by_clauses.append(column_to_sort.desc())
            else:
                order_by_clauses.append(column_to_sort.asc())

        else:
            # Handle all other fields on the WorkOrder model
            column = getattr(WorkOrder, field, None)
            if column:
                if field in ["WorkOrderNo", "CustID"]:
                    cast_column = cast(column, Integer)
                    if direction == "desc":
                        order_by_clauses.append(cast_column.desc())
                    else:
                        order_by_clauses.append(cast_column.asc())

                elif field in ["DateIn", "DateRequired"]:
                    cast_column = case(
                        (
                            column.op("~")(
                                "^[0-1][0-9]/[0-3][0-9]/[0-9]{2} [0-2][0-9]:[0-5][0-9]:[0-5][0-9]$"
                            ),
                            func.to_date(column, "MM/DD/YY HH24:MI:SS"),
                        ),
                        (
                            column.op("~")("^[0-2][0-9]{3}-[0-1][0-9]-[0-3][0-9]$"),
                            func.to_date(column, "YYYY-MM-DD"),
                        ),
                        else_=literal(None),
                    )
                    if direction == "desc":
                        order_by_clauses.append(cast_column.desc().nulls_last())
                    else:
                        order_by_clauses.append(cast_column.asc().nulls_last())
                else:
                    if direction == "desc":
                        order_by_clauses.append(column.desc())
                    else:
                        order_by_clauses.append(column.asc())
        i += 1

    if order_by_clauses:
        query = query.order_by(*order_by_clauses)
    else:
        query = query.order_by(WorkOrder.WorkOrderNo.desc())

    total = query.count()
    work_orders = query.paginate(page=page, per_page=size, error_out=False)

    data = [
        {
            "WorkOrderNo": wo.WorkOrderNo,
            "CustID": wo.CustID,
            "WOName": wo.WOName,
            "DateIn": format_date_from_str(wo.DateIn),
            "DateRequired": format_date_from_str(wo.DateRequired),
            "Source": wo.customer.source_info.SSource
            if wo.customer and wo.customer.source_info
            else None,
            "detail_url": url_for(
                "work_orders.view_work_order", work_order_no=wo.WorkOrderNo
            ),
            "customer_url": url_for("customers.customer_detail", customer_id=wo.CustID)
            if wo.customer
            else None,
        }
        for wo in work_orders.items
    ]

    return jsonify(
        {
            "data": data,
            "total": total,
            "last_page": work_orders.pages,
        }
    )


@work_orders_bp.route("/delete/<work_order_no>", methods=["POST"])
@login_required
def delete_work_order(work_order_no):
    """Delete a work order without adjusting inventory"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()
    try:
        # Delete all associated work order items
        for item in work_order.items:
            db.session.delete(item)

        # Delete the work order itself
        db.session.delete(work_order)
        db.session.commit()
        flash(f"Work Order {work_order_no} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting work order: {str(e)}", "danger")

    return redirect(url_for("work_orders.list_work_orders"))
