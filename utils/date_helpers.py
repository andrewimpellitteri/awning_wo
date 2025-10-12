"""
Date helper utilities for form parsing and API responses.

Provides reusable functions for parsing dates from forms and formatting
dates for JSON API responses.

Reduces code duplication and ensures consistent date handling across
all route files.
"""

from datetime import datetime, date


def parse_form_date(form, field_name, required=False, default=None):
    """
    Parse date from form with consistent error handling.

    Args:
        form: Flask request.form or dict-like object
        field_name: Name of the form field
        required: If True, raises ValueError if field is missing
        default: Default value if field is empty (only used if not required)

    Returns:
        date object or None (or default value)

    Raises:
        ValueError: If required and missing, or if date format is invalid

    Example:
        DateIn = parse_form_date(request.form, "DateIn", default=date.today())
        DateRequired = parse_form_date(request.form, "DateRequired")
        DateCompleted = parse_form_date(request.form, "DateCompleted", required=False)
    """
    value = form.get(field_name)

    if not value or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError(f"{field_name} is required")
        return default

    # Handle string values
    if isinstance(value, str):
        value = value.strip()
        if not value:
            if required:
                raise ValueError(f"{field_name} is required")
            return default

        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date format for {field_name}: {value}. Expected YYYY-MM-DD") from e

    # Handle date objects (already parsed)
    if isinstance(value, date):
        return value

    # Handle datetime objects
    if isinstance(value, datetime):
        return value.date()

    # Unknown type
    raise ValueError(f"Invalid type for {field_name}: {type(value)}")


def format_date_for_api(date_value):
    """
    Convert date/datetime to YYYY-MM-DD string for JSON API responses.

    Args:
        date_value: date, datetime, or string

    Returns:
        String in YYYY-MM-DD format, or None if input is None/empty

    Example:
        {
            "DateIn": format_date_for_api(work_order.DateIn),
            "DateRequired": format_date_for_api(work_order.DateRequired),
        }
    """
    if not date_value:
        return None

    # Already a string - return as-is
    if isinstance(date_value, str):
        # Could add validation here if needed
        return date_value

    # datetime or date object
    if isinstance(date_value, (datetime, date)):
        return date_value.strftime("%Y-%m-%d")

    # Unknown type - try to convert to string
    return str(date_value)


def format_date_from_str(value):
    """
    Formats a datetime object or date string to YYYY-MM-DD format.
    Handles 'MM/DD/YY HH:MM:SS' strings from the database.

    This is a legacy function kept for backward compatibility.
    New code should use format_date_for_api instead.

    Args:
        value: date, datetime, or string

    Returns:
        String in YYYY-MM-DD format, or None if input is None/empty
    """
    if not value:
        return None

    # Case 1: Value is already a datetime or date object.
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")

    # Case 2: Value is a string. We need to parse it first.
    if isinstance(value, str):
        try:
            # Try to parse the specific 'MM/DD/YY HH:MM:SS' format.
            dt_object = datetime.strptime(value, "%m/%d/%y %H:%M:%S")
            return dt_object.strftime("%Y-%m-%d")
        except ValueError:
            # If that fails, return the value as-is (might already be formatted)
            return value

    return None
