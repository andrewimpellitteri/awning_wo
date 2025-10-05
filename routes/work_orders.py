from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    send_file,
    abort,
)
from flask_login import login_required
from models.work_order import WorkOrder, WorkOrderItem
from models.customer import Customer
from models.source import Source
from models.inventory import Inventory
from models.work_order_file import WorkOrderFile
from utils.file_upload import (
    save_work_order_file,
    generate_presigned_url,
    get_file_size,
)
from sqlalchemy import or_, func, cast, Integer, case, literal
from extensions import db
from datetime import datetime, date
import uuid
from work_order_pdf import generate_work_order_pdf
from decorators import role_required

work_orders_bp = Blueprint("work_orders", __name__, url_prefix="/work_orders")


@work_orders_bp.route("/<work_order_no>/files/upload", methods=["POST"])
@login_required
def upload_work_order_file(work_order_no):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    saved_file = save_work_order_file(work_order_no, file)
    if saved_file:
        return jsonify(
            {"message": "File uploaded successfully", "file_id": saved_file.id}
        )
    return jsonify({"error": "Invalid file type"}), 400


@work_orders_bp.route("/<work_order_no>/files/<int:file_id>/download")
@login_required
def download_work_order_file(work_order_no, file_id):
    """
    Download a file attached to a work order.
    Supports local files or S3 files (via pre-signed URLs).
    """
    wo_file = WorkOrderFile.query.filter_by(
        id=file_id, WorkOrderNo=work_order_no
    ).first()

    if not wo_file:
        abort(404, description="File not found for this work order.")

    if wo_file.file_path.startswith("s3://"):
        # S3 file → redirect to pre-signed URL
        presigned_url = generate_presigned_url(wo_file.file_path)
        return redirect(presigned_url)

    # Local file → serve directly
    return send_file(
        wo_file.file_path,
        as_attachment=True,
        download_name=wo_file.filename,
    )


@work_orders_bp.route("/thumbnail/<int:file_id>")
@login_required
def get_thumbnail(file_id):
    """Serve thumbnail for a work order file"""
    try:
        # Get the file record
        wo_file = WorkOrderFile.query.get_or_404(file_id)

        if wo_file.thumbnail_path:
            if wo_file.thumbnail_path.startswith("s3://"):
                # Generate presigned URL for S3 thumbnail
                thumbnail_url = generate_presigned_url(
                    wo_file.thumbnail_path, expires_in=3600
                )
                return redirect(thumbnail_url)
            else:
                # Serve local thumbnail
                return send_file(wo_file.thumbnail_path)
        else:
            # No thumbnail available, return a default icon or 404
            abort(404)

    except Exception as e:
        print(f"Error serving thumbnail for file {file_id}: {e}")
        abort(404)


# Add this to your template context
@work_orders_bp.context_processor
def utility_processor():
    return dict(get_file_size=get_file_size)


@work_orders_bp.route("/<work_order_no>/files")
@login_required
def list_work_order_files(work_order_no):
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()
    files = [
        {"id": f.id, "filename": f.filename, "uploaded": f.uploaded_at.isoformat()}
        for f in work_order.files
    ]
    return jsonify(files)


def assign_queue_position_to_new_work_order(work_order):
    """Assign queue position to a newly created work order"""
    if work_order.QueuePosition is not None:
        return  # Already has a position

    try:
        # Get the highest existing queue position for incomplete work orders
        base_filter = WorkOrder.DateCompleted.is_(None)
        max_position = (
            db.session.query(func.max(WorkOrder.QueuePosition))
            .filter(base_filter)
            .scalar()
            or 0
        )

        # Assign the next position
        work_order.QueuePosition = max_position + 1
        print(
            f"Assigned queue position {work_order.QueuePosition} to work order {work_order.WorkOrderNo}"
        )

    except Exception as e:
        print(f"Error assigning queue position to new work order: {e}")
        # Fallback: assign position 1 if something goes wrong
        work_order.QueuePosition = 1


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
    work_order = (
        WorkOrder.query.filter_by(WorkOrderNo=work_order_no)
        .options(db.joinedload(WorkOrder.files))  # eager load for safety
        .first_or_404()
    )
    return render_template(
        "work_orders/detail.html",
        work_order=work_order,
        files=work_order.files,  # pass files explicitly
    )


