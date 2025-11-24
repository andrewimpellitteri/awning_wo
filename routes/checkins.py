from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
)
from flask_login import login_required
from models.checkin import CheckIn, CheckInItem
from models.checkin_file import CheckInFile
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.inventory import Inventory
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from extensions import db
from datetime import datetime, date
from decorators import role_required
from utils.file_upload import (
    save_order_file_generic,
    allowed_file,
    commit_deferred_uploads,
    cleanup_deferred_files
)

checkins_bp = Blueprint("checkins", __name__, url_prefix="/checkins")


# ============================================================================
# HELPER FUNCTIONS
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


# ============================================================================
# CHECK-IN ROUTES
# ============================================================================


@checkins_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create_checkin():
    """Create a new check-in"""
    if request.method == "POST":
        try:
            # Get form data
            cust_id = request.form.get("CustID")
            date_in = _parse_date_field(request.form.get("DateIn"))
            date_required = _parse_date_field(request.form.get("DateRequired"))

            if not cust_id:
                flash("Customer is required", "error")
                return redirect(url_for("checkins.create_checkin"))

            if not date_in:
                date_in = date.today()

            # Create check-in
            checkin = CheckIn(
                CustID=cust_id,
                DateIn=date_in,
                Status="pending",
                DateRequired=date_required,
                ReturnTo=request.form.get("ReturnTo"),
                StorageTime=request.form.get("StorageTime"),
                RackNo=request.form.get("RackNo"),
                SpecialInstructions=request.form.get("SpecialInstructions"),
                RepairsNeeded=bool(request.form.get("RepairsNeeded")),
                RushOrder=bool(request.form.get("RushOrder"))
            )

            db.session.add(checkin)
            db.session.flush()  # Get the CheckInID

            # Process check-in items
            descriptions = request.form.getlist("item_description[]")
            materials = request.form.getlist("item_material[]")
            colors = request.form.getlist("item_color[]")
            qtys = request.form.getlist("item_qty[]")
            sizewgts = request.form.getlist("item_sizewgt[]")
            prices = request.form.getlist("item_price[]")
            conditions = request.form.getlist("item_condition[]")
            inventory_keys = request.form.getlist("item_inventorykey[]")

            for i in range(len(descriptions)):
                if descriptions[i]:  # Only add if description is not empty
                    # Get inventory key if present (empty string means manually added item)
                    inv_key = inventory_keys[i] if i < len(inventory_keys) and inventory_keys[i] else None
                    inv_key = int(inv_key) if inv_key and inv_key.strip() else None

                    item = CheckInItem(
                        CheckInID=checkin.CheckInID,
                        Description=descriptions[i],
                        Material=materials[i] if i < len(materials) else "Unknown",
                        Color=colors[i] if i < len(colors) else None,
                        Qty=int(qtys[i]) if i < len(qtys) and qtys[i] else 0,
                        SizeWgt=sizewgts[i] if i < len(sizewgts) else None,
                        Price=float(prices[i]) if i < len(prices) and prices[i] else None,
                        Condition=conditions[i] if i < len(conditions) else None,
                        InventoryKey=inv_key,  # Track if from inventory or NEW
                    )
                    db.session.add(item)

            # Handle file uploads with deferred S3 upload (prevents orphaned S3 files)
            uploaded_file_objects = []
            if 'files[]' in request.files:
                uploaded_files = request.files.getlist('files[]')
                if uploaded_files and uploaded_files[0].filename:  # Check if files were actually selected
                    for file in uploaded_files:
                        if file and file.filename and allowed_file(file.filename):
                            try:
                                # Use deferred upload - files staged in memory, uploaded after DB commit
                                file_obj = save_order_file_generic(
                                    order_no=str(checkin.CheckInID),
                                    file=file,
                                    order_type="checkin",
                                    to_s3=True,
                                    generate_thumbnails=False,  # Don't need thumbnails for check-ins
                                    file_model_class=CheckInFile,
                                    defer_s3_upload=True  # Changed to True for deferred upload
                                )

                                if file_obj:
                                    # Update the CheckInID since generic function doesn't know about it
                                    file_obj.CheckInID = checkin.CheckInID
                                    db.session.add(file_obj)
                                    uploaded_file_objects.append(file_obj)
                            except Exception as file_error:
                                # Log the error but don't fail the whole check-in
                                flash(f"Warning: Could not upload {file.filename}: {str(file_error)}", "warning")

            # Commit DB transaction first
            db.session.commit()

            # AFTER successful DB commit, upload files to S3
            # This prevents orphaned S3 files if DB commit fails
            if uploaded_file_objects:
                success, uploaded, failed = commit_deferred_uploads(uploaded_file_objects)
                if not success:
                    # Log warning but don't fail - DB is already committed
                    print(f"WARNING: {len(failed)} files failed to upload to S3 for check-in #{checkin.CheckInID}")
                    for file_obj, error in failed:
                        print(f"  - {file_obj.file_name}: {error}")
                        flash(f"Warning: File '{file_obj.file_name}' failed to upload to S3", "warning")

            flash(f"Check-in #{checkin.CheckInID} created successfully with {len(uploaded_file_objects)} files!", "success")
            return redirect(url_for("checkins.view_pending"))

        except IntegrityError as e:
            db.session.rollback()
            # Clean up deferred file data on rollback
            if 'uploaded_file_objects' in locals():
                cleanup_deferred_files(uploaded_file_objects)
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("checkins.create_checkin"))
        except Exception as e:
            db.session.rollback()
            # Clean up deferred file data on rollback
            if 'uploaded_file_objects' in locals():
                cleanup_deferred_files(uploaded_file_objects)
            flash(f"Error creating check-in: {str(e)}", "error")
            return redirect(url_for("checkins.create_checkin"))

    # GET request - show form
    customers = Customer.query.order_by(Customer.Name).all()
    return render_template(
        "checkins/new.html",
        customers=customers,
        today=date.today().strftime("%Y-%m-%d")
    )


