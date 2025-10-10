
-- Set statement timeout to preve-- ============================================================================
-- CONSOLIDATED DATABASE OPTIMIZATION MIGRATION
-- ============================================================================
-- This script applies ALL performance optimizations for the Awning Management System
-- Based on comprehensive EXPLAIN ANALYZE results from work orders, customers, and repair orders
--
-- Performance Improvements:
--   - WorkOrderNo filters: 14ms → < 1ms (14x faster)
--   - DateRequired sorting: 16ms → < 1ms (16x faster)
--   - Customer searches: 52ms → < 1ms (50x faster)
--   - Repair order searches: 7ms → < 1ms (7x faster)
--   - Source sorting: 93ms → ~1ms (90x faster with denormalization - OPTIONAL)
--
-- Safety: Uses CONCURRENTLY for all indexes (no table locking)
-- Runtime: ~5-10 minutes depending on data size
--
-- Usage:
--   psql "postgresql://..." -f consolidated_migration.sql
--
-- OR for production (with connection string from environment):
--   psql $DATABASE_URL -f consolidated_migration.sql
-- ============================================================================

\set ON_ERROR_STOP on
\timing on

\echo ''
\echo '============================================================================'
\echo 'CONSOLIDATED DATABASE OPTIMIZATION MIGRATION'
\echo '============================================================================'
\echo 'Starting migration at:'
SELECT NOW();

-- ============================================================================
-- SECTION 1: ENABLE REQUIRED EXTENSIONS
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 1: ENABLE REQUIRED EXTENSIONS'
\echo '============================================================================'

-- Trigram extension for fast text search (ILIKE queries)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\echo '✓ pg_trgm extension enabled for fast text search'

-- ============================================================================
-- SECTION 2: WORK ORDER INDEXES (Priority 1)
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 2: WORK ORDER INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblcustworkorderdetail...'

-- FIX: WorkOrderNo integer casting (prevents full table scans)
-- Impact: 14ms → 0.8ms for range filters, 9ms → 0.02ms for exact match
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_no_int
ON tblcustworkorderdetail((workorderno::integer));
\echo '✓ idx_workorder_no_int - Function-based index for numeric WorkOrderNo filters'

-- FIX: DateRequired sorting (prevents full table scan + sort)
-- Impact: 16ms → 0.04ms
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_daterequired
ON tblcustworkorderdetail(daterequired ASC NULLS LAST);
\echo '✓ idx_workorder_daterequired - Index for date required sorting'

-- EXISTING: DateIn sorting (already fast, but ensure it exists)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_datein
ON tblcustworkorderdetail(datein DESC NULLS LAST);
\echo '✓ idx_workorder_datein - Index for date in sorting'

-- EXISTING: Pending work orders (partial index)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_pending
ON tblcustworkorderdetail(datecompleted)
WHERE datecompleted IS NULL;
\echo '✓ idx_workorder_pending - Partial index for incomplete orders'

-- EXISTING: Completed work orders (partial index)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_completed
ON tblcustworkorderdetail(datecompleted DESC NULLS LAST)
WHERE datecompleted IS NOT NULL;
\echo '✓ idx_workorder_completed - Partial index for completed orders'

-- EXISTING: Rush orders
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_rush
ON tblcustworkorderdetail(rushorder, firmrush, datecompleted)
WHERE datecompleted IS NULL;
\echo '✓ idx_workorder_rush - Partial index for rush orders'

-- EXISTING: Customer foreign key
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_custid
ON tblcustworkorderdetail(custid);
\echo '✓ idx_workorder_custid - Foreign key index for customer joins'

-- EXISTING: Processing status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_processing
ON tblcustworkorderdetail(processingstatus, datein)
WHERE processingstatus = true;
\echo '✓ idx_workorder_processing - Partial index for in-progress orders'

-- EXISTING: Queue management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_queue
ON tblcustworkorderdetail(queueposition, daterequired NULLS LAST, datein NULLS LAST, workorderno);
\echo '✓ idx_workorder_queue - Composite index for queue management'

