from flask import Blueprint, render_template, request, jsonify, url_for, flash, redirect
from flask_login import login_required
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.customer import Customer  # Assuming you might need this for joins
from models.source import Source
from sqlalchemy import or_, case, func, literal, desc, cast, Integer
from datetime import datetime
from extensions import db

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
    repair_work_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()
    return render_template(
        "repair_orders/detail.html", repair_work_order=repair_work_order
    )


@repair_work_orders_bp.route("/api/repair_work_orders")
def api_repair_work_orders():
    """
    API endpoint to provide repair work order data with robust date sorting.
    """
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()
    search = request.args.get("search", "").strip()

    query = RepairWorkOrder.query

    # ✅ Status quick filters
    if status == "pending":
        query = query.filter(
            or_(
                RepairWorkOrder.DateCompleted.is_(None),
                RepairWorkOrder.DateCompleted == "",
            )
        )
    elif status == "completed":
        query = query.filter(
            RepairWorkOrder.DateCompleted.isnot(None),
            RepairWorkOrder.DateCompleted != "",
        )
    elif status == "rush":
        query = query.filter(
            or_(RepairWorkOrder.RushOrder == "YES", RepairWorkOrder.FirmRush == "YES"),
            or_(
                RepairWorkOrder.DateCompleted.is_(None),
                RepairWorkOrder.DateCompleted == "",
            ),
        )

    # 🔎 Global search filter
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

    # 📝 Per-column filters
    filterable_columns = [
        "RepairOrderNo",
        "CustID",
        "ROName",
        "ITEM_TYPE",
        "TYPE_OF_REPAIR",
        "DateIn",
        "DateCompleted",
        "LOCATION",
    ]
    for col in filterable_columns:
        filter_val = request.args.get(f"filter_{col}")
        if filter_val:
            # Check for exact match on RepairOrderNo and CustID
            if col in ["RepairOrderNo", "CustID"]:
                query = query.filter(getattr(RepairWorkOrder, col) == filter_val)
            else:
                # Use partial match for all other columns
                query = query.filter(
                    getattr(RepairWorkOrder, col).ilike(f"%{filter_val}%")
                )

    # ↕️ Sorting logic with date parsing
    order_by_clauses = []
    i = 0
    while True:
        field = request.args.get(f"sort[{i}][field]")
        if not field:
            break
        direction = request.args.get(f"sort[{i}][dir]", "asc")
        column = getattr(RepairWorkOrder, field, None)

        if column:
            if field in ["RepairOrderNo", "CustID"]:
                cast_column = cast(column, Integer)
                order_by_clauses.append(
                    cast_column.desc() if direction == "desc" else cast_column.asc()
                )

            elif field in ["DateIn", "DateCompleted"]:
                # Use CASE with multiple formats for dates
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
                order_by_clauses.append(
                    cast_column.desc().nulls_last()
                    if direction == "desc"
                    else cast_column.asc().nulls_last()
                )
            else:
                order_by_clauses.append(
                    column.desc() if direction == "desc" else column.asc()
                )
        i += 1

    # Default sorting if none provided
    if order_by_clauses:
        query = query.order_by(*order_by_clauses)
    else:
        query = query.order_by(
            case(
                (
                    RepairWorkOrder.DateIn.op("~")(
                        "^[0-1][0-9]/[0-3][0-9]/[0-9]{2} [0-2][0-9]:[0-5][0-9]:[0-5][0-9]$"
                    ),
                    func.to_date(RepairWorkOrder.DateIn, "MM/DD/YY HH24:MI:SS"),
                ),
                (
                    RepairWorkOrder.DateIn.op("~")(
                        "^[0-2][0-9]{3}-[0-1][0-9]-[0-3][0-9]$"
                    ),
                    func.to_date(RepairWorkOrder.DateIn, "YYYY-MM-DD"),
                ),
                else_=literal(None),
            )
            .desc()
            .nulls_last(),
            RepairWorkOrder.RepairOrderNo.desc(),
        )

    total = query.count()
    pagination = query.paginate(page=page, per_page=size, error_out=False)

    data = [
        {
            "RepairOrderNo": order.RepairOrderNo,
            "CustID": order.CustID,
            "ROName": order.ROName,
            "ITEM_TYPE": order.ITEM_TYPE,
            "TYPE_OF_REPAIR": order.TYPE_OF_REPAIR,
            "DateIn": format_date_from_str(order.DateIn),
            "DateCompleted": format_date_from_str(order.DateCompleted),
            "LOCATION": order.LOCATION,
            "is_rush": order.RushOrder == "YES" or order.FirmRush == "YES",
            "detail_url": url_for(
                "repair_work_orders.view_repair_work_order",
                repair_order_no=order.RepairOrderNo,
            ),
            "customer_url": url_for(
                "customers.customer_detail", customer_id=order.CustID
            )
            if order.customer
            else None,
        }
        for order in pagination.items
    ]

    return jsonify(
        {
            "data": data,
            "total": total,
            "last_page": pagination.pages,
        }
    )


