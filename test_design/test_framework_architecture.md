# ALD Control System - Test Framework Architecture

**Version:** 1.0
**Date:** 2025-10-10
**Status:** Architecture Design

---

## Executive Summary

This document defines the comprehensive test framework architecture for the ALD Control System's 3-terminal architecture. The framework integrates unit, integration, stress, and end-to-end testing strategies while addressing the unique challenges of async operations, multi-terminal coordination, PLC simulation, and database isolation.

**Key Architecture Decisions:**
- pytest-based framework with async support (pytest-asyncio)
- Parallel test execution via pytest-xdist
- Terminal-specific test isolation
- Real PLC simulation (not just mocks)
- Database transaction-based isolation
- Fixture-based dependency injection
- Comprehensive stress and performance testing

---

## 1. Test Framework Architecture

### 1.1 Core Testing Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Execution Layer                      │
│  pytest + pytest-asyncio + pytest-xdist + pytest-cov        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Test Organization Layer                   │
│  Unit │ Integration │ E2E │ Stress │ Architecture           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Fixture & Utility Layer                   │
│  PLC Sim │ DB Isolation │ Terminal Orchestration │ Mocks    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  Real PLC │ Test Database │ Performance Monitor │ Coverage  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Test Runner Configuration

**pytest.ini:**
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Parallel execution
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-branch
    -n auto  # Auto-detect CPU cores for parallel execution

# Custom markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (medium speed, requires services)
    e2e: End-to-end tests (slow, full system)
    stress: Stress and performance tests (very slow)
    terminal1: Tests for Terminal 1 (PLC Data Service)
    terminal2: Tests for Terminal 2 (Recipe Service)
    terminal3: Tests for Terminal 3 (Parameter Service)
    multi_terminal: Tests requiring multiple terminals
    slow: Slow tests (>5 seconds)
    hardware: Requires real hardware (skip in CI)
    benchmark: Performance benchmark tests
    flaky: Potentially flaky tests (retry enabled)
    serial: Must run serially (no parallelization)

# Timeout settings
timeout = 300
timeout_method = thread

# Coverage settings
[coverage:run]
source = src
omit =
    */tests/*
    */debug/*
    */__pycache__/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

### 1.3 Fixture Architecture

**Fixture Hierarchy:**

```
Session-scoped Fixtures (created once per test session)
├── event_loop → Async event loop for all tests
├── test_database → Test database connection (isolated schema)
├── plc_simulation_server → PLC simulation server (pyModbusTCP server)
└── performance_baseline → Performance metrics baseline

Function-scoped Fixtures (created per test)
├── mock_plc → Mock PLC interface (unit tests)
├── mock_database → Mock database service (unit tests)
├── test_plc_connection → Real PLC simulation connection
├── isolated_db_transaction → Database transaction (auto-rollback)
├── temp_dir → Temporary directory for test files
└── test_data_factory → Factory for creating test data

Test-specific Fixtures (as needed)
├── terminal1_service → Terminal 1 service instance
├── terminal2_service → Terminal 2 service instance
├── terminal3_service → Terminal 3 service instance
├── multi_terminal_orchestrator → Coordinates multiple terminals
└── stress_test_monitor → Performance monitoring for stress tests
```

**Fixture Scopes Strategy:**
- **Session:** Expensive setup (database, PLC server) - shared across all tests
- **Module:** Shared state for related tests in one file
- **Function:** Default - isolated per test (most common)
- **Class:** Shared within test class

### 1.4 Mock vs Real Strategy

**When to Use Mocks:**
- Unit tests for business logic
- Testing error handling paths
- Fast feedback cycle (<100ms per test)
- No external dependencies needed

**When to Use Real Implementations:**
- Integration tests
- End-to-end tests
- Testing actual PLC communication
- Database query correctness
- Timing-sensitive tests (data collection precision)

**Mock Implementations:**
```python
# PLC Mock (fast, predictable)
@pytest.fixture
def mock_plc():
    from abstractions.interfaces import IPLCInterface
    mock = Mock(spec=IPLCInterface)
    mock.connect = AsyncMock(return_value=True)
    mock.read_parameter = AsyncMock(return_value=42.0)
    mock.write_parameter = AsyncMock(return_value=True)
    return mock

# Real PLC Simulation (accurate, slower)
@pytest.fixture(scope="session")
async def plc_simulation_server():
    from pyModbusTCP.server import ModbusServer
    server = ModbusServer(host="127.0.0.1", port=5020, no_block=True)
    server.start()
    yield server
    server.stop()

@pytest.fixture
async def test_plc_connection(plc_simulation_server):
    from src.plc.simulation_plc import SimulationPLC
    plc = SimulationPLC(host="127.0.0.1", port=5020)
    await plc.connect()
    yield plc
    await plc.disconnect()
```