@checkins_bp.route("/pending")
@login_required
@role_required("admin", "manager")
def view_pending():
    """View all pending check-ins"""
    pending_checkins = (
        CheckIn.query
        .filter_by(Status="pending")
        .order_by(CheckIn.DateIn.desc(), CheckIn.created_at.desc())
        .all()
    )
    return render_template("checkins/pending.html", checkins=pending_checkins)


@checkins_bp.route("/<int:checkin_id>")
@login_required
@role_required("admin", "manager")
def view_checkin(checkin_id):
    """View a specific check-in"""
    checkin = CheckIn.query.get_or_404(checkin_id)
    return render_template("checkins/detail.html", checkin=checkin)


@checkins_bp.route("/<int:checkin_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit_checkin(checkin_id):
    """Edit an existing check-in"""
    checkin = CheckIn.query.get_or_404(checkin_id)

    # Prevent editing processed check-ins
    if checkin.Status == "processed":
        flash("Cannot edit a processed check-in", "error")
        return redirect(url_for("checkins.view_checkin", checkin_id=checkin_id))

    if request.method == "POST":
        try:
            # Update check-in fields
            checkin.CustID = request.form.get("CustID")
            checkin.DateIn = _parse_date_field(request.form.get("DateIn")) or date.today()
            checkin.DateRequired = _parse_date_field(request.form.get("DateRequired"))
            checkin.ReturnTo = request.form.get("ReturnTo")
            checkin.StorageTime = request.form.get("StorageTime")
            checkin.RackNo = request.form.get("RackNo")
            checkin.SpecialInstructions = request.form.get("SpecialInstructions")
            checkin.RepairsNeeded = bool(request.form.get("RepairsNeeded"))
            checkin.RushOrder = bool(request.form.get("RushOrder"))

            # Handle check-in items - delete all existing and recreate
            # This follows the same pattern as repair order item updates (Issue #94)
            CheckInItem.query.filter_by(CheckInID=checkin.CheckInID).delete()

            # Process new items from form
            descriptions = request.form.getlist("item_description[]")
            materials = request.form.getlist("item_material[]")
            colors = request.form.getlist("item_color[]")
            qtys = request.form.getlist("item_qty[]")
            sizewgts = request.form.getlist("item_sizewgt[]")
            prices = request.form.getlist("item_price[]")
            conditions = request.form.getlist("item_condition[]")
            inventory_keys = request.form.getlist("item_inventorykey[]")

            for i in range(len(descriptions)):
                if descriptions[i]:  # Only add if description is not empty
                    # Get inventory key if present (empty string means manually added item)
                    inv_key = inventory_keys[i] if i < len(inventory_keys) and inventory_keys[i] else None
                    inv_key = int(inv_key) if inv_key and inv_key.strip() else None

                    item = CheckInItem(
                        CheckInID=checkin.CheckInID,
                        Description=descriptions[i],
                        Material=materials[i] if i < len(materials) else "Unknown",
                        Color=colors[i] if i < len(colors) else None,
                        Qty=int(qtys[i]) if i < len(qtys) and qtys[i] else 0,
                        SizeWgt=sizewgts[i] if i < len(sizewgts) else None,
                        Price=float(prices[i]) if i < len(prices) and prices[i] else None,
                        Condition=conditions[i] if i < len(conditions) else None,
                        InventoryKey=inv_key,  # Track if from inventory or NEW
                    )
                    db.session.add(item)

            # Handle file uploads with deferred S3 upload
            uploaded_file_objects = []
            if 'files[]' in request.files:
                uploaded_files = request.files.getlist('files[]')
                if uploaded_files and uploaded_files[0].filename:
                    for file in uploaded_files:
                        if file and file.filename and allowed_file(file.filename):
                            try:
                                file_obj = save_order_file_generic(
                                    order_no=str(checkin.CheckInID),
                                    file=file,
                                    order_type="checkin",
                                    to_s3=True,
                                    generate_thumbnails=False,
                                    file_model_class=CheckInFile,
                                    defer_s3_upload=True  # Changed to True for deferred upload
                                )

                                if file_obj:
                                    file_obj.CheckInID = checkin.CheckInID
                                    db.session.add(file_obj)
                                    uploaded_file_objects.append(file_obj)
                            except Exception as file_error:
                                flash(f"Warning: Could not upload {file.filename}: {str(file_error)}", "warning")

            # Commit DB transaction first
            db.session.commit()

            # AFTER successful DB commit, upload files to S3
            if uploaded_file_objects:
                success, uploaded, failed = commit_deferred_uploads(uploaded_file_objects)
                if not success:
                    print(f"WARNING: {len(failed)} files failed to upload to S3 for check-in #{checkin.CheckInID}")
                    for file_obj, error in failed:
                        print(f"  - {file_obj.file_name}: {error}")
                        flash(f"Warning: File '{file_obj.file_name}' failed to upload to S3", "warning")

            file_msg = f" with {len(uploaded_file_objects)} files" if uploaded_file_objects else ""
            flash(f"Check-in #{checkin.CheckInID} updated successfully{file_msg}!", "success")
            return redirect(url_for("checkins.view_checkin", checkin_id=checkin.CheckInID))

        except IntegrityError as e:
            db.session.rollback()
            # Clean up deferred file data on rollback
            if 'uploaded_file_objects' in locals():
                cleanup_deferred_files(uploaded_file_objects)
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for("checkins.edit_checkin", checkin_id=checkin_id))
        except Exception as e:
            db.session.rollback()
            # Clean up deferred file data on rollback
            if 'uploaded_file_objects' in locals():
                cleanup_deferred_files(uploaded_file_objects)
            flash(f"Error updating check-in: {str(e)}", "error")
            return redirect(url_for("checkins.edit_checkin", checkin_id=checkin_id))

    # GET request - show form with existing data
    customers = Customer.query.order_by(Customer.Name).all()
    # Convert items to dict for JSON serialization in template
    items_data = [item.to_dict() for item in checkin.items]
    return render_template(
        "checkins/edit.html",
        checkin=checkin,
        customers=customers,
        items_data=items_data,
        today=date.today().strftime("%Y-%m-%d")
    )


