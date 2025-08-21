def debug_wo_items():
    from models.work_order import WorkOrder, WorkOrderItem

    # Get the work order
    wo = WorkOrder.query.filter_by(WorkOrderNo="45555").first()

    print(f"Work Order: {wo.WorkOrderNo}")
    print(f"Current items property: {len(wo.items)}")

    # Check direct SQL query
    direct_items = WorkOrderItem.query.filter_by(WorkOrderNo="45555").all()
    print(f"Direct query items: {len(direct_items)}")

    # Show what the items property returns
    print("Items from wo.items:")
    for i, item in enumerate(wo.items):
        print(f"  {i + 1}. {item.Description} - {item.Material} - Qty: {item.Qty}")

    # Show what direct query returns
    print("Items from direct query:")
    for i, item in enumerate(direct_items):
        print(f"  {i + 1}. {item.Description} - {item.Material} - Qty: {item.Qty}")
