# Utility Functions Reference

## Overview

The Awning Management System includes a comprehensive collection of utility functions organized into specialized modules in the `utils/` directory. These functions handle common tasks like data parsing, validation, file uploads, caching, and more.

This reference provides a complete catalog of all utility modules and their functions, with examples and usage guidelines.

## Quick Navigation

- [General Helpers](#general-helpers) - Common utility functions
- [Order Item Helpers](#order-item-helpers) - Work order and repair order item processing
- [Form Helpers](#form-helpers) - Form field extraction and validation
- [Date Helpers](#date-helpers) - Date parsing and formatting
- [Data Processing](#data-processing) - Analytics data cleaning and parsing
- [File Upload](#file-upload) - S3 and local file management
- [Cache Helpers](#cache-helpers) - Caching and cache invalidation
- [PDF Helpers](#pdf-helpers) - PDF generation utilities
- [Thumbnail Generator](#thumbnail-generator) - Image thumbnail creation

---

## General Helpers

**Module:** `utils/helpers.py`

### Phone Number Formatting

#### `format_phone_number(phone)`
Format phone number for consistent display.

**Args:**
- `phone` (str): Raw phone number string

**Returns:** Formatted phone number string

**Examples:**
```python
from utils.helpers import format_phone_number

format_phone_number("5551234567")      # "(555) 123-4567"
format_phone_number("15551234567")     # "(555) 123-4567"
format_phone_number("555-123-4567")    # "(555) 123-4567"
format_phone_number("")                # ""
```

**Usage in templates:** Also available as Jinja2 filter `format_phone`.

---

### Order Number Generation

#### `generate_work_order_number()`
Generate the next work order number in sequence.

**Returns:** Work order number string (format: `WO000001`)

**Example:**
```python
from utils.helpers import generate_work_order_number

next_wo = generate_work_order_number()  # "WO000042"
```

**Thread Safety:** Not thread-safe. Should be called within a database transaction.

#### `generate_repair_order_number()`
Generate the next repair order number in sequence.

**Returns:** Repair order number string (format: `RO000001`)

**Example:**
```python
from utils.helpers import generate_repair_order_number

next_ro = generate_repair_order_number()  # "RO000015"
```

---

### Boolean Conversion

#### `safe_bool_convert(value, default=False)`
Safely convert various types to boolean.

**Args:**
- `value`: Value to convert (bool, int, str, or None)
- `default` (bool): Default value if conversion fails (default: False)

**Returns:** Boolean value

**Examples:**
```python
from utils.helpers import safe_bool_convert

safe_bool_convert(True)                  # True
safe_bool_convert("1")                   # True
safe_bool_convert("yes")                 # True
safe_bool_convert(0)                     # False
safe_bool_convert(None)                  # False
safe_bool_convert("invalid", default=True)  # True
```

**Common Use Cases:**
- Converting HTML checkbox values from forms
- Parsing boolean fields from CSV imports
- API request parameter validation

#### `map_bool_display(value, true_text="Yes", false_text="No", default=False)`
Map boolean values to display text for PDFs and other outputs.

**Args:**
- `value`: Value to convert (bool, int, str, or None)
- `true_text` (str): Text for True values (default: "Yes")
- `false_text` (str): Text for False values (default: "No")
- `default` (bool): Default boolean value if conversion fails

**Returns:** Display text string

**Examples:**
```python
from utils.helpers import map_bool_display

map_bool_display(True)                  # "Yes"
map_bool_display(False)                 # "No"
map_bool_display("1")                   # "Yes"
map_bool_display(0)                     # "No"
map_bool_display(True, "✓", "✗")        # "✓"
map_bool_display(None)                  # "No"
```

**Usage in PDFs:** Commonly used in PDF generation to convert boolean fields to user-friendly text.

---

### Status Color Mapping

#### `get_status_color(status)`
Return Bootstrap color class for status values.

**Args:**
- `status` (str): Status value

**Returns:** Bootstrap color class string

**Status Mapping:**
| Status | Bootstrap Class | Visual Color |
|--------|----------------|--------------|
| pending | warning | Yellow |
| in_progress | info | Blue |
| completed | success | Green |
| cancelled | danger | Red |
| on_hold | secondary | Gray |
| (unknown) | secondary | Gray |

**Example:**
```python
from utils.helpers import get_status_color

get_status_color("completed")   # "success"
get_status_color("pending")     # "warning"
get_status_color("cancelled")   # "danger"
```

**Template Usage:**
```html
<span class="badge badge-{{ get_status_color(order.status) }}">
    {{ order.status }}
</span>
```

---

### Date Calculations

#### `calculate_days_since(date)`
Calculate days since a given date.

**Args:**
- `date`: Date object or YYYY-MM-DD string

**Returns:** Integer days since date, or None if date is None

**Example:**
```python
from utils.helpers import calculate_days_since
from datetime import date

calculate_days_since(date(2024, 1, 1))  # Days from Jan 1, 2024 to today
calculate_days_since("2024-01-01")      # Same as above
calculate_days_since(None)              # None
```

---

### Date Formatting and Sorting

#### `format_date_from_str(date_str)`
Parse date string from various formats. (Defined in helpers.py but primarily used via date_helpers module)

**Args:**
- `date_str` (str): Date string to parse

**Returns:** datetime object or None

**Supported Formats:**
- `MM/DD/YY HH:MM:SS` (legacy database format)
- `YYYY-MM-DD` (ISO format)

**Example:**
```python
from utils.helpers import format_date_from_str

format_date_from_str("12/31/23 14:30:00")  # datetime(2023, 12, 31, 14, 30, 0)
format_date_from_str("2024-01-15")         # datetime(2024, 1, 15, 0, 0, 0)
format_date_from_str(None)                 # None
```

#### `safe_date_sort_key(date_obj)`
Returns a sortable key for date objects, handling None values.

**Args:**
- `date_obj`: Date object, string, or None

**Returns:** Sortable date object (datetime.min for None values)

**Example:**
```python
from utils.helpers import safe_date_sort_key

orders = sorted(work_orders, key=lambda wo: safe_date_sort_key(wo.DateIn))
```

**Why This Exists:** Python's sorted() function fails when comparing None with date objects. This helper ensures None values sort to the beginning.

---

### Queue Management

#### `initialize_queue_positions_for_unassigned()`
Assign sequential queue positions to work orders that don't have one.

**Note:** This is a simplified version for testing. The production version with priority handling is in [routes/queue.py](../../routes/queue.py).

**Example:**
```python
from utils.helpers import initialize_queue_positions_for_unassigned

# Assign queue positions to all unassigned work orders
initialize_queue_positions_for_unassigned()
```

**Database Impact:** Commits changes directly to the database.

---

### File Upload Helpers

#### `allowed_file(filename)`
Check if uploaded file has allowed extension.

**Args:**
- `filename` (str): Filename to check

**Returns:** Boolean

**Allowed Extensions:** Configured in [extensions.py](../../extensions.py):
- Documents: `pdf`, `docx`, `txt`, `csv`, `xlsx`
- Images: `jpg`, `jpeg`, `png`

**Example:**
```python
from utils.helpers import allowed_file

allowed_file("invoice.pdf")     # True
allowed_file("photo.jpg")       # True
allowed_file("malware.exe")     # False
```

#### `save_uploaded_photo(form_photo, customer_id)`
Save uploaded photo with resizing and return filename.

**Args:**
- `form_photo`: Flask file upload object
- `customer_id`: Customer ID for folder organization

**Returns:** Tuple of (filename, file_path) or (None, None) if invalid

**Features:**
- Generates secure random filename
- Creates customer-specific directory
- Resizes images to max 1200x1200 pixels
- Validates file extension

**Example:**
```python
from utils.helpers import save_uploaded_photo

if 'photo' in request.files:
    filename, path = save_uploaded_photo(request.files['photo'], customer.CustID)
    if filename:
        customer.photo = filename
        db.session.commit()
```

---

### Pagination

#### `paginate_query(query, page, per_page=50)`
Helper function for SQLAlchemy query pagination.

**Args:**
- `query`: SQLAlchemy query object
- `page` (int): Page number (1-indexed)
- `per_page` (int): Results per page (default: 50)

**Returns:** Flask-SQLAlchemy pagination object

**Example:**
```python
from utils.helpers import paginate_query

query = WorkOrder.query.order_by(WorkOrder.DateIn.desc())
pagination = paginate_query(query, page=1, per_page=25)

for order in pagination.items:
    print(order.WorkOrderNo)
```

---

## Order Item Helpers

**Module:** `utils/order_item_helpers.py`

This module reduces code duplication in create/edit route handlers by providing reusable functions for processing work order and repair order items.

### Safe Value Conversions

#### `safe_int_conversion(value)`
Safely convert a value to integer, handling various input types.

**Args:**
- `value`: Value to convert (string, int, float, None, etc.)

**Returns:** Integer value (minimum 1)

**Examples:**
```python
from utils.order_item_helpers import safe_int_conversion

safe_int_conversion("5")        # 5
safe_int_conversion("3.7")      # 3
safe_int_conversion("")         # 1 (default)
safe_int_conversion(None)       # 1 (default)
safe_int_conversion("invalid")  # 1 (default)
```

**Use Cases:**
- Parsing quantity fields from forms
- Ensuring positive integer values
- Handling empty form fields

#### `safe_price_conversion(value)`
Safely convert a value to float for price fields.

**Args:**
- `value`: Value to convert (string, int, float, None, etc.)

**Returns:** Float value (minimum 0.0) or None if empty

**Examples:**
```python
from utils.order_item_helpers import safe_price_conversion

safe_price_conversion("125.50")     # 125.5
safe_price_conversion("$125.50")    # 125.5
safe_price_conversion("")           # None
safe_price_conversion(None)         # None
safe_price_conversion("invalid")    # None
```

**Note:** Returns None for empty values (unlike safe_int_conversion which defaults to 1). This allows database NULL values for optional price fields.

---

### Processing Inventory Items

#### `process_selected_inventory_items(form, order_no, cust_id, item_class)`
Process items selected from customer inventory catalog.

**Args:**
- `form`: Flask request.form object
- `order_no` (str): Work order or repair order number
- `cust_id` (str): Customer ID
- `item_class`: WorkOrderItem or RepairWorkOrderItem class

**Returns:** List of item instances (not yet added to session)

**Form Data Expected:**
- `selected_items[]`: List of inventory keys
- `item_qty_{inv_key}`: Quantity for each selected item

**Example:**
```python
from utils.order_item_helpers import process_selected_inventory_items
from models.work_order import WorkOrderItem

items = process_selected_inventory_items(
    request.form,
    next_wo_no,
    customer.CustID,
    WorkOrderItem
)

for item in items:
    db.session.add(item)

db.session.commit()
```

**How It Works:**
1. Reads `selected_items[]` array from form
2. Builds quantity map from `item_qty_*` fields
3. Queries Inventory table for each selected item
4. Creates WorkOrderItem/RepairWorkOrderItem instances
5. Sets `InventoryKey` field to track source inventory

---

### Processing New Items

#### `process_new_items(form, order_no, cust_id, item_class, update_catalog=True)`
Process manually added new items.

**Args:**
- `form`: Flask request.form object
- `order_no` (str): Work order or repair order number
- `cust_id` (str): Customer ID
- `item_class`: WorkOrderItem or RepairWorkOrderItem class
- `update_catalog` (bool): If True, add/update items in inventory catalog

**Returns:** Tuple of (items, catalog_updates)
- `items`: List of item instances (not yet added to session)
- `catalog_updates`: List of inventory items to add/update

**Form Data Expected:**
- `new_item_description[]`: Array of descriptions
- `new_item_material[]`: Array of materials
- `new_item_qty[]`: Array of quantities
- `new_item_condition[]`: Array of conditions
- `new_item_color[]`: Array of colors
- `new_item_size[]`: Array of sizes
- `new_item_price[]`: Array of prices

**Example:**
```python
from utils.order_item_helpers import process_new_items
from models.work_order import WorkOrderItem

items, catalog_updates = process_new_items(
    request.form,
    next_wo_no,
    customer.CustID,
    WorkOrderItem,
    update_catalog=True
)

# Add all items to session
for item in items:
    db.session.add(item)

for inv in catalog_updates:
    db.session.add(inv)

db.session.commit()
```

**Catalog Update Behavior:**
- If `update_catalog=True`, automatically calls `add_or_update_catalog()` for each new item
- Updates quantity if item with same attributes already exists in catalog
- Creates new catalog entry if item doesn't exist
- Displays flash messages to user about catalog changes

---

### Catalog Management

#### `add_or_update_catalog(cust_id, description, material, condition, color, size, price, qty)`
Add a new item to the inventory catalog or update existing quantity.

**Args:**
- `cust_id` (str): Customer ID
- `description` (str): Item description
- `material` (str): Material type
- `condition` (str): Item condition
- `color` (str): Item color
- `size` (str): Size/weight
- `price` (str/float): Price
- `qty` (int): Quantity to add

**Returns:** Inventory object (new or updated), or None if no action needed

**Example:**
```python
from utils.order_item_helpers import add_or_update_catalog

inv_item = add_or_update_catalog(
    cust_id="CUST001",
    description="Canvas Awning",
    material="Sunbrella",
    condition="Good",
    color="Blue",
    size="10x12",
    price="150.00",
    qty=1
)

if inv_item:
    db.session.add(inv_item)
    db.session.commit()
```

**Behavior:**
1. Searches for existing inventory item by customer + attributes
2. If found: Increments quantity (read-modify-write pattern - see note below)
3. If not found: Creates new inventory item with generated key

**Race Condition Note (Issue #95):**
The read-modify-write pattern at lines 281-283 is technically susceptible to race conditions, but this is safe for the awning business workflow because:
- Only one user works on a customer's orders at a time
- Low collision probability even with concurrent users
- Item specificity requires exact attribute match

**If workflow changes** to support concurrent editing, use atomic SQL update:
```python
db.session.execute(
    update(Inventory)
    .where(Inventory.InventoryKey == existing_inventory.InventoryKey)
    .values(Qty=Inventory.Qty + qty)
)
```

---

## Form Helpers

**Module:** `utils/form_helpers.py`

Provides reusable functions for extracting and validating form data, reducing code duplication in create/edit route handlers.

### Work Order Forms

#### `extract_work_order_fields(form)`
Extract all work order fields from form into dict.

**Args:**
- `form`: Flask request.form or dict-like object

**Returns:** Dict ready to pass to `WorkOrder(**data)`

**Raises:** ValueError for validation errors

**Example:**
```python
from utils.form_helpers import extract_work_order_fields

try:
    wo_data = extract_work_order_fields(request.form)
    work_order = WorkOrder(WorkOrderNo=next_wo_no, **wo_data)
    db.session.add(work_order)
    db.session.commit()
except ValueError as e:
    flash(str(e), 'error')
```

**Validation:**
- Requires `CustID`
- Requires `WOName`

**Boolean Fields:** Automatically handles checkbox conversion for:
- `RepairsNeeded`
- `RushOrder`
- `FirmRush`

**Date Fields:** Uses `parse_form_date()` for:
- `DateIn`
- `DateRequired`
- `Clean`
- `Treat`
- `DateCompleted`

---

### Repair Order Forms

#### `extract_repair_order_fields(form)`
Extract all repair order fields from form into dict.

**Args:**
- `form`: Flask request.form or dict-like object

**Returns:** Dict ready to pass to `RepairWorkOrder(**data)`

**Raises:** ValueError for validation errors

**Example:**
```python
from utils.form_helpers import extract_repair_order_fields

try:
    ro_data = extract_repair_order_fields(request.form)
    repair_order = RepairWorkOrder(RepairOrderNo=next_ro_no, **ro_data)
    db.session.add(repair_order)
    db.session.commit()
except ValueError as e:
    flash(str(e), 'error')
```

**Validation:**
- Requires `CustID`
- Requires `ROName`

**Boolean Fields:**
- `RushOrder`
- `FirmRush`

**Date Fields:**
- `DateIn`
- `DateRequired`
- `DateCompleted`

---

## Date Helpers

**Module:** `utils/date_helpers.py`

Provides reusable functions for parsing dates from forms and formatting dates for JSON API responses.

### Form Date Parsing

#### `parse_form_date(form, field_name, required=False, default=None)`
Parse date from form with consistent error handling.

**Args:**
- `form`: Flask request.form or dict-like object
- `field_name` (str): Name of the form field
- `required` (bool): If True, raises ValueError if field is missing
- `default`: Default value if field is empty (only used if not required)

**Returns:** date object or None (or default value)

**Raises:** ValueError if required and missing, or if date format is invalid

**Examples:**
```python
from utils.date_helpers import parse_form_date
from datetime import date

# With default
DateIn = parse_form_date(request.form, "DateIn", default=date.today())

# Optional field
DateRequired = parse_form_date(request.form, "DateRequired")

# Required field
try:
    DateCompleted = parse_form_date(request.form, "DateCompleted", required=True)
except ValueError as e:
    flash(str(e), 'error')
```

**Supported Input Types:**
- HTML date input: `YYYY-MM-DD` string
- Date objects (already parsed)
- Datetime objects (converts to date)
- Empty string or None (returns default)

---

### API Date Formatting

#### `format_date_for_api(date_value)`
Convert date/datetime to YYYY-MM-DD string for JSON API responses.

**Args:**
- `date_value`: date, datetime, or string

**Returns:** String in YYYY-MM-DD format, or None if input is None/empty

**Example:**
```python
from utils.date_helpers import format_date_for_api

response = {
    "DateIn": format_date_for_api(work_order.DateIn),
    "DateRequired": format_date_for_api(work_order.DateRequired),
}
return jsonify(response)
```

---

### Legacy Date Formatting

#### `format_date_from_str(value)`
Formats datetime or date string to YYYY-MM-DD format. Handles legacy database formats.

**Note:** This is a legacy function kept for backward compatibility. New code should use `format_date_for_api()` instead.

**Handles:**
- `MM/DD/YY HH:MM:SS` strings (legacy database format)
- datetime objects
- date objects
- YYYY-MM-DD strings (returns as-is)

---

## Data Processing

**Module:** `utils/data_processing.py`

Comprehensive data cleaning and parsing utilities for analytics dashboard, handling various formats with extensive edge case support.

### Currency Parsing

#### `clean_numeric_string(value)`
Clean currency strings to float.

**Args:**
- `value`: String, number, or None to clean

**Returns:** Float value, or 0.0 if invalid

**Supported Formats:**
```python
from utils.data_processing import clean_numeric_string

clean_numeric_string("$1,234.56")   # 1234.56
clean_numeric_string("1234.56")     # 1234.56
clean_numeric_string("Approved")    # 0.0
clean_numeric_string(None)          # 0.0
clean_numeric_string("")            # 0.0
```

---

### Sail Weight Parsing

#### `clean_sail_weight(value)`
Parse sail weight strings with pound notation.

**Args:**
- `value`: Sail weight string with # suffix

**Returns:** Float weight value, or 0.0 if invalid

**Examples:**
```python
from utils.data_processing import clean_sail_weight

clean_sail_weight("30#")    # 30.0
clean_sail_weight("45#")    # 45.0
clean_sail_weight("95#")    # 95.0
clean_sail_weight("")       # 0.0
clean_sail_weight(".")      # 0.0
```

---

### Square Footage Parsing

#### `clean_square_footage(value)`
Parse size strings from various formats into square footage.

**This is the most comprehensive parser in the system**, handling:

**Dimension Formats:**
- Simple: `"8x10"` → 80.0
- Feet/Inches: `"10'6\"x8'3\""` → 86.625
- Approximations: `"~10x6"` → 60.0

**Pre-calculated Values:**
- With equals: `"8x10=80'"` → 80.0 (uses calculated value)
- Complex: `"10'10x10'11=118.26'"` → 118.26

**Circular/Round:**
- `"4'8R=68.48'"` → 68.48
- `"7'R=153.86'"` → 153.86
- `"14' round=153.86'"` → 153.86

**Complex Expressions:**
- Multiple sections: `"10x5+2x3"` → 56.0 (sums sections)
- With modifiers: `"10x6-cutouts=55'"` → 55.0 (uses calculated)
- Wings: `"10'10x10'2-wings=120'"` → 120.0

**Other Formats:**
- Yardage: `"44 yds."` → 44.0
- Simple footage: `"25'"` → 25.0, `"318.13'"` → 318.13
- Each notation: `"16.00 ea."` → 16.0
- Sail weights: `"30#"` → 30.0
- Plain numbers: `"100"` → 100.0

**Invalid/Empty:**
- `""`, `"."`, `"na"`, `"*"`, `"?"` → 0.0

**Example:**
```python
from utils.data_processing import clean_square_footage

clean_square_footage("8x10")                      # 80.0
clean_square_footage("10'6\"x8'3\"")              # 86.625
clean_square_footage("10x6-cutouts=55'")          # 55.0
clean_square_footage("4'8R=68.48'")               # 68.48
clean_square_footage("30#")                       # 30.0
clean_square_footage("44 yds.")                   # 44.0
```

**Implementation Details:**
This function delegates to specialized parsers:
- `_parse_dimension_string()` - Handles x notation
- `_parse_circular_dimension()` - Handles R notation and "round"
- `_parse_yardage()` - Handles "yds" notation
- `_parse_simple_footage()` - Handles simple `'` notation
- `_feet_inches_to_feet()` - Converts feet/inches to decimal feet
- `_extract_calculated_value()` - Extracts pre-calculated values from `=` notation

---

### Product Type Identification

#### `identify_product_type(sizewgt)`
Identify whether an item is a Sail or Awning based on size/weight notation.

**Rules:**
- Contains `#` → "Sail"
- Otherwise → "Awning"

**Example:**
```python
from utils.data_processing import identify_product_type

identify_product_type("30#")        # "Sail"
identify_product_type("10x12")      # "Awning"
identify_product_type(None)         # "Awning"
```

---

### Work Order Item Processing

#### `parse_work_order_items(items_df, detect_outliers=True, outlier_threshold=8000.0, replace_with_mean=True)`
Process a DataFrame of work order items, parsing sizes and identifying product types.

**Args:**
- `items_df` (DataFrame): DataFrame with columns: workorderno, custid, qty, sizewgt, price
- `detect_outliers` (bool): Whether to detect and flag outliers (default: True)
- `outlier_threshold` (float): Square footage threshold for outlier detection (default: 8000.0)
- `replace_with_mean` (bool): Whether to replace outliers with mean (default: True)

**Returns:** DataFrame with additional computed columns:
- `price_numeric`: Cleaned price as float
- `product_type`: "Sail" or "Awning"
- `qty_numeric`: Cleaned quantity as float
- `sqft`: Total square footage (qty * parsed size) - **ONLY for Awnings**, 0.0 for Sails
- `is_outlier`: Boolean flag for extreme outliers

**Note on Sail Exclusion:**
Sails are identified by the presence of `#` in the sizewgt field and are **excluded from square footage calculations**. This prevents skewing analytics with sail weights.

**Outlier Detection:**
Automatically detects extreme outliers (default > 8000 sqft) which are likely data entry errors:
- Example: `"29x11319'"` should be `"29x11.319'"`
- Can optionally replace outliers with the mean value of similar-sized items

**Example:**
```python
from utils.data_processing import parse_work_order_items
import pandas as pd

items_df = pd.DataFrame({
    'workorderno': ['WO000001', 'WO000002'],
    'custid': ['CUST001', 'CUST002'],
    'qty': [1, 2],
    'sizewgt': ['10x12', '8x10'],
    'price': ['$150.00', '$120.00']
})

processed = parse_work_order_items(
    items_df,
    detect_outliers=True,
    outlier_threshold=10000.0
)

# Access computed columns
print(processed[['sqft', 'product_type', 'is_outlier']])
```

---

## File Upload

**Module:** `utils/file_upload.py`

Comprehensive file upload system with S3 integration, thumbnail generation, and deferred upload support to prevent orphaned S3 files.

### Configuration

**Environment Variables:**
- `AWS_S3_BUCKET`: S3 bucket name (required)
- `AWS_REGION`: AWS region (default: us-east-1)
- `AWS_ACCESS_KEY_ID`: Access key (local dev only)
- `AWS_SECRET_ACCESS_KEY`: Secret key (local dev only)

**Allowed Extensions:**
- Documents: `pdf`, `docx`, `txt`, `csv`, `xlsx`
- Images: `jpg`, `jpeg`, `png`

---

### Environment Detection

#### `is_running_on_aws()`
Detect if running in AWS environment.

**Returns:** Boolean

**Checks for:**
- `AWS_EXECUTION_ENV` environment variable
- `AWS_LAMBDA_FUNCTION_NAME` environment variable
- `AWS_REGION` environment variable
- `/var/app/current` directory (EB)
- `/opt/elasticbeanstalk` directory (EB)

**Why This Matters:**
- On AWS: Uses IAM role for S3 access (no credentials needed)
- Local: Uses explicit AWS credentials from environment variables

---

### Core Upload Functions

#### `save_order_file_generic(order_no, file, order_type="work_order", to_s3=True, generate_thumbnails=True, file_model_class=None, defer_s3_upload=False)`
Generic function to save order files (work orders or repair orders).

**Args:**
- `order_no` (str): The order number
- `file`: The file object to save
- `order_type` (str): "work_order" or "repair_order"
- `to_s3` (bool): Whether to save to S3 (True) or locally (False)
- `generate_thumbnails` (bool): Whether to generate thumbnails
- `file_model_class`: Model class (WorkOrderFile or RepairOrderFile)
- `defer_s3_upload` (bool): If True, stores file content in memory for upload after DB commit

**Returns:** File model instance (not committed to DB)

**Deferred Upload Feature:**
When `defer_s3_upload=True`, the function stores file content in memory and attaches temporary attributes to the file object:
- `_deferred_file_content`: The file bytes to upload
- `_deferred_s3_key`: The S3 key to upload to
- `_deferred_thumbnail_content`: Optional thumbnail bytes
- `_deferred_thumbnail_key`: Optional thumbnail S3 key

**Why Defer Uploads?**
Prevents orphaned S3 files when database commits fail. The workflow is:
1. Store file content in memory
2. Create database records
3. Commit database transaction
4. **Only if commit succeeds**, upload to S3
5. If commit fails, memory is cleaned up (no orphaned S3 files)

**Example (Immediate Upload):**
```python
from utils.file_upload import save_work_order_file

file_obj = save_work_order_file(
    work_order_no="WO000001",
    file=request.files['document'],
    to_s3=True,
    generate_thumbnails=True,
    defer_s3_upload=False  # Upload immediately (old behavior)
)

db.session.add(file_obj)
db.session.commit()
```

**Example (Deferred Upload - Recommended):**
```python
from utils.file_upload import save_work_order_file, commit_deferred_uploads, cleanup_deferred_files

# Step 1: Process files (stores in memory)
file_objects = []
for uploaded_file in request.files.getlist('documents'):
    file_obj = save_work_order_file(
        work_order_no="WO000001",
        file=uploaded_file,
        to_s3=True,
        generate_thumbnails=True,
        defer_s3_upload=True  # Defer upload until after DB commit
    )
    file_objects.append(file_obj)
    db.session.add(file_obj)

# Step 2: Try to commit DB changes
try:
    db.session.add(work_order)
    db.session.commit()

    # Step 3: DB commit succeeded, upload to S3
    success, uploaded, failed = commit_deferred_uploads(file_objects)
    if not success:
        flash("Some files failed to upload", "warning")

except Exception as e:
    db.session.rollback()

    # Step 4: DB commit failed, clean up memory (no S3 orphans!)
    cleanup_deferred_files(file_objects)
    flash(f"Error: {e}", "error")
```

---

### Wrapper Functions

#### `save_work_order_file(work_order_no, file, to_s3=True, generate_thumbnails=True, defer_s3_upload=False)`
Save work order file - wrapper around `save_order_file_generic()`.

#### `save_repair_order_file(repair_order_no, file, to_s3=True, generate_thumbnails=True, defer_s3_upload=False)`
Save repair order file - wrapper around `save_order_file_generic()`.

---

### Deferred Upload Management

#### `commit_deferred_uploads(file_objects)`
Upload files to S3 that were deferred until after DB commit.

**Args:**
- `file_objects` (list): List of file model objects with deferred upload data

**Returns:** Tuple of (success, uploaded_files, failed_files)
- `success` (bool): True if all uploads succeeded
- `uploaded_files` (list): List of successfully uploaded file objects
- `failed_files` (list): List of (file_obj, error_message) tuples

**Example:**
```python
success, uploaded, failed = commit_deferred_uploads(file_objects)

if not success:
    for file_obj, error in failed:
        print(f"Failed to upload {file_obj.filename}: {error}")
```

#### `cleanup_deferred_files(file_objects)`
Clean up memory for files that were staged for deferred upload but the transaction was rolled back.

**Args:**
- `file_objects` (list): List of file model objects with deferred upload data

**Purpose:** Prevents memory leaks by removing temporary attributes after rollback.

---

### File Utilities

#### `allowed_file(filename)`
Check if uploaded file has allowed extension.

#### `get_file_size(file_path)`
Get human-readable file size.

**Args:**
- `file_path` (str): S3 path (s3://...) or local path

**Returns:** Human-readable size string (e.g., "1.5 MB") or None if file not found

**Example:**
```python
from utils.file_upload import get_file_size

get_file_size("s3://my-bucket/file.pdf")     # "2.3 MB"
get_file_size("/path/to/local/file.pdf")     # "1.5 MB"
get_file_size("s3://my-bucket/missing.pdf")  # None
```

---

### Presigned URLs

#### `generate_presigned_url(file_path, expires_in=3600)`
Generate a pre-signed URL for S3 file access.

**Args:**
- `file_path` (str): Full S3 path (s3://bucket/key)
- `expires_in` (int): URL expiration in seconds (default: 3600 = 1 hour)

**Returns:** Pre-signed URL string

**Example:**
```python
from utils.file_upload import generate_presigned_url

url = generate_presigned_url("s3://my-bucket/file.pdf", expires_in=7200)
# User can access this URL for 2 hours
```

#### `generate_thumbnail_presigned_url(thumbnail_path, expires_in=3600)`
Generate presigned URL for thumbnail.

#### `get_file_with_thumbnail_urls(wo_file, expires_in=3600)`
Get file URLs including thumbnail for a WorkOrderFile object.

**Returns:** Dict with keys:
- `file`: The WorkOrderFile object
- `file_url`: Presigned URL or file path
- `thumbnail_url`: Presigned thumbnail URL or None
- `has_thumbnail`: Boolean

---

### S3 File Management

#### `delete_file_from_s3(file_path)`
Delete a file from S3 given its full s3:// path.

**Args:**
- `file_path` (str): Full S3 path (e.g., s3://bucket-name/path/to/file.jpg)

**Returns:** Boolean (True on success, False on failure)

**Example:**
```python
from utils.file_upload import delete_file_from_s3

# Delete file
success = delete_file_from_s3("s3://my-bucket/work_orders/WO000001/file.pdf")

# Also handles thumbnails
delete_file_from_s3("s3://my-bucket/work_orders/WO000001/thumbnails/file_thumb.jpg")
```

---

### ML Model Management

#### `save_ml_model(model, metadata, model_name="latest_model")`
Save a trained ML model and its metadata to S3.

**Args:**
- `model`: Trained model object (will be pickled)
- `metadata` (dict): Model metadata
- `model_name` (str): Model name (default: "latest_model")

**Returns:** Dict with keys:
- `model_path`: S3 path to model pickle
- `metadata_path`: S3 path to metadata JSON
- `saved_at`: Timestamp string

**Example:**
```python
from utils.file_upload import save_ml_model

metadata = {
    "mae": 2.5,
    "features": ["sqft", "rush_order"],
    "trained_on": "2024-01-15"
}

result = save_ml_model(model, metadata, "production_model_v2")
print(result["model_path"])  # s3://bucket/ml_models/production_model_v2.pkl
```

#### `load_ml_model(model_name="latest_model")`
Load a trained ML model and its metadata from S3.

**Returns:** Tuple of (model, metadata) or (None, None) if not found

#### `list_saved_models()`
List all saved models in S3.

**Returns:** List of dicts with keys: name, size, last_modified

#### `delete_ml_model(model_name)`
Delete a model and its metadata from S3.

---

## Cache Helpers

**Module:** `utils/cache_helpers.py`

Caching decorators and helper functions to optimize database queries and expensive computations.

### Cache Decorator

#### `@cached_query(timeout=300, key_prefix=None)`
Decorator to cache database query results.

**Args:**
- `timeout` (int): Cache timeout in seconds (default: 300 = 5 minutes)
- `key_prefix` (str): Optional custom cache key prefix

**Example:**
```python
from utils.cache_helpers import cached_query
from models.source import Source

@cached_query(timeout=600)  # Cache for 10 minutes
def get_all_sources():
    return Source.query.order_by(Source.SSource).all()

# First call: hits database
sources = get_all_sources()

# Second call within 10 minutes: returns cached result
sources = get_all_sources()
```

**Cache Key Generation:**
- Function name
- Arguments (positional and keyword)
- Key format: `query:function_name:arg1:arg2:key1=val1:key2=val2`

---

### Cache Invalidation

#### `invalidate_cache_pattern(pattern)`
Invalidate all cache keys matching a pattern.

**Args:**
- `pattern` (str): Pattern to match (e.g., "query:get_customer_*")

**Note:**
- For RedisCache (production), uses Redis SCAN to delete matching keys
- For SimpleCache (development), this is a no-op

#### `invalidate_customer_cache()`
Invalidate customer-related cache entries. Call when customer data is modified.

**Example:**
```python
from utils.cache_helpers import invalidate_customer_cache

# After updating customer
customer.CompanyName = "New Name"
db.session.commit()
invalidate_customer_cache()
```

#### `invalidate_source_cache()`
Invalidate source-related cache entries.

#### `invalidate_work_order_cache(work_order_no=None)`
Invalidate work order-related cache entries.

**Args:**
- `work_order_no` (str): Optional specific work order to invalidate

#### `invalidate_repair_order_cache(repair_order_no=None)`
Invalidate repair order-related cache entries.

#### `invalidate_analytics_cache()`
Invalidate analytics-related cache entries.

#### `clear_all_caches()`
Clear all application caches.

**Warning:** Use with caution - only in development or after major data migrations.

---

## PDF Helpers

**Module:** `utils/pdf_helpers.py`

For detailed PDF generation documentation, see [PDF Generation Guide](./pdf-generation.md).

## Thumbnail Generator

**Module:** `utils/thumbnail_generator.py`

### `generate_thumbnail(file_content, filename)`
Generate thumbnail from image file content.

### `save_thumbnail_to_s3(thumbnail_img, s3_client, bucket, s3_key)`
Save thumbnail to S3.

### `save_thumbnail_locally(thumbnail_img, file_path)`
Save thumbnail to local filesystem.

---

## Usage Patterns

### Common Import Pattern

```python
# General helpers
from utils.helpers import (
    format_phone_number,
    generate_work_order_number,
    safe_bool_convert,
    get_status_color
)

# Order item processing
from utils.order_item_helpers import (
    process_selected_inventory_items,
    process_new_items,
    safe_int_conversion,
    safe_price_conversion
)

# Form processing
from utils.form_helpers import (
    extract_work_order_fields,
    extract_repair_order_fields
)

# Date handling
from utils.date_helpers import (
    parse_form_date,
    format_date_for_api
)

# File uploads
from utils.file_upload import (
    save_work_order_file,
    commit_deferred_uploads,
    cleanup_deferred_files
)

# Caching
from utils.cache_helpers import (
    cached_query,
    invalidate_work_order_cache
)
```

### Complete Work Order Creation Example

```python
from flask import request, flash, redirect, url_for
from utils.helpers import generate_work_order_number
from utils.form_helpers import extract_work_order_fields
from utils.order_item_helpers import process_selected_inventory_items, process_new_items
from utils.file_upload import save_work_order_file, commit_deferred_uploads, cleanup_deferred_files
from models.work_order import WorkOrder, WorkOrderItem
from extensions import db

@work_orders_bp.route('/create', methods=['POST'])
def create_work_order():
    try:
        # Generate order number
        next_wo_no = generate_work_order_number()

        # Extract form fields
        wo_data = extract_work_order_fields(request.form)
        work_order = WorkOrder(WorkOrderNo=next_wo_no, **wo_data)

        # Process items from inventory
        items = process_selected_inventory_items(
            request.form,
            next_wo_no,
            wo_data['CustID'],
            WorkOrderItem
        )

        # Process new items
        new_items, catalog_updates = process_new_items(
            request.form,
            next_wo_no,
            wo_data['CustID'],
            WorkOrderItem,
            update_catalog=True
        )

        # Process file uploads (deferred)
        file_objects = []
        for uploaded_file in request.files.getlist('documents'):
            file_obj = save_work_order_file(
                work_order_no=next_wo_no,
                file=uploaded_file,
                to_s3=True,
                generate_thumbnails=True,
                defer_s3_upload=True  # Prevent S3 orphans
            )
            file_objects.append(file_obj)

        # Add everything to session
        db.session.add(work_order)
        for item in items + new_items:
            db.session.add(item)
        for inv in catalog_updates:
            db.session.add(inv)
        for file_obj in file_objects:
            db.session.add(file_obj)

        # Commit database changes
        db.session.commit()

        # Upload files to S3 (only after successful commit)
        success, uploaded, failed = commit_deferred_uploads(file_objects)
        if not success:
            flash("Some files failed to upload", "warning")

        flash(f"Work order {next_wo_no} created successfully", "success")
        return redirect(url_for('work_orders.view', work_order_no=next_wo_no))

    except ValueError as e:
        db.session.rollback()
        cleanup_deferred_files(file_objects)
        flash(str(e), 'error')
        return redirect(url_for('work_orders.create_form'))

    except Exception as e:
        db.session.rollback()
        cleanup_deferred_files(file_objects)
        flash(f"Error creating work order: {e}", 'error')
        return redirect(url_for('work_orders.create_form'))
```

---

## Best Practices

### Data Validation
1. **Always use safe conversion functions** (`safe_int_conversion`, `safe_price_conversion`) when processing form data
2. **Validate required fields** using form helper functions
3. **Handle exceptions** with try-except blocks and user-friendly error messages

### File Uploads
1. **Use deferred uploads** (`defer_s3_upload=True`) to prevent orphaned S3 files
2. **Always clean up** deferred files on rollback using `cleanup_deferred_files()`
3. **Check allowed file types** before processing uploads
4. **Generate thumbnails** for images to improve user experience

### Caching
1. **Cache expensive queries** using `@cached_query` decorator
2. **Invalidate caches** when data changes using appropriate `invalidate_*_cache()` functions
3. **Use appropriate timeouts** based on data volatility

### Date Handling
1. **Use `parse_form_date()`** for all form date fields
2. **Use `format_date_for_api()`** for JSON API responses
3. **Handle None values** gracefully with default parameters

### Error Handling
1. **Catch specific exceptions** (ValueError, KeyError, etc.)
2. **Provide user-friendly messages** via flash()
3. **Log errors** for debugging (use print() or logging module)
4. **Rollback transactions** on errors to maintain data integrity

---

## See Also

- [Forms and Validation](./forms-and-validation.md) - Detailed form handling patterns
- [File Uploads](./file-uploads.md) - Comprehensive file upload guide
- [Database Schema](./database-schema.md) - Database models and relationships
- [Testing](./testing.md) - Testing utility functions
- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
