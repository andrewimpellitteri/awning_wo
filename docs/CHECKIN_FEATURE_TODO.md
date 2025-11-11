# Check-In Feature - Todo List & Code Review

**Created:** 2025-11-09
**Status:** Feature Partially Complete - Critical Items Remaining
**Related Files:** `routes/checkins.py`, `models/checkin.py`, `templates/checkins/`

## Executive Summary

The check-in feature allows staff (managers/admins) to record customer items as they arrive for cleaning/repair. Admins can later convert pending check-ins into work orders. The feature is **80% complete** but has **critical missing functionality** and several bugs that need addressing.

### What Works ✅
- ✅ Check-in creation with customer search (Selectize.js)
- ✅ Item entry with full metadata (Description, Material, Color, Qty, Size, Price, Condition)
- ✅ Additional fields matching work order (SpecialInstructions, StorageTime, RackNo, ReturnTo, DateRequired, RepairsNeeded, RushOrder)
- ✅ Pending check-ins list view
- ✅ Check-in detail view with all fields displayed
- ✅ Admin-only conversion to work order
- ✅ Pre-filling work order form from check-in data
- ✅ Status tracking (pending → processed)
- ✅ Check-in deletion (pending only)
- ✅ Source information display
- ✅ Comprehensive test coverage (7 tests, all passing)

### What's Missing ❌
- ❌ **CRITICAL:** Customer item history not shown on check-in form
- ❌ **CRITICAL:** File upload UI not implemented (database ready, but no routes/templates)
- ❌ Item pre-selection from customer catalog (major UX issue)
- ❌ Edit check-in functionality
- ❌ Badge count in navigation for pending check-ins
- ❌ Check-in search/filter functionality
- ❌ Mobile responsiveness testing
- ❌ File attachment viewing on detail page

---

## Priority 1 - Critical Issues (Must Fix)

### 🚨 P1.1: Add Customer Item History to Check-In Form
**Status:** Not Started
**Impact:** High - Staff must manually re-enter all item details instead of selecting from history
**Effort:** Medium (2-3 hours)

**Problem:**
The check-in creation form (`templates/checkins/new.html`) does NOT show customer item history like the work order form does. This forces staff to manually type every item detail from scratch, which:
- Increases data entry time by 5-10x
- Introduces typos and inconsistencies (e.g., "Sunbrela" vs "Sunbrella")
- Defeats the purpose of having an inventory catalog system

**Expected Behavior:**
When a customer is selected in the check-in form, it should:
1. Load their previous items from `Inventory` table via AJAX
2. Display items in a selectable card UI (same as work order form)
3. Allow staff to check items to add them to the check-in
4. Show item details: Description, Material, Color, Size, Last Price, Last Condition
5. Auto-populate item fields when selected (editable)

**Implementation Steps:**
1. Import the `customer_inventory_section()` macro from `_order_macros.html` into `templates/checkins/new.html`
2. Add the macro call after the "Check-In Information" card (line 88)
3. Include `order-form-shared.js` script in the template's `{% block scripts %}`
4. Update Selectize.js `onChange` handler to call `loadCustomerInventory(value)`
5. Ensure the existing `/work_orders/api/customer_inventory/<cust_id>` endpoint works for check-ins
6. Test with a customer who has previous work order items

**Files to Modify:**
- `templates/checkins/new.html` (lines 88-89, 205-210)
- May need to create a check-in-specific JS file or modify `order-form-shared.js`

**Testing:**
- Create a new check-in for a customer with previous work orders
- Verify item history loads via AJAX
- Verify items can be selected and added to check-in
- Verify selected items appear in the items section with pre-filled data

**Related Code:**
- Work order implementation: `templates/work_orders/edit.html:2-4` (macro import)
- Inventory API: `routes/work_orders.py:611-633`
- Shared JS: `static/js/order-form-shared.js:91-150`

---

### 🚨 P1.2: Implement File Upload for Check-Ins
**Status:** Not Started (Database Ready, Routes/UI Missing)
**Impact:** High - Staff cannot attach photos/documents to check-ins
**Effort:** Medium (3-4 hours)

**Problem:**
The `CheckInFile` model and database table (`tblcheckinfiles`) exist, but:
- No file upload UI in `templates/checkins/new.html`
- No routes in `routes/checkins.py` for handling file uploads
- No display of uploaded files in `templates/checkins/detail.html`
- Files cannot be transferred to work orders during conversion

