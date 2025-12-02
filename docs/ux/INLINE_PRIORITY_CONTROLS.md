# Inline Priority Controls - Queue Management Enhancement

## Overview

Add inline priority controls to the cleaning queue view to reduce clicks and improve workflow efficiency. Currently, changing a work order's priority requires 4 clicks (queue → detail → edit → save → back). This enhancement reduces it to **1 click**.

## Current vs. Proposed UX

### Current Workflow (4 Clicks)
```
Queue List
  ↓ Click WO number
Work Order Detail
  ↓ Click "Edit"
Edit Work Order
  ↓ Toggle Rush/Firm Rush checkbox
  ↓ Click "Save"
Redirected back to detail
  ↓ Click "Back to Queue"
Queue List
```

**Total**: 4 clicks, ~15-20 seconds

### Proposed Workflow (1 Click)
```
Queue List
  ↓ Click priority button (Regular/Rush/Firm Rush)
Queue List (priority updated instantly)
```

**Total**: 1 click, ~2 seconds

**Time Savings**: ~18 seconds per priority change × 50 changes/day = **15 minutes saved daily**

---

## Implementation Design

### Visual Design

#### Before (Current)
```
┌────────────────────────────────────────────────┐
│ 🟢 WO-12345  │  ABC Corp  │  Sail Loft        │
│ 🟡 WO-12346  │  XYZ Inc   │  Custom Source    │
│ 🔴 WO-12347  │  Test Co   │  Sail Loft        │
└────────────────────────────────────────────────┘
```

#### After (Proposed)
```
┌──────────────────────────────────────────────────────────────────┐
│ WO-12345 │ ABC Corp │ Sail Loft │ [Regular] Rush  Firm Rush     │
│ WO-12346 │ XYZ Inc  │ Custom    │  Regular [Rush] Firm Rush     │
│ WO-12347 │ Test Co  │ Sail Loft │  Regular  Rush [Firm Rush]    │
└──────────────────────────────────────────────────────────────────┘
                                      ↑ Click to change instantly
```

### UI Component (Button Group)

Three states: **Regular**, **Rush**, **Firm Rush**

```html
<!-- For each work order in queue -->
<div class="priority-controls">
    <div class="btn-group btn-group-sm" role="group">
        <!-- Regular -->
        <button type="button"
                class="btn btn-outline-success {{ 'active' if not wo.RushOrder and not wo.FirmRush }}"
                onclick="updatePriority('{{ wo.WorkOrderNo }}', 'regular')"
                title="Regular Priority">
            Regular
        </button>

        <!-- Rush -->
        <button type="button"
                class="btn btn-outline-warning {{ 'active' if wo.RushOrder and not wo.FirmRush }}"
                onclick="updatePriority('{{ wo.WorkOrderNo }}', 'rush')"
                title="Rush Order">
            Rush
        </button>

        <!-- Firm Rush -->
        <button type="button"
                class="btn btn-outline-danger {{ 'active' if wo.FirmRush }}"
                onclick="updatePriority('{{ wo.WorkOrderNo }}', 'firm_rush')"
                title="Firm Rush - Date Required">
            Firm Rush
        </button>
    </div>
</div>
```

### Color Scheme

| Priority | Color | Bootstrap Class | When Active |
|----------|-------|----------------|-------------|
| Regular | Green | `btn-success` | `!RushOrder && !FirmRush` |
| Rush | Yellow/Orange | `btn-warning` | `RushOrder && !FirmRush` |
| Firm Rush | Red | `btn-danger` | `FirmRush` |

---

## Backend Implementation

### API Endpoint

Create new route in `routes/queue.py`:

```python
@queue_bp.route('/update-priority/<work_order_no>', methods=['POST'])
@login_required
def update_priority(work_order_no):
    """
    Update work order priority from queue view.

    POST body (JSON):
    {
        "priority": "regular" | "rush" | "firm_rush"
    }

    Returns:
        JSON with success status
    """
    try:
        data = request.get_json()
        priority = data.get('priority')

        if priority not in ['regular', 'rush', 'firm_rush']:
            return jsonify({'error': 'Invalid priority'}), 400

        # Get work order
        wo = WorkOrder.query.filter_by(WorkOrderNo=work_order_no).first()
        if not wo:
            return jsonify({'error': 'Work order not found'}), 404

        # Update priority flags
        if priority == 'regular':
            wo.RushOrder = False
            wo.FirmRush = False
        elif priority == 'rush':
            wo.RushOrder = True
            wo.FirmRush = False
        elif priority == 'firm_rush':
            wo.RushOrder = True  # Firm Rush implies Rush
            wo.FirmRush = True

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Updated {work_order_no} to {priority}',
            'priority': priority
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

---

## Frontend Implementation

### JavaScript (templates/queue/list.html)

```javascript
/**
 * Update work order priority via AJAX
 * @param {string} workOrderNo - Work order number
 * @param {string} priority - 'regular', 'rush', or 'firm_rush'
 */
