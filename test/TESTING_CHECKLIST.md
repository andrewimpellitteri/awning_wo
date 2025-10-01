# Testing Checklist - Awning Work Order System

**Last Updated:** 2025-09-30
**Current Coverage Status:** Models ✅ | Routes ⚠️ | Utils ❌ | Integration ❌

---

## Current Test Status

### ✅ **COMPLETED**
- [x] User Model (test_models.py)
- [x] Customer Model (test_models.py)
- [x] Inventory Model (test_models.py)
- [x] InviteToken Model (test_models.py)
- [x] RepairWorkOrder Model (test_models.py)
- [x] RepairWorkOrderItem Model (test_models.py)
- [x] Source Model (test_models.py)
- [x] WorkOrder Model (test_models.py)
- [x] WorkOrderItem Model (test_models.py)
- [x] WorkOrderFile Model (test_models.py)
- [x] Basic setup tests (test_basic_setup.py)
- [x] Configuration tests (test_config.py)
- [x] Work order logic tests - partial (work_order_test.py)

---

## 🔴 HIGH PRIORITY - SECURITY & CORE BUSINESS LOGIC

### 1. Authentication Routes Tests (`routes/auth.py`)
**File to create:** `test/test_auth.py`

- [x] **Login Tests**
  - [x] POST /login with valid credentials - should succeed
  - [x] POST /login with invalid username - should fail
  - [x] POST /login with invalid password - should fail
  - [x] POST /login when already authenticated - should redirect
  - [x] GET /login - should render login page
  - [x] Login flash messages display correctly

- [x] **Logout Tests**
  - [x] GET /logout - should clear session
  - [x] GET /logout - should redirect to login
  - [x] Logout flash message displays

- [x] **Registration Tests**
  - [x] POST /register with valid invite token - should succeed
  - [x] POST /register with invalid token - should fail
  - [x] POST /register with used token - should fail
  - [x] POST /register with duplicate username - should fail
  - [x] POST /register with duplicate email - should fail
  - [x] POST /register marks token as used
  - [x] GET /register - should render registration form
  - [x] Registration with missing required fields - should fail

**Why Important:** Authentication is the gateway to the system. Without proper testing, unauthorized access is possible.

---

### 2. Authorization Decorator Tests (`decorators.py`)
**File to create:** `test/test_decorators.py`

- [x] **Role-Based Access Control**
  - [x] @role_required("admin") - allows admin users
  - [x] @role_required("admin") - blocks non-admin users (403)
  - [x] @role_required("admin") - redirects unauthenticated users
  - [x] @role_required("manager") - allows manager users
  - [x] @role_required("admin", "manager") - allows either role
  - [x] Multiple roles - blocks regular users
  - [x] Flash messages for unauthorized access

**Why Important:** Prevents privilege escalation and unauthorized access to admin/manager functions.

---

### 3. Work Orders CRUD Tests (`routes/work_orders.py`)
**File to create:** `test/test_work_orders_routes.py`

- [x] **List & Search**
  - [x] GET /work_orders/ - renders list page
  - [x] Search by WorkOrderNo - returns correct results
  - [x] Search by CustID - returns correct results
  - [x] Search by WOName - returns correct results
  - [x] Search by Storage - returns correct results
  - [x] Search by RackNo - returns correct results
  - [x] Search by ShipTo - returns correct results
  - [x] Pagination works correctly
  - [x] Empty search returns all orders

- [x] **View Detail**
  - [x] GET /work_orders/<no> - displays order details
  - [x] View includes customer information
  - [x] View includes all work order items
  - [x] View handles missing work order (404)

- [x] **Create Work Order**
  - [x] GET /work_orders/new - renders creation form
  - [x] POST /work_orders/new - creates work order successfully
  - [x] Auto-generates WorkOrderNo sequentially
  - [x] Creates work order with selected inventory items
  - [x] Creates work order with new items
  - [x] Creates work order with mixed items (inventory + new)
  - [x] Validates required fields (CustID)
  - [x] Assigns initial queue position
  - [x] Redirects to work order detail after creation

- [x] **Edit Work Order**
  - [x] GET /work_orders/<no>/edit - renders edit form
  - [x] POST /work_orders/<no>/edit - updates work order
  - [x] Updates work order fields correctly
  - [x] Updates existing items
  - [x] Adds new items during edit
  - [x] Deletes items during edit
  - [x] Handles DateCompleted changes