@repair_work_orders_bp.route("/new", methods=["GET", "POST"])
@repair_work_orders_bp.route("/new/<prefill_cust_id>", methods=["GET", "POST"])
@login_required
def create_repair_order(prefill_cust_id=None):
    """Create a new repair work order"""
    if request.method == "POST":
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
                WO_DATE=request.form.get("WO_DATE"),
                DATE_TO_SUB=request.form.get("DATE_TO_SUB"),
                DateRequired=request.form.get("DateRequired"),
                RushOrder=request.form.get("RushOrder", "0"),
                FirmRush=request.form.get("FirmRush", "0"),
                QUOTE=request.form.get("QUOTE"),
                QUOTE_BY=request.form.get("QUOTE_BY"),
                APPROVED=request.form.get("APPROVED"),
                RackNo=request.form.get("RackNo"),
                STORAGE=request.form.get("STORAGE"),
                ITEM_TYPE=request.form.get("ITEM_TYPE"),
                TYPE_OF_REPAIR=request.form.get("TYPE_OF_REPAIR"),
                SPECIALINSTRUCTIONS=request.form.get("SPECIALINSTRUCTIONS"),
                CLEAN=request.form.get("CLEAN"),
                SEECLEAN=request.form.get("SEECLEAN"),
                CLEANFIRST=request.form.get("CLEANFIRST"),
                REPAIRSDONEBY=request.form.get("REPAIRSDONEBY"),
                DateCompleted=request.form.get("DateCompleted"),
                MaterialList=request.form.get("MaterialList"),
                CUSTOMERPRICE=request.form.get("CUSTOMERPRICE"),
                RETURNSTATUS=request.form.get("RETURNSTATUS"),
                RETURNDATE=request.form.get("RETURNDATE"),
                LOCATION=request.form.get("LOCATION"),
                DATEOUT=request.form.get("DATEOUT"),
                DateIn=datetime.now().strftime("%Y-%m-%d"),
            )

            db.session.add(repair_order)
            db.session.flush()  # to get the RepairOrderNo

            # Handle repair order items
            item_descriptions = request.form.getlist("item_description[]")
            item_materials = request.form.getlist("item_material[]")
            item_qtys = request.form.getlist("item_qty[]")
            item_conditions = request.form.getlist("item_condition[]")
            item_colors = request.form.getlist("item_color[]")
            item_sizes = request.form.getlist("item_size[]")
            item_prices = request.form.getlist("item_price[]")

            for i, descrip in enumerate(item_descriptions):
                if descrip and i < len(item_materials):
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
                    "repair_orders.view_repair_order", repair_order_no=next_order_no
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
        form_data["CustID"] = str(prefill_cust_id)
    return render_template(
        "repair_orders/create.html",
        customers=customers,
        sources=sources,
        form_data=form_data,
    )


