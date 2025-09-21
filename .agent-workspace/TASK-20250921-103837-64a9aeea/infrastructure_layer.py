# Infrastructure Layer Implementation for Clean Architecture
# Addresses critical performance, security, and data integrity issues

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator, TypeVar, Generic
import hashlib
import aiofiles
from functools import wraps

# Import domain and application interfaces
from domain_interfaces import (
    IRecipeRepository, IParameterRepository, IProcessRepository, IMachineRepository,
    IPLCService, IDataLogger, IEventBus, IEventHandler,
    ParameterValue, MachineState, MachineStatus, DataQuality
)
from application_layer import (
    IPerformanceMonitor, IHealthMonitor, ITaskScheduler
)

# Connection Pool and Database Infrastructure
class AsyncDatabasePool:
    """High-performance async database connection pool with connection pooling optimization"""

    def __init__(self, config: Dict[str, Any], pool_size: int = 20):
        self.config = config
        self.pool_size = pool_size
        self._pool = None
        self._prepared_statements = {}

    async def initialize(self):
        """Initialize connection pool with prepared statements"""
        import asyncpg

        self._pool = await asyncpg.create_pool(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            min_size=5,
            max_size=self.pool_size,
            command_timeout=5.0,
            server_settings={
                'application_name': 'ald_control_system',
                'tcp_keepalives_interval': '600',
                'tcp_keepalives_count': '3'
            }
        )

        # Pre-compile frequently used statements
        await self._prepare_statements()

    async def _prepare_statements(self):
        """Prepare frequently used SQL statements for performance"""
        statements = {
            'insert_parameter_history': """
                INSERT INTO parameter_value_history (parameter_id, value, timestamp, quality, source)
                VALUES ($1, $2, $3, $4, $5)
            """,
            'insert_process_data_point': """
                INSERT INTO process_data_points (process_id, parameter_id, value, timestamp, quality, source)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
            'get_machine_state': """
                SELECT status, current_process_id, last_heartbeat, error_message
                FROM machines WHERE id = $1
            """,
            'update_machine_state': """
                UPDATE machines SET status = $2, current_process_id = $3, last_heartbeat = $4, error_message = $5
                WHERE id = $1
            """,
            'get_active_parameters': """
                SELECT id, name, modbus_address, data_type, min_value, max_value, read_frequency
                FROM parameters WHERE active = true ORDER BY modbus_address
            """
        }

        async with self._pool.acquire() as conn:
            for name, sql in statements.items():
                self._prepared_statements[name] = await conn.prepare(sql)

    @asynccontextmanager
    async def acquire(self):
        """Acquire connection from pool"""
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        """Acquire connection and start transaction"""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def close(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()

# High-Performance Cache Implementation
class AsyncCache:
    """High-performance async cache with TTL and memory management"""

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if datetime.utcnow() > entry['expires']:
                del self._cache[key]
                return None

            return entry['value']

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl_seconds or self._default_ttl
        expires = datetime.utcnow() + timedelta(seconds=ttl)

        async with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self._max_size:
                await self._evict_expired()
                if len(self._cache) >= self._max_size:
                    # Remove oldest entry
                    oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]['created'])
                    del self._cache[oldest_key]

            self._cache[key] = {
                'value': value,
                'expires': expires,
                'created': datetime.utcnow()
            }

    async def _evict_expired(self):
        """Remove expired entries"""
        now = datetime.utcnow()
        expired_keys = [k for k, v in self._cache.items() if now > v['expires']]
        for key in expired_keys:
            del self._cache[key]

# Repository Implementations with Performance Optimizations
class SupabaseParameterRepository(IParameterRepository):
    """High-performance parameter repository with caching and bulk operations"""

    def __init__(self, db_pool: AsyncDatabasePool, cache: AsyncCache):
        self._db_pool = db_pool
        self._cache = cache

    async def get_by_id(self, parameter_id: str) -> 'Parameter':
        # Check cache first
        cached = await self._cache.get(f"parameter:{parameter_id}")
        if cached:
            return cached

        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM parameters WHERE id = $1", parameter_id
            )
            if not row:
                raise ValueError(f"Parameter {parameter_id} not found")

            parameter = self._map_to_domain(row)
            await self._cache.set(f"parameter:{parameter_id}", parameter, ttl_seconds=300)
            return parameter

    async def get_active_parameters(self) -> List['Parameter']:
        """Get active parameters with aggressive caching for performance"""
        cache_key = "active_parameters"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._db_pool.acquire() as conn:
            # Use prepared statement for performance
            stmt = self._db_pool._prepared_statements['get_active_parameters']
            rows = await conn.fetch(stmt.query)

            parameters = [self._map_to_domain(row) for row in rows]

            # Cache for 60 seconds for balance of consistency and performance
            await self._cache.set(cache_key, parameters, ttl_seconds=60)
            return parameters

    async def get_by_modbus_address(self, address: int) -> Optional['Parameter']:
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM parameters WHERE modbus_address = $1", address
            )
            return self._map_to_domain(row) if row else None

    async def save(self, parameter: 'Parameter') -> None:
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO parameters (id, name, modbus_address, data_type, min_value, max_value, active)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    modbus_address = EXCLUDED.modbus_address,
                    data_type = EXCLUDED.data_type,
                    min_value = EXCLUDED.min_value,
                    max_value = EXCLUDED.max_value,
                    active = EXCLUDED.active
            """, parameter.id, parameter.name, parameter.modbus_address,
                parameter.data_type.value, parameter.constraints.min_value,
                parameter.constraints.max_value, True)

        # Invalidate cache
        await self._cache.set(f"parameter:{parameter.id}", None, ttl_seconds=0)
        await self._cache.set("active_parameters", None, ttl_seconds=0)

    def _map_to_domain(self, row) -> 'Parameter':
        """Map database row to domain entity"""
        from domain_interfaces import Parameter, ParameterConstraints, ParameterDataType

        return Parameter(
            id=row['id'],
            name=row['name'],
            modbus_address=row['modbus_address'],
            data_type=ParameterDataType(row['data_type']),
            constraints=ParameterConstraints(
                min_value=row.get('min_value'),
                max_value=row.get('max_value'),
                data_type=ParameterDataType(row['data_type'])
            ),
            read_frequency=row.get('read_frequency')
        )