---

## 2. Test Organization Structure

### 2.1 Directory Structure

```
tests/
├── conftest.py                          # Global fixtures and configuration
├── pytest.ini                           # Pytest configuration
│
├── unit/                                # Unit tests (fast, isolated)
│   ├── conftest.py                      # Unit test fixtures
│   ├── terminal1/                       # Terminal 1 unit tests
│   │   ├── test_plc_data_service.py
│   │   ├── test_data_collection_loop.py
│   │   ├── test_parameter_metadata.py
│   │   └── test_timing_precision.py
│   ├── terminal2/                       # Terminal 2 unit tests
│   │   ├── test_recipe_service.py
│   │   ├── test_recipe_executor.py
│   │   ├── test_step_executor.py
│   │   ├── test_loop_counting.py
│   │   └── test_cancellation.py
│   ├── terminal3/                       # Terminal 3 unit tests
│   │   ├── test_parameter_service.py
│   │   ├── test_command_processing.py
│   │   ├── test_plc_write_operations.py
│   │   ├── test_retry_logic.py
│   │   └── test_fallback_paths.py
│   ├── plc/                             # PLC module tests
│   │   ├── test_plc_manager.py
│   │   ├── test_simulation_plc.py
│   │   ├── test_communicator.py
│   │   └── test_factory.py
│   ├── database/                        # Database module tests
│   │   ├── test_database_service.py
│   │   ├── test_supabase_client.py
│   │   └── test_query_builder.py
│   └── utilities/                       # Utility module tests
│       ├── test_connection_monitor.py
│       ├── test_performance_monitor.py
│       └── test_logging.py
│
├── integration/                         # Integration tests (medium speed)
│   ├── conftest.py                      # Integration test fixtures
│   ├── terminal1/                       # Terminal 1 integration tests
│   │   ├── test_plc_database_integration.py
│   │   ├── test_data_collection_flow.py
│   │   ├── test_connection_recovery.py
│   │   └── test_signal_handling.py
│   ├── terminal2/                       # Terminal 2 integration tests
│   │   ├── test_recipe_command_flow.py
│   │   ├── test_recipe_execution_flow.py
│   │   ├── test_step_execution_flow.py
│   │   └── test_database_state_updates.py
│   ├── terminal3/                       # Terminal 3 integration tests
│   │   ├── test_parameter_command_flow.py
│   │   ├── test_parameter_write_flow.py
│   │   ├── test_confirmation_reads.py
│   │   └── test_database_polling.py
│   └── cross_terminal/                  # Multi-terminal integration
│       ├── test_plc_contention.py
│       ├── test_database_contention.py
│       ├── test_concurrent_operations.py
│       └── test_state_consistency.py
│
├── e2e/                                 # End-to-end tests (slow)
│   ├── conftest.py                      # E2E test fixtures
│   ├── test_full_recipe_execution.py    # Complete recipe workflow
│   ├── test_parameter_control_workflow.py
│   ├── test_data_collection_workflow.py
│   ├── test_multi_terminal_startup.py
│   ├── test_graceful_shutdown.py
│   └── test_failure_scenarios.py
│
├── stress/                              # Stress and performance tests
│   ├── conftest.py                      # Stress test fixtures
│   ├── database/
│   │   ├── test_connection_pool_stress.py
│   │   ├── test_query_rate_limits.py
│   │   ├── test_concurrent_writes.py
│   │   └── test_realtime_subscription_load.py
│   ├── plc/
│   │   ├── test_plc_concurrent_access.py
│   │   ├── test_plc_connection_limits.py
│   │   ├── test_modbus_protocol_stress.py
│   │   └── test_network_conditions.py
│   ├── stability/
│   │   ├── test_24hour_stability.py
│   │   ├── test_memory_leaks.py
│   │   ├── test_resource_cleanup.py
│   │   └── test_error_recovery.py
│   └── benchmarks/
│       ├── test_data_collection_performance.py
│       ├── test_recipe_execution_performance.py
│       └── test_parameter_write_performance.py
│
├── architecture/                        # Architecture compliance tests
│   ├── test_dependency_injection.py
│   ├── test_interface_compliance.py
│   ├── test_singleton_patterns.py
│   └── test_async_patterns.py
│
└── fixtures/                            # Reusable test fixtures
    ├── __init__.py
    ├── plc_fixtures.py                  # PLC-related fixtures
    ├── database_fixtures.py             # Database fixtures
    ├── terminal_fixtures.py             # Terminal service fixtures
    ├── data_factories.py                # Test data factories
    └── utilities.py                     # Test utilities
```

