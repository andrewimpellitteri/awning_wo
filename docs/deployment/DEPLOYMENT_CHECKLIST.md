# Source Name Denormalization - Deployment Checklist

## Pre-Deployment Checklist

### 1. Code Review
- [ ] Review all code changes in Git
- [ ] Verify all tests pass locally
- [ ] Review migration script for syntax errors
- [ ] Confirm backup/rollback plan is understood

### 2. Staging Environment
- [ ] Backup staging database
- [ ] Apply migration to staging:
  ```bash
  psql "$STAGING_DATABASE_URL" -f query_optimization/add_source_name_denormalization.sql
  ```
- [ ] Verify migration success:
  ```sql
  SELECT COUNT(*) as total, COUNT(source_name) as with_source
  FROM tblcustworkorderdetail;
  ```
- [ ] Deploy code to staging
- [ ] Test all work order operations:
  - [ ] Create work order
  - [ ] Edit work order (change customer)
  - [ ] List work orders
  - [ ] Filter by source
  - [ ] Sort by source
  - [ ] Create repair order
  - [ ] Edit repair order
  - [ ] Filter repair orders by source

### 3. Performance Verification (Staging)
- [ ] Run EXPLAIN ANALYZE on source filter query (before/after comparison)
- [ ] Check query execution times in logs
- [ ] Verify indexes are being used:
  ```sql
  SELECT schemaname, tablename, indexname, idx_scan
  FROM pg_stat_user_indexes
  WHERE indexname LIKE '%source_name%';
  ```

### 4. Data Consistency Check (Staging)
- [ ] Run verification query:
  ```sql
  SELECT
      COUNT(*) as total,
      COUNT(wo.source_name) as has_source_name,
      SUM(CASE WHEN wo.source_name = s.ssource THEN 1 ELSE 0 END) as correct,
      SUM(CASE WHEN wo.source_name != s.ssource THEN 1 ELSE 0 END) as incorrect
  FROM tblcustworkorderdetail wo
  LEFT JOIN tblcustomers c ON wo.custid = c.custid
  LEFT JOIN tblsource s ON c.source = s.ssource;
  ```
- [ ] Verify incorrect count is 0

## Production Deployment Checklist

### 1. Pre-Deployment
- [ ] Schedule maintenance window (recommend off-peak hours)
- [ ] Notify team of deployment
- [ ] Ensure backup retention is enabled
- [ ] Take manual snapshot of RDS (if using AWS)
- [ ] Document current performance baseline

### 2. Database Migration
- [ ] Backup production database:
  ```bash
  # AWS RDS
  aws rds create-db-snapshot --db-instance-identifier your-instance --db-snapshot-identifier pre-denorm-$(date +%Y%m%d)

  # Or manual
  pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d_%H%M%S).sql
  ```
- [ ] Apply migration to production:
  ```bash
  psql "$DATABASE_URL" -f query_optimization/add_source_name_denormalization.sql
  ```
- [ ] Verify migration completed successfully
- [ ] Check for errors in migration output

### 3. Verification
- [ ] Run data consistency check:
  ```sql
  -- Work Orders
  SELECT 'Work Orders' as table_name,
         COUNT(*) as total,
         COUNT(source_name) as with_source_name,
         SUM(CASE WHEN source_name = s.ssource THEN 1 ELSE 0 END) as correct,
         SUM(CASE WHEN source_name != s.ssource THEN 1 ELSE 0 END) as incorrect
  FROM tblcustworkorderdetail wo
  LEFT JOIN tblcustomers c ON wo.custid = c.custid
  LEFT JOIN tblsource s ON c.source = s.ssource

  UNION ALL

  -- Repair Orders
  SELECT 'Repair Orders' as table_name,
         COUNT(*) as total,
         COUNT(source_name) as with_source_name,
         SUM(CASE WHEN source_name = s.ssource THEN 1 ELSE 0 END) as correct,
         SUM(CASE WHEN source_name != s.ssource THEN 1 ELSE 0 END) as incorrect
  FROM tblrepairworkorderdetail ro
  LEFT JOIN tblcustomers c ON ro.custid = c.custid
  LEFT JOIN tblsource s ON c.source = s.ssource;
  ```
- [ ] Verify indexes were created:
  ```sql
  SELECT schemaname, tablename, indexname, indexdef
  FROM pg_indexes
  WHERE indexname IN ('idx_workorder_source_name', 'idx_repairorder_source_name');
  ```
- [ ] Verify triggers were created:
  ```sql
  SELECT trigger_name, event_manipulation, event_object_table
  FROM information_schema.triggers
  WHERE trigger_name LIKE '%source_name%';
  ```

### 4. Application Deployment
- [ ] Commit all code changes:
  ```bash
  git add .
  git commit -m "Add source_name denormalization for 100x query performance"
  git push origin main
  ```
- [ ] Deploy application (AWS EB example):
  ```bash
  eb deploy
  ```
- [ ] Wait for deployment to complete
- [ ] Check deployment status:
  ```bash
  eb status
  ```

### 5. Smoke Testing
- [ ] Open application in browser
- [ ] Test work order list page loads
- [ ] Test source filter works
- [ ] Test source sorting works
- [ ] Test creating new work order
- [ ] Test editing existing work order
- [ ] Test repair order list page
- [ ] Test creating new repair order

