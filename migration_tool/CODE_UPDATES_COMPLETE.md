# Code Updates for Data Type Migration - Status

## ✅ COMPLETED: Model Updates

All database models have been updated to use proper data types:

### 1. WorkOrder Model (`models/work_order.py`)
✅ **Date Fields:**
- `DateCompleted` → `db.DateTime`
- `DateRequired` → `db.Date`
- `DateIn` → `db.Date` (with default=func.current_date())
- `Clean` → `db.Date` (date when cleaning completed)
- `Treat` → `db.Date` (date when treatment completed)

✅ **Boolean Fields:**
- `Quote` → `db.Boolean`
- `RushOrder` → `db.Boolean`
- `FirmRush` → `db.Boolean`
- `SeeRepair` → `db.Boolean`

✅ **String Fields (unchanged):**
- `CleanFirstWO` → String (work order reference)
- `StorageTime` → String ("Seasonal"/"Temporary")

✅ **to_dict() method updated** - Properly serializes dates to strings

### 2. WorkOrderItem Model (`models/work_order.py`)
✅ `Qty` → `db.Integer`
✅ `Price` → `db.Numeric(10, 2)`

### 3. RepairWorkOrder Model (`models/repair_order.py`)
✅ **Date Fields:**
- `WO_DATE` → `db.Date`
- `DATE_TO_SUB` → `db.Date`
- `DateRequired` → `db.Date`
- `DateCompleted` → `db.DateTime`
- `RETURNDATE` → `db.Date`
- `DATEOUT` → `db.Date`
- `DateIn` → `db.Date`

✅ **Boolean Fields:**
- `RushOrder` → `db.Boolean`
- `FirmRush` → `db.Boolean`
- `QUOTE` → `db.Boolean`
- `APPROVED` → `db.Boolean`
- `CLEAN` → `db.Boolean` (uses "YES"/"NO" values)
- `CLEANFIRST` → `db.Boolean` (uses "YES"/"NO" values)

✅ **String Fields (unchanged):**
- `SEECLEAN` → String (work order reference)

✅ **Timestamp Fields:**
- `created_at` → `db.DateTime` with server_default=func.now()
- `updated_at` → `db.DateTime` with server_default=func.now(), onupdate=func.now()

✅ **to_dict() method updated** - Properly serializes dates to strings

### 4. RepairWorkOrderItem Model (`models/repair_order.py`)
✅ `Qty` → `db.Integer`
✅ `Price` → `db.Numeric(10, 2)`

### 5. Inventory Model (`models/inventory.py`)
✅ `Qty` → `db.Integer`
✅ `Price` → `db.Numeric(10, 2)`

---

## 🔧 TODO: Route Updates Needed

The following route files need updates to handle the new data types:

### High Priority (Most Changes Needed)

#### 1. `routes/work_orders.py`
**Boolean Field Updates:**
```python
# OLD (string comparison)
if wo.RushOrder == "1":
work_order.RushOrder = request.form.get("RushOrder", "0")

# NEW (boolean)
if wo.RushOrder:
work_order.RushOrder = "RushOrder" in request.form
```

**Date Field Updates:**
```python
# OLD (string)
work_order.DateIn = datetime.now().strftime("%Y-%m-%d")
work_order.DateCompleted = request.form.get("DateCompleted")

# NEW (date object)
from datetime import date
work_order.DateIn = date.today()
date_str = request.form.get("DateCompleted")
work_order.DateCompleted = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
```

**Query Updates:**
```python
# OLD
or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")

# NEW
WorkOrder.DateCompleted.is_(None)
```

#### 2. `routes/queue.py`
**Sorting Logic Updates:**
```python
# OLD (string fallback)
wo.DateRequired or "9999-12-31"

# NEW (date object)
from datetime import date
wo.DateRequired or date.max
```

**Boolean Comparisons:**
```python
# OLD
if wo.FirmRush == "1":
elif wo.RushOrder == "1":

# NEW
if wo.FirmRush:
elif wo.RushOrder:
```