**Expected Behavior:**
1. Check-in creation form shows file upload dropzone (like work orders)
2. Files are uploaded to S3 during check-in creation
3. Detail page displays uploaded files with download links
4. Files are COPIED to work order when converting check-in

**Implementation Steps:**
1. Add file upload section to `templates/checkins/new.html`
   - Import `file_upload_section()` macro from `_order_macros.html`
   - Add dropzone UI after "Additional Details" card
2. Update `routes/checkins.py` POST handler:
   - Add `from utils.file_upload import handle_file_uploads`
   - Process uploaded files after check-in creation
   - Create `CheckInFile` records for each uploaded file
3. Update `templates/checkins/detail.html`:
   - Add "Files" card section to display `checkin.files`
   - Show file name, size, upload date, download link
4. Update `routes/work_orders.py` conversion logic:
   - Copy files from check-in to work order during conversion
   - Create corresponding `WorkOrderFile` records

**Files to Modify:**
- `templates/checkins/new.html` (add file upload section)
- `routes/checkins.py:52-117` (POST handler for create_checkin)
- `templates/checkins/detail.html:186-233` (add files display section)
- `routes/work_orders.py:693-750` (work order POST handler for conversion)

**Testing:**
- Upload files during check-in creation
- Verify files saved to S3 and database records created
- View check-in detail page and verify files displayed
- Convert check-in to work order and verify files copied

**Security Considerations:**
- Reuse existing file validation from `utils/file_upload.py`
- Enforce file size limits (10MB)
- Validate file types (PDF, JPG, PNG, DOCX, XLSX, TXT, CSV)
- Sanitize file names to prevent path traversal attacks

---

## Priority 2 - Important Features (Should Have)

### P2.1: Add Edit Check-In Functionality
**Status:** Not Implemented
**Impact:** Medium - Staff cannot correct mistakes without deleting and recreating
**Effort:** Medium (2-3 hours)

**Problem:**
There is no way to edit a check-in after creation. Staff must delete and recreate to fix:
- Wrong customer selected
- Missing items
- Incorrect item details
- Wrong dates or special instructions

**Expected Behavior:**
- "Edit" button on check-in detail page (pending only)
- Edit form pre-filled with all current data
- Item updates use same pattern as work orders (delete-then-insert)
- Cannot edit processed check-ins

**Implementation Steps:**
1. Create `templates/checkins/edit.html` (similar to `new.html`)
2. Add GET route: `@checkins_bp.route("/<int:checkin_id>/edit")`
3. Add POST route to handle updates
4. Use delete-then-insert pattern for items (same as repair orders)
5. Add "Edit" button to detail page (line 148-150, next to "Edit as Work Order")

**Files to Create/Modify:**
- `templates/checkins/edit.html` (new file)
- `routes/checkins.py` (add edit routes)
- `templates/checkins/detail.html` (add edit button)

---

### P2.2: Add Pending Check-In Badge to Navigation
**Status:** Not Implemented
**Impact:** Medium - Staff cannot see at-a-glance if check-ins need processing
**Effort:** Small (30 minutes)

**Problem:**
The navigation has no visual indicator of pending check-ins count, unlike other features (e.g., cleaning queue shows count).

**Expected Behavior:**
- Navigation link shows "Check-Ins" with badge count (e.g., "Check-Ins (3)")
- Badge updates in real-time when check-ins are created/processed
- Badge color: warning (yellow/orange) for pending items

**Implementation Steps:**
1. Update `templates/base.html` navigation to include badge
2. Use existing API endpoint: `GET /checkins/api/pending_count` (already exists at line 213)
3. Add JavaScript to poll endpoint every 30 seconds
4. Update badge count dynamically

**Files to Modify:**
- `templates/base.html` (navigation section)
- Add JavaScript in `static/js/` or inline in base.html

**Existing API:**
```python
@checkins_bp.route("/api/pending_count")
@login_required
def get_pending_count():
    """Get count of pending check-ins for navigation badge"""
    count = CheckIn.query.filter_by(Status="pending").count()
    return jsonify({"count": count})
```

---

### P2.3: Add Search/Filter to Pending Check-Ins List
**Status:** Not Implemented
**Impact:** Medium - Hard to find specific check-ins as list grows
**Effort:** Medium (2 hours)

