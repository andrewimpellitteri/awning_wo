# Storage Fields Guide (Issue #82)

## TL;DR

**Work Orders:**
- ✅ Use `RackNo` (db: `rack_number`) for physical location
- ✅ Use `StorageTime` (db: `storagetime`) for "Seasonal" / "Temporary"
- ❌ Do NOT use `Storage` (deprecated, empty)

**Repair Orders:**
- ✅ Use `RackNo` (db: `RACK#`) for physical location
- ✅ Use `STORAGE` (db: `storage`) for "TEMPORARY" / "SEASONAL"
- ⚠️ `LOCATION` exists but `RackNo` is primary location field

---

## The Confusion Explained

There was confusion between **storage time type** (how long something is stored) and **physical location** (where it is stored). This guide clarifies which fields to use for what purpose.

### Field Naming Issues

| What You Want | Work Order Field | Repair Order Field | Why It's Confusing |
|---------------|------------------|--------------------|--------------------|
| **Physical Location**<br>(e.g., "5 B", "bin 4 top") | `RackNo`<br>(db: `rack_number`) | `RackNo`<br>(db: `RACK#`) | ✅ Clear - named after racks |
| **Storage Duration Type**<br>("Seasonal" / "Temporary") | `StorageTime`<br>(db: `storagetime`) | `STORAGE`<br>(db: `storage`) | ⚠️ Confusing - RO field is named "STORAGE" not "StorageTime" |
| **Deprecated/Unused** | `Storage`<br>(db: `storage`) | N/A | ❌ Empty, don't use |

---

## Work Orders - Field Usage

### Model: `WorkOrder` (Table: `tblcustworkorderdetail`)

```python
# ✅ CORRECT - Use these fields:

# For physical location (where the item is)
work_order.RackNo = "5 B"  # Maps to rack_number column
work_order.RackNo = "bin 4 top"
work_order.RackNo = "cleaning room"

# For storage time type (how long it's stored)
work_order.StorageTime = "Seasonal"  # Maps to storagetime column
work_order.StorageTime = "Temporary"

# For post-cleaning location
work_order.final_location = "Customer pickup area"

# ❌ WRONG - Don't use this:
work_order.Storage = "..."  # DEPRECATED - column is empty/unused
```

### Database Columns

| Python Attribute | DB Column | Purpose | Values |
|-----------------|-----------|---------|--------|
| `RackNo` | `rack_number` | Physical location | "5 B", "bin 4 top", etc. |
| `StorageTime` | `storagetime` | Storage duration type | "Seasonal", "Temporary" |
| `final_location` | `finallocation` | Post-service location | Any string |
| `Storage` | `storage` | ❌ DEPRECATED | Empty/unused |

---

## Repair Orders - Field Usage

### Model: `RepairWorkOrder` (Table: `tblrepairworkorderdetail`)

```python
# ✅ CORRECT - Use these fields:

# For physical location (where the item is)
repair_order.RackNo = "hang 4"  # Maps to RACK# column
repair_order.RackNo = "6D"
repair_order.RackNo = "1 D"

# For storage time type (how long it's stored)
# NOTE: Field is named STORAGE but it's actually storage TIME type!
repair_order.STORAGE = "TEMPORARY"  # Maps to storage column
repair_order.STORAGE = "SEASONAL"

# For additional location details (legacy)
repair_order.LOCATION = "Back room"  # Maps to location column

# For post-repair location
repair_order.final_location = "Ship to customer"
```

### Database Columns

| Python Attribute | DB Column | Purpose | Values |
|-----------------|-----------|---------|--------|
| `RackNo` | `RACK#` | Physical location (PRIMARY) | "hang 4", "6D", "1 D", etc. |
| `STORAGE` | `storage` | Storage duration type ⚠️ | "TEMPORARY", "SEASONAL" |
| `LOCATION` | `location` | Additional location details | Any string |
| `final_location` | `finallocation` | Post-service location | Any string |

**⚠️ Important:** Despite being named `STORAGE`, this field stores the storage TIME type (Seasonal/Temporary), not a physical location!

---

## Template Labels

### Current Labels (Confusing)

**Work Order Edit:**
- Label says: "Storage"
- Actually saves to: `RackNo` (rack_number)
- **Problem:** Misleading label

**Repair Order Edit:**
- Label says: "Storage"
- Actually saves to: `STORAGE` (storage type dropdown)
- Label says: "Location"
- Actually saves to: `LOCATION` but pre-fills from `RackNo`
- **Problem:** Multiple fields for same purpose

### Recommended Labels (Clear)

**Work Orders:**
```html
<!-- For physical location -->
<label>Location / Rack #</label>
<input name="RackNo" value="{{ work_order.RackNo }}">

<!-- For storage duration -->
<label>Storage Time</label>
<select name="StorageTime">
    <option value="Seasonal">Seasonal</option>
    <option value="Temporary">Temporary</option>
</select>

<!-- For post-cleaning location -->
<label>Final Location (after cleaning)</label>
<input name="final_location" value="{{ work_order.final_location }}">
```

