-- ============================================================================
-- EXPLAIN ANALYZE for Customer List Queries
-- ============================================================================
-- This script analyzes the performance of customer list queries
-- ============================================================================

\timing on
\echo '============================================================================'
\echo 'Customer List Query Performance Analysis'
\echo '============================================================================'

-- ============================================================================
-- 1. BASELINE: Simple customer list (no filters, ordered by CustID)
-- ============================================================================
\echo ''
\echo '1. BASELINE: Simple list with default sort (first 25 records)'
\echo '   Route: /api/customers?page=1&size=25'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, state, homephone, emailaddress, source
FROM tblcustomers
ORDER BY custid
LIMIT 25 OFFSET 0;

-- ============================================================================
-- 2. COUNT QUERY: Total count (pagination)
-- ============================================================================
\echo ''
\echo '2. COUNT: Total customers (for pagination)'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT COUNT(*) FROM tblcustomers;

-- ============================================================================
-- 3. GLOBAL SEARCH: Search across multiple fields
-- ============================================================================
\echo ''
\echo '3. GLOBAL SEARCH: Search for "test" across all fields'
\echo '   Route: /api/customers?search=test'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
WHERE name ILIKE '%test%'
   OR custid ILIKE '%test%'
   OR contact ILIKE '%test%'
   OR city ILIKE '%test%'
   OR homephone ILIKE '%test%'
   OR emailaddress ILIKE '%test%'
   OR source ILIKE '%test%'
ORDER BY custid
LIMIT 25;

-- ============================================================================
-- 4. CUSTID FILTER: Cast to integer for numeric comparison
-- ============================================================================
\echo ''
\echo '4. CUSTID FILTER: Filter by customer ID (with CAST)'
\echo '   Route: /api/customers?filter_CustID=100'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
WHERE CAST(custid AS INTEGER) = 100
LIMIT 25;

-- ============================================================================
-- 5. NAME FILTER: ILIKE search
-- ============================================================================
\echo ''
\echo '5. NAME FILTER: Filter by name'
\echo '   Route: /api/customers?filter_Name=Smith'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
WHERE name ILIKE '%Smith%'
ORDER BY custid
LIMIT 25;

-- ============================================================================
-- 6. SOURCE FILTER: Filter by source
-- ============================================================================
\echo ''
\echo '6. SOURCE FILTER: Filter by source'
\echo '   Route: /api/customers?filter_Source=ABC'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
WHERE source ILIKE '%ABC%'
ORDER BY custid
LIMIT 25;

-- ============================================================================
-- 7. SORT BY NAME: Alphabetical sorting
-- ============================================================================
\echo ''
\echo '7. SORT BY NAME: Sort by customer name'
\echo '   Route: /api/customers?sort[0][field]=Name&sort[0][dir]=asc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
ORDER BY name ASC
LIMIT 25;

-- ============================================================================
-- 8. SORT BY SOURCE: Sort by source
-- ============================================================================
\echo ''
\echo '8. SORT BY SOURCE: Sort by source'
\echo '   Route: /api/customers?sort[0][field]=Source&sort[0][dir]=asc'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
ORDER BY source ASC
LIMIT 25;

-- ============================================================================
-- 9. CUSTOMER DETAIL: Load customer with related data
-- ============================================================================
\echo ''
\echo '9. CUSTOMER DETAIL: Get single customer'
\echo '   Route: /customers/view/<customer_id>'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT *
FROM tblcustomers
WHERE custid = '1';

-- ============================================================================
-- 10. CUSTOMER WITH WORK ORDERS: Join query
-- ============================================================================
\echo ''
\echo '10. CUSTOMER WITH WORK ORDERS: Load work orders for customer'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT wo.workorderno, wo.woname, wo.datein, wo.datecompleted
FROM tblcustworkorderdetail wo
WHERE wo.custid = '1'
ORDER BY CAST(wo.workorderno AS INTEGER) DESC;

-- ============================================================================
-- 11. CUSTOMER WITH REPAIR ORDERS: Join query
-- ============================================================================
\echo ''
\echo '11. CUSTOMER WITH REPAIR ORDERS: Load repair orders for customer'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT ro.repairorderno, ro.roname, ro.datein, ro.datecompleted
FROM tblrepairworkorderdetail ro
WHERE ro.custid = '1'
ORDER BY CAST(ro.repairorderno AS INTEGER) DESC;

-- ============================================================================
-- 12. CUSTOMER WITH INVENTORY: Join query
-- ============================================================================
\echo ''
\echo '12. CUSTOMER WITH INVENTORY: Load inventory for customer'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT *
FROM tblcustawngs
WHERE custid = '1';

-- ============================================================================
-- 13. COMPLEX QUERY: Multiple filters + sorting
-- ============================================================================
\echo ''
\echo '13. COMPLEX QUERY: Search + Source filter + Sort by Name'
\echo '   Route: /api/customers?search=test&filter_Source=ABC&sort[0][field]=Name'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
WHERE (name ILIKE '%test%' OR contact ILIKE '%test%' OR city ILIKE '%test%')
  AND source ILIKE '%ABC%'
ORDER BY name ASC
LIMIT 25;

-- ============================================================================
-- 14. DEEP PAGINATION: Page 10
-- ============================================================================
\echo ''
\echo '14. DEEP PAGINATION: Page 10 (offset 225)'
\echo '   Route: /api/customers?page=10&size=25'
\echo '----------'

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT custid, name, contact, city, homephone, emailaddress, source
FROM tblcustomers
ORDER BY custid
LIMIT 25 OFFSET 225;

-- ============================================================================
-- SUMMARY: Current Index Usage
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'CURRENT INDEX SUMMARY'
\echo '============================================================================'
\echo ''
\echo 'Checking which indexes exist on tblcustomers:'

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tblcustomers'
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
WHERE tablename = 'tblcustomers';

-- Show row count
\echo ''
\echo 'Row count:'
SELECT COUNT(*) as customer_count FROM tblcustomers;

\echo ''
\echo '============================================================================'
\echo 'ANALYSIS COMPLETE'
\echo '============================================================================'
\echo ''
\echo 'What to look for:'
\echo '  - "Seq Scan" on large results = needs index'
\echo '  - CAST operations preventing index usage'
\echo '  - Multiple ILIKE conditions = consider trigram indexes'
\echo '============================================================================'