**Problem:**
`templates/checkins/pending.html` shows all pending check-ins in date order with no search or filter capabilities.

**Expected Behavior:**
- Search by customer name, CustID, or check-in ID
- Filter by date range (DateIn, DateRequired)
- Filter by flags (RepairsNeeded, RushOrder)
- Sort by date, customer name, or created date

**Implementation Steps:**
1. Add search input and filter controls to `templates/checkins/pending.html`
2. Implement client-side filtering with JavaScript (simple, fast)
3. OR implement server-side filtering with query params
4. Add "Clear Filters" button

**Files to Modify:**
- `templates/checkins/pending.html`
- Possibly `routes/checkins.py:128-139` (if server-side)

---

## Priority 3 - Nice to Have (Future Enhancements)

### P3.1: Mobile Responsiveness Testing
**Status:** Unknown
**Impact:** Low-Medium - Depends on mobile usage
**Effort:** Small (1 hour testing + fixes)

**Action Items:**
- Test all check-in pages on mobile viewport (375px, 768px)
- Verify Selectize.js works on touch devices
- Ensure item cards stack properly
- Test file upload on mobile
- Fix any layout issues

---

### P3.2: Check-In Analytics Dashboard
**Status:** Not Implemented
**Impact:** Low - Nice for business insights
**Effort:** Medium (3 hours)

**Potential Metrics:**
- Average time from check-in to work order conversion
- Most common items by customer/source
- Rush order frequency
- Check-ins by day/week/month

---

### P3.3: Bulk Actions for Pending Check-Ins
**Status:** Not Implemented
**Impact:** Low - Would speed up admin workflow
**Effort:** Medium (2-3 hours)

**Features:**
- Select multiple check-ins with checkboxes
- Bulk convert to work orders
- Bulk delete (with confirmation)
- Assign to specific staff member

---

## Code Review Findings

### 🐛 Bug #1: Boolean Field Handling in Check-In Creation
**Location:** `routes/checkins.py:76-77`
**Severity:** Low
**Status:** Existing (Works but could be better)

**Current Code:**
```python
RepairsNeeded=bool(request.form.get("RepairsNeeded")),
RushOrder=bool(request.form.get("RushOrder"))
```

**Issue:**
Using `bool(request.form.get(...))` will evaluate to `True` even if the checkbox is unchecked but the field exists in the form. In HTML forms, unchecked checkboxes don't send any value, but if the field is present with any value (even empty string), `bool("")` returns `False`, which is correct. However, this is fragile.

**Better Approach:**
```python
RepairsNeeded=request.form.get("RepairsNeeded") == "1",
RushOrder=request.form.get("RushOrder") == "1"
```

This explicitly checks for the value "1" (which is what the checkbox sends when checked).

**Fix Priority:** Low (current code works, but explicit is better)

---

### 🐛 Bug #2: Missing Form Enctype for Future File Uploads
**Location:** `templates/checkins/new.html:50`
**Severity:** High (Blocking P1.2)
**Status:** Critical Bug

**Current Code:**
```html
<form method="POST" id="checkinForm">
```

**Issue:**
When file uploads are added (P1.2), the form will NOT work because it's missing `enctype="multipart/form-data"`.

**Fix:**
```html
<form method="POST" id="checkinForm" enctype="multipart/form-data">
```

**Fix Priority:** High (must be fixed before implementing file uploads)

---

### 🐛 Bug #3: No Error Handling for Customer Search AJAX
**Location:** `templates/checkins/new.html:243-246`
**Severity:** Medium
**Status:** Existing Issue

**Current Code:**
```javascript
error: function(xhr, status, error) {
    console.error('AJAX error:', status, error);
    callback();
},
```

**Issue:**
When customer search API fails, the error is only logged to console. User sees no feedback that search failed.

**Better Approach:**
```javascript
error: function(xhr, status, error) {
    console.error('AJAX error:', status, error);
    alert('Error searching customers. Please try again or contact support.');
    callback();
},
```

Or use a toast notification for better UX.

**Fix Priority:** Medium (affects user experience when API fails)

---

### 🐛 Bug #4: Form Validation Allows Empty Item Description
**Location:** `templates/checkins/new.html:306-307`
**Severity:** Low
**Status:** Handled by Backend

**Current Code:**
```html
<input type="text" class="form-control form-control-sm" name="item_description[]" required
       placeholder="e.g., Awning, Cushion, Bimini">
```

