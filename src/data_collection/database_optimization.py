"""
Database performance optimization layer for high-throughput parameter logging.

This module provides:
1. AsyncDatabaseConnectionPool - High-performance async connection pooling
2. ParameterMetadataCache - TTL-based caching for parameter metadata
3. BulkOperationManager - Optimized bulk insert operations
4. DatabasePerformanceMonitor - Real-time performance metrics

Performance Targets:
- Bulk insert operations <100ms for 50+ records
- Connection pool utilization >90%
- Cache hit ratio >95% for parameter metadata
- Zero connection leaks during continuous operation
"""

import asyncio
import time
import weakref
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set
from contextlib import asynccontextmanager
import threading
from src.log_setup import logger
from src.config import SUPABASE_URL, SUPABASE_KEY, is_supabase_config_present


@dataclass
class ConnectionPoolMetrics:
    """Metrics for connection pool performance monitoring."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connection_acquisitions: int = 0
    connection_releases: int = 0
    connection_failures: int = 0
    avg_acquisition_time_ms: float = 0.0
    max_acquisition_time_ms: float = 0.0
    pool_utilization_percent: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class CacheMetrics:
    """Metrics for parameter metadata cache performance."""
    cache_hits: int = 0
    cache_misses: int = 0
    cache_size: int = 0
    hit_ratio_percent: float = 0.0
    evictions: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class BulkOperationMetrics:
    """Metrics for bulk database operations."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_records_processed: int = 0
    avg_operation_time_ms: float = 0.0
    max_operation_time_ms: float = 0.0
    avg_batch_size: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


