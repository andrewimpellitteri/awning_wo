from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    url_for,
    flash,
    redirect,
    send_file,
    abort,
)
from flask_login import login_required
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.repair_order_file import RepairOrderFile
from models.customer import Customer
from models.inventory import Inventory
from models.source import Source
from sqlalchemy import or_, case, func, literal, desc, cast, Integer
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from extensions import db
import time
import random
from decorators import role_required
from utils.repair_order_pdf import generate_repair_order_pdf
from sqlalchemy.orm import joinedload
from utils.pdf_helpers import prepare_order_data_for_pdf
from utils.file_upload import (
    save_repair_order_file,
    generate_presigned_url,
    get_file_size,
    commit_deferred_uploads,
    cleanup_deferred_files,
)
from utils.query_helpers import (
    apply_column_filters,
    apply_tabulator_sorting,
    apply_search_filter,
)
from utils.order_item_helpers import safe_price_conversion


repair_work_orders_bp = Blueprint(
    "repair_work_orders", __name__, url_prefix="/repair_work_orders"
)


# ============================================================================
# PRIVATE HELPER FUNCTIONS FOR REPAIR ORDER CREATE/EDIT
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


def _update_repair_order_fields(repair_order, form_data):
    """
    Update repair order fields from form data.
    Handles all basic fields, dates, and boolean checkboxes.
    """
    repair_order.CustID = form_data.get("CustID")
    repair_order.ROName = form_data.get("ROName")
    repair_order.SOURCE = form_data.get("SOURCE")
    repair_order.RackNo = form_data.get("RackNo")
    repair_order.STORAGE = form_data.get("STORAGE")
    repair_order.SPECIALINSTRUCTIONS = form_data.get("SPECIALINSTRUCTIONS")
    repair_order.CLEAN = "CLEAN" in form_data
    repair_order.SEECLEAN = form_data.get("SEECLEAN")
    repair_order.REPAIRSDONEBY = form_data.get("REPAIRSDONEBY")
    repair_order.MaterialList = form_data.get("MaterialList")
    repair_order.CUSTOMERPRICE = form_data.get("CUSTOMERPRICE")
    repair_order.RETURNSTATUS = form_data.get("RETURNSTATUS")
    repair_order.RETURNTO = form_data.get("RETURNTO")
    repair_order.LOCATION = form_data.get("LOCATION")
    repair_order.final_location = form_data.get("final_location")
    repair_order.RushOrder = "RushOrder" in form_data
    repair_order.FirmRush = "FirmRush" in form_data
    repair_order.QUOTE = form_data.get("QUOTE") or None

    # Parse date fields
    repair_order.WO_DATE = _parse_date_field(form_data.get("WO_DATE"))
    repair_order.DATE_TO_SUB = _parse_date_field(form_data.get("DATE_TO_SUB"))
    repair_order.DateRequired = _parse_date_field(form_data.get("DateRequired"))
    repair_order.DateCompleted = _parse_date_field(form_data.get("DateCompleted"))
    repair_order.RETURNDATE = _parse_date_field(form_data.get("RETURNDATE"))
    repair_order.DATEOUT = _parse_date_field(form_data.get("DATEOUT"))
    repair_order.DateIn = _parse_date_field(form_data.get("DateIn"))


def _handle_selected_inventory_items(form_data, repair_order_no, cust_id):
    """
    Process selected inventory items and create RepairWorkOrderItems.
    Returns list of RepairWorkOrderItem objects to add to session.
    """
    items_to_add = []
    selected_item_ids = form_data.getlist("selected_items[]")

    for item_id in selected_item_ids:
        if not item_id:
            continue

        original_item = Inventory.query.filter_by(InventoryKey=item_id).first()
        if not original_item:
            continue

        # Get quantity from form
        qty_raw = form_data.get(f"item_qty_{item_id}", original_item.Qty or 1)
        try:
            qty = int(qty_raw)
        except ValueError:
            qty = 1

        repair_item = RepairWorkOrderItem(
            RepairOrderNo=repair_order_no,
            CustID=cust_id,
            Description=original_item.Description,
            Material=original_item.Material,
            Qty=qty,
            Condition=original_item.Condition,
            Color=original_item.Color,
            SizeWgt=original_item.SizeWgt,
            Price=original_item.Price,
        )
        items_to_add.append(repair_item)

    return items_to_add


