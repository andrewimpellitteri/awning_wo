-- ============================================================================
-- Database Index Migration for Awning Management System
-- ============================================================================
--
-- This script creates indexes to optimize query performance across the
-- application. Run this against your PostgreSQL database.
--
-- Usage:
--   psql -d awning_db -f migration_scripts.sql
--
-- IMPORTANT:
--   - Run during low-traffic period if possible
--   - CREATE INDEX CONCURRENTLY is used to avoid blocking writes
--   - Estimated time: 5-15 minutes depending on data size
--   - Monitor disk space: indexes will use ~10-20% of table size
-- ============================================================================

-- Set statement timeout to prevent long-running migrations
SET statement_timeout = '30min';

-- Enable timing to see execution time
\timing on

-- Display message
\echo '============================================================================'
\echo 'Starting index creation for query optimization'
\echo '============================================================================'

-- ============================================================================
-- PRIORITY 1: Work Order Indexes (High Impact)
-- ============================================================================

\echo ''
\echo 'Creating indexes for tblcustworkorderdetail (WorkOrder)...'

-- Index for pending work orders (most common filter)
-- Partial index is very efficient for this use case
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_pending
    ON tblcustworkorderdetail(datecompleted)
    WHERE datecompleted IS NULL;

-- Composite index for queue management
-- Covers: queueposition, daterequired, datein, workorderno
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_queue
    ON tblcustworkorderdetail(queueposition, daterequired NULLS LAST, datein NULLS LAST, workorderno);

-- Index for rush orders
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_rush
    ON tblcustworkorderdetail(rushorder, firmrush, datecompleted)
    WHERE datecompleted IS NULL;

-- Foreign key index for customer joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_custid
    ON tblcustworkorderdetail(custid);

-- Index for processing status filter
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_processing
    ON tblcustworkorderdetail(processingstatus, datein)
    WHERE processingstatus = true;

-- Index for date-based sorting and filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_datein
    ON tblcustworkorderdetail(datein DESC NULLS LAST);

-- Index for completed orders
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_completed
    ON tblcustworkorderdetail(datecompleted DESC NULLS LAST)
    WHERE datecompleted IS NOT NULL;

\echo 'Work order indexes created.'

-- ============================================================================
-- PRIORITY 1: Work Order Items Indexes
-- ============================================================================

\echo ''
\echo 'Creating indexes for tblorddetcustawngs (WorkOrderItem)...'

-- Foreign key for work order joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorderitem_workorderno
    ON tblorddetcustawngs(workorderno);

-- Foreign key for customer joins
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorderitem_custid
    ON tblorddetcustawngs(custid);

\echo 'Work order item indexes created.'

-- ============================================================================
-- PRIORITY 1: Repair Order Indexes
-- ============================================================================

\echo ''
\echo 'Creating indexes for repair work orders...'

-- Assuming table name is tblrepairworkorder
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_custid
    ON tblrepairworkorder(custid);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_datecompleted
    ON tblrepairworkorder(datecompleted);

-- Index for getting next repair order number efficiently
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_no_desc
    ON tblrepairworkorder(repairorderno DESC);

-- Pending repair orders
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_pending
    ON tblrepairworkorder(datecompleted)
    WHERE datecompleted IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_roname_trgm
