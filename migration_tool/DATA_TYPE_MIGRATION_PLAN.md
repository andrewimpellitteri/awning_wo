# Data Type Migration Plan
## Converting String Fields to Proper Data Types

### Executive Summary
This document outlines the migration strategy for converting improperly typed fields (strings used for dates, booleans, and numeric values) to their correct data types across the database models. The current implementation uses strings throughout due to legacy Access database constraints.

---

## 📊 Current State Analysis

### Models Affected
1. **WorkOrder** (`models/work_order.py`)
2. **WorkOrderItem** (`models/work_order.py`)
3. **RepairWorkOrder** (`models/repair_order.py`)
4. **RepairWorkOrderItem** (`models/repair_order.py`)
5. **Inventory** (`models/inventory.py`)

### Fields Requiring Type Conversion

#### WorkOrder Model
| Field Name | Current Type | Target Type | Values/Format | Usage Notes |
|------------|-------------|-------------|---------------|-------------|
| `DateCompleted` | String | DateTime (nullable) | YYYY-MM-DD or MM/DD/YY HH:MM:SS | Used for completion filtering |
| `DateRequired` | String | Date (nullable) | YYYY-MM-DD | Used for rush order sorting |
| `DateIn` | String | Date | YYYY-MM-DD | Set to `datetime.now()` on creation |
| `Clean` | String | **Date (nullable)** | YYYY-MM-DD | **Date input field** - when cleaning completed |
| `Treat` | String | **Date (nullable)** | YYYY-MM-DD | **Date input field** - when treatment completed |
| `RushOrder` | String | Boolean | "1", "0" | Checkbox, compared as `== "1"` |
| `FirmRush` | String | Boolean | "1", "0" | Checkbox, compared as `== "1"` |
| `Quote` | String | Boolean | "1", "0", or None | Checkbox in forms |
| `SeeRepair` | String | Boolean | "1", "0", or None | Checkbox in forms |
| `CleanFirstWO` | String | **String (keep)** | Work order number reference | Text field - references another WO |
| `StorageTime` | String | String with CHECK constraint | "Seasonal", "Temporary", or None | Dropdown - keep as string, add constraint |

#### RepairWorkOrder Model
| Field Name | Current Type | Target Type | Values/Format | Usage Notes |
|------------|-------------|-------------|---------------|-------------|
| `WO_DATE` | String | Date (nullable) | Various formats | Uppercase with space |
| `DATE_TO_SUB` | String | Date (nullable) | Various formats | Uppercase with spaces |
| `DateRequired` | String | Date (nullable) | YYYY-MM-DD | Standard date field |
| `DateCompleted` | String | DateTime (nullable) | Various formats | Completion tracking |
| `RETURNDATE` | String | Date (nullable) | Various formats | Return tracking |
| `DATEOUT` | String | Date (nullable) | Various formats | Output tracking |
| `DateIn` | String | Date | YYYY-MM-DD | Input tracking |
| `RushOrder` | String | Boolean | "1", "0", or None | Priority flag |
| `FirmRush` | String | Boolean | "1", "0", or None | Higher priority flag |
| `QUOTE` | String | Boolean | "1", "0", or None | Quote flag |
| `APPROVED` | String | Boolean | "1", "0", "Approved", or None | Approval status |
| `CLEAN` | String | **Boolean** | "YES" or None | **Checkbox** - uses "YES" not "1" |
| `SEECLEAN` | String | **String (keep)** | Work order number reference | References cleaning WO number |
| `CLEANFIRST` | String | **Boolean** | "YES" or None | **Checkbox** - uses "YES" not "1" |
| `created_at` | String | DateTime | ISO format string | Uses lambda for default |
| `updated_at` | String | DateTime | ISO format string | Uses lambda for onupdate |

#### WorkOrderItem & RepairWorkOrderItem Models
| Field Name | Current Type | Target Type | Values/Format | Usage Notes |
|------------|-------------|-------------|---------------|-------------|
| `Qty` | String | Integer (nullable) | Numeric strings | Quantity field |
| `Price` | String | Decimal(10,2) (nullable) | Currency strings with $ | Used in analytics |

#### Inventory Model
| Field Name | Current Type | Target Type | Values/Format | Usage Notes |
|------------|-------------|-------------|---------------|-------------|
| `Qty` | String | Integer (nullable) | Numeric strings | Quantity tracking |
| `Price` | String | Decimal(10,2) (nullable) | Currency strings | Pricing |

---

## 🔍 Code Dependencies Analysis

### Template/Form Dependencies
- **Checkboxes**: Forms use `value="1"` and check with `{% if form_data.get('RushOrder') == '1' %}checked{% endif %}`
- **Date Inputs**: Use `<input type="date">` which works with strings
- **Current approach**: Templates expect string values