def _handle_new_repair_items(form_data, repair_order_no, cust_id):
    """
    Process new repair order items from form.
    Returns list of RepairWorkOrderItem objects to add to session.
    """
    items_to_add = []

    item_descriptions = form_data.getlist("item_description[]")
    item_materials = form_data.getlist("item_material[]")
    item_qtys = form_data.getlist("item_qty[]")
    item_conditions = form_data.getlist("item_condition[]")
    item_colors = form_data.getlist("item_color[]")
    item_sizes = form_data.getlist("item_size_wgt[]")
    item_prices = form_data.getlist("item_price[]")

    for i, descrip in enumerate(item_descriptions):
        if descrip and descrip.strip():
            price_raw = item_prices[i] if i < len(item_prices) else ""
            repair_item = RepairWorkOrderItem(
                RepairOrderNo=repair_order_no,
                CustID=cust_id,
                Description=descrip,
                Material=item_materials[i] if i < len(item_materials) else "",
                Qty=item_qtys[i] if i < len(item_qtys) else "1",
                Condition=item_conditions[i] if i < len(item_conditions) else "",
                Color=item_colors[i] if i < len(item_colors) else "",
                SizeWgt=item_sizes[i] if i < len(item_sizes) else "",
                Price=safe_price_conversion(price_raw),
            )
            items_to_add.append(repair_item)

    return items_to_add


def _handle_existing_repair_items(form_data, repair_order_no, cust_id):
    """
    Recreate existing repair order items from edit form.
    Returns list of RepairWorkOrderItem objects to add to session.
    """
    items_to_add = []

    existing_descriptions = form_data.getlist("existing_description[]")
    existing_materials = form_data.getlist("existing_material[]")
    existing_qtys = form_data.getlist("existing_qty[]")
    existing_conditions = form_data.getlist("existing_condition[]")
    existing_colors = form_data.getlist("existing_color[]")
    existing_sizes = form_data.getlist("existing_size[]")
    existing_prices = form_data.getlist("existing_price[]")

    for i, descrip in enumerate(existing_descriptions):
        if descrip and descrip.strip():
            price_str = existing_prices[i] if i < len(existing_prices) else None
            repair_item = RepairWorkOrderItem(
                RepairOrderNo=repair_order_no,
                CustID=cust_id,
                Description=descrip,
                Material=existing_materials[i] if i < len(existing_materials) else "",
                Qty=existing_qtys[i] if i < len(existing_qtys) else "1",
                Condition=existing_conditions[i]
                if i < len(existing_conditions)
                else "",
                Color=existing_colors[i] if i < len(existing_colors) else "",
                SizeWgt=existing_sizes[i] if i < len(existing_sizes) else "",
                Price=safe_price_conversion(price_str),
            )
            items_to_add.append(repair_item)

    return items_to_add


def _handle_new_repair_items_edit(form_data, repair_order_no, cust_id):
    """
    Process new repair order items from edit form.
    Returns list of RepairWorkOrderItem objects to add to session.
    """
    items_to_add = []

    new_descriptions = form_data.getlist("new_description[]")
    new_materials = form_data.getlist("new_material[]")
    new_qtys = form_data.getlist("new_qty[]")
    new_conditions = form_data.getlist("new_condition[]")
    new_colors = form_data.getlist("new_color[]")
    new_sizes = form_data.getlist("new_size[]")
    new_prices = form_data.getlist("new_price[]")

    for i, descrip in enumerate(new_descriptions):
        if descrip and descrip.strip():
            price_str = new_prices[i] if i < len(new_prices) else None
            repair_item = RepairWorkOrderItem(
                RepairOrderNo=repair_order_no,
                CustID=cust_id,
                Description=descrip,
                Material=new_materials[i] if i < len(new_materials) else "",
                Qty=new_qtys[i] if i < len(new_qtys) else "1",
                Condition=new_conditions[i] if i < len(new_conditions) else "",
                Color=new_colors[i] if i < len(new_colors) else "",
                SizeWgt=new_sizes[i] if i < len(new_sizes) else "",
                Price=safe_price_conversion(price_str),
            )
            items_to_add.append(repair_item)

    return items_to_add


