# Route Refactoring Plan

## Priority 1: Query Helpers (Biggest Impact, Low Risk)

**Impact:** Reduces ~300 lines across all route files
**Complexity:** Low - Pure utility functions
**Files affected:** `work_orders.py`, `repair_order.py`, `customers.py`, `queue.py`

### Create `utils/query_helpers.py`

```python
def apply_search_filter(query, model, search_term, searchable_fields):
    """
    Apply OR-based search across multiple model fields.

    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class (WorkOrder, RepairWorkOrder, etc.)
        search_term: Search string from request.args
        searchable_fields: List of field names to search

    Returns:
        Modified query with search filters applied

    Example:
        query = apply_search_filter(
            query,
            WorkOrder,
            "ABC123",
            ["WorkOrderNo", "CustID", "WOName", "ShipTo"]
        )
    """

def apply_column_filters(query, model, request_args, filter_config):
    """
    Apply individual column filters from Tabulator.

    Args:
        filter_config: Dict mapping filter names to columns
            {
                "filter_CustID": {"column": Customer.CustID, "type": "exact"},
                "filter_Name": {"column": Customer.Name, "type": "like"}
            }
    """

def apply_tabulator_sorting(query, model, request_args, type_config=None):
    """
    Parse and apply Tabulator multi-column sorting.

    Args:
        type_config: Dict of field types for casting
            {
                "WorkOrderNo": "integer",
                "DateIn": "date",
                "CustID": "integer"
            }

    Handles: sort[0][field], sort[0][dir], etc.
    Auto-casts numeric/date fields with nulls_last()
    """

def optimize_relationship_loading(query, model, request_args, relationship_map):
    """
    Conditionally eager-load relationships based on filters/sorts.

    Args:
        relationship_map: Dict of relationships to check for
            {
                "Source": {
                    "join_path": [WorkOrder.customer, Customer.source_info],
                    "load_path": [WorkOrder.customer, Customer.source_info]
                }
            }

    Checks if Source is in filter_* or sort[*][field] params.
    Only joins/loads if needed (avoids N+1 and unnecessary joins).
    """
```

### Refactor Examples

**Before (work_orders.py lines 909-1043):**
```python
# 135 lines of complex filtering and sorting
```

**After:**
```python
@work_orders_bp.route("/api/work_orders")
@login_required
def api_work_orders():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 25, type=int)
    status = request.args.get("status", "").lower()

    query = WorkOrder.query

    # Optimize relationship loading
    query = optimize_relationship_loading(
        query, WorkOrder, request.args,
        {"Source": {
            "join_path": [WorkOrder.customer, Customer.source_info],
            "load_path": [WorkOrder.customer, Customer.source_info]
        }}
    )

    # Apply filters
    if status == "pending":
        query = query.filter(WorkOrder.DateCompleted.is_(None))
    elif status == "completed":
        query = query.filter(WorkOrder.DateCompleted.isnot(None))
    elif status == "rush":
        query = query.filter(
            or_(WorkOrder.RushOrder == True, WorkOrder.FirmRush == True),
            WorkOrder.DateCompleted.is_(None)
        )

    # Column-specific filters
    query = apply_column_filters(query, WorkOrder, request.args, {
        "filter_WorkOrderNo": {"column": WorkOrder.WorkOrderNo, "type": "range_or_exact"},
        "filter_CustID": {"column": WorkOrder.CustID, "type": "exact"},
        "filter_WOName": {"column": WorkOrder.WOName, "type": "like"},
        "filter_DateIn": {"column": WorkOrder.DateIn, "type": "like"},
        "filter_DateRequired": {"column": WorkOrder.DateRequired, "type": "like"},
        "filter_Source": {"column": Source.SSource, "type": "like"}
    })

    # Sorting
    query = apply_tabulator_sorting(query, WorkOrder, request.args, {
        "WorkOrderNo": "integer",
        "CustID": "integer",
        "DateIn": "date",
        "DateRequired": "date",
        "Source": Source.SSource
    })

    total = query.count()
    items = query.paginate(page=page, per_page=size, error_out=False)

    return build_tabulator_response(
        items.items,
        total,
        page,
        items.pages,
        row_builder=build_work_order_row
    )
```

**Lines saved:** ~100 lines per API route × 4 routes = **400 lines**

---

## Priority 2: Date Helpers (High Impact, Zero Risk)

**Impact:** Reduces ~150 lines, eliminates bugs
**Complexity:** Trivial
**Files affected:** All route files

### Create `utils/date_helpers.py`

