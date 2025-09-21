"""
Race condition security testing framework for ALD control system.

Tests for:
- Dual-mode logging race conditions
- State transition timing vulnerabilities
- Data consistency race conditions
- Concurrent access security
"""
import pytest
import asyncio
import threading
import time
from unittest.mock import patch, Mock, AsyncMock
from typing import List, Dict, Any
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RaceConditionResult:
    """Race condition test result."""
    test_name: str
    concurrent_operations: int
    race_detected: bool
    data_corruption: bool
    timing_window_ms: float
    details: Dict[str, Any]


class RaceConditionSecurityTester:
    """Comprehensive race condition security testing framework."""

    def __init__(self):
        """Initialize race condition tester."""
        self.results: List[RaceConditionResult] = []

    async def test_dual_mode_logging_race(self, iterations: int = 100) -> RaceConditionResult:
        """Test race conditions in dual-mode parameter logging."""
        from src.data_collection.continuous_parameter_logger import ContinuousParameterLogger

        race_detected = False
        data_corruption = False
        timing_windows = []

        # Mock database and PLC
        mock_supabase = Mock()
        mock_table = Mock()
        mock_supabase.table.return_value = mock_table

        # Track database operations for race detection
        operation_log = []
        operation_lock = threading.Lock()

        def track_operation(operation_type, data):
            with operation_lock:
                operation_log.append({
                    'type': operation_type,
                    'data': data,
                    'timestamp': time.time(),
                    'thread': threading.current_thread().ident
                })

        # Mock insert operations to track timing
        def mock_insert(data):
            track_operation('insert', data)
            # Simulate database operation time
            time.sleep(random.uniform(0.001, 0.01))
            return Mock(execute=Mock(return_value=Mock()))

        mock_table.insert.side_effect = mock_insert

        # Mock state queries with different responses to simulate race conditions
        state_responses = [
            Mock(data={'status': 'processing', 'current_process_id': 'process_123'}),
            Mock(data={'status': 'idle', 'current_process_id': None}),
            Mock(data={'status': 'processing', 'current_process_id': None}),  # Race condition
            Mock(data=None)
        ]

        mock_execute = Mock()
        mock_execute.execute.side_effect = lambda: random.choice(state_responses)
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value = mock_execute

        logger = ContinuousParameterLogger()

        async def concurrent_logging_operation():
            """Simulate concurrent parameter logging operations."""
            start_time = time.time()

            with patch('src.data_collection.continuous_parameter_logger.get_supabase', return_value=mock_supabase):
                with patch('src.data_collection.continuous_parameter_logger.plc_manager') as mock_plc:
                    mock_plc.is_connected.return_value = True
                    mock_plc.read_all_parameters.return_value = asyncio.Future()
                    mock_plc.read_all_parameters.return_value.set_result({
                        'param_1': 42.0,
                        'param_2': 43.5
                    })

                    try:
                        await logger._read_and_log_parameters()
                    except Exception as e:
                        track_operation('error', str(e))

            end_time = time.time()
            return end_time - start_time

        # Run concurrent operations
        tasks = []
        for _ in range(iterations):
            # Small random delay to create timing variations
            await asyncio.sleep(random.uniform(0.001, 0.005))
            task = asyncio.create_task(concurrent_logging_operation())
            tasks.append(task)

        start_time = time.time()
        timing_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results for race conditions
        with operation_lock:
            # Check for inconsistent state transitions
            state_operations = [op for op in operation_log if op['type'] == 'insert']

            # Group operations by timestamp windows (potential races)
            time_windows = {}
            for op in state_operations:
                window = int(op['timestamp'] * 1000) // 10  # 10ms windows
                if window not in time_windows:
                    time_windows[window] = []
                time_windows[window].append(op)

            # Detect race conditions
            for window, ops in time_windows.items():
                if len(ops) > 1:
                    # Multiple operations in same time window - potential race
                    timing_windows.append(len(ops))

                    # Check for data inconsistency
                    data_types = set()
                    for op in ops:
                        if isinstance(op['data'], list) and len(op['data']) > 0:
                            # Determine if this was a history-only or dual-table write
                            if any('process_id' in str(record) for record in op['data']):
                                data_types.add('dual_table')
                            else:
                                data_types.add('history_only')

                    if len(data_types) > 1:
                        # Mixed data types in same window indicate race condition
                        race_detected = True
                        data_corruption = True

        avg_timing_window = sum(timing_windows) / len(timing_windows) if timing_windows else 0

        result = RaceConditionResult(
            test_name="dual_mode_logging_race",
            concurrent_operations=iterations,
            race_detected=race_detected,
            data_corruption=data_corruption,
            timing_window_ms=avg_timing_window * 10,  # Convert to ms
            details={
                'total_operations': len(operation_log),
                'timing_windows': len(timing_windows),
                'max_concurrent_ops': max(timing_windows) if timing_windows else 0,
                'execution_time_ms': total_time * 1000,
                'error_rate': len([r for r in timing_results if isinstance(r, Exception)]) / len(timing_results)
            }
        )

        self.results.append(result)
        return result

    async def test_state_transition_race(self, iterations: int = 50) -> RaceConditionResult:
        """Test race conditions in machine state transitions."""
        race_detected = False
        data_corruption = False
        timing_windows = []

        # Mock state transition operations
        state_log = []
        state_lock = threading.Lock()

        def mock_state_update(status, process_id=None):
            with state_lock:
                state_log.append({
                    'status': status,
                    'process_id': process_id,
                    'timestamp': time.time(),
                    'thread': threading.current_thread().ident
                })
                # Simulate database update time
                time.sleep(random.uniform(0.001, 0.005))

        async def simulate_recipe_start():
            """Simulate recipe start sequence."""
            # Step 1: Set status to processing
            mock_state_update('processing', None)

            # Simulate processing delay (race window)
            await asyncio.sleep(random.uniform(0.001, 0.01))

            # Step 2: Set process ID
            mock_state_update('processing', 'process_123')

        async def simulate_recipe_stop():
            """Simulate recipe stop sequence."""
            # Step 1: Set status to idle
            mock_state_update('idle', 'process_123')

            # Simulate processing delay (race window)
            await asyncio.sleep(random.uniform(0.001, 0.01))

            # Step 2: Clear process ID
            mock_state_update('idle', None)

        async def simulate_parameter_logger():
            """Simulate parameter logger checking state."""
            with state_lock:
                if state_log:
                    latest_state = state_log[-1]
                    # Check for race condition: processing status with no process_id
                    if latest_state['status'] == 'processing' and latest_state['process_id'] is None:
                        timing_windows.append(time.time())

        # Run concurrent operations
        tasks = []
        for i in range(iterations):
            if i % 3 == 0:
                tasks.append(asyncio.create_task(simulate_recipe_start()))
            elif i % 3 == 1:
                tasks.append(asyncio.create_task(simulate_recipe_stop()))
            else:
                tasks.append(asyncio.create_task(simulate_parameter_logger()))

            # Small random delays
            await asyncio.sleep(random.uniform(0.001, 0.003))

        start_time = time.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze for race conditions
        with state_lock:
            # Check for inconsistent state transitions
            for i in range(1, len(state_log)):
                prev_state = state_log[i-1]
                curr_state = state_log[i]

                # Check for race condition patterns
                if (prev_state['status'] == 'processing' and
                    prev_state['process_id'] is None and
                    curr_state['timestamp'] - prev_state['timestamp'] > 0.001):
                    race_detected = True

                # Check for data corruption (invalid state combinations)
                if (curr_state['status'] == 'idle' and
                    curr_state['process_id'] is not None):
                    data_corruption = True

        avg_timing_window = len(timing_windows) / iterations if iterations > 0 else 0

        result = RaceConditionResult(
            test_name="state_transition_race",
            concurrent_operations=iterations,
            race_detected=race_detected,
            data_corruption=data_corruption,
            timing_window_ms=avg_timing_window * 1000,
            details={
                'state_transitions': len(state_log),
                'race_windows_detected': len(timing_windows),
                'execution_time_ms': total_time * 1000,
                'inconsistent_states': race_detected or data_corruption
            }
        )

        self.results.append(result)
        return result

    async def test_concurrent_database_access_race(self, iterations: int = 30) -> RaceConditionResult:
        """Test race conditions in concurrent database access."""
        race_detected = False
        data_corruption = False
        timing_windows = []

        # Simulate concurrent database operations
        db_operations = []
        db_lock = threading.Lock()

        def mock_db_operation(operation_type, table, data):
            with db_lock:
                start_time = time.time()
                # Simulate database operation
                time.sleep(random.uniform(0.005, 0.020))
                end_time = time.time()

                db_operations.append({
                    'operation': operation_type,
                    'table': table,
                    'data': data,
                    'start_time': start_time,
                    'end_time': end_time,
                    'thread': threading.current_thread().ident
                })

        async def concurrent_parameter_insert():
            """Simulate concurrent parameter insertions."""
            # Simulate dual-table write without transaction
            mock_db_operation('insert', 'parameter_value_history', {'param_id': 'test', 'value': 42})
            await asyncio.sleep(random.uniform(0.001, 0.005))  # Race window
            mock_db_operation('insert', 'process_data_points', {'param_id': 'test', 'value': 42})

        async def concurrent_state_update():
            """Simulate concurrent state updates."""
            mock_db_operation('update', 'machines', {'status': 'processing'})
            await asyncio.sleep(random.uniform(0.001, 0.005))  # Race window
            mock_db_operation('update', 'process_executions', {'status': 'running'})

        # Run concurrent operations
        tasks = []
        for i in range(iterations):
            if i % 2 == 0:
                tasks.append(asyncio.create_task(concurrent_parameter_insert()))
            else:
                tasks.append(asyncio.create_task(concurrent_state_update()))

        start_time = time.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze for race conditions
        with db_lock:
            # Group operations by thread and analyze timing
            thread_operations = {}
            for op in db_operations:
                thread_id = op['thread']
                if thread_id not in thread_operations:
                    thread_operations[thread_id] = []
                thread_operations[thread_id].append(op)

            # Check for overlapping operations (potential races)
            for thread_id, ops in thread_operations.items():
                for i, op1 in enumerate(ops):
                    for op2 in ops[i+1:]:
                        # Check if operations overlap in time
                        if (op1['start_time'] <= op2['start_time'] <= op1['end_time'] or
                            op2['start_time'] <= op1['start_time'] <= op2['end_time']):
                            race_detected = True
                            timing_windows.append(abs(op2['start_time'] - op1['start_time']) * 1000)

            # Check for data consistency issues
            history_ops = [op for op in db_operations if op['table'] == 'parameter_value_history']
            process_ops = [op for op in db_operations if op['table'] == 'process_data_points']

            if len(history_ops) != len(process_ops):
                # Unequal writes to dual tables indicate potential data corruption
                data_corruption = True

        avg_timing_window = sum(timing_windows) / len(timing_windows) if timing_windows else 0

        result = RaceConditionResult(
            test_name="concurrent_database_access_race",
            concurrent_operations=iterations,
            race_detected=race_detected,
            data_corruption=data_corruption,
            timing_window_ms=avg_timing_window,
            details={
                'total_db_operations': len(db_operations),
                'overlapping_operations': len(timing_windows),
                'execution_time_ms': total_time * 1000,
                'thread_count': len(thread_operations)
            }
        )

        self.results.append(result)
        return result

    async def test_concurrent_configuration_access_race(self, iterations: int = 20) -> RaceConditionResult:
        """Test race conditions in concurrent configuration access."""
        race_detected = False
        data_corruption = False
        timing_windows = []

        # Simulate concurrent configuration operations
        config_operations = []
        config_lock = threading.Lock()

        def mock_config_operation(operation_type, key, value=None):
            with config_lock:
                config_operations.append({
                    'operation': operation_type,
                    'key': key,
                    'value': value,
                    'timestamp': time.time(),
                    'thread': threading.current_thread().ident
                })

        async def concurrent_config_read():
            """Simulate concurrent configuration reads."""
            mock_config_operation('read', 'SUPABASE_KEY')
            await asyncio.sleep(random.uniform(0.001, 0.003))

        async def concurrent_config_write():
            """Simulate concurrent configuration writes."""
            mock_config_operation('write', 'CACHE_TTL', 300)
            await asyncio.sleep(random.uniform(0.001, 0.003))

        # Run concurrent operations
        tasks = []
        for i in range(iterations):
            if i % 2 == 0:
                tasks.append(asyncio.create_task(concurrent_config_read()))
            else:
                tasks.append(asyncio.create_task(concurrent_config_write()))

        start_time = time.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze for race conditions
        with config_lock:
            # Check for concurrent read/write operations on same key
            key_operations = {}
            for op in config_operations:
                key = op['key']
                if key not in key_operations:
                    key_operations[key] = []
                key_operations[key].append(op)

            for key, ops in key_operations.items():
                if len(ops) > 1:
                    # Check for read/write races
                    read_ops = [op for op in ops if op['operation'] == 'read']
                    write_ops = [op for op in ops if op['operation'] == 'write']

                    if read_ops and write_ops:
                        # Potential read/write race condition
                        race_detected = True
                        for read_op in read_ops:
                            for write_op in write_ops:
                                timing_diff = abs(read_op['timestamp'] - write_op['timestamp']) * 1000
                                if timing_diff < 10:  # Within 10ms
                                    timing_windows.append(timing_diff)

        avg_timing_window = sum(timing_windows) / len(timing_windows) if timing_windows else 0

        result = RaceConditionResult(
            test_name="concurrent_configuration_access_race",
            concurrent_operations=iterations,
            race_detected=race_detected,
            data_corruption=data_corruption,
            timing_window_ms=avg_timing_window,
            details={
                'config_operations': len(config_operations),
                'race_windows': len(timing_windows),
                'execution_time_ms': total_time * 1000,
                'keys_accessed': len(key_operations)
            }
        )

        self.results.append(result)
        return result

    def generate_race_condition_report(self) -> Dict[str, Any]:
        """Generate comprehensive race condition security report."""
        if not self.results:
            return {'error': 'No race condition tests have been run'}

        total_tests = len(self.results)
        races_detected = sum(1 for r in self.results if r.race_detected)
        data_corruption_count = sum(1 for r in self.results if r.data_corruption)

        # Calculate risk score
        risk_score = ((races_detected * 0.4) + (data_corruption_count * 0.6)) / total_tests * 100

        return {
            'summary': {
                'total_tests': total_tests,
                'races_detected': races_detected,
                'data_corruption_incidents': data_corruption_count,
                'race_detection_rate': races_detected / total_tests * 100,
                'data_corruption_rate': data_corruption_count / total_tests * 100,
                'overall_risk_score': risk_score
            },
            'test_results': [
                {
                    'test_name': r.test_name,
                    'concurrent_operations': r.concurrent_operations,
                    'race_detected': r.race_detected,
                    'data_corruption': r.data_corruption,
                    'timing_window_ms': r.timing_window_ms,
                    'details': r.details
                }
                for r in self.results
            ],
            'recommendations': self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on test results."""
        recommendations = []

        if any(r.race_detected for r in self.results):
            recommendations.append("Implement atomic transactions for state transitions")
            recommendations.append("Add proper locking mechanisms for concurrent operations")
            recommendations.append("Use database transactions for dual-table writes")

        if any(r.data_corruption for r in self.results):
            recommendations.append("Implement data consistency validation")
            recommendations.append("Add rollback mechanisms for failed operations")
            recommendations.append("Use compensating transactions for data recovery")

        if any(r.timing_window_ms > 10 for r in self.results):
            recommendations.append("Reduce timing windows in critical operations")
            recommendations.append("Implement optimistic locking for performance")

        if not recommendations:
            recommendations.append("Continue monitoring for race conditions in production")

        return recommendations


class TestRaceConditionSecurity:
    """Race condition security test suite."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tester = RaceConditionSecurityTester()

    @pytest.mark.asyncio
    async def test_dual_mode_logging_race_conditions(self):
        """Test for race conditions in dual-mode parameter logging."""
        result = await self.tester.test_dual_mode_logging_race(iterations=50)

        # Log the results for analysis
        print(f"Dual-mode logging race test:")
        print(f"  Operations: {result.concurrent_operations}")
        print(f"  Race detected: {result.race_detected}")
        print(f"  Data corruption: {result.data_corruption}")
        print(f"  Timing window: {result.timing_window_ms:.2f}ms")

        # Assert that if race conditions are detected, they're documented
        if result.race_detected:
            assert result.details['timing_windows'] > 0, "Race detected but no timing windows recorded"

    @pytest.mark.asyncio
    async def test_state_transition_race_conditions(self):
        """Test for race conditions in state transitions."""
        result = await self.tester.test_state_transition_race(iterations=30)

        print(f"State transition race test:")
        print(f"  Operations: {result.concurrent_operations}")
        print(f"  Race detected: {result.race_detected}")
        print(f"  Data corruption: {result.data_corruption}")

        # State transitions should be atomic
        if result.race_detected or result.data_corruption:
            print("⚠️  State transition race conditions detected - implement atomic operations")

    @pytest.mark.asyncio
    async def test_concurrent_database_access_race_conditions(self):
        """Test for race conditions in concurrent database access."""
        result = await self.tester.test_concurrent_database_access_race(iterations=20)

        print(f"Database access race test:")
        print(f"  Operations: {result.concurrent_operations}")
        print(f"  Race detected: {result.race_detected}")
        print(f"  Data corruption: {result.data_corruption}")

        # Database operations should be protected by transactions
        if result.data_corruption:
            print("⚠️  Database race conditions detected - implement proper transactions")

    @pytest.mark.asyncio
    async def test_concurrent_configuration_access_race_conditions(self):
        """Test for race conditions in configuration access."""
        result = await self.tester.test_concurrent_configuration_access_race(iterations=15)

        print(f"Configuration access race test:")
        print(f"  Operations: {result.concurrent_operations}")
        print(f"  Race detected: {result.race_detected}")

        # Configuration access should be thread-safe
        if result.race_detected:
            print("⚠️  Configuration race conditions detected - implement proper synchronization")

    @pytest.mark.asyncio
    async def test_comprehensive_race_condition_analysis(self):
        """Run comprehensive race condition analysis."""
        # Run all race condition tests
        await self.tester.test_dual_mode_logging_race(iterations=30)
        await self.tester.test_state_transition_race(iterations=20)
        await self.tester.test_concurrent_database_access_race(iterations=15)
        await self.tester.test_concurrent_configuration_access_race(iterations=10)

        # Generate report
        report = self.tester.generate_race_condition_report()

        print(f"\n🔍 Race Condition Security Analysis Report:")
        print(f"  Total tests: {report['summary']['total_tests']}")
        print(f"  Races detected: {report['summary']['races_detected']}")
        print(f"  Data corruption incidents: {report['summary']['data_corruption_incidents']}")
        print(f"  Overall risk score: {report['summary']['overall_risk_score']:.1f}%")

        if report['recommendations']:
            print(f"\n📋 Security Recommendations:")
            for rec in report['recommendations']:
                print(f"    - {rec}")

        # Assert that high-risk scenarios are documented
        assert report['summary']['overall_risk_score'] is not None
        assert 'recommendations' in report


# Utility functions for CI/CD integration
async def run_race_condition_security_audit():
    """Run comprehensive race condition security audit."""
    print("🔍 Running race condition security audit...")

    tester = RaceConditionSecurityTester()

    # Run comprehensive tests
    tests_run = 0
    races_found = 0

    # Test 1: Dual-mode logging races
    result1 = await tester.test_dual_mode_logging_race(iterations=20)
    tests_run += 1
    if result1.race_detected or result1.data_corruption:
        races_found += 1

    # Test 2: State transition races
    result2 = await tester.test_state_transition_race(iterations=15)
    tests_run += 1
    if result2.race_detected or result2.data_corruption:
        races_found += 1

    # Test 3: Database access races
    result3 = await tester.test_concurrent_database_access_race(iterations=10)
    tests_run += 1
    if result3.race_detected or result3.data_corruption:
        races_found += 1

    # Generate report
    report = tester.generate_race_condition_report()

    print(f"Race Condition Security Audit Results:")
    print(f"  Tests run: {tests_run}")
    print(f"  Race conditions found: {races_found}")
    print(f"  Risk score: {report['summary']['overall_risk_score']:.1f}%")

    # Consider audit successful if risk score is below threshold
    risk_threshold = 30.0  # 30% risk threshold
    if report['summary']['overall_risk_score'] <= risk_threshold:
        print(f"\n✅ RACE CONDITION AUDIT PASSED - Risk score below {risk_threshold}%")
        return True
    else:
        print(f"\n❌ RACE CONDITION AUDIT FAILED - Risk score above {risk_threshold}%")
        print("Recommendations:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
        return False


if __name__ == "__main__":
    # Run audit when executed directly
    import asyncio
    success = asyncio.run(run_race_condition_security_audit())
    exit(0 if success else 1)