### Route/Controller Dependencies

#### Boolean String Comparisons Found:
```python
# routes/work_orders.py
if wo.RushOrder == "1"
if wo.FirmRush == "1"
or_(WorkOrder.RushOrder == "1", WorkOrder.FirmRush == "1")

# routes/queue.py
if wo.FirmRush == "1":
elif wo.RushOrder == "1":

# routes/dashboard.py
rush_orders_count = sum(1 for wo in recent_orders if wo.RushOrder == "Y")  # Note: "Y" not "1"!
```

#### Date String Operations Found:
```python
# routes/work_orders.py
or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
WorkOrder.DateIn = datetime.now().strftime("%Y-%m-%d")  # Creates string
order_by(WorkOrder.DateIn.desc())

# routes/queue.py
wo.DateRequired or "9999-12-31"  # String fallback for sorting
wo.DateIn or "9999-12-31"

# routes/ml.py
"datein": order.DateIn or datetime.now().strftime("%Y-%m-%d")
completion_date = pd.to_datetime(order.DateIn) + pd.Timedelta(days=prediction)
```

#### Template Filter Dependencies:
```python
# app.py
@app.template_filter("yesdash")
def yesdash(value):
    if str(value).upper() in ("1", "YES", "TRUE"):
        return "Yes"
    return "-"

@app.template_filter("date_format")
def format_date(value):
    # Handles datetime, date, custom strings, and ISO strings
    # Multiple format parsing logic
```

### Migration Tool Dependencies
```python
# migration_tool/run_migration.py - Step 3
# Currently transfers data as-is without type conversion
# No date parsing or boolean conversion logic
```

### Analytics Dependencies
```python
# routes/analytics.py
def clean_numeric_string(value):
    # Parses currency strings to float
    # Used for Price fields

# Date operations in analytics likely use pandas to_datetime
```

---

## 🚧 Migration Strategy

### Phase 0: Pre-Migration Data Audit (CRITICAL FIRST STEP)
**Goal**: Understand all data variations before writing migration logic

#### Step 0.1: Create Data Audit Script
Create `migration_tool/audit_data_quality.py`:

```python
"""
Data quality audit script - run BEFORE migration to understand data variations
"""
import pandas as pd
from sqlalchemy import create_engine, text
from migration_config import POSTGRES_URI

def audit_boolean_fields(engine):
    """Check what actual values exist in boolean fields"""
    print("\n" + "="*80)
    print("BOOLEAN FIELD AUDIT")
    print("="*80)

    boolean_fields = {
        'tblcustworkorderdetail': ['rushorder', 'firmrush', 'quote', 'seerepair'],
        'tblrepairworkorderdetail': ['rushorder', 'firmrush', 'quote', 'approved', 'clean', 'cleanfirst']
    }

    results = {}
    for table, fields in boolean_fields.items():
        results[table] = {}
        for field in fields:
            query = text(f"""
                SELECT {field} as value, COUNT(*) as count
                FROM {table}
                GROUP BY {field}
                ORDER BY count DESC
            """)
            df = pd.read_sql(query, engine)
            results[table][field] = df
            print(f"\n{table}.{field}:")
            print(df.to_string(index=False))

    return results

def audit_date_fields(engine):
    """Check date field formats and sample values"""
    print("\n" + "="*80)
    print("DATE FIELD AUDIT")
    print("="*80)

    date_fields = {
        'tblcustworkorderdetail': ['datecompleted', 'daterequired', 'datein', 'clean', 'treat'],
        'tblrepairworkorderdetail': ['"WO DATE"', '"DATE TO SUB"', 'daterequired', 'datecompleted', 'returndate', 'dateout', 'datein']
    }

    results = {}
    for table, fields in date_fields.items():
        results[table] = {}
        for field in fields:
            # Sample distinct values
            query = text(f"""
                SELECT DISTINCT {field} as value, COUNT(*) as count
                FROM {table}
                WHERE {field} IS NOT NULL AND {field} != ''
                GROUP BY {field}
                ORDER BY count DESC
                LIMIT 30
            """)
            df = pd.read_sql(query, engine)
            results[table][field] = df
            print(f"\n{table}.{field} - Top 30 values:")
            print(df.to_string(index=False))

            # Check for potentially invalid dates
            invalid_query = text(f"""
                SELECT {field} as value, COUNT(*) as count
                FROM {table}
                WHERE {field} LIKE '%0000%'
                   OR {field} LIKE '%99/99%'
                   OR {field} LIKE '%00/00%'
                GROUP BY {field}
            """)
            invalid_df = pd.read_sql(invalid_query, engine)
            if len(invalid_df) > 0:
                print(f"  WARNING: Potentially invalid dates found:")
                print(invalid_df.to_string(index=False))

    return results

def audit_numeric_fields(engine):
    """Check Price and Qty fields for formatting issues"""
    print("\n" + "="*80)
    print("NUMERIC FIELD AUDIT")
    print("="*80)

    numeric_fields = {
        'tblorddetcustawngs': ['qty', 'price'],
        'tblreporddetcustawngs': ['qty', 'price'],
        'tblcustawngs': ['qty', 'price']
    }

    results = {}
    for table, fields in numeric_fields.items():
        results[table] = {}
        for field in fields:
            # Sample distinct values
            query = text(f"""
                SELECT DISTINCT {field} as value, COUNT(*) as count
                FROM {table}
                WHERE {field} IS NOT NULL AND {field} != ''
                GROUP BY {field}
                ORDER BY count DESC
                LIMIT 20
            """)
            df = pd.read_sql(query, engine)
            results[table][field] = df
            print(f"\n{table}.{field} - Sample values:")
            print(df.to_string(index=False))

            # Check for values with currency symbols
            currency_query = text(f"""
                SELECT {field} as value, COUNT(*) as count
                FROM {table}
                WHERE {field} LIKE '%$%' OR {field} LIKE '%,%'
                GROUP BY {field}
                LIMIT 10
            """)
            currency_df = pd.read_sql(currency_query, engine)
            if len(currency_df) > 0:
                print(f"  Found values with currency formatting:")
                print(currency_df.to_string(index=False))

    return results

def generate_audit_report(boolean_results, date_results, numeric_results):
    """Generate summary report of findings"""
    print("\n" + "="*80)
    print("AUDIT SUMMARY REPORT")
    print("="*80)

    # Boolean summary
    print("\nBoolean Field Value Variations:")
    all_bool_values = set()
    for table, fields in boolean_results.items():
        for field, df in fields.items():
            all_bool_values.update(df['value'].dropna().astype(str).unique())
    print(f"  Unique boolean values found: {sorted(all_bool_values)}")

    # Date format summary
    print("\nDate Format Issues:")
    print("  Check output above for:")
    print("    - Multiple date formats")
    print("    - Invalid dates (0000-00-00, 99/99/99)")
    print("    - Empty strings vs NULL")

    # Numeric summary
    print("\nNumeric Field Issues:")
    print("  Check output above for:")
    print("    - Currency symbols ($)")
    print("    - Commas in numbers")
    print("    - Non-numeric values")

    print("\n" + "="*80)
    print("Next steps:")
    print("1. Review all output above")
    print("2. Update convert_boolean_field() to handle all found variations")
    print("3. Update convert_date_field() to handle all found formats")
    print("4. Create test cases for edge cases")
    print("5. Export sample problematic records for testing")
    print("="*80)

if __name__ == "__main__":
    engine = create_engine(POSTGRES_URI)

    print("Starting data quality audit...")
    print(f"Database: {POSTGRES_URI}")

    boolean_results = audit_boolean_fields(engine)
    date_results = audit_date_fields(engine)
    numeric_results = audit_numeric_fields(engine)

    generate_audit_report(boolean_results, date_results, numeric_results)

    print("\nAudit complete! Review findings above before proceeding with migration.")
```

#### Step 0.2: Run Audit and Document Findings
```bash
cd migration_tool
python audit_data_quality.py > audit_report_$(date +%Y%m%d).txt
```

Review the audit report and update conversion functions based on actual data found.

### Phase 1: Data Migration Script
**Goal**: Convert existing data in database from string formats to proper types

#### Step 1.1: Create Backup
```bash
pg_dump -U postgres -d clean_repair > backup_before_type_migration.sql
```

#### Step 1.2: Add Migration Logic to `run_migration.py`
Create new function `step_3_5_convert_data_types()` to run between steps 3 and 4:

