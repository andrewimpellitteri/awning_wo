from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.work_order import WorkOrder, WorkOrderItem
from models.customer import Customer
from models.source import Source
from sqlalchemy import or_, func, desc
from extensions import db
from datetime import datetime

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
@login_required
def create_work_order():
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

    return render_template(
        "work_orders/create.html", customers=customers, sources=sources
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
    latest_wo = WorkOrder.query.order_by(desc(WorkOrder.WorkOrderNo)).first()
    if latest_wo:
        try:
            latest_num = int(latest_wo.WorkOrderNo)
            next_wo_no = str(latest_num + 1)
        except ValueError:
            next_wo_no = str(int(datetime.now().timestamp()))
    else:
        next_wo_no = "1"

    return jsonify({"next_wo_number": next_wo_no})