async function updatePriority(workOrderNo, priority) {
    try {
        // Show loading state
        const buttonGroup = event.target.closest('.btn-group');
        const originalButtons = buttonGroup.innerHTML;
        buttonGroup.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        // Send AJAX request
        const response = await fetch(`/cleaning_queue/update-priority/${workOrderNo}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ priority: priority })
        });

        const data = await response.json();

        if (data.success) {
            // Update button states
            updateButtonStates(buttonGroup, priority);

            // Show success message
            showToast('Priority updated successfully', 'success');

            // Optional: Re-sort queue if needed
            // reloadQueue();
        } else {
            // Restore original buttons on error
            buttonGroup.innerHTML = originalButtons;
            showToast('Failed to update priority: ' + data.error, 'error');
        }

    } catch (error) {
        console.error('Error updating priority:', error);
        showToast('Network error updating priority', 'error');
    }
}

/**
 * Update button visual states
 */
function updateButtonStates(buttonGroup, priority) {
    const buttons = buttonGroup.querySelectorAll('button');

    // Remove all active states
    buttons.forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('btn-outline-success', 'btn-outline-warning', 'btn-outline-danger');
        btn.classList.remove('btn-success', 'btn-warning', 'btn-danger');
    });

    // Add active state to selected button
    if (priority === 'regular') {
        buttons[0].classList.add('active', 'btn-success');
        buttons[0].classList.remove('btn-outline-success');
    } else if (priority === 'rush') {
        buttons[1].classList.add('active', 'btn-warning');
        buttons[1].classList.remove('btn-outline-warning');
    } else if (priority === 'firm_rush') {
        buttons[2].classList.add('active', 'btn-danger');
        buttons[2].classList.remove('btn-outline-danger');
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
    `;
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
```

---

## Template Changes

### File: `templates/queue/list.html`

Add priority controls column to the queue table:

```html+jinja
<!-- Current queue item row -->
<div class="queue-item" data-wo-id="{{ wo.WorkOrderNo }}">
    <div class="queue-handle">☰</div>
    <div class="queue-number">{{ loop.index }}</div>
    <div class="queue-content">
        <!-- Existing content: WO number, customer, source, etc. -->
        <div class="wo-number">
            <a href="{{ url_for('work_orders.work_order_detail', work_order_no=wo.WorkOrderNo) }}">
                {{ wo.WorkOrderNo }}
            </a>
        </div>
        <div class="customer-name">{{ wo.customer.Name }}</div>
        <div class="source-badge">
            <span class="badge bg-info">{{ wo.customer_source_name }}</span>
        </div>

        <!-- NEW: Inline Priority Controls -->
        <div class="priority-controls">
            <div class="btn-group btn-group-sm" role="group" aria-label="Priority controls">
                <button type="button"
                        class="btn {% if not wo.RushOrder and not wo.FirmRush %}btn-success{% else %}btn-outline-success{% endif %}"
                        onclick="updatePriority('{{ wo.WorkOrderNo }}', 'regular')"
                        title="Regular Priority">
                    Regular
                </button>
                <button type="button"
                        class="btn {% if wo.RushOrder and not wo.FirmRush %}btn-warning{% else %}btn-outline-warning{% endif %}"
                        onclick="updatePriority('{{ wo.WorkOrderNo }}', 'rush')"
                        title="Rush Order">
                    Rush
                </button>
                <button type="button"
                        class="btn {% if wo.FirmRush %}btn-danger{% else %}btn-outline-danger{% endif %}"
                        onclick="updatePriority('{{ wo.WorkOrderNo }}', 'firm_rush')"
                        title="Firm Rush - Date Required">
                    Firm Rush
                </button>
            </div>
        </div>
    </div>
</div>
```

### CSS Styling

Add to `static/css/style.css`:

```css
/* Priority Controls in Queue */
.priority-controls {
    display: inline-flex;
    align-items: center;
    margin-left: 15px;
}

.priority-controls .btn-group {
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.priority-controls .btn {
    font-size: 0.8rem;
    padding: 0.25rem 0.75rem;
    transition: all 0.2s ease;
}

.priority-controls .btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.15);
}

.priority-controls .btn.active {
    font-weight: 600;
    cursor: default;
}

/* Loading spinner */
.priority-controls .spinner-border {
    width: 1rem;
    height: 1rem;
}

/* Mobile responsive */
@media (max-width: 768px) {
    .priority-controls {
        display: block;
        margin-left: 0;
        margin-top: 10px;
    }

    .priority-controls .btn-group {
        width: 100%;
    }

    .priority-controls .btn {
        flex: 1;
        font-size: 0.75rem;
    }
}
```

---

## Keyboard Shortcuts

Add keyboard shortcuts for power users:

```javascript
// In keyboard-shortcuts.js

// Priority shortcuts (when row is selected)
hotkeys('1', (e) => {
    if (tableNavigator && !tableNavigator.isInputFocused()) {
        e.preventDefault();
        setSelectedRowPriority('regular');
    }
});

hotkeys('2', (e) => {
    if (tableNavigator && !tableNavigator.isInputFocused()) {
        e.preventDefault();
        setSelectedRowPriority('rush');
    }
});

hotkeys('3', (e) => {
    if (tableNavigator && !tableNavigator.isInputFocused()) {
        e.preventDefault();
        setSelectedRowPriority('firm_rush');
    }
});

function setSelectedRowPriority(priority) {
    const selectedRow = document.querySelector('.queue-item.selected');
    if (!selectedRow) return;

    const workOrderNo = selectedRow.dataset.woId;
    updatePriority(workOrderNo, priority);
}
```

**Usage**: Navigate to row with `j`/`k`, then press `1`/`2`/`3` to set priority.

---

## Testing

### Manual Testing

1. Navigate to `/cleaning_queue/cleaning-queue`
2. Find a work order in the queue
3. Click "Rush" button
4. Verify button becomes active (filled yellow)
5. Verify "Regular" and "Firm Rush" are inactive (outlined)
6. Refresh page
7. Verify priority persisted (Rush still active)

### Integration Testing

```python
# tests/test_queue_priority.py

def test_update_priority_to_rush(client, logged_in_admin):
    """Test updating work order priority to rush"""
    # Create test work order
    wo = WorkOrder(WorkOrderNo='TEST-123', CustID='TEST', RushOrder=False, FirmRush=False)
    db.session.add(wo)
    db.session.commit()

    # Update to rush
    response = client.post(
        '/cleaning_queue/update-priority/TEST-123',
        json={'priority': 'rush'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

    # Verify database updated
    wo = WorkOrder.query.filter_by(WorkOrderNo='TEST-123').first()
    assert wo.RushOrder is True
    assert wo.FirmRush is False

def test_update_priority_to_firm_rush(client, logged_in_admin):
    """Test updating work order priority to firm rush"""
    wo = WorkOrder(WorkOrderNo='TEST-124', CustID='TEST', RushOrder=False, FirmRush=False)
    db.session.add(wo)
    db.session.commit()

    response = client.post(
        '/cleaning_queue/update-priority/TEST-124',
        json={'priority': 'firm_rush'}
    )

    assert response.status_code == 200

    # Verify both flags set
    wo = WorkOrder.query.filter_by(WorkOrderNo='TEST-124').first()
    assert wo.RushOrder is True  # Firm Rush implies Rush
    assert wo.FirmRush is True

def test_update_priority_invalid(client, logged_in_admin):
    """Test invalid priority value"""
    wo = WorkOrder(WorkOrderNo='TEST-125', CustID='TEST')
    db.session.add(wo)
    db.session.commit()

    response = client.post(
        '/cleaning_queue/update-priority/TEST-125',
        json={'priority': 'invalid'}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
```

---

## Performance Considerations

### AJAX Call Optimization

- **Optimistic UI Update**: Update button state immediately, rollback on error
- **Debouncing**: Prevent double-clicks with 500ms debounce
- **Batch Updates**: If implementing "Select All + Change Priority"

### Database Impact

- Priority change is a simple UPDATE query on 2 boolean fields
- No cascade updates or triggers affected
- Minimal performance impact

### Network Efficiency

```javascript
// Add debouncing to prevent double-clicks
const updatePriority = debounce(async (workOrderNo, priority) => {
    // ... existing code
}, 500);

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}
```

---

## Rollout Plan

### Phase 1: Backend (15 minutes)
1. Add API endpoint to `routes/queue.py`
2. Test endpoint with curl
3. Deploy to test environment

### Phase 2: Frontend (30 minutes)
1. Update `templates/queue/list.html`
2. Add JavaScript functions
3. Add CSS styling
4. Test locally

### Phase 3: Testing (20 minutes)
1. Write integration tests
2. Manual testing in test environment
3. Verify mobile responsive

### Phase 4: Production (10 minutes)
1. Deploy to production
2. Monitor logs
3. Get user feedback

**Total Time**: ~75 minutes

---

## User Documentation

### For Managers

**Changing Work Order Priority in Queue:**

1. Go to **Queue** page (Ctrl+Shift+5)
2. Find the work order you want to change
3. Click the priority button: **Regular**, **Rush**, or **Firm Rush**
4. The priority updates instantly—no need to save or refresh

**Priority Meanings:**
- **Regular**: Normal processing order
- **Rush**: Expedited processing (yellow indicator)
- **Firm Rush**: Date-critical, highest priority (red indicator)

**Keyboard Shortcuts:**
- Press `j` or `k` to navigate between work orders
- Press `1` for Regular, `2` for Rush, `3` for Firm Rush

### For Users

Users with limited permissions will **not see** the priority controls (read-only queue view).

---

## Accessibility

### Screen Reader Support

```html
<div class="btn-group btn-group-sm" role="group" aria-label="Priority controls for work order {{ wo.WorkOrderNo }}">
    <button type="button"
            class="btn btn-success"
            onclick="updatePriority('{{ wo.WorkOrderNo }}', 'regular')"
            aria-pressed="true"
            aria-label="Set priority to Regular">
        Regular
    </button>
    <!-- ... -->
</div>
```

### Keyboard Navigation

- All buttons are keyboard accessible (Tab to focus, Enter to click)
- Visual focus indicators on all buttons
- Keyboard shortcuts for power users

### Color Blind Friendly

- Don't rely solely on color
- Add icons to priority buttons (optional):
  - Regular: `○`
  - Rush: `◐`
  - Firm Rush: `●`

---

## Future Enhancements

### 1. Bulk Priority Update

Select multiple work orders and change priority at once:

```html
<button onclick="bulkUpdatePriority('rush')">
    Mark Selected as Rush
</button>
```

### 2. Priority Change Log

Track who changed priority and when:

```python
class PriorityChangeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_order_no = db.Column(db.String, db.ForeignKey('tblcustworkorderdetail.workorderno'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    old_priority = db.Column(db.String)
    new_priority = db.Column(db.String)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 3. Date Required Quick Edit

For Firm Rush orders, inline edit for date required:

```html
<input type="date"
       class="form-control form-control-sm"
       value="{{ wo.DateRequired }}"
       onchange="updateDateRequired('{{ wo.WorkOrderNo }}', this.value)">
```

### 4. Priority Suggestions

ML-based priority suggestions:

```javascript
// Show recommendation based on customer history
<span class="badge bg-secondary">
    Suggested: Rush (based on customer history)
</span>
```

---

## Metrics to Track

After deployment, monitor:

1. **Usage**: How many priority changes per day?
2. **Speed**: Average time from click to update (target: <500ms)
3. **Errors**: Failed priority update rate (target: <1%)
4. **User Satisfaction**: Survey: "How satisfied are you with the new priority controls?"

---

## Files to Modify

### Backend
- [ ] `routes/queue.py` - Add `update_priority()` endpoint

### Frontend
- [ ] `templates/queue/list.html` - Add button group HTML
- [ ] `templates/queue/list.html` - Add JavaScript functions
- [ ] `static/css/style.css` - Add priority control styling

### Testing
- [ ] `tests/test_queue_priority.py` - Integration tests

### Documentation
- [ ] Update `CLAUDE.md` with new feature
- [ ] Update user guide with priority controls section

---

## Deployment Command

```bash
# Test locally first
python app.py

# Commit changes
git add routes/queue.py templates/queue/list.html static/css/style.css
git commit -m "Add inline priority controls to queue view"

# Push to GitHub
git push

# Deploy to AWS
eb deploy

# Monitor logs
eb logs --stream
```

---

**Last Updated**: 2025-01-15
**Version**: 1.0
**Estimated Impact**: Saves 15 minutes/day per user, reduces clicks by 75%
**Implementation Time**: 75 minutes
**Author**: Claude (Senior UX Designer)
