-- ============================================================================
-- EXPLAIN ANALYZE for Repair Order List Queries
-- ============================================================================
-- This script analyzes the performance of repair order list queries
-- ============================================================================

\timing on
\echo '============================================================================'
\echo 'Repair Order List Query Performance Analysis'
\echo '============================================================================'

-- ============================================================================
-- 1. BASELINE: Simple repair order list (default sort)
-- ============================================================================
\echo ''
\echo '1. BASELINE: Simple list with default sort (first 25 records)'
\echo '   Route: /api/repair_work_orders?page=1&size=25'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
ORDER BY datein DESC, repairorderno DESC
LIMIT 25 OFFSET 0;

-- ============================================================================
-- 2. COUNT QUERY: Total count (pagination)
-- ============================================================================
\echo ''
\echo '2. COUNT: Total repair orders (for pagination)'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT COUNT(*) FROM tblrepairworkorderdetail;

-- ============================================================================
-- 3. WITH CUSTOMER JOIN: Eager load customer
-- ============================================================================
\echo ''
\echo '3. WITH CUSTOMER JOIN: Load with customer data'
\echo '   Route: /api/repair_work_orders (with customer)'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    ro.repairorderno,
    ro.custid,
    ro.roname,
    ro.datein,
    ro.datecompleted,
    c.custid as c_custid,
    c.name as c_name
FROM tblrepairworkorderdetail ro
LEFT JOIN tblcustomers c ON ro.custid = c.custid
ORDER BY ro.datein DESC, ro.repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 4. WITH SOURCE JOIN: Including source information
-- ============================================================================
\echo ''
\echo '4. WITH SOURCE JOIN: Including source information'
\echo '   Route: /api/repair_work_orders?filter_Source=X or sort by Source'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    ro.repairorderno,
    ro.custid,
    ro.roname,
    ro.datein,
    ro.datecompleted,
    c.name as c_name,
    s.ssource
FROM tblrepairworkorderdetail ro
LEFT JOIN tblcustomers c ON ro.custid = c.custid
LEFT JOIN tblsource s ON c.source = s.ssource
ORDER BY ro.datein DESC, ro.repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 5. PENDING FILTER: Incomplete repair orders
-- ============================================================================
\echo ''
\echo '5. PENDING FILTER: Incomplete repair orders'
\echo '   Route: /api/repair_work_orders?status=pending'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE datecompleted IS NULL
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- With count
\echo ''
\echo '   Count for pending:'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT COUNT(*) FROM tblrepairworkorderdetail WHERE datecompleted IS NULL;

-- ============================================================================
-- 6. COMPLETED FILTER
-- ============================================================================
\echo ''
\echo '6. COMPLETED FILTER: Completed repair orders'
\echo '   Route: /api/repair_work_orders?status=completed'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE datecompleted IS NOT NULL
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 7. RUSH ORDERS FILTER
-- ============================================================================
\echo ''
\echo '7. RUSH ORDERS: Rush orders that are incomplete'
\echo '   Route: /api/repair_work_orders?status=rush'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE (rushorder = true OR firmrush = true)
  AND datecompleted IS NULL
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 8. GLOBAL SEARCH: Search across multiple fields
-- ============================================================================
\echo ''
\echo '8. GLOBAL SEARCH: Search for "test"'
\echo '   Route: /api/repair_work_orders?search=test'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE repairorderno ILIKE '%test%'
   OR custid ILIKE '%test%'
   OR roname ILIKE '%test%'
   OR "ITEM TYPE" ILIKE '%test%'
   OR "TYPE OF REPAIR" ILIKE '%test%'
   OR location ILIKE '%test%'
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 9. REPAIRORDERNO FILTER: Exact match
-- ============================================================================
\echo ''
\echo '9. REPAIRORDERNO FILTER: Filter by repair order number'
\echo '   Route: /api/repair_work_orders?filter_RepairOrderNo=100'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE repairorderno = '100'
LIMIT 25;

-- ============================================================================
-- 10. CUSTID FILTER: Filter by customer ID
-- ============================================================================
\echo ''
\echo '10. CUSTID FILTER: Filter by customer ID'
\echo '   Route: /api/repair_work_orders?filter_CustID=123'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE custid = '123'
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 11. RONAME FILTER: Text search in ROName
-- ============================================================================
\echo ''
\echo '11. RONAME FILTER: Text search in ROName'
\echo '   Route: /api/repair_work_orders?filter_ROName=test'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
WHERE roname ILIKE '%test%'
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 12. SOURCE FILTER: Filter by source (with joins)
-- ============================================================================
\echo ''
\echo '12. SOURCE FILTER: Filter by source name'
\echo '   Route: /api/repair_work_orders?filter_Source=Smith'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    ro.repairorderno,
    ro.custid,
    ro.roname,
    ro.datein,
    ro.datecompleted,
    s.ssource
