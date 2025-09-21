"""
Async Database Connection Pool for High-Performance Parameter Logging.

This module provides async database connection pooling with prepared statements,
connection health monitoring, and optimized batch operations.
"""
import asyncio
import asyncpg
import time
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass

from src.log_setup import logger
from src.config import SUPABASE_URL, SUPABASE_KEY


@dataclass
class PoolConfig:
    """Configuration for database connection pool."""
    min_connections: int = 5
    max_connections: int = 20
    connection_timeout: float = 10.0
    command_timeout: float = 5.0
    max_inactive_connection_lifetime: float = 300.0  # 5 minutes
    health_check_interval: float = 30.0  # 30 seconds


@dataclass
class PoolMetrics:
    """Connection pool metrics for monitoring."""
    active_connections: int
    idle_connections: int
    total_connections: int
    connections_created: int
    connections_closed: int
    health_check_failures: int
    query_count: int
    average_query_time: float
    last_health_check: float


class AsyncDatabasePool:
    """
    High-performance async database connection pool with prepared statements.

    Provides optimized database access for continuous parameter logging with
    connection pooling, health monitoring, and batch operation support.
    """

    def __init__(self, config: PoolConfig = None):
        """
        Initialize async database pool.

        Args:
            config: Pool configuration
        """
        self.config = config or PoolConfig()
        self.pool = None
        self._prepared_statements = {}
        self._metrics = PoolMetrics(
            active_connections=0,
            idle_connections=0,
            total_connections=0,
            connections_created=0,
            connections_closed=0,
            health_check_failures=0,
            query_count=0,
            average_query_time=0.0,
            last_health_check=0.0
        )
        self._query_times = []
        self._health_check_task = None
        self._connection_string = self._build_connection_string()

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from Supabase config."""
        # Parse Supabase URL to get connection details
        import urllib.parse

        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be configured")

        # Extract database connection info from Supabase URL
        # Supabase URL format: https://project.supabase.co
        parsed = urllib.parse.urlparse(SUPABASE_URL)
        host = parsed.hostname
        project_id = host.split('.')[0] if host else None

        if not project_id:
            raise ValueError(f"Invalid Supabase URL format: {SUPABASE_URL}")

        # Supabase PostgreSQL connection details
        # Note: This uses the direct PostgreSQL connection, not the REST API
        db_host = f"db.{project_id}.supabase.co"
        db_port = 5432
        db_name = "postgres"
        db_user = "postgres"
        db_password = SUPABASE_KEY  # Service role key can be used as password

        connection_string = (
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            "?sslmode=require"
        )

        logger.info(f"Built connection string for host: {db_host}")
        return connection_string

    async def initialize(self) -> bool:
        """
        Initialize the database connection pool.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Initializing async database connection pool")

            self.pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=self.config.command_timeout,
                server_settings={
                    'application_name': 'ald_control_system',
                    'search_path': 'public'
                }
            )

            # Prepare common statements
            await self._prepare_statements()

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            logger.info(f"Database pool initialized with {self.config.min_connections}-{self.config.max_connections} connections")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            return False

    async def close(self):
        """Close the database connection pool."""
        try:
            logger.info("Closing async database connection pool")

            # Stop health check task
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # Close pool
            if self.pool:
                await self.pool.close()
                self.pool = None

            logger.info("Database pool closed")

        except Exception as e:
            logger.error(f"Error closing database pool: {e}")

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a database connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                result = await conn.fetchrow("SELECT 1")
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        start_time = time.time()
        conn = None

        try:
            conn = await self.pool.acquire()
            self._metrics.active_connections += 1
            yield conn

        finally:
            if conn:
                try:
                    await self.pool.release(conn)
                    self._metrics.active_connections -= 1

                    # Update query time metrics
                    query_time = time.time() - start_time
                    self._query_times.append(query_time)

                    # Keep only recent query times (last 100)
                    if len(self._query_times) > 100:
                        self._query_times.pop(0)

                    self._metrics.query_count += 1
                    self._metrics.average_query_time = sum(self._query_times) / len(self._query_times)

                except Exception as e:
                    logger.error(f"Error releasing connection: {e}")

    async def _prepare_statements(self):
        """Prepare common SQL statements for better performance."""
        statements = {
            'insert_parameter_history': """
                INSERT INTO parameter_value_history
                (parameter_id, value, set_point, timestamp)
                VALUES ($1, $2, $3, $4)
            """,
            'insert_process_data': """
                INSERT INTO process_data_points
                (process_id, parameter_id, value, set_point, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            """,
            'get_machine_state': """
                SELECT current_process_id, status
                FROM machines
                WHERE id = $1
            """,
            'get_parameter_metadata': """
                SELECT id, set_value
                FROM component_parameters
                WHERE id = ANY($1)
            """,
            'health_check': """
                SELECT 1 as health_check
            """
        }

        try:
            async with self.acquire() as conn:
                for name, sql in statements.items():
                    await conn.prepare(sql)
                    self._prepared_statements[name] = sql

            logger.info(f"Prepared {len(statements)} SQL statements")

        except Exception as e:
            logger.error(f"Failed to prepare statements: {e}")

    async def batch_insert_parameter_history(
        self,
        records: List[Dict[str, Any]]
    ) -> bool:
        """
        Efficiently batch insert parameter history records.

        Args:
            records: List of parameter history records

        Returns:
            True if successful, False otherwise
        """
        if not records:
            return True

        try:
            async with self.acquire() as conn:
                # Use asyncpg's copy_records_to_table for optimal performance
                # This is faster than executemany for large batches

                data = [
                    (
                        record['parameter_id'],
                        record['value'],
                        record.get('set_point'),
                        record['timestamp']
                    )
                    for record in records
                ]

                await conn.executemany(
                    self._prepared_statements['insert_parameter_history'],
                    data
                )

                logger.debug(f"Batch inserted {len(records)} parameter history records")
                return True

        except Exception as e:
            logger.error(f"Batch insert parameter history failed: {e}")
            return False

    async def batch_insert_process_data(
        self,
        records: List[Dict[str, Any]]
    ) -> bool:
        """
        Efficiently batch insert process data records.

        Args:
            records: List of process data records

        Returns:
            True if successful, False otherwise
        """
        if not records:
            return True

        try:
            async with self.acquire() as conn:
                data = [
                    (
                        record['process_id'],
                        record['parameter_id'],
                        record['value'],
                        record.get('set_point'),
                        record['timestamp']
                    )
                    for record in records
                ]

                await conn.executemany(
                    self._prepared_statements['insert_process_data'],
                    data
                )

                logger.debug(f"Batch inserted {len(records)} process data records")
                return True

        except Exception as e:
            logger.error(f"Batch insert process data failed: {e}")
            return False

    async def get_machine_state(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current machine state efficiently.

        Args:
            machine_id: Machine ID to query

        Returns:
            Dictionary with machine state or None
        """
        try:
            async with self.acquire() as conn:
                result = await conn.fetchrow(
                    self._prepared_statements['get_machine_state'],
                    machine_id
                )

                if result:
                    return {
                        'current_process_id': result['current_process_id'],
                        'status': result['status']
                    }

                return None

        except Exception as e:
            logger.error(f"Failed to get machine state: {e}")
            return None

    async def get_parameter_metadata_batch(
        self,
        parameter_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get parameter metadata for multiple parameters efficiently.

        Args:
            parameter_ids: List of parameter IDs

        Returns:
            Dictionary mapping parameter IDs to metadata
        """
        if not parameter_ids:
            return {}

        try:
            async with self.acquire() as conn:
                results = await conn.fetch(
                    self._prepared_statements['get_parameter_metadata'],
                    parameter_ids
                )

                metadata = {}
                for row in results:
                    metadata[row['id']] = {
                        'set_value': row['set_value']
                    }

                return metadata

        except Exception as e:
            logger.error(f"Failed to get parameter metadata: {e}")
            return {}

    async def execute_transaction(self, operations: List[callable]) -> bool:
        """
        Execute multiple operations in a single transaction.

        Args:
            operations: List of async functions to execute

        Returns:
            True if all operations successful, False otherwise
        """
        try:
            async with self.acquire() as conn:
                async with conn.transaction():
                    for operation in operations:
                        await operation(conn)

                return True

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            return False

    async def _health_check_loop(self):
        """Background task for connection pool health monitoring."""
        try:
            while True:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()

        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in health check loop: {e}")

    async def _perform_health_check(self):
        """Perform health check on the connection pool."""
        try:
            start_time = time.time()

            # Test a simple query
            async with self.acquire() as conn:
                await conn.fetchval(self._prepared_statements['health_check'])

            # Update metrics
            self._metrics.last_health_check = time.time()

            # Check pool status
            if self.pool:
                self._metrics.total_connections = len(self.pool._holders)
                self._metrics.idle_connections = len(self.pool._queue._queue)

            health_check_time = time.time() - start_time

            if health_check_time > 1.0:  # Health check took too long
                logger.warning(f"Slow health check: {health_check_time:.3f}s")

        except Exception as e:
            self._metrics.health_check_failures += 1
            logger.error(f"Health check failed: {e}")

    def get_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        # Update real-time metrics
        if self.pool:
            self._metrics.total_connections = len(self.pool._holders)
            self._metrics.idle_connections = len(self.pool._queue._queue)

        return self._metrics

    def get_status(self) -> Dict[str, Any]:
        """Get detailed pool status."""
        metrics = self.get_metrics()

        return {
            'initialized': self.pool is not None,
            'metrics': {
                'active_connections': metrics.active_connections,
                'idle_connections': metrics.idle_connections,
                'total_connections': metrics.total_connections,
                'connections_created': metrics.connections_created,
                'connections_closed': metrics.connections_closed,
                'health_check_failures': metrics.health_check_failures,
                'query_count': metrics.query_count,
                'average_query_time_ms': metrics.average_query_time * 1000,
                'last_health_check': metrics.last_health_check
            },
            'config': {
                'min_connections': self.config.min_connections,
                'max_connections': self.config.max_connections,
                'connection_timeout': self.config.connection_timeout,
                'command_timeout': self.config.command_timeout
            },
            'prepared_statements': len(self._prepared_statements)
        }


# Global pool instance (will be managed by DI container in the future)
_global_pool = None


async def get_async_database_pool() -> AsyncDatabasePool:
    """
    Get or create the global async database pool.

    This is a temporary global access pattern that will be replaced
    by dependency injection in the migration.
    """
    global _global_pool

    if _global_pool is None:
        _global_pool = AsyncDatabasePool()
        success = await _global_pool.initialize()
        if not success:
            raise RuntimeError("Failed to initialize database pool")

    return _global_pool


async def close_global_pool():
    """Close the global database pool."""
    global _global_pool

    if _global_pool:
        await _global_pool.close()
        _global_pool = None