@repair_work_orders_bp.route("/<repair_order_no>/edit", methods=["GET", "POST"])
@login_required
def edit_repair_order(repair_order_no):
    """Edit an existing repair work order"""
    repair_order = RepairWorkOrder.query.filter_by(
        RepairOrderNo=repair_order_no
    ).first_or_404()

    if request.method == "POST":
        try:
            # Update the repair work order fields
            repair_order.CustID = request.form.get("CustID")
            repair_order.ROName = request.form.get("ROName")
            repair_order.SOURCE = request.form.get("SOURCE")
            repair_order.WO_DATE = request.form.get("WO_DATE")
            repair_order.DATE_TO_SUB = request.form.get("DATE_TO_SUB")
            repair_order.DateRequired = request.form.get("DateRequired")
            repair_order.RushOrder = "YES" if request.form.get("RushOrder") else "NO"
            repair_order.FirmRush = "YES" if request.form.get("FirmRush") else "NO"
            repair_order.QUOTE = request.form.get("QUOTE")
            repair_order.QUOTE_BY = request.form.get("QUOTE_BY")
            repair_order.APPROVED = request.form.get("APPROVED")
            repair_order.RackNo = request.form.get("RackNo")
            repair_order.STORAGE = request.form.get("STORAGE")
            repair_order.ITEM_TYPE = request.form.get("ITEM_TYPE")
            repair_order.TYPE_OF_REPAIR = request.form.get("TYPE_OF_REPAIR")
            repair_order.SPECIALINSTRUCTIONS = request.form.get("SPECIALINSTRUCTIONS")
            repair_order.CLEAN = request.form.get("CLEAN")
            repair_order.SEECLEAN = request.form.get("SEECLEAN")
            repair_order.CLEANFIRST = request.form.get("CLEANFIRST")
            repair_order.REPAIRSDONEBY = request.form.get("REPAIRSDONEBY")
            repair_order.DateCompleted = request.form.get("DateCompleted")
            repair_order.MaterialList = request.form.get("MaterialList")
            repair_order.CUSTOMERPRICE = request.form.get("CUSTOMERPRICE")
            repair_order.RETURNSTATUS = request.form.get("RETURNSTATUS")
            repair_order.RETURNDATE = request.form.get("RETURNDATE")
            repair_order.LOCATION = request.form.get("LOCATION")
            repair_order.DATEOUT = request.form.get("DATEOUT")

            # Handle existing items updates
            existing_item_ids = request.form.getlist("existing_item_id[]")
            existing_descriptions = request.form.getlist("existing_description[]")
            existing_materials = request.form.getlist("existing_material[]")
            existing_qtys = request.form.getlist("existing_qty[]")
            existing_conditions = request.form.getlist("existing_condition[]")
            existing_colors = request.form.getlist("existing_color[]")
            existing_sizes = request.form.getlist("existing_size[]")
            existing_prices = request.form.getlist("existing_price[]")
            items_to_delete = request.form.getlist("delete_item[]")

            # Delete marked items
            if items_to_delete:
                RepairWorkOrderItem.query.filter(
                    RepairWorkOrderItem.id.in_(items_to_delete)
                ).delete(synchronize_session=False)

            # Update existing items
            for i, item_id in enumerate(existing_item_ids):
                if item_id and i < len(existing_descriptions):
                    item = RepairWorkOrderItem.query.get(item_id)
                    if item:
                        item.Description = existing_descriptions[i]
                        item.Material = (
                            existing_materials[i] if i < len(existing_materials) else ""
                        )
                        item.Qty = existing_qtys[i] if i < len(existing_qtys) else "1"
                        item.Condition = (
                            existing_conditions[i]
                            if i < len(existing_conditions)
                            else ""
                        )
                        item.Color = (
                            existing_colors[i] if i < len(existing_colors) else ""
                        )
                        item.SizeWgt = (
                            existing_sizes[i] if i < len(existing_sizes) else ""
                        )
                        item.Price = (
                            existing_prices[i] if i < len(existing_prices) else ""
                        )

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
        repair_order=repair_order,
        customers=customers,
        sources=sources,
    )