FROM tblrepairworkorderdetail ro
LEFT JOIN tblcustomers c ON ro.custid = c.custid
LEFT JOIN tblsource s ON c.source = s.ssource
WHERE s.ssource ILIKE '%Smith%'
ORDER BY ro.datein DESC, ro.repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 13. SORT BY DATEIN: Date sorting (descending)
-- ============================================================================
\echo ''
\echo '13. SORT BY DATEIN: Sort by date in (default sort)'
\echo '   Route: /api/repair_work_orders?sort[0][field]=DateIn&sort[0][dir]=desc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
ORDER BY datein DESC, repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 14. SORT BY DATECOMPLETED: Date completed sorting
-- ============================================================================
\echo ''
\echo '14. SORT BY DATECOMPLETED: Sort by date completed'
\echo '   Route: /api/repair_work_orders?sort[0][field]=DateCompleted&sort[0][dir]=desc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
ORDER BY datecompleted DESC NULLS LAST
LIMIT 25;

-- ============================================================================
-- 15. SORT BY SOURCE: Sort by source name (with joins)
-- ============================================================================
\echo ''
\echo '15. SORT BY SOURCE: Sort by source name'
\echo '   Route: /api/repair_work_orders?sort[0][field]=Source&sort[0][dir]=asc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    ro.repairorderno,
    ro.custid,
    ro.roname,
    ro.datein,
    ro.datecompleted,
    s.ssource
FROM tblrepairworkorderdetail ro
LEFT JOIN tblcustomers c ON ro.custid = c.custid
LEFT JOIN tblsource s ON c.source = s.ssource
ORDER BY s.ssource ASC
LIMIT 25;

-- ============================================================================
-- 16. SORT BY REPAIRORDERNO: Numeric sort with CAST
-- ============================================================================
\echo ''
\echo '16. SORT BY REPAIRORDERNO: Sort by repair order number (numeric)'
\echo '   Route: /api/repair_work_orders?sort[0][field]=RepairOrderNo&sort[0][dir]=desc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
ORDER BY CAST(repairorderno AS INTEGER) DESC
LIMIT 25;

-- ============================================================================
-- 17. COMPLEX QUERY: Multiple filters + joins + sorting
-- ============================================================================
\echo ''
\echo '17. COMPLEX QUERY: Pending + Text search + Sort by DateIn'
\echo '   Route: /api/repair_work_orders?status=pending&search=test&sort[0][field]=DateIn'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    ro.repairorderno,
    ro.custid,
    ro.roname,
    ro.datein,
    ro.datecompleted
FROM tblrepairworkorderdetail ro
WHERE ro.datecompleted IS NULL
  AND (ro.roname ILIKE '%test%' OR ro."ITEM TYPE" ILIKE '%test%')
ORDER BY ro.datein DESC, ro.repairorderno DESC
LIMIT 25;

-- ============================================================================
-- 18. DEEP PAGINATION: Page 10
-- ============================================================================
\echo ''
\echo '18. DEEP PAGINATION: Page 10 (offset 225)'
\echo '   Route: /api/repair_work_orders?page=10&size=25'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT repairorderno, custid, roname, datein, datecompleted
FROM tblrepairworkorderdetail
ORDER BY datein DESC, repairorderno DESC
LIMIT 25 OFFSET 225;

-- ============================================================================
-- SUMMARY: Current Index Usage
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'CURRENT INDEX SUMMARY'
\echo '============================================================================'
\echo ''
\echo 'Checking which indexes exist on tblrepairworkorderdetail:'

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tblrepairworkorderdetail'
ORDER BY indexname;

\echo ''
\echo '============================================================================'
\echo 'TABLE STATISTICS'
\echo '============================================================================'

-- Show table size
\echo ''
\echo 'Table and index sizes:'
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE tablename = 'tblrepairworkorderdetail';

-- Show row count
\echo ''
\echo 'Row count:'
SELECT COUNT(*) as repair_order_count FROM tblrepairworkorderdetail;

\echo ''
\echo '============================================================================'
\echo 'ANALYSIS COMPLETE'
\echo '============================================================================'
\echo ''
\echo 'What to look for:'
\echo '  - "Seq Scan" on large results = needs index'
\echo '  - CAST operations preventing index usage'
\echo '  - Multiple ILIKE conditions = consider trigram indexes'
\echo '  - Source sorting performance (should have same issues as work orders)'
\echo '============================================================================'