ON tblrepairworkorder USING gin(ROName gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_item_type_trgm
ON tblrepairworkorder USING gin(ITEM_TYPE gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_type_of_repair_trgm
ON tblrepairworkorder USING gin(TYPE_OF_REPAIR gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorder_location_trgm
ON tblrepairworkorder USING gin(LOCATION gin_trgm_ops);


\echo 'Repair order indexes created.'

-- ============================================================================
-- PRIORITY 1: Repair Order Items Indexes
-- ============================================================================

\echo ''
\echo 'Creating indexes for repair order items...'

-- Assuming table name is tblrepairworkorderitems
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repairorderitem_repairorderno
    ON tblrepairworkorderitems(repairorderno);

\echo 'Repair order item indexes created.'

-- ============================================================================
-- PRIORITY 2: Customer Indexes (Medium Impact)
-- ============================================================================

\echo ''
\echo 'Creating indexes for tblcustomers (Customer)...'

-- Foreign key for source relationship
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_source
    ON tblcustomers(source);

-- Index for state filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_state
    ON tblcustomers(state);

-- Composite index for customer searches (name + contact)
-- This helps with LIKE queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_name_contact
    ON tblcustomers(LOWER(name), LOWER(contact));

\echo 'Customer indexes created.'

-- ============================================================================
-- PRIORITY 2: Inventory Indexes
-- ============================================================================

\echo ''
\echo 'Creating indexes for tblinventory (Inventory)...'

-- Foreign key for customer relationship
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_custid
    ON tblinventory(custid);

-- Index for description searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_description
    ON tblinventory(LOWER(description));

\echo 'Inventory indexes created.'

-- ============================================================================
-- PRIORITY 2: Source Indexes
-- ============================================================================

\echo ''
\echo 'Creating indexes for tblsource (Source)...'

-- Index for state filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_source_state
    ON tblsource(sourcestate);

\echo 'Source indexes created.'

-- ============================================================================
-- PRIORITY 3: Full-Text Search Indexes (Optional)
-- ============================================================================

\echo ''
\echo 'Creating full-text search indexes (optional, may take longer)...'

-- Enable pg_trgm extension for trigram-based searches (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Customer full-text search using GIN index
-- This dramatically speeds up LIKE/ILIKE queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_name_trgm
    ON tblcustomers USING gin(name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_contact_trgm
    ON tblcustomers USING gin(contact gin_trgm_ops);

-- Inventory full-text search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_description_trgm
    ON tblinventory USING gin(description gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_material_trgm
    ON tblinventory USING gin(material gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workorder_woname_trgm
ON tblcustworkorderdetail USING gin(WOName gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_source_ssource_trgm
ON tblsource USING gin(SSource gin_trgm_ops);


\echo 'Full-text search indexes created.'

-- ============================================================================
-- SEQUENCES FOR AUTO-INCREMENT IDs (Recommended)
-- ============================================================================

\echo ''
\echo 'Creating sequences for auto-increment IDs...'
\echo 'NOTE: This will analyze existing data to set starting values'

-- Create sequence for work order numbers
CREATE SEQUENCE IF NOT EXISTS workorder_no_seq;

-- Set the sequence to the current maximum value
DO $$
DECLARE
    max_val INTEGER;
BEGIN
    -- Get current max WorkOrderNo
    SELECT COALESCE(MAX(CAST(workorderno AS INTEGER)), 0)
    INTO max_val
    FROM tblcustworkorderdetail
    WHERE workorderno ~ '^[0-9]+$';  -- Only numeric values

    -- Set sequence start value
    PERFORM setval('workorder_no_seq', max_val);

    RAISE NOTICE 'Work order sequence initialized to: %', max_val;
END $$;

-- Create sequence for repair order numbers
CREATE SEQUENCE IF NOT EXISTS repairorder_no_seq;

-- Set the sequence to the current maximum value
DO $$
DECLARE
    max_val INTEGER;
BEGIN
    -- Get current max RepairOrderNo
    SELECT COALESCE(MAX(CAST(repairorderno AS INTEGER)), 0)
    INTO max_val
    FROM tblrepairworkorder
    WHERE repairorderno ~ '^[0-9]+$';  -- Only numeric values

    -- Set sequence start value
    PERFORM setval('repairorder_no_seq', max_val);

    RAISE NOTICE 'Repair order sequence initialized to: %', max_val;
END $$;

\echo 'Sequences created and initialized.'

-- ============================================================================
-- ANALYZE TABLES
-- ============================================================================

\echo ''
\echo 'Analyzing tables to update statistics...'

ANALYZE tblcustworkorderdetail;
ANALYZE tblorddetcustawngs;
ANALYZE tblrepairworkorder;
ANALYZE tblrepairworkorderitems;
ANALYZE tblcustomers;
ANALYZE tblinventory;
ANALYZE tblsource;

\echo 'Table analysis complete.'

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'Index creation complete! Verifying indexes...'
\echo '============================================================================'
\echo ''

-- Show all indexes created
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN (
    'tblcustworkorderdetail',
    'tblorddetcustawngs',
    'tblrepairworkorder',
    'tblrepairworkorderitems',
    'tblcustomers',
    'tblinventory',
    'tblsource'
)
ORDER BY tablename, indexname;

-- Show index sizes
\echo ''
\echo 'Index sizes:'
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE tablename IN (
    'tblcustworkorderdetail',
    'tblorddetcustawngs',
    'tblrepairworkorder',
    'tblrepairworkorderitems',
    'tblcustomers',
    'tblinventory',
    'tblsource'
)
ORDER BY tablename, indexname;

\echo ''
\echo '============================================================================'
\echo 'Migration complete!'
\echo ''
\echo 'Next steps:'
\echo '1. Monitor query performance using query_benchmark.py'
\echo '2. Run EXPLAIN ANALYZE on slow queries to verify index usage'
\echo '3. Update application code to use sequences (see optimization_examples.py)'
\echo '4. Consider implementing the N+1 query fixes from the optimization guide'
\echo '============================================================================'