```python
def convert_date_field(value):
    """Convert various date string formats to proper date object"""
    if pd.isna(value) or value in ['', None]:
        return None
    try:
        # Try YYYY-MM-DD format
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except:
        try:
            # Try MM/DD/YY HH:MM:SS format
            return datetime.strptime(str(value), "%m/%d/%y %H:%M:%S").date()
        except:
            # Try ISO format
            try:
                return datetime.fromisoformat(str(value)).date()
            except:
                return None

def convert_boolean_field(value):
    """Convert string boolean to actual boolean - handles messy legacy data"""
    if pd.isna(value) or value in ['', None]:
        return None

    # Convert to uppercase string for comparison
    str_value = str(value).strip().upper()

    # Truthy values
    if str_value in ("1", "YES", "Y", "TRUE", "T"):
        return True

    # Falsy values (explicit false)
    if str_value in ("0", "NO", "N", "FALSE", "F"):
        return False

    # Default to None for unexpected values
    return None

def convert_numeric_field(value, field_type='integer'):
    """Convert string numeric to integer or decimal"""
    if pd.isna(value) or value in ['', None]:
        return None

    try:
        # Remove currency symbols and commas
        cleaned = str(value).replace('$', '').replace(',', '').strip()

        if field_type == 'integer':
            # Convert to int
            return int(float(cleaned))  # float first to handle "5.0" -> 5
        else:
            # Convert to decimal (for Price fields)
            return round(float(cleaned), 2)
    except (ValueError, AttributeError):
        print(f"WARNING: Could not convert numeric value: {repr(value)}")
        return None
```

#### Step 1.3: Update Column Types via Alembic Migration
Create Alembic migration script:
```bash
flask db revision -m "convert_string_fields_to_proper_types"
```

Migration operations needed:
- Use `ALTER COLUMN` with `USING` clause for type conversion
- Handle NULL values appropriately
- Add constraints for non-nullable fields

### Phase 2: Model Updates
**Goal**: Update SQLAlchemy models with correct data types

#### Step 2.1: Update WorkOrder Model
```python
# Before
DateCompleted = db.Column("datecompleted", db.String)
DateRequired = db.Column("daterequired", db.String)
DateIn = db.Column("datein", db.String)
Clean = db.Column("clean", db.String)
Treat = db.Column("treat", db.String)
RushOrder = db.Column("rushorder", db.String)
FirmRush = db.Column("firmrush", db.String)

# After
DateCompleted = db.Column("datecompleted", db.DateTime, nullable=True)
DateRequired = db.Column("daterequired", db.Date, nullable=True)
DateIn = db.Column("datein", db.Date, nullable=False, default=func.current_date())
Clean = db.Column("clean", db.Date, nullable=True)  # Date when cleaning completed
Treat = db.Column("treat", db.Date, nullable=True)  # Date when treatment completed
RushOrder = db.Column("rushorder", db.Boolean, default=False)
FirmRush = db.Column("firmrush", db.Boolean, default=False)
Quote = db.Column("quote", db.Boolean, default=False)
SeeRepair = db.Column("seerepair", db.Boolean, default=False)
CleanFirstWO = db.Column("cleanfirstwo", db.String)  # Work order number reference
StorageTime = db.Column("storagetime", db.String)  # "Seasonal" or "Temporary"
```

#### Step 2.2: Update RepairWorkOrder Model
Similar pattern for all date and boolean fields, plus:
```python
# Date fields
WO_DATE = db.Column("WO DATE", db.Date, nullable=True)
DATE_TO_SUB = db.Column("DATE TO SUB", db.Date, nullable=True)
DateRequired = db.Column("daterequired", db.Date, nullable=True)
DateCompleted = db.Column("datecompleted", db.DateTime, nullable=True)
RETURNDATE = db.Column("returndate", db.Date, nullable=True)
DATEOUT = db.Column("dateout", db.Date, nullable=True)
DateIn = db.Column("datein", db.Date, nullable=True)

# Boolean fields - note: uses "YES" values, not "1"
RushOrder = db.Column("rushorder", db.Boolean, default=False)
FirmRush = db.Column("firmrush", db.Boolean, default=False)
QUOTE = db.Column("quote", db.Boolean, default=False)
APPROVED = db.Column("approved", db.Boolean, default=False)
CLEAN = db.Column("clean", db.Boolean, default=False)
CLEANFIRST = db.Column("cleanfirst", db.Boolean, default=False)

# String reference fields - keep as strings
SEECLEAN = db.Column("seeclean", db.String)  # Work order number reference

# Fix created_at and updated_at
created_at = db.Column(db.DateTime, server_default=func.now())
updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())
```

#### Step 2.3: Update Item Models
```python
# WorkOrderItem and RepairWorkOrderItem
Qty = db.Column("qty", db.Integer, nullable=True)
Price = db.Column("price", db.Numeric(10, 2), nullable=True)
```

### Phase 3: Route/Controller Updates
**Goal**: Update all route handlers to work with proper data types

#### Step 3.1: Boolean Field Updates
**Find and replace pattern:**
```python
# Old
if wo.RushOrder == "1":
work_order.RushOrder = request.form.get("RushOrder", "0")

# New
if wo.RushOrder:
work_order.RushOrder = bool(request.form.get("RushOrder"))
```

**Checkbox handling:**
```python
# Old approach
RushOrder=request.form.get("RushOrder", "0")

# New approach
RushOrder=bool(request.form.get("RushOrder"))
# Or for checkboxes specifically:
RushOrder="RushOrder" in request.form
```

