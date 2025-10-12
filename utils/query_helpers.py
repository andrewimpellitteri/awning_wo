"""
Query helper utilities for API routes.

Provides reusable functions for filtering, sorting, and optimizing
SQLAlchemy queries in Tabulator-based API endpoints.

Reduces code duplication across work_orders, repair_orders, customers,
and queue route files.
"""

from sqlalchemy import cast, Integer, or_
from sqlalchemy.orm import joinedload


def check_relationship_needed(request_args, field_name, max_sort_index=10):
    """
    Check if a relationship field is needed for filtering or sorting.

    Args:
        request_args: Flask request.args
        field_name: Name of the field to check (e.g., "Source")
        max_sort_index: Maximum sort index to check (default 10)

    Returns:
        bool: True if field is used in filters or sorting

    Example:
        if check_relationship_needed(request.args, "Source"):
            query = query.join(WorkOrder.customer).join(Customer.source_info)
    """
    # Check for filter
    if request_args.get(f"filter_{field_name}"):
        return True

    # Check for sort
    for i in range(max_sort_index):
        if request_args.get(f"sort[{i}][field]") == field_name:
            return True

    return False


def optimize_relationship_loading(query, request_args, relationship_config):
    """
    Conditionally eager-load relationships based on filters/sorts.

    Only joins and loads relationships when they're actually needed,
    avoiding unnecessary joins while preventing N+1 queries.

    Args:
        query: SQLAlchemy query object
        request_args: Flask request.args
        relationship_config: Dict mapping field names to relationship paths
            {
                "Source": {
                    "join_path": [WorkOrder.customer, Customer.source_info],
                    "load_path": [WorkOrder.customer, Customer.source_info],
                    "default_load": [WorkOrder.customer]  # Optional: load if not using Source
                }
            }

    Returns:
        Modified query with optimized joins and eager loading

    Example:
        query = optimize_relationship_loading(
            query, request.args,
            {
                "Source": {
                    "join_path": [WorkOrder.customer, Customer.source_info],
                    "load_path": [WorkOrder.customer, Customer.source_info],
                    "default_load": [WorkOrder.customer]
                }
            }
        )
    """
    for field_name, config in relationship_config.items():
        if check_relationship_needed(request_args, field_name):
            # Field is needed - join and load the full path
            join_path = config.get("join_path", [])
            load_path = config.get("load_path", [])

            # Apply joins
            for relationship in join_path:
                query = query.join(relationship)

            # Apply eager loading
            if load_path:
                load_option = joinedload(load_path[0])
                for rel in load_path[1:]:
                    load_option = load_option.joinedload(rel)
                query = query.options(load_option)

            return query

    # No special relationships needed - use default loading if provided
    for field_name, config in relationship_config.items():
        default_load = config.get("default_load")
        if default_load:
            load_option = joinedload(default_load[0])
            for rel in default_load[1:]:
                load_option = load_option.joinedload(rel)
            query = query.options(load_option)
            break  # Only apply one default

    return query


def apply_column_filters(query, model, request_args, filter_config):
    """
    Apply individual column filters from Tabulator.

    Supports different filter types: exact, like, range_or_exact, integer_exact.

    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class (WorkOrder, Customer, etc.)
        request_args: Flask request.args
        filter_config: Dict mapping filter names to column and type
            {
                "filter_WorkOrderNo": {"column": WorkOrder.WorkOrderNo, "type": "range_or_exact"},
                "filter_CustID": {"column": WorkOrder.CustID, "type": "integer_exact"},
                "filter_WOName": {"column": WorkOrder.WOName, "type": "like"},
                "filter_Source": {"column": Source.SSource, "type": "like"}
            }

    Returns:
        Modified query with filters applied

    Example:
        query = apply_column_filters(query, WorkOrder, request.args, {
            "filter_WorkOrderNo": {"column": WorkOrder.WorkOrderNo, "type": "range_or_exact"},
            "filter_CustID": {"column": WorkOrder.CustID, "type": "integer_exact"},
            "filter_WOName": {"column": WorkOrder.WOName, "type": "like"}
        })
    """
    for filter_name, config in filter_config.items():
        filter_val = request_args.get(filter_name)
        if not filter_val:
            continue

        filter_val = filter_val.strip()
        if not filter_val:
            continue

        column = config["column"]
        filter_type = config.get("type", "like")

        if filter_type == "range_or_exact":
            # Handle range (e.g., "100-200") or exact match
            if "-" in filter_val:
                try:
                    start, end = map(int, filter_val.split("-", 1))
                    query = query.filter(
                        cast(column, Integer) >= start,
                        cast(column, Integer) <= end
                    )
                except ValueError:
                    pass  # Invalid format, skip filter
            else:
                try:
                    val = int(filter_val)
                    query = query.filter(cast(column, Integer) == val)
                except ValueError:
                    pass  # Invalid format, skip filter

        elif filter_type == "integer_exact":
            # Exact integer match only
            try:
                val = int(filter_val)
                query = query.filter(column == val)
            except ValueError:
                pass  # Invalid format, skip filter

        elif filter_type == "exact":
            # Exact string match
            query = query.filter(column == filter_val)

        elif filter_type == "like":
            # Case-insensitive partial match
            query = query.filter(column.ilike(f"%{filter_val}%"))

    return query