- [x] **Delete Work Order**
  - [x] POST /work_orders/<no>/delete - deletes work order
  - [x] Deletes associated items (cascade)
  - [x] Deletes associated files
  - [x] Confirms deletion with flash message
  - [x] Handles missing work order (404)

- [x] **File Operations**
  - [x] POST /work_orders/<no>/files/upload - uploads file
  - [x] Upload validates file type
  - [x] Upload validates file size
  - [x] GET /work_orders/<no>/files/<id>/download - downloads file
  - [x] Download from local storage works
  - [x] Download from S3 works
  - [x] GET /work_orders/thumbnail/<id> - generates thumbnail
  - [x] GET /work_orders/<no>/files - lists files (API)
  - [x] File deletion works

- [x] **PDF Generation**
  - [x] GET /work_orders/<no>/pdf - generates PDF
  - [x] PDF contains work order details
  - [x] PDF contains item list
  - [x] PDF contains customer information

**Why Important:** Work orders are the core business entity. All CRUD operations must work flawlessly.

---

### 4. Repair Orders CRUD Tests (`routes/repair_order.py`)
**File to create:** `test/test_repair_orders_routes.py`

- [x] **List & Filter**
  - [x] GET /repair_work_orders/ - renders list page
  - [x] GET /repair_work_orders/api/repair_work_orders - API endpoint works
  - [x] Filter by status (pending, completed, rush)
  - [x] Global search across all fields
  - [x] Filter by RepairOrderNo
  - [x] Filter by CustID
  - [x] Filter by ROName
  - [x] Filter by Source
  - [x] Sort by RepairOrderNo (numeric)
  - [x] Sort by dates with multiple format handling
  - [x] Pagination works correctly

- [x] **View Detail**
  - [x] GET /repair_work_orders/<no> - displays repair order
  - [x] View includes customer information
  - [x] View includes all repair items
  - [x] View handles missing repair order (404)

- [x] **Create Repair Order**
  - [x] Auto-generates RepairOrderNo sequentially
  - [x] Creates repair order with items
  - [x] Validates required fields
  - [x] Redirects after creation

- [x] **Edit Repair Order**
  - [x] Updates repair order fields
  - [x] Updates repair items
  - [x] Adds new items
  - [x] Deletes items

- [x] **Delete Repair Order**
  - [x] Deletes repair order and items
  - [x] Handles missing repair order (404)

- [x] **PDF Generation**
  - [x] Generates repair order PDF
  - [x] PDF contains repair details

- [x] **Date Formatting**
  - [x] format_date_from_str() handles MM/DD/YY HH:MM:SS
  - [x] format_date_from_str() handles YYYY-MM-DD
  - [x] format_date_from_str() handles None/empty

**Why Important:** Repair orders are a separate critical workflow with complex date handling.

---

### 5. Customer Management Tests (`routes/customers.py`)
**File to create:** `test/test_customers_routes.py`

- [x] **List & Filter**
  - [x] GET /customers/ - renders list page
  - [x] GET /customers/api/customers - API endpoint with pagination
  - [x] Search across multiple fields
  - [x] Filter by source
  - [x] Filter by state
  - [x] Column-specific filters work
  - [x] Sorting works (Tabulator format)
  - [x] Pagination works

- [x] **View Detail**
  - [x] GET /customers/view/<id> - displays customer
  - [x] Shows all work orders for customer
  - [x] Shows all repair orders for customer
  - [x] Shows all inventory for customer
  - [x] Handles missing customer (404)

- [x] **Create Customer**
  - [x] GET /customers/new - renders form
  - [x] POST /customers/new - creates customer
  - [x] Auto-generates CustID sequentially
  - [x] Auto-populates source address when source selected
  - [x] Validates name is required
  - [x] Redirects after creation

- [x] **Edit Customer**
  - [x] GET /customers/edit/<id> - renders form
  - [x] POST /customers/edit/<id> - updates customer
  - [x] All fields update correctly

- [x] **Delete Customer**
  - [x] POST /customers/delete/<id> - deletes customer
  - [x] Handles foreign key constraints
  - [x] Flash message on success

- [x] **API Endpoints**
  - [x] GET /customers/api/source_info/<name> - returns source info
  - [x] Source info includes address fields

