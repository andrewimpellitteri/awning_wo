"""
Shared PDF generation helpers for work orders and repair orders.
This module contains common data preparation logic used by both PDF route handlers.
"""


def prepare_order_data_for_pdf(order, order_type="work_order"):
    """
    Prepare order data dictionary for PDF generation.

    Args:
        order: WorkOrder or RepairWorkOrder model instance
        order_type: "work_order" or "repair_order"

    Returns:
        dict: Prepared order data with customer and source information
    """
    # Base dict from order
    order_dict = order.to_dict()

    # Add items if it's a repair order (work orders have items via relationship)
    if order_type == "repair_order":
        order_dict["items"] = [
            {
                "Qty": item.Qty if item.Qty is not None else "0",
                "Description": item.Description,
                "Material": item.Material,
                "Condition": item.Condition,
                "Color": item.Color,
                "SizeWgt": item.SizeWgt,
                "Price": item.Price,
            }
            for item in order.items
        ]

    # Enrich with customer info if available
    if order.customer:
        order_dict["customer"] = order.customer.to_dict()
        order_dict["customer"]["PrimaryPhone"] = order.customer.get_primary_phone()
        order_dict["customer"]["FullAddress"] = order.customer.get_full_address()
        order_dict["customer"]["MailingAddress"] = order.customer.get_mailing_address()
        # Use clean email to remove #mailto: suffix
        order_dict["customer"]["EmailAddress"] = order.customer.clean_email()

    # Handle source information
    order_dict["source"] = _prepare_source_info(order, order_type)

    return order_dict


def _prepare_source_info(order, order_type):
    """
    Prepare source information for the order.

    Args:
        order: WorkOrder or RepairWorkOrder model instance
        order_type: "work_order" or "repair_order"

    Returns:
        dict: Source information with Name, FullAddress, Phone, Email
    """
    # Try customer.Source first (common to both order types)
    if order.customer and order.customer.Source:
        return {
            "Name": order.customer.Source,
            "FullAddress": " ".join(
                filter(
                    None,
                    [
                        order.customer.SourceAddress,
                        order.customer.SourceCity,
                        order.customer.SourceState,
                        order.customer.SourceZip,
                    ],
                )
            ).strip(),
        }

    # Work order specific: try ship_to_source relationship
    if (
        order_type == "work_order"
        and hasattr(order, "ship_to_source")
        and order.ship_to_source
    ):
        return {
            "Name": order.ship_to_source.SSource or "",
            "FullAddress": order.ship_to_source.get_full_address(),
            "Phone": order.ship_to_source.clean_phone(),
            "Email": order.ship_to_source.clean_email(),
        }

    # Repair order specific: try SOURCE field
    if order_type == "repair_order" and hasattr(order, "SOURCE") and order.SOURCE:
        # Check if SOURCE is a string or a relationship
        if isinstance(order.SOURCE, str):
            return {
                "Name": order.SOURCE,
                "FullAddress": "",
                "Phone": "",
                "Email": "",
            }
        else:
            # It's a relationship object
            return {
                "Name": order.SOURCE.SSource or "",
                "FullAddress": order.SOURCE.get_full_address(),
                "Phone": order.SOURCE.clean_phone(),
                "Email": order.SOURCE.clean_email(),
            }

    # Fallback to ShipTo for work orders or ROName for repair orders
    fallback_name = ""
    if order_type == "work_order" and hasattr(order, "ShipTo"):
        fallback_name = order.ShipTo or ""
    elif order_type == "repair_order" and hasattr(order, "ROName"):
        fallback_name = order.ROName or ""
    elif order_type == "repair_order" and order.customer:
        fallback_name = order.customer.Source or ""

    return {
        "Name": fallback_name,
        "FullAddress": "",
        "Phone": "",
        "Email": "",
    }