**Repair Orders:**
```html
<!-- For physical location -->
<label>Location / Rack #</label>
<input name="RackNo" value="{{ repair_order.RackNo }}">

<!-- For storage duration (note: field name is STORAGE!) -->
<label>Storage Time</label>
<select name="STORAGE">
    <option value="TEMPORARY">Temporary</option>
    <option value="SEASONAL">Seasonal</option>
</select>

<!-- For post-repair location -->
<label>Final Location (after repair)</label>
<input name="final_location" value="{{ repair_order.final_location }}">
```

---

## Routes - Reading/Writing

### Work Orders Routes

```python
# ✅ CORRECT
from routes.work_orders import work_orders_bp

@work_orders_bp.route('/edit/<work_order_no>', methods=['POST'])
def edit_work_order(work_order_no):
    work_order = WorkOrder.query.get_or_404(work_order_no)

    # Physical location
    work_order.RackNo = request.form.get("RackNo")  # "5 B", "bin 4 top"

    # Storage duration type
    work_order.StorageTime = request.form.get("StorageTime")  # "Seasonal"/"Temporary"

    # Post-service location
    work_order.final_location = request.form.get("final_location")

    # ❌ WRONG - Don't use Storage field
    # work_order.Storage = request.form.get("Storage")  # DEPRECATED!
```

### Repair Orders Routes

```python
# ✅ CORRECT
from routes.repair_order import repair_order_bp

@repair_order_bp.route('/edit/<repair_order_no>', methods=['POST'])
def edit_repair_order(repair_order_no):
    repair_order = RepairWorkOrder.query.get_or_404(repair_order_no)

    # Physical location
    repair_order.RackNo = request.form.get("RackNo")  # "hang 4", "6D"

    # Storage duration type (note field name!)
    repair_order.STORAGE = request.form.get("STORAGE")  # "TEMPORARY"/"SEASONAL"

    # Additional location (optional, legacy)
    repair_order.LOCATION = request.form.get("LOCATION")

    # Post-service location
    repair_order.final_location = request.form.get("final_location")
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Using WorkOrder.Storage
```python
# WRONG - Storage field is deprecated and empty
work_order.Storage = "5 B"  # This goes nowhere useful!

# CORRECT - Use RackNo
work_order.RackNo = "5 B"
```

### ❌ Mistake 2: Confusing STORAGE with location in Repair Orders
```python
# WRONG - STORAGE is for time type, not location
repair_order.STORAGE = "hang 4"  # This is a location, not a time type!

# CORRECT - Use RackNo for location, STORAGE for time
repair_order.RackNo = "hang 4"      # Physical location
repair_order.STORAGE = "TEMPORARY"   # How long it's stored
```

### ❌ Mistake 3: Inconsistent field names between WO and RO
```python
# WRONG - Field names are different!
work_order.STORAGE = "Seasonal"      # Field doesn't exist in WO
repair_order.StorageTime = "SEASONAL"  # Field doesn't exist in RO

# CORRECT - Use the right field for each model
work_order.StorageTime = "Seasonal"     # WO uses StorageTime
repair_order.STORAGE = "SEASONAL"       # RO uses STORAGE (unfortunately)
```

---

## Data Migration Notes

### Work Order Storage Field
- The `storage` column in `tblcustworkorderdetail` is **empty**
- All location data is in `rack_number` column
- No data migration needed - just don't use `Storage` attribute

### Repair Order Storage Field
- The `storage` column in `tblrepairworkorderdetail` **contains data**
- Data is storage time type: "TEMPORARY", "SEASONAL"
- This is why we can't rename it easily - it's actively used!

---

## Why Not Fix This With a Migration?

You might ask: "Why not just rename STORAGE → StorageTime in repair orders?"

**Answer:** We decided not to change the schema because:
1. Schema changes require coordination across dev/test/prod databases
2. Risk of data loss or application downtime
3. The app works correctly - it's just confusing field names
4. Clear documentation and comments solve the problem without risk

---

## Quick Reference Card

**Need to store WHERE something is located?**
- Work Orders: Use `RackNo` (db: `rack_number`)
- Repair Orders: Use `RackNo` (db: `RACK#`)

**Need to store HOW LONG it's stored?**
- Work Orders: Use `StorageTime` (db: `storagetime`) → "Seasonal"/"Temporary"
- Repair Orders: Use `STORAGE` (db: `storage`) → "TEMPORARY"/"SEASONAL"

**Need to store WHERE it goes after service?**
- Both: Use `final_location` (db: `finallocation`)

---

## Related Issues

- **Issue #82**: Combine Storage + Rack # into one field on detail page
- **Issue #67**: Add cleaning storage information to all work order edits (final_location)

---

## See Also

- [models/work_order.py](models/work_order.py) - Lines 17-27 (Storage field definitions)
- [models/repair_order.py](models/repair_order.py) - Lines 48-64 (Storage field definitions)
- [CLAUDE.md](CLAUDE.md) - Project documentation