#### 3. `routes/ml.py`
**Feature Engineering:**
```python
# OLD
"datein": order.DateIn or datetime.now().strftime("%Y-%m-%d")
"rushorder": order.RushOrder or False

# NEW
from datetime import date
"datein": order.DateIn or date.today()
"rushorder": bool(order.RushOrder)  # Already boolean, but explicit conversion
```

#### 4. `routes/dashboard.py`
**Boolean Value Check:**
```python
# OLD
rush_orders_count = sum(1 for wo in recent_orders if wo.RushOrder == "Y")

# NEW
rush_orders_count = sum(1 for wo in recent_orders if wo.RushOrder)
```

#### 5. `routes/repair_order.py`
**Checkbox Handling:**
```python
# OLD
CLEAN=request.form.get("CLEAN")  # Gets "YES" or None

# NEW
CLEAN="CLEAN" in request.form  # True if checked, False if not
```

### Medium Priority

#### 6. `routes/analytics.py`
- Update date operations to handle date objects
- Price/Qty fields now numeric (may need `.float()` or casting removed)

#### 7. `routes/in_progress.py`
- Update boolean field checks
- Update date field handling

---

## 🎨 TODO: Template Updates Needed

### Template Files to Update (25 files)

#### High Priority Templates:

**`templates/work_orders/create.html`**
- Checkboxes work as-is (just check for boolean truthy value)
- Date inputs need `.isoformat()` for value attribute

**`templates/work_orders/edit.html`**
- Same as create.html
- Update Clean/Treat date input handling

**`templates/work_orders/cleaning_room_edit.html`**
- Update Clean/Treat date inputs

**`templates/work_orders/detail.html`**
- Boolean display (use `yesdash` filter)
- Date display (use `date_format` filter)

**`templates/repair_orders/create.html`**
- Update CLEAN/CLEANFIRST checkbox handling (value="YES")

**`templates/repair_orders/edit.html`**
- Same as create

**`templates/repair_orders/detail.html`**
- Boolean/date display updates

**`templates/queue/list.html`**
- Rush order badge logic
- Date sorting display

### Template Pattern Updates:

**Checkbox Pattern:**
```html
<!-- WORKS AS-IS - Boolean truthy check -->
<input type="checkbox" name="RushOrder" value="1"
       {% if work_order.RushOrder %}checked{% endif %}>
```

**Date Input Pattern:**
```html
<!-- OLD -->
<input type="date" name="DateIn" value="{{ work_order.DateIn }}">

<!-- NEW -->
<input type="date" name="DateIn"
       value="{{ work_order.DateIn.isoformat() if work_order.DateIn else '' }}">
```

**Date Display Pattern:**
```html
<!-- Use date_format filter (needs updating) -->
{{ work_order.DateIn | date_format }}
```

---

## 🔧 TODO: Template Filter Updates

### `app.py` - Template Filters

**1. Update `yesdash` filter:**
```python
# OLD
@app.template_filter("yesdash")
def yesdash(value):
    if str(value).upper() in ("1", "YES", "TRUE"):
        return "Yes"
    return "-"

# NEW
@app.template_filter("yesdash")
def yesdash(value):
    return "Yes" if value else "-"
```

**2. Update `date_format` filter:**
```python
# OLD (complex string parsing)
@app.template_filter("date_format")
def format_date(value):
    # Multiple format parsing logic...

# NEW (simpler, handles date objects)
@app.template_filter("date_format")
def format_date(value):
    from datetime import datetime, date
    if not value:
        return "-"
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime):
            return value.strftime("%m/%d/%Y %H:%M:%S")
        return value.strftime("%m/%d/%Y")
    # Fallback for any remaining string values
    return str(value)
```

---

## 📋 Migration Execution Plan

### Step 1: Run Database Migration ✅ READY
```bash
export DATABASE_URL="postgresql://postgres:DoloresFlagstaff9728@database-1.ca3sci02uq0g.us-east-1.rds.amazonaws.com:5432/clean_repair"

./migration_tool/complete_migration.sh
```