#### Step 3.2: Date Field Updates
```python
# Old
DateIn=datetime.now().strftime("%Y-%m-%d")
work_order.DateCompleted = request.form.get("DateCompleted")

# New
DateIn=date.today()
date_str = request.form.get("DateCompleted")
work_order.DateCompleted = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
```

#### Step 3.3: Query Updates
```python
# Old
or_(WorkOrder.DateCompleted.is_(None), WorkOrder.DateCompleted == "")
WorkOrder.DateIn.desc()

# New
WorkOrder.DateCompleted.is_(None)
WorkOrder.DateIn.desc().nullslast()
```

#### Step 3.4: Sorting Logic Updates (queue.py)
```python
# Old
wo.DateRequired or "9999-12-31"

# New
wo.DateRequired or date.max
# Or use nullslast() in SQLAlchemy queries
```

### Phase 4: Template Updates
**Goal**: Update Jinja2 templates to work with proper data types

#### Step 4.1: Checkbox Updates
**No changes needed** - checkboxes work the same:
```html
<!-- Works with both string and boolean -->
<input type="checkbox" name="RushOrder" value="1"
       {% if work_order.RushOrder %}checked{% endif %}>
```

#### Step 4.2: Date Input Updates
**Minimal changes needed:**
```html
<!-- Old -->
<input type="date" name="DateIn" value="{{ work_order.DateIn }}">

<!-- New - add date filter for safety -->
<input type="date" name="DateIn"
       value="{{ work_order.DateIn.isoformat() if work_order.DateIn else '' }}">
```

#### Step 4.3: Template Filter Updates
```python
# yesdash filter - needs update
@app.template_filter("yesdash")
def yesdash(value):
    # Before: checks string values
    # After:
    return "Yes" if value else "-"

# date_format filter - simplify
@app.template_filter("date_format")
def format_date(value):
    if not value:
        return "-"
    if isinstance(value, (datetime, date)):
        return value.strftime("%m/%d/%Y")
    return str(value)
```

### Phase 5: Form Validation Updates
**Goal**: Add proper validation for new data types

#### Step 5.1: Create WTForms Form Classes
Replace manual form handling with WTForms:
```python
from wtforms import StringField, BooleanField, DateField, DecimalField
from wtforms.validators import Optional, DataRequired

class WorkOrderForm(FlaskForm):
    DateIn = DateField('Date In', validators=[DataRequired()])
    DateRequired = DateField('Date Required', validators=[Optional()])
    DateCompleted = DateTimeField('Date Completed', validators=[Optional()])
    Clean = DateField('Clean Date', validators=[Optional()])  # Date when cleaning completed
    Treat = DateField('Treat Date', validators=[Optional()])  # Date when treatment completed
    RushOrder = BooleanField('Rush Order')
    FirmRush = BooleanField('Firm Rush')
    Quote = BooleanField('Quote')
    SeeRepair = BooleanField('See Repair')
    CleanFirstWO = StringField('Clean First WO')  # Work order number reference
    StorageTime = SelectField('Storage Time', choices=[('', ''), ('Seasonal', 'Seasonal'), ('Temporary', 'Temporary')])
    # ... etc
```

### Phase 6: ML/Analytics Updates
**Goal**: Update data processing code to handle proper types

#### Step 6.1: Update Feature Engineering
```python
# Old
"datein": order.DateIn or datetime.now().strftime("%Y-%m-%d")
"rushorder": order.RushOrder or False

# New
"datein": order.DateIn or date.today()
"rushorder": bool(order.RushOrder)
```

#### Step 6.2: Update DataFrame Operations
```python
# Pandas will handle proper types automatically now
df['DateIn'] = pd.to_datetime(df['DateIn'])  # No longer needed if already datetime
```

### Phase 7: PDF Generation Updates
**Goal**: Update PDF generation to handle new types

#### Step 7.1: Date Formatting
```python
# work_order_pdf.py and repair_order_pdf.py
# Old
if work_order.DateIn:
    formatted_date = work_order.DateIn

# New
if work_order.DateIn:
    formatted_date = work_order.DateIn.strftime("%m/%d/%Y")
```

### Phase 8: Testing Updates
**Goal**: Update all tests to use proper data types

#### Step 8.1: Test Fixtures
```python
# Old
test_work_order = WorkOrder(
    DateIn="2024-01-15",
    RushOrder="1",
    Clean="0"
)

# New
test_work_order = WorkOrder(
    DateIn=date(2024, 1, 15),
    RushOrder=True,
    Clean=date(2024, 1, 20),  # Date when cleaned
    Treat=None  # Not yet treated
)
```

