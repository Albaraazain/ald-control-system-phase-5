-- DATABASE PERFORMANCE OPTIMIZATION INDEXES
-- Target: Reduce 140-189ms query latency to sub-50ms
-- Focus: component_parameters table optimization

-- ============================================================================
-- 1. CRITICAL INDEXES FOR N+1 QUERY OPTIMIZATION
-- ============================================================================

-- Index for component_id lookups (data_recorder.py bulk query optimization)
-- Supports: SELECT * FROM component_parameters WHERE component_id IN (...)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_component_parameters_component_id
ON component_parameters (component_id);

-- Composite index for active component parameters
-- Supports queries filtering by component + active status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_component_parameters_component_active
ON component_parameters (component_id, is_active)
WHERE is_active = true;

-- ============================================================================
-- 2. PARAMETER LOOKUP OPTIMIZATION INDEXES
-- ============================================================================

-- Primary key index (already exists, but ensuring it's optimized)
-- Supports: SELECT * FROM component_parameters WHERE id = ?
-- Note: This should already exist as primary key, but verify performance

-- Index for parameter metadata bulk queries
-- Supports: SELECT id, set_value FROM component_parameters WHERE id IN (...)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_component_parameters_id_set_value
ON component_parameters (id) INCLUDE (set_value, min_value, max_value);

-- ============================================================================
-- 3. MACHINE COMPONENTS OPTIMIZATION
-- ============================================================================

-- Index for machine component lookups (used in data_recorder.py step 1)
-- Supports: SELECT id FROM machine_components WHERE machine_id = ? AND is_activated = true
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_machine_components_machine_activated
ON machine_components (machine_id, is_activated)
WHERE is_activated = true;

-- ============================================================================
-- 4. PROCESS DATA POINTS OPTIMIZATION
-- ============================================================================

-- Index for process data points insertion performance
-- Supports fast inserts and queries by process_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_process_data_points_process_timestamp
ON process_data_points (process_id, timestamp);

-- Index for parameter value history (continuous logger optimization)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_parameter_value_history_param_timestamp
ON parameter_value_history (parameter_id, timestamp);

-- ============================================================================
-- 5. PARAMETER VALUE QUERIES OPTIMIZATION
-- ============================================================================

-- Index for current_value and set_value lookups
-- Supports real-time parameter monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_component_parameters_values
ON component_parameters (current_value, set_value)
WHERE current_value IS NOT NULL;

-- Composite index for parameter synchronization queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_component_parameters_sync
ON component_parameters (component_id, updated_at)
WHERE current_value IS NOT NULL;

-- ============================================================================
-- 6. QUERY PERFORMANCE MONITORING
-- ============================================================================

-- Enable query statistics for performance monitoring
-- This helps track improvement after index implementation
-- Note: Enable this in production for monitoring

-- Example monitoring query to check index usage:
/*
SELECT
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'component_parameters'
ORDER BY idx_scan DESC;
*/

-- ============================================================================
-- 7. CONNECTION POOL OPTIMIZATION SETTINGS
-- ============================================================================

-- Recommended PostgreSQL settings for connection pool optimization
-- Add these to postgresql.conf for production deployment:

/*
# Connection Pool Optimization
max_connections = 200                    # Increase from default 100
shared_buffers = 256MB                   # 25% of RAM for caching
effective_cache_size = 1GB              # 75% of RAM for query planner
work_mem = 4MB                          # Memory per query operation
maintenance_work_mem = 64MB             # Memory for maintenance operations

# Query Performance
random_page_cost = 1.1                  # SSD optimization
effective_io_concurrency = 200          # SSD concurrent I/O
default_statistics_target = 100         # Better query planning

# Write Performance
wal_buffers = 16MB                      # WAL buffer size
checkpoint_completion_target = 0.7       # Spread checkpoint I/O
wal_compression = on                     # Compress WAL files

# Connection Management
idle_in_transaction_session_timeout = 300000  # 5 minutes
statement_timeout = 30000                # 30 seconds max query time
*/

-- ============================================================================
-- PERFORMANCE IMPACT ESTIMATION:
-- ============================================================================

/*
BEFORE OPTIMIZATION:
- data_recorder.py: 4-6 individual queries × 32ms = 128-192ms
- parameter_step.py: Individual lookup per operation = 32ms
- Missing indexes: Full table scans on component_parameters
- Total baseline latency: 140-189ms

AFTER OPTIMIZATION:
- data_recorder.py: Single bulk query with index = 25-40ms (80% improvement)
- parameter_step.py: Cached lookups = <10ms (60% improvement)
- Indexed queries: Sub-10ms response time
- Connection pooling: Reduced connection overhead
- Target latency: Sub-50ms (65% overall improvement)

CRITICAL SUCCESS METRICS:
1. Query latency reduction: 140-189ms → <50ms
2. Database roundtrips reduction: 4-6 queries → 1 bulk query
3. Cache hit ratio: >90% for parameter metadata
4. Index usage: >95% of queries using indexes
5. Connection pool efficiency: <5ms connection overhead
*/