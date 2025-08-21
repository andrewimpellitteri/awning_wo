from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.cust_awning import CustAwning
from extensions import db
from sqlalchemy import or_

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/")
@login_required
def inventory_list():
    """Display all inventory items with search functionality"""
    search_query = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = CustAwning.query

    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                CustAwning.Description.contains(search_query),
                CustAwning.Material.contains(search_query),
                CustAwning.Color.contains(search_query),
                CustAwning.Condition.contains(search_query),
            )
        )

    items = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "inventory/list.html",
        items=items,
        search_query=search_query,
    )


@inventory_bp.route("/view/<int:item_id>")
@login_required
def inventory_detail(item_id):
    """Display detailed view of an inventory item"""
    item = CustAwning.query.get_or_404(item_id)
    return render_template("inventory/detail.html", item=item)


@inventory_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_inventory():
    """Create a new inventory item"""
    if request.method == "POST":
        data = request.form

        try:
            item = CustAwning(
                Description=data.get("Description"),
                Material=data.get("Material"),
                Condition=data.get("Condition"),
                Color=data.get("Color"),
                SizeWgt=data.get("SizeWgt"),
                Price=data.get("Price"),
                CustID=data.get("CustID"),
                Qty=data.get("Qty"),
                InventoryKey=data.get("InventoryKey"),
            )

            db.session.add(item)
            db.session.commit()

            flash("Inventory item created successfully", "success")
            return redirect(url_for("inventory.inventory_detail", item_id=item.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating inventory item: {str(e)}", "error")
            return render_template("inventory/form.html", form_data=data)

    return render_template("inventory/form.html")


@inventory_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit_inventory(item_id):
    """Edit an existing inventory item"""
    item = CustAwning.query.get_or_404(item_id)

    if request.method == "POST":
        data = request.form

        try:
            item.Description = data.get("Description")
            item.Material = data.get("Material")
            item.Condition = data.get("Condition")
            item.Color = data.get("Color")
            item.SizeWgt = data.get("SizeWgt")
            item.Price = data.get("Price")
            item.CustID = data.get("CustID")
            item.Qty = data.get("Qty")
            item.InventoryKey = data.get("InventoryKey")

            db.session.commit()
            flash("Inventory item updated successfully", "success")
            return redirect(url_for("inventory.inventory_detail", item_id=item.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating inventory item: {str(e)}", "error")

    return render_template("inventory/form.html", item=item, edit_mode=True)


@inventory_bp.route("/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_inventory(item_id):
    """Delete an inventory item"""
    item = CustAwning.query.get_or_404(item_id)

    try:
        db.session.delete(item)
        db.session.commit()
        flash("Inventory item deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting inventory item: {str(e)}", "error")

    return redirect(url_for("inventory.inventory_list"))


# --- API endpoints ---


@inventory_bp.route("/api/search")
@login_required
def api_search_inventory():
    """API endpoint for searching inventory"""
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    items = (
        CustAwning.query.filter(
            or_(
                CustAwning.Description.contains(query),
                CustAwning.Material.contains(query),
                CustAwning.Color.contains(query),
                CustAwning.Condition.contains(query),
            )
        )
        .limit(10)
        .all()
    )

    return jsonify(
        [
            {
                "id": item.id,
                "description": item.Description,
                "material": item.Material,
                "color": item.Color,
                "condition": item.Condition,
                "qty": item.Qty,
            }
            for item in items
        ]
    )