@checkins_bp.route("/<int:checkin_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "manager")
def delete_checkin(checkin_id):
    """Delete a check-in"""
    try:
        checkin = CheckIn.query.get_or_404(checkin_id)

        if checkin.Status == "processed":
            flash("Cannot delete a processed check-in", "error")
            return redirect(url_for("checkins.view_pending"))

        db.session.delete(checkin)
        db.session.commit()
        flash(f"Check-in #{checkin_id} deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting check-in: {str(e)}", "error")

    return redirect(url_for("checkins.view_pending"))


@checkins_bp.route("/api/customer_search")
@login_required
@role_required("admin", "manager")
def customer_search():
    """
    Search customers for Selectize.js autocomplete.

    Optimized with database indexes on LOWER(name), LOWER(contact), LOWER(custid).
    Uses joinedload to avoid N+1 queries on source_info relationship.
    """
    from sqlalchemy.orm import joinedload

    query = request.args.get("q", "").lower()

    # Preserve exact original behavior: return empty array if query < 2 chars
    if not query or len(query) < 2:
        return jsonify([])

    # Search by name, contact, or CustID (with optimized join)
    customers = (
        Customer.query
        .options(joinedload(Customer.source_info))  # Avoid N+1 queries
        .filter(
            func.lower(Customer.Name).contains(query) |
            func.lower(Customer.Contact).contains(query) |
            func.lower(Customer.CustID).contains(query)
        )
        .order_by(Customer.Name)
        .limit(20)
        .all()
    )

    # Exact same result format as before
    results = [
        {
            "value": c.CustID,
            "name": c.Name or "",
            "contact": c.Contact or "",
            "source": c.source_info.SSource if c.source_info else (c.Source or ""),
            "text": f"{c.Name}{' - ' + c.Contact if c.Contact else ''}",
            "address": c.Address or "",
            "city": c.City or "",
            "state": c.State or "",
        }
        for c in customers
    ]

    return jsonify(results)


@checkins_bp.route("/api/pending_count")
@login_required
def get_pending_count():
    """Get count of pending check-ins for navigation badge"""
    count = CheckIn.query.filter_by(Status="pending").count()
    return jsonify({"count": count})


@checkins_bp.route("/files/<int:file_id>/download")
@login_required
@role_required("admin", "manager")
def download_checkin_file(file_id):
    """Download a check-in file from S3"""
    from utils.file_upload import generate_presigned_url

    checkin_file = CheckInFile.query.get_or_404(file_id)

    try:
        # Generate presigned URL for download
        download_url = generate_presigned_url(checkin_file.file_path, expiration=300)
        return redirect(download_url)
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for("checkins.view_checkin", checkin_id=checkin_file.CheckInID))
