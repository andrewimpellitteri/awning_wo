# Database Schema

Complete reference for the Awning Management System database schema.

## Overview

The application uses PostgreSQL with SQLAlchemy ORM. The schema is managed through Alembic migrations. See the [Alembic Guide](../database/ALEMBIC_GUIDE.md) for migration workflows.

**Key Characteristics:**
- **Database:** PostgreSQL 12+
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Naming:** Legacy Access DB naming (mixed case, some inconsistencies)

---

## Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌────────────┐
│   Source    │────┬────│   Customer   │────┬────│ WorkOrder  │
│  (Vendor)   │    │    │              │    │    │            │
└─────────────┘    │    └──────────────┘    │    └────────────┘
                   │            │            │           │
                   │            │            │           ├── WorkOrderItem
                   │            │            │           └── WorkOrderFile
                   │            │            │
                   │            │            └────┬────────────────┐
                   │            │                 │  RepairOrder   │
                   │            └─────────────────┤                │
                   │                              └────────────────┘
                   │                                       │
                   └───────────────────────────────────────┤
                                                          └── RepairOrderItem
                                                          └── RepairOrderFile

┌─────────────┐
│    User     │  (Flask-Login auth)
└─────────────┘

┌─────────────┐
│ InviteToken │  (User registration)
└─────────────┘

┌─────────────┐
│  Inventory  │  (Available items)
└─────────────┘
```

---

## Core Tables

### Customer (`tblcustomers`)

Customer information and contact details.

**Primary Key:** `custid` (Text)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `custid` | Text | Customer ID (Primary Key) |
| `name` | Text | Customer name |
| `contact` | Text | Contact person |
| `address` | Text | Physical address line 1 |
| `address2` | Text | Physical address line 2 |
| `city` | Text | City |
| `state` | Text | State |
| `zipcode` | Text | ZIP code |
| `homephone` | Text | Home phone number |
| `workphone` | Text | Work phone number |
| `cellphone` | Text | Cell phone number |
| `emailaddress` | Text | Email address |
| `mailaddress` | Text | Mailing address (if different) |
| `mailcity` | Text | Mailing city |
| `mailstate` | Text | Mailing state |
| `mailzip` | Text | Mailing ZIP |
| `sourceold` | Text | Legacy source field |
| `source` | Text | Source/vendor (FK → `tblsource.ssource`) |
| `sourceaddress` | Text | Source address |
| `sourcestate` | Text | Source state |
| `sourcecity` | Text | Source city |
| `sourcezip` | Text | Source ZIP |

#### Relationships
- **Has many:** WorkOrder (via `custid`)
- **Has many:** RepairWorkOrder (via `custid`)
- **Belongs to:** Source (via `source`)

#### Methods
- `to_dict()` - Convert to dictionary
- `clean_email()` - Remove `#mailto:` suffix
- `clean_phone(field)` - Format phone numbers
- `get_full_address()` - Formatted physical address
- `get_mailing_address()` - Formatted mailing address
- `get_primary_phone()` - First available phone number

**Model:** [models/customer.py](../../models/customer.py)

---

### WorkOrder (`tblcustworkorderdetail`)

Cleaning work orders.

**Primary Key:** `workorderno` (String)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `workorderno` | String | Work order number (Primary Key) |
| `custid` | String | Customer ID (FK → `tblcustomers.custid`) |
| `woname` | String | Work order name/title |
| `storage` | String | **DEPRECATED** - Do not use |
| `storagetime` | String | Storage duration: "Seasonal" or "Temporary" |
| `rack_number` | String | **Physical location** (e.g., "5 B", "bin 4 top") |
| `finallocation` | String | Location after cleaning is complete |
| `specialinstructions` | Text | Special instructions |
| `repairsneeded` | Boolean | Repairs needed flag |
| `returnstatus` | String | Return status |
| `datecompleted` | DateTime | Completion timestamp |
| `daterequired` | Date | Required by date |
| `datein` | Date | Date received |
| `clean` | Date | Date cleaned |
| `treat` | Date | Date treated |
| `quote` | String | Quote information |
| `rushorder` | Boolean | Rush order flag |
| `firmrush` | Boolean | Firm rush flag |
| `seerepair` | String | Related repair order reference |
| `shipto` | String | Ship to source (FK → `tblsource.ssource`) |
| `cleanfirstwo` | String | **DEPRECATED** - Historical only |
| `queueposition` | Integer | Position in cleaning queue |
| `processingstatus` | Boolean | Currently being processed |
| `source_name` | Text | **Denormalized** source name (for performance) |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

!!! warning "Storage Fields"
    See [Storage Fields Guide](../database/STORAGE_FIELDS_GUIDE.md) for detailed explanation of `storage`, `storagetime`, and `rack_number` fields.

