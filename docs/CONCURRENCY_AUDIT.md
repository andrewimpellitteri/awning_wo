# Concurrency & Race Condition Audit Report

**Date:** 2025-10-12
**Application:** Awning Work Order Management System
**Target Load:** 8 concurrent users on AWS Elastic Beanstalk

---

## Executive Summary

This audit identified **11 distinct concurrency issues** in the Flask application, ranging from critical race conditions in ID generation to architectural concerns with global state management. The application is generally well-structured with good practices, but several issues could cause data corruption or inconsistent behavior under concurrent load.

### Issue Breakdown
- 🔴 **Critical (4):** Race conditions that can cause data corruption
- 🟡 **High Priority (3):** Architectural issues affecting consistency
- 🟠 **Medium Priority (4):** Potential data loss or inconsistency scenarios

---

## 🔴 Critical Issues

### 1. Race Condition: Work Order Number Generation
**Impact:** Duplicate work order numbers under concurrent load
**Location:** `routes/work_orders.py:355-358`
**Affected Operations:** Creating new work orders

**Current Code:**
```python
latest_num = db.session.query(func.max(cast(WorkOrder.WorkOrderNo, Integer))).scalar()
next_wo_no = str(latest_num + 1) if latest_num is not None else "1"
```

**Problem:** Two simultaneous requests can retrieve the same max value and attempt to create work orders with identical numbers.

**Solution:**
- Add UNIQUE constraint to `WorkOrderNo` in database
- Implement retry logic with IntegrityError handling
- Use database sequences or serial columns

---

### 2. Race Condition: Customer ID Generation
**Impact:** Duplicate customer IDs
**Location:** `routes/customers.py:220-223`
**Affected Operations:** Creating new customers

**Current Code:**
```python
max_cust_id = db.session.query(func.max(cast(Customer.CustID, Integer))).scalar()
new_cust_id = str(max_cust_id + 1) if max_cust_id else "1"
```

**Problem:** Same read-then-increment race condition as work orders.

**Solution:** Same as Issue #1

---

### 3. Race Condition: Repair Order Number Generation
**Impact:** Duplicate repair order numbers
**Location:** `routes/repair_order.py:366-377`
**Affected Operations:** Creating new repair orders

**Current Code:**
```python
latest_order = RepairWorkOrder.query.order_by(desc(RepairWorkOrder.RepairOrderNo)).first()
if latest_order:
    try:
        next_num = int(latest_order.RepairOrderNo) + 1
    except ValueError:
        next_num = int(datetime.now().timestamp())
else:
    next_num = 1
```

**Problem:** Same pattern - vulnerable to concurrent creation.

**Solution:** Same as Issue #1

---

### 4. Race Condition: Queue Position Updates
**Impact:** Conflicting queue position assignments
**Location:** `routes/queue.py:481-493`
**Affected Operations:** Manual queue reordering

**Current Code:**
```python
for index, wo_id in enumerate(work_order_ids):
    work_order = WorkOrder.query.filter_by(WorkOrderNo=wo_id).first()
    work_order.QueuePosition = start_position + index
db.session.commit()
```

**Problem:** Two users reordering simultaneously can create position conflicts.

**Solution:**
- Use `SELECT FOR UPDATE` (pessimistic locking)
- Add version column for optimistic locking
- Add mutex/lock for queue operations

---

## 🟡 High Priority Issues

### 5. Global Mutable State: ML Model
**Impact:** Inconsistent predictions, model update race conditions
**Location:** `routes/ml.py:49-50`
**Affected Operations:** ML predictions, model retraining

**Current Code:**
```python
current_model = None
model_metadata = {}
```

**Problem:**
- Global variables shared across requests in same worker
- No synchronization during updates
- Each Gunicorn worker has different model state
- Race conditions during concurrent predictions and retraining

**Solution:**
- Use threading.Lock for model updates
- Store model in Redis or shared storage
- Load model on worker startup
- Implement proper multi-worker coordination

---

### 6. Weak Authentication: ML Cron Endpoint
**Impact:** Unauthorized model retraining
**Location:** `routes/ml.py:704-712`
**Affected Operations:** Automated ML model retraining