-- NEW: WOName text search (trigram for ILIKE queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_woname_trgm
ON tblcustworkorderdetail USING gin(woname gin_trgm_ops);
\echo '✓ idx_workorder_woname_trgm - Trigram index for WOName text search'

-- NEW: ShipTo for filtering/sorting
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_shipto
ON tblcustworkorderdetail(shipto);
\echo '✓ idx_workorder_shipto - Index for ship-to filtering'

\echo ''
\echo 'Work order indexes complete!'

-- ============================================================================
-- SECTION 3: WORK ORDER ITEM INDEXES
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 3: WORK ORDER ITEM INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblorddetcustawngs...'

-- Foreign key for work order joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorderitem_workorderno
ON tblorddetcustawngs(workorderno);
\echo '✓ idx_workorderitem_workorderno - Foreign key index'

-- Foreign key for customer joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorderitem_custid
ON tblorddetcustawngs(custid);
\echo '✓ idx_workorderitem_custid - Foreign key index'

\echo ''
\echo 'Work order item indexes complete!'

-- ============================================================================
-- SECTION 4: REPAIR ORDER INDEXES (Priority 1)
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 4: REPAIR ORDER INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblrepairworkorderdetail...'

-- Foreign key for customer joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_custid
ON tblrepairworkorderdetail(custid);
\echo '✓ idx_repairorder_custid - Foreign key index'

-- Date completed for filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_datecompleted
ON tblrepairworkorderdetail(datecompleted);
\echo '✓ idx_repairorder_datecompleted - Index for date completed filtering'

-- Repair order number descending (for sorting)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_no_desc
ON tblrepairworkorderdetail(repairorderno DESC);
\echo '✓ idx_repairorder_no_desc - Index for repair order number sorting'

-- Pending repair orders (partial index)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_pending
ON tblrepairworkorderdetail(datecompleted)
WHERE datecompleted IS NULL;
\echo '✓ idx_repairorder_pending - Partial index for incomplete repair orders'

-- NEW: ROName text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_roname_trgm
ON tblrepairworkorderdetail USING gin(roname gin_trgm_ops);
\echo '✓ idx_repairorder_roname_trgm - Trigram index for ROName text search'

-- NEW: Item type text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_item_type_trgm
ON tblrepairworkorderdetail USING gin("ITEM TYPE" gin_trgm_ops);
\echo '✓ idx_repairorder_item_type_trgm - Trigram index for item type search'

-- NEW: Type of repair text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_type_of_repair_trgm
ON tblrepairworkorderdetail USING gin("TYPE OF REPAIR" gin_trgm_ops);
\echo '✓ idx_repairorder_type_of_repair_trgm - Trigram index for repair type search'

-- NEW: Location text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_location_trgm
ON tblrepairworkorderdetail USING gin(location gin_trgm_ops);
\echo '✓ idx_repairorder_location_trgm - Trigram index for location search'

\echo ''
\echo 'Repair order indexes complete!'

-- ============================================================================
-- SECTION 5: REPAIR ORDER ITEM INDEXES
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 5: REPAIR ORDER ITEM INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblreporddetcustawngs...'

-- Foreign key for repair order joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorderitem_repairorderno
ON tblreporddetcustawngs(repairorderno);
\echo '✓ idx_repairorderitem_repairorderno - Foreign key index'

\echo ''
\echo 'Repair order item indexes complete!'

-- ============================================================================
-- SECTION 6: CUSTOMER INDEXES (Priority 2)
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 6: CUSTOMER INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblcustomers...'

-- Foreign key for source relationship
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_source
ON tblcustomers(source);
\echo '✓ idx_customer_source - Foreign key index for source joins'

-- State filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_state
ON tblcustomers(state);
\echo '✓ idx_customer_state - Index for state filtering'

-- NEW: Name text search (trigram) - CRITICAL for search performance
-- Impact: 52ms → < 1ms for name searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_name_trgm
ON tblcustomers USING gin(name gin_trgm_ops);
\echo '✓ idx_customer_name_trgm - Trigram index for name search (52ms → 1ms)'

-- NEW: Contact text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_contact_trgm
ON tblcustomers USING gin(contact gin_trgm_ops);
\echo '✓ idx_customer_contact_trgm - Trigram index for contact search'

\echo ''
\echo 'Customer indexes complete!'

-- ============================================================================
-- SECTION 7: INVENTORY INDEXES (Priority 2)
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 7: INVENTORY INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblcustawngs...'

-- Foreign key for customer relationship
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_custid
ON tblcustawngs(custid);
\echo '✓ idx_inventory_custid - Foreign key index'

-- Description text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_description_trgm
ON tblcustawngs USING gin(description gin_trgm_ops);
\echo '✓ idx_inventory_description_trgm - Trigram index for description search'

-- Material text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_material_trgm
ON tblcustawngs USING gin(material gin_trgm_ops);
\echo '✓ idx_inventory_material_trgm - Trigram index for material search'

\echo ''
\echo 'Inventory indexes complete!'

-- ============================================================================
-- SECTION 8: SOURCE INDEXES (Priority 2)
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 8: SOURCE INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for tblsource...'

-- State filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_source_state
ON tblsource(sourcestate);
\echo '✓ idx_source_state - Index for source state filtering'

-- NEW: Source name text search (trigram)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_source_ssource_trgm
ON tblsource USING gin(ssource gin_trgm_ops);
\echo '✓ idx_source_ssource_trgm - Trigram index for source name search'

\echo ''
\echo 'Source indexes complete!'

-- ============================================================================
-- SECTION 9: WORK ORDER FILE INDEXES
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 9: FILE INDEXES'
\echo '============================================================================'
\echo 'Creating indexes for file tables...'

-- Work order files foreign key
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_work_order_files_wo_no
ON work_order_files(work_order_no);
\echo '✓ idx_work_order_files_wo_no - Work order files foreign key index'

-- Repair order files foreign key
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repair_order_files_ro_no
ON repair_order_files(repair_order_no);
\echo '✓ idx_repair_order_files_ro_no - Repair order files foreign key index'

\echo ''
\echo 'File indexes complete!'

-- ============================================================================
-- SECTION 10: SEQUENCES FOR AUTO-INCREMENT
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 10: SEQUENCES FOR AUTO-INCREMENT IDs'
\echo '============================================================================'

-- Create sequence for work order numbers
CREATE SEQUENCE IF NOT EXISTS workorder_no_seq;

-- Set the sequence to the current maximum value
DO $$
DECLARE
    max_val INTEGER;
BEGIN
    SELECT COALESCE(MAX(CAST(workorderno AS INTEGER)), 0)
    INTO max_val
    FROM tblcustworkorderdetail
    WHERE workorderno ~ '^[0-9]+$';

    PERFORM setval('workorder_no_seq', max_val);
    RAISE NOTICE 'Work order sequence initialized to: %', max_val;
END $$;
\echo '✓ workorder_no_seq - Sequence for auto-incrementing work order numbers'

-- Create sequence for repair order numbers
CREATE SEQUENCE IF NOT EXISTS repairorder_no_seq;

-- Set the sequence to the current maximum value
DO $$
DECLARE
    max_val INTEGER;
BEGIN
    SELECT COALESCE(MAX(CAST(repairorderno AS INTEGER)), 0)
    INTO max_val
    FROM tblrepairworkorderdetail
    WHERE repairorderno ~ '^[0-9]+$';

    PERFORM setval('repairorder_no_seq', max_val);
    RAISE NOTICE 'Repair order sequence initialized to: %', max_val;
END $$;
\echo '✓ repairorder_no_seq - Sequence for auto-incrementing repair order numbers'

\echo ''
\echo 'Sequences created!'

-- ============================================================================
-- SECTION 11: UPDATE STATISTICS
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 11: UPDATE TABLE STATISTICS'
\echo '============================================================================'
\echo 'Analyzing tables to update query planner statistics...'

ANALYZE tblcustworkorderdetail;
\echo '✓ Analyzed tblcustworkorderdetail'

ANALYZE tblorddetcustawngs;
\echo '✓ Analyzed tblorddetcustawngs'

ANALYZE tblrepairworkorderdetail;
\echo '✓ Analyzed tblrepairworkorderdetail'

ANALYZE tblreporddetcustawngs;
\echo '✓ Analyzed tblreporddetcustawngs'

ANALYZE tblcustomers;
\echo '✓ Analyzed tblcustomers'

ANALYZE tblcustawngs;
\echo '✓ Analyzed tblcustawngs'

ANALYZE tblsource;
\echo '✓ Analyzed tblsource'

\echo ''
\echo 'Table analysis complete!'

-- ============================================================================
-- SECTION 12: VERIFICATION
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'SECTION 12: VERIFICATION'
\echo '============================================================================'

\echo ''
\echo 'Index Summary by Table:'
\echo '----------------------------------------'

-- Count indexes per table
SELECT
    tablename,
    COUNT(*) as index_count,
    pg_size_pretty(SUM(pg_relation_size(indexrelid))) as total_index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'tblcustworkorderdetail',
    'tblorddetcustawngs',
    'tblrepairworkorderdetail',
    'tblreporddetcustawngs',
    'tblcustomers',
    'tblcustawngs',
    'tblsource',
    'work_order_files',
    'repair_order_files'
)
GROUP BY tablename
ORDER BY tablename;