### 2.2 Test Naming Conventions

**File Naming:**
- `test_<module_name>.py` - Unit tests for specific module
- `test_<feature>_flow.py` - Integration tests for feature flow
- `test_<scenario>_workflow.py` - E2E tests for complete scenarios

**Test Function Naming:**
```python
# Unit tests
def test_<function>_<condition>_<expected_result>():
    """Example: test_read_parameter_when_connected_returns_value"""
    pass

# Integration tests
def test_<feature>_<scenario>():
    """Example: test_data_collection_handles_database_failure"""
    pass

# E2E tests
def test_<workflow>_<scenario>():
    """Example: test_recipe_execution_completes_successfully"""
    pass

# Edge cases
def test_<function>_<edge_case>_raises_<exception>():
    """Example: test_write_parameter_invalid_address_raises_error"""
    pass
```

### 2.3 Test Categorization

**Categories by Speed:**
- **Fast (<100ms):** Unit tests, mocks, pure logic
- **Medium (100ms-5s):** Integration tests, real services
- **Slow (5s-60s):** E2E tests, multi-terminal tests
- **Very Slow (>60s):** Stress tests, stability tests

**Categories by Scope:**
- **Unit:** Single function/class, mocked dependencies
- **Integration:** Multiple components, real dependencies
- **E2E:** Complete workflows, all terminals
- **Stress:** High load, edge conditions, performance

**Categories by Terminal:**
- **Terminal 1:** PLC data collection service
- **Terminal 2:** Recipe execution service
- **Terminal 3:** Parameter control service
- **Multi-terminal:** Cross-terminal interactions

---

## 3. Test Environment Setup

### 3.1 Environment Configuration

**Environment Variables:**
```bash
# Test Mode
export TEST_MODE=true
export LOG_LEVEL=DEBUG

# PLC Configuration
export PLC_TYPE=simulation
export PLC_HOST=127.0.0.1
export PLC_PORT=5020

# Database Configuration
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5432/test_ald
export SUPABASE_URL=https://test.supabase.co
export SUPABASE_KEY=test_key_for_testing
export SUPABASE_SERVICE_ROLE_KEY=test_service_key

# Machine Configuration
export MACHINE_ID=test-machine
export TERMINAL_ID=test-terminal

# Test-specific Settings
export ENABLE_PERFORMANCE_MONITORING=true
export ENABLE_COVERAGE_TRACKING=true
export PARALLEL_TEST_WORKERS=auto
```

### 3.2 Database Setup/Teardown Strategy

**Approach: Transaction-based Isolation**

```python
@pytest.fixture(scope="session")
async def test_database():
    """Create test database schema once per session."""
    from data_collection.database_service import DatabaseService

    db = DatabaseService()
    await db.connect()

    # Create test schema
    await db.execute_query("""
        CREATE SCHEMA IF NOT EXISTS test_schema;
        SET search_path TO test_schema;
    """)

    # Run migrations
    await db.execute_migrations("migrations/test_schema")

    yield db

    # Cleanup: Drop test schema
    await db.execute_query("DROP SCHEMA test_schema CASCADE;")
    await db.disconnect()

@pytest.fixture
async def isolated_db_transaction(test_database):
    """Provide isolated database transaction per test (auto-rollback)."""
    # Begin transaction
    await test_database.execute_query("BEGIN;")

    # Create savepoint for nested transactions
    await test_database.execute_query("SAVEPOINT test_savepoint;")

    yield test_database

    # Rollback transaction (undo all changes)
    await test_database.execute_query("ROLLBACK TO SAVEPOINT test_savepoint;")
    await test_database.execute_query("ROLLBACK;")
```

**Database Isolation Levels:**
- **Session:** Shared schema, separate from production
- **Test:** Transaction with auto-rollback
- **Parallel:** Each worker gets own database connection

### 3.3 PLC Simulation Configuration

**PLC Simulation Server Fixture:**

```python
@pytest.fixture(scope="session")
async def plc_simulation_server():
    """Start PLC simulation server for all tests."""
    from pyModbusTCP.server import ModbusServer

    server = ModbusServer(
        host="127.0.0.1",
        port=5020,
        no_block=True,
        data_bank={
            "holding_registers": [0] * 10000,  # 10000 registers
            "coils": [False] * 10000          # 10000 coils
        }
    )

    server.start()

    # Wait for server to be ready
    await asyncio.sleep(0.5)

    yield server

    server.stop()

@pytest.fixture
async def test_plc_manager(plc_simulation_server):
    """Provide PLCManager connected to simulation server."""
    from src.plc.manager import PLCManager

    # Override PLC configuration for testing
    os.environ["PLC_TYPE"] = "simulation"
    os.environ["PLC_HOST"] = "127.0.0.1"
    os.environ["PLC_PORT"] = "5020"

    manager = PLCManager()
    await manager.initialize()

    yield manager

    await manager.disconnect()
```