@work_orders_bp.route("/status/<status>")
def list_by_status(status):
    """Filter work orders by completion status using DateCompleted"""
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Pending = DateCompleted is NULL
    if status.upper() == "PENDING":
        query = WorkOrder.query.filter(WorkOrder.DateCompleted.is_(None))
    # Completed = DateCompleted has a value
    elif status.upper() == "COMPLETED":
        query = WorkOrder.query.filter(WorkOrder.DateCompleted.isnot(None))
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
        or_(WorkOrder.RushOrder == True, WorkOrder.FirmRush == True),
        WorkOrder.DateCompleted.is_(None),
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


def safe_int_conversion(value):
    """
    Safely convert a value to integer, handling various input types
    """
    if value is None or value == "":
        return 1  # Default to 1 if empty

    try:
        # Handle string inputs
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return 1

        # Convert to float first, then int (handles decimal strings like "1.0")
        float_val = float(value)
        int_val = int(float_val)

        # Ensure positive value
        return max(1, int_val)

    except (ValueError, TypeError):
        print(f"Warning: Could not convert '{value}' to integer, defaulting to 1")
        return 1


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
@role_required("admin", "manager")
def create_work_order(prefill_cust_id=None):
    """Create a new work order - inventory quantities never change"""
    if request.method == "POST":
        try:
            # --- Generate next WorkOrderNo ---
            latest_num = db.session.query(
                func.max(cast(WorkOrder.WorkOrderNo, Integer))
            ).scalar()
            next_wo_no = str(latest_num + 1) if latest_num is not None else "1"

            print("--- Form Data Received ---")
            print(f"Request Form Keys: {request.form.keys()}")
            print(f"Selected Items: {request.form.getlist('selected_items[]')}")
            print(
                f"New Item Descriptions: {request.form.getlist('new_item_description[]')}"
            )

            # --- Create Work Order ---
            work_order = WorkOrder(
                WorkOrderNo=next_wo_no,
                CustID=request.form.get("CustID"),
                WOName=request.form.get("WOName"),
                StorageTime=request.form.get("StorageTime"),
                RackNo=request.form.get("RackNo"),
                SpecialInstructions=request.form.get("SpecialInstructions"),
                RepairsNeeded=request.form.get("RepairsNeeded"),
                # Boolean fields - checkbox present = True
                SeeRepair="SeeRepair" in request.form,
                Quote="Quote" in request.form,
                RushOrder="RushOrder" in request.form,
                FirmRush="FirmRush" in request.form,
                # Date fields - convert from string or use defaults
                DateIn=datetime.strptime(request.form.get("DateIn"), "%Y-%m-%d").date() if request.form.get("DateIn") else date.today(),
                DateRequired=datetime.strptime(request.form.get("DateRequired"), "%Y-%m-%d").date() if request.form.get("DateRequired") else None,
                Clean=datetime.strptime(request.form.get("Clean"), "%Y-%m-%d").date() if request.form.get("Clean") else None,
                Treat=datetime.strptime(request.form.get("Treat"), "%Y-%m-%d").date() if request.form.get("Treat") else None,
                # String fields
                ReturnStatus=request.form.get("ReturnStatus"),
                ShipTo=request.form.get("ShipTo"),
                CleanFirstWO=request.form.get("CleanFirstWO"),
            )
            db.session.add(work_order)
            db.session.flush()  # ensures parent exists in DB for FK references

            # --- Handle Selected Inventory Items ---
            selected_items = request.form.getlist("selected_items[]")
            item_quantities = {
                key.replace("item_qty_", ""): safe_int_conversion(value)
                for key, value in request.form.items()
                if key.startswith("item_qty_") and value
            }

            for inventory_key in selected_items:
                requested_qty = item_quantities.get(inventory_key, 1)
                inventory_item = Inventory.query.get(inventory_key)
                if inventory_item:
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

            # --- Handle New Inventory Items ---
            new_item_descriptions = request.form.getlist("new_item_description[]")
            new_item_materials = request.form.getlist("new_item_material[]")
            new_item_quantities = request.form.getlist("new_item_qty[]")
            new_item_conditions = request.form.getlist("new_item_condition[]")
            new_item_colors = request.form.getlist("new_item_color[]")
            new_item_sizes = request.form.getlist("new_item_size[]")
            new_item_prices = request.form.getlist("new_item_price[]")

            for i, description in enumerate(new_item_descriptions):
                if not description:
                    continue

                work_order_qty = safe_int_conversion(
                    new_item_quantities[i] if i < len(new_item_quantities) else "1"
                )

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

                # Update or insert into inventory catalog
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
                    existing_inventory.Qty = str(
                        safe_int_conversion(existing_inventory.Qty) + work_order_qty
                    )
                    flash(
                        f"Updated catalog: Customer now has {existing_inventory.Qty} total of '{description}'",
                        "info",
                    )
                else:
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
                        Color=new_item_colors[i] if i < len(new_item_colors) else "",
                        SizeWgt=new_item_sizes[i] if i < len(new_item_sizes) else "",
                        Price=new_item_prices[i] if i < len(new_item_prices) else "",
                        Qty=str(work_order_qty),
                    )
                    db.session.add(new_inventory_item)
                    flash(
                        f"New item '{description}' added to catalog with quantity {work_order_qty}",
                        "success",
                    )

            uploaded_files = []
            if "files[]" in request.files:
                files = request.files.getlist("files[]")
                print(f"Processing {len(files)} files")

                for i, file in enumerate(files):
                    if file and file.filename:
                        # Use the no-commit version for batch processing
                        wo_file = save_work_order_file(
                            next_wo_no, file, to_s3=True, generate_thumbnails=True
                        )
                        if not wo_file:
                            raise Exception(f"Failed to process file: {file.filename}")

                        uploaded_files.append(wo_file)
                        db.session.add(wo_file)  # Add to session but don't commit yet
                        print(f"Prepared file {i + 1}/{len(files)}: {wo_file.filename}")

                        # Log thumbnail info
                        if wo_file.thumbnail_path:
                            print(f"  - Thumbnail generated: {wo_file.thumbnail_path}")

            # --- Final Commit (everything at once) ---
            db.session.commit()

            flash(
                f"Work Order {next_wo_no} created successfully with {len(uploaded_files)} files!",
                "success",
            )
            return redirect(
                url_for("work_orders.view_work_order", work_order_no=next_wo_no)
            )

        except Exception as e:
            db.session.rollback()
            print(f"Error creating work order: {str(e)}")
            flash(f"Error creating work order: {str(e)}", "error")
            return render_template(
                "work_orders/create.html",
                customers=Customer.query.all(),
                sources=Source.query.all(),
                form_data=request.form,
            )

    # --- GET Request: Render Form ---
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    form_data = {}
    if prefill_cust_id:
        customer = Customer.query.get(str(prefill_cust_id))
        if customer:
            form_data["CustID"] = str(prefill_cust_id)
            form_data["WOName"] = customer.Name
            if customer.Source:
                form_data["ShipTo"] = customer.Source

    return render_template(
        "work_orders/create.html",
        customers=customers,
        sources=sources,
        form_data=form_data,
    )


@work_orders_bp.route("/edit/<work_order_no>", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
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
            work_order.ReturnStatus = request.form.get("ReturnStatus")
            work_order.ShipTo = request.form.get("ShipTo")
            work_order.CleanFirstWO = request.form.get("CleanFirstWO")

            # Boolean fields - checkbox present = True
            work_order.SeeRepair = "SeeRepair" in request.form
            work_order.Quote = "Quote" in request.form
            work_order.RushOrder = "RushOrder" in request.form
            work_order.FirmRush = "FirmRush" in request.form

            # Date fields - convert from string
            date_required_str = request.form.get("DateRequired")
            work_order.DateRequired = datetime.strptime(date_required_str, "%Y-%m-%d").date() if date_required_str else None

            clean_str = request.form.get("Clean")
            work_order.Clean = datetime.strptime(clean_str, "%Y-%m-%d").date() if clean_str else None

            treat_str = request.form.get("Treat")
            work_order.Treat = datetime.strptime(treat_str, "%Y-%m-%d").date() if treat_str else None

            date_completed_str = request.form.get("DateCompleted")
            work_order.DateCompleted = datetime.strptime(date_completed_str, "%Y-%m-%d") if date_completed_str else None

            # Handle existing work order items (NO INVENTORY IMPACT)
            existing_items = WorkOrderItem.query.filter_by(
                WorkOrderNo=work_order_no
            ).all()

            # Get updated items from form
            updated_items = request.form.getlist("existing_item_key[]")
            updated_quantities = {}
            updated_prices = {}

            # Parse quantities for existing items
            for key, value in request.form.items():
                if key.startswith("existing_item_qty_"):
                    item_key = key.replace("existing_item_qty_", "")
                    if item_key in updated_items and value:
                        updated_quantities[item_key] = safe_int_conversion(value)
                elif key.startswith("existing_item_price_"):
                    item_key = key.replace("existing_item_price_", "")
                    if item_key in updated_items and value:
                        try:
                            updated_prices[item_key] = float(value)
                        except ValueError:
                            updated_prices[item_key] = 0.0  # fallback if invalid input

            # Update or remove existing items (NO INVENTORY CHANGES)
            for item in existing_items:
                item_key = f"{item.Description}_{item.Material}"
                if item_key in updated_items:
                    # Update quantity in work order only
                    if item_key in updated_quantities:
                        item.Qty = str(updated_quantities[item_key])
                    # Update price
                    if item_key in updated_prices:
                        item.Price = updated_prices[item_key]
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


@work_orders_bp.route("/cleaning-room/edit/<work_order_no>", methods=["GET", "POST"])
@role_required("user")
def cleaning_room_edit_work_order(work_order_no):
    """Restricted edit for cleaning room staff - can only edit Clean, Treat, and SpecialInstructions"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()

    if request.method == "POST":
        try:
            # Only allow updating Clean, Treat, and SpecialInstructions
            clean_str = request.form.get("Clean")
            work_order.Clean = datetime.strptime(clean_str, "%Y-%m-%d").date() if clean_str else None

            treat_str = request.form.get("Treat")
            work_order.Treat = datetime.strptime(treat_str, "%Y-%m-%d").date() if treat_str else None

            work_order.SpecialInstructions = request.form.get("SpecialInstructions")

            # Set ProcessingStatus based on form checkbox
            in_progress = request.form.get("ProcessingStatus") == "on"
            work_order.ProcessingStatus = in_progress

            # Reset ProcessingStatus if Treat date is set
            if work_order.Treat:
                work_order.ProcessingStatus = False

            uploaded_files = []
            if "files[]" in request.files:
                files = request.files.getlist("files[]")
                print(f"Processing {len(files)} files")

                for i, file in enumerate(files):
                    if file and file.filename:
                        # Use the no-commit version for batch processing
                        wo_file = save_work_order_file(
                            work_order_no, file, to_s3=True, generate_thumbnails=True
                        )
                        if not wo_file:
                            raise Exception(f"Failed to process file: {file.filename}")

                        uploaded_files.append(wo_file)
                        db.session.add(wo_file)  # Add to session but don't commit yet
                        print(f"Prepared file {i + 1}/{len(files)}: {wo_file.filename}")

                        # Log thumbnail info
                        if wo_file.thumbnail_path:
                            print(f"  - Thumbnail generated: {wo_file.thumbnail_path}")

            db.session.commit()
            flash(
                f"Work Order {work_order_no} (cleaning room update) saved successfully!",
                "success",
            )
            return redirect(
                url_for("work_orders.view_work_order", work_order_no=work_order_no)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating work order: {str(e)}", "error")

    # GET request - show limited edit form
    return render_template(
        "work_orders/cleaning_room_edit.html",
        work_order=work_order,
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

    # Start with base query
    query = WorkOrder.query

    # Flag to check if we need to join the customer and source tables
    needs_source_join = False

    # Check for filters and sorting on the 'Source' field
    if request.args.get("filter_Source") or any(
        request.args.get(f"sort[{i}][field]") == "Source" for i in range(5)
    ):
        needs_source_join = True

    # Apply joins if needed for Source filtering or sorting
    if needs_source_join:
        query = query.join(Customer).join(Source)

    # --- Start of Filter Logic ---
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
            filter_val = filter_val.strip()

            if field == "WorkOrderNo":
                # Handle range or exact match with casting
                if "-" in filter_val:
                    try:
                        start, end = map(
                            int, filter_val.split("-", 1)
                        )  # Only split on first dash
                        query = query.filter(
                            cast(WorkOrder.WorkOrderNo, Integer) >= start,
                            cast(WorkOrder.WorkOrderNo, Integer) <= end,
                        )
                    except ValueError:
                        # If parsing fails, ignore this filter
                        pass
                else:
                    try:
                        val = int(filter_val)
                        query = query.filter(
                            cast(WorkOrder.WorkOrderNo, Integer) == val
                        )
                    except ValueError:
                        # If parsing fails, ignore this filter
                        pass

            elif field == "CustID":
                # exact match only
                try:
                    val = int(filter_val)
                    query = query.filter(WorkOrder.CustID == val)
                except ValueError:
                    pass

            elif field == "Source":
                # Filter on the correct column from the joined table
                query = query.filter(Source.SSource.ilike(f"%{filter_val}%"))

            else:
                # For other text fields (WOName, DateIn, DateRequired)
                query = query.filter(getattr(WorkOrder, field).ilike(f"%{filter_val}%"))

    # Status quick filters
    if status == "pending":
        query = query.filter(WorkOrder.DateCompleted.is_(None))
    elif status == "completed":
        query = query.filter(WorkOrder.DateCompleted.isnot(None))
    elif status == "rush":
        query = query.filter(
            or_(WorkOrder.RushOrder == True, WorkOrder.FirmRush == True),
            WorkOrder.DateCompleted.is_(None),
        )
    # --- End of Filter Logic ---

    # --- Start of Sorting Logic ---
    order_by_clauses = []
    i = 0
    while True:
        field = request.args.get(f"sort[{i}][field]")
        if not field:
            break
        direction = request.args.get(f"sort[{i}][dir]", "asc")

        # Handle the special case of 'Source'
        if field == "Source":
            # The query is already joined, so we can sort on the joined table's column
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
                    # These are proper DATE types in the database, sort them directly
                    # No need for regex parsing or to_date conversion
                    if direction == "desc":
                        order_by_clauses.append(column.desc().nulls_last())
                    else:
                        order_by_clauses.append(column.asc().nulls_last())
                else:
                    if direction == "desc":
                        order_by_clauses.append(column.desc())
                    else:
                        order_by_clauses.append(column.asc())
        i += 1

    # Apply sorting
    if order_by_clauses:
        query = query.order_by(*order_by_clauses)
    else:
        query = query.order_by(WorkOrder.WorkOrderNo.desc())
    # --- End of Sorting Logic ---

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
            "edit_url": url_for(
                "work_orders.edit_work_order", work_order_no=wo.WorkOrderNo
            ),
            "delete_url": url_for(
                "work_orders.delete_work_order", work_order_no=wo.WorkOrderNo
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
@role_required("admin", "manager")
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


@work_orders_bp.route("/<work_order_no>/pdf/download")
@login_required
def download_work_order_pdf(work_order_no):
    """download PDF in browser for a work order"""
    # Fetch work order + relationships in one query
    work_order = (
        WorkOrder.query.filter_by(WorkOrderNo=work_order_no)
        .options(
            db.joinedload(WorkOrder.customer), db.joinedload(WorkOrder.ship_to_source)
        )
        .first_or_404()
    )

    # Base dict from work order
    wo_dict = work_order.to_dict()

    # Enrich with customer info
    if work_order.customer:
        wo_dict["customer"] = work_order.customer.to_dict()
        wo_dict["customer"]["PrimaryPhone"] = work_order.customer.get_primary_phone()
        wo_dict["customer"]["FullAddress"] = work_order.customer.get_full_address()
        wo_dict["customer"]["MailingAddress"] = (
            work_order.customer.get_mailing_address()
        )

    if work_order.customer and work_order.customer.Source:
        wo_dict["source"] = {
            "Name": work_order.customer.Source,
            "FullAddress": " ".join(
                filter(
                    None,
                    [
                        work_order.customer.SourceAddress,
                        work_order.customer.SourceCity,
                        work_order.customer.SourceState,
                        work_order.customer.SourceZip,
                    ],
                )
            ).strip(),
        }
    else:
        # fallback to ShipTo relationship if no customer.Source
        if work_order.ship_to_source:
            wo_dict["source"] = work_order.ship_to_source.to_dict()
        else:
            wo_dict["source"] = {
                "Name": work_order.ShipTo or "",
                "FullAddress": "",
                "Phone": "",
                "Email": "",
            }

    print(wo_dict)

    try:
        pdf_buffer = generate_work_order_pdf(
            wo_dict,
            company_info={
                "name": "Awning Cleaning Industries - In House Cleaning Work Order"
            },
        )

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"WorkOrder_{work_order_no}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        return redirect(
            url_for("work_orders.view_work_order", work_order_no=work_order_no)
        )


@work_orders_bp.route("/<work_order_no>/pdf/view")
@login_required
def view_work_order_pdf(work_order_no):
    """View PDF in browser for a work order"""
    # Fetch work order + relationships in one query
    work_order = (
        WorkOrder.query.filter_by(WorkOrderNo=work_order_no)
        .options(
            db.joinedload(WorkOrder.customer), db.joinedload(WorkOrder.ship_to_source)
        )
        .first_or_404()
    )

    # Base dict from work order
    wo_dict = work_order.to_dict()

    # Enrich with customer info
    if work_order.customer:
        wo_dict["customer"] = work_order.customer.to_dict()
        wo_dict["customer"]["PrimaryPhone"] = work_order.customer.get_primary_phone()
        wo_dict["customer"]["FullAddress"] = work_order.customer.get_full_address()
        wo_dict["customer"]["MailingAddress"] = (
            work_order.customer.get_mailing_address()
        )

    if work_order.ship_to_source:
        wo_dict["source"] = work_order.ship_to_source.to_dict()
        wo_dict["source"]["FullAddress"] = work_order.ship_to_source.get_full_address()
        wo_dict["source"]["Phone"] = work_order.ship_to_source.clean_phone()
        wo_dict["source"]["Email"] = work_order.ship_to_source.clean_email()

    else:
        # fallback if the relationship is broken / missing
        wo_dict["source"] = {
            "Name": work_order.ShipTo or "",
            "FullAddress": "",
            "Phone": "",
            "Email": "",
        }

    print(wo_dict)

    try:
        pdf_buffer = generate_work_order_pdf(
            wo_dict,
            company_info={
                "name": "Awning Cleaning Industries - In House Cleaning Work Order"
            },
        )

        return send_file(
            pdf_buffer,
            as_attachment=False,
            download_name=f"WorkOrder_{work_order_no}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        return redirect(
            url_for("work_orders.view_work_order", work_order_no=work_order_no)
        )