def _handle_file_uploads_repair(files_list, repair_order_no):
    """
    Process file uploads for a repair order.
    Returns list of RepairOrderFile objects to add to session.

    Uses deferred S3 upload to prevent orphaned files if DB commit fails.
    """
    uploaded_files = []
    if not files_list:
        return uploaded_files

    for i, file in enumerate(files_list):
        if not file or not file.filename:
            continue

        ro_file = save_repair_order_file(
            repair_order_no,
            file,
            to_s3=True,
            generate_thumbnails=True,
            defer_s3_upload=True,
        )
        if not ro_file:
            raise Exception(f"Failed to process file: {file.filename}")

        uploaded_files.append(ro_file)
        print(
            f"Prepared file {i + 1}/{len(files_list)}: {ro_file.filename} (deferred upload)"
        )

        if ro_file.thumbnail_path:
            print(
                f"  - Thumbnail prepared for deferred upload: {ro_file.thumbnail_path}"
            )

    return uploaded_files


def _handle_seeclean_backlink(repair_order_no, new_seeclean, old_seeclean=None):
    """
    Manage SEECLEAN backlink between repair orders and work orders.
    Removes old backlink if changed, adds new backlink if provided.
    Returns a flash message if a new link was created.

    Note: Only creates backlinks for numeric SEECLEAN values (work order numbers).
    Text values (notes like "can't be cleaned") are ignored for backlinking.
    """
    from models.work_order import WorkOrder

    flash_message = None

    def _is_numeric(value):
        """Check if a value is numeric (work order number) vs text (note)."""
        if not value:
            return False
        try:
            float(str(value).strip())
            return True
        except (ValueError, TypeError):
            return False

    # If SEECLEAN changed, update backlinks
    if new_seeclean != old_seeclean:
        # Remove old backlink if it existed and was numeric
        if old_seeclean and _is_numeric(old_seeclean):
            old_work_order = WorkOrder.query.filter_by(WorkOrderNo=old_seeclean).first()
            if old_work_order and old_work_order.SeeRepair == repair_order_no:
                old_work_order.SeeRepair = None

        # Add new backlink if provided and is numeric (work order number)
        if new_seeclean and new_seeclean.strip() and _is_numeric(new_seeclean):
            new_work_order = WorkOrder.query.filter_by(
                WorkOrderNo=new_seeclean.strip()
            ).first()
            if new_work_order:
                new_work_order.SeeRepair = repair_order_no
                flash_message = (
                    f"Auto-linked Work Order {new_seeclean} to this Repair Order"
                )

    return flash_message


def _generate_next_repair_order_number():
    """
    Generate the next repair order number.
    Returns the next repair order number as a string.
    """
    latest_order = RepairWorkOrder.query.order_by(
        desc(cast(RepairWorkOrder.RepairOrderNo, Integer))
    ).first()

    if latest_order:
        try:
            return str(int(latest_order.RepairOrderNo) + 1)
        except ValueError:
            return str(int(datetime.now().timestamp()))
    else:
        return "1"


def _validate_repair_order_form(form_data):
    """
    Validate repair order form data.
    Returns list of error messages (empty if valid).
    """
    errors = []
    if not form_data.get("CustID"):
        errors.append("Customer is required.")
    if not form_data.get("ROName"):
        errors.append("Name is required.")
    return errors


# ============================================================================
# PUBLIC ROUTE HANDLERS
# ============================================================================