- [x] **Authorization**
  - [x] Manager/admin can create/edit/delete
  - [x] Regular users cannot modify (403)

**Why Important:** Customers are central to the business. Auto-ID generation and data integrity must work correctly.

---

### 6. Queue Management Tests (`routes/queue.py`)
**File to create:** `test/test_queue_routes.py`

- [ ] **Queue Display**
  - [ ] GET /cleaning_queue/cleaning-queue - renders queue page
  - [ ] Orders sorted by priority (firm rush > rush > regular)
  - [ ] Within priority, sorted by date
  - [ ] Unassigned orders get initialized to end of queue
  - [ ] Search functionality works
  - [ ] Pagination works
  - [ ] Sail order filtering works

- [ ] **Queue Operations**
  - [ ] POST /cleaning_queue/api/cleaning-queue/reorder - reorders queue
  - [ ] Reorder updates queue_position for all orders
  - [ ] Reorder persists to database
  - [ ] GET /cleaning_queue/api/cleaning-queue/summary - returns summary
  - [ ] POST /cleaning_queue/api/cleaning-queue/initialize - initializes positions
  - [ ] POST /cleaning_queue/api/cleaning-queue/reset - resets all positions

- [ ] **Utility Functions**
  - [ ] safe_date_sort_key() handles None dates
  - [ ] safe_date_sort_key() handles datetime objects
  - [ ] safe_date_sort_key() handles string dates
  - [ ] initialize_queue_positions_for_unassigned() assigns correct positions

- [ ] **Authorization**
  - [ ] Manager/admin can reorder
  - [ ] Regular users cannot reorder (403)

**Why Important:** Queue management controls workflow. Priority sorting and position persistence are critical.

---

### 7. File Upload/Download Tests
**File to create:** `test/test_file_operations.py`

- [ ] **File Upload (utils/file_upload.py)**
  - [ ] save_work_order_file() saves to S3 when configured
  - [ ] save_work_order_file() saves to local storage when S3 unavailable
  - [ ] File type validation (allowed extensions)
  - [ ] File size limits enforced
  - [ ] Generates unique filenames
  - [ ] Creates work_order_files database record

- [ ] **File Download**
  - [ ] generate_presigned_url() creates valid S3 URL
  - [ ] Download from local storage works
  - [ ] Handles missing files gracefully

- [ ] **File Security**
  - [ ] Rejects disallowed file types
  - [ ] Rejects oversized files
  - [ ] Path traversal prevention
  - [ ] S3 bucket access control

- [ ] **Thumbnail Generation (utils/thumbnail_generator.py)**
  - [ ] Generates thumbnails for images
  - [ ] Respects size constraints
  - [ ] Handles invalid images gracefully

**Why Important:** File handling must be secure and reliable. Data loss or unauthorized access is unacceptable.

---

### 8. PDF Generation Tests
**File to create:** `test/test_pdf_generation.py`

- [ ] **Work Order PDF (work_order_pdf.py)**
  - [ ] generate_work_order_pdf() creates valid PDF
  - [ ] PDF contains work order number
  - [ ] PDF contains customer name and address
  - [ ] PDF contains all work order items
  - [ ] PDF contains dates (DateIn, DateRequired, DateCompleted)
  - [ ] PDF contains special instructions
  - [ ] PDF is valid binary content
  - [ ] Handles missing optional fields

- [ ] **Repair Order PDF (repair_order_pdf.py)**
  - [ ] generate_repair_order_pdf() creates valid PDF
  - [ ] PDF contains repair order details
  - [ ] PDF contains customer information
  - [ ] PDF contains repair items
  - [ ] PDF is valid binary content

**Why Important:** PDFs are customer-facing documents. They must be accurate and professional.

---

## 🟡 MEDIUM PRIORITY - IMPORTANT FEATURES

### 9. Inventory Management Tests (`routes/inventory.py`)
**File to create:** `test/test_inventory_routes.py`

- [ ] **List & Search**
  - [ ] GET /inventory/ - renders list page
  - [ ] Search functionality works
  - [ ] Pagination works
  - [ ] GET /inventory/api/search - API search works
  - [ ] GET /inventory/api/customer/<id> - returns customer inventory

