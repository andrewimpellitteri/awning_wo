# Item Exclusion Feature - Dynamic Item List Management

## Overview
When editing work orders or repair orders, the "Existing Items" list and "Customer Item History" list should be mutually exclusive. An item should only appear in ONE list at a time to prevent confusion and duplication.

## Business Requirements

### User Story
As a user editing a work order, I want to see a clear separation between:
- **Existing Items**: Items currently in THIS work order
- **Customer Item History**: Available items from the customer's inventory catalog that are NOT already in this work order

### Behavior

#### Scenario 1: Initial Page Load
- **Given**: A work order with items A and C already added
- **When**: User opens the edit page
- **Then**:
  - Existing Items shows: [A, C]
  - Customer Item History shows: [B, D, E] (all other customer items, excluding A and C)

#### Scenario 2: Removing Item from Work Order
- **Given**:
  - Existing Items: [A, C]
  - Customer Item History: [B, D, E]
- **When**: User unchecks/removes item A from existing items
- **Then**:
  - Existing Items: [C]
  - Customer Item History: [A, B, D, E] ← A reappears in history

#### Scenario 3: Adding Item from History
- **Given**:
  - Existing Items: [C]
  - Customer Item History: [A, B, D, E]
- **When**: User selects item B from customer history
- **Then**:
  - Existing Items: [C, B] ← B added
  - Customer Item History: [A, D, E] ← B removed from history

#### Scenario 4: Re-adding Previously Removed Item
- **Given**:
  - Existing Items: [C]
  - Customer Item History: [A, B, D, E]
- **When**: User checks item A from history (which was previously removed)
- **Then**:
  - Existing Items: [C, A] ← A re-added
  - Customer Item History: [B, D, E] ← A disappears from history

## Technical Implementation

### Database Schema

#### Inventory Table (`tblcustawngs`)
- **Primary Key**: `InventoryKey` (unique identifier for each catalog item)
- Contains the master catalog of items per customer
- Fields: Description, Material, Condition, Color, SizeWgt, Price, CustID, Qty

#### WorkOrderItem Table (`tblorddetcustawngs`)
- **Primary Key**: `id` (auto-increment)
- Contains items specific to each work order
- **No foreign key to Inventory** - items are copied snapshots
- Fields: WorkOrderNo, CustID, Description, Material, Condition, Color, SizeWgt, Price, Qty

#### RepairWorkOrderItem Table (`tblrwodetcustawngs`)
- **Primary Key**: `id` (auto-increment)
- Contains items specific to each repair order
- **No foreign key to Inventory** - items are copied snapshots
- Fields: RepairOrderNo, CustID, Description, Material, Condition, Color, SizeWgt, Price, Qty

### Matching Logic

Since there's no foreign key relationship, we match items by their **InventoryKey**:

```javascript
// Inventory item structure from API
{
  "id": "INV-12345",  // InventoryKey
  "description": "Awning",
  "material": "Canvas",
  "condition": "Good",
  "color": "Blue",
  "size_wgt": "10x12",
  "price": 150.00,
  "qty": 1
}
```

When an item is added to a work order from inventory, we need to track which `InventoryKey` it came from.

### Implementation Approach

#### Option 1: Track InventoryKey in WorkOrderItem (Recommended)
**Pros:**
- Clean, reliable matching
- Can trace items back to their catalog source
- Handles edge cases (identical items with different prices)

**Cons:**
- Requires database migration to add `InventoryKey` field to WorkOrderItem and RepairWorkOrderItem

**Implementation:**
1. Add migration to add `inventory_key` column to both item tables
2. Update `process_selected_inventory_items()` to store the InventoryKey
3. In edit form, pass InventoryKey along with item data
4. JavaScript filters history items by checking if their InventoryKey exists in current items

#### Option 2: Match by Description + Material (Alternative)
**Pros:**
- No database changes required
- Works with existing schema

**Cons:**
- Fragile matching (what if two items have same desc/material but different sizes?)
- Can't distinguish between identical items with different prices
- Edge cases may cause confusion

**Implementation:**
1. JavaScript creates a Set of "description|material" keys from existing items
2. Filter history items by checking if their key exists in the Set
3. Update Set when items are added/removed dynamically

### Solution Architecture