**Current Code:**
```python
secret = request.headers.get("X-Cron-Secret") or (request.json or {}).get("secret")
expected_secret = os.getenv("CRON_SECRET", "your-secret-key")
if secret != expected_secret:
    return jsonify({"error": "Unauthorized"}), 401
```

**Problem:** Only header-based secret, no additional protection

**Solution:**
- Add IP whitelist for cron jobs
- Implement rate limiting
- Use request signing with timestamp
- Consider AWS EventBridge with IAM

---

### 7. Missing Transaction Boundaries
**Impact:** Partial updates on failure
**Location:** Multiple routes (e.g., `repair_order.py:661-663`)
**Affected Operations:** Repair order item updates

**Current Code:**
```python
RepairWorkOrderItem.query.filter_by(RepairOrderNo=repair_order_no).delete()
# ... then add new items
```

**Problem:** If process fails after delete but before adding new items, data is lost.

**Solution:**
- Use explicit `db.session.begin_nested()` for savepoints
- Ensure atomic delete+insert operations
- Add proper rollback on any exception

---

## 🟠 Medium Priority Issues

### 8. Inventory Quantity Race Condition
**Impact:** Lost inventory updates
**Location:** `routes/work_orders.py:624-630`
**Affected Operations:** Adding new items to catalog

**Current Code:**
```python
current_catalog_qty = safe_int_conversion(existing_inventory.Qty)
new_catalog_qty = current_catalog_qty + work_order_qty
existing_inventory.Qty = str(new_catalog_qty)
```

**Problem:** Read-modify-write without locking; concurrent additions lose updates

**Solution:** Use atomic SQL update
```python
db.session.query(Inventory).filter_by(
    InventoryKey=key
).update({
    Inventory.Qty: Inventory.Qty + work_order_qty
})
```

---

### 9. Cache Invalidation Timing
**Impact:** Stale cache on commit failure
**Location:** `routes/customers.py:259, 328, 372`
**Affected Operations:** Customer create/update/delete

**Current Pattern:**
```python
db.session.commit()
invalidate_customer_cache()  # After commit
```

**Problem:** If commit fails after cache invalidation is called (in exception handler), cache is unnecessarily cleared.

**Solution:** Invalidate only after successful commit (current code is actually correct, but add explicit error handling)

---

### 10. File Upload Transaction Coordination
**Impact:** Orphaned S3 files on database failure
**Location:** `utils/file_upload.py`
**Affected Operations:** Work order and repair order file uploads

**Problem:** S3 upload happens before database commit. If commit fails, S3 files remain orphaned.

**Solution:**
- Upload to S3 AFTER database commit succeeds
- Implement cleanup job for orphaned files
- Use two-phase commit pattern
- Store files locally first, upload async

---

### 11. Backlink Update Race Condition
**Impact:** Unexpected overwrite of repair-to-work-order links
**Location:** `routes/work_orders.py:422-433`
**Affected Operations:** Linking work orders to repair orders

**Current Code:**
```python
if see_repair and see_repair.strip():
    referenced_repair = RepairWorkOrder.query.filter_by(
        RepairOrderNo=see_repair.strip()
    ).first()
    if referenced_repair:
        referenced_repair.SEECLEAN = next_wo_no
```

**Problem:** Two work orders linking to same repair simultaneously can cause last-write-wins.

**Solution:**
- Use optimistic locking with version column
- Add validation for conflicting links
- Consider link table instead of direct foreign keys

---

## ✅ Good Practices Found

1. **Proper exception handling** with `db.session.rollback()`
2. **Connection pool configuration** - `pool_size=10`, `max_overflow=20`
3. **Pool pre-ping** enabled to prevent stale connections
4. **Connection recycling** at 300s
5. **CSRF protection** enabled
6. **Role-based access control** with decorators
7. **Eager loading** with `joinedload()` prevents N+1 queries
8. **Denormalized data** (`source_name`) for performance
9. **Inventory as "static catalog only"** avoids complex stock management races

---

## Configuration Review

