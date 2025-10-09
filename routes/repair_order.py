from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    url_for,
    flash,
    redirect,
    send_file,
)
from flask_login import login_required
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.customer import Customer  # Assuming you might need this for joins
from models.source import Source
from sqlalchemy import or_, case, func, literal, desc, cast, Integer
from datetime import datetime
from extensions import db
from decorators import role_required
from repair_order_pdf import generate_repair_order_pdf
from sqlalchemy.orm import joinedload
from utils.pdf_helpers import prepare_order_data_for_pdf


repair_work_orders_bp = Blueprint(
    "repair_work_orders", __name__, url_prefix="/repair_work_orders"
)


def format_date_from_str(value):
    """Ensure dates are returned as YYYY-MM-DD strings to avoid object serialization issues."""
    if not value:
        return None
    # If it's already a string, assume correct format. Otherwise, format the date/datetime object.
    return value.strftime("%Y-%m-%d") if not isinstance(value, str) else value


@repair_work_orders_bp.route("/")
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
        RepairWorkOrder.query.options(joinedload(RepairWorkOrder.customer))
        .filter_by(RepairOrderNo=repair_order_no)
        .first_or_404()
    )
    return render_template(
        "repair_orders/detail.html", repair_work_order=repair_work_order
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

    is_source_filter = request.args.get("filter_Source")
    is_source_sort = any(
        request.args.get(f"sort[{i}][field]") == "Source" for i in range(5)
    )

    # If sorting or filtering by source, join necessary tables
    if is_source_filter or is_source_sort:
        query = query.join(RepairWorkOrder.customer).join(Customer.source_info)
        query = query.options(
            joinedload(RepairWorkOrder.customer).joinedload(Customer.source_info)
        )
    else:
        query = query.options(joinedload(RepairWorkOrder.customer))

    # --------------------------
    # ✅ Status filters
    # ---------------------------
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

    # ---------------------------
    # 🔎 Global search
    # ---------------------------
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RepairWorkOrder.RepairOrderNo.ilike(search_term),
                RepairWorkOrder.CustID.ilike(search_term),
                RepairWorkOrder.ROName.ilike(search_term),
                RepairWorkOrder.ITEM_TYPE.ilike(search_term),
                RepairWorkOrder.TYPE_OF_REPAIR.ilike(search_term),
                RepairWorkOrder.LOCATION.ilike(search_term),
            )
        )

    # ---------------------------
    # 🎯 Column filters
    # ---------------------------
    filterable_columns = {
        "RepairOrderNo": RepairWorkOrder.RepairOrderNo,
        "CustID": RepairWorkOrder.CustID,
        "ROName": RepairWorkOrder.ROName,
        "DateIn": RepairWorkOrder.DateIn,
        "DateCompleted": RepairWorkOrder.DateCompleted,
    }

    for col, column in filterable_columns.items():
        filter_val = request.args.get(f"filter_{col}")
        if filter_val:
            if col in ["RepairOrderNo", "CustID"]:
                query = query.filter(column == filter_val)
            else:
                query = query.filter(column.ilike(f"%{filter_val}%"))

    # Special handling for Source filter
    filter_val = request.args.get("filter_Source")
    if filter_val:
        query = query.join(RepairWorkOrder.customer).join(Customer.source_info)
        query = query.filter(Source.SSource.ilike(f"%{filter_val}%"))

    # ---------------------------
    # ↕️ Sorting
    # ---------------------------
    order_by_clauses = []
    simple_sort = request.args.get("sort")
    simple_dir = request.args.get("dir", "asc")

    if simple_sort:  # Simple sort mode
        column = getattr(RepairWorkOrder, simple_sort, None)
        if column:
            if simple_sort in ["RepairOrderNo", "CustID"]:
                column = cast(column, Integer)
            order_by_clauses.append(
                column.desc() if simple_dir == "desc" else column.asc()
            )
    else:  # Tabulator multi-sort mode
        i = 0
        while True:
            field = request.args.get(f"sort[{i}][field]")
            if not field:
                break
            direction = request.args.get(f"sort[{i}][dir]", "asc")

            if field == "Source":
                column = Source.SSource
            else:
                column = getattr(RepairWorkOrder, field, None)

            if column:
                if field in ["RepairOrderNo", "CustID"]:
                    column = cast(column, Integer)
                order_by_clauses.append(
                    column.desc() if direction == "desc" else column.asc()
                )
            i += 1

    # Apply default sort if none provided
    if order_by_clauses:
        query = query.order_by(*order_by_clauses)
    else:
        query = query.order_by(
            RepairWorkOrder.DateIn.desc(), RepairWorkOrder.RepairOrderNo.desc()
        )

    # ---------------------------
    # 📊 Pagination & results
    # ---------------------------
    total = query.count()
    pagination = query.paginate(page=page, per_page=size, error_out=False)

    data = []
    for order in pagination.items:
        data.append(
            {
                "RepairOrderNo": order.RepairOrderNo,
                "CustID": order.CustID,
                "ROName": order.ROName,
                "DateIn": format_date_from_str(order.DateIn),
                "DateCompleted": format_date_from_str(order.DateCompleted),
                "Source": (
                    order.customer.source_info.SSource
                    if order.customer and order.customer.source_info
                    else None
                ),
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
        desc(RepairWorkOrder.RepairOrderNo)
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

        try:
            # Generate next RepairOrderNo
            latest_order = RepairWorkOrder.query.order_by(
                desc(RepairWorkOrder.RepairOrderNo)
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
                QUOTE="QUOTE" in request.form,
                QUOTE_BY=request.form.get("QUOTE_BY"),
                APPROVED="APPROVED" in request.form,
                RackNo=request.form.get("RackNo"),
                STORAGE=request.form.get("STORAGE"),
                ITEM_TYPE=request.form.get("ITEM_TYPE"),
                TYPE_OF_REPAIR=request.form.get("TYPE_OF_REPAIR"),
                SPECIALINSTRUCTIONS=request.form.get("SPECIALINSTRUCTIONS"),
                CLEAN="CLEAN" in request.form,
                SEECLEAN=request.form.get("SEECLEAN"),
                CLEANFIRST="CLEANFIRST" in request.form,
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
                LOCATION=request.form.get("LOCATION"),
                DATEOUT=datetime.strptime(
                    request.form.get("DATEOUT"), "%Y-%m-%d"
                ).date()
                if request.form.get("DATEOUT")
                else None,
                DateIn=datetime.now().date(),
            )

            db.session.add(repair_order)
            db.session.flush()  # to get the RepairOrderNo

            # Handle selected items from customer inventory
            from models.work_order import WorkOrderItem

            selected_item_ids = request.form.getlist("selected_items[]")

            for item_id in selected_item_ids:
                if item_id:
                    # Fetch the original item from work orders
                    original_item = WorkOrderItem.query.get(item_id)
                    if original_item:
                        qty_key = f"item_qty_{item_id}"
                        qty = request.form.get(qty_key, original_item.Qty or "1")

                        # Create a copy of this item for the repair order
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

            for i, descrip in enumerate(item_descriptions):
                if descrip and descrip.strip():
                    repair_item = RepairWorkOrderItem(
                        RepairOrderNo=next_order_no,
                        CustID=request.form.get("CustID"),
                        Description=descrip,
                        Material=item_materials[i] if i < len(item_materials) else "",
                        Qty=item_qtys[i] if i < len(item_qtys) else "1",
                        Condition=item_conditions[i]
                        if i < len(item_conditions)
                        else "",
                        Color=item_colors[i] if i < len(item_colors) else "",
                        SizeWgt=item_sizes[i] if i < len(item_sizes) else "",
                        Price=item_prices[i] if i < len(item_prices) else "",
                    )
                    db.session.add(repair_item)

            db.session.commit()
            flash(f"Repair Work Order {next_order_no} created successfully!", "success")
            return redirect(
                url_for(
                    "repair_work_orders.view_repair_work_order",
                    repair_order_no=next_order_no,
                )
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
            repair_order.QUOTE = "QUOTE" in request.form
            repair_order.QUOTE_BY = request.form.get("QUOTE_BY")
            repair_order.APPROVED = "APPROVED" in request.form
            repair_order.RackNo = request.form.get("RackNo")
            repair_order.STORAGE = request.form.get("STORAGE")
            repair_order.ITEM_TYPE = request.form.get("ITEM_TYPE")
            repair_order.TYPE_OF_REPAIR = request.form.get("TYPE_OF_REPAIR")
            repair_order.SPECIALINSTRUCTIONS = request.form.get("SPECIALINSTRUCTIONS")
            repair_order.CLEAN = "CLEAN" in request.form
            repair_order.SEECLEAN = request.form.get("SEECLEAN")
            repair_order.CLEANFIRST = "CLEANFIRST" in request.form
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
            repair_order.LOCATION = request.form.get("LOCATION")
            repair_order.DATEOUT = (
                datetime.strptime(request.form.get("DATEOUT"), "%Y-%m-%d").date()
                if request.form.get("DATEOUT")
                else None
            )

            # Handle items: delete all existing and recreate from form data
            # This is simpler than trying to update items with composite keys
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
                        Price=existing_prices[i] if i < len(existing_prices) else "",
                    )
                    db.session.add(repair_item)

            # Handle selected items from customer inventory
            from models.work_order import WorkOrderItem

            selected_item_ids = request.form.getlist("selected_items[]")

            for item_id in selected_item_ids:
                if item_id:
                    # Fetch the original item from work orders
                    original_item = WorkOrderItem.query.get(item_id)
                    if original_item:
                        qty_key = f"item_qty_{item_id}"
                        qty = request.form.get(qty_key, original_item.Qty or "1")

                        # Create a copy of this item for the repair order
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
                    repair_item = RepairWorkOrderItem(
                        RepairOrderNo=repair_order_no,
                        CustID=request.form.get("CustID"),
                        Description=descrip,
                        Material=new_materials[i] if i < len(new_materials) else "",
                        Qty=new_qtys[i] if i < len(new_qtys) else "1",
                        Condition=new_conditions[i] if i < len(new_conditions) else "",
                        Color=new_colors[i] if i < len(new_colors) else "",
                        SizeWgt=new_sizes[i] if i < len(new_sizes) else "",
                        Price=new_prices[i] if i < len(new_prices) else "",
                    )
                    db.session.add(repair_item)

            db.session.commit()
            flash(
                f"Repair Work Order {repair_order_no} updated successfully!", "success"
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
    """Delete a repair work order and all associated items"""

    repair_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()

    try:
        # Optional: Add business logic checks
        # For example, prevent deletion of completed orders
        # if repair_order.DateCompleted:
        #     flash("Cannot delete completed repair orders", "error")
        #     return redirect(url_for('repair_work_orders.view_repair_work_order',
        #                           repair_order_no=repair_order_no))

        # Delete associated items first (if cascade is not set up)
        RepairWorkOrderItem.query.filter_by(RepairOrderNo=repair_order_no).delete()

        # Delete the repair order
        db.session.delete(repair_order)
        db.session.commit()

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
