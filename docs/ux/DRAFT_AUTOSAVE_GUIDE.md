# Draft Auto-Save Feature - Implementation Guide

## Overview

The draft auto-save feature prevents data loss by automatically saving form data to the database every 30 seconds. Drafts are **user-specific** and stored in the `work_order_drafts` table in PostgreSQL.

## Architecture

### Components

1. **Database Model**: `models/work_order_draft.py`
   - Stores user-specific drafts with JSON form data
   - Auto-cleanup keeps only 5 most recent drafts per user

2. **API Routes**: `routes/drafts.py`
   - `POST /api/drafts/save` - Save or update draft
   - `GET /api/drafts/list` - List user's drafts
   - `GET /api/drafts/<id>` - Get specific draft
   - `DELETE /api/drafts/<id>` - Delete draft
   - `POST /api/drafts/cleanup` - Manual cleanup

3. **JavaScript Module**: `static/js/draft-autosave.js`
   - Auto-saves every 30 seconds
   - Prompts user to restore on page load
   - Shows save indicator in bottom-right
   - Handles before-unload protection

## Database Schema

```sql
CREATE TABLE work_order_drafts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    draft_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    form_data JSON NOT NULL,
    form_type VARCHAR(50) DEFAULT 'work_order',

    INDEX idx_user_id (user_id),
    INDEX idx_form_type (form_type)
);
```

## Setup Instructions

### 1. Create Database Migration

```bash
# Generate migration
./alembic_db.sh test revision --autogenerate -m "add_work_order_drafts_table"

# Review the migration in alembic/versions/

# Apply to test database
./alembic_db.sh test upgrade head

# Verify it works, then apply to production
./alembic_db.sh prod upgrade head
```

### 2. Add to Existing Form Templates

Add these two lines to any form template (e.g., `templates/work_orders/create.html`):

```html
<!-- Before closing </body> tag -->
<script src="{{ url_for('static', filename='js/draft-autosave.js') }}"></script>
<script>
    // Initialize auto-save for work order form
    DraftAutoSave.init('work_order', '#workOrderForm');

    // Disable auto-save when form is submitted successfully
    document.getElementById('workOrderForm').addEventListener('submit', function() {
        DraftAutoSave.cleanup();  // Deletes draft after successful submit
    });
</script>
```

### 3. For Repair Order Forms

```html
<script src="{{ url_for('static', filename='js/draft-autosave.js') }}"></script>
<script>
    DraftAutoSave.init('repair_order', '#repairOrderForm');

    document.getElementById('repairOrderForm').addEventListener('submit', function() {
        DraftAutoSave.cleanup();
    });
</script>
```

### 4. For Quote Forms

```html
<script src="{{ url_for('static', filename='js/draft-autosave.js') }}"></script>
<script>
    DraftAutoSave.init('quote', '#quoteForm');

    document.getElementById('quoteForm').addEventListener('submit', function() {
        DraftAutoSave.cleanup();
    });
</script>
```

## User Experience Flow

### First-Time Use (No Draft)

1. User opens work order create page
2. Auto-save starts in background
3. Every 30 seconds, form data is saved to database
4. Bottom-right indicator shows: "✓ Draft saved 2 minutes ago"
5. User submits form → Draft is deleted

### Returning User (Draft Exists)

1. User opens work order create page
2. Prompt appears: "Found a saved draft from 10 minutes ago. Would you like to restore it?"
3. User clicks OK → All form fields are populated from draft
4. User continues editing
5. User submits → Draft is deleted

### Browser Crash Recovery

1. User is filling out form for 10 minutes
2. Browser crashes
3. User reopens browser and navigates to form
4. Prompt appears: "Found a saved draft from 2 minutes ago. Would you like to restore it?"
5. User clicks OK → All data is restored (only lost last 30 seconds)

## API Usage

### Save Draft (Automatic)

```javascript
// Automatically called every 30 seconds by DraftAutoSave.js
fetch('/api/drafts/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        form_type: 'work_order',
        form_data: {
            CustID: '12345',
            WOName: 'Test Order',
            DateIn: '2025-01-15',
            // ... all form fields
        },
        draft_id: 123  // Optional: for updating existing draft
    })
})
```

### List User's Drafts

```bash
curl -X GET "http://localhost:5000/api/drafts/list?form_type=work_order&limit=5" \
  -H "Cookie: session=..."
```

Response:
```json
{
    "success": true,
    "drafts": [
        {
            "id": 123,
            "user_id": 1,
            "form_type": "work_order",
            "created_at": "2025-01-15T10:30:00",
            "updated_at": "2025-01-15T10:32:00",
            "form_data": { ... }
        }
    ]
}
```

### Delete Draft

```bash
curl -X DELETE "http://localhost:5000/api/drafts/123" \
  -H "Cookie: session=..."
```

## Configuration

Edit `static/js/draft-autosave.js` to customize:

```javascript
const CONFIG = {
    AUTOSAVE_INTERVAL: 30000,  // 30 seconds (change to 60000 for 1 minute)
    API_ENDPOINT: '/api/drafts',
    DEBOUNCE_DELAY: 1000,      // Wait time after last change
};
```

## Manual API Operations

### Trigger Manual Save

```javascript
// Force immediate save (useful for "Save Draft" button)
DraftAutoSave.manualSave();
```

### Disable Auto-Save Temporarily