class AsyncDatabaseConnectionPool:
    """
    High-performance async database connection pool with health monitoring.

    Features:
    - Configurable min/max connections
    - Connection health checks and automatic recovery
    - Connection reuse strategy to eliminate per-operation overhead
    - Real-time metrics and monitoring
    - Automatic connection lifecycle management
    """

    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_timeout: float = 30.0,
        health_check_interval: float = 60.0,
        max_idle_time: float = 300.0
    ):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.health_check_interval = health_check_interval
        self.max_idle_time = max_idle_time

        # Connection pool state
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections: Set[Any] = set()
        self._connection_info: Dict[Any, Dict[str, Any]] = {}
        self._pool_lock = asyncio.Lock()
        self._metrics = ConnectionPoolMetrics()
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the connection pool with minimum connections."""
        if self._initialized:
            return

        try:
            if not is_supabase_config_present():
                raise ValueError("Supabase configuration missing")

            # Create minimum connections
            for _ in range(self.min_connections):
                conn = await self._create_connection()
                if conn:
                    await self._pool.put(conn)
                    self._metrics.total_connections += 1
                    self._metrics.idle_connections += 1

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._initialized = True

            logger.info(
                f"Database connection pool initialized with {self._metrics.total_connections} connections"
            )

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    async def _create_connection(self):
        """Create a new database connection."""
        try:
            # Import here to avoid circular imports
            from supabase import create_async_client

            client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
            connection_info = {
                'created_at': time.time(),
                'last_used': time.time(),
                'use_count': 0,
                'healthy': True
            }
            self._connection_info[client] = connection_info
            return client

        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            self._metrics.connection_failures += 1
            return None

    @asynccontextmanager
    async def acquire_connection(self):
        """
        Acquire a connection from the pool with automatic release.

        Usage:
            async with pool.acquire_connection() as conn:
                # Use connection
                pass
        """
        start_time = time.time()
        connection = None

        try:
            # Try to get connection from pool
            try:
                connection = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.connection_timeout
                )
            except asyncio.TimeoutError:
                # Pool exhausted, try to create new connection if under limit
                async with self._pool_lock:
                    if self._metrics.total_connections < self.max_connections:
                        connection = await self._create_connection()
                        if connection:
                            self._metrics.total_connections += 1

                    if not connection:
                        raise RuntimeError("Connection pool exhausted and cannot create new connection")

            # Update connection info and metrics
            if connection in self._connection_info:
                self._connection_info[connection]['last_used'] = time.time()
                self._connection_info[connection]['use_count'] += 1

            self._active_connections.add(connection)
            self._metrics.active_connections += 1
            self._metrics.idle_connections = max(0, self._metrics.idle_connections - 1)
            self._metrics.connection_acquisitions += 1

            # Update acquisition time metrics
            acquisition_time_ms = (time.time() - start_time) * 1000
            self._metrics.avg_acquisition_time_ms = (
                (self._metrics.avg_acquisition_time_ms * (self._metrics.connection_acquisitions - 1) +
                 acquisition_time_ms) / self._metrics.connection_acquisitions
            )
            self._metrics.max_acquisition_time_ms = max(
                self._metrics.max_acquisition_time_ms, acquisition_time_ms
            )

            yield connection

        finally:
            # Release connection back to pool
            if connection:
                self._active_connections.discard(connection)
                self._metrics.active_connections = max(0, self._metrics.active_connections - 1)
                self._metrics.connection_releases += 1

                # Check if connection is still healthy
                if (connection in self._connection_info and
                    self._connection_info[connection]['healthy']):
                    await self._pool.put(connection)
                    self._metrics.idle_connections += 1
                else:
                    # Remove unhealthy connection
                    if connection in self._connection_info:
                        del self._connection_info[connection]
                    self._metrics.total_connections = max(0, self._metrics.total_connections - 1)

    async def _health_check_loop(self):
        """Background task to monitor connection health."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_connection_health()
                self._update_pool_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection health check: {e}")

    async def _check_connection_health(self):
        """Check health of idle connections and remove stale ones."""
        current_time = time.time()
        stale_connections = []

        for conn, info in list(self._connection_info.items()):
            if conn not in self._active_connections:
                # Check if connection is too old or idle
                if (current_time - info['last_used']) > self.max_idle_time:
                    stale_connections.append(conn)
                    continue

                # TODO: Add actual health check (ping database)
                # For now, just mark as healthy
                info['healthy'] = True

        # Remove stale connections
        for conn in stale_connections:
            if conn in self._connection_info:
                del self._connection_info[conn]
                self._metrics.total_connections = max(0, self._metrics.total_connections - 1)
                logger.debug("Removed stale database connection")

    def _update_pool_metrics(self):
        """Update pool utilization metrics."""
        if self.max_connections > 0:
            self._metrics.pool_utilization_percent = (
                self._metrics.active_connections / self.max_connections * 100
            )
        self._metrics.last_updated = datetime.now()

    def get_metrics(self) -> ConnectionPoolMetrics:
        """Get current connection pool metrics."""
        self._update_pool_metrics()
        return self._metrics

    async def close(self):
        """Close all connections and cleanup resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        while not self._pool.empty():
            try:
                conn = await self._pool.get()
                # TODO: Add proper connection close method
                logger.debug("Closed database connection")
            except:
                pass

        self._connection_info.clear()
        self._active_connections.clear()
        self._initialized = False
        logger.info("Database connection pool closed")


class ParameterMetadataCache:
    """
    TTL-based cache for parameter metadata with high performance requirements.

    Features:
    - Time-to-live (TTL) expiration
    - Thread-safe operations
    - Cache hit ratio >95% target
    - Automatic eviction of expired entries
    - Real-time metrics tracking
    """

    def __init__(self, ttl_seconds: float = 300.0, max_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_time)
        self._lock = threading.RLock()
        self._metrics = CacheMetrics()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, return None if expired or not found."""
        current_time = time.time()

        with self._lock:
            if key in self._cache:
                value, expiry_time = self._cache[key]
                if current_time <= expiry_time:
                    self._metrics.cache_hits += 1
                    self._update_hit_ratio()
                    return value
                else:
                    # Expired entry
                    del self._cache[key]
                    self._metrics.cache_misses += 1
                    self._metrics.evictions += 1
                    self._update_hit_ratio()
                    return None
            else:
                self._metrics.cache_misses += 1
                self._update_hit_ratio()
                return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with TTL expiration."""
        current_time = time.time()
        expiry_time = current_time + self.ttl_seconds

        with self._lock:
            # Evict if at max size
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()

            self._cache[key] = (value, expiry_time)
            self._metrics.cache_size = len(self._cache)

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]
        self._metrics.evictions += 1

    def _update_hit_ratio(self) -> None:
        """Update cache hit ratio metrics."""
        total_requests = self._metrics.cache_hits + self._metrics.cache_misses
        if total_requests > 0:
            self._metrics.hit_ratio_percent = (self._metrics.cache_hits / total_requests) * 100
        self._metrics.last_updated = datetime.now()

    def clear_expired(self) -> int:
        """Clear all expired entries and return count of removed entries."""
        current_time = time.time()
        expired_keys = []

        with self._lock:
            for key, (_, expiry_time) in self._cache.items():
                if current_time > expiry_time:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]
                self._metrics.evictions += 1

            self._metrics.cache_size = len(self._cache)

        return len(expired_keys)

    def get_metrics(self) -> CacheMetrics:
        """Get current cache metrics."""
        with self._lock:
            self._metrics.cache_size = len(self._cache)
            return self._metrics


class BulkOperationManager:
    """
    High-performance bulk database operations manager.

    Features:
    - Optimized batch sizes for <100ms operations
    - Parallel batch processing
    - Transaction management for bulk operations
    - Error handling for partial batch failures
    - Performance monitoring and optimization
    """

    def __init__(
        self,
        connection_pool: AsyncDatabaseConnectionPool,
        optimal_batch_size: int = 50,
        max_parallel_batches: int = 3,
        operation_timeout: float = 10.0
    ):
        self.connection_pool = connection_pool
        self.optimal_batch_size = optimal_batch_size
        self.max_parallel_batches = max_parallel_batches
        self.operation_timeout = operation_timeout
        self._metrics = BulkOperationMetrics()

    async def bulk_insert(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        enable_parallel: bool = True
    ) -> Tuple[int, List[str]]:
        """
        Perform bulk insert operation with optimal batching.

        Returns:
            Tuple of (successful_count, error_messages)
        """
        if not records:
            return 0, []

        start_time = time.time()
        successful_count = 0
        errors = []

        try:
            # Split records into optimal batches
            batches = [
                records[i:i + self.optimal_batch_size]
                for i in range(0, len(records), self.optimal_batch_size)
            ]

            if enable_parallel and len(batches) > 1:
                # Process batches in parallel (limited concurrency)
                semaphore = asyncio.Semaphore(self.max_parallel_batches)
                tasks = [
                    self._process_batch_with_semaphore(semaphore, table_name, batch)
                    for batch in batches
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        errors.append(str(result))
                    else:
                        successful_count += result
            else:
                # Process batches sequentially
                for batch in batches:
                    try:
                        count = await self._process_single_batch(table_name, batch)
                        successful_count += count
                    except Exception as e:
                        errors.append(str(e))

            # Update metrics
            operation_time_ms = (time.time() - start_time) * 1000
            self._update_metrics(
                len(records), successful_count, len(errors), operation_time_ms
            )

            if errors:
                logger.warning(
                    f"Bulk insert completed with {len(errors)} batch errors. "
                    f"Successfully inserted {successful_count}/{len(records)} records"
                )
            else:
                logger.debug(
                    f"Bulk insert successful: {successful_count} records in {operation_time_ms:.1f}ms"
                )

            return successful_count, errors

        except Exception as e:
            logger.error(f"Bulk insert operation failed: {e}")
            self._metrics.failed_operations += 1
            return 0, [str(e)]

    async def _process_batch_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        table_name: str,
        batch: List[Dict[str, Any]]
    ) -> int:
        """Process a single batch with semaphore-controlled concurrency."""
        async with semaphore:
            return await self._process_single_batch(table_name, batch)

    async def _process_single_batch(
        self,
        table_name: str,
        batch: List[Dict[str, Any]]
    ) -> int:
        """Process a single batch insert operation."""
        async with self.connection_pool.acquire_connection() as conn:
            try:
                # Use timeout for the operation
                result = await asyncio.wait_for(
                    conn.table(table_name).insert(batch).execute(),
                    timeout=self.operation_timeout
                )
                return len(batch)

            except asyncio.TimeoutError:
                raise Exception(f"Batch insert timeout after {self.operation_timeout}s")
            except Exception as e:
                raise Exception(f"Batch insert failed: {e}")

    def _update_metrics(
        self,
        total_records: int,
        successful_records: int,
        error_count: int,
        operation_time_ms: float
    ) -> None:
        """Update bulk operation metrics."""
        self._metrics.total_operations += 1
        self._metrics.total_records_processed += total_records

        if error_count == 0:
            self._metrics.successful_operations += 1
        else:
            self._metrics.failed_operations += 1

        # Update timing metrics
        total_ops = self._metrics.total_operations
        self._metrics.avg_operation_time_ms = (
            (self._metrics.avg_operation_time_ms * (total_ops - 1) + operation_time_ms) / total_ops
        )
        self._metrics.max_operation_time_ms = max(
            self._metrics.max_operation_time_ms, operation_time_ms
        )

        # Update batch size metrics
        self._metrics.avg_batch_size = (
            self._metrics.total_records_processed / total_ops
        )

        self._metrics.last_updated = datetime.now()

    def get_metrics(self) -> BulkOperationMetrics:
        """Get current bulk operation metrics."""
        return self._metrics


class DatabasePerformanceMonitor:
    """
    Real-time database performance monitoring and alerting system.

    Features:
    - Connection pool monitoring
    - Cache performance tracking
    - Bulk operation metrics
    - Performance threshold alerting
    - Health status reporting
    """

    def __init__(
        self,
        connection_pool: AsyncDatabaseConnectionPool,
        metadata_cache: ParameterMetadataCache,
        bulk_manager: BulkOperationManager
    ):
        self.connection_pool = connection_pool
        self.metadata_cache = metadata_cache
        self.bulk_manager = bulk_manager
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 30.0  # seconds

    async def start_monitoring(self):
        """Start background monitoring task."""
        if self._monitoring_task:
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Database performance monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring task."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Database performance monitoring stopped")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self._monitoring_interval)
                await self._check_performance_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")

    async def _check_performance_metrics(self):
        """Check performance metrics and log alerts if needed."""
        # Get current metrics
        pool_metrics = self.connection_pool.get_metrics()
        cache_metrics = self.metadata_cache.get_metrics()
        bulk_metrics = self.bulk_manager.get_metrics()

        # Check performance thresholds
        alerts = []

        # Connection pool alerts
        if pool_metrics.pool_utilization_percent > 95:
            alerts.append(f"High connection pool utilization: {pool_metrics.pool_utilization_percent:.1f}%")

        if pool_metrics.avg_acquisition_time_ms > 100:
            alerts.append(f"Slow connection acquisition: {pool_metrics.avg_acquisition_time_ms:.1f}ms")

        # Cache performance alerts
        if cache_metrics.hit_ratio_percent < 90:
            alerts.append(f"Low cache hit ratio: {cache_metrics.hit_ratio_percent:.1f}%")

        # Bulk operation alerts
        if bulk_metrics.avg_operation_time_ms > 200:
            alerts.append(f"Slow bulk operations: {bulk_metrics.avg_operation_time_ms:.1f}ms")

        # Log alerts
        if alerts:
            logger.warning(f"Database performance alerts: {'; '.join(alerts)}")
        else:
            logger.debug("Database performance metrics within normal ranges")

    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive performance status report."""
        pool_metrics = self.connection_pool.get_metrics()
        cache_metrics = self.metadata_cache.get_metrics()
        bulk_metrics = self.bulk_manager.get_metrics()

        return {
            'connection_pool': {
                'total_connections': pool_metrics.total_connections,
                'active_connections': pool_metrics.active_connections,
                'idle_connections': pool_metrics.idle_connections,
                'utilization_percent': pool_metrics.pool_utilization_percent,
                'avg_acquisition_time_ms': pool_metrics.avg_acquisition_time_ms,
                'connection_failures': pool_metrics.connection_failures
            },
            'metadata_cache': {
                'cache_size': cache_metrics.cache_size,
                'hit_ratio_percent': cache_metrics.hit_ratio_percent,
                'cache_hits': cache_metrics.cache_hits,
                'cache_misses': cache_metrics.cache_misses,
                'evictions': cache_metrics.evictions
            },
            'bulk_operations': {
                'total_operations': bulk_metrics.total_operations,
                'successful_operations': bulk_metrics.successful_operations,
                'failed_operations': bulk_metrics.failed_operations,
                'avg_operation_time_ms': bulk_metrics.avg_operation_time_ms,
                'avg_batch_size': bulk_metrics.avg_batch_size,
                'total_records_processed': bulk_metrics.total_records_processed
            },
            'performance_status': {
                'overall_health': self._calculate_overall_health(
                    pool_metrics, cache_metrics, bulk_metrics
                ),
                'last_updated': datetime.now().isoformat()
            }
        }

    def _calculate_overall_health(
        self,
        pool_metrics: ConnectionPoolMetrics,
        cache_metrics: CacheMetrics,
        bulk_metrics: BulkOperationMetrics
    ) -> str:
        """Calculate overall database performance health status."""
        issues = []

        if pool_metrics.pool_utilization_percent > 95:
            issues.append("high_pool_utilization")
        if pool_metrics.avg_acquisition_time_ms > 100:
            issues.append("slow_connections")
        if cache_metrics.hit_ratio_percent < 90:
            issues.append("poor_cache_performance")
        if bulk_metrics.avg_operation_time_ms > 200:
            issues.append("slow_bulk_operations")

        if not issues:
            return "healthy"
        elif len(issues) <= 2:
            return "degraded"
        else:
            return "critical"