```python
def parse_form_date(form, field_name, required=False, default=None):
    """
    Parse date from form with consistent error handling.

    Returns: date object or None
    Raises: ValueError if required and missing
    """
    value = form.get(field_name)
    if not value:
        if required:
            raise ValueError(f"{field_name} is required")
        return default

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format for {field_name}")

def format_date_for_api(date_value):
    """Convert date/datetime to YYYY-MM-DD string for JSON."""
    if not date_value:
        return None
    if isinstance(date_value, str):
        return date_value
    return date_value.strftime("%Y-%m-%d")
```

### Refactor Examples

**Before (work_orders.py lines 397-410):**
```python
DateIn=datetime.strptime(request.form.get("DateIn"), "%Y-%m-%d").date()
if request.form.get("DateIn")
else date.today(),
DateRequired=datetime.strptime(
    request.form.get("DateRequired"), "%Y-%m-%d"
).date()
if request.form.get("DateRequired")
else None,
Clean=datetime.strptime(request.form.get("Clean"), "%Y-%m-%d").date()
if request.form.get("Clean")
else None,
# ... repeated 5 more times
```

**After:**
```python
from utils.date_helpers import parse_form_date

DateIn=parse_form_date(request.form, "DateIn", default=date.today()),
DateRequired=parse_form_date(request.form, "DateRequired"),
Clean=parse_form_date(request.form, "Clean"),
Treat=parse_form_date(request.form, "Treat"),
```

**Lines saved:** ~10 lines per route × 15 routes = **150 lines**

---

## Priority 3: API Response Builders (Medium Impact, Low Risk)

**Impact:** Reduces ~100 lines, standardizes responses
**Complexity:** Low
**Files affected:** All API routes

### Create `utils/api_helpers.py`

```python
def build_tabulator_response(items, total, page, pages, row_builder=None):
    """
    Standard Tabulator pagination response.

    Args:
        row_builder: Function to convert model instance to dict
    """
    if row_builder:
        data = [row_builder(item) for item in items]
    else:
        data = [item.__dict__ for item in items]

    return jsonify({
        "data": data,
        "total": total,
        "page": page,
        "last_page": pages
    })

def build_work_order_row(work_order, include_source=True):
    """Convert WorkOrder model to API dict."""
    row = {
        "WorkOrderNo": work_order.WorkOrderNo,
        "CustID": work_order.CustID,
        "WOName": work_order.WOName,
        "DateIn": format_date_for_api(work_order.DateIn),
        "DateRequired": format_date_for_api(work_order.DateRequired),
        "detail_url": url_for("work_orders.view_work_order", work_order_no=work_order.WorkOrderNo),
        "edit_url": url_for("work_orders.edit_work_order", work_order_no=work_order.WorkOrderNo),
        "delete_url": url_for("work_orders.delete_work_order", work_order_no=work_order.WorkOrderNo),
    }

    if include_source and work_order.customer and work_order.customer.source_info:
        row["Source"] = work_order.customer.source_info.SSource

    if work_order.customer:
        row["customer_url"] = url_for("customers.customer_detail", customer_id=work_order.CustID)

    return row
```

---

## Priority 4: Form Data Extraction (High Impact, Medium Risk)

**Impact:** Reduces ~200 lines, makes validation easier
**Complexity:** Medium - requires careful testing
**Files affected:** `work_orders.py`, `repair_order.py`

### Create `utils/form_helpers.py`

```python
def extract_work_order_fields(form):
    """
    Extract all work order fields from form into dict.

    Returns: Dict ready to pass to WorkOrder(**data)
    Raises: ValueError for validation errors
    """
    from utils.date_helpers import parse_form_date

    if not form.get("CustID"):
        raise ValueError("Customer is required")
    if not form.get("WOName"):
        raise ValueError("Name is required")

    return {
        "CustID": form.get("CustID"),
        "WOName": form.get("WOName"),
        "StorageTime": form.get("StorageTime"),
        "RackNo": form.get("RackNo"),
        "SpecialInstructions": form.get("SpecialInstructions"),
        "RepairsNeeded": "RepairsNeeded" in form,
        "SeeRepair": form.get("SeeRepair"),
        "Quote": form.get("Quote"),
        "RushOrder": "RushOrder" in form,
        "FirmRush": "FirmRush" in form,
        "DateIn": parse_form_date(form, "DateIn", default=date.today()),
        "DateRequired": parse_form_date(form, "DateRequired"),
        "Clean": parse_form_date(form, "Clean"),
        "Treat": parse_form_date(form, "Treat"),
        "ReturnStatus": form.get("ReturnStatus"),
        "ShipTo": form.get("ShipTo"),
    }
```

**Before (work_orders.py lines 383-414): 31 lines**
**After: 2 lines**
```python
wo_data = extract_work_order_fields(request.form)
work_order = WorkOrder(WorkOrderNo=next_wo_no, **wo_data)
```