#### Frontend (JavaScript)
```javascript
// Global state
let existingItemKeys = new Set();  // InventoryKeys of items in work order
let allInventoryItems = [];        // Full inventory from API

// On page load
function initializeItemLists() {
  // Collect InventoryKeys from existing items
  existingItemKeys = collectExistingItemKeys();

  // Load customer inventory
  loadCustomerInventory(custId);
}

// Filter inventory to exclude existing items
function filterInventoryItems(inventoryItems) {
  return inventoryItems.filter(item => !existingItemKeys.has(item.id));
}

// When item is removed from work order
function onItemRemovedFromWorkOrder(inventoryKey) {
  existingItemKeys.delete(inventoryKey);
  refreshInventoryDisplay();
}

// When item is added from inventory
function onItemAddedFromInventory(inventoryKey) {
  existingItemKeys.add(inventoryKey);
  refreshInventoryDisplay();
}
```

#### Backend Changes

**If using Option 1 (recommended):**

1. **Database Migration**
```python
# alembic/versions/xxxx_add_inventory_key_to_items.py
def upgrade():
    op.add_column('tblorddetcustawngs',
                  sa.Column('inventory_key', sa.String(), nullable=True))
    op.add_column('tblrwodetcustawngs',
                  sa.Column('inventory_key', sa.String(), nullable=True))

def downgrade():
    op.drop_column('tblorddetcustawngs', 'inventory_key')
    op.drop_column('tblrwodetcustawngs', 'inventory_key')
```

2. **Model Updates**
```python
class WorkOrderItem(db.Model):
    # ... existing fields ...
    InventoryKey = db.Column("inventory_key", db.String, nullable=True)
```

3. **Update item processing functions**
```python
def process_selected_inventory_items(form, order_no, cust_id, item_class):
    for inv_key in selected_ids:
        inventory_item = Inventory.query.get(inv_key)
        item = item_class(
            # ... existing fields ...
            InventoryKey=inv_key,  # NEW: Track source
        )
```

4. **Update edit template to include InventoryKey**
```html
<input type="hidden" name="existing_item_inventory_key[]" value="{{ item.InventoryKey }}">
```

**If using Option 2 (no DB changes):**

Just use JavaScript matching - no backend changes needed.

## Files to Modify

### Templates
- `/templates/work_orders/edit.html` - Add InventoryKey hidden fields, update JavaScript
- `/templates/repair_orders/edit.html` - Add InventoryKey hidden fields, update JavaScript
- `/static/js/order-form-shared.js` - Add filtering logic to `loadCustomerInventory()`

### Models (Option 1 only)
- `/models/work_order.py` - Add `InventoryKey` field to `WorkOrderItem`
- `/models/repair_order.py` - Add `InventoryKey` field to `RepairWorkOrderItem`

### Routes (Option 1 only)
- `/utils/order_item_helpers.py` - Update `process_selected_inventory_items()` to store InventoryKey

### Migrations (Option 1 only)
- Create new Alembic migration to add `inventory_key` column

## Testing Checklist

- [ ] Initial page load: items in work order don't appear in history
- [ ] Remove item from work order: item reappears in history
- [ ] Add item from history: item disappears from history
- [ ] Add item from history: item appears in existing items
- [ ] Refresh page after save: state persists correctly
- [ ] Edge case: Item with no InventoryKey (manually added) doesn't break filtering
- [ ] Edge case: Multiple items with same description/material are handled correctly
- [ ] Works for both work orders and repair orders

## Recommended Approach

**Use Option 1** (add InventoryKey tracking) because:
1. More reliable and future-proof
2. Enables better item tracking and reporting
3. Handles edge cases correctly
4. Small database change with big benefits

Start with Option 2 for quick implementation if migration is not feasible immediately, but plan to migrate to Option 1 later.

## Implementation Steps

1. ✅ Document requirements (this file)
2. ⏳ Decide on Option 1 vs Option 2
3. ⏳ If Option 1: Create and run database migration
4. ⏳ Update models to include InventoryKey field
5. ⏳ Update backend to store InventoryKey when creating items
6. ⏳ Update edit templates to output InventoryKey in hidden fields
7. ⏳ Update JavaScript to collect and track InventoryKeys
8. ⏳ Implement dynamic filtering in loadCustomerInventory()
9. ⏳ Add event handlers for add/remove actions
10. ⏳ Test thoroughly with various scenarios
11. ⏳ Deploy and monitor

## Questions/Decisions

- **Decision needed**: Option 1 (InventoryKey tracking) vs Option 2 (Description+Material matching)?
- **Decision needed**: Should manually added items (not from inventory) also get an InventoryKey generated?
- **Question**: What happens if an item exists in the work order but was deleted from inventory?