- [ ] **CRUD Operations**
  - [ ] GET /inventory/view/<key> - displays inventory detail
  - [ ] GET /inventory/new - renders creation form
  - [ ] POST /inventory/new - creates inventory item
  - [ ] Validates required fields
  - [ ] GET /inventory/edit/<key> - renders edit form
  - [ ] POST /inventory/edit/<key> - updates inventory
  - [ ] POST /inventory/delete/<key> - deletes inventory

- [ ] **AJAX Operations**
  - [ ] POST /inventory/add_ajax - adds item via AJAX
  - [ ] POST /inventory/edit_ajax/<key> - edits via AJAX
  - [ ] POST /inventory/delete_ajax/<key> - deletes via AJAX
  - [ ] POST /inventory/api/bulk_update - bulk quantity updates

- [ ] **Authorization**
  - [ ] Manager/admin can create/edit/delete
  - [ ] Regular users cannot modify (403)

**Why Important:** Inventory is referenced by work orders. Data integrity is critical.

---

### 10. Source Management Tests (`routes/source.py`)
**File to create:** `test/test_source_routes.py`

- [ ] **List & Filter**
  - [ ] GET /sources/ - renders list page
  - [ ] Search functionality works
  - [ ] State filtering works
  - [ ] Pagination works

- [ ] **CRUD Operations**
  - [ ] GET /sources/view/<name> - displays source detail
  - [ ] GET /sources/new - renders creation form
  - [ ] POST /sources/new - creates source
  - [ ] Validates required fields (name)
  - [ ] Prevents duplicate source names
  - [ ] GET /sources/edit/<name> - renders edit form
  - [ ] POST /sources/edit/<name> - updates source
  - [ ] POST /sources/delete/<name> - deletes source

- [ ] **API Endpoints**
  - [ ] GET /sources/api/search - API search works
  - [ ] GET /sources/api/states - returns unique states

- [ ] **Authorization**
  - [ ] Manager/admin can create/edit/delete
  - [ ] Regular users cannot modify (403)

**Why Important:** Sources are referenced by customers. Duplicate prevention and referential integrity matter.

---

### 11. Analytics Tests (`routes/analytics.py`)
**File to create:** `test/test_analytics_routes.py`

- [ ] **Dashboard**
  - [ ] GET /analytics/ - renders dashboard
  - [ ] GET /analytics/api/data - returns chart data
  - [ ] Manager/admin only (403 for regular users)

- [ ] **Data Loading**
  - [ ] load_work_orders() loads all completed orders
  - [ ] Filters out pending orders
  - [ ] Includes customer and source joins

- [ ] **Data Cleaning**
  - [ ] clean_numeric_string() parses $1,234.56 correctly
  - [ ] clean_numeric_string() handles None/empty
  - [ ] clean_square_footage() parses "8x10" → 80
  - [ ] clean_square_footage() parses "8'9"x10'2"" correctly
  - [ ] clean_square_footage() handles invalid formats
  - [ ] clean_sail_weight() parses "95#" → 95
  - [ ] clean_sail_weight() handles None/empty

- [ ] **Calculations**
  - [ ] calculate_kpis() computes total revenue correctly
  - [ ] calculate_kpis() computes average order value
  - [ ] calculate_kpis() computes order count
  - [ ] get_monthly_trends() groups by month
  - [ ] get_daily_throughput() calculates daily metrics
  - [ ] get_daily_throughput() calculates 7-day rolling average
  - [ ] get_backlog_data() counts pending vs completed
  - [ ] get_status_distribution() groups by status

**Why Important:** Analytics drive business decisions. Calculations must be accurate.

---

### 12. ML/Prediction Tests (`routes/ml.py`)
**File to create:** `test/test_ml_routes.py`

- [ ] **Data Loading & Preprocessing**
  - [ ] MLService.load_work_orders() loads data from database
  - [ ] MLService.convert_to_binary() converts Yes/No/Unknown correctly
  - [ ] MLService.convert_to_numeric() converts numeric strings
  - [ ] MLService.preprocess_data() handles missing values
  - [ ] MLService.engineer_features() creates new features

- [ ] **Model Operations**
  - [ ] Model training endpoint works
  - [ ] Model training with "max_complexity" config
  - [ ] Model training with "deep_wide" config
  - [ ] Model training with "baseline" config
  - [ ] Trained model saves to S3
  - [ ] Model metadata persisted correctly
  - [ ] Prediction endpoint loads model from S3
  - [ ] Prediction endpoint returns valid predictions
  - [ ] Handles missing model gracefully

