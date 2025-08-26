from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.inventory import Inventory  # Updated import
from extensions import db
from sqlalchemy import or_
import uuid

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/")
@login_required
def inventory_list():
    """Display all inventory items with search functionality"""
    search_query = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Inventory.query

    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Inventory.Description.contains(search_query),
                Inventory.Material.contains(search_query),
                Inventory.Color.contains(search_query),
                Inventory.Condition.contains(search_query),
                Inventory.CustID.contains(search_query),
            )
        )

    items = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "inventory/list.html",
        items=items,
        search_query=search_query,
    )


@inventory_bp.route("/view/<inventory_key>")
@login_required
def inventory_detail(inventory_key):
    """Display detailed view of an inventory item"""
    item = Inventory.query.get_or_404(inventory_key)
    return render_template("inventory/detail.html", item=item)


@inventory_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_inventory():
    """Create a new inventory item"""
    if request.method == "POST":
        data = request.form

        try:
            # Generate unique inventory key
            inventory_key = f"INV_{uuid.uuid4().hex[:8].upper()}"

            item = Inventory(
                InventoryKey=inventory_key,
                Description=data.get("Description"),
                Material=data.get("Material"),
                Condition=data.get("Condition"),
                Color=data.get("Color"),
                SizeWgt=data.get("SizeWgt"),
                Price=data.get("Price"),
                CustID=data.get("CustID"),
                Qty=data.get("Qty", "0"),
            )

            db.session.add(item)
            db.session.commit()

            flash("Inventory item created successfully", "success")
            return redirect(
                url_for("inventory.inventory_detail", inventory_key=inventory_key)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating inventory item: {str(e)}", "error")
            return render_template("inventory/form.html", form_data=data)

    return render_template("inventory/form.html")


@inventory_bp.route("/edit/<inventory_key>", methods=["GET", "POST"])
@login_required
def edit_inventory(inventory_key):
    """Edit an existing inventory item"""
    item = Inventory.query.get_or_404(inventory_key)

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

            db.session.commit()
            flash("Inventory item updated successfully", "success")
            return redirect(
                url_for("inventory.inventory_detail", inventory_key=inventory_key)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating inventory item: {str(e)}", "error")

    return render_template("inventory/form.html", item=item, edit_mode=True)


@inventory_bp.route("/delete/<inventory_key>", methods=["POST"])
@login_required
def delete_inventory(inventory_key):
    """Delete an inventory item"""
    item = Inventory.query.get_or_404(inventory_key)

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
    cust_id = request.args.get("cust_id", "").strip()

    if not query and not cust_id:
        return jsonify([])

    base_query = Inventory.query

    # Filter by customer if provided
    if cust_id:
        base_query = base_query.filter_by(CustID=cust_id)

    # Apply search filter if provided
    if query:
        base_query = base_query.filter(
            or_(
                Inventory.Description.contains(query),
                Inventory.Material.contains(query),
                Inventory.Color.contains(query),
                Inventory.Condition.contains(query),
            )
        )

    items = base_query.limit(10).all()

    return jsonify(
        [
            {
                "id": item.InventoryKey,
                "description": item.Description,
                "material": item.Material,
                "color": item.Color,
                "condition": item.Condition,
                "qty": item.Qty,
                "price": item.Price,
                "size_wgt": item.SizeWgt,
                "cust_id": item.CustID,
            }
            for item in items
        ]
    )


@inventory_bp.route("/api/customer/<cust_id>")
@login_required
def api_customer_inventory(cust_id):
    """API endpoint for getting all inventory for a specific customer"""
    items = Inventory.query.filter_by(CustID=cust_id).all()

    return jsonify(
        [
            {
                "id": item.InventoryKey,
                "description": item.Description or "",
                "material": item.Material or "",
                "color": item.Color or "",
                "condition": item.Condition or "",
                "qty": item.Qty or "0",
                "price": item.Price or "",
                "size_wgt": item.SizeWgt or "",
            }
            for item in items
        ]
    )


@inventory_bp.route("/api/bulk_update", methods=["POST"])
@login_required
def api_bulk_update_inventory():
    """API endpoint for bulk updating inventory quantities"""
    updates = request.get_json()

    if not updates:
        return jsonify({"error": "No updates provided"}), 400

    try:
        for update in updates:
            inventory_key = update.get("inventory_key")
            new_qty = update.get("qty")

            if not inventory_key:
                continue

            item = Inventory.query.get(inventory_key)
            if item:
                item.Qty = str(new_qty or "0")

        db.session.commit()
        return jsonify({"message": "Inventory updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@inventory_bp.route("/add_ajax", methods=["POST"])
@login_required
def add_inventory_ajax():
    data = request.form
    customer_id = data.get("CustID")
    inventory_key = f"INV_{uuid.uuid4().hex[:8].upper()}"

    try:
        item = Inventory(
            InventoryKey=inventory_key,
            Description=data.get("Description"),
            Material=data.get("Material"),
            Condition=data.get("Condition"),
            Color=data.get("Color"),
            SizeWgt=data.get("SizeWgt"),
            Price=data.get("Price"),
            CustID=customer_id,
            Qty=data.get("Qty", "0"),
        )
        db.session.add(item)
        db.session.commit()

        # Return the new item as JSON
        return jsonify({"success": True, "item": item.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/edit_ajax/<inventory_key>", methods=["POST"])
@login_required
def edit_inventory_ajax(inventory_key):
    item = Inventory.query.get_or_404(inventory_key)
    data = request.form

    try:
        item.Description = data.get("Description")
        item.Material = data.get("Material")
        item.Condition = data.get("Condition")
        item.Color = data.get("Color")
        item.SizeWgt = data.get("SizeWgt")
        item.Price = data.get("Price")
        item.Qty = data.get("Qty")

        db.session.commit()
        return jsonify({"success": True, "item": item.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/delete_ajax/<inventory_key>", methods=["POST"])
@login_required
def delete_inventory_ajax(inventory_key):
    """Delete an inventory item via AJAX"""
    item = Inventory.query.get_or_404(inventory_key)

    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"success": True, "message": "Item deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