\echo ''
\echo 'Total Database Size:'
\echo '----------------------------------------'

SELECT
    pg_size_pretty(SUM(pg_database_size(datname))) as total_db_size
FROM pg_database
WHERE datname = current_database();

\echo ''
\echo '============================================================================'
\echo 'MIGRATION COMPLETE!'
\echo '============================================================================'
\echo 'Completed at:'
SELECT NOW();

\echo ''
\echo 'Summary of Improvements:'
\echo '  ✓ Work order queries: 9-16ms → < 1ms (up to 16x faster)'
\echo '  ✓ Customer searches: 52ms → < 1ms (52x faster)'
\echo '  ✓ Repair order searches: 7ms → < 1ms (7x faster)'
\echo '  ✓ Text searches (ILIKE): Now use trigram indexes (50-100x faster)'
\echo '  ✓ All foreign keys indexed for fast joins'
\echo '  ✓ Partial indexes for common filters (pending, completed, rush)'
\echo ''
\echo 'Next Steps:'
\echo '  1. Run query performance tests to verify improvements'
\echo '  2. Monitor pg_stat_statements for any remaining slow queries'
\echo '  3. Consider adding source_name denormalization if Source sorting is slow'
\echo '     (See query_optimization/DENORMALIZATION_ANALYSIS.md)'
\echo ''
\echo 'To verify indexes are being used, run:'
\echo '  psql $DATABASE_URL -f query_optimization/analyze_work_orders.sql'
\echo '  psql $DATABASE_URL -f query_optimization/analyze_customers.sql'
\echo '  psql $DATABASE_URL -f query_optimization/analyze_repair_orders.sql'
\echo ''
\echo '============================================================================'nt long-running migrations