### Current Database Pool Settings (`config.py`)
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20,
}
```

**Assessment:** ✅ Excellent for 8 concurrent users
- 10 persistent connections + 20 overflow = 30 max connections
- Well-sized for 8 users with buffer

### Cache Configuration (`config.py`)
```python
CACHE_TYPE = "SimpleCache"  # In-memory, thread-safe
CACHE_DEFAULT_TIMEOUT = 300
```

**Assessment:** ⚠️ Not ideal for multi-worker deployment
- `SimpleCache` is thread-safe but NOT process-safe
- Each Gunicorn worker has separate cache
- Cache invalidation only affects one worker

**Recommendation:** Use Redis for production
```python
CACHE_TYPE = "redis"
CACHE_REDIS_URL = "redis://localhost:6379/0"
```

### Session Configuration
```python
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
SESSION_COOKIE_SECURE = FLASK_ENV == "production"
SESSION_COOKIE_HTTPONLY = True
```

**Assessment:** ✅ Good security practices

---

## Recommended Action Plan

### Phase 1: Critical Fixes (Week 1)
1. Add UNIQUE constraints to database schema
2. Implement retry logic for ID generation
3. Add threading.Lock to ML model updates
4. Use SELECT FOR UPDATE for queue operations

### Phase 2: High Priority (Week 2)
1. Migrate to Redis cache
2. Strengthen cron endpoint security
3. Add explicit transaction boundaries
4. Implement ML model coordination across workers

### Phase 3: Medium Priority (Week 3-4)
1. Fix inventory atomic updates
2. Improve file upload transaction handling
3. Add optimistic locking for backlinks
4. Implement orphaned file cleanup job

---

## Testing Recommendations

### Load Testing
```bash
# Apache Bench - 100 requests, 8 concurrent
ab -n 100 -c 8 -p form_data.json -T application/json \
   http://your-app/work_orders/new

# Check for duplicate IDs
psql -c "SELECT workorderno, COUNT(*) FROM tblcustworkorderdetail
         GROUP BY workorderno HAVING COUNT(*) > 1;"
```

### Locust Test Script
```python
from locust import HttpUser, task, between

class WorkOrderUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def create_work_order(self):
        self.client.post("/work_orders/new", json={...})

    @task(1)
    def reorder_queue(self):
        self.client.post("/cleaning_queue/api/cleaning-queue/reorder", json={...})
```

### Monitor for Issues
- Database: Look for duplicate primary keys in logs
- Connection pool: Watch for pool exhaustion warnings
- ML predictions: Compare predictions across multiple requests
- Queue: Check for position conflicts

---

## Database Schema Additions Needed

```sql
-- Add unique constraints
ALTER TABLE tblcustworkorderdetail
  ADD CONSTRAINT uk_workorderno UNIQUE (workorderno);

ALTER TABLE tblcustomers
  ADD CONSTRAINT uk_custid UNIQUE (custid);

ALTER TABLE tblrepairworkorder
  ADD CONSTRAINT uk_repairorderno UNIQUE (repairorderno);

-- Add version column for optimistic locking (optional)
ALTER TABLE tblcustworkorderdetail
  ADD COLUMN version INTEGER DEFAULT 0;

ALTER TABLE tblrepairworkorder
  ADD COLUMN version INTEGER DEFAULT 0;
```

---

## Gunicorn Configuration

**Recommended `gunicorn.conf.py`:**
```python
workers = 3  # CPU cores
threads = 2  # 3 * 2 = 6 concurrent handlers
worker_class = 'gthread'
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
```

**Total capacity:** 6 concurrent request handlers for 8 users = ✅ Adequate

---

## Conclusion

The application has a solid foundation with good database configuration and security practices. The main concerns are:

1. **ID generation race conditions** - highest priority, can cause immediate data corruption
2. **Global ML model state** - architectural issue affecting prediction consistency
3. **Multi-worker cache coordination** - causes stale data across workers

For 8 concurrent users, these issues are **manageable but should be fixed** to prevent:
- Duplicate order numbers (confusing for staff)
- Inconsistent ML predictions (erodes trust in system)
- Stale cached data (customer sees old information)

**Estimated effort:** 2-3 weeks for comprehensive fixes across all priority levels.

**Risk assessment:**
- **Without fixes:** Medium risk - issues will surface occasionally under load
- **With Phase 1 fixes:** Low risk - critical data integrity issues resolved
- **With all phases:** Very low risk - production-ready for concurrent users