### 3.4 Terminal Orchestration

**Multi-Terminal Test Fixture:**

```python
@pytest.fixture
async def multi_terminal_orchestrator():
    """Orchestrate multiple terminals for integration tests."""

    class TerminalOrchestrator:
        def __init__(self):
            self.terminal1_process = None
            self.terminal2_process = None
            self.terminal3_process = None

        async def start_terminal1(self, config=None):
            """Start Terminal 1 (PLC Data Service)."""
            from plc_data_service import PLCDataService

            service = PLCDataService(config or {})
            self.terminal1_task = asyncio.create_task(service.run())

            # Wait for service to be ready
            await asyncio.sleep(1.0)

            return service

        async def start_terminal2(self, config=None):
            """Start Terminal 2 (Recipe Service)."""
            from simple_recipe_service import SimpleRecipeService

            service = SimpleRecipeService(config or {})
            self.terminal2_task = asyncio.create_task(service.run())

            await asyncio.sleep(1.0)

            return service

        async def start_terminal3(self, config=None):
            """Start Terminal 3 (Parameter Service)."""
            from parameter_service import ParameterService

            service = ParameterService(config or {})
            self.terminal3_task = asyncio.create_task(service.run())

            await asyncio.sleep(1.0)

            return service

        async def stop_all(self):
            """Stop all running terminals."""
            tasks = [t for t in [
                self.terminal1_task,
                self.terminal2_task,
                self.terminal3_task
            ] if t is not None]

            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

    orchestrator = TerminalOrchestrator()

    yield orchestrator

    await orchestrator.stop_all()
```

---

## 4. Test Utilities and Helpers

### 4.1 Async Test Utilities

```python
class AsyncTestHelpers:
    """Utilities for async testing."""

    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout=5.0,
        interval=0.1,
        error_message="Condition not met"
    ):
        """Wait for a condition to become true."""
        start_time = asyncio.get_event_loop().time()

        while True:
            result = await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func()

            if result:
                return True

            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"{error_message} within {timeout}s")

            await asyncio.sleep(interval)

    @staticmethod
    async def run_with_timeout(coro, timeout=5.0):
        """Run coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout}s")

    @staticmethod
    async def collect_events(event_queue, count, timeout=5.0):
        """Collect N events from async queue."""
        events = []
        deadline = asyncio.get_event_loop().time() + timeout

        while len(events) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Only collected {len(events)}/{count} events")

            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=remaining)
                events.append(event)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Only collected {len(events)}/{count} events")

        return events
```

### 4.2 Database Test Utilities

```python
class DatabaseTestHelpers:
    """Utilities for database testing."""

    @staticmethod
    async def insert_test_parameter(db, parameter_id, value, machine_id="test-machine"):
        """Insert test parameter value."""
        await db.execute_query("""
            INSERT INTO parameter_value_history
            (parameter_id, value, timestamp, machine_id)
            VALUES ($1, $2, NOW(), $3)
        """, parameter_id, value, machine_id)

    @staticmethod
    async def insert_test_recipe_command(db, recipe_id, status="pending", machine_id="test-machine"):
        """Insert test recipe command."""
        result = await db.execute_query("""
            INSERT INTO recipe_commands
            (recipe_id, status, machine_id, created_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id
        """, recipe_id, status, machine_id)

        return result[0]["id"]

    @staticmethod
    async def cleanup_test_data(db, machine_id="test-machine"):
        """Clean up all test data for machine."""
        await db.execute_query("""
            DELETE FROM parameter_value_history WHERE machine_id = $1;
            DELETE FROM recipe_commands WHERE machine_id = $1;
            DELETE FROM process_executions WHERE machine_id = $1;
            DELETE FROM parameter_control_commands WHERE machine_id = $1;
        """, machine_id)

    @staticmethod
    async def wait_for_database_record(
        db,
        table,
        condition,
        timeout=5.0
    ):
        """Wait for database record matching condition."""
        async def check_record():
            result = await db.execute_query(f"""
                SELECT * FROM {table} WHERE {condition}
            """)
            return len(result) > 0

        await AsyncTestHelpers.wait_for_condition(
            check_record,
            timeout=timeout,
            error_message=f"Record in {table} with {condition} not found"
        )
```

### 4.3 PLC Test Utilities

