"""
Form helper utilities for extracting and validating form data.

Provides reusable functions for extracting work order and repair order
fields from Flask forms, with consistent validation and error handling.

Reduces code duplication in create/edit route handlers.
"""

from datetime import date
from utils.date_helpers import parse_form_date


def extract_work_order_fields(form):
    """
    Extract all work order fields from form into dict.

    Args:
        form: Flask request.form or dict-like object

    Returns:
        Dict ready to pass to WorkOrder(**data)

    Raises:
        ValueError: For validation errors

    Example:
        wo_data = extract_work_order_fields(request.form)
        work_order = WorkOrder(WorkOrderNo=next_wo_no, **wo_data)
    """
    # Basic validation
    if not form.get("CustID"):
        raise ValueError("Customer is required")
    if not form.get("WOName"):
        raise ValueError("Work Order Name is required")

    return {
        "CustID": form.get("CustID"),
        "WOName": form.get("WOName"),
        "StorageTime": form.get("StorageTime"),
        "RackNo": form.get("RackNo"),
        "final_location": form.get("final_location"),
        "SpecialInstructions": form.get("SpecialInstructions"),
        "RepairsNeeded": "RepairsNeeded" in form,
        "SeeRepair": form.get("SeeRepair"),
        "Quote": form.get("Quote"),
        "RushOrder": "RushOrder" in form,
        "FirmRush": "FirmRush" in form,
        "DateIn": parse_form_date(form, "DateIn"),
        "DateRequired": parse_form_date(form, "DateRequired"),
        "Clean": parse_form_date(form, "Clean"),
        "Treat": parse_form_date(form, "Treat"),
        "DateCompleted": parse_form_date(form, "DateCompleted"),
        "ReturnStatus": form.get("ReturnStatus"),
        "ReturnTo": form.get("ReturnTo"),
        "ShipTo": form.get("ShipTo"),
    }


def extract_repair_order_fields(form):
    """
    Extract all repair order fields from form into dict.

    Args:
        form: Flask request.form or dict-like object

    Returns:
        Dict ready to pass to RepairWorkOrder(**data)

    Raises:
        ValueError: For validation errors

    Example:
        ro_data = extract_repair_order_fields(request.form)
        repair_order = RepairWorkOrder(RepairOrderNo=next_ro_no, **ro_data)
    """
    # Basic validation
    if not form.get("CustID"):
        raise ValueError("Customer is required")
    if not form.get("ROName"):
        raise ValueError("Repair Order Name is required")

    return {
        "CustID": form.get("CustID"),
        "ROName": form.get("ROName"),
        "ITEM_TYPE": form.get("ITEM_TYPE"),
        "TYPE_OF_REPAIR": form.get("TYPE_OF_REPAIR"),
        "LOCATION": form.get("LOCATION"),
        "SpecialInstructions": form.get("SpecialInstructions"),
        "SEECLEAN": form.get("SEECLEAN"),
        "RushOrder": "RushOrder" in form,
        "FirmRush": "FirmRush" in form,
        "DateIn": parse_form_date(form, "DateIn"),
        "DateRequired": parse_form_date(form, "DateRequired"),
        "DateCompleted": parse_form_date(form, "DateCompleted"),
        "ReturnStatus": form.get("ReturnStatus"),
        "RETURNTO": form.get("RETURNTO"),
        "ShipTo": form.get("ShipTo"),
    }