def apply_tabulator_sorting(query, model, request_args, sort_config=None):
    """
    Parse and apply Tabulator multi-column sorting.

    Handles sort[0][field], sort[0][dir], sort[1][field], etc.
    Auto-casts numeric/date fields with proper null handling.

    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class
        request_args: Flask request.args
        sort_config: Dict mapping field names to column objects or type strings
            {
                "WorkOrderNo": "integer",  # Will cast to Integer
                "CustID": "integer",
                "DateIn": "date",  # Will use nulls_last()
                "DateRequired": "date",
                "Source": Source.SSource  # Custom column object
            }

    Returns:
        Modified query with sorting applied

    Example:
        query = apply_tabulator_sorting(query, WorkOrder, request.args, {
            "WorkOrderNo": "integer",
            "CustID": "integer",
            "DateIn": "date",
            "DateRequired": "date",
            "Source": Source.SSource
        })
    """
    sort_config = sort_config or {}
    order_by_clauses = []

    i = 0
    while True:
        field = request_args.get(f"sort[{i}][field]")
        if not field:
            break

        direction = request_args.get(f"sort[{i}][dir]", "asc")

        # Check if this field has a custom column object
        if field in sort_config and not isinstance(sort_config[field], str):
            column = sort_config[field]
            if direction == "desc":
                order_by_clauses.append(column.desc())
            else:
                order_by_clauses.append(column.asc())
        else:
            # Try to get the column from the model
            column = getattr(model, field, None)
            if not column:
                i += 1
                continue

            # Determine the sort type
            sort_type = sort_config.get(field, "string")

            if sort_type == "integer":
                # Cast to integer for proper numeric sorting
                cast_column = cast(column, Integer)
                if direction == "desc":
                    order_by_clauses.append(cast_column.desc())
                else:
                    order_by_clauses.append(cast_column.asc())

            elif sort_type == "date":
                # Date fields with nulls_last()
                if direction == "desc":
                    order_by_clauses.append(column.desc().nulls_last())
                else:
                    order_by_clauses.append(column.asc().nulls_last())

            else:
                # String or default sorting
                if direction == "desc":
                    order_by_clauses.append(column.desc())
                else:
                    order_by_clauses.append(column.asc())

        i += 1

    # Apply sorting if any clauses were built
    if order_by_clauses:
        query = query.order_by(*order_by_clauses)

    return query


def apply_search_filter(query, model, search_term, searchable_fields):
    """
    Apply OR-based search across multiple model fields.

    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class
        search_term: Search string from request.args
        searchable_fields: List of field names to search (as strings)

    Returns:
        Modified query with search filters applied

    Example:
        search = request.args.get("search", "")
        if search:
            query = apply_search_filter(
                query, WorkOrder, search,
                ["WorkOrderNo", "CustID", "WOName", "ShipTo"]
            )
    """
    if not search_term:
        return query

    search_term = search_term.strip()
    if not search_term:
        return query

    search_pattern = f"%{search_term}%"

    # Build OR conditions for all searchable fields
    conditions = []
    for field_name in searchable_fields:
        column = getattr(model, field_name, None)
        if column:
            conditions.append(column.ilike(search_pattern))

    if conditions:
        query = query.filter(or_(*conditions))

    return query