---

## 📋 Implementation Checklist

### Pre-Migration
- [ ] Create full database backup
- [ ] **CRITICAL: Run data quality audit on production data**
  - [ ] Run `audit_boolean_fields()` to find all boolean value variations
  - [ ] Run `audit_date_fields()` to find all date format variations
  - [ ] Document unexpected values and edge cases
  - [ ] Export sample data with messy values for testing
  - [ ] Create test cases for all discovered value patterns
- [ ] Set up test environment with production data copy
- [ ] Review all forms for checkbox handling patterns
- [ ] Audit all string comparison operations (`grep -r '== "1"'`, `grep -r '== "Y"'`)
- [ ] **Create data quality report** with findings from audit

### Migration Execution
- [ ] Phase 1: Data migration script
  - [ ] Create Alembic migration
  - [ ] Add data conversion functions
  - [ ] Test on development database
  - [ ] Test on staging database with production copy
- [ ] Phase 2: Model updates
  - [ ] Update WorkOrder model
  - [ ] Update RepairWorkOrder model
  - [ ] Update WorkOrderItem model
  - [ ] Update RepairWorkOrderItem model
  - [ ] Update Inventory model
- [ ] Phase 3: Route updates (47 files to check)
  - [ ] Update work_orders.py (highest priority - 20+ changes)
  - [ ] Update queue.py (15+ changes)
  - [ ] Update ml.py (10+ changes)
  - [ ] Update dashboard.py (5+ changes)
  - [ ] Update repair_order.py
  - [ ] Update analytics.py
  - [ ] Update in_progress.py
- [ ] Phase 4: Template updates (25 templates to check)
  - [ ] Update work_orders/create.html
  - [ ] Update work_orders/edit.html
  - [ ] Update work_orders/detail.html
  - [ ] Update work_orders/cleaning_room_edit.html
  - [ ] Update repair_orders/create.html
  - [ ] Update repair_orders/edit.html
  - [ ] Update repair_orders/detail.html
  - [ ] Update queue/list.html
  - [ ] Update template filters in app.py
- [ ] Phase 5: Form validation
  - [ ] Create WTForms classes for WorkOrder
  - [ ] Create WTForms classes for RepairWorkOrder
  - [ ] Add validation error handling
- [ ] Phase 6: ML/Analytics updates
  - [ ] Update feature engineering code
  - [ ] Update DataFrame operations
  - [ ] Update prediction endpoints
- [ ] Phase 7: PDF generation updates
  - [ ] Update work_order_pdf.py
  - [ ] Update repair_order_pdf.py
- [ ] Phase 8: Testing
  - [ ] Update test fixtures
  - [ ] Update test assertions
  - [ ] Run full test suite
  - [ ] Manual testing of all forms
  - [ ] Manual testing of all queries

### Post-Migration
- [ ] Run full test suite
- [ ] Perform manual QA on all major workflows
- [ ] Monitor error logs for type-related issues
- [ ] Update CLAUDE.md documentation
- [ ] Deploy to staging
- [ ] Deploy to production
- [ ] Monitor production for 48 hours

---

## ⚠️ Risk Assessment

### High Risk Areas
1. **Boolean Comparisons** - Many places check `== "1"` or `== "Y"`, inconsistent values
2. **Date Sorting in Queue** - Complex sorting logic with string fallbacks
3. **Form Submissions** - Checkbox values need careful handling
4. **ML Feature Engineering** - Hardcoded string parsing logic
5. **Analytics Queries** - Complex date filtering and aggregation

### Medium Risk Areas
1. **PDF Generation** - Date formatting changes
2. **Template Filters** - Used throughout templates
3. **API Responses** - JSON serialization of new types
4. **to_dict() Methods** - Need to handle date/bool serialization

### Low Risk Areas
1. **User Model** - Already has proper types
2. **Source Model** - Minimal date/bool fields
3. **Customer Model** - Text-heavy, few type changes needed

---

## 🔄 Rollback Plan

### If Migration Fails
1. Restore database from pre-migration backup
2. Revert code changes via git
3. Redeploy previous version to Elastic Beanstalk
4. Analyze failure logs
5. Fix issues in development
6. Re-test before retry

### Partial Rollback Strategy
- Migration is all-or-nothing due to tight coupling
- Cannot partially migrate due to model dependencies
- Must complete all phases or fully rollback

---

## 📝 Special Considerations

### 1. Inconsistent Boolean Values
Current code shows both `"1"`/`"0"` and `"Y"`/`"N"` patterns. Migration must handle:
```python
# dashboard.py uses "Y"
if wo.RushOrder == "Y"

# queue.py uses "1"
if wo.RushOrder == "1"
```
**Solution**: Convert both to boolean True/False