---

## Priority 5: Order Item Processing (Highest Complexity, High Impact)

**Impact:** Reduces ~400 lines, biggest code smell
**Complexity:** High - complex business logic
**Files affected:** `work_orders.py`, `repair_order.py`

### Create `utils/order_item_helpers.py`

```python
def process_selected_inventory_items(form, order_no, cust_id, item_class):
    """
    Process items selected from customer inventory.

    Args:
        item_class: WorkOrderItem or RepairWorkOrderItem

    Returns: List of item instances (not yet added to session)
    """
    items = []
    selected_ids = form.getlist("selected_items[]")

    for inv_key in selected_ids:
        inventory_item = Inventory.query.get(inv_key)
        if not inventory_item:
            continue

        qty_key = f"item_qty_{inv_key}"
        qty = safe_int_conversion(form.get(qty_key, 1))

        item = item_class(
            WorkOrderNo=order_no,
            CustID=cust_id,
            Description=inventory_item.Description,
            Material=inventory_item.Material,
            Qty=str(qty),
            Condition=inventory_item.Condition,
            Color=inventory_item.Color,
            SizeWgt=inventory_item.SizeWgt,
            Price=inventory_item.Price,
        )
        items.append(item)

    return items

def process_new_items(form, order_no, cust_id, item_class, update_catalog=True):
    """
    Process manually added new items.

    Returns: (items, catalog_updates)
        items: List of item instances
        catalog_updates: List of inventory updates if update_catalog=True
    """
    items = []
    catalog_updates = []

    descriptions = form.getlist("new_item_description[]")
    materials = form.getlist("new_item_material[]")
    quantities = form.getlist("new_item_qty[]")
    # ... etc

    for i, description in enumerate(descriptions):
        if not description:
            continue

        # Create order item
        item = item_class(...)
        items.append(item)

        # Catalog update logic
        if update_catalog:
            catalog_update = add_or_update_catalog(cust_id, item_data)
            if catalog_update:
                catalog_updates.append(catalog_update)

    return items, catalog_updates
```

**Before (work_orders.py create_work_order): 225 lines**
**After: ~60 lines**

---

## Implementation Order

### Week 1: Foundation (Low Risk)
1. ✅ Create `utils/date_helpers.py`
2. ✅ Refactor all date parsing (test thoroughly)
3. ✅ Create `utils/query_helpers.py`
4. ✅ Refactor one API route as proof of concept

### Week 2: API Layer (Medium Risk)
5. ✅ Create `utils/api_helpers.py`
6. ✅ Refactor all API routes
7. ✅ Test Tabulator functionality

### Week 3: Forms (Higher Risk)
8. ✅ Create `utils/form_helpers.py`
9. ✅ Refactor work_orders create/edit
10. ✅ Refactor repair_orders create/edit
11. ✅ Extensive testing

### Week 4: Items (Highest Risk)
12. ✅ Create `utils/order_item_helpers.py`
13. ✅ Refactor item processing
14. ✅ Test inventory catalog updates
15. ✅ Regression testing

---

## Testing Strategy

### Unit Tests (New)
- Test each helper function in isolation
- Mock database calls
- Test edge cases (None, empty, invalid dates)

### Integration Tests (Existing)
- Run full test suite after each refactor
- Pay special attention to:
  - Date parsing edge cases
  - Inventory quantity tracking
  - API response formats

### Manual Testing Checklist
- [ ] Create work order with selected items
- [ ] Create work order with new items
- [ ] Edit work order and remove items
- [ ] API filtering works (all columns)
- [ ] API sorting works (all columns)
- [ ] Date fields handle None correctly
- [ ] Rush orders filter correctly
- [ ] Pagination works on all views

---

## Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total route LOC | 3,685 | 2,150 | -42% |
| Longest function | 225 lines | 60 lines | -73% |
| Code duplication | High | Low | ✅ |
| Test coverage | 60% | 85% | +25% |
| Helper functions | 5 | 25 | +400% |

---

## Risk Mitigation

### High-Risk Areas
1. **Inventory catalog updates** - Complex business logic, easy to break
   - Solution: Unit test helpers thoroughly
   - Solution: Compare before/after catalog state in tests

2. **Date parsing** - Used everywhere, silent failures possible
   - Solution: Explicit error handling in helpers
   - Solution: Return None vs raise exception (document clearly)

3. **Query optimization** - Could break N+1 or add unnecessary joins
   - Solution: Log SQL queries in dev
   - Solution: Benchmark before/after

### Rollback Plan
- Keep old code commented out for 1 sprint
- Feature flag for new helpers (if needed)
- Git tags for each refactor phase