**Why Important:** ML predictions affect business planning. Data processing and model reliability are critical.

---

### 13. Admin Routes Tests (`routes/admin.py`)
**File to create:** `test/test_admin_routes.py`

- [ ] **User Management**
  - [ ] GET /admin/users - lists all users (admin only)
  - [ ] Non-admin users get 403
  - [ ] POST /admin/users - generates invite token
  - [ ] Generated token is unique
  - [ ] POST /admin/users/<id>/delete - deletes user
  - [ ] Cannot delete self
  - [ ] POST /admin/users/<id>/update_role - updates role
  - [ ] Validates role is valid (user, manager, admin)
  - [ ] Invalid role returns error

**Why Important:** User management controls access. Self-deletion prevention is critical.

---

### 14. Template Filter Tests
**File to create:** `test/test_template_filters.py`

- [ ] **Price Formatting**
  - [ ] price_format filter formats "$1,234.56" correctly
  - [ ] Handles None/empty values
  - [ ] Handles numeric input

- [ ] **Phone Formatting**
  - [ ] format_phone filter formats "5551234567" as "(555) 123-4567"
  - [ ] Handles already formatted numbers
  - [ ] Handles None/empty values

- [ ] **Yes/Dash Formatting**
  - [ ] yesdash filter converts "1" → "Yes"
  - [ ] yesdash filter converts "0" → "-"
  - [ ] yesdash filter handles None/empty

- [ ] **Date Formatting**
  - [ ] date_format filter handles datetime objects
  - [ ] date_format filter handles string dates
  - [ ] date_format filter handles MM/DD/YY HH:MM:SS
  - [ ] date_format filter handles YYYY-MM-DD
  - [ ] date_format filter handles None/empty

**Why Important:** Filters ensure consistent data display across all templates.

---

### 15. API Endpoint Tests
**File to create:** `test/test_api_endpoints.py`

- [ ] **Pagination**
  - [ ] All API endpoints support pagination
  - [ ] Page parameter works
  - [ ] Per-page parameter works
  - [ ] Returns correct total count

- [ ] **Filtering**
  - [ ] Filtering works across all API endpoints
  - [ ] Multiple filters combine with AND
  - [ ] Invalid filters return empty results

- [ ] **Sorting**
  - [ ] Sorting works for all sortable fields
  - [ ] Ascending sort works
  - [ ] Descending sort works
  - [ ] Invalid sort field returns error

- [ ] **Error Handling**
  - [ ] Invalid data returns 400
  - [ ] Missing required fields returns 400
  - [ ] Not found returns 404
  - [ ] Unauthorized returns 401
  - [ ] Forbidden returns 403
  - [ ] Server errors return 500 with message

**Why Important:** APIs power frontend functionality. Consistency and error handling are essential.

---

## 🟢 LOW PRIORITY - NICE TO HAVE

### 16. Dashboard Tests (`routes/dashboard.py`)
**File to create:** `test/test_dashboard_routes.py`

- [ ] GET / - renders dashboard
- [ ] get_recent_orders() returns recent orders
- [ ] Statistics calculations are correct
- [ ] Handles database errors gracefully
- [ ] Sail order counting works
- [ ] Rush order counting works

**Why Important:** Dashboard is mostly display. Less critical than CRUD operations.

---

### 17. In Progress Tests (`routes/in_progress.py`)
**File to create:** `test/test_in_progress_routes.py`

- [ ] GET /in_progress/ - renders in-progress page
- [ ] Filters by ProcessingStatus = True
- [ ] Pagination works
- [ ] Orders sorted by DateIn descending

**Why Important:** Simple route with minimal logic. Low complexity.

---

### 18. Utility Helper Tests
**File to create:** `test/test_utils_helpers.py`

- [ ] **File Validation (utils/helpers.py)**
  - [ ] allowed_file() validates extensions correctly
  - [ ] save_uploaded_photo() resizes images
  - [ ] save_uploaded_photo() saves to correct location

- [ ] **Number Generation (utils/helpers.py)**
  - [ ] generate_work_order_number() increments correctly
  - [ ] generate_work_order_number() handles gaps
  - [ ] generate_repair_order_number() increments correctly