class SupabaseMachineRepository(IMachineRepository):
    """Machine repository with atomic state operations to prevent race conditions"""

    def __init__(self, db_pool: AsyncDatabasePool):
        self._db_pool = db_pool

    async def get_by_id(self, machine_id: str) -> 'Machine':
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM machines WHERE id = $1", machine_id)
            if not row:
                raise ValueError(f"Machine {machine_id} not found")
            return self._map_to_domain(row)

    async def get_current_state(self, machine_id: str) -> MachineState:
        """Atomic read of machine state to prevent race conditions"""
        async with self._db_pool.acquire() as conn:
            # Use prepared statement for performance
            stmt = self._db_pool._prepared_statements['get_machine_state']
            row = await conn.fetchrow(stmt.query, machine_id)

            if not row:
                raise ValueError(f"Machine {machine_id} not found")

            return MachineState(
                status=MachineStatus(row['status']),
                current_process_id=row['current_process_id'],
                last_heartbeat=row['last_heartbeat'] or datetime.utcnow(),
                error_message=row['error_message']
            )

    async def update_state(self, machine_id: str, new_state: MachineState) -> None:
        """Atomic state update to prevent race conditions"""
        async with self._db_pool.transaction() as trans:
            # Use prepared statement for performance
            stmt = self._db_pool._prepared_statements['update_machine_state']
            result = await trans.execute(
                stmt.query,
                machine_id,
                new_state.status.value,
                new_state.current_process_id,
                new_state.last_heartbeat,
                new_state.error_message
            )

            if result == "UPDATE 0":
                raise ValueError(f"Machine {machine_id} not found")

    async def save(self, machine: 'Machine') -> None:
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO machines (id, name, status, current_process_id, last_heartbeat)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    status = EXCLUDED.status,
                    current_process_id = EXCLUDED.current_process_id,
                    last_heartbeat = EXCLUDED.last_heartbeat
            """, machine.id, machine.name, machine.state.status.value,
                machine.state.current_process_id, machine.state.last_heartbeat)

    def _map_to_domain(self, row) -> 'Machine':
        """Map database row to domain entity"""
        from domain_interfaces import Machine

        return Machine(
            id=row['id'],
            name=row['name'],
            state=MachineState(
                status=MachineStatus(row['status']),
                current_process_id=row['current_process_id'],
                last_heartbeat=row['last_heartbeat'] or datetime.utcnow(),
                error_message=row.get('error_message')
            )
        )

# High-Performance Data Logger with Atomic Dual-Mode Operations
class SupabaseDataLogger(IDataLogger):
    """Data logger with atomic dual-table operations and performance optimization"""

    def __init__(self, db_pool: AsyncDatabasePool, performance_monitor: IPerformanceMonitor):
        self._db_pool = db_pool
        self._performance_monitor = performance_monitor

    async def log_process_data(
        self,
        process_id: str,
        parameter_values: List[ParameterValue]
    ) -> None:
        """Atomic dual-table logging for process mode - addresses critical race condition"""

        if not parameter_values:
            return

        with self._performance_monitor.measure("dual_table_logging"):
            async with self._db_pool.transaction() as trans:
                # Batch insert to parameter_value_history
                await self._bulk_insert_parameter_history(trans, parameter_values)

                # Batch insert to process_data_points
                await self._bulk_insert_process_data(trans, parameter_values, process_id)

    async def log_parameter_history(
        self,
        parameter_values: List[ParameterValue]
    ) -> None:
        """Single-table logging for idle mode - high performance"""

        if not parameter_values:
            return

        with self._performance_monitor.measure("parameter_history_logging"):
            async with self._db_pool.acquire() as conn:
                await self._bulk_insert_parameter_history(conn, parameter_values)

    async def _bulk_insert_parameter_history(
        self,
        conn,
        parameter_values: List[ParameterValue]
    ) -> None:
        """High-performance bulk insert to parameter_value_history"""

        # Prepare data for bulk insert
        data = [
            (pv.parameter_id, pv.value, pv.timestamp, pv.quality.value, pv.source)
            for pv in parameter_values
        ]

        # Use COPY for maximum performance with large batches
        if len(data) > 100:
            await conn.copy_records_to_table(
                'parameter_value_history',
                records=data,
                columns=['parameter_id', 'value', 'timestamp', 'quality', 'source']
            )
        else:
            # Use prepared statement for smaller batches
            stmt = self._db_pool._prepared_statements['insert_parameter_history']
            await conn.executemany(stmt.query, data)

    async def _bulk_insert_process_data(
        self,
        conn,
        parameter_values: List[ParameterValue],
        process_id: str
    ) -> None:
        """High-performance bulk insert to process_data_points"""

        # Prepare data for bulk insert
        data = [
            (process_id, pv.parameter_id, pv.value, pv.timestamp, pv.quality.value, pv.source)
            for pv in parameter_values
        ]

        # Use COPY for maximum performance with large batches
        if len(data) > 100:
            await conn.copy_records_to_table(
                'process_data_points',
                records=data,
                columns=['process_id', 'parameter_id', 'value', 'timestamp', 'quality', 'source']
            )
        else:
            # Use prepared statement for smaller batches
            stmt = self._db_pool._prepared_statements['insert_process_data_point']
            await conn.executemany(stmt.query, data)

# High-Performance Modbus PLC Adapter
class ModbusPLCAdapter(IPLCService):
    """High-performance Modbus PLC adapter with bulk operations and connection pooling"""

    def __init__(
        self,
        config: Dict[str, Any],
        performance_monitor: IPerformanceMonitor,
        connection_pool_size: int = 5
    ):
        self.config = config
        self._performance_monitor = performance_monitor
        self._connection_pool = None
        self._connection_pool_size = connection_pool_size
        self._parameter_cache = {}

    async def initialize(self):
        """Initialize connection pool"""
        from pymodbus.client.asynchronous.asyncio import AsyncModbusTCPClient

        self._connection_pool = []
        for _ in range(self._connection_pool_size):
            client = AsyncModbusTCPClient(
                host=self.config['ip_address'],
                port=self.config['port'],
                timeout=2.0
            )
            await client.connect()
            self._connection_pool.append(client)

    @asynccontextmanager
    async def _acquire_connection(self):
        """Acquire connection from pool"""
        if not self._connection_pool:
            raise RuntimeError("Connection pool not initialized")

        # Simple round-robin pool management
        client = self._connection_pool.pop(0)
        try:
            yield client
        finally:
            self._connection_pool.append(client)

    async def read_parameter(self, parameter_id: str) -> ParameterValue:
        """Read single parameter (legacy interface)"""
        parameters = await self.read_parameters_bulk([self._get_parameter_config(parameter_id)])
        return parameters[0] if parameters else None

    async def read_parameters_bulk(self, parameters: List['Parameter']) -> List[ParameterValue]:
        """High-performance bulk parameter reading with address grouping"""

        if not parameters:
            return []

        with self._performance_monitor.measure("bulk_plc_read"):
            # Group parameters by contiguous address ranges for bulk reads
            address_groups = self._group_by_address_ranges(parameters)

            # Read all groups concurrently
            tasks = [
                self._read_address_group(group)
                for group in address_groups
            ]

            try:
                group_results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                # Return failed parameter values for error handling
                return [
                    ParameterValue(
                        parameter_id=p.id,
                        value=0.0,
                        timestamp=datetime.utcnow(),
                        quality=DataQuality.BAD,
                        source="PLC_ERROR"
                    )
                    for p in parameters
                ]

            # Flatten and map to parameter values
            return self._map_to_parameter_values(group_results, parameters)

    def _group_by_address_ranges(self, parameters: List['Parameter']) -> List['AddressGroup']:
        """Group parameters by contiguous Modbus address ranges for bulk reads"""

        # Sort by address
        sorted_params = sorted(parameters, key=lambda p: p.modbus_address)

        groups = []
        current_group = []
        last_address = None

        for param in sorted_params:
            if last_address is None or param.modbus_address == last_address + 1:
                # Contiguous address
                current_group.append(param)
            else:
                # Address gap - start new group
                if current_group:
                    groups.append(self._create_address_group(current_group))
                current_group = [param]

            last_address = param.modbus_address

        # Add final group
        if current_group:
            groups.append(self._create_address_group(current_group))

        return groups

    def _create_address_group(self, parameters: List['Parameter']) -> 'AddressGroup':
        """Create address group for bulk read"""
        start_address = min(p.modbus_address for p in parameters)
        end_address = max(p.modbus_address for p in parameters)
        count = end_address - start_address + 1

        return AddressGroup(
            start_address=start_address,
            count=count,
            parameters=parameters
        )

    async def _read_address_group(self, group: 'AddressGroup') -> List[float]:
        """Read contiguous address group from PLC"""

        async with self._acquire_connection() as client:
            response = await client.read_holding_registers(
                address=group.start_address,
                count=group.count,
                unit=1
            )

            if response.isError():
                raise Exception(f"Modbus read error: {response}")

            return response.registers

    def _map_to_parameter_values(
        self,
        group_results: List[List[float]],
        parameters: List['Parameter']
    ) -> List[ParameterValue]:
        """Map raw register values to parameter values"""

        parameter_values = []
        timestamp = datetime.utcnow()

        # Create parameter lookup by address
        param_by_address = {p.modbus_address: p for p in parameters}

        # Process each group result
        address_offset = 0
        for group_registers in group_results:
            if isinstance(group_registers, Exception):
                continue

            for i, register_value in enumerate(group_registers):
                address = min(param_by_address.keys()) + address_offset + i
                parameter = param_by_address.get(address)

                if parameter:
                    # Convert register value based on parameter data type
                    converted_value = self._convert_register_value(
                        register_value, parameter.data_type
                    )

                    parameter_values.append(ParameterValue(
                        parameter_id=parameter.id,
                        value=converted_value,
                        timestamp=timestamp,
                        quality=DataQuality.GOOD,
                        source="PLC"
                    ))

            address_offset += len(group_registers)

        return parameter_values

    def _convert_register_value(self, register_value: int, data_type: 'ParameterDataType') -> float:
        """Convert raw register value based on parameter data type"""
        from domain_interfaces import ParameterDataType

        if data_type == ParameterDataType.FLOAT:
            # Convert 16-bit register to float (implementation depends on PLC format)
            return float(register_value) / 100.0  # Example scaling
        elif data_type == ParameterDataType.INTEGER:
            return float(register_value)
        elif data_type == ParameterDataType.BOOLEAN:
            return float(1 if register_value > 0 else 0)
        else:
            return float(register_value)

    async def write_parameter(self, parameter_id: str, value: float) -> bool:
        """Write parameter value to PLC"""
        parameter = self._get_parameter_config(parameter_id)

        async with self._acquire_connection() as client:
            # Convert value to register format
            register_value = self._convert_value_to_register(value, parameter.data_type)

            response = await client.write_register(
                address=parameter.modbus_address,
                value=register_value,
                unit=1
            )

            return not response.isError()

    async def control_valve(self, valve_number: int, state: bool, duration_ms: Optional[int] = None) -> bool:
        """Control valve state"""
        # Implementation depends on specific valve control registers
        valve_address = 1000 + valve_number  # Example addressing

        async with self._acquire_connection() as client:
            response = await client.write_coil(
                address=valve_address,
                value=state,
                unit=1
            )

            if duration_ms and state:
                # Schedule valve close after duration
                await asyncio.sleep(duration_ms / 1000.0)
                await client.write_coil(address=valve_address, value=False, unit=1)

            return not response.isError()

    async def execute_purge(self, duration_ms: int) -> bool:
        """Execute purge operation"""
        # Implementation depends on specific purge control
        purge_control_address = 2000
        purge_duration_address = 2001

        async with self._acquire_connection() as client:
            # Set duration
            await client.write_register(
                address=purge_duration_address,
                value=duration_ms,
                unit=1
            )

            # Start purge
            response = await client.write_coil(
                address=purge_control_address,
                value=True,
                unit=1
            )

            return not response.isError()

    def _get_parameter_config(self, parameter_id: str) -> 'Parameter':
        """Get parameter configuration (should be injected in real implementation)"""
        # This is a placeholder - in real implementation, this would be injected
        pass

    def _convert_value_to_register(self, value: float, data_type: 'ParameterDataType') -> int:
        """Convert float value to register format"""
        from domain_interfaces import ParameterDataType

        if data_type == ParameterDataType.FLOAT:
            return int(value * 100.0)  # Example scaling
        elif data_type == ParameterDataType.INTEGER:
            return int(value)
        elif data_type == ParameterDataType.BOOLEAN:
            return 1 if value > 0 else 0
        else:
            return int(value)

# Supporting Classes
@dataclass
class AddressGroup:
    start_address: int
    count: int
    parameters: List['Parameter']

# Event Bus Implementation
class AsyncEventBus(IEventBus):
    """High-performance async event bus with middleware support"""

    def __init__(self, logger: logging.Logger):
        self._handlers: Dict[type, List[IEventHandler]] = {}
        self._middleware: List['IEventMiddleware'] = []
        self._logger = logger

    def subscribe(self, event_type: type, handler: IEventHandler) -> None:
        """Subscribe handler to event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: 'DomainEvent') -> None:
        """Publish event to all registered handlers"""

        # Apply middleware before publish
        for middleware in self._middleware:
            await middleware.before_publish(event)

        # Get handlers for event type
        handlers = self._handlers.get(type(event), [])

        if handlers:
            # Execute all handlers concurrently with error isolation
            tasks = [self._safe_handle_event(handler, event) for handler in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Apply middleware after publish
        for middleware in self._middleware:
            await middleware.after_publish(event)

    async def _safe_handle_event(self, handler: IEventHandler, event: 'DomainEvent') -> None:
        """Handle event with error isolation"""
        try:
            await handler.handle(event)
        except Exception as e:
            self._logger.error(f"Error handling event {type(event).__name__}: {e}", exc_info=True)

    def add_middleware(self, middleware: 'IEventMiddleware') -> None:
        """Add event middleware"""
        self._middleware.append(middleware)

# Performance and Health Monitoring
class PerformanceMonitor(IPerformanceMonitor):
    """Performance monitoring with metrics collection"""

    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    def measure(self, operation_name: str) -> 'PerformanceContext':
        """Create performance measurement context"""
        return PerformanceContext(self, operation_name)

    async def record_metric(self, metric_name: str, value: float) -> None:
        """Record performance metric"""
        async with self._lock:
            if metric_name not in self._metrics:
                self._metrics[metric_name] = []

            self._metrics[metric_name].append(value)

            # Keep only last 1000 measurements
            if len(self._metrics[metric_name]) > 1000:
                self._metrics[metric_name] = self._metrics[metric_name][-1000:]

    async def get_metrics_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics summary"""
        async with self._lock:
            summary = {}
            for metric_name, values in self._metrics.items():
                if values:
                    summary[metric_name] = {
                        'count': len(values),
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'last': values[-1]
                    }
            return summary

class PerformanceContext:
    """Context manager for performance measurement"""

    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self._monitor = monitor
        self._operation_name = operation_name
        self._start_time = None

    def __enter__(self):
        self._start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time:
            duration_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
            asyncio.create_task(self._monitor.record_metric(self._operation_name, duration_ms))

# This infrastructure layer provides:
# 1. High-performance database operations with connection pooling
# 2. Atomic dual-table logging to fix race conditions
# 3. Bulk PLC operations for performance improvement
# 4. Comprehensive caching for parameter metadata
# 5. Event-driven architecture with performance monitoring
# 6. Error isolation and resilience patterns