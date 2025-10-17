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
)
from utils.query_helpers import (
    apply_column_filters,
    apply_tabulator_sorting,
    apply_search_filter,
)


repair_work_orders_bp = Blueprint(
    "repair_work_orders", __name__, url_prefix="/repair_work_orders"
)


@repair_work_orders_bp.route("/<repair_order_no>/files/upload", methods=["POST"])
@login_required
def upload_repair_order_file(repair_order_no):
    """Upload a file to a repair order"""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    saved_file = save_repair_order_file(repair_order_no, file)
    if saved_file:
        db.session.add(saved_file)
        db.session.commit()
        return jsonify(
            {"message": "File uploaded successfully", "file_id": saved_file.id}
        )
    return jsonify({"error": "Invalid file type"}), 400


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
        cust_id = request.form.get("CustID")
        ro_name = request.form.get("ROName")

        errors = []
        if not cust_id:
            errors.append("Customer is required.")
        if not ro_name:
            errors.append("Name is required.")

        if errors:
            for error in errors:
                flash(error, "error")
            # Re-render the form with the data
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
        base_delay = 0.1  # 100ms base delay

        while retry_count < max_retries:
            try:
                # Generate next RepairOrderNo
                latest_order = RepairWorkOrder.query.order_by(
                    desc(cast(RepairWorkOrder.RepairOrderNo, Integer))
                ).first()
                print(latest_order, type(latest_order))
                if latest_order:
                    try:
                        next_num = int(latest_order.RepairOrderNo) + 1
                    except ValueError:
                        next_num = int(datetime.now().timestamp())
                else:
                    next_num = 1
                next_order_no = str(next_num)

                print(f"[DEBUG] Next RepairOrderNo: {next_order_no}")

                # Create the repair work order
                repair_order = RepairWorkOrder(
                    RepairOrderNo=next_order_no,
                    CustID=request.form.get("CustID"),
                    ROName=request.form.get("ROName"),
                    SOURCE=request.form.get("SOURCE"),
                    WO_DATE=datetime.strptime(
                        request.form.get("WO_DATE"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("WO_DATE")
                    else None,
                    DATE_TO_SUB=datetime.strptime(
                        request.form.get("DATE_TO_SUB"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("DATE_TO_SUB")
                    else None,
                    DateRequired=datetime.strptime(
                        request.form.get("DateRequired"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("DateRequired")
                    else None,
                    RushOrder="RushOrder" in request.form,
                    FirmRush="FirmRush" in request.form,
                    QUOTE=request.form.get("QUOTE") or None,  # String: 'YES', 'DONE', 'APPROVED', or NULL
                    # Storage/Location fields (See STORAGE_FIELDS_GUIDE.md)
                    RackNo=request.form.get("RackNo"),  # Primary location field
                    STORAGE=request.form.get(
                        "STORAGE"
                    ),  # Storage time type (TEMPORARY/SEASONAL)
                    SPECIALINSTRUCTIONS=request.form.get("SPECIALINSTRUCTIONS"),
                    CLEAN="CLEAN" in request.form,
                    SEECLEAN=request.form.get("SEECLEAN"),
                    REPAIRSDONEBY=request.form.get("REPAIRSDONEBY"),
                    DateCompleted=datetime.strptime(
                        request.form.get("DateCompleted"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("DateCompleted")
                    else None,
                    MaterialList=request.form.get("MaterialList"),
                    CUSTOMERPRICE=request.form.get("CUSTOMERPRICE"),
                    RETURNSTATUS=request.form.get("RETURNSTATUS"),
                    RETURNDATE=datetime.strptime(
                        request.form.get("RETURNDATE"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("RETURNDATE")
                    else None,
                    LOCATION=request.form.get("LOCATION"),  # Legacy - RackNo is primary
                    final_location=request.form.get(
                        "final_location"
                    ),  # Post-repair location
                    DATEOUT=datetime.strptime(
                        request.form.get("DATEOUT"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("DATEOUT")
                    else None,
                    DateIn=datetime.strptime(
                        request.form.get("DateIn"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("DateIn")
                    else datetime.now().date(),
                )

                db.session.add(repair_order)
                db.session.flush()  # to get the RepairOrderNo

                print(
                    f"[DEBUG] Repair order added to session: {repair_order.RepairOrderNo}"
                )

                # Sync source_name from customer (database trigger will also handle this)
                repair_order.sync_source_name()

                # Handle selected items from customer inventory
                from models.repair_order import RepairWorkOrderItem

                selected_item_ids = request.form.getlist("selected_items[]")
                print(f"[DEBUG] Selected item IDs from form: {selected_item_ids}")
                for item_id in selected_item_ids:
                    if not item_id:
                        continue

                    original_item = Inventory.query.filter_by(
                        InventoryKey=item_id
                    ).first()

                    if not original_item:
                        print(
                            f"[DEBUG] No inventory item found for InventoryKey: {item_id}"
                        )
                        continue

                    # Get the quantity from the form (default to inventory Qty or 1)
                    qty_raw = request.form.get(
                        f"item_qty_{item_id}", original_item.Qty or 1
                    )
                    try:
                        qty = int(qty_raw)
                    except ValueError:
                        qty = 1

                    print(
                        f"[DEBUG] Adding item: {original_item.Description}, Qty: {qty}"
                    )

                    # Create a new RepairWorkOrderItem
                    repair_item = RepairWorkOrderItem(
                        RepairOrderNo=next_order_no,
                        CustID=request.form.get("CustID"),
                        Description=original_item.Description,
                        Material=original_item.Material,
                        Qty=qty,
                        Condition=original_item.Condition,
                        Color=original_item.Color,
                        SizeWgt=original_item.SizeWgt,
                        Price=original_item.Price,
                    )
                    db.session.add(repair_item)

                # Handle new repair order items (manually added)
                item_descriptions = request.form.getlist("item_description[]")
                item_materials = request.form.getlist("item_material[]")
                item_qtys = request.form.getlist("item_qty[]")
                item_conditions = request.form.getlist("item_condition[]")
                item_colors = request.form.getlist("item_color[]")
                item_sizes = request.form.getlist("item_size_wgt[]")
                item_prices = request.form.getlist("item_price[]")

                print(f"[DEBUG] New item descriptions from form: {item_descriptions}")
                for i, descrip in enumerate(item_descriptions):
                    print(f"[DEBUG] Processing new item {i}: {descrip}")
                    if descrip and descrip.strip():
                        repair_item = RepairWorkOrderItem(
                            RepairOrderNo=next_order_no,
                            CustID=request.form.get("CustID"),
                            Description=descrip,
                            Material=item_materials[i]
                            if i < len(item_materials)
                            else "",
                            Qty=item_qtys[i] if i < len(item_qtys) else "1",
                            Condition=item_conditions[i]
                            if i < len(item_conditions)
                            else "",
                            Color=item_colors[i] if i < len(item_colors) else "",
                            SizeWgt=item_sizes[i] if i < len(item_sizes) else "",
                            Price=item_prices[i] if i < len(item_prices) else "",
                        )
                        print(f"[DEBUG] Qty raw from form: {qty}")
                        db.session.add(repair_item)

                # Handle file uploads
                uploaded_files = []
                if "files[]" in request.files:
                    files = request.files.getlist("files[]")
                    print(f"Processing {len(files)} files")

                    for i, file in enumerate(files):
                        if file and file.filename:
                            ro_file = save_repair_order_file(
                                next_order_no,
                                file,
                                to_s3=True,
                                generate_thumbnails=True,
                            )
                            if not ro_file:
                                raise Exception(
                                    f"Failed to process file: {file.filename}"
                                )

                            uploaded_files.append(ro_file)
                            db.session.add(ro_file)
                            print(
                                f"Prepared file {i + 1}/{len(files)}: {ro_file.filename}"
                            )

                            if ro_file.thumbnail_path:
                                print(
                                    f"  - Thumbnail generated: {ro_file.thumbnail_path}"
                                )

                # --- Handle SEECLEAN backlink ---
                see_clean = request.form.get("SEECLEAN")
                if see_clean and see_clean.strip():
                    # Find the referenced work order and update its SeeRepair field
                    from models.work_order import WorkOrder

                    referenced_work_order = WorkOrder.query.filter_by(
                        WorkOrderNo=see_clean.strip()
                    ).first()
                    if referenced_work_order:
                        referenced_work_order.SeeRepair = next_order_no
                        flash(
                            f"Auto-linked Work Order {see_clean} to this Repair Order",
                            "info",
                        )

                db.session.commit()
                flash(
                    f"Repair Work Order {next_order_no} created successfully"
                    + (
                        f" with {len(uploaded_files)} files!" if uploaded_files else "!"
                    ),
                    "success",
                )
                return redirect(
                    url_for(
                        "repair_work_orders.view_repair_work_order",
                        repair_order_no=next_order_no,
                    )
                )

            except IntegrityError as ie:
                db.session.rollback()
                retry_count += 1

                # Check if it's a duplicate key error
                error_msg = (
                    str(ie.orig).lower() if hasattr(ie, "orig") else str(ie).lower()
                )
                is_duplicate = "duplicate" in error_msg or "unique" in error_msg

                if is_duplicate and retry_count < max_retries:
                    # Exponential backoff with jitter
                    delay = base_delay * (2**retry_count) + (random.random() * 0.05)
                    print(
                        f"Duplicate repair order number detected. Retry {retry_count}/{max_retries} after {delay:.3f}s"
                    )
                    time.sleep(delay)
                    continue  # Retry the loop
                else:
                    # Not a duplicate error or max retries exceeded
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
        cust_id = request.form.get("CustID")
        ro_name = request.form.get("ROName")

        errors = []
        if not cust_id:
            errors.append("Customer is required.")
        if not ro_name:
            errors.append("Name is required.")

        if errors:
            for error in errors:
                flash(error, "error")
            # Re-render the form with the data
            customers = Customer.query.order_by(Customer.Name).all()
            sources = Source.query.order_by(Source.SSource).all()
            return render_template(
                "repair_orders/edit.html",
                repair_work_order=repair_order,
                customers=customers,
                sources=sources,
            )

        try:
            # Track if customer changed (for source_name sync)
            old_cust_id = repair_order.CustID

            # Update the repair work order fields
            repair_order.CustID = cust_id
            repair_order.ROName = ro_name
            repair_order.SOURCE = request.form.get("SOURCE")
            repair_order.WO_DATE = (
                datetime.strptime(request.form.get("WO_DATE"), "%Y-%m-%d").date()
                if request.form.get("WO_DATE")
                else None
            )
            repair_order.DATE_TO_SUB = (
                datetime.strptime(request.form.get("DATE_TO_SUB"), "%Y-%m-%d").date()
                if request.form.get("DATE_TO_SUB")
                else None
            )
            repair_order.DateRequired = (
                datetime.strptime(request.form.get("DateRequired"), "%Y-%m-%d").date()
                if request.form.get("DateRequired")
                else None
            )
            repair_order.RushOrder = "RushOrder" in request.form
            repair_order.FirmRush = "FirmRush" in request.form
            repair_order.QUOTE = request.form.get("QUOTE") or None  # String: 'YES', 'DONE', 'APPROVED', or NULL
            # Storage/Location fields (See STORAGE_FIELDS_GUIDE.md)
            repair_order.RackNo = request.form.get("RackNo")  # Primary location field
            repair_order.STORAGE = request.form.get(
                "STORAGE"
            )  # Storage time type (TEMPORARY/SEASONAL)
            repair_order.SPECIALINSTRUCTIONS = request.form.get("SPECIALINSTRUCTIONS")
            repair_order.CLEAN = "CLEAN" in request.form
            repair_order.SEECLEAN = request.form.get("SEECLEAN")
            repair_order.REPAIRSDONEBY = request.form.get("REPAIRSDONEBY")
            repair_order.DateCompleted = (
                datetime.strptime(request.form.get("DateCompleted"), "%Y-%m-%d").date()
                if request.form.get("DateCompleted")
                else None
            )
            repair_order.MaterialList = request.form.get("MaterialList")
            repair_order.CUSTOMERPRICE = request.form.get("CUSTOMERPRICE")
            repair_order.RETURNSTATUS = request.form.get("RETURNSTATUS")
            repair_order.RETURNDATE = (
                datetime.strptime(request.form.get("RETURNDATE"), "%Y-%m-%d").date()
                if request.form.get("RETURNDATE")
                else None
            )
            # Legacy LOCATION field - kept for backward compatibility but RackNo is primary
            repair_order.LOCATION = request.form.get("LOCATION")
            repair_order.final_location = request.form.get(
                "final_location"
            )  # Post-repair location
            repair_order.DATEOUT = (
                datetime.strptime(request.form.get("DATEOUT"), "%Y-%m-%d").date()
                if request.form.get("DATEOUT")
                else None
            )
            repair_order.DateIn = (
                datetime.strptime(request.form.get("DateIn"), "%Y-%m-%d").date()
                if request.form.get("DateIn")
                else None
            )

            # Handle items: delete all existing and recreate from form data
            RepairWorkOrderItem.query.filter_by(RepairOrderNo=repair_order_no).delete()

            # Get existing item data from form
            existing_descriptions = request.form.getlist("existing_description[]")
            existing_materials = request.form.getlist("existing_material[]")
            existing_qtys = request.form.getlist("existing_qty[]")
            existing_conditions = request.form.getlist("existing_condition[]")
            existing_colors = request.form.getlist("existing_color[]")
            existing_sizes = request.form.getlist("existing_size[]")
            existing_prices = request.form.getlist("existing_price[]")

            # Recreate existing items (that weren't marked for deletion)
            for i, descrip in enumerate(existing_descriptions):
                if descrip and descrip.strip():
                    price_str = existing_prices[i] if i < len(existing_prices) else None
                    repair_item = RepairWorkOrderItem(
                        RepairOrderNo=repair_order_no,
                        CustID=request.form.get("CustID"),
                        Description=descrip,
                        Material=existing_materials[i]
                        if i < len(existing_materials)
                        else "",
                        Qty=existing_qtys[i] if i < len(existing_qtys) else "1",
                        Condition=existing_conditions[i]
                        if i < len(existing_conditions)
                        else "",
                        Color=existing_colors[i] if i < len(existing_colors) else "",
                        SizeWgt=existing_sizes[i] if i < len(existing_sizes) else "",
                        Price=price_str if price_str else None,
                    )
                    db.session.add(repair_item)

            # Handle selected items from customer inventory
            selected_item_ids = request.form.getlist("selected_items[]")
            print(f"[DEBUG] Selected item IDs from form: {selected_item_ids}")
            for item_id in selected_item_ids:
                if not item_id:
                    continue

                original_item = Inventory.query.filter_by(
                    InventoryKey=item_id
                ).first()

                if not original_item:
                    print(
                        f"[DEBUG] No inventory item found for InventoryKey: {item_id}"
                    )
                    continue

                # Get the quantity from the form (default to inventory Qty or 1)
                qty_raw = request.form.get(
                    f"item_qty_{item_id}", original_item.Qty or 1
                )
                try:
                    qty = int(qty_raw)
                except ValueError:
                    qty = 1

                print(
                    f"[DEBUG] Adding item: {original_item.Description}, Qty: {qty}"
                )

                # Create a new RepairWorkOrderItem
                repair_item = RepairWorkOrderItem(
                    RepairOrderNo=repair_order_no,
                    CustID=request.form.get("CustID"),
                    Description=original_item.Description,
                    Material=original_item.Material,
                    Qty=qty,
                    Condition=original_item.Condition,
                    Color=original_item.Color,
                    SizeWgt=original_item.SizeWgt,
                    Price=original_item.Price,
                )
                db.session.add(repair_item)


            # Handle new items
            new_descriptions = request.form.getlist("new_description[]")
            new_materials = request.form.getlist("new_material[]")
            new_qtys = request.form.getlist("new_qty[]")
            new_conditions = request.form.getlist("new_condition[]")
            new_colors = request.form.getlist("new_color[]")
            new_sizes = request.form.getlist("new_size[]")
            new_prices = request.form.getlist("new_price[]")

            for i, descrip in enumerate(new_descriptions):
                if descrip and descrip.strip():
                    price_str = new_prices[i] if i < len(new_prices) else None
                    repair_item = RepairWorkOrderItem(
                        RepairOrderNo=repair_order_no,
                        CustID=request.form.get("CustID"),
                        Description=descrip,
                        Material=new_materials[i] if i < len(new_materials) else "",
                        Qty=new_qtys[i] if i < len(new_qtys) else "1",
                        Condition=new_conditions[i] if i < len(new_conditions) else "",
                        Color=new_colors[i] if i < len(new_colors) else "",
                        SizeWgt=new_sizes[i] if i < len(new_sizes) else "",
                        Price=price_str if price_str else None,
                    )
                    db.session.add(repair_item)

            # Handle file uploads
            uploaded_files = []
            if "files[]" in request.files:
                files = request.files.getlist("files[]")
                print(f"Processing {len(files)} files")

                for i, file in enumerate(files):
                    if file and file.filename:
                        ro_file = save_repair_order_file(
                            repair_order_no, file, to_s3=True, generate_thumbnails=True
                        )
                        if not ro_file:
                            raise Exception(f"Failed to process file: {file.filename}")

                        uploaded_files.append(ro_file)
                        db.session.add(ro_file)
                        print(f"Prepared file {i + 1}/{len(files)}: {ro_file.filename}")

                        if ro_file.thumbnail_path:
                            print(f"  - Thumbnail generated: {ro_file.thumbnail_path}")

            # --- Handle SEECLEAN backlink ---
            see_clean_new = request.form.get("SEECLEAN")
            see_clean_old = (
                repair_order.SEECLEAN.strip() if repair_order.SEECLEAN else None
            )

            # If SEECLEAN changed, update backlinks
            if see_clean_new != see_clean_old:
                # Remove old backlink if it existed
                if see_clean_old:
                    from models.work_order import WorkOrder

                    old_work_order = WorkOrder.query.filter_by(
                        WorkOrderNo=see_clean_old
                    ).first()
                    if old_work_order and old_work_order.SeeRepair == repair_order_no:
                        old_work_order.SeeRepair = None

                # Add new backlink if provided
                if see_clean_new and see_clean_new.strip():
                    from models.work_order import WorkOrder

                    new_work_order = WorkOrder.query.filter_by(
                        WorkOrderNo=see_clean_new.strip()
                    ).first()
                    if new_work_order:
                        new_work_order.SeeRepair = repair_order_no
                        flash(
                            f"Auto-linked Work Order {see_clean_new} to this Repair Order",
                            "info",
                        )

            # Sync source_name if customer changed
            if repair_order.CustID != old_cust_id:
                repair_order.sync_source_name()

            db.session.commit()
            flash(
                f"Repair Work Order {repair_order_no} updated successfully"
                + (f" with {len(uploaded_files)} files!" if uploaded_files else "!"),
                "success",
            )
            return redirect(
                url_for(
                    "repair_work_orders.view_repair_work_order",
                    repair_order_no=repair_order_no,
                )
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating repair work order: {str(e)}", "error")

    # GET request - show form with existing data
    customers = Customer.query.order_by(Customer.CustID).all()
    sources = Source.query.order_by(Source.SSource).all()

    return render_template(
        "repair_orders/edit.html",
        repair_work_order=repair_order,  # FIX: Use consistent naming
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
        return redirect(url_for("repair_work_orders.list_repair_work_orders"))

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting repair work order: {str(e)}", "error")
        return redirect(
            url_for(
                "repair_work_orders.view_repair_work_order",
                repair_order_no=repair_order_no,
            )
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
