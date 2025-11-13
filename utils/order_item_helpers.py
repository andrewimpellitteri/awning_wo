"""
Order item processing utilities for work orders and repair orders.

Provides reusable functions for processing selected inventory items
and new items from forms, with catalog management.

Reduces code duplication in create/edit route handlers.
"""

import uuid
from flask import flash
from models.inventory import Inventory
from models.work_order import WorkOrderItem
from models.repair_order import RepairWorkOrderItem


def safe_int_conversion(value):
    """
    Safely convert a value to integer, handling various input types.

    Args:
        value: Value to convert (string, int, float, None, etc.)

    Returns:
        int: Converted value, or 1 as default

    Example:
        qty = safe_int_conversion(form.get("qty"))
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


def safe_price_conversion(value):
    """
    Safely convert a value to float/Decimal for price fields, handling various input types.

    Args:
        value: Value to convert (string, int, float, None, etc.)

    Returns:
        float or None: Converted value, or None if empty/invalid

    Example:
        price = safe_price_conversion(form.get("price"))
    """
    if value is None or value == "":
        return None  # Return None for empty values

    try:
        # Handle string inputs
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

        # Convert to float
        float_val = float(value)

        # Ensure non-negative value
        return max(0.0, float_val)

    except (ValueError, TypeError):
        print(f"Warning: Could not convert '{value}' to price, defaulting to None")
        return None


def process_selected_inventory_items(form, order_no, cust_id, item_class):
    """
    Process items selected from customer inventory.

    Args:
        form: Flask request.form
        order_no: Work order or repair order number
        cust_id: Customer ID
        item_class: WorkOrderItem or RepairWorkOrderItem class

    Returns:
        List of item instances (not yet added to session)

    Example:
        items = process_selected_inventory_items(
            request.form, next_wo_no, cust_id, WorkOrderItem
        )
        for item in items:
            db.session.add(item)
    """
    items = []
    selected_ids = form.getlist("selected_items[]")

    # Build quantity map
    item_quantities = {
        key.replace("item_qty_", ""): safe_int_conversion(value)
        for key, value in form.items()
        if key.startswith("item_qty_") and value
    }

    for inv_key in selected_ids:
        inventory_item = Inventory.query.get(inv_key)
        if not inventory_item:
            continue

        requested_qty = item_quantities.get(inv_key, 1)

        # Determine the correct field name based on item class
        if item_class == WorkOrderItem:
            order_no_field = "WorkOrderNo"
        elif item_class == RepairWorkOrderItem:
            order_no_field = "RepairOrderNo"
        else:
            raise ValueError(f"Unknown item class: {item_class}")

        item = item_class(
            **{order_no_field: order_no},
            CustID=cust_id,
            Description=inventory_item.Description,
            Material=inventory_item.Material,
            Qty=requested_qty,
            Condition=inventory_item.Condition,
            Color=inventory_item.Color,
            SizeWgt=inventory_item.SizeWgt,
            Price=safe_price_conversion(inventory_item.Price),
            InventoryKey=inv_key,  # Track which inventory item this came from
        )
        items.append(item)

    return items


def process_new_items(form, order_no, cust_id, item_class, update_catalog=True):
    """
    Process manually added new items.

    Args:
        form: Flask request.form
        order_no: Work order or repair order number
        cust_id: Customer ID
        item_class: WorkOrderItem or RepairWorkOrderItem class
        update_catalog: If True, add/update items in inventory catalog

    Returns:
        Tuple of (items, catalog_updates):
            items: List of item instances (not yet added to session)
            catalog_updates: List of inventory items to add/update

    Example:
        items, catalog_updates = process_new_items(
            request.form, next_wo_no, cust_id, WorkOrderItem, update_catalog=True
        )
        for item in items:
            db.session.add(item)
        for inv in catalog_updates:
            db.session.add(inv)
    """
    items = []
    catalog_updates = []

    # Extract all new item arrays from form
    descriptions = form.getlist("new_item_description[]")
    materials = form.getlist("new_item_material[]")
    quantities = form.getlist("new_item_qty[]")
    conditions = form.getlist("new_item_condition[]")
    colors = form.getlist("new_item_color[]")
    sizes = form.getlist("new_item_size[]")
    prices = form.getlist("new_item_price[]")

    # Determine the correct field name based on item class
    if item_class == WorkOrderItem:
        order_no_field = "WorkOrderNo"
    elif item_class == RepairWorkOrderItem:
        order_no_field = "RepairOrderNo"
    else:
        raise ValueError(f"Unknown item class: {item_class}")

    for i, description in enumerate(descriptions):
        if not description or not description.strip():
            continue

        # Get values with safe indexing
        material = materials[i] if i < len(materials) else ""
        qty = safe_int_conversion(quantities[i] if i < len(quantities) else "1")
        condition = conditions[i] if i < len(conditions) else ""
        color = colors[i] if i < len(colors) else ""
        size = sizes[i] if i < len(sizes) else ""
        price_raw = prices[i] if i < len(prices) else ""
        price = safe_price_conversion(price_raw)

        # Create order item
        item = item_class(
            **{order_no_field: order_no},
            CustID=cust_id,
            Description=description.strip(),
            Material=material,
            Qty=qty,
            Condition=condition,
            Color=color,
            SizeWgt=size,
            Price=price,
        )

        # Issue #177: Try to match with existing inventory item to populate InventoryKey
        # This ensures items can be properly filtered in the edit page
        existing_inventory = Inventory.query.filter_by(
            CustID=cust_id,
            Description=description.strip(),
            Material=material,
            Condition=condition,
            Color=color,
            SizeWgt=size,
        ).first()

        if existing_inventory:
            item.InventoryKey = existing_inventory.InventoryKey

        items.append(item)

        # Update catalog if requested
        if update_catalog:
            catalog_item = add_or_update_catalog(
                cust_id,
                description.strip(),
                material,
                condition,
                color,
                size,
                price_raw,  # Pass raw price string, function will convert it
                qty,
            )
            if catalog_item:
                catalog_updates.append(catalog_item)

    return items, catalog_updates


def add_or_update_catalog(cust_id, description, material, condition, color, size, price, qty):
    """
    Add a new item to the inventory catalog or update existing quantity.

    Args:
        cust_id: Customer ID
        description: Item description
        material: Material type
        condition: Item condition
        color: Item color
        size: Size/weight
        price: Price
        qty: Quantity to add

    Returns:
        Inventory object (new or updated), or None if no action needed

    Example:
        inv_item = add_or_update_catalog(
            cust_id="123",
            description="Awning",
            material="Canvas",
            condition="Good",
            color="Blue",
            size="10x12",
            price="150.00",
            qty=1
        )
        if inv_item:
            db.session.add(inv_item)
    """
    # Look for existing inventory item with same attributes
    existing_inventory = Inventory.query.filter_by(
        CustID=cust_id,
        Description=description,
        Material=material,
        Condition=condition,
        Color=color,
        SizeWgt=size,
    ).first()

    if existing_inventory:
        # Update quantity
        current_qty = safe_int_conversion(existing_inventory.Qty)
        new_qty = current_qty + qty
        existing_inventory.Qty = new_qty
        flash(
            f"Updated catalog: Customer now has {new_qty} total of '{description}'",
            "info",
        )
        return existing_inventory
    else:
        # Create new catalog item
        from datetime import datetime
        inventory_key = f"INV_{uuid.uuid4().hex[:8].upper()}"
        new_inventory_item = Inventory(
            InventoryKey=inventory_key,
            CustID=cust_id,
            Description=description,
            Material=material,
            Condition=condition,
            Color=color,
            SizeWgt=size,
            Price=safe_price_conversion(price),
            Qty=qty,
            created_at=datetime.utcnow(),
        )
        flash(
            f"New item '{description}' added to catalog with quantity {qty}",
            "success",
        )
        return new_inventory_item
