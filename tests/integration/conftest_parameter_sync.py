"""
Parameter Synchronization Integration Test Configuration

Provides specialized fixtures and configuration for parameter synchronization
integration tests. Extends the main conftest.py with parameter-specific
test utilities and mock configurations.
"""

import os
import sys
import asyncio
import pytest
import uuid
from datetime import datetime
from typing import Generator, AsyncGenerator, Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch

# Add src to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) + "/src")

from src.db import get_supabase
from src.data_collection.transactional.interfaces import ParameterData, MachineState, DualModeResult
from src.plc.manager import plc_manager


@pytest.fixture(scope="session")
def parameter_sync_test_config():
    """Configuration for parameter synchronization tests."""
    return {
        "test_machine_id": f"test-machine-{uuid.uuid4()}",
        "test_parameters_count": 10,
        "performance_target_ms": 1000,
        "concurrent_operations": 5,
        "parameter_batch_size": 50
    }


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for parameter synchronization tests."""
    mock_client = Mock()

    # Mock table operations
    mock_table = Mock()
    mock_client.table.return_value = mock_table

    # Mock query operations
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.single.return_value = mock_table
    mock_table.limit.return_value = mock_table

    # Mock execute with configurable responses
    mock_table.execute.return_value = Mock(data=[
        {
            "id": str(uuid.uuid4()),
            "current_value": 50.0,
            "set_value": 50.0,
            "updated_at": datetime.now().isoformat()
        }
    ])

    return mock_client


@pytest.fixture
def mock_enhanced_plc():
    """Mock PLC interface with enhanced parameter synchronization capabilities."""
    mock_plc = Mock()

    # Standard PLC operations
    mock_plc.connect = AsyncMock(return_value=True)
    mock_plc.disconnect = AsyncMock()
    mock_plc.is_connected = Mock(return_value=True)
    mock_plc.get_connection_status = Mock(return_value="connected")

    # Parameter operations
    mock_plc.read_parameter = AsyncMock(return_value=42.0)
    mock_plc.write_parameter = AsyncMock(return_value=True)
    mock_plc.read_all_parameters = AsyncMock(return_value={
        "1": 42.0,
        "2": 84.0,
        "3": 126.0
    })

    # Enhanced operations for synchronization testing
    mock_plc.read_multiple_parameters = AsyncMock(return_value={
        "param_1": 10.5,
        "param_2": 20.5,
        "param_3": 30.5
    })

    # Valve and purge operations
    mock_plc.control_valve = AsyncMock(return_value=True)
    mock_plc.execute_purge = AsyncMock(return_value=True)

    return mock_plc


@pytest.fixture
def mock_dual_mode_repository():
    """Mock dual mode repository for transaction testing."""
    mock_repo = Mock()

    # Enhanced dual mode operations
    mock_repo.insert_dual_mode_atomic = AsyncMock(return_value=DualModeResult(
        history_count=3,
        process_count=0,
        component_updates_count=3,  # Enhanced: component_parameters updated
        machine_state=MachineState("idle", None, datetime.now()),
        transaction_id=str(uuid.uuid4()),
        success=True
    ))

    mock_repo.insert_history_only = AsyncMock(return_value=3)
    mock_repo.validate_batch_constraints = AsyncMock(return_value=[])

    return mock_repo


@pytest.fixture
def sample_parameter_data():
    """Sample parameter data for testing."""
    return [
        ParameterData(
            parameter_id="param_1",
            value=42.5,
            set_point=45.0,
            timestamp=datetime.now()
        ),
        ParameterData(
            parameter_id="param_2",
            value=84.0,
            set_point=85.0,
            timestamp=datetime.now()
        ),
        ParameterData(
            parameter_id="param_3",
            value=126.5,
            set_point=130.0,
            timestamp=datetime.now()
        )
    ]


@pytest.fixture
def sample_machine_states():
    """Sample machine states for testing."""
    return {
        "idle": MachineState(
            status="idle",
            current_process_id=None,
            timestamp=datetime.now()
        ),
        "processing": MachineState(
            status="processing",
            current_process_id=str(uuid.uuid4()),
            timestamp=datetime.now()
        ),
        "error": MachineState(
            status="error",
            current_process_id=None,
            timestamp=datetime.now()
        )
    }


@pytest.fixture
async def test_parameter_factory(mock_supabase):
    """Factory for creating test parameters in the database."""
    created_params = []

    async def create_parameter(name: str = None, **kwargs) -> str:
        param_id = str(uuid.uuid4())
        param_data = {
            "id": param_id,
            "name": name or f"test_param_{len(created_params)}",
            "display_name": kwargs.get("display_name", "Test Parameter"),
            "unit": kwargs.get("unit", "units"),
            "min_value": kwargs.get("min_value", 0.0),
            "max_value": kwargs.get("max_value", 1000.0),
            "default_value": kwargs.get("default_value", 50.0),
            "current_value": kwargs.get("current_value", 50.0),
            "set_value": kwargs.get("set_value", 50.0),
            "read_modbus_address": kwargs.get("read_modbus_address", 1001 + len(created_params)),
            "write_modbus_address": kwargs.get("write_modbus_address", 2001 + len(created_params)),
            "component_id": kwargs.get("component_id", str(uuid.uuid4())),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Mock database insert
        mock_supabase.table("component_parameters").insert(param_data).execute.return_value = Mock(
            data=[param_data]
        )

        created_params.append(param_id)
        return param_id

    yield create_parameter

    # Cleanup (if using real database)
    # for param_id in created_params:
    #     try:
    #         mock_supabase.table("component_parameters").delete().eq("id", param_id).execute()
    #     except:
    #         pass


@pytest.fixture
async def test_process_factory(mock_supabase):
    """Factory for creating test process executions."""
    created_processes = []

    async def create_process(recipe_id: str = None, **kwargs) -> str:
        process_id = str(uuid.uuid4())
        process_data = {
            "id": process_id,
            "session_id": kwargs.get("session_id", str(uuid.uuid4())),
            "machine_id": kwargs.get("machine_id", f"test-machine-{uuid.uuid4()}"),
            "recipe_id": recipe_id or str(uuid.uuid4()),
            "recipe_version": kwargs.get("recipe_version", {}),
            "start_time": kwargs.get("start_time", datetime.now().isoformat()),
            "operator_id": kwargs.get("operator_id", str(uuid.uuid4())),
            "status": kwargs.get("status", "running"),
            "parameters": kwargs.get("parameters", {}),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Mock database insert
        mock_supabase.table("process_executions").insert(process_data).execute.return_value = Mock(
            data=[process_data]
        )

        # Create execution state
        state_data = {
            "execution_id": process_id,
            "current_step_index": 0,
            "current_overall_step": 0,
            "total_overall_steps": kwargs.get("total_steps", 1),
            "progress": {"total_steps": kwargs.get("total_steps", 1), "completed_steps": 0},
            "created_at": datetime.now().isoformat()
        }

        mock_supabase.table("process_execution_state").insert(state_data).execute.return_value = Mock(
            data=[state_data]
        )

        created_processes.append(process_id)
        return process_id

    yield create_process

    # Cleanup (if using real database)
    # for process_id in created_processes:
    #     try:
    #         mock_supabase.table("process_executions").delete().eq("id", process_id).execute()
    #         mock_supabase.table("process_execution_state").delete().eq("execution_id", process_id).execute()
    #     except:
    #         pass


@pytest.fixture
def performance_monitor():
    """Performance monitoring utilities for parameter sync tests."""
    import time
    import psutil
    import threading
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class ParameterSyncMetrics:
        operation_type: str
        duration_ms: float
        parameters_processed: int
        memory_peak_mb: float
        cpu_usage_percent: float
        throughput_params_per_sec: float
        database_operations: int
        transaction_count: int

    class ParameterSyncMonitor:
        def __init__(self):
            self.metrics = []
            self.start_time = None
            self.monitoring = False
            self.peak_memory = 0
            self.cpu_samples = []

        def start_monitoring(self, operation_type: str):
            self.operation_type = operation_type
            self.start_time = time.time()
            self.monitoring = True
            self.peak_memory = 0
            self.cpu_samples = []
            self._start_system_monitoring()

        def stop_monitoring(self, parameters_processed: int, db_ops: int = 0, txn_count: int = 0):
            self.monitoring = False
            if self.start_time is None:
                return None

            duration_ms = (time.time() - self.start_time) * 1000
            throughput = parameters_processed / (duration_ms / 1000) if duration_ms > 0 else 0
            avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0

            metrics = ParameterSyncMetrics(
                operation_type=self.operation_type,
                duration_ms=duration_ms,
                parameters_processed=parameters_processed,
                memory_peak_mb=self.peak_memory,
                cpu_usage_percent=avg_cpu,
                throughput_params_per_sec=throughput,
                database_operations=db_ops,
                transaction_count=txn_count
            )

            self.metrics.append(metrics)
            return metrics

        def _start_system_monitoring(self):
            def monitor():
                process = psutil.Process()
                while self.monitoring:
                    try:
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        cpu_percent = process.cpu_percent()

                        self.peak_memory = max(self.peak_memory, memory_mb)
                        self.cpu_samples.append(cpu_percent)

                        time.sleep(0.1)
                    except:
                        break

            thread = threading.Thread(target=monitor, daemon=True)
            thread.start()

        def get_summary(self) -> Dict[str, Any]:
            if not self.metrics:
                return {}

            return {
                "total_operations": len(self.metrics),
                "avg_duration_ms": sum(m.duration_ms for m in self.metrics) / len(self.metrics),
                "total_parameters": sum(m.parameters_processed for m in self.metrics),
                "avg_throughput": sum(m.throughput_params_per_sec for m in self.metrics) / len(self.metrics),
                "peak_memory_mb": max(m.memory_peak_mb for m in self.metrics),
                "avg_cpu_percent": sum(m.cpu_usage_percent for m in self.metrics) / len(self.metrics),
                "total_db_operations": sum(m.database_operations for m in self.metrics),
                "total_transactions": sum(m.transaction_count for m in self.metrics)
            }

    return ParameterSyncMonitor()


@pytest.fixture
def transaction_test_helper():
    """Helper utilities for transaction integrity testing."""
    class TransactionTestHelper:
        def __init__(self):
            self.transaction_log = []
            self.rollback_log = []

        async def simulate_transaction_failure(self, failure_point: str, error_message: str):
            """Simulate transaction failure at specific point."""
            self.transaction_log.append({
                "type": "failure",
                "point": failure_point,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
            raise RuntimeError(f"Simulated failure at {failure_point}: {error_message}")

        async def simulate_rollback(self, transaction_id: str, operations: List[Dict]):
            """Simulate transaction rollback with compensation actions."""
            self.rollback_log.append({
                "transaction_id": transaction_id,
                "operations": operations,
                "timestamp": datetime.now().isoformat()
            })

        def verify_atomicity(self, expected_operations: int, actual_operations: int):
            """Verify all-or-nothing property."""
            return actual_operations in [0, expected_operations]

        def verify_consistency(self, before_state: Dict, after_state: Dict, expected_changes: Dict):
            """Verify consistency constraints."""
            for key, expected_value in expected_changes.items():
                if after_state.get(key) != expected_value:
                    return False
            return True

    return TransactionTestHelper()


@pytest.fixture(autouse=True)
def setup_parameter_sync_environment():
    """Setup environment for parameter synchronization tests."""
    # Set test environment variables
    os.environ.update({
        "PARAMETER_SYNC_TEST_MODE": "true",
        "TRANSACTION_TIMEOUT_MS": "5000",
        "BATCH_SIZE": "50",
        "PERFORMANCE_MONITORING": "true"
    })

    yield

    # Cleanup
    for key in ["PARAMETER_SYNC_TEST_MODE", "TRANSACTION_TIMEOUT_MS", "BATCH_SIZE", "PERFORMANCE_MONITORING"]:
        os.environ.pop(key, None)


@pytest.fixture
def async_test_utilities():
    """Utilities for async testing with timeouts and concurrency."""
    class AsyncTestUtils:
        @staticmethod
        async def run_concurrent_operations(operations: List, max_concurrent: int = 5):
            """Run operations concurrently with controlled concurrency."""
            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_with_semaphore(operation):
                async with semaphore:
                    return await operation()

            tasks = [run_with_semaphore(op) for op in operations]
            return await asyncio.gather(*tasks, return_exceptions=True)

        @staticmethod
        async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
            """Wait for condition to become true with timeout."""
            start_time = asyncio.get_event_loop().time()

            while True:
                if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                    return True

                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError(f"Condition not met within {timeout} seconds")

                await asyncio.sleep(interval)

        @staticmethod
        async def measure_async_operation(operation):
            """Measure duration of async operation."""
            start_time = time.time()
            result = await operation()
            duration = time.time() - start_time
            return result, duration

    return AsyncTestUtils()


# Test markers for parameter synchronization tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.sync,
    pytest.mark.asyncio
]