**Issue:**
The `required` attribute is on each item's description field, but if the user removes all items, the form can still be submitted with no items (checked by JavaScript at line 368-373).

However, the backend handles this gracefully at `routes/checkins.py:93`:
```python
if descriptions[i]:  # Only add if description is not empty
```

**Assessment:** This is actually fine. The JavaScript validation prevents submission with zero items, and the backend ignores empty descriptions.

**Fix Priority:** None (working as intended)

---

### 🐛 Bug #5: Customer Info Box Shows on Page Load
**Location:** `templates/checkins/new.html:83-86`
**Severity:** Low
**Status:** Visual Glitch

**Current Code:**
```html
<div id="customer-info" class="alert alert-info" style="display: none;">
    <strong>Customer Info:</strong>
    <div id="customer-details"></div>
</div>
```

**Issue:**
The customer info box is hidden with `display: none`, but when a customer is selected, `slideDown()` is called (line 266). This creates a smooth animation, which is good. However, if the user refreshes the page or navigates back, the box might not be hidden properly.

**Assessment:** Minor visual issue, unlikely to cause problems.

**Fix Priority:** None (acceptable behavior)

---

### ⚠️ Warning #1: SQLAlchemy Query.get() Deprecation
**Location:** Multiple places (tests, routes)
**Severity:** Medium (Future breaking change)
**Status:** Widespread Issue

**Example from tests:**
```python
checkin = CheckIn.query.get(checkin_id)  # Deprecated in SQLAlchemy 2.0
```

**Better Approach:**
```python
checkin = db.session.get(CheckIn, checkin_id)
```

**Locations to Fix:**
- `routes/checkins.py:147` - `CheckIn.query.get_or_404(checkin_id)`
- `routes/checkins.py:157` - `CheckIn.query.get_or_404(checkin_id)`
- `routes/work_orders.py:796` - `CheckIn.query.get(checkin_id)`
- All test files using `.query.get()`

**Fix Priority:** Medium (should fix eventually, not urgent)

---

### 💡 Code Quality Issue #1: Duplicate Customer Loading Logic
**Location:** `templates/checkins/new.html:239-251` vs `static/js/order-form-shared.js:115`
**Severity:** Low
**Status:** Tech Debt

**Issue:**
The customer search AJAX logic in the check-in form is almost identical to the inventory loading logic in work orders. This violates DRY principle.

**Recommendation:**
Extract Selectize initialization into a shared function in `order-form-shared.js`:
```javascript
function initializeCustomerSearch(elementId, onChangeCallback) {
    // Shared Selectize setup
}
```

**Fix Priority:** Low (works fine, but creates maintenance burden)

---

### 💡 Code Quality Issue #2: Magic Strings for Status Values
**Location:** Multiple files
**Severity:** Low
**Status:** Acceptable but could be better

**Examples:**
```python
Status="pending"
Status="processed"
```

**Better Approach:**
Define constants in `models/checkin.py`:
```python
class CheckInStatus:
    PENDING = "pending"
    PROCESSED = "processed"

# Usage
checkin.Status = CheckInStatus.PENDING
```

**Fix Priority:** Low (convention-over-configuration, not critical)

---

### 💡 Code Quality Issue #3: Missing Docstrings
**Location:** `routes/checkins.py:29-40`
**Severity:** Low
**Status:** Good practice missing

**Issue:**
The helper function `_parse_date_field()` has a good docstring, but some route functions don't:
- `create_checkin()` - has docstring ✅
- `view_pending()` - has docstring ✅
- `view_checkin()` - has docstring ✅
- `delete_checkin()` - has docstring ✅
- `customer_search()` - has docstring ✅
- `get_pending_count()` - has docstring ✅

**Assessment:** All routes actually DO have docstrings! Great job!

---

### ✅ Good Practices Found

1. **Comprehensive Tests:** 7 tests covering conversion behavior, role access, field transfer - excellent coverage
2. **Transaction Safety:** Database commits wrapped in try/except with rollback on error
3. **Input Validation:** Form validation on both client and server side
4. **SQL Injection Prevention:** Using SQLAlchemy ORM, parameterized queries
5. **XSS Prevention:** Jinja2 auto-escaping enabled
6. **CSRF Protection:** Flask-WTF CSRF tokens (assumed, check base template)
7. **Role-Based Access:** `@role_required` decorator properly used
8. **Code Organization:** Clear separation of routes, models, templates
9. **Database Migrations:** Proper Alembic migrations for schema changes
10. **Error Handling:** User-friendly flash messages, not exposing stack traces