### 2. Date Format Variations - MESSY DATA WARNING
Multiple date formats found in production data:
- `YYYY-MM-DD` (most common)
- `MM/DD/YY HH:MM:SS` (legacy Access format)
- `MM/DD/YYYY` (alternative format)
- `M/D/YY` or `M/D/YYYY` (single-digit months/days)
- ISO format strings (`YYYY-MM-DDTHH:MM:SS`)
- Empty strings `""` and NULL values
- Potentially invalid dates like `"0000-00-00"` or `"99/99/99"`

**Solution**: Migration script must handle all formats with robust fallback logic:
```python
def convert_date_field(value):
    """Convert various date string formats to proper date object - handles messy data"""
    if pd.isna(value) or value in ['', None, '0000-00-00', '00/00/00', '00/00/0000']:
        return None

    try:
        # Try pandas to_datetime first (handles most formats)
        parsed = pd.to_datetime(str(value), errors='coerce')
        if pd.notna(parsed):
            return parsed.date()
    except:
        pass

    # Try common formats explicitly
    formats = [
        "%Y-%m-%d",           # 2024-01-15
        "%m/%d/%y %H:%M:%S",  # 01/15/24 14:30:00
        "%m/%d/%Y",           # 01/15/2024
        "%m/%d/%y",           # 01/15/24
        "%-m/%-d/%y",         # 1/5/24 (single digit)
        "%-m/%-d/%Y",         # 1/5/2024
        "%Y-%m-%dT%H:%M:%S",  # ISO format
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except (ValueError, AttributeError):
            continue

    # Log failed conversions for review
    print(f"WARNING: Could not convert date value: {repr(value)}")
    return None
```

**Data quality check needed:**
```python
def audit_date_fields():
    """Check date field formats in production data"""
    date_fields = {
        'tblcustworkorderdetail': ['datecompleted', 'daterequired', 'datein', 'clean', 'treat'],
        'tblrepairworkorderdetail': ['WO DATE', 'DATE TO SUB', 'daterequired', 'datecompleted', 'returndate', 'dateout', 'datein']
    }

    for table, fields in date_fields.items():
        for field in fields:
            query = f"""
                SELECT DISTINCT {field}
                FROM {table}
                WHERE {field} IS NOT NULL AND {field} != ''
                LIMIT 20
            """
            print(f"\n{table}.{field} sample values:")
            # Run query and print results to identify format patterns
```

### 3. StorageTime Field
Currently stores `"Seasonal"` or `"Temporary"` as strings
**Options**:
- Convert to Enum type
- Convert to Integer (0, 1, 2) with lookup
- Keep as String but add CHECK constraint
**Recommendation**: Use SQLAlchemy Enum for type safety

### 4. Price/Quote Fields
Some use strings with `$` and `,` formatting
**Solution**: Strip formatting in migration, use Decimal type

### 5. RepairWorkOrder created_at/updated_at
Currently use lambda functions that return ISO strings
**Solution**: Use `server_default=func.now()` like WorkOrder

### 6. Clean and Treat Fields - CRITICAL DISCOVERY
**WorkOrder.Clean and WorkOrder.Treat are DATE fields, NOT booleans!**

Evidence from templates:
```html
<!-- templates/work_orders/cleaning_room_edit.html -->
<label for="Clean">Clean Date</label>
<input type="date" name="Clean" id="Clean" value="{{ work_order.Clean or '' }}">

<label for="Treat">Treat Date</label>
<input type="date" name="Treat" id="Treat" value="{{ work_order.Treat or '' }}">
```

These fields track **when** cleaning and treatment were completed, not just **if** they were done.

**Migration impact:**
- `Clean` → `db.Date` (nullable) - date when cleaning was completed
- `Treat` → `db.Date` (nullable) - date when treatment was completed
- ML code checks `order.Clean or False` - needs updating to check for date existence
- `if work_order.Treat:` checks need to handle date objects properly
- Template `date_format` filter already handles these correctly

**Route updates needed:**
```python
# routes/work_orders.py:747
# Old
if work_order.Treat:  # String check
    work_order.ProcessingStatus = False

# New - will still work!
if work_order.Treat:  # Date check - truthy if date exists
    work_order.ProcessingStatus = False
```

### 7. CleanFirstWO Field - Keep as String
This is a work order number reference (e.g., "12345"), not a boolean checkbox.
Should remain as String type.

### 8. RepairWorkOrder Boolean Field Values - MESSY DATA WARNING
RepairWorkOrder uses `"YES"` for checkbox values instead of `"1"`, but legacy Access data may have inconsistent values:
```html
<input type="checkbox" name="CLEAN" value="YES">
<input type="checkbox" name="CLEANFIRST" value="YES">
```