@repair_work_orders_bp.route("/<repair_order_no>/files/upload", methods=["POST"])
@login_required
def upload_repair_order_file(repair_order_no):
    """Upload a file to a repair order"""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        # Use deferred upload to prevent orphaned S3 files if DB commit fails
        saved_file = save_repair_order_file(
            repair_order_no,
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


@repair_work_orders_bp.route("/<repair_order_no>/files/<int:file_id>/download")
@login_required
def download_repair_order_file(repair_order_no, file_id):
    """
    Download a file attached to a repair order.
    Supports local files or S3 files (via pre-signed URLs).
    """
    ro_file = RepairOrderFile.query.filter_by(
        id=file_id, RepairOrderNo=repair_order_no
    ).first()

    if not ro_file:
        abort(404, description="File not found for this repair order.")

    if ro_file.file_path.startswith("s3://"):
        # S3 file → redirect to pre-signed URL
        presigned_url = generate_presigned_url(ro_file.file_path)
        return redirect(presigned_url)

    # Local file → serve directly
    return send_file(
        ro_file.file_path,
        as_attachment=True,
        download_name=ro_file.filename,
    )


@repair_work_orders_bp.route("/thumbnail/<int:file_id>")
@login_required
def get_repair_order_thumbnail(file_id):
    """Serve thumbnail for a repair order file"""
    try:
        # Get the file record
        ro_file = RepairOrderFile.query.get_or_404(file_id)

        if ro_file.thumbnail_path:
            if ro_file.thumbnail_path.startswith("s3://"):
                # Generate presigned URL for S3 thumbnail
                thumbnail_url = generate_presigned_url(
                    ro_file.thumbnail_path, expires_in=3600
                )
                return redirect(thumbnail_url)
            else:
                # Serve local thumbnail
                return send_file(ro_file.thumbnail_path)
        else:
            # No thumbnail available, return 404
            abort(404)

    except Exception as e:
        print(f"Error serving thumbnail for file {file_id}: {e}")
        abort(404)


@repair_work_orders_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return dict(get_file_size=get_file_size)


@repair_work_orders_bp.route("/<repair_order_no>/files")
@login_required
def list_repair_order_files(repair_order_no):
    """List all files for a repair order"""
    repair_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()
    files = [
        {"id": f.id, "filename": f.filename, "uploaded": f.uploaded_at.isoformat()}
        for f in repair_order.files
    ]
    return jsonify(files)


def format_date_from_str(value):
    """Ensure dates are returned as YYYY-MM-DD strings to avoid object serialization issues."""
    if not value:
        return None
    # If it's already a string, assume correct format. Otherwise, format the date/datetime object.
    return value.strftime("%Y-%m-%d") if not isinstance(value, str) else value


@repair_work_orders_bp.route("/")
@login_required
@role_required("admin", "manager")
def list_repair_work_orders():
    """
    Renders the main page for repair work orders.
    The page will be populated with data by the Tabulator table via an API call.
    """
    return render_template("repair_orders/list.html")


@repair_work_orders_bp.route("/<repair_order_no>")
def view_repair_work_order(repair_order_no):
    """Displays the detail page for a single repair work order."""
    repair_work_order = (
        RepairWorkOrder.query.options(
            joinedload(RepairWorkOrder.customer), joinedload(RepairWorkOrder.files)
        )
        .filter_by(RepairOrderNo=repair_order_no)
        .first_or_404()
    )

    return render_template(
        "repair_orders/detail.html",
        repair_work_order=repair_work_order,
        files=repair_work_order.files,
    )


@repair_work_orders_bp.route("/api/repair_work_orders")
def api_repair_work_orders():
    """
    API endpoint to provide repair work order data with robust filtering,
    searching, sorting, and pagination.
    """
    # Pagination params
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()
    search = request.args.get("search", "").strip()

    query = RepairWorkOrder.query

    # Optimize relationship loading - Source is denormalized, so just load customer
    query = query.options(joinedload(RepairWorkOrder.customer))

    # Apply status filters
    if status == "pending":
        query = query.filter(RepairWorkOrder.DateCompleted.is_(None))
    elif status == "completed":
        query = query.filter(RepairWorkOrder.DateCompleted.isnot(None))
    elif status == "rush":
        query = query.filter(
            or_(
                RepairWorkOrder.RushOrder.is_(True),
                RepairWorkOrder.FirmRush.is_(True),
            ),
            RepairWorkOrder.DateCompleted.is_(None),
        )

    # Apply global search
    query = apply_search_filter(
        query,
        RepairWorkOrder,
        search,
        [
            "RepairOrderNo",
            "CustID",
            "ROName",
            "LOCATION",
        ],
    )

    # Apply column-specific filters
    query = apply_column_filters(
        query,
        RepairWorkOrder,
        request.args,
        {
            "filter_RepairOrderNo": {
                "column": RepairWorkOrder.RepairOrderNo,
                "type": "exact",
            },
            "filter_CustID": {"column": RepairWorkOrder.CustID, "type": "exact"},
            "filter_ROName": {"column": RepairWorkOrder.ROName, "type": "like"},
            "filter_DateIn": {"column": RepairWorkOrder.DateIn, "type": "like"},
            "filter_DateCompleted": {
                "column": RepairWorkOrder.DateCompleted,
                "type": "like",
            },
            "filter_Source": {
                "column": RepairWorkOrder.source_name,
                "type": "like",
            },  # Use denormalized column
        },
    )

    # Apply sorting (support both simple and Tabulator multi-sort)
    simple_sort = request.args.get("sort")
    if simple_sort:
        # Simple sort mode
        simple_dir = request.args.get("dir", "asc")
        column = getattr(RepairWorkOrder, simple_sort, None)
        if column:
            if simple_sort in ["RepairOrderNo", "CustID"]:
                column = cast(column, Integer)
            query = query.order_by(
                column.desc() if simple_dir == "desc" else column.asc()
            )
    else:
        # Tabulator multi-sort mode
        query = apply_tabulator_sorting(
            query,
            RepairWorkOrder,
            request.args,
            {
                "RepairOrderNo": "integer",
                "CustID": "integer",
                "DateIn": "date",
                "DateCompleted": "date",
                "Source": RepairWorkOrder.source_name,  # Use denormalized column
            },
        )

    # Apply default sort if none provided
    if not simple_sort and not any(
        request.args.get(f"sort[{i}][field]") for i in range(10)
    ):
        query = query.order_by(
            RepairWorkOrder.DateIn.desc(), RepairWorkOrder.RepairOrderNo.desc()
        )

    # Pagination & results
    total = query.count()
    pagination = query.paginate(page=page, per_page=size, error_out=False)

    # Build response data
    data = []
    for order in pagination.items:
        data.append(
            {
                "RepairOrderNo": order.RepairOrderNo,
                "CustID": order.CustID,
                "ROName": order.ROName,
                "DateIn": format_date_from_str(order.DateIn),
                "DateCompleted": format_date_from_str(order.DateCompleted),
                "Source": order.source_name,  # Use denormalized column for performance
                "is_rush": bool(order.RushOrder) or bool(order.FirmRush),
                "detail_url": url_for(
                    "repair_work_orders.view_repair_work_order",
                    repair_order_no=order.RepairOrderNo,
                ),
                "customer_url": (
                    url_for("customers.customer_detail", customer_id=order.CustID)
                    if order.customer
                    else None
                ),
                "edit_url": url_for(
                    "repair_work_orders.edit_repair_order",
                    repair_order_no=order.RepairOrderNo,
                ),
                "delete_url": url_for(
                    "repair_work_orders.delete_repair_order",
                    repair_order_no=order.RepairOrderNo,
                ),
            }
        )

    return jsonify(
        {
            "data": data,
            "total": total,
            "last_page": pagination.pages,
        }
    )


@repair_work_orders_bp.route("/api/next_ro_number")
@login_required
def get_next_ro_number():
    """API endpoint to get the next repair order number"""
    latest_order = RepairWorkOrder.query.order_by(
        desc(cast(RepairWorkOrder.RepairOrderNo, Integer))
    ).first()

    if latest_order:
        try:
            next_num = int(latest_order.RepairOrderNo) + 1
        except ValueError:
            next_num = int(datetime.now().timestamp())
    else:
        next_num = 1

    return jsonify({"next_ro_number": str(next_num)})


@repair_work_orders_bp.route("/new", methods=["GET", "POST"])
@repair_work_orders_bp.route("/new/<prefill_cust_id>", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create_repair_order(prefill_cust_id=None):
    """Create a new repair work order"""
    if request.method == "POST":
        # Validation
        errors = _validate_repair_order_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            customers = Customer.query.order_by(Customer.Name).all()
            sources = Source.query.order_by(Source.SSource).all()
            return render_template(
                "repair_orders/create.html",
                customers=customers,
                sources=sources,
                prefill_cust_id=prefill_cust_id,
            )

        # Retry logic to handle race conditions in repair order number generation
        max_retries = 5
        retry_count = 0
        base_delay = 0.1

        while retry_count < max_retries:
            try:
                next_order_no = _generate_next_repair_order_number()

                # Create the repair work order with basic fields
                repair_order = RepairWorkOrder(RepairOrderNo=next_order_no)
                _update_repair_order_fields(repair_order, request.form)

                # Set default DateIn if not provided
                if not repair_order.DateIn:
                    repair_order.DateIn = datetime.now().date()

                db.session.add(repair_order)
                db.session.flush()

                # Sync source_name from customer
                repair_order.sync_source_name()

                # Process repair order items
                selected_items = _handle_selected_inventory_items(
                    request.form, next_order_no, request.form.get("CustID")
                )
                for item in selected_items:
                    db.session.add(item)

                new_items = _handle_new_repair_items(
                    request.form, next_order_no, request.form.get("CustID")
                )
                for item in new_items:
                    db.session.add(item)

                # Process file uploads (deferred)
                uploaded_files = _handle_file_uploads_repair(
                    request.files.getlist("files[]"), next_order_no
                )
                for ro_file in uploaded_files:
                    db.session.add(ro_file)

                # Handle SEECLEAN backlink
                backlink_msg = _handle_seeclean_backlink(
                    next_order_no, request.form.get("SEECLEAN")
                )
                if backlink_msg:
                    flash(backlink_msg, "info")

                # Commit DB transaction first
                db.session.commit()

                # AFTER successful DB commit, upload files to S3
                if uploaded_files:
                    success, uploaded, failed = commit_deferred_uploads(uploaded_files)
                    if not success:
                        print(f"WARNING: {len(failed)} files failed to upload to S3")
                        for file_obj, error in failed:
                            print(f"  - {file_obj.filename}: {error}")

                flash(
                    f"Repair Work Order {next_order_no} created successfully"
                    + (
                        f" with {len(uploaded_files)} files!" if uploaded_files else "!"
                    ),
                    "success",
                )
                return redirect(
                    url_for(
                        "customers.customer_detail", customer_id=repair_order.CustID
                    )
                )

            except IntegrityError as ie:
                db.session.rollback()
                if "uploaded_files" in locals():
                    cleanup_deferred_files(uploaded_files)
                retry_count += 1

                error_msg = (
                    str(ie.orig).lower() if hasattr(ie, "orig") else str(ie).lower()
                )
                is_duplicate = "duplicate" in error_msg or "unique" in error_msg

                if is_duplicate and retry_count < max_retries:
                    delay = base_delay * (2**retry_count) + (random.random() * 0.05)
                    print(
                        f"Duplicate repair order number detected. Retry {retry_count}/{max_retries} after {delay:.3f}s"
                    )
                    time.sleep(delay)
                    continue
                else:
                    print(f"Error creating repair order (IntegrityError): {str(ie)}")
                    flash(f"Error creating repair work order: {str(ie)}", "error")
                    return render_template(
                        "repair_orders/create.html",
                        customers=Customer.query.all(),
                        sources=Source.query.all(),
                        form_data=request.form,
                    )

            except Exception as e:
                db.session.rollback()
                if "uploaded_files" in locals():
                    cleanup_deferred_files(uploaded_files)
                flash(f"Error creating repair work order: {str(e)}", "error")
                return render_template(
                    "repair_orders/create.html",
                    customers=Customer.query.all(),
                    sources=Source.query.all(),
                    form_data=request.form,
                )

        # If we exhausted all retries
        flash(
            "Error creating repair order: Unable to generate unique repair order number after multiple attempts",
            "error",
        )
        return render_template(
            "repair_orders/create.html",
            customers=Customer.query.all(),
            sources=Source.query.all(),
            form_data=request.form,
        )

    # GET request - show form
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()
    form_data = {}
    if prefill_cust_id:
        customer = Customer.query.get(str(prefill_cust_id))
        if customer:
            form_data["CustID"] = str(prefill_cust_id)
            form_data["ROName"] = customer.Name
    return render_template(
        "repair_orders/create.html",
        customers=customers,
        sources=sources,
        form_data=form_data,
    )


@repair_work_orders_bp.route("/<repair_order_no>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit_repair_order(repair_order_no):
    """Edit an existing repair work order"""
    repair_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()

    if request.method == "POST":
        # Validation
        errors = _validate_repair_order_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            customers = Customer.query.order_by(Customer.Name).all()
            sources = Source.query.order_by(Source.SSource).all()
            return render_template(
                "repair_orders/edit.html",
                repair_work_order=repair_order,
                customers=customers,
                sources=sources,
            )

        try:
            old_cust_id = repair_order.CustID
            old_see_clean = (
                repair_order.SEECLEAN.strip() if repair_order.SEECLEAN else None
            )

            # Update repair order fields
            _update_repair_order_fields(repair_order, request.form)

            # Delete all existing items and recreate from form data
            RepairWorkOrderItem.query.filter_by(RepairOrderNo=repair_order_no).delete()

            # Recreate existing items from form
            existing_items = _handle_existing_repair_items(
                request.form, repair_order_no, request.form.get("CustID")
            )
            for item in existing_items:
                db.session.add(item)

            # Handle items selected from customer inventory
            selected_items = _handle_selected_inventory_items(
                request.form, repair_order_no, request.form.get("CustID")
            )
            for item in selected_items:
                db.session.add(item)

            # Handle new items
            new_items = _handle_new_repair_items_edit(
                request.form, repair_order_no, request.form.get("CustID")
            )
            for item in new_items:
                db.session.add(item)

            # Process file uploads (deferred)
            uploaded_files = _handle_file_uploads_repair(
                request.files.getlist("files[]"), repair_order_no
            )
            for ro_file in uploaded_files:
                db.session.add(ro_file)

            # Handle SEECLEAN backlink
            backlink_msg = _handle_seeclean_backlink(
                repair_order_no, request.form.get("SEECLEAN"), old_see_clean
            )
            if backlink_msg:
                flash(backlink_msg, "info")

            # Sync source_name if customer changed
            if repair_order.CustID != old_cust_id:
                repair_order.sync_source_name()

            # Commit DB transaction first
            db.session.commit()

            # AFTER successful DB commit, upload files to S3
            if uploaded_files:
                success, uploaded, failed = commit_deferred_uploads(uploaded_files)
                if not success:
                    print(f"WARNING: {len(failed)} files failed to upload to S3")

            flash(
                f"Repair Work Order {repair_order_no} updated successfully"
                + (f" with {len(uploaded_files)} files!" if uploaded_files else "!"),
                "success",
            )
            return redirect(
                url_for("customers.customer_detail", customer_id=repair_order.CustID)
            )

        except Exception as e:
            db.session.rollback()
            if "uploaded_files" in locals():
                cleanup_deferred_files(uploaded_files)
            flash(f"Error updating repair work order: {str(e)}", "error")

    # GET request - show form with existing data
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    # # Cast SEECLEAN to string if it's a float (avoid "4321.0" display bug)
    # if isinstance(repair_order.SEECLEAN, float):
    #     old_val = repair_order.SEECLEAN
    #     repair_order.SEECLEAN = (
    #         str(int(repair_order.SEECLEAN))
    #         if repair_order.SEECLEAN.is_integer()
    #         else str(repair_order.SEECLEAN)
    #     )
    #     print(
    #         f"[DEBUG] Converted SEECLEAN from float {old_val} → '{repair_order.SEECLEAN}'"
    #     )

    return render_template(
        "repair_orders/edit.html",
        repair_work_order=repair_order,
        customers=customers,
        sources=sources,
    )


@repair_work_orders_bp.route("/<repair_order_no>/delete", methods=["POST"])
@login_required
@role_required("admin", "manager")
def delete_repair_order(repair_order_no):
    """Delete a repair work order, its associated files from S3, and all associated items"""

    repair_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()

    try:
        # Import the delete function
        from utils.file_upload import delete_file_from_s3

        # Delete S3 files first (before deleting DB records)
        files_deleted = 0
        for file_obj in repair_order.files:
            # Delete main file
            if delete_file_from_s3(file_obj.file_path):
                files_deleted += 1
            # Delete thumbnail if it exists
            if file_obj.thumbnail_path and delete_file_from_s3(file_obj.thumbnail_path):
                files_deleted += 1

        # Delete associated items first (if cascade is not set up)
        RepairWorkOrderItem.query.filter_by(RepairOrderNo=repair_order_no).delete()

        # Delete the repair order (cascade will delete file records)
        db.session.delete(repair_order)
        db.session.commit()

        if files_deleted > 0:
            flash(
                f"Repair Work Order #{repair_order_no} has been deleted successfully (removed {files_deleted} files from S3)",
                "success",
            )
        else:
            flash(
                f"Repair Work Order #{repair_order_no} has been deleted successfully",
                "success",
            )
        return redirect(
            url_for("customers.customer_detail", customer_id=repair_order.CustID)
        )

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting repair work order: {str(e)}", "error")
        return redirect(
            url_for("customers.customer_detail", customer_id=repair_order.CustID)
        )


@repair_work_orders_bp.route("/<repair_order_no>/pdf")
@repair_work_orders_bp.route("/<repair_order_no>/pdf/download")
@login_required
def download_repair_order_pdf(repair_order_no):
    """download PDF in browser for a work order"""
    # Fetch work order + relationships in one query
    repair_order = (
        RepairWorkOrder.query.filter_by(RepairOrderNo=repair_order_no)
        .options(
            db.joinedload(RepairWorkOrder.customer),
        )
        .first_or_404()
    )

    # Prepare order data using shared helper
    ro_dict = prepare_order_data_for_pdf(repair_order, order_type="repair_order")

    try:
        pdf_buffer = generate_repair_order_pdf(
            ro_dict,
            company_info={"name": "Awning Cleaning Industries - Repair Work Order"},
        )

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"WorkOrder_{repair_order_no}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        return redirect(
            url_for(
                "repair_work_orders.view_repair_work_order",
                repair_order_no=repair_order_no,
            )
        )


@repair_work_orders_bp.route("/<repair_order_no>/pdf/view")
@login_required
def view_repair_order_pdf(repair_order_no):
    """View PDF in browser for a work order"""
    # Fetch work order + relationships in one query
    repair_order = (
        RepairWorkOrder.query.options(joinedload(RepairWorkOrder.customer))
        .filter_by(RepairOrderNo=repair_order_no)
        .first_or_404()
    )

    # Prepare order data using shared helper
    ro_dict = prepare_order_data_for_pdf(repair_order, order_type="repair_order")

    try:
        pdf_buffer = generate_repair_order_pdf(
            ro_dict,
            company_info={"name": "Awning Cleaning Industries - Repair Work Order"},
        )

        return send_file(
            pdf_buffer,
            as_attachment=False,
            download_name=f"WorkOrder_{repair_order_no}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        return redirect(
            url_for(
                "repair_work_orders.view_repair_work_order",
                repair_order_no=repair_order_no,
            )
        )
