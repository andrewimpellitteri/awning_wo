# Caching Implementation Guide

## What's Been Implemented

### Core Setup (Complete)
- ✅ Flask-Caching installed and configured
- ✅ SimpleCache for production/dev (in-memory)
- ✅ NullCache for tests (no caching during tests)
- ✅ Cache utilities in `utils/cache_helpers.py`

### Customer Routes (Complete)
**File:** `routes/customers.py`
- ✅ Cached `get_customer_filter_options()` - 10min cache
- ✅ Cache invalidation in create/edit/delete
- **Savings:** 2 queries eliminated per page load

---

## Recommended Additions

### High Priority (Easy Wins)

#### 1. Source Routes (`routes/source.py`)
Similar to customers - filter dropdowns rarely change.

```python
@cache.memoize(timeout=900)  # 15 minutes
def get_source_filter_options():
    states = db.session.query(Source.SourceState).distinct().all()
    return unique_states

# Invalidate in: create_source(), edit_source(), delete_source()
```

**Impact:** 1-2 queries saved per source list page load

---

#### 2. Dashboard Metrics (`routes/dashboard.py`)
Counts and stats don't need to be real-time.

```python
@cache.memoize(timeout=300)  # 5 minutes
def get_dashboard_counts():
    pending = WorkOrder.query.filter(...).count()
    in_progress = WorkOrder.query.filter(...).count()
    completed_today = WorkOrder.query.filter(...).count()
    return {'pending': pending, 'in_progress': in_progress, ...}

# Invalidate when work orders change
```

**Impact:** 3-5 count queries saved per dashboard load

---

#### 3. Analytics Data (`routes/analytics.py`)
Most expensive - pandas/plotly operations.

```python
@cache.memoize(timeout=1800)  # 30 minutes
def get_revenue_chart_data(date_range):
    df = pd.read_sql(query, db.engine)
    # ... expensive processing ...
    return fig.to_json()

# Invalidate when work orders completed
```

**Impact:** Huge - 2-5 second queries reduced to milliseconds

---

### Medium Priority

#### 4. Work Order Filter Options (`routes/work_orders.py`)
Similar pattern to customers.

```python
@cache.memoize(timeout=600)
def get_work_order_filter_options():
    # Ship-to sources, statuses, etc.
    pass
```

#### 5. Inventory Lookups (`routes/inventory.py`)
If customers have large inventories.

```python
@cache.memoize(timeout=300)
def get_customer_inventory(cust_id):
    return Inventory.query.filter_by(CustID=cust_id).all()
```

---

### Low Priority (Optional)

#### 6. Source Lookups
Frequently accessed but rarely changed.

```python
@cache.memoize(timeout=1800)
def get_source_by_name(source_name):
    return Source.query.filter_by(SSource=source_name).first()
```

#### 7. Queue Summary Stats (`routes/queue.py`)
If summary endpoint is slow.

```python
@cache.memoize(timeout=120)  # 2 minutes - more dynamic
def get_queue_summary():
    # firm_rush_count, rush_count, regular_count
    pass
```

---

## Cache Invalidation Strategy

### When to Invalidate

| Event | Invalidate |
|-------|-----------|
| Customer created/edited/deleted | `invalidate_customer_cache()` |
| Source created/edited/deleted | `invalidate_source_cache()` |
| Work order created/edited/completed | `invalidate_work_order_cache()` |
| Repair order created/edited/completed | `invalidate_repair_order_cache()` |
| Dashboard should refresh | `invalidate_work_order_cache()` |
| Analytics should refresh | `invalidate_analytics_cache()` |

All helpers are in `utils/cache_helpers.py`.

---

## Testing

Caching is automatically disabled in tests (`CACHE_TYPE = "NullCache"`).

To manually test caching in development:

```python
# In Flask shell or route
from extensions import cache

# Check if cached
cached_val = cache.get('some_key')

# Clear specific cache
cache.delete_memoized(get_customer_filter_options)

# Clear all caches
cache.clear()
```

---

## Performance Monitoring

To see cache effectiveness, enable SQLAlchemy query logging:

```python
# In development
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Load page twice - second time should show fewer queries
```

---

## Notes

- **SimpleCache** is in-memory and process-specific
- Cache is cleared on app restart (by design)
- For 8 users and 50MB DB, this is perfect
- If you scale beyond 1 instance, consider Redis (but not needed now)
- Cache timeouts are conservative - adjust based on usage patterns

---

## Quick Reference

```python
# Import in routes
from extensions import cache
from utils.cache_helpers import invalidate_customer_cache

# Cache a function
@cache.memoize(timeout=600)  # seconds
def my_expensive_query():
    return db.session.query(...).all()

# Invalidate when data changes
db.session.commit()
invalidate_customer_cache()
```