```python
class PLCTestHelpers:
    """Utilities for PLC testing."""

    @staticmethod
    async def set_plc_register(plc_server, address, value):
        """Set PLC holding register value."""
        plc_server.data_bank.set_holding_registers(address, [int(value)])

    @staticmethod
    async def get_plc_register(plc_server, address):
        """Get PLC holding register value."""
        return plc_server.data_bank.get_holding_registers(address, 1)[0]

    @staticmethod
    async def set_plc_coil(plc_server, address, value):
        """Set PLC coil value."""
        plc_server.data_bank.set_coils(address, [bool(value)])

    @staticmethod
    async def simulate_plc_disconnect(plc_manager):
        """Simulate PLC disconnection."""
        await plc_manager.disconnect()

    @staticmethod
    async def simulate_plc_error(plc_server, address):
        """Simulate PLC read/write error."""
        # Implementation depends on PLC server capabilities
        pass
```

### 4.4 Performance Test Utilities

```python
class PerformanceTestHelpers:
    """Utilities for performance testing."""

    @staticmethod
    def measure_execution_time(func):
        """Decorator to measure execution time."""
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            return result, duration
        return wrapper

    @staticmethod
    async def measure_throughput(operation, duration_seconds=10):
        """Measure operation throughput."""
        count = 0
        start = time.perf_counter()
        deadline = start + duration_seconds

        while time.perf_counter() < deadline:
            await operation()
            count += 1

        actual_duration = time.perf_counter() - start
        throughput = count / actual_duration

        return {
            "count": count,
            "duration": actual_duration,
            "throughput": throughput,
            "avg_time": actual_duration / count if count > 0 else 0
        }

    @staticmethod
    def assert_performance_threshold(
        measured_value,
        threshold,
        metric_name,
        comparison="<="
    ):
        """Assert performance meets threshold."""
        comparisons = {
            "<=": lambda a, b: a <= b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            ">": lambda a, b: a > b
        }

        if not comparisons[comparison](measured_value, threshold):
            raise AssertionError(
                f"{metric_name} {measured_value} does not meet threshold "
                f"{comparison} {threshold}"
            )
```

---

## 5. Parallel vs Serial Execution Strategy

### 5.1 Parallelization Rules

**Run in Parallel (default):**
- Unit tests (isolated, no shared state)
- Integration tests within same terminal
- Database tests with transaction isolation
- PLC tests with separate connections

**Must Run Serially:**
- Multi-terminal integration tests (marked `@pytest.mark.serial`)
- Tests modifying global state
- Tests with file system locks
- Stress tests measuring absolute performance

**Parallelization Configuration:**

```python
# conftest.py
def pytest_configure(config):
    """Configure parallel execution."""
    # Serial tests run in single worker
    config.option.dist = "loadscope"  # Distribute by test module

def pytest_collection_modifyitems(config, items):
    """Modify test collection for parallelization."""
    # Group serial tests together
    serial_items = []
    parallel_items = []

    for item in items:
        if "serial" in item.keywords:
            serial_items.append(item)
        else:
            parallel_items.append(item)

    # Serial tests run first in single worker
    items[:] = serial_items + parallel_items
```

### 5.2 Test Execution Order

**Execution Phases:**

1. **Phase 1 - Fast Unit Tests (parallel)**
   - Run all unit tests across N workers
   - Target: <5 minutes total

2. **Phase 2 - Integration Tests (parallel by terminal)**
   - Terminal 1 tests in worker 1
   - Terminal 2 tests in worker 2
   - Terminal 3 tests in worker 3
   - Target: <10 minutes total

3. **Phase 3 - Multi-Terminal Tests (serial)**
   - Run cross-terminal integration tests
   - Single worker to avoid conflicts
   - Target: <10 minutes total

4. **Phase 4 - E2E Tests (serial)**
   - Full workflow tests
   - Single worker
   - Target: <15 minutes total

5. **Phase 5 - Stress Tests (optional, serial)**
   - Only run on-demand or in nightly builds
   - Single worker
   - Target: <2 hours total

### 5.3 Test Isolation Strategy

**Isolation Mechanisms:**

```python
# File-level isolation (single instance locks)
@pytest.fixture
def isolated_lock_file(tmp_path):
    """Provide unique lock file per test."""
    lock_file = tmp_path / f"test_{uuid.uuid4()}.lock"
    yield str(lock_file)
    # Cleanup happens automatically

# Database isolation (transactions)
@pytest.fixture
async def isolated_db(test_database):
    """Provide isolated database transaction."""
    await test_database.execute_query("BEGIN;")
    yield test_database
    await test_database.execute_query("ROLLBACK;")

# PLC isolation (separate connections)
@pytest.fixture
async def isolated_plc(plc_simulation_server):
    """Provide isolated PLC connection."""
    plc = SimulationPLC(host="127.0.0.1", port=5020)
    await plc.connect()
    yield plc
    await plc.disconnect()
```