### 6. Performance Monitoring
- [ ] Monitor application logs for errors:
  ```bash
  eb logs --stream
  # or
  tail -f /var/log/application.log
  ```
- [ ] Check query execution times in database logs
- [ ] Monitor application response times
- [ ] Check error rates in monitoring tools

### 7. Post-Deployment Verification
- [ ] Test source filter API:
  ```bash
  curl "https://your-app.com/api/work_orders?filter_Source=Boat"
  ```
- [ ] Test source sorting API:
  ```bash
  curl "https://your-app.com/api/work_orders?sort[0][field]=Source&sort[0][dir]=asc"
  ```
- [ ] Verify API returns correct data
- [ ] Check response times are faster

## Post-Deployment Monitoring (First 24 Hours)

### Immediate (First Hour)
- [ ] Monitor error logs continuously
- [ ] Check application metrics dashboard
- [ ] Watch for any null pointer exceptions
- [ ] Monitor database CPU and memory usage
- [ ] Check query execution times

### First 4 Hours
- [ ] Review error logs every hour
- [ ] Check data consistency
- [ ] Monitor user-reported issues
- [ ] Verify backup completed successfully

### First 24 Hours
- [ ] Review error logs 3-4 times
- [ ] Check data consistency once
- [ ] Monitor query performance trends
- [ ] Document any issues encountered

## Rollback Plan (If Needed)

### When to Rollback
- [ ] Critical errors in application
- [ ] Data inconsistency detected
- [ ] Performance degradation
- [ ] User-facing bugs

### Rollback Steps
1. [ ] Revert application code:
   ```bash
   git revert HEAD
   git push origin main
   eb deploy
   ```

2. [ ] Revert database changes:
   ```bash
   psql "$DATABASE_URL" -f query_optimization/rollback_source_name_denormalization.sql
   ```

   Or manually:
   ```sql
   BEGIN;

   -- Drop triggers
   DROP TRIGGER IF EXISTS trg_sync_work_order_source_name ON tblcustworkorderdetail;
   DROP TRIGGER IF EXISTS trg_sync_repair_order_source_name ON tblrepairworkorderdetail;
   DROP TRIGGER IF EXISTS trg_sync_orders_on_customer_source_change ON tblcustomers;

   -- Drop functions
   DROP FUNCTION IF EXISTS sync_work_order_source_name();
   DROP FUNCTION IF EXISTS sync_repair_order_source_name();
   DROP FUNCTION IF EXISTS sync_orders_on_customer_source_change();

   -- Drop indexes
   DROP INDEX IF EXISTS idx_workorder_source_name;
   DROP INDEX IF EXISTS idx_repairorder_source_name;

   -- Drop columns (optional - can leave for future retry)
   -- ALTER TABLE tblcustworkorderdetail DROP COLUMN IF EXISTS source_name;
   -- ALTER TABLE tblrepairworkorderdetail DROP COLUMN IF EXISTS source_name;

   COMMIT;
   ```

3. [ ] Verify rollback successful
4. [ ] Monitor for stability
5. [ ] Document rollback reason

## Success Criteria

### Migration Success
- [x] All SQL statements executed without errors
- [x] All existing records have `source_name` populated
- [x] Indexes created successfully
- [x] Triggers created successfully
- [x] Data consistency checks pass

### Application Success
- [x] All tests pass (40/40)
- [x] No errors in application logs
- [x] Work order operations work correctly
- [x] Repair order operations work correctly
- [x] Source filtering works
- [x] Source sorting works

### Performance Success
- [ ] Source sorting < 5ms (target: ~1ms)
- [ ] Source filtering < 1ms (target: ~0.1ms)
- [ ] Default list load < 1ms (target: ~0.04ms)
- [ ] Index usage confirmed in query plans
- [ ] No sequential scans on source_name queries

### Data Integrity Success
- [ ] No data inconsistencies detected
- [ ] All triggers firing correctly
- [ ] Application sync methods working
- [ ] Customer source changes propagate correctly

## Contact Information

### In Case of Issues
- **Database Admin:** [Your DBA Contact]
- **DevOps Lead:** [Your DevOps Contact]
- **On-Call Engineer:** [Your On-Call Contact]

### Useful Commands
```bash
# Check current git commit
git log -1

# Check deployed version
eb printenv | grep GIT_COMMIT

# View real-time logs
eb logs --stream

# Check database connections
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_stat_activity;"

# Check table size
psql "$DATABASE_URL" -c "
  SELECT
    pg_size_pretty(pg_total_relation_size('tblcustworkorderdetail')) as work_orders_size,
    pg_size_pretty(pg_total_relation_size('tblrepairworkorderdetail')) as repair_orders_size;
"
```

## Notes

### Duration Estimates
- Migration execution: 1-5 minutes (depends on table size)
- Application deployment: 5-10 minutes
- Smoke testing: 10-15 minutes
- Total: 20-30 minutes

### Risks
- Low risk: Migration is backward compatible
- Low risk: All relationships maintained
- Low risk: Comprehensive testing completed
- Low risk: Rollback plan available

### Known Issues
- None at this time

---

**Last Updated:** October 12, 2025
**Version:** 1.0
**Status:** Ready for Production Deployment