This will:
1. Backup users (already done ✅)
2. Convert Access DB → SQLite
3. Audit data quality
4. Create PostgreSQL schema
5. Transfer data with type conversions
6. Restore users

### Step 2: Update Code (IN PROGRESS)
- ✅ Models updated
- ⏳ Routes need updating (6-8 files)
- ⏳ Templates need updating (25 files)
- ⏳ Template filters need updating (2 filters)

### Step 3: Test Application
- Run application against migrated database
- Test all forms
- Test all queries
- Test PDF generation
- Test ML predictions

---

## 🚀 Quick Reference: Common Patterns

### Form Submission (Routes)

**Boolean Checkboxes:**
```python
# Checkbox is present = True, absent = False
work_order.RushOrder = "RushOrder" in request.form
work_order.FirmRush = "FirmRush" in request.form
```

**Date Fields:**
```python
from datetime import datetime, date

# Date input
date_str = request.form.get("DateIn")
work_order.DateIn = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()

# DateTime input
datetime_str = request.form.get("DateCompleted")
work_order.DateCompleted = datetime.strptime(datetime_str, "%Y-%m-%d") if datetime_str else None
```

**Numeric Fields:**
```python
# Integer
qty_str = request.form.get("Qty")
item.Qty = int(qty_str) if qty_str else None

# Decimal
price_str = request.form.get("Price")
item.Price = float(price_str) if price_str else None
```

### Query Patterns

**Boolean Filters:**
```python
# OLD
WorkOrder.query.filter(WorkOrder.RushOrder == "1")

# NEW
WorkOrder.query.filter(WorkOrder.RushOrder == True)
# OR
WorkOrder.query.filter(WorkOrder.RushOrder.is_(True))
```

**Date Filters:**
```python
# NULL checks
WorkOrder.query.filter(WorkOrder.DateCompleted.is_(None))

# Date range
from datetime import date, timedelta
start_date = date.today() - timedelta(days=30)
WorkOrder.query.filter(WorkOrder.DateIn >= start_date)
```

**Sorting:**
```python
# Dates sort naturally now
WorkOrder.query.order_by(WorkOrder.DateIn.desc())

# With NULL handling
WorkOrder.query.order_by(WorkOrder.DateRequired.desc().nullslast())
```

---

## 📝 Files Modified

### Models (5 files) ✅
- ✅ `models/work_order.py` - WorkOrder, WorkOrderItem
- ✅ `models/repair_order.py` - RepairWorkOrder, RepairWorkOrderItem
- ✅ `models/inventory.py` - Inventory

### Routes (7 files) ⏳
- ⏳ `routes/work_orders.py` (highest priority - 20+ changes)
- ⏳ `routes/queue.py` (15+ changes)
- ⏳ `routes/ml.py` (10+ changes)
- ⏳ `routes/dashboard.py` (5+ changes)
- ⏳ `routes/repair_order.py`
- ⏳ `routes/analytics.py`
- ⏳ `routes/in_progress.py`

### Templates (25 files) ⏳
- ⏳ `templates/work_orders/` (all files)
- ⏳ `templates/repair_orders/` (all files)
- ⏳ `templates/queue/` (list.html)
- ⏳ `templates/in_progress/` (all files)
- ⏳ `templates/dashboard.html`

### Filters (1 file) ⏳
- ⏳ `app.py` - Template filters (yesdash, date_format)

---

## 🎯 Next Steps

1. **Update template filters in app.py** - Quick, affects all templates
2. **Update high-priority route files** - work_orders.py, queue.py, ml.py
3. **Update high-priority templates** - create.html, edit.html for both WO and RO
4. **Test incrementally** - Test after each major file update
5. **Run full test suite** - pytest
6. **Manual QA** - Test all major workflows

---

*Models Updated: 2025-10-03*
*Ready for Route/Template Updates*