---

## Testing Gaps

### Missing Test Coverage:
1. ❌ File upload during check-in creation (can't test until P1.2 implemented)
2. ❌ File transfer from check-in to work order during conversion
3. ❌ Edit check-in functionality (doesn't exist yet)
4. ❌ Customer inventory loading on check-in form (P1.1)
5. ❌ Mobile viewport testing
6. ❌ Long description/instruction text (potential overflow issues)
7. ❌ Special characters in item descriptions (SQL injection, XSS)
8. ❌ Concurrent check-in creation by multiple users for same customer
9. ❌ Invalid date formats (JavaScript vs backend parsing)
10. ❌ Customer with no Source information (null handling)

### Recommended New Tests:
```python
def test_checkin_with_special_characters_in_description(manager_client, app):
    """Test item descriptions with special characters don't cause XSS or SQL injection"""
    pass

def test_checkin_with_missing_customer_source(admin_client, app):
    """Test check-in detail page when customer has no source_info"""
    pass

def test_multiple_checkins_same_customer_concurrent(admin_client, app):
    """Test race condition: two users create check-ins for same customer"""
    pass
```

---

## Database Schema Review

### Table: `tblcheckins`
**Status:** ✅ Well Designed

**Columns:**
- `checkinid` (PK) - Auto-increment ✅
- `custid` (FK) - References customers ✅
- `datein` (Date) - Check-in date ✅
- `status` (String) - "pending" or "processed" ✅
- `workorderno` (FK, nullable) - Links to work order after conversion ✅
- `specialinstructions` (Text) - ✅
- `storagetime` (String) - ✅
- `rack_number` (String) - Note: Column name is `rack_number` but model uses `RackNo` ✅
- `returnto` (String) - ✅
- `daterequired` (Date) - ✅
- `repairsneeded` (Boolean) - ✅
- `rushorder` (Boolean) - ✅
- `created_at` (DateTime) - ✅
- `updated_at` (DateTime) - ✅

**Indexes:**
- ❓ Missing index on `status` (frequently queried for pending check-ins)
- ❓ Missing index on `custid` (for customer history lookup)

**Recommendations:**
```sql
CREATE INDEX idx_tblcheckins_status ON tblcheckins(status);
CREATE INDEX idx_tblcheckins_custid ON tblcheckins(custid);
```

---

### Table: `tblcheckinitems`
**Status:** ✅ Well Designed

**Columns:**
- `id` (PK) - Auto-increment ✅
- `checkinid` (FK, indexed) - ✅
- `description` (String) - ✅
- `material` (String) - Defaults to "Unknown" ✅
- `color` (String) - ✅
- `qty` (Integer) - ✅
- `sizewgt` (String) - Size/weight ✅
- `price` (Numeric 10,2) - ✅
- `condition` (String) - ✅

**Indexes:**
- ✅ Index on `checkinid` (already exists per model line 91)

---

### Table: `tblcheckinfiles`
**Status:** ✅ Well Designed (Not Used Yet)

**Columns:**
- `id` (PK) - Auto-increment ✅
- `checkinid` (FK, indexed) - ✅
- `file_name` (String 255) - ✅
- `file_path` (String 500) - ✅
- `file_size` (Integer) - ✅
- `file_type` (String 100) - ✅
- `uploaded_at` (DateTime) - ✅

**Indexes:**
- ✅ Index on `checkinid` (per migration line 20)

---

## Security Review

### ✅ Secure Practices:
1. **Authentication Required:** All routes use `@login_required`
2. **Role-Based Access:** `@role_required("admin", "manager")` on all check-in routes
3. **CSRF Protection:** Flask forms have CSRF tokens
4. **SQL Injection:** Using SQLAlchemy ORM (parameterized queries)
5. **XSS Prevention:** Jinja2 auto-escaping enabled
6. **File Upload Validation:** (Will be needed for P1.2 - see `utils/file_upload.py`)

### ⚠️ Security Concerns:
1. **Future:** File upload must validate types, sizes, scan for malware (P1.2)
2. **Future:** S3 signed URLs must have short expiration times for file downloads
3. **Review:** Check if `base.html` includes CSRF meta tag for AJAX requests

### 🔒 Recommended Security Enhancements:
1. Add rate limiting to customer search API (prevent enumeration attacks)
2. Add audit logging for check-in creation/deletion (who created what, when)
3. Add "created_by" field to track which user created the check-in
4. Add input sanitization for special instructions (prevent HTML injection)

---

## Performance Considerations

### Current Performance: ✅ Good

**Observations:**
1. Customer search is limited to 20 results (`routes/checkins.py:192`)
2. Selectize loadThrottle: 300ms prevents API spam (`templates/checkins/new.html:226`)
3. Check-in items loaded via relationship (lazy loading by default)
4. Pending check-ins query is simple and fast

### 📊 Potential Optimizations:
1. Add pagination to pending check-ins list if count > 50
2. Use `lazy="joined"` for `checkin.customer` relationship (avoid N+1 queries)
3. Add database index on `tblcheckins.status` (see schema review)
4. Cache pending count API response for 30 seconds (reduce DB hits)

---

## Documentation Needs

### Missing Documentation:
1. ❌ User guide: "How to create a check-in"
2. ❌ User guide: "How to convert check-in to work order"
3. ❌ User guide: "Understanding check-in vs work order"
4. ❌ Developer guide: "Check-in workflow architecture"
5. ❌ API documentation for `/checkins/api/*` endpoints

### Recommended Documentation:
Create: `docs/user-guide/checkins.md`
```markdown
# Check-In Feature User Guide

## What is a Check-In?
...

## Creating a Check-In
1. Navigate to Check-Ins > New Check-In
2. Search and select customer
3. Enter item details
4. Click "Save Check-In"

## Converting to Work Order (Admin Only)
...
```

---

## Implementation Roadmap

### Phase 1: Critical Fixes (1 week)
1. **Day 1-2:** Implement P1.1 (Customer Item History)
2. **Day 3-4:** Implement P1.2 (File Upload)
3. **Day 5:** Test and fix any bugs

### Phase 2: Important Features (1 week)
1. **Day 1-2:** Implement P2.1 (Edit Check-In)
2. **Day 3:** Implement P2.2 (Navigation Badge)
3. **Day 4:** Implement P2.3 (Search/Filter)
4. **Day 5:** Testing and bug fixes

### Phase 3: Polish (3 days)
1. Mobile responsiveness testing
2. Add missing database indexes
3. Write user documentation
4. Address tech debt items

---

## Acceptance Criteria

### Feature Complete When:
- [x] Check-ins can be created with all fields
- [x] Check-ins display correctly on detail page
- [x] Check-ins can be converted to work orders (admin only)
- [x] All check-in fields transfer to work order
- [ ] **Customer item history shows on check-in form** (P1.1)
- [ ] **Files can be uploaded and attached to check-ins** (P1.2)
- [ ] Check-ins can be edited (P2.1)
- [ ] Pending count badge shows in navigation (P2.2)
- [ ] Pending list can be searched/filtered (P2.3)
- [ ] All tests pass
- [ ] Mobile responsive
- [ ] User documentation exists

---

## Related Issues & PRs

- Migration: `alembic/versions/20251109_1729-add_checkin_extra_fields.py`
- Migration: `alembic/versions/20251109_1750-add_checkin_files_table.py`
- Tests: `test/test_checkins_routes.py:478-779` (7 tests, all passing)

---

## Questions for Product Owner

1. **File Upload:** Should files be COPIED or MOVED to work order during conversion?
2. **Edit Permissions:** Should managers be able to edit check-ins, or only admins?
3. **Check-In Retention:** How long should processed check-ins be kept? Archive policy?
4. **Notifications:** Should admins be notified when new check-ins are created?
5. **Bulk Operations:** Is bulk conversion needed, or one-at-a-time acceptable?

---

## Conclusion

The check-in feature has a **solid foundation** with good code quality, comprehensive tests, and proper security practices. However, it's **not production-ready** due to two critical missing features:

1. **Customer item history not shown** - Staff must manually type everything
2. **File upload not implemented** - Cannot attach photos/documents

**Estimated Time to Production-Ready:** 2-3 weeks (with testing)

**Risk Assessment:** 🟡 Medium Risk
- Core functionality works
- Missing features block efficient workflow
- No show-stopper bugs, but UX is incomplete

**Recommendation:** Prioritize P1.1 and P1.2 before releasing to production.