---

## 6. Coverage Strategy

### 6.1 Coverage Targets

**Overall Coverage Goals:**
- **Minimum:** 80% code coverage
- **Target:** 90% code coverage
- **Stretch:** 95% code coverage

**Coverage by Component:**

| Component | Target Coverage | Priority | Notes |
|-----------|----------------|----------|-------|
| PLC Data Service (Terminal 1) | 95% | CRITICAL | Core data collection |
| Recipe Service (Terminal 2) | 90% | HIGH | Recipe execution |
| Parameter Service (Terminal 3) | 90% | HIGH | Parameter control |
| PLC Manager | 95% | CRITICAL | Hardware interface |
| Database Service | 85% | HIGH | Data persistence |
| Recipe Executor | 90% | HIGH | Core business logic |
| Step Executor | 90% | HIGH | Step execution |
| Connection Monitor | 80% | MEDIUM | Utility |
| Performance Monitor | 75% | MEDIUM | Non-critical |
| Logging | 70% | LOW | Support functionality |

### 6.2 Branch Coverage Requirements

**Branch Coverage Strategy:**
- All critical paths: 100% branch coverage
- Error handling: 90% branch coverage
- Edge cases: 85% branch coverage
- Utility functions: 80% branch coverage

**Critical Paths Requiring 100% Coverage:**
- PLC connection/disconnection
- Database transactions
- Recipe execution state machine
- Parameter write operations
- Data collection loop
- Error recovery paths

### 6.3 Integration Coverage Approach

**Integration Coverage Matrix:**

```
         │ PLC │ DB │ T1 │ T2 │ T3 │ Monitor
─────────┼─────┼────┼────┼────┼────┼─────────
PLC      │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
DB       │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
T1       │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
T2       │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
T3       │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
Monitor  │  ✓  │ ✓  │ ✓  │ ✓  │ ✓  │   ✓
```

**Integration Test Coverage:**
- Every component pair: At least 1 integration test
- Critical paths: At least 3 integration tests
- Error paths: At least 2 integration tests

### 6.4 Edge Case Coverage Tracking

**Edge Case Categories:**
1. **Input Validation** (100% coverage required)
   - Invalid data types
   - Out-of-range values
   - Missing required fields
   - Malformed data structures

2. **Error Conditions** (90% coverage required)
   - Connection failures
   - Timeout scenarios
   - Database errors
   - PLC communication errors

3. **Concurrency** (85% coverage required)
   - Race conditions
   - Deadlocks
   - Resource contention
   - Concurrent access

4. **State Transitions** (95% coverage required)
   - Invalid state transitions
   - State consistency
   - Rollback scenarios
   - Recovery paths

---

## 7. Tool Recommendations

### 7.1 Required Tools

**Core Testing:**
- `pytest==8.3.3` - Test framework
- `pytest-asyncio==0.24.0` - Async test support
- `pytest-xdist==3.6.0` - Parallel test execution
- `pytest-cov==5.0.0` - Coverage reporting
- `pytest-mock==3.14.0` - Mocking utilities
- `pytest-timeout==2.3.1` - Test timeout enforcement

**Additional Testing Tools:**
- `pytest-benchmark==4.0.0` - Performance benchmarking
- `pytest-retry==1.6.3` - Retry flaky tests
- `pytest-html==4.1.1` - HTML test reports
- `pytest-json-report==1.5.0` - JSON test reports

**Mocking and Simulation:**
- `pyModbusTCP==0.2.0` - PLC simulation server
- `faker==24.0.0` - Test data generation
- `freezegun==1.5.0` - Time mocking
- `responses==0.25.0` - HTTP mocking

**Performance and Profiling:**
- `psutil==5.9.8` - Process monitoring
- `memory-profiler==0.61.0` - Memory profiling
- `py-spy==0.3.14` - Python profiler

**Coverage and Quality:**
- `coverage[toml]==7.6.0` - Coverage measurement
- `diff-cover==9.0.0` - Diff coverage reports
- `mutmut==2.4.5` - Mutation testing

### 7.2 CI/CD Integration Tools

**GitHub Actions / GitLab CI:**
```yaml
# .github/workflows/tests.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/unit -v -n auto --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/integration -v -n auto

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/e2e -v --timeout=300
```

### 7.3 Development Tools

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest-quick
        entry: pytest tests/unit -v -x
        language: system
        pass_filenames: false
        always_run: true
```

**Test Helper Scripts:**
```bash
# scripts/test-quick.sh - Fast feedback
pytest tests/unit -v -x --ff

# scripts/test-integration.sh - Integration tests
pytest tests/integration -v -n auto

