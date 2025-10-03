# Test Fixtures Fix Guide

## Critical Issue: CI Tests Failing

**Status**: 5 tests failing due to string values being passed to date/boolean fields

**Root Cause**: After updating models to use proper Date/Boolean types, test fixtures still create instances with string values, causing SQLAlchemy type errors.

---

## Failing Tests Summary

### Test File Errors

1. **test/test_queue_routes.py** (4 failures)
   - `test_queue_sorting_by_priority`
   - `test_queue_search`
   - `test_queue_reorder_api`
   - `test_queue_summary_api`
   - **Error**: `TypeError: SQLite Date type only accepts Python date objects as input.`

2. **test/test_repair_orders_routes.py** (1 failure)
   - `test_filter_by_status`
   - **Error**: `TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.`

---

## Fix Pattern

### Date Fields
```python
# ❌ WRONG (causes TypeError)
work_order = WorkOrder(
    DateIn="2024-01-10",
    DateRequired="2024-01-15",
    DateCompleted="2024-01-20"
)

# ✅ CORRECT
from datetime import date, datetime

work_order = WorkOrder(
    DateIn=date(2024, 1, 10),
    DateRequired=date(2024, 1, 15),
    DateCompleted=datetime(2024, 1, 20, 14, 30, 0)  # DateTime for completion
)
```

### Boolean Fields
```python
# ❌ WRONG (causes issues)
work_order = WorkOrder(
    RushOrder="1",
    FirmRush="0",
    Quote="1"
)

# ✅ CORRECT
work_order = WorkOrder(
    RushOrder=True,
    FirmRush=False,
    Quote=True
)
```

### Nullable Fields
```python
# ✅ CORRECT - Use None for NULL values
work_order = WorkOrder(
    DateCompleted=None,  # Not yet completed
    DateRequired=None,   # No required date
    Clean=None,          # Not yet cleaned
    Treat=None           # Not yet treated
)
```

---

## Files to Update

### 1. test/conftest.py
**Fixture**: `sample_customers_and_work_orders`

**Current Issue**: Creates WorkOrder with string dates
```python
wo1 = WorkOrder(
    WorkOrderNo="1001",
    WOName="Regular Order",
    DateIn="2024-01-10",  # ❌ String
    CustID=c1.CustID,
)
```

**Fix**:
```python
from datetime import date, datetime

wo1 = WorkOrder(
    WorkOrderNo="1001",
    WOName="Regular Order",
    DateIn=date(2024, 1, 10),  # ✅ Date object
    CustID=c1.CustID,
)
```

### 2. test/test_queue_routes.py
**Fixture**: `sample_customers_and_work_orders`

**Lines to Fix**:
- All `DateIn="2024-XX-XX"` → `DateIn=date(2024, X, X)`
- All `DateRequired="2024-XX-XX"` → `DateRequired=date(2024, X, X)`
- All `RushOrder="1"` → `RushOrder=True`
- All `FirmRush="1"` → `FirmRush=True`

### 3. test/test_repair_orders_routes.py
**Fixture**: `sample_repair_orders`

**Lines to Fix**:
- All `WO_DATE="2024-XX-XX"` → `WO_DATE=date(2024, X, X)`
- All `DATE_TO_SUB="2024-XX-XX"` → `DATE_TO_SUB=date(2024, X, X)`
- All `DateIn="2024-XX-XX"` → `DateIn=date(2024, X, X)`
- All `DateCompleted="2024-XX-XX"` → `DateCompleted=datetime(2024, X, X)`
- All `RushOrder="1"` → `RushOrder=True`
- All boolean string values → proper booleans

### 4. test/test_work_orders_routes.py
**Check all test functions** that create WorkOrder instances directly

---

## Quick Fix Script

Add these imports to the top of each test file:
```python
from datetime import date, datetime
```

Then use search and replace:

### For date fields:
```python
# Pattern to find:
DateIn="(\d{4})-(\d{2})-(\d{2})"

# Replace with:
DateIn=date(\1, \2, \3)
```

### For boolean fields:
```python
# Pattern to find:
RushOrder="1"

# Replace with:
RushOrder=True

# Pattern to find:
FirmRush="0"

# Replace with:
FirmRush=False
```

---

## Verification

After fixing, run:
```bash
# Run failing tests
pytest test/test_queue_routes.py -v
pytest test/test_repair_orders_routes.py::TestRepairOrderRoutes::test_filter_by_status -v

# Run all tests
pytest test/ -v --maxfail=5
```

**Expected Result**: All 227 tests should pass

---

## Common Pitfalls

1. **Mixed Date/DateTime**: `DateCompleted` uses `DateTime`, most others use `Date`
2. **Nullable vs Required**: `DateIn` is required, most others are nullable
3. **Zero vs False**: Don't use `"0"`, use `False` for booleans
4. **Leading Zeros**: `date(2024, 1, 5)` not `date(2024, 01, 05)` (no quotes)

---

## Testing Checklist

After fixes:
- [ ] `test_queue_routes.py` all tests pass
- [ ] `test_repair_orders_routes.py` all tests pass
- [ ] `test_work_orders_routes.py` all tests pass
- [ ] No string date values in any test fixtures
- [ ] No string boolean values ("1", "0") in any test fixtures
- [ ] CI pipeline passes

---

*Created: 2025-10-03*
*Priority: CRITICAL - Blocks all other work*