#### Relationships
- **Belongs to:** Customer (via `custid`)
- **Belongs to:** Source (via `shipto` - ship to location)
- **Has many:** WorkOrderItem (child items)
- **Has many:** WorkOrderFile (attached files)

#### Properties
- `is_completed` - Boolean indicating completion status
- `total_items` - Count of order items
- `file_count` - Count of attached files

**Model:** [models/work_order.py](../../models/work_order.py)

---

### WorkOrderItem (`tblorddetcustawngs`)

Individual items within a work order.

**Primary Key:** `itemid` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `itemid` | Integer | Item ID (Primary Key) |
| `workorderno` | String | Work order number (FK → `tblcustworkorderdetail.workorderno`) |
| `sizewgt` | String | Size/weight description (e.g., "8'x10'", "95#") |
| `price` | Numeric | Item price |
| `qty` | String | Quantity (may contain non-numeric values) |
| `desc` | Text | Item description |
| `location` | String | Item-specific location |

#### Item Types

The `sizewgt` field determines the item type:
- **Awning:** Contains dimensions (e.g., "8'x10'", "12'6"x15'3"")
- **Sail:** Contains weight with `#` (e.g., "95#", "120#")

**Model:** [models/work_order.py](../../models/work_order.py) (WorkOrderItem class)

---

### RepairWorkOrder (`tblrepairworkorderdetail`)

Repair work orders.

**Primary Key:** `repairorderno` (String)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `repairorderno` | String | Repair order number (Primary Key) |
| `custid` | String | Customer ID (FK → `tblcustomers.custid`) |
| `roname` | String | Repair order name/title |
| `source` | String | Source field (not FK) |
| `WO DATE` | Date | Work order date ⚠️ **Uppercase with space** |
| `DATE TO SUB` | Date | Date to subcontractor ⚠️ **Uppercase with spaces** |
| `daterequired` | Date | Required by date |
| `datecompleted` | DateTime | Completion timestamp |
| `returndate` | Date | Return date |
| `dateout` | Date | Date sent out |
| `datein` | Date | Date received |
| `rushorder` | Boolean | Rush order flag |
| `firmrush` | Boolean | Firm rush flag |
| `quote` | Boolean | Quote flag |
| `approved` | Boolean | Approved flag |
| `clean` | Boolean | Clean before repair |
| `cleanfirst` | Boolean | **DEPRECATED** - Historical only |
| `QUOTE  BY` | String | Quoted by ⚠️ **Two spaces** |
| `RACK#` | String | **Physical location** (e.g., "hang 4", "6D") |
| `storage` | String | Storage duration: "TEMPORARY" or "SEASONAL" |
| `location` | String | Additional location details |
| `finallocation` | String | Location after repair is complete |
| `ITEM TYPE` | String | Item type ⚠️ **Uppercase with space** |
| `TYPE OF REPAIR` | String | Repair type ⚠️ **Uppercase with spaces** |
| `specialinstructions` | Text | Special instructions |
| `seeclean` | String | Related work order reference |
| `repairsdoneby` | String | Repair technician |
| `materiallist` | Text | Materials used |
| `customerprice` | String | Price quoted to customer |
| `returnstatus` | String | Return status |
| `source_name` | Text | **Denormalized** source name (for performance) |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

!!! warning "Column Name Quirks"
    Some columns have uppercase names or spaces: `WO DATE`, `DATE TO SUB`, `RACK#`, `QUOTE  BY`, `ITEM TYPE`, `TYPE OF REPAIR`.

#### Relationships
- **Belongs to:** Customer (via `custid`)
- **Has many:** RepairOrderItem (child items)
- **Has many:** RepairOrderFile (attached files)

**Model:** [models/repair_order.py](../../models/repair_order.py)

---

### Source (`tblsource`)

Vendors, sail lofts, and source organizations.

**Primary Key:** `ssource` (Text)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `ssource` | Text | Source identifier (Primary Key) |
| `name` | Text | Source name |
| `contact` | Text | Contact person |
| `address` | Text | Address |
| `city` | Text | City |
| `state` | Text | State |
| `zip` | Text | ZIP code |
| `phone` | Text | Phone number |
| `email` | Text | Email address |

#### Relationships
- **Has many:** Customer (via `source`)
- **Has many:** WorkOrder (via `shipto`)

**Model:** [models/source.py](../../models/source.py)

---

### Inventory (`tblinventory`)

Inventory items available for use.

**Primary Key:** `invid` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `invid` | Integer | Inventory ID (Primary Key) |
| `custid` | String | Customer ID (optional, for customer-specific items) |
| `description` | Text | Item description |
| `size` | String | Size/dimensions |
| `quantity` | Integer | Quantity available |
| `location` | String | Storage location |
| `notes` | Text | Additional notes |

**Model:** [models/inventory.py](../../models/inventory.py)

---

## File Attachments

### WorkOrderFile (`work_order_files`)

Files attached to work orders.

**Primary Key:** `id` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | File ID (Primary Key) |
| `work_order_no` | String | Work order number (FK → `tblcustworkorderdetail.workorderno`) |
| `file_name` | String | Original filename |
| `s3_key` | String | S3 object key |
| `file_size` | Integer | File size in bytes |
| `content_type` | String | MIME type |
| `uploaded_at` | DateTime | Upload timestamp |

#### Relationships
- **Belongs to:** WorkOrder (via `work_order_no`)

**Storage:** AWS S3 bucket

**Model:** [models/work_order_file.py](../../models/work_order_file.py)

---

### RepairOrderFile (`repair_order_files`)

Files attached to repair orders.

**Primary Key:** `id` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | File ID (Primary Key) |
| `repair_order_no` | String | Repair order number (FK → `tblrepairworkorderdetail.repairorderno`) |
| `file_name` | String | Original filename |
| `s3_key` | String | S3 object key |
| `file_size` | Integer | File size in bytes |
| `content_type` | String | MIME type |
| `uploaded_at` | DateTime | Upload timestamp |

#### Relationships
- **Belongs to:** RepairWorkOrder (via `repair_order_no`)

**Storage:** AWS S3 bucket

**Model:** [models/repair_order_file.py](../../models/repair_order_file.py)

---

## Authentication & Users

### User (`users`)

Application users for Flask-Login authentication.

**Primary Key:** `id` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | User ID (Primary Key) |
| `username` | String(80) | Username (unique) |
| `password_hash` | String(255) | Bcrypt password hash |
| `role` | String(20) | User role: "admin" or "user" |
| `created_at` | DateTime | Account creation timestamp |

#### Methods
- `set_password(password)` - Hash and set password
- `check_password(password)` - Verify password
- `is_admin()` - Check if user has admin role

**Model:** [models/user.py](../../models/user.py)

---

### InviteToken (`invite_tokens`)

Invitation tokens for user registration.

**Primary Key:** `id` (Integer, auto-increment)

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Token ID (Primary Key) |
| `token` | String(100) | Invite token (unique, indexed) |
| `role` | String(20) | Role to assign: "admin" or "user" |
| `used` | Boolean | Token used flag |
| `created_at` | DateTime | Token creation timestamp |
| `used_at` | DateTime | Token usage timestamp |

**Model:** [models/invite_token.py](../../models/invite_token.py)

---

## Indexes

Key indexes for performance optimization:

### Work Orders
- `idx_workorder_custid` on `custid` (foreign key)
- `idx_workorder_source_name` on `source_name` (denormalized field for filtering)
- `idx_workorder_datecompleted` on `datecompleted` (filtering completed orders)
- `idx_workorder_datein` on `datein` (filtering by intake date)

### Repair Orders
- `idx_repairorder_custid` on `custid` (foreign key)
- `idx_repairorder_source_name` on `source_name` (denormalized field for filtering)
- `idx_repairorder_datecompleted` on `datecompleted` (filtering completed orders)

### Customers
- `idx_customer_source` on `source` (foreign key)
- `idx_customer_name` on `name` (searching by name)

### Files
- `idx_workorderfile_work_order_no` on `work_order_no` (foreign key)
- `idx_repairorderfile_repair_order_no` on `repair_order_no` (foreign key)

---

## Performance Optimizations

### Denormalization

The `source_name` field is denormalized in both `WorkOrder` and `RepairWorkOrder` tables:

**Purpose:** Avoid expensive 3-table joins when filtering/sorting by source
**Synced via:** Database triggers and application-level sync methods
**Performance gain:** ~100x faster for source filtering queries

See [Denormalization Analysis](../planning/DENORMALIZATION_ANALYSIS.md) for details.

### Lazy Loading

Relationships use strategic lazy loading:
- `lazy='dynamic'` for large collections (e.g., customer → work_orders)
- `lazy='joined'` for frequently accessed relationships (e.g., work_order → files)
- Default `lazy='select'` for most relationships

---

## Data Types

### Date/DateTime Handling

- **Date:** Used for calendar dates (no time component)
  - Examples: `datein`, `daterequired`, `clean`, `treat`
- **DateTime:** Used when time matters
  - Examples: `datecompleted`, `created_at`, `updated_at`

### Boolean Fields

- Stored as PostgreSQL `BOOLEAN` type
- Python: `True`/`False`
- Database: `true`/`false`
- Legacy data may contain: "YES"/"NO", "TRUE"/"FALSE", 1/0

### Numeric Fields

- **Prices:** `Numeric` type (precise decimal)
- **Quantities:** Often stored as `String` (may contain non-numeric values like "TBD")
- **IDs:** Auto-increment integers or string-based custom IDs

---

## Common Queries

### Get all pending work orders for a customer

```python
pending_orders = WorkOrder.query.filter_by(
    CustID=customer_id,
    DateCompleted=None
).order_by(WorkOrder.DateIn.desc()).all()
```

### Get work orders with source name (denormalized)

```python
work_orders = WorkOrder.query.filter(
    WorkOrder.source_name == 'Boat Covers Inc'
).all()
```

### Get customer with all relationships

```python
customer = Customer.query.options(
    joinedload(Customer.work_orders),
    joinedload(Customer.repair_work_orders),
    joinedload(Customer.source_info)
).get(customer_id)
```

---

## Schema Changes

All schema changes must go through Alembic migrations. See the [Alembic Guide](../database/ALEMBIC_GUIDE.md) for the workflow.

### Adding a Column

```python
# Create migration
./alembic_db.sh test revision --autogenerate -m "add_new_column"

# Review and apply
./alembic_db.sh test upgrade head
./alembic_db.sh prod upgrade head
```

### Renaming a Column

```python
# Create migration manually
./alembic_db.sh test revision -m "rename_column"

# Edit migration file
def upgrade():
    op.alter_column('table_name', 'old_name', new_column_name='new_name')
```

---

## Legacy Database Notes

This database was migrated from Microsoft Access, which explains some quirks:

- **Mixed case column names** (e.g., `CustID`, `workorderno`)
- **Spaces in column names** (e.g., `WO DATE`, `TYPE OF REPAIR`)
- **Inconsistent naming** (some camelCase, some lowercase, some UPPERCASE)
- **Multiple spaces** in names (e.g., `QUOTE  BY` has two spaces)
- **Deprecated fields** left for historical data compatibility

When working with the schema, always check the exact column name in the model definition.

---

## ER Diagram - Detailed

```
┌────────────────────────────────────────────┐
│              tblcustomers                  │
│────────────────────────────────────────────│
│ PK custid         TEXT                     │
│    name           TEXT                     │
│    contact        TEXT                     │
│    address        TEXT                     │
│    city, state, zipcode                    │
│    homephone, workphone, cellphone         │
│    emailaddress   TEXT                     │
│ FK source         TEXT  → tblsource        │
└────────────────────────────────────────────┘
          │                           │
          │ 1                       1 │
          │                           │
          │ N                       N │
          ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ tblcustworkorder... │     │ tblrepairworkorder..│
│─────────────────────│     │─────────────────────│
│ PK workorderno      │     │ PK repairorderno    │
│ FK custid           │     │ FK custid           │
│    woname           │     │    roname           │
│    rack_number      │     │    RACK#            │
│    storagetime      │     │    storage          │
│    datein, dateout  │     │    datein, dateout  │
│    source_name      │     │    source_name      │
│    ...              │     │    ...              │
└─────────────────────┘     └─────────────────────┘
          │                           │
          │ 1                       1 │
          │                           │
          │ N                       N │
          ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│  tblorddetcust...   │     │ repair_order_items  │
│─────────────────────│     │─────────────────────│
│ PK itemid           │     │ PK id               │
│ FK workorderno      │     │ FK repairorderno    │
│    sizewgt          │     │    description      │
│    price, qty       │     │    price, qty       │
└─────────────────────┘     └─────────────────────┘

          │ 1                       1 │
          │ N                       N │
          ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ work_order_files    │     │ repair_order_files  │
│─────────────────────│     │─────────────────────│
│ PK id               │     │ PK id               │
│ FK work_order_no    │     │ FK repair_order_no  │
│    s3_key           │     │    s3_key           │
│    file_name        │     │    file_name        │
└─────────────────────┘     └─────────────────────┘

┌────────────────────────────────────────────┐
│              tblsource                     │
│────────────────────────────────────────────│
│ PK ssource        TEXT                     │
│    name           TEXT                     │
│    contact        TEXT                     │
│    address        TEXT                     │
│    phone, email   TEXT                     │
└────────────────────────────────────────────┘
```

---

## See Also

- [Alembic Migration Guide](../database/ALEMBIC_GUIDE.md) - Database migrations
- [Storage Fields Guide](../database/STORAGE_FIELDS_GUIDE.md) - Understanding storage/location fields
- [API Reference](api-reference.md) - API endpoints
- [Performance Analysis](../architecture/PERFORMANCE_ANALYSIS.md) - Query optimization
- [Denormalization Analysis](../planning/DENORMALIZATION_ANALYSIS.md) - Performance improvements