# scripts/test-full.sh - Full test suite
pytest tests/ -v -n auto --cov=src --cov-report=html

# scripts/test-coverage.sh - Coverage report
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html
coverage report --fail-under=80

# scripts/test-stress.sh - Stress tests
pytest tests/stress -v --timeout=7200

# scripts/test-terminal.sh - Terminal-specific tests
pytest tests/unit/terminal$1 tests/integration/terminal$1 -v
```

---

## 8. Implementation Roadmap

### 8.1 Phase 1: Foundation (Week 1-2)

**Tasks:**
1. ✅ Enhance `conftest.py` with comprehensive fixtures
2. ✅ Create PLC simulation server fixture
3. ✅ Implement database transaction isolation
4. ✅ Create async test utilities
5. ✅ Set up pytest configuration
6. ✅ Configure parallel execution
7. ✅ Set up coverage reporting

**Deliverables:**
- Enhanced `tests/conftest.py`
- `tests/fixtures/` directory with all fixtures
- `pytest.ini` configuration
- `.coveragerc` configuration
- Test utility modules

### 8.2 Phase 2: Unit Tests (Week 3-4)

**Tasks:**
1. Implement Terminal 1 unit tests (all edge cases)
2. Implement Terminal 2 unit tests (all edge cases)
3. Implement Terminal 3 unit tests (all edge cases)
4. Implement PLC module unit tests
5. Implement database module unit tests
6. Achieve 80%+ unit test coverage

**Deliverables:**
- `tests/unit/terminal1/` (complete)
- `tests/unit/terminal2/` (complete)
- `tests/unit/terminal3/` (complete)
- `tests/unit/plc/` (complete)
- `tests/unit/database/` (complete)
- Coverage report ≥80%

### 8.3 Phase 3: Integration Tests (Week 5-6)

**Tasks:**
1. Implement Terminal 1 integration tests
2. Implement Terminal 2 integration tests
3. Implement Terminal 3 integration tests
4. Implement cross-terminal integration tests
5. Test PLC contention scenarios
6. Test database contention scenarios

**Deliverables:**
- `tests/integration/terminal1/` (complete)
- `tests/integration/terminal2/` (complete)
- `tests/integration/terminal3/` (complete)
- `tests/integration/cross_terminal/` (complete)
- Integration coverage report

### 8.4 Phase 4: E2E and Stress Tests (Week 7-8)

**Tasks:**
1. Implement E2E workflow tests
2. Implement stress tests (database, PLC, stability)
3. Implement performance benchmarks
4. Set up long-running stability tests
5. Configure CI/CD pipeline

**Deliverables:**
- `tests/e2e/` (complete)
- `tests/stress/` (complete)
- CI/CD configuration
- Performance baseline documentation
- Complete test documentation

### 8.5 Phase 5: Optimization and Maintenance (Ongoing)

**Tasks:**
1. Monitor test execution time
2. Optimize slow tests
3. Reduce flaky tests
4. Improve coverage gaps
5. Update tests for new features

**Metrics:**
- Test suite execution time: <30 minutes
- Test flakiness rate: <1%
- Coverage: ≥90%
- Stress test pass rate: ≥95%

---

## 9. Success Metrics

### 9.1 Quantitative Metrics

**Test Coverage:**
- ✅ Unit test coverage ≥80%
- ✅ Integration test coverage ≥70%
- ✅ Overall code coverage ≥85%
- ✅ Branch coverage ≥80%

**Test Execution:**
- ✅ Unit tests complete in <5 minutes
- ✅ Integration tests complete in <15 minutes
- ✅ Full suite (excluding stress) completes in <30 minutes
- ✅ Test flakiness rate <1%

**Test Quality:**
- ✅ All critical paths have tests
- ✅ All edge cases documented and tested
- ✅ All failure scenarios tested
- ✅ No untested code in production paths

### 9.2 Qualitative Metrics

**Code Quality:**
- ✅ Tests are readable and maintainable
- ✅ Tests follow consistent patterns
- ✅ Test failures provide clear error messages
- ✅ Tests serve as documentation

**Developer Experience:**
- ✅ Fast feedback cycle (<5 minutes for unit tests)
- ✅ Easy to run tests locally
- ✅ Clear test organization
- ✅ Good test isolation (no flakiness)

**Confidence:**
- ✅ Developers trust the test suite
- ✅ Safe to refactor with test coverage
- ✅ Bugs caught before production
- ✅ Regression prevention

---

## 10. Appendix

### 10.1 Test Data Factories

```python
# tests/fixtures/data_factories.py