```javascript
// Stop auto-saving (e.g., during file upload)
DraftAutoSave.disable();

// Re-enable
DraftAutoSave.enable();
```

### Check Save Status

```javascript
// Check if form has unsaved changes
if (DraftAutoSave.isDirty) {
    console.log('Form has unsaved changes');
}

// Get last save time
console.log('Last saved:', DraftAutoSave.lastSaveTime);
```

## Cleanup & Maintenance

### Automatic Cleanup

The system automatically keeps only the **5 most recent drafts** per user. Old drafts are deleted when new ones are created.

### Manual Cleanup (Admin)

Run cleanup for all users:

```python
# In Flask shell or cron job
from models.work_order_draft import WorkOrderDraft
from models.user import User

users = User.query.all()
for user in users:
    deleted = WorkOrderDraft.cleanup_old_drafts(user.id, keep_most_recent=5)
    print(f"User {user.username}: deleted {deleted} old drafts")
```

Or via API endpoint:

```bash
curl -X POST "http://localhost:5000/api/drafts/cleanup" \
  -H "Cookie: session=..."
```

### Database Cleanup Query

Remove all drafts older than 30 days:

```sql
DELETE FROM work_order_drafts
WHERE updated_at < NOW() - INTERVAL '30 days';
```

## Troubleshooting

### Draft Not Saving

1. Check browser console for errors
2. Verify user is logged in (`current_user` available)
3. Check network tab for failed API calls
4. Verify database connection

### Draft Not Restoring

1. Check if `form_data` JSON matches form field names
2. Verify form ID matches selector (`#workOrderForm`)
3. Check for JavaScript errors in console

### Performance Issues

If auto-save is slow with large forms:

1. Increase `AUTOSAVE_INTERVAL` to 60 seconds
2. Add indexes on `work_order_drafts` table:
   ```sql
   CREATE INDEX idx_drafts_user_updated ON work_order_drafts(user_id, updated_at DESC);
   ```

## Testing

### Manual Testing

1. Open work order create page
2. Fill in some fields
3. Wait 30 seconds (watch console logs)
4. Refresh page
5. Should see prompt to restore draft
6. Click OK
7. Verify all fields are populated

### Integration Testing

```python
# tests/test_drafts.py
def test_save_draft(client, logged_in_user):
    response = client.post('/api/drafts/save', json={
        'form_type': 'work_order',
        'form_data': {'CustID': '12345', 'WOName': 'Test'}
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'draft_id' in data

def test_list_drafts(client, logged_in_user):
    # Create a draft first
    client.post('/api/drafts/save', json={
        'form_type': 'work_order',
        'form_data': {'CustID': '12345'}
    })

    # List drafts
    response = client.get('/api/drafts/list?form_type=work_order')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert len(data['drafts']) > 0
```

## Security Considerations

✅ **User Isolation**: Drafts are tied to `user_id` via foreign key
✅ **Authentication**: All endpoints require `@login_required`
✅ **Authorization**: Users can only access their own drafts
✅ **Cascade Delete**: Drafts auto-delete when user is deleted
✅ **Rate Limiting**: Consider adding to prevent abuse

### Add Rate Limiting (Optional)

```python
# In routes/drafts.py
from flask_limiter import Limiter

limiter = Limiter(key_func=lambda: current_user.id)

@drafts_bp.route("/save", methods=["POST"])
@login_required
@limiter.limit("60/minute")  # Max 60 saves per minute
def save_draft():
    # ... existing code
```

## Future Enhancements

### 1. Named Drafts

Allow users to name their drafts:

```javascript
DraftAutoSave.init('work_order', '#workOrderForm', {
    draftName: 'Rush Order - ABC Corp'
});
```

### 2. Draft Manager UI

Create a page to view/manage all drafts:

```
/drafts
  - List all drafts with preview
  - Search by customer name
  - Delete multiple drafts
  - Open draft in form
```

### 3. Real-Time Sync (Advanced)

Use WebSockets for multi-device sync:

```javascript
// Save draft on Device A
// → WebSocket broadcast
// → Device B shows "Draft updated on another device"
```

### 4. Offline Support

Use Service Workers + IndexedDB:

```javascript
// Save to IndexedDB when offline
// Sync to server when back online
```

## Deployment Checklist

- [ ] Create migration file
- [ ] Apply migration to test database
- [ ] Test auto-save functionality
- [ ] Apply migration to production
- [ ] Deploy code with `eb deploy`
- [ ] Test in production environment
- [ ] Monitor logs for errors
- [ ] Set up cleanup cron job (optional)

## Files Modified/Created

### New Files
- `models/work_order_draft.py` - Database model
- `routes/drafts.py` - API endpoints
- `static/js/draft-autosave.js` - Client-side logic
- `DRAFT_AUTOSAVE_GUIDE.md` - This documentation

### Modified Files
- `app.py` - Register drafts blueprint
- `models/__init__.py` - Import WorkOrderDraft
- `templates/work_orders/create.html` - Add autosave script (to be done)
- `templates/repair_orders/create.html` - Add autosave script (to be done)

## Support

For issues or questions:
1. Check browser console for errors
2. Check Flask logs: `eb logs --stream`
3. Verify database migration applied
4. Test API endpoints with curl

---

**Last Updated**: 2025-01-15
**Version**: 1.0
**Author**: Claude (Senior UX Designer)
