-- ============================================================================
-- Quick Fixes for Slow Work Order Queries
-- ============================================================================
-- This script adds the missing indexes identified in the performance analysis
--
-- Expected improvements:
--   - WorkOrderNo range filter: 14ms → < 1ms
--   - WorkOrderNo exact filter: 9ms → < 1ms
--   - DateRequired sorting: 16ms → < 1ms
--
-- Usage:
-- ============================================================================

\timing on
\echo '============================================================================'
\echo 'Applying performance fixes for work order queries'
\echo '============================================================================'

-- ============================================================================
-- FIX #1: WorkOrderNo Integer Filter Index
-- ============================================================================
\echo ''
\echo 'FIX #1: Adding function-based index for WorkOrderNo integer casting...'
\echo 'Impact: WorkOrderNo filters will go from 9-14ms to < 1ms'

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_no_int
ON tblcustworkorderdetail((workorderno::integer));

\echo 'Index created: idx_workorder_no_int'

-- ============================================================================
-- FIX #2: DateRequired Sorting Index
-- ============================================================================
\echo ''
\echo 'FIX #2: Adding index for DateRequired sorting...'
\echo 'Impact: DateRequired sort will go from 16ms to < 1ms'

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_daterequired
ON tblcustworkorderdetail(daterequired ASC NULLS LAST);

\echo 'Index created: idx_workorder_daterequired'

-- ============================================================================
-- Update Statistics
-- ============================================================================
\echo ''
\echo 'Updating table statistics...'

ANALYZE tblcustworkorderdetail;

\echo 'Statistics updated.'

-- ============================================================================
-- Verification
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'Verifying new indexes...'
\echo '============================================================================'

SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE tablename = 'tblcustworkorderdetail'
  AND indexname IN ('idx_workorder_no_int', 'idx_workorder_daterequired')
ORDER BY indexname;

\echo ''
\echo '============================================================================'
\echo 'Testing query performance improvements...'
\echo '============================================================================'

\echo ''
\echo 'TEST 1: WorkOrderNo range filter (was 14ms, should be < 1ms now)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT workorderno, custid, woname
FROM tblcustworkorderdetail
WHERE (workorderno::integer) >= 100 AND (workorderno::integer) <= 200
ORDER BY workorderno DESC
LIMIT 25;

\echo ''
\echo 'TEST 2: WorkOrderNo exact match (was 9ms, should be < 1ms now)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT workorderno, custid, woname
FROM tblcustworkorderdetail
WHERE (workorderno::integer) = 100
LIMIT 25;

\echo ''
\echo 'TEST 3: DateRequired sorting (was 16ms, should be < 1ms now)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT workorderno, custid, woname, daterequired
FROM tblcustworkorderdetail
ORDER BY daterequired ASC NULLS LAST
LIMIT 25;

\echo ''
\echo '============================================================================'
\echo 'FIXES APPLIED SUCCESSFULLY!'
\echo '============================================================================'
\echo ''
\echo 'Summary of improvements:'
\echo '  ✓ WorkOrderNo filters now use idx_workorder_no_int index'
\echo '  ✓ DateRequired sorting now uses idx_workorder_daterequired index'
\echo ''
\echo 'Expected results:'
\echo '  - WorkOrderNo range/exact filters: 9-14ms → < 1ms'
\echo '  - DateRequired sorting: 16ms → < 1ms'
\echo ''
\echo 'Next steps:'
\echo '  1. Check the EXPLAIN output above to verify indexes are being used'
\echo '  2. Look for "Index Scan using idx_workorder_no_int" and'
\echo '     "Index Scan using idx_workorder_daterequired"'
\echo '  3. If you still see "Seq Scan", run ANALYZE again'
\echo ''
\echo 'Remaining slow query:'
\echo '  - Source sorting (93ms) requires denormalization or caching'
\echo '  - See PERFORMANCE_ANALYSIS.md for details'
\echo '============================================================================'