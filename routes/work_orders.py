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
from models.repair_order import RepairWorkOrder
from models.work_order_file import WorkOrderFile
from utils.file_upload import (
    save_work_order_file,
    generate_presigned_url,
    get_file_size,
    commit_deferred_uploads,
    cleanup_deferred_files,
)
from sqlalchemy import or_, func, cast, Integer
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from extensions import db
from datetime import datetime, date
import time
import random
from utils.work_order_pdf import generate_work_order_pdf
from decorators import role_required
from utils.pdf_helpers import prepare_order_data_for_pdf
from utils.query_helpers import (
    apply_column_filters,
    apply_tabulator_sorting,
)
from utils.form_helpers import extract_work_order_fields
from utils.order_item_helpers import (
    process_selected_inventory_items,
    process_new_items,
    safe_int_conversion,
    safe_price_conversion,
)
from io import BytesIO
import fitz  # PyMuPDF

work_orders_bp = Blueprint("work_orders", __name__, url_prefix="/work_orders")


# ============================================================================
# PRIVATE HELPER FUNCTIONS FOR WORK ORDER CREATE/EDIT
# ============================================================================


def _parse_date_field(date_str):
    """
    Parse a date string to a date object.
    Returns None if empty or invalid.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _update_work_order_fields(work_order, form_data):
    """
    Update work order fields from form data.
    Handles all basic fields, dates, and boolean checkboxes.
    """
    work_order.CustID = form_data.get("CustID")
    work_order.WOName = form_data.get("WOName")
    work_order.StorageTime = form_data.get("StorageTime")
    work_order.RackNo = form_data.get("RackNo")
    work_order.final_location = form_data.get("final_location")
    work_order.SpecialInstructions = form_data.get("SpecialInstructions")
    work_order.RepairsNeeded = "RepairsNeeded" in form_data
    work_order.ReturnStatus = form_data.get("ReturnStatus")
    work_order.ReturnTo = form_data.get("ReturnTo")
    work_order.ShipTo = form_data.get("ShipTo")
    work_order.SeeRepair = form_data.get("SeeRepair")
    work_order.Quote = form_data.get("Quote")
    work_order.RushOrder = "RushOrder" in form_data
    work_order.FirmRush = "FirmRush" in form_data

    # Parse date fields
    work_order.DateRequired = _parse_date_field(form_data.get("DateRequired"))
    work_order.Clean = _parse_date_field(form_data.get("Clean"))
    work_order.Treat = _parse_date_field(form_data.get("Treat"))

    # Parse DateCompleted as datetime
    date_completed_str = form_data.get("DateCompleted")
    if date_completed_str not in (None, "", "null"):
        try:
            work_order.DateCompleted = datetime.strptime(date_completed_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            work_order.DateCompleted = None
    else:
        work_order.DateCompleted = None

    # Set ProcessingStatus based on Clean date
    if work_order.Clean:
        work_order.ProcessingStatus = False


def _handle_file_uploads(files_list, work_order_no):
    """
    Process file uploads for a work order.
    Returns list of WorkOrderFile objects to add to session.

    Uses deferred S3 upload to prevent orphaned files if DB commit fails.
    Files are staged in memory and uploaded to S3 only after successful DB commit.
    """
    uploaded_files = []
    if not files_list:
        return uploaded_files

    for i, file in enumerate(files_list):
        if not file or not file.filename:
            continue

        # Use defer_s3_upload=True to prevent orphaned S3 files
        wo_file = save_work_order_file(
            work_order_no,
            file,
            to_s3=True,
            generate_thumbnails=True,
            defer_s3_upload=True,
        )
        if not wo_file:
            raise Exception(f"Failed to process file: {file.filename}")

        uploaded_files.append(wo_file)
        print(
            f"Prepared file {i + 1}/{len(files_list)}: {wo_file.filename} (deferred upload)"
        )

        if wo_file.thumbnail_path:
            print(
                f"  - Thumbnail prepared for deferred upload: {wo_file.thumbnail_path}"
            )

    return uploaded_files


def _handle_see_repair_backlink(work_order_no, new_repair_no, old_repair_no=None):
    """
    Manage SeeRepair backlink between work orders and repair orders.
    Removes old backlink if changed, adds new backlink if provided.
    Returns a flash message if a new link was created.

    Note: Only creates backlinks for numeric repair order numbers.
    Text values in SeeRepair are ignored for backlinking.
    Will not overwrite existing SEECLEAN values (which may contain text notes).
    """
    flash_message = None

    def _is_numeric(value):
        """Check if a value is numeric (repair order number) vs text (note)."""
        if not value:
            return False
        try:
            float(str(value).strip())
            return True
        except (ValueError, TypeError):
            return False

    # If SeeRepair changed, update backlinks
    if new_repair_no != old_repair_no:
        # Remove old backlink if it existed and was numeric
        if old_repair_no and _is_numeric(old_repair_no):
            old_repair = RepairWorkOrder.query.filter_by(
                RepairOrderNo=old_repair_no
            ).first()
            if old_repair and old_repair.SEECLEAN == work_order_no:
                old_repair.SEECLEAN = None

        # Add new backlink if provided and is numeric (repair order number)
        if new_repair_no and new_repair_no.strip() and _is_numeric(new_repair_no):
            new_repair = RepairWorkOrder.query.filter_by(
                RepairOrderNo=new_repair_no.strip()
            ).first()
            if new_repair:
                # Only set backlink if SEECLEAN is empty or already points to this WO
                # Don't overwrite text notes like "can't be cleaned"
                if not new_repair.SEECLEAN or new_repair.SEECLEAN == work_order_no:
                    new_repair.SEECLEAN = work_order_no
                    flash_message = (
                        f"Auto-linked Repair Order {new_repair_no} to this Work Order"
                    )
                elif _is_numeric(new_repair.SEECLEAN):
                    # SEECLEAN already has a different WO number - allow overwrite
                    new_repair.SEECLEAN = work_order_no
                    flash_message = (
                        f"Auto-linked Repair Order {new_repair_no} to this Work Order "
                        f"(replaced previous link to WO {new_repair.SEECLEAN})"
                    )
                # else: SEECLEAN has a text note - don't overwrite it

    return flash_message


def _update_existing_work_order_items(work_order_no, form_data):
    """
    Update existing work order items based on form data.
    Handles quantity/price updates and item deletions.
    Returns list of flash messages for removed items.
    """
    flash_messages = []
    existing_items = WorkOrderItem.query.filter_by(WorkOrderNo=work_order_no).all()

    # Get the IDs of items that should remain in the work order from the form
    updated_item_ids = set(form_data.getlist("existing_item_id[]"))

    # Parse updated quantities and prices, keyed by item ID
    updated_quantities = {}
    updated_prices = {}
    for key, value in form_data.items():
        if key.startswith("existing_item_qty_"):
            item_id = key.replace("existing_item_qty_", "")
            if value:
                updated_quantities[item_id] = safe_int_conversion(value)
        elif key.startswith("existing_item_price_"):
            item_id = key.replace("existing_item_price_", "")
            # Use safe_price_conversion to handle empty strings and invalid values
            price = safe_price_conversion(value)
            if price is not None:
                updated_prices[item_id] = price

    # Loop through items currently in the database for this work order
    for item in existing_items:
        item_id_str = str(item.id)

        # If the item's ID is in the list from the form, update it
        if item_id_str in updated_item_ids:
            if item_id_str in updated_quantities:
                item.Qty = updated_quantities[item_id_str]
            if item_id_str in updated_prices:
                item.Price = updated_prices[item_id_str]
        else:
            # Item was unchecked, delete it
            db.session.delete(item)
            flash_messages.append(f"Removed item '{item.Description}' from work order.")

    return flash_messages


def _handle_work_order_items(form_data, work_order_no, cust_id):
    """
    Process all work order items: selected from inventory and new items.
    Returns tuple of (items_to_add, catalog_items_to_add, flash_messages).
    """
    items_to_add = []
    catalog_items_to_add = []
    flash_messages = []

    # Process selected inventory items
    selected_items = process_selected_inventory_items(
        form_data, work_order_no, cust_id, WorkOrderItem
    )
    items_to_add.extend(selected_items)

    # Process new items and update catalog
    new_items, catalog_updates = process_new_items(
        form_data, work_order_no, cust_id, WorkOrderItem, update_catalog=True
    )
    items_to_add.extend(new_items)
    catalog_items_to_add.extend(catalog_updates)

    return items_to_add, catalog_items_to_add, flash_messages


def _generate_next_work_order_number():
    """
    Generate the next work order number.
    Returns the next work order number as a string.
    """
    latest_num = db.session.query(
        func.max(cast(WorkOrder.WorkOrderNo, Integer))
    ).scalar()
    return str(latest_num + 1) if latest_num is not None else "1"


def _restore_draft_data(draft_id, current_user):
    """
    Restore form data from a saved draft.

    Args:
        draft_id: The ID of the draft to restore
        current_user: The current logged-in user

    Returns:
        tuple: (form_data dict, checkin_items list) if successful
               (empty dict, empty list) if draft not found
    """
    from models.work_order_draft import WorkOrderDraft

    draft = WorkOrderDraft.query.filter_by(
        id=draft_id,
        user_id=current_user.id
    ).first()

    if not draft or not draft.form_data:
        flash("Draft not found or has been deleted.", "warning")
        return {}, []

    # Show success message to user
    flash(f"Draft from {draft.updated_at.strftime('%b %d, %Y at %I:%M %p')} has been restored.", "success")

    # Load all form data from the draft
    form_data = draft.form_data.copy()
    checkin_items = []

    # Handle new items if they exist in the draft
    # The draft stores new_item_description[], new_item_material[], etc.
    # We need to reconstruct the checkin_items format for the template
    new_item_descriptions = form_data.get("new_item_description[]", [])
    if isinstance(new_item_descriptions, str):
        new_item_descriptions = [new_item_descriptions]

    if new_item_descriptions:
        new_item_materials = form_data.get("new_item_material[]", [])
        new_item_colors = form_data.get("new_item_color[]", [])
        new_item_qtys = form_data.get("new_item_qty[]", [])
        new_item_sizewgts = form_data.get("new_item_sizewgt[]", [])
        new_item_prices = form_data.get("new_item_price[]", [])
        new_item_conditions = form_data.get("new_item_condition[]", [])

        # Ensure all are lists
        if isinstance(new_item_materials, str):
            new_item_materials = [new_item_materials]
        if isinstance(new_item_colors, str):
            new_item_colors = [new_item_colors]
        if isinstance(new_item_qtys, str):
            new_item_qtys = [new_item_qtys]
        if isinstance(new_item_sizewgts, str):
            new_item_sizewgts = [new_item_sizewgts]
        if isinstance(new_item_prices, str):
            new_item_prices = [new_item_prices]
        if isinstance(new_item_conditions, str):
            new_item_conditions = [new_item_conditions]

        # Build checkin_items array for template
        for i, description in enumerate(new_item_descriptions):
            if description:  # Only add if description exists
                checkin_items.append({
                    "description": description,
                    "material": new_item_materials[i] if i < len(new_item_materials) else "",
                    "color": new_item_colors[i] if i < len(new_item_colors) else "",
                    "qty": new_item_qtys[i] if i < len(new_item_qtys) else 0,
                    "sizewgt": new_item_sizewgts[i] if i < len(new_item_sizewgts) else "",
                    "price": float(new_item_prices[i]) if i < len(new_item_prices) and new_item_prices[i] else 0.00,
                    "condition": new_item_conditions[i] if i < len(new_item_conditions) else "",
                })

    # Handle selected inventory items
    selected_items = form_data.get("selected_items[]", [])
    if isinstance(selected_items, str):
        selected_items = [selected_items]
    if selected_items:
        form_data["selected_inventory_keys"] = selected_items

    return form_data, checkin_items


# ============================================================================
# PUBLIC ROUTE HANDLERS
# ============================================================================


@work_orders_bp.route("/api/open_repair_orders/<cust_id>")
@login_required
def get_open_repair_orders(cust_id):
    """Get all open repair orders for a specific customer"""
    open_repair_orders = RepairWorkOrder.query.filter(
        RepairWorkOrder.CustID == cust_id, RepairWorkOrder.DateCompleted.is_(None)
    ).all()

    return jsonify(
        [
            {
                "RepairOrderNo": order.RepairOrderNo,
            }
            for order in open_repair_orders
        ]
    )


@work_orders_bp.route("/<work_order_no>/files/upload", methods=["POST"])
@login_required
def upload_work_order_file(work_order_no):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        # Use deferred upload to prevent orphaned S3 files if DB commit fails
        saved_file = save_work_order_file(
            work_order_no,
            file,
            to_s3=True,
            generate_thumbnails=True,
            defer_s3_upload=True
        )

        if not saved_file:
            return jsonify({"error": "Invalid file type"}), 400

        # Add to database session
        db.session.add(saved_file)

        # Commit to database first
        db.session.commit()

        # Then upload to S3 (prevents orphaned S3 files)
        success, uploaded, failed = commit_deferred_uploads([saved_file])
        if not success:
            print(f"WARNING: File failed to upload to S3: {saved_file.filename}")
            # Database record exists but S3 upload failed
            # Consider rolling back or flagging the record
            db.session.delete(saved_file)
            db.session.commit()
            return jsonify({"error": "Failed to upload file to S3"}), 500

        return jsonify(
            {"message": "File uploaded successfully", "file_id": saved_file.id}
        )

    except Exception as e:
        db.session.rollback()
        if 'saved_file' in locals():
            cleanup_deferred_files([saved_file])
        print(f"Error uploading file: {str(e)}")
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500


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
@login_required
@role_required("admin", "manager")
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
    # Get the referrer from query param or request referrer
    return_url = request.args.get(
        "return_url", request.referrer or url_for("work_orders.list_work_orders")
    )

    return render_template(
        "work_orders/detail.html",
        work_order=work_order,
        files=work_order.files,  # pass files explicitly
        return_url=return_url,
        get_file_size=get_file_size,  # pass function to template
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
        max_retries = 5
        retry_count = 0
        base_delay = 0.1

        while retry_count < max_retries:
            try:
                next_wo_no = _generate_next_work_order_number()

                print("--- Form Data Received ---")
                print(f"Request Form Keys: {request.form.keys()}")
                print(f"Selected Items: {request.form.getlist('selected_items[]')}")
                print(
                    f"New Item Descriptions: {request.form.getlist('new_item_description[]')}"
                )

                # Extract work order fields and create work order
                wo_data = extract_work_order_fields(request.form)
                work_order = WorkOrder(WorkOrderNo=next_wo_no, **wo_data)

                if work_order.Clean:
                    work_order.ProcessingStatus = False

                db.session.add(work_order)
                db.session.flush()

                work_order.sync_source_name()

                # Process work order items
                items_to_add, catalog_to_add, _ = _handle_work_order_items(
                    request.form, next_wo_no, request.form.get("CustID")
                )
                for item in items_to_add:
                    db.session.add(item)
                for catalog_item in catalog_to_add:
                    db.session.add(catalog_item)

                # Process file uploads (deferred - not uploaded to S3 yet)
                uploaded_files = _handle_file_uploads(
                    request.files.getlist("files[]"), next_wo_no
                )
                for wo_file in uploaded_files:
                    db.session.add(wo_file)

                # Handle SeeRepair backlink
                backlink_msg = _handle_see_repair_backlink(
                    next_wo_no, request.form.get("SeeRepair")
                )
                if backlink_msg:
                    flash(backlink_msg, "info")

                # Commit DB transaction first
                db.session.commit()

                # Mark check-in as processed if converting from check-in
                checkin_id = request.form.get("checkin_id")
                if checkin_id:
                    from models.checkin import CheckIn
                    checkin = CheckIn.query.get(checkin_id)
                    if checkin and checkin.Status == "pending":
                        checkin.Status = "processed"
                        checkin.WorkOrderNo = next_wo_no
                        db.session.commit()

                # AFTER successful DB commit, upload files to S3
                # This prevents orphaned S3 files if DB commit fails
                if uploaded_files:
                    success, uploaded, failed = commit_deferred_uploads(uploaded_files)
                    if not success:
                        # Log warning but don't fail - DB is already committed
                        print(f"WARNING: {len(failed)} files failed to upload to S3")
                        for file_obj, error in failed:
                            print(f"  - {file_obj.filename}: {error}")

                flash(
                    f"Work Order {next_wo_no} created successfully with {len(uploaded_files)} files!",
                    "success",
                )
                return redirect(
                    url_for("customers.customer_detail", customer_id=work_order.CustID)
                )

            except IntegrityError as ie:
                db.session.rollback()
                # Clean up deferred file data on rollback
                if "uploaded_files" in locals():
                    cleanup_deferred_files(uploaded_files)
                retry_count += 1

                error_msg = (
                    str(ie.orig).lower() if hasattr(ie, "orig") else str(ie).lower()
                )

                if "datein" in error_msg:
                    flash(
                        "⚠️ Date In field is required. Please select a valid date before saving.",
                        "danger",
                    )

                is_duplicate = "duplicate" in error_msg or "unique" in error_msg

                if is_duplicate and retry_count < max_retries:
                    delay = base_delay * (2**retry_count) + (random.random() * 0.05)
                    print(
                        f"Duplicate work order number detected. Retry {retry_count}/{max_retries} after {delay:.3f}s"
                    )
                    time.sleep(delay)
                    continue
                else:
                    print(f"Error creating work order (IntegrityError): {str(ie)}")
                    flash(
                        "⚠️ Database error occurred. Please contact support.", "danger"
                    )
                    return render_template(
                        "work_orders/create.html",
                        customers=Customer.query.all(),
                        sources=Source.query.all(),
                        form_data=request.form,
                    )

            except Exception as e:
                db.session.rollback()
                # Clean up deferred file data on rollback
                if "uploaded_files" in locals():
                    cleanup_deferred_files(uploaded_files)
                print(f"Error creating work order: {str(e)}")
                flash(f"Error creating work order: {str(e)}", "error")
                return render_template(
                    "work_orders/create.html",
                    customers=Customer.query.all(),
                    sources=Source.query.all(),
                    form_data=request.form,
                )

        flash(
            "Error creating work order: Unable to generate unique work order number after multiple attempts",
            "error",
        )
        return render_template(
            "work_orders/create.html",
            customers=Customer.query.all(),
            sources=Source.query.all(),
            form_data=request.form,
        )

    # GET Request: Render Form
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    form_data = {}
    checkin_items = []
    checkin_id = request.args.get("checkin_id")
    draft_id = request.args.get("draft_id")

    # Handle draft restoration
    if draft_id:
        from flask_login import current_user
        draft_form_data, draft_checkin_items = _restore_draft_data(draft_id, current_user)
        if draft_form_data:
            form_data = draft_form_data
            checkin_items = draft_checkin_items

    # Handle check-in conversion
    elif checkin_id:
        from models.checkin import CheckIn
        checkin = CheckIn.query.get(checkin_id)
        if checkin and checkin.Status == "pending":
            # Pre-fill form with check-in data
            form_data["CustID"] = checkin.CustID
            form_data["DateIn"] = checkin.DateIn.strftime("%Y-%m-%d") if checkin.DateIn else ""
            form_data["WOName"] = checkin.customer.Name if checkin.customer else ""
            if checkin.customer and checkin.customer.Source:
                form_data["ShipTo"] = checkin.customer.Source

            # Pre-fill new check-in fields
            if checkin.SpecialInstructions:
                form_data["SpecialInstructions"] = checkin.SpecialInstructions
            if checkin.StorageTime:
                form_data["StorageTime"] = checkin.StorageTime
            if checkin.RackNo:
                form_data["RackNo"] = checkin.RackNo
            if checkin.ReturnTo:
                form_data["ReturnTo"] = checkin.ReturnTo
            if checkin.DateRequired:
                form_data["DateRequired"] = checkin.DateRequired.strftime("%Y-%m-%d")
            if checkin.RepairsNeeded:
                form_data["RepairsNeeded"] = "1"
            if checkin.RushOrder:
                form_data["RushOrder"] = "1"

            # Convert check-in items to work order format for pre-filling
            # Items WITH InventoryKey = from existing inventory (pre-select them)
            # Items WITHOUT InventoryKey = NEW items (add as new items)
            selected_inventory_keys = []
            checkin_items = []

            for item in checkin.items:
                if item.InventoryKey:
                    # Item from existing inventory - add to selected keys
                    selected_inventory_keys.append(str(item.InventoryKey))
                else:
                    # NEW item - add to checkin_items for "new items" section
                    checkin_items.append({
                        "description": item.Description,
                        "material": item.Material or "Unknown",
                        "color": item.Color or "",
                        "qty": item.Qty or 0,
                        "sizewgt": item.SizeWgt or "",
                        "price": float(item.Price) if item.Price else 0.00,
                        "condition": item.Condition or "",
                    })

            # Store selected keys for JavaScript to pre-select in inventory section
            form_data["selected_inventory_keys"] = selected_inventory_keys

    # Handle customer prefill (existing functionality)
    elif prefill_cust_id:
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
        checkin_items=checkin_items,
        checkin_id=checkin_id,
    )


@work_orders_bp.route("/edit/<work_order_no>", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit_work_order(work_order_no):
    """Edit an existing work order (NO INVENTORY ADJUSTMENTS EVER)"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()

    # Get the return URL from query param or referrer
    return_url = request.args.get(
        "return_url", request.referrer or url_for("work_orders.list_work_orders")
    )

    if request.method == "POST":
        try:
            old_cust_id = work_order.CustID
            old_see_repair = (
                work_order.SeeRepair.strip() if work_order.SeeRepair else None
            )

            # Track old values for queue-relevant fields
            old_rush_order = work_order.RushOrder
            old_firm_rush = work_order.FirmRush
            old_date_required = work_order.DateRequired
            old_date_in = work_order.DateIn
            old_clean = work_order.Clean
            old_treat = work_order.Treat
            old_date_completed = work_order.DateCompleted
            old_quote = work_order.Quote

            # Update work order fields
            _update_work_order_fields(work_order, request.form)

            # Handle existing work order items (update/delete)
            item_flash_messages = _update_existing_work_order_items(
                work_order_no, request.form
            )
            for msg in item_flash_messages:
                flash(msg, "info")

            # Handle items selected from customer inventory
            selected_items = process_selected_inventory_items(
                request.form, work_order_no, work_order.CustID, WorkOrderItem
            )
            for item in selected_items:
                db.session.add(item)
                flash(f"Added item '{item.Description}' from customer history.", "info")

            # Handle new items being added to this work order
            new_items, catalog_updates = process_new_items(
                request.form,
                work_order_no,
                work_order.CustID,
                WorkOrderItem,
                update_catalog=True,
            )
            for item in new_items:
                db.session.add(item)
            for catalog_item in catalog_updates:
                db.session.add(catalog_item)

            # Process file uploads
            uploaded_files = _handle_file_uploads(
                request.files.getlist("files[]"), work_order_no
            )
            for wo_file in uploaded_files:
                db.session.add(wo_file)

            # Handle SeeRepair backlink
            backlink_msg = _handle_see_repair_backlink(
                work_order_no, request.form.get("SeeRepair"), old_see_repair
            )
            if backlink_msg:
                flash(backlink_msg, "info")

            # Sync source_name if customer changed
            if work_order.CustID != old_cust_id:
                work_order.sync_source_name()

            # Clear queue position if queue-relevant fields changed
            # The queue page will auto-reassign position correctly on next load
            queue_fields_changed = (
                work_order.RushOrder != old_rush_order
                or work_order.FirmRush != old_firm_rush
                or work_order.DateRequired != old_date_required
                or work_order.DateIn != old_date_in
                or work_order.Clean != old_clean
                or work_order.Treat != old_treat
                or work_order.DateCompleted != old_date_completed
                or work_order.Quote != old_quote
            )

            if queue_fields_changed and work_order.QueuePosition is not None:
                print(f"Queue-relevant fields changed for WO {work_order_no}, clearing QueuePosition")
                work_order.QueuePosition = None

            db.session.commit()

            # AFTER successful DB commit, upload files to S3
            if uploaded_files:
                success, uploaded, failed = commit_deferred_uploads(uploaded_files)
                if not success:
                    print(f"WARNING: {len(failed)} files failed to upload to S3")
                    for file_obj, error in failed:
                        print(f"  - {file_obj.filename}: {error}")

            flash(
                f"Work Order {work_order_no} updated successfully"
                + (f" with {len(uploaded_files)} files!" if uploaded_files else "!"),
                "success",
            )

            # Redirect to customer page instead of work order page
            return redirect(
                url_for("customers.customer_detail", customer_id=work_order.CustID)
            )

        except Exception as e:
            db.session.rollback()
            print(f"Error editing Work Order: {e}")
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
        return_url=return_url,
    )