- [ ] **Formatting (utils/helpers.py)**
  - [ ] format_phone_number() handles 10-digit numbers
  - [ ] format_phone_number() handles 11-digit numbers
  - [ ] format_phone_number() handles already formatted
  - [ ] calculate_days_since() calculates date difference
  - [ ] get_status_color() maps status to Bootstrap class

- [ ] **Pagination (utils/helpers.py)**
  - [ ] paginate_query() returns correct page
  - [ ] paginate_query() handles invalid page numbers
  - [ ] paginate_query() calculates total pages correctly

**Why Important:** Utilities are used throughout but are relatively simple. Good for additional coverage.

---

### 19. CSV Handler Tests
**File to create:** `test/test_csv_handler.py`

- [ ] CSV import works
- [ ] CSV export works
- [ ] Data validation during import
- [ ] Handles malformed CSV files
- [ ] Error messages for invalid data

**Why Important:** CSV functionality is likely used infrequently for data migration.

---

### 20. Integration Tests
**File to create:** `test/test_integration.py`

- [ ] **End-to-End Workflows**
  - [ ] Complete work order lifecycle
  - [ ] Complete repair order lifecycle
  - [ ] Customer → Inventory → Work Order flow
  - [ ] File upload → Download → Delete flow
  - [ ] User registration → Login → Access flow

- [ ] **Database Integration**
  - [ ] Transaction rollback on error
  - [ ] Concurrent access handling
  - [ ] Foreign key constraints work
  - [ ] Cascade delete works

**Why Important:** Integration tests ensure components work together but are time-consuming to write and run.

---

### 21. Performance Tests
**File to create:** `test/test_performance.py`

- [ ] Large dataset pagination performs well
- [ ] Complex queries perform well (joins, subqueries)
- [ ] N+1 query prevention
- [ ] Index usage verification
- [ ] Connection pool efficiency

**Why Important:** Performance matters but is less critical than correctness. Optimize after core functionality is solid.

---

## Test Coverage Goals

**Current Estimated Coverage:** ~15% (models only)

**Target Coverage by Priority:**
- **Phase 1 (HIGH):** 60% coverage - Authentication, CRUD, Authorization
- **Phase 2 (MEDIUM):** 75% coverage - Inventory, Sources, Analytics, ML
- **Phase 3 (LOW):** 85%+ coverage - Utilities, Integration, Performance

---

## Testing Tools & Commands

**Run all tests:**
```bash
pytest test/
```

**Run specific test file:**
```bash
pytest test/test_auth.py -v
```

**Run tests by marker:**
```bash
pytest -m unit          # Fast unit tests only
pytest -m integration   # Database integration tests
pytest -m auth          # Authentication tests
```

**Run with coverage:**
```bash
pytest --cov=. --cov-report=html test/
```

**Run specific test:**
```bash
pytest test/test_auth.py::TestLoginRoutes::test_valid_login -v
```

---

## Notes

- All test files should use the fixtures defined in `conftest.py`
- Mock external dependencies (S3, ML models, email)
- Test both success and failure paths
- Use descriptive test names: `test_<action>_<scenario>_<expected_result>`
- Add docstrings to complex tests
- Keep tests isolated - each test should be independent
- Clean up test data after each test (use fixtures with teardown)

---

## Priority Order for Test Creation

1. `test/test_auth.py` - Authentication (security critical)
2. `test/test_decorators.py` - Authorization (security critical)
3. `test/test_work_orders_routes.py` - Work orders CRUD (core business)
4. `test/test_repair_orders_routes.py` - Repair orders CRUD (core business)
5. `test/test_customers_routes.py` - Customer management (core business)
6. `test/test_queue_routes.py` - Queue management (workflow critical)
7. `test/test_file_operations.py` - File upload/download (data integrity)
8. `test/test_pdf_generation.py` - PDF generation (customer-facing)
9. `test/test_inventory_routes.py` - Inventory management
10. `test/test_source_routes.py` - Source management
11. `test/test_analytics_routes.py` - Analytics
12. `test/test_ml_routes.py` - ML predictions
13. `test/test_admin_routes.py` - Admin functions
14. `test/test_template_filters.py` - Template filters
15. `test/test_api_endpoints.py` - API consistency
16. Continue with LOW priority tests...

---

**End of Testing Checklist**