class ParameterDataFactory:
    """Factory for creating test parameter data."""

    @staticmethod
    def create_parameter(
        parameter_id=1,
        name="test_parameter",
        modbus_address=100,
        data_type="float",
        min_value=0.0,
        max_value=100.0
    ):
        return {
            "id": parameter_id,
            "name": name,
            "modbus_address": modbus_address,
            "data_type": data_type,
            "min_value": min_value,
            "max_value": max_value
        }

    @staticmethod
    def create_parameter_value(
        parameter_id=1,
        value=42.0,
        timestamp=None,
        machine_id="test-machine"
    ):
        return {
            "parameter_id": parameter_id,
            "value": value,
            "timestamp": timestamp or datetime.now().isoformat(),
            "machine_id": machine_id
        }

class RecipeDataFactory:
    """Factory for creating test recipe data."""

    @staticmethod
    def create_recipe(
        recipe_id=1,
        name="test_recipe",
        steps=None
    ):
        if steps is None:
            steps = [
                {"type": "valve", "valve_number": 1, "state": "open", "duration": 5.0},
                {"type": "purge", "duration": 10.0},
                {"type": "set parameter", "parameter_name": "temperature", "value": 100.0}
            ]

        return {
            "id": recipe_id,
            "name": name,
            "steps": steps,
            "created_at": datetime.now().isoformat()
        }

    @staticmethod
    def create_recipe_command(
        recipe_id=1,
        status="pending",
        machine_id="test-machine"
    ):
        return {
            "recipe_id": recipe_id,
            "status": status,
            "machine_id": machine_id,
            "created_at": datetime.now().isoformat()
        }

class CommandDataFactory:
    """Factory for creating test command data."""

    @staticmethod
    def create_parameter_command(
        parameter_name="test_parameter",
        target_value=42.0,
        machine_id="test-machine",
        timeout_ms=5000
    ):
        return {
            "parameter_name": parameter_name,
            "target_value": target_value,
            "machine_id": machine_id,
            "timeout_ms": timeout_ms,
            "created_at": datetime.now().isoformat()
        }
```

### 10.2 Common Test Patterns

**Pattern 1: Testing Async Functions**
```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function with proper await."""
    result = await async_function()
    assert result == expected_value
```

**Pattern 2: Testing Exceptions**
```python
@pytest.mark.asyncio
async def test_function_raises_exception():
    """Test that function raises expected exception."""
    with pytest.raises(ExpectedException, match="expected message"):
        await function_that_raises()
```

**Pattern 3: Testing with Mocks**
```python
@pytest.mark.asyncio
async def test_with_mock(mock_plc):
    """Test using mock dependency."""
    service = Service(plc=mock_plc)
    await service.operation()

    mock_plc.read_parameter.assert_called_once_with(parameter_id=1)
```

**Pattern 4: Testing with Real Services**
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_with_real_service(test_plc_manager, isolated_db):
    """Test using real services."""
    service = Service(plc=test_plc_manager, db=isolated_db)
    result = await service.operation()

    assert result is not None
```

**Pattern 5: Testing Time-Dependent Code**
```python
@pytest.mark.asyncio
async def test_time_dependent(async_test_helpers):
    """Test time-dependent behavior."""
    start_time = time.time()

    await async_test_helpers.wait_for_condition(
        lambda: check_condition(),
        timeout=5.0
    )

    duration = time.time() - start_time
    assert duration < 5.0
```

### 10.3 Troubleshooting Guide

**Issue: Tests are slow**
- Solution: Use mocks for unit tests, reserve real services for integration
- Check: Are you running tests in parallel? (`pytest -n auto`)
- Check: Are database transactions being rolled back?

**Issue: Tests are flaky**
- Solution: Add proper waits and timeouts
- Check: Are tests properly isolated?
- Check: Are there race conditions?
- Use: `@pytest.mark.flaky(reruns=3)` as last resort

**Issue: Coverage is low**
- Solution: Add tests for uncovered branches
- Check: Run `coverage report --show-missing`
- Focus: Critical paths first, utilities last

**Issue: Tests fail in CI but pass locally**
- Solution: Check environment variables
- Check: Database configuration
- Check: Timing-dependent tests
- Check: Parallel execution conflicts

---

## Conclusion

This test framework architecture provides a comprehensive, production-ready testing strategy for the ALD Control System. By following this architecture, we ensure:

1. **High Coverage:** ≥85% code coverage with focus on critical paths
2. **Fast Feedback:** Unit tests complete in <5 minutes
3. **Reliability:** Test isolation prevents flakiness
4. **Maintainability:** Clear organization and patterns
5. **Confidence:** Comprehensive coverage of edge cases and failure scenarios

The framework supports all test types (unit, integration, e2e, stress) while maintaining fast execution times through parallelization and smart fixture management.