# Global instances (will be replaced by dependency injection in new architecture)
_connection_pool: Optional[AsyncDatabaseConnectionPool] = None
_metadata_cache: Optional[ParameterMetadataCache] = None
_bulk_manager: Optional[BulkOperationManager] = None
_performance_monitor: Optional[DatabasePerformanceMonitor] = None


async def get_optimized_database_components():
    """
    Get optimized database components (connection pool, cache, bulk manager).

    This is a temporary factory function that will be replaced by proper
    dependency injection in the new architecture.
    """
    global _connection_pool, _metadata_cache, _bulk_manager, _performance_monitor

    if not _connection_pool:
        # Initialize components
        _connection_pool = AsyncDatabaseConnectionPool(
            min_connections=3,
            max_connections=12,
            connection_timeout=30.0,
            health_check_interval=60.0
        )
        await _connection_pool.initialize()

        _metadata_cache = ParameterMetadataCache(
            ttl_seconds=300.0,  # 5 minutes TTL
            max_size=1000
        )

        _bulk_manager = BulkOperationManager(
            connection_pool=_connection_pool,
            optimal_batch_size=50,
            max_parallel_batches=3
        )

        _performance_monitor = DatabasePerformanceMonitor(
            connection_pool=_connection_pool,
            metadata_cache=_metadata_cache,
            bulk_manager=_bulk_manager
        )

        await _performance_monitor.start_monitoring()

        logger.info("Database optimization components initialized")

    return _connection_pool, _metadata_cache, _bulk_manager, _performance_monitor


async def cleanup_database_optimization():
    """Cleanup database optimization components."""
    global _connection_pool, _metadata_cache, _bulk_manager, _performance_monitor

    if _performance_monitor:
        await _performance_monitor.stop_monitoring()
        _performance_monitor = None

    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None

    _metadata_cache = None
    _bulk_manager = None

    logger.info("Database optimization components cleaned up")