@work_orders_bp.route("/cleaning-room/edit/<work_order_no>", methods=["GET", "POST"])
@role_required("user")
def cleaning_room_edit_work_order(work_order_no):
    """Restricted edit for cleaning room staff - can only edit Clean, Treat, and SpecialInstructions"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()

    # Get the return URL from query param or referrer
    return_url = request.args.get(
        "return_url", request.referrer or url_for("work_orders.list_work_orders")
    )

    if request.method == "POST":
        try:
            # Track old values for queue-relevant fields
            old_clean = work_order.Clean
            old_treat = work_order.Treat

            clean_str = request.form.get("Clean")
            work_order.Clean = (
                datetime.strptime(clean_str, "%Y-%m-%d").date() if clean_str else None
            )
            if work_order.Clean:
                work_order.ProcessingStatus = False

            treat_str = request.form.get("Treat")
            work_order.Treat = (
                datetime.strptime(treat_str, "%Y-%m-%d").date() if treat_str else None
            )

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
                        # Use deferred upload to prevent orphaned S3 files
                        wo_file = save_work_order_file(
                            work_order_no,
                            file,
                            to_s3=True,
                            generate_thumbnails=True,
                            defer_s3_upload=True,
                        )
                        if not wo_file:
                            raise Exception(f"Failed to process file: {file.filename}")

                        uploaded_files.append(wo_file)
                        db.session.add(wo_file)  # Add to session but don't commit yet
                        print(
                            f"Prepared file {i + 1}/{len(files)}: {wo_file.filename} (deferred)"
                        )

                        # Log thumbnail info
                        if wo_file.thumbnail_path:
                            print(f"  - Thumbnail prepared: {wo_file.thumbnail_path}")

            work_order.final_location = request.form.get("final_location")

            # Clear queue position if Clean or Treat dates were set
            # (work order is now in progress, should not be in cleaning queue)
            queue_fields_changed = (
                work_order.Clean != old_clean or work_order.Treat != old_treat
            )

            if queue_fields_changed and work_order.QueuePosition is not None:
                print(f"Clean/Treat date changed for WO {work_order_no}, clearing QueuePosition")
                work_order.QueuePosition = None

            # Commit DB transaction first
            db.session.commit()

            # AFTER successful DB commit, upload files to S3
            if uploaded_files:
                success, uploaded, failed = commit_deferred_uploads(uploaded_files)
                if not success:
                    print(f"WARNING: {len(failed)} files failed to upload to S3")

            flash(
                f"Work Order {work_order_no} (cleaning room update) saved successfully!",
                "success",
            )
            return redirect(
                url_for("customers.customer_detail", customer_id=work_order.CustID)
            )

        except Exception as e:
            db.session.rollback()
            # Clean up deferred file data on rollback
            if "uploaded_files" in locals():
                cleanup_deferred_files(uploaded_files)
            flash(f"Error updating work order: {str(e)}", "error")

    # GET request - show limited edit form
    return render_template(
        "work_orders/cleaning_room_edit.html",
        work_order=work_order,
        return_url=return_url,
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

    # Optimize relationship loading - Source is denormalized, so just load customer
    query = query.options(joinedload(WorkOrder.customer))

    # Apply status quick filters
    if status == "pending":
        query = query.filter(WorkOrder.DateCompleted.is_(None))
    elif status == "completed":
        query = query.filter(WorkOrder.DateCompleted.isnot(None))
    elif status == "rush":
        query = query.filter(
            or_(WorkOrder.RushOrder == True, WorkOrder.FirmRush == True),
            WorkOrder.DateCompleted.is_(None),
        )

    # Make request.args mutable
    args = request.args.copy()

    # Ensure CustID filter is a string
    if "filter_CustID" in args:
        args["filter_CustID"] = str(args["filter_CustID"])

    # Apply column-specific filters
    query = apply_column_filters(
        query,
        WorkOrder,
        args,
        {
            "filter_WorkOrderNo": {
                "column": WorkOrder.WorkOrderNo,
                "type": "range_or_exact",
            },
            "filter_CustID": {"column": WorkOrder.CustID, "type": "exact"},
            "filter_WOName": {"column": WorkOrder.WOName, "type": "like"},
            "filter_DateIn": {"column": WorkOrder.DateIn, "type": "like"},
            "filter_DateRequired": {"column": WorkOrder.DateRequired, "type": "like"},
            "filter_Source": {
                "column": WorkOrder.source_name,
                "type": "like",
            },  # Use denormalized column
        },
    )

    # Apply sorting
    query = apply_tabulator_sorting(
        query,
        WorkOrder,
        request.args,
        {
            "WorkOrderNo": "integer",
            "CustID": "integer",
            "DateIn": "date",
            "DateRequired": "date",
            "Source": WorkOrder.source_name,  # Use denormalized column
        },
    )

    # Default sort if no sort specified
    if not any(request.args.get(f"sort[{i}][field]") for i in range(10)):
        query = query.order_by(WorkOrder.WorkOrderNo.desc())

    # Paginate
    total = query.count()
    work_orders = query.paginate(page=page, per_page=size, error_out=False)

    # Build response data
    data = [
        {
            "WorkOrderNo": wo.WorkOrderNo,
            "CustID": wo.CustID,
            "WOName": wo.WOName,
            "DateIn": format_date_from_str(wo.DateIn),
            "DateRequired": format_date_from_str(wo.DateRequired),
            "Source": wo.source_name,  # Use denormalized column for performance
            "is_rush": bool(wo.RushOrder or wo.FirmRush),  # Add rush flag
            "detail_url": url_for(
                "work_orders.view_work_order",
                work_order_no=wo.WorkOrderNo,
                return_url=url_for("work_orders.list_work_orders", _external=False),
            ),
            "edit_url": url_for(
                "work_orders.edit_work_order",
                work_order_no=wo.WorkOrderNo,
                return_url=url_for("work_orders.list_work_orders", _external=False),
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
    """Delete a work order, its associated files from S3, and without adjusting inventory"""
    work_order = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first_or_404()
    try:
        # Import the delete function
        from utils.file_upload import delete_file_from_s3

        # Delete S3 files first (before deleting DB records)
        files_deleted = 0
        for file_obj in work_order.files:
            # Delete main file
            if delete_file_from_s3(file_obj.file_path):
                files_deleted += 1
            # Delete thumbnail if it exists
            if file_obj.thumbnail_path and delete_file_from_s3(file_obj.thumbnail_path):
                files_deleted += 1

        # Delete all associated work order items
        for item in work_order.items:
            db.session.delete(item)

        # Delete the work order itself (cascade will delete file records)
        db.session.delete(work_order)
        db.session.commit()

        if files_deleted > 0:
            flash(
                f"Work Order {work_order_no} deleted successfully (removed {files_deleted} files from S3)!",
                "success",
            )
        else:
            flash(f"Work Order {work_order_no} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting work order: {str(e)}", "danger")

    return redirect(url_for("customers.customer_detail", customer_id=work_order.CustID))


@work_orders_bp.route("/delete_file/<int:file_id>", methods=["DELETE"])
@login_required
@role_required("admin", "manager")
def delete_work_order_file(file_id):
    """Delete a single file associated with a work order (from S3 + DB)"""
    file_obj = WorkOrderFile.query.get_or_404(file_id)

    try:
        from utils.file_upload import delete_file_from_s3

        # Delete from S3 (main + thumbnail)
        if file_obj.file_path:
            delete_file_from_s3(file_obj.file_path)
        if file_obj.thumbnail_path:
            delete_file_from_s3(file_obj.thumbnail_path)

        # Delete DB record
        db.session.delete(file_obj)
        db.session.commit()

        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


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

    # Prepare order data using shared helper
    wo_dict = prepare_order_data_for_pdf(work_order, order_type="work_order")

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

    # Prepare order data using shared helper
    wo_dict = prepare_order_data_for_pdf(work_order, order_type="work_order")

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


@work_orders_bp.route("/api/bulk_pdf", methods=["POST"])
@login_required
def bulk_pdf_work_orders():
    """Generate a concatenated PDF for multiple work orders"""
    try:
        data = request.get_json()
        work_order_numbers = data.get("work_order_numbers", [])

        if not work_order_numbers:
            return jsonify({"error": "No work orders provided"}), 400

        # Create a new PDF document
        merged_pdf = fitz.open()

        # Generate PDF for each work order and merge
        for wo_no in work_order_numbers:
            work_order = (
                WorkOrder.query.filter_by(WorkOrderNo=wo_no)
                .options(
                    db.joinedload(WorkOrder.customer),
                    db.joinedload(WorkOrder.ship_to_source),
                )
                .first()
            )

            if not work_order:
                continue

            # Prepare order data using shared helper
            wo_dict = prepare_order_data_for_pdf(work_order, order_type="work_order")

            # Generate PDF for this work order
            pdf_buffer = generate_work_order_pdf(
                wo_dict,
                company_info={
                    "name": "Awning Cleaning Industries - In House Cleaning Work Order"
                },
            )

            # Open the generated PDF and append to merged PDF
            temp_pdf = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
            merged_pdf.insert_pdf(temp_pdf)
            temp_pdf.close()

        # Save merged PDF to buffer
        output_buffer = BytesIO()
        merged_pdf.save(output_buffer)
        merged_pdf.close()
        output_buffer.seek(0)

        return send_file(
            output_buffer,
            as_attachment=True,
            download_name=f"WorkOrders_Bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        print(f"Error generating bulk PDF: {str(e)}")
        return jsonify({"error": str(e)}), 500
