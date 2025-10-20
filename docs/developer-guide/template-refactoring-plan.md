# Template Unification Refactoring Plan

## Overview
This document outlines the plan to unify the UI between Work Orders and Repair Orders, following DRY principles and ensuring consistent user experience.

## Current State

### Work Orders
- **create.html**: 1,212 lines - Modern card-based UI
- **edit.html**: 1,110 lines - Similar to create
- **Features**:
  - Card-style new item layout
  - Sophisticated file upload with drag-and-drop
  - Customer inventory selection with modern UI
  - Comprehensive field organization
  - Inline JavaScript (~700 lines)

### Repair Orders
- **create.html**: 852 lines - Table-based UI
- **edit.html**: 945 lines - Similar to create
- **Features**:
  - Table-based item layout (less user-friendly)
  - Basic file upload
  - Customer inventory selection (similar to work orders)
  - Inline JavaScript (~400 lines)

## Completed Work

### 1. Shared Components Created
- ✅ **templates/_order_macros.html** - Reusable Jinja2 macros
  - `customer_inventory_section()` - Customer item history
  - `file_upload_section()` - File upload with drag-and-drop
  - `new_items_section_cards()` - Modern card-style item layout
  - `order_summary_sidebar()` - Order summary with counters

- ✅ **static/js/order-form-shared.js** - Centralized JavaScript (~450 lines)
  - Inventory management functions
  - Item CRUD operations (add/remove)
  - File upload handling with validation
  - Counter updates and UI state management
  - Autocomplete datalist creation

### 2. Backend Refactoring
- ✅ Work order routes refactored with private helper functions
- ✅ Repair order routes refactored with private helper functions
- ✅ Both follow same clean pattern

## Refactoring Strategy

### Phase 1: Update Repair Order Templates (Priority)
Replace table-based layout with modern card-based layout to match work orders.

**Files to modify**:
1. `templates/repair_orders/create.html`
2. `templates/repair_orders/edit.html`

**Changes**:
1. Import `_order_macros.html` at top
2. Replace "Add New Items" table section with `new_items_section_cards()` macro
3. Replace inline customer inventory code with `customer_inventory_section()` macro
4. Replace inline file upload code with `file_upload_section()` macro
5. Replace inline order summary with `order_summary_sidebar()` macro
6. Include `order-form-shared.js` script
7. Add repair-order-specific JavaScript only (minimal)
8. Remove duplicate JavaScript code

**Expected reduction**: ~400 lines per file (~800 lines total)

### Phase 2: Update Work Order Templates
Refactor to use shared components and remove duplication.

**Files to modify**:
1. `templates/work_orders/create.html`
2. `templates/work_orders/edit.html`

**Changes**:
1. Import `_order_macros.html` at top
2. Replace inline sections with macros (same as repair orders)
3. Include `order-form-shared.js` script
4. Add work-order-specific JavaScript only (e.g., RepairsNeeded logic, SeeRepair field)
5. Remove duplicate JavaScript code

**Expected reduction**: ~700 lines per file (~1,400 lines total)

### Phase 3: Testing
Test all functionality in both work orders and repair orders:
- ✅ Customer selection and inventory loading
- ✅ Item selection from inventory
- ✅ Adding new items (card-based UI)
- ✅ Removing items
- ✅ File upload (drag-and-drop and click)
- ✅ File removal
- ✅ Form validation
- ✅ Form submission
- ✅ Counter updates
- ✅ Rush order badges

## Specific Template Structure

### Proposed Repair Order Create Template Structure
```jinja2
{% extends "base.html" %}
{% from "_order_macros.html" import
    customer_inventory_section,
    file_upload_section,
    new_items_section_cards,
    order_summary_sidebar
%}

{% block title %}Create New Repair Work Order{% endblock %}

{% block styles %}
{{ super() }}
<!-- Any repair-order-specific styles -->
{% endblock %}

{% block content %}
<div class="container-fluid">
    <form method="POST" id="repairOrderForm" enctype="multipart/form-data">
        <div class="row">
            <div class="col-lg-8">
                <!-- Order Information Card -->
                <!-- (repair-order-specific fields) -->

                <!-- Repair Details Card -->
                <!-- (repair-order-specific fields) -->

                <!-- Customer Inventory - SHARED MACRO -->
                {{ customer_inventory_section() }}

                <!-- New Items - SHARED MACRO -->
                {{ new_items_section_cards(title="Add New Items") }}

                <!-- File Upload - SHARED MACRO -->
                {{ file_upload_section() }}
            </div>

            <div class="col-lg-4">
                <!-- Quote & Pricing Card -->
                <!-- (repair-order-specific) -->

                <!-- Order Summary - SHARED MACRO -->
                {{ order_summary_sidebar() }}

                <!-- Actions Card -->
                <!-- (form buttons) -->
            </div>
        </div>
    </form>
</div>
{% endblock %}

{% block scripts %}
{{ super() }}
<!-- Include shared JavaScript -->
<script src="{{ url_for('static', filename='js/order-form-shared.js') }}"></script>

<!-- Repair-order-specific initialization -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Initialize shared components
    createDatalists();
    initializeFileUpload();

    // Load next repair order number
    fetch('/repair_work_orders/api/next_ro_number')
        .then(response => response.json())
        .then(data => {
            document.getElementById('next_ro_number').value = data.next_ro_number;
            document.getElementById('ro-number-display').textContent = `RO-${data.next_ro_number}`;
        });

    // Customer change handler
    document.getElementById('CustID').addEventListener('change', function() {
        loadCustomerInventory(this.value);
        // Load customer source
        fetch(`/customers/api/customer/${this.value}`)
            .then(response => response.json())
            .then(customer => {
                document.getElementById('SOURCE').value = customer.Source || '';
            });
    });

    // Rush order change handlers
    document.getElementById('RushOrder').addEventListener('change', updateRushStatus);
    document.getElementById('FirmRush').addEventListener('change', updateRushStatus);

    // Initialize counts
    updateCounts();
});
</script>
{% endblock %}
```

## Benefits

1. **Code Reduction**: ~2,200 lines removed across 4 templates
2. **Consistency**: Identical UI/UX between work orders and repair orders
3. **Maintainability**: Single source of truth for common components
4. **DRY Principle**: No duplicate code
5. **Modern UI**: Card-based layout everywhere (better UX)
6. **Easier Updates**: Change once, applies everywhere

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Comprehensive testing after each template |
| Form field names mismatch | Careful review of backend expectations |
| JavaScript conflicts | Proper namespace management |
| CSS styling issues | Test in actual browser |

## Implementation Order

1. **Repair Orders First** - They need the most improvement
   - create.html (estimated 2 hours)
   - edit.html (estimated 2 hours)
   - Testing (1 hour)

2. **Work Orders Second** - They're already good, just DRY them
   - create.html (estimated 1.5 hours)
   - edit.html (estimated 1.5 hours)
   - Testing (1 hour)

3. **Integration Testing** - Full end-to-end
   - Create work order flow
   - Edit work order flow
   - Create repair order flow
   - Edit repair order flow
   - File uploads
   - Form validation

## Next Steps

**Option A: Full Automated Refactoring**
- I proceed with refactoring all 4 templates
- Run tests after each template
- Create git commits for each phase

**Option B: Incremental Refactoring**
- Start with `repair_orders/create.html` only
- Test thoroughly
- Get approval before proceeding to next template

**Option C: Manual Review First**
- I provide detailed diffs for one template
- You review and approve approach
- Then I proceed with remaining templates

Which approach would you prefer?