**Possible messy values in production data:**
- Truthy: `"YES"`, `"Y"`, `"yes"`, `"y"`, `"1"`, `"TRUE"`, `"True"`, `"true"`
- Falsy: `"NO"`, `"N"`, `"no"`, `"n"`, `"0"`, `"FALSE"`, `"False"`, `"false"`, `""`, `None`

Migration must handle all variations:
```python
def convert_boolean_field(value):
    """Convert string boolean to actual boolean - handles messy legacy data"""
    if pd.isna(value) or value in ['', None]:
        return None

    # Convert to uppercase string for comparison
    str_value = str(value).strip().upper()

    # Truthy values
    if str_value in ("1", "YES", "Y", "TRUE", "T"):
        return True

    # Falsy values (explicit false)
    if str_value in ("0", "NO", "N", "FALSE", "F"):
        return False

    # Default to None for unexpected values
    return None
```

**Data quality check needed before migration:**
```python
# Add to migration script - audit unique values
def audit_boolean_fields():
    """Check what actual values exist in production data"""
    boolean_fields = {
        'tblcustworkorderdetail': ['rushorder', 'firmrush', 'quote', 'seerepair'],
        'tblrepairworkorderdetail': ['rushorder', 'firmrush', 'quote', 'approved', 'clean', 'cleanfirst']
    }

    for table, fields in boolean_fields.items():
        for field in fields:
            query = f"SELECT DISTINCT {field}, COUNT(*) FROM {table} GROUP BY {field}"
            print(f"\n{table}.{field} unique values:")
            # Run query and print results
```

---

## 🎯 Success Metrics

### Migration Success Criteria
- [ ] All tests pass (pytest)
- [ ] Zero type-related errors in logs for 48 hours post-deployment
- [ ] All forms submit successfully
- [ ] All queries execute without errors
- [ ] PDFs generate correctly
- [ ] ML predictions continue to work
- [ ] Analytics dashboard loads and displays data
- [ ] Queue sorting works correctly
- [ ] Date filtering works correctly

### Performance Improvements Expected
- Faster date range queries (proper indexing on date columns)
- More efficient boolean filtering (no string comparisons)
- Reduced storage size (boolean vs string)
- Better query optimization by PostgreSQL

---

## 🔧 Development Commands

```bash
# Create Alembic migration
flask db revision -m "convert_string_fields_to_proper_types"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade

# Run tests
pytest -v --cov=.

# Check for string comparisons
grep -r "== \"1\"" routes/
grep -r "== \"Y\"" routes/
grep -r "== \"0\"" routes/

# Check for date string operations
grep -r "strftime" routes/
grep -r "strptime" routes/
```

---

## 📚 References

### Files to Modify
- `models/work_order.py`
- `models/repair_order.py`
- `models/inventory.py`
- `routes/work_orders.py` (highest priority)
- `routes/queue.py`
- `routes/ml.py`
- `routes/dashboard.py`
- `routes/analytics.py`
- `routes/repair_order.py`
- `routes/in_progress.py`
- `app.py` (template filters)
- `work_order_pdf.py`
- `repair_order_pdf.py`
- All template files in `templates/work_orders/`
- All template files in `templates/repair_orders/`
- `migration_tool/run_migration.py`

### Testing Priority Order
1. Work order creation
2. Work order editing
3. Queue management
4. Date filtering and sorting
5. ML predictions
6. PDF generation
7. Analytics dashboard
8. Repair order workflows

---

## 📅 Estimated Timeline

- **Phase 1 (Data Migration Script)**: 2-3 days
- **Phase 2 (Model Updates)**: 1 day
- **Phase 3 (Route Updates)**: 3-4 days
- **Phase 4 (Template Updates)**: 2 days
- **Phase 5 (Form Validation)**: 2 days
- **Phase 6 (ML/Analytics)**: 1-2 days
- **Phase 7 (PDF Generation)**: 1 day
- **Phase 8 (Testing)**: 2-3 days
- **QA and Deployment**: 2 days

**Total Estimated Time**: 16-20 days

---

## 🚀 Quick Start for Developer

1. **Read this entire document**
2. **Create a development branch**: `git checkout -b feature/proper-data-types`
3. **Start with Phase 1** (data migration script)
4. **Test each phase independently** before moving to the next
5. **Use grep to find all instances** of patterns that need changing
6. **Update tests incrementally** as you go
7. **Document any new edge cases** you discover
8. **Keep CLAUDE.md updated** with changes

---

*Last Updated: 2025-10-02*
*Author: Claude Code Migration Tool*
*Version: 1.0*
