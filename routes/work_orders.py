from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.work_order import WorkOrder, WorkOrderItem
from models.customer import Customer
from models.source import Source
from sqlalchemy import or_, func, desc, cast, Integer, case, literal
from extensions import db
from datetime import datetime, date
from sqlalchemy.types import Date  # Generic SQLAlchemy Date type for PostgreSQL
from sqlalchemy.dialects.postgresql import dialect as pg_dialect

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


@work_orders_bp.route("/new", methods=["GET", "POST"])
@work_orders_bp.route("/new/<int:prefill_cust_id>", methods=["GET", "POST"])
@login_required
def create_work_order(prefill_cust_id=None):
    """Create a new work order"""
    if request.method == "POST":
        try:
            # Get the next work order number
            latest_wo = WorkOrder.query.order_by(desc(WorkOrder.WorkOrderNo)).first()
            if latest_wo:
                try:
                    # Extract numeric part and increment
                    latest_num = int(latest_wo.WorkOrderNo)
                    next_wo_no = str(latest_num + 1)
                except ValueError:
                    # If conversion fails, use a timestamp-based approach
                    next_wo_no = str(int(datetime.now().timestamp()))
            else:
                next_wo_no = "1"

            # Create the work order
            work_order = WorkOrder(
                WorkOrderNo=next_wo_no,
                CustID=request.form.get("CustID"),
                WOName=request.form.get("WOName"),
                Storage=request.form.get("Storage"),
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
            db.session.flush()  # Get the work order ID

            # Handle selected inventory items (from previous work orders)
            selected_items = request.form.getlist("selected_items[]")
            item_quantities = {}

            # Parse quantities for selected items
            for key, value in request.form.items():
                if key.startswith("item_qty_"):
                    item_id = key.replace("item_qty_", "")
                    if item_id in selected_items and value:
                        item_quantities[item_id] = value

            # Add selected inventory items to work order
            # Since we're using composite IDs from previous items, we need to parse them
            for item_id in selected_items:
                if item_id in item_quantities:
                    # Parse the composite ID to get item details
                    parts = item_id.split("_")
                    if len(parts) >= 3:
                        description = parts[0]
                        material = parts[1]

                        # Find the original item to get other details
                        original_item = WorkOrderItem.query.filter_by(
                            CustID=request.form.get("CustID"),
                            Description=description,
                            Material=material,
                        ).first()

                        if original_item:
                            work_order_item = WorkOrderItem(
                                WorkOrderNo=next_wo_no,
                                CustID=request.form.get("CustID"),
                                Description=original_item.Description,
                                Material=original_item.Material,
                                Qty=item_quantities[item_id],
                                Condition=original_item.Condition,
                                Color=original_item.Color,
                                SizeWgt=original_item.SizeWgt,
                                Price=original_item.Price,
                            )
                            db.session.add(work_order_item)

            # Handle new inventory items
            new_item_descriptions = request.form.getlist("new_item_description[]")
            new_item_materials = request.form.getlist("new_item_material[]")
            new_item_quantities = request.form.getlist("new_item_qty[]")
            new_item_conditions = request.form.getlist("new_item_condition[]")
            new_item_colors = request.form.getlist("new_item_color[]")
            new_item_sizes = request.form.getlist("new_item_size[]")
            new_item_prices = request.form.getlist("new_item_price[]")

            for i, description in enumerate(new_item_descriptions):
                if description and i < len(new_item_materials):
                    # Add directly to work order (no separate inventory table)
                    work_order_item = WorkOrderItem(
                        WorkOrderNo=next_wo_no,
                        CustID=request.form.get("CustID"),
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Qty=new_item_quantities[i]
                        if i < len(new_item_quantities)
                        else "1",
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                        Price=new_item_prices[i] if i < len(new_item_prices) else "",
                    )
                    db.session.add(work_order_item)

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

    # GET request - show the form
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    form_data = {}
    if prefill_cust_id:
        form_data["CustID"] = str(
            prefill_cust_id
        )  # convert to string for comparison in template

    return render_template(
        "work_orders/create.html",
        customers=customers,
        sources=sources,
        form_data=form_data,  # pass the prefilled data
    )


@work_orders_bp.route("/api/customer_inventory/<cust_id>")
@login_required
def get_customer_inventory(cust_id):
    """Get inventory items for a specific customer from previous work orders"""
    # Get distinct items from previous work orders for this customer
    items = (
        db.session.query(
            WorkOrderItem.Description,
            WorkOrderItem.Material,
            WorkOrderItem.Color,
            WorkOrderItem.Condition,
            WorkOrderItem.SizeWgt,
            WorkOrderItem.Price,
            func.max(WorkOrderItem.Qty).label("qty"),
        )
        .filter_by(CustID=cust_id)
        .group_by(
            WorkOrderItem.Description,
            WorkOrderItem.Material,
            WorkOrderItem.Color,
            WorkOrderItem.Condition,
            WorkOrderItem.SizeWgt,
            WorkOrderItem.Price,
        )
        .all()
    )

    return jsonify(
        [
            {
                "id": f"{item.Description}_{item.Material}_{i}",  # Create unique ID
                "description": item.Description or "",
                "material": item.Material or "",
                "color": item.Color or "",
                "condition": item.Condition or "",
                "size_wgt": item.SizeWgt or "",
                "price": item.Price or "",
                "qty": item.qty or "1",
            }
            for i, item in enumerate(items)
        ]
    )


@work_orders_bp.route("/api/next_wo_number")
@login_required
def get_next_wo_number():
    """Get the next work order number"""
    latest_num = db.session.query(
        func.max(cast(WorkOrder.WorkOrderNo, Integer))
    ).scalar()

    if latest_num is not None:
        next_wo_no = str(latest_num + 1)
    else:
        next_wo_no = "1"

    return jsonify({"next_wo_number": next_wo_no})


# Add this route to your work_orders_bp blueprint


@work_orders_bp.route("/edit/<work_order_no>", methods=["GET", "POST"])
@login_required
def edit_work_order(work_order_no):
    """Edit an existing work order"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()

    if request.method == "POST":
        try:
            # Update work order fields
            work_order.CustID = request.form.get("CustID")
            work_order.WOName = request.form.get("WOName")
            work_order.Storage = request.form.get("Storage")
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

            # Handle existing work order items
            # First, get all existing items for this work order
            existing_items = WorkOrderItem.query.filter_by(
                WorkOrderNo=work_order_no
            ).all()
            existing_item_ids = [
                item.id for item in existing_items if hasattr(item, "id")
            ]

            # Handle updated quantities for existing items
            updated_items = request.form.getlist("existing_item_id[]")
            updated_quantities = {}

            # Parse quantities for existing items
            for key, value in request.form.items():
                if key.startswith("existing_item_qty_"):
                    item_id = key.replace("existing_item_qty_", "")
                    if item_id in updated_items and value:
                        updated_quantities[item_id] = value

            # Update existing items that are still selected
            for item in existing_items:
                item_id_str = str(item.id) if hasattr(item, "id") else None
                if item_id_str and item_id_str in updated_items:
                    # Update quantity if provided
                    if item_id_str in updated_quantities:
                        item.Qty = updated_quantities[item_id_str]
                else:
                    # Remove items that are no longer selected
                    db.session.delete(item)

            # Handle selected inventory items (from previous work orders)
            selected_items = request.form.getlist("selected_items[]")
            item_quantities = {}

            # Parse quantities for selected items
            for key, value in request.form.items():
                if key.startswith("item_qty_"):
                    item_id = key.replace("item_qty_", "")
                    if item_id in selected_items and value:
                        item_quantities[item_id] = value

            # Add newly selected inventory items to work order
            for item_id in selected_items:
                if item_id in item_quantities:
                    # Parse the composite ID to get item details
                    parts = item_id.split("_")
                    if len(parts) >= 3:
                        description = parts[0]
                        material = parts[1]

                        # Find the original item to get other details
                        original_item = WorkOrderItem.query.filter_by(
                            CustID=work_order.CustID,
                            Description=description,
                            Material=material,
                        ).first()

                        if original_item:
                            # Check if this item already exists in current work order
                            existing_item = WorkOrderItem.query.filter_by(
                                WorkOrderNo=work_order_no,
                                Description=description,
                                Material=material,
                            ).first()

                            if not existing_item:
                                work_order_item = WorkOrderItem(
                                    WorkOrderNo=work_order_no,
                                    CustID=work_order.CustID,
                                    Description=original_item.Description,
                                    Material=original_item.Material,
                                    Qty=item_quantities[item_id],
                                    Condition=original_item.Condition,
                                    Color=original_item.Color,
                                    SizeWgt=original_item.SizeWgt,
                                    Price=original_item.Price,
                                )
                                db.session.add(work_order_item)

            # Handle new inventory items
            new_item_descriptions = request.form.getlist("new_item_description[]")
            new_item_materials = request.form.getlist("new_item_material[]")
            new_item_quantities = request.form.getlist("new_item_qty[]")
            new_item_conditions = request.form.getlist("new_item_condition[]")
            new_item_colors = request.form.getlist("new_item_color[]")
            new_item_sizes = request.form.getlist("new_item_size[]")
            new_item_prices = request.form.getlist("new_item_price[]")

            for i, description in enumerate(new_item_descriptions):
                if description and i < len(new_item_materials):
                    work_order_item = WorkOrderItem(
                        WorkOrderNo=work_order_no,
                        CustID=work_order.CustID,
                        Description=description,
                        Material=new_item_materials[i]
                        if i < len(new_item_materials)
                        else "",
                        Qty=new_item_quantities[i]
                        if i < len(new_item_quantities)
                        else "1",
                        Condition=new_item_conditions[i]
                        if i < len(new_item_conditions)
                        else "",
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                        Price=new_item_prices[i] if i < len(new_item_prices) else "",
                    )
                    db.session.add(work_order_item)

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

    # Get existing work order items
    work_order_items = WorkOrderItem.query.filter_by(WorkOrderNo=work_order_no).all()

    return render_template(
        "work_orders/edit.html",
        work_order=work_order,
        work_order_items=work_order_items,
        customers=customers,
        sources=sources,
    )


from datetime import datetime, date


def format_date_from_str(value):
    """
    Formats a datetime object or date string to YYYY-MM-DD format.
    Handles 'MM/DD/YY HH:MM:SS' strings from the database.
    """
    print(
        f"\n[DEBUG] format_date_from_str called with: {repr(value)} of type {type(value)}"
    )

    if not value:
        print("[DEBUG] Input value is None or empty. Returning None.")
        return None

    # Case 1: Value is already a datetime or date object.
    if isinstance(value, (datetime, date)):
        formatted_value = value.strftime("%Y-%m-%d")
        print(f"[DEBUG] Formatted datetime/date object. Returning: {formatted_value}")
        return formatted_value

    # Case 2: Value is a string. We need to parse it first.
    if isinstance(value, str):
        try:
            # Try to parse the specific 'MM/DD/YY HH:MM:SS' format.
            dt_object = datetime.strptime(value, "%m/%d/%y %H:%M:%S")
            formatted_value = dt_object.strftime("%Y-%m-%d")
            print(
                f"[DEBUG] Parsed and formatted custom string. Original: {value} -> Parsed: {dt_object} -> Returning: {formatted_value}"
            )
            return formatted_value
        except ValueError as e:
            # Log the error for debugging invalid formats
            print(
                f"[DEBUG] Failed to parse string '{value}' with format '%m/%d/%y %H:%M:%S'. Error: {e}. Returning original value: {value}"
            )
            return value

    # Case 3: Handle any other data types that might slip through.
    print(
        f"[DEBUG] Unhandled data type '{type(value)}' for value: {repr(value)}. Returning None."
    )
    return None


@work_orders_bp.route("/api/work_orders")
@login_required
def api_work_orders():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()

    # Debug: Log request parameters
    print(
        f"\n[DEBUG] API called with params: page={page}, size={size}, status={status}"
    )
    print(f"[DEBUG] All request args: {request.args}")

    query = WorkOrder.query

    # 🔎 Per-column filters
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
            print(f"[DEBUG] Applying filter on {field}: {filter_val}")
            if field == "Source":
                query = (
                    query.join(Customer)
                    .join(Source)
                    .filter(Source.SSource.ilike(f"%{filter_val}%"))
                )
            else:
                query = query.filter(getattr(WorkOrder, field).ilike(f"%{filter_val}%"))

    # ✅ Status quick filters
    if status == "pending":
        print("[DEBUG] Applying status filter: pending")
        query = query.filter(
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
        )
    elif status == "completed":
        print("[DEBUG] Applying status filter: completed")
        query = query.filter(
            WorkOrder.DateCompleted.isnot(None), WorkOrder.DateCompleted != ""
        )
    elif status == "rush":
        print("[DEBUG] Applying status filter: rush")
        query = query.filter(
            or_(WorkOrder.RushOrder == "1", WorkOrder.FirmRush == "1"),
            or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == ""),
        )

    # Debug: Sample raw dates from DB
    sample_query = query.limit(5).all()
    print("\n[DEBUG] Raw date samples from DB:")
    for wo in sample_query:
        print(
            f"[DEBUG] WorkOrderNo={wo.WorkOrderNo}: DateIn={repr(wo.DateIn)}, DateRequired={repr(wo.DateRequired)}"
        )

    # Debug: Check for non-standard DateIn and DateRequired values
    for field in ["DateIn", "DateRequired"]:
        invalid_date_query = (
            WorkOrder.query.filter(
                ~getattr(WorkOrder, field).op("~")(
                    "^[0-1][0-9]/[0-3][0-9]/[0-9]{2} [0-2][0-9]:[0-5][0-9]:[0-5][0-9]$"
                ),
                getattr(WorkOrder, field).isnot(None),
            )
            .limit(5)
            .all()
        )
        if invalid_date_query:
            print(f"\n[DEBUG] Non-standard {field} values detected:")
            for wo in invalid_date_query:
                print(
                    f"[DEBUG] WorkOrderNo={wo.WorkOrderNo}: {field}={repr(getattr(wo, field))}"
                )

    # ↕️ Sorting
    order_by_clauses = []
    i = 0
    while True:
        field = request.args.get(f"sort[{i}][field]")
        if not field:
            break
        direction = request.args.get(f"sort[{i}][dir]", "asc")
        column = getattr(WorkOrder, field, None)
        print(
            f"[DEBUG] Processing sort parameter: field={field}, direction={direction}"
        )

        if column:
            print(f"[DEBUG] Building sort for field={field}, direction={direction}")
            if field in ["DateIn", "DateRequired"]:
                # Use CASE to try multiple date formats
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
                    else_=literal(None),  # Invalid formats sort as NULL
                )
                print(
                    f"[DEBUG] Using PostgreSQL CASE with to_date for {field} (MM/DD/YY HH24:MI:SS and YYYY-MM-DD)"
                )
                if direction == "desc":
                    order_by_clauses.append(cast_column.desc().nulls_last())
                    print(f"[DEBUG] Sorting {field} DESC with NULLS LAST")
                else:
                    order_by_clauses.append(cast_column.asc().nulls_last())
                    print(f"[DEBUG] Sorting {field} ASC with NULLS LAST")
            else:
                print(f"[DEBUG] Using standard sorting for {field}")
                if direction == "desc":
                    order_by_clauses.append(column.desc())
                else:
                    order_by_clauses.append(column.asc())
        else:
            print(f"[DEBUG] Invalid sort field: {field}")
        i += 1

    if order_by_clauses:
        print(f"[DEBUG] Applying order_by clauses: {order_by_clauses}")
        query = query.order_by(*order_by_clauses)
    else:
        print("[DEBUG] No custom sort; defaulting to WorkOrderNo DESC")
        query = query.order_by(WorkOrder.WorkOrderNo.desc())

    # Debug: Log compiled SQL query safely
    try:
        if query.session.bind:
            compiled_query = query.statement.compile(dialect=query.session.bind.dialect)
            print(f"\n[DEBUG] Compiled SQL query: {compiled_query}")
            print(f"[DEBUG] Query params: {compiled_query.params}")
        else:
            print(
                "[DEBUG] No database bind available; using PostgreSQL dialect for compilation"
            )
            compiled_query = query.statement.compile(dialect=pg_dialect())
            print(f"[DEBUG] Compiled SQL query (fallback): {compiled_query}")
            print(f"[DEBUG] Query params (fallback): {compiled_query.params}")
    except Exception as e:
        print(f"[DEBUG] Failed to compile query: {e}")

    total = query.count()
    work_orders = query.paginate(page=page, per_page=size, error_out=False)

    # Debug: Sample formatted output
    print("\n[DEBUG] Formatted output samples (first 3):")
    for wo in work_orders.items[:3]:
        print(
            f"[DEBUG] WorkOrderNo={wo.WorkOrderNo}: Formatted DateIn={format_date_from_str(wo.DateIn)}, DateRequired={format_date_from_str(wo.DateRequired)}"
        )

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
