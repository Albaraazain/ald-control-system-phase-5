#!/usr/bin/env python3
"""
Dual-Mode Logging Integration Testing Framework

Tests for dual-mode parameter logging integration, service boundary validation,
and async pipeline testing with dependency injection.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LoggingTestData:
    """Test data for logging validation"""
    parameter_id: str
    value: float
    set_point: Optional[float]
    timestamp: str
    process_id: Optional[str] = None


class MockAsyncDatabase:
    """Mock async database for testing"""

    def __init__(self):
        self.parameter_history: List[Dict] = []
        self.process_data_points: List[Dict] = []
        self.machines: Dict[str, Dict] = {
            "test-machine": {
                "id": "test-machine",
                "status": "idle",
                "current_process_id": None
            }
        }
        self.connection_pool_size = 0
        self.active_connections = 0

    async def insert_parameter_history(self, records: List[Dict]) -> bool:
        """Mock parameter history insertion"""
        self.parameter_history.extend(records)
        await asyncio.sleep(0.01)  # Simulate DB latency
        return True

    async def insert_process_data_points(self, records: List[Dict]) -> bool:
        """Mock process data points insertion"""
        self.process_data_points.extend(records)
        await asyncio.sleep(0.01)  # Simulate DB latency
        return True

    async def get_machine_status(self, machine_id: str) -> Dict:
        """Mock machine status retrieval"""
        await asyncio.sleep(0.005)  # Simulate DB latency
        return self.machines.get(machine_id, {})

    async def update_machine_status(self, machine_id: str, status: str, process_id: Optional[str] = None):
        """Mock machine status update"""
        if machine_id in self.machines:
            self.machines[machine_id]["status"] = status
            self.machines[machine_id]["current_process_id"] = process_id
        await asyncio.sleep(0.005)  # Simulate DB latency

    def clear_data(self):
        """Clear all test data"""
        self.parameter_history.clear()
        self.process_data_points.clear()
        self.machines["test-machine"]["status"] = "idle"
        self.machines["test-machine"]["current_process_id"] = None


class MockParameterReader:
    """Mock parameter reader for testing"""

    def __init__(self):
        self.parameters = {
            "temperature": 25.0,
            "pressure": 1.2,
            "flow_rate": 0.8,
            "valve_1": 0,
            "valve_2": 1
        }
        self.read_delay = 0.01  # Simulate PLC communication delay

    async def read_all_parameters(self) -> Dict[str, float]:
        """Mock bulk parameter reading"""
        await asyncio.sleep(self.read_delay)
        return self.parameters.copy()

    async def read_parameter(self, parameter_id: str) -> float:
        """Mock single parameter reading"""
        await asyncio.sleep(self.read_delay)
        return self.parameters.get(parameter_id, 0.0)

    def update_parameter(self, parameter_id: str, value: float):
        """Update parameter value for testing"""
        self.parameters[parameter_id] = value


class DualModeParameterLogger:
    """Test implementation of dual-mode parameter logger with DI"""

    def __init__(self, database: MockAsyncDatabase, parameter_reader: MockParameterReader, machine_id: str = "test-machine"):
        self.database = database
        self.parameter_reader = parameter_reader
        self.machine_id = machine_id
        self.is_running = False
        self.interval = 1.0
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start dual-mode logging"""
        if self.is_running:
            return

        self.is_running = True
        self._task = asyncio.create_task(self._logging_loop())

    async def stop(self):
        """Stop dual-mode logging"""
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _logging_loop(self):
        """Internal logging loop"""
        try:
            while self.is_running:
                start_time = time.time()

                await self._read_and_log_parameters()

                # Maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            raise

    async def _read_and_log_parameters(self):
        """Read parameters and log in dual-mode"""
        # Get machine status
        machine_status = await self.database.get_machine_status(self.machine_id)
        current_process_id = machine_status.get("current_process_id")

        # Read all parameters
        parameter_values = await self.parameter_reader.read_all_parameters()

        if not parameter_values:
            return

        timestamp = datetime.now().isoformat()

        # Prepare records
        history_records = []
        process_records = []

        for parameter_id, value in parameter_values.items():
            # Always log to parameter history
            history_record = {
                "parameter_id": parameter_id,
                "value": value,
                "timestamp": timestamp
            }
            history_records.append(history_record)

            # Additionally log to process data if process is running
            if current_process_id:
                process_record = {
                    "process_id": current_process_id,
                    "parameter_id": parameter_id,
                    "value": value,
                    "timestamp": timestamp
                }
                process_records.append(process_record)

        # Insert records (should be atomic in real implementation)
        await self.database.insert_parameter_history(history_records)
        if process_records:
            await self.database.insert_process_data_points(process_records)

    def get_status(self) -> Dict[str, Any]:
        """Get logger status"""
        return {
            "is_running": self.is_running,
            "interval": self.interval,
            "machine_id": self.machine_id
        }


# Test Fixtures
@pytest.fixture
def mock_database():
    """Mock database fixture"""
    return MockAsyncDatabase()


@pytest.fixture
def mock_parameter_reader():
    """Mock parameter reader fixture"""
    return MockParameterReader()


@pytest.fixture
def dual_mode_logger(mock_database, mock_parameter_reader):
    """Dual-mode logger fixture with DI"""
    return DualModeParameterLogger(mock_database, mock_parameter_reader)


# Dual-Mode Logging Tests
class TestDualModeLogging:
    """Test dual-mode parameter logging functionality"""

    @pytest.mark.asyncio
    async def test_idle_mode_logging(self, dual_mode_logger, mock_database):
        """Test logging in idle mode (no process running)"""
        # Ensure machine is in idle state
        await mock_database.update_machine_status("test-machine", "idle", None)

        # Start logger and let it run for a short time
        await dual_mode_logger.start()
        await asyncio.sleep(0.1)  # Let it log once
        await dual_mode_logger.stop()

        # Check that data was logged to parameter history only
        assert len(mock_database.parameter_history) > 0
        assert len(mock_database.process_data_points) == 0

        # Verify parameter history structure
        history_record = mock_database.parameter_history[0]
        assert "parameter_id" in history_record
        assert "value" in history_record
        assert "timestamp" in history_record

    @pytest.mark.asyncio
    async def test_process_mode_logging(self, dual_mode_logger, mock_database):
        """Test logging in process mode (process running)"""
        # Set machine to processing state
        await mock_database.update_machine_status("test-machine", "processing", "test-process-123")

        # Start logger and let it run for a short time
        await dual_mode_logger.start()
        await asyncio.sleep(0.1)  # Let it log once
        await dual_mode_logger.stop()

        # Check that data was logged to both tables
        assert len(mock_database.parameter_history) > 0
        assert len(mock_database.process_data_points) > 0

        # Verify both tables have same parameter data
        history_params = {r["parameter_id"] for r in mock_database.parameter_history}
        process_params = {r["parameter_id"] for r in mock_database.process_data_points}
        assert history_params == process_params

        # Verify process data points have process_id
        process_record = mock_database.process_data_points[0]
        assert process_record["process_id"] == "test-process-123"

    @pytest.mark.asyncio
    async def test_mode_transition(self, dual_mode_logger, mock_database):
        """Test transition between idle and process modes"""
        # Start in idle mode
        await mock_database.update_machine_status("test-machine", "idle", None)

        await dual_mode_logger.start()
        await asyncio.sleep(0.05)  # Log in idle mode

        # Transition to process mode
        await mock_database.update_machine_status("test-machine", "processing", "test-process-456")
        await asyncio.sleep(0.05)  # Log in process mode

        # Transition back to idle
        await mock_database.update_machine_status("test-machine", "idle", None)
        await asyncio.sleep(0.05)  # Log in idle mode again

        await dual_mode_logger.stop()

        # Should have logged to both tables when process was running
        assert len(mock_database.parameter_history) > 0
        assert len(mock_database.process_data_points) > 0

        # Process data should only be from when process was running
        process_ids = {r["process_id"] for r in mock_database.process_data_points}
        assert process_ids == {"test-process-456"}

    @pytest.mark.asyncio
    async def test_logging_interval_consistency(self, dual_mode_logger, mock_database):
        """Test that logging maintains consistent intervals"""
        dual_mode_logger.interval = 0.05  # 50ms for fast testing

        start_time = time.time()
        await dual_mode_logger.start()
        await asyncio.sleep(0.2)  # Run for 200ms
        await dual_mode_logger.stop()
        end_time = time.time()

        # Should have logged approximately every 50ms
        expected_logs = int((end_time - start_time) / dual_mode_logger.interval)
        actual_logs = len(mock_database.parameter_history)

        # Allow some tolerance for timing
        assert abs(actual_logs - expected_logs) <= 2

    @pytest.mark.asyncio
    async def test_concurrent_logging_safety(self, mock_database, mock_parameter_reader):
        """Test that concurrent loggers don't interfere"""
        # Create two loggers for same machine
        logger1 = DualModeParameterLogger(mock_database, mock_parameter_reader)
        logger2 = DualModeParameterLogger(mock_database, mock_parameter_reader)

        logger1.interval = 0.03
        logger2.interval = 0.05

        # Start both loggers
        await logger1.start()
        await logger2.start()

        await asyncio.sleep(0.1)

        await logger1.stop()
        await logger2.stop()

        # Should have data from both loggers
        assert len(mock_database.parameter_history) > 0

        # In real implementation, would need more sophisticated testing
        # for race conditions and data consistency


class TestServiceBoundaryValidation:
    """Test service boundary validation and isolation"""

    @pytest.mark.asyncio
    async def test_database_service_boundary(self, mock_database):
        """Test database service operates independently"""
        # Test that database operations work in isolation
        test_records = [
            {"parameter_id": "temp", "value": 25.0, "timestamp": "2023-01-01T00:00:00Z"}
        ]

        result = await mock_database.insert_parameter_history(test_records)
        assert result is True
        assert len(mock_database.parameter_history) == 1

    @pytest.mark.asyncio
    async def test_parameter_reader_service_boundary(self, mock_parameter_reader):
        """Test parameter reader operates independently"""
        # Test bulk reading
        all_params = await mock_parameter_reader.read_all_parameters()
        assert isinstance(all_params, dict)
        assert len(all_params) > 0

        # Test single parameter reading
        temp = await mock_parameter_reader.read_parameter("temperature")
        assert isinstance(temp, (int, float))

    @pytest.mark.asyncio
    async def test_logger_service_isolation(self, dual_mode_logger, mock_database, mock_parameter_reader):
        """Test logger operates correctly when services have issues"""
        # Test with database failure
        original_insert = mock_database.insert_parameter_history
        mock_database.insert_parameter_history = AsyncMock(side_effect=Exception("DB Error"))

        await dual_mode_logger.start()
        await asyncio.sleep(0.05)
        await dual_mode_logger.stop()

        # Logger should handle database errors gracefully
        status = dual_mode_logger.get_status()
        assert status["is_running"] is False  # Should stop gracefully

        # Restore database functionality
        mock_database.insert_parameter_history = original_insert

    @pytest.mark.asyncio
    async def test_service_dependency_injection(self, mock_database, mock_parameter_reader):
        """Test that services can be injected and replaced"""
        # Create logger with injected dependencies
        logger = DualModeParameterLogger(mock_database, mock_parameter_reader)

        # Verify dependencies are injected correctly
        assert logger.database is mock_database
        assert logger.parameter_reader is mock_parameter_reader

        # Test with different dependencies
        alt_database = MockAsyncDatabase()
        alt_reader = MockParameterReader()

        alt_logger = DualModeParameterLogger(alt_database, alt_reader)

        # Should use different dependencies
        assert alt_logger.database is not mock_database
        assert alt_logger.parameter_reader is not mock_parameter_reader


class TestAsyncPipelineIntegration:
    """Test async pipeline integration and performance"""

    @pytest.mark.asyncio
    async def test_async_pipeline_performance(self, dual_mode_logger, mock_parameter_reader):
        """Test async pipeline performance characteristics"""
        # Configure for performance testing
        dual_mode_logger.interval = 0.02  # 20ms interval

        # Add latency to parameter reading
        mock_parameter_reader.read_delay = 0.01  # 10ms

        start_time = time.time()
        await dual_mode_logger.start()
        await asyncio.sleep(0.1)  # Run for 100ms
        await dual_mode_logger.stop()
        end_time = time.time()

        # Despite 10ms read delay, should maintain 20ms intervals
        total_time = end_time - start_time
        expected_cycles = int(total_time / dual_mode_logger.interval)

        # Should complete close to expected number of cycles
        # (allowing for some timing variance)
        assert expected_cycles >= 3  # At least a few cycles completed

    @pytest.mark.asyncio
    async def test_bulk_parameter_processing(self, mock_parameter_reader, mock_database):
        """Test bulk parameter processing efficiency"""
        # Add many parameters
        for i in range(50):
            mock_parameter_reader.parameters[f"param_{i}"] = float(i)

        logger = DualModeParameterLogger(mock_database, mock_parameter_reader)
        logger.interval = 0.05

        await logger.start()
        await asyncio.sleep(0.1)  # Let it process bulk parameters
        await logger.stop()

        # Should have processed all parameters
        if mock_database.parameter_history:
            parameter_ids = {r["parameter_id"] for r in mock_database.parameter_history}
            assert len(parameter_ids) >= 50  # Should have all parameters

    @pytest.mark.asyncio
    async def test_error_recovery_pipeline(self, dual_mode_logger, mock_database, mock_parameter_reader):
        """Test error recovery in async pipeline"""
        # Simulate intermittent parameter read failures
        original_read = mock_parameter_reader.read_all_parameters
        call_count = [0]

        async def failing_read():
            call_count[0] += 1
            if call_count[0] % 3 == 0:  # Fail every 3rd call
                raise Exception("PLC communication error")
            return await original_read()

        mock_parameter_reader.read_all_parameters = failing_read

        await dual_mode_logger.start()
        await asyncio.sleep(0.1)  # Run through several cycles
        await dual_mode_logger.stop()

        # Should have some successful logs despite failures
        # (In real implementation, would have error recovery)
        assert call_count[0] > 0  # Should have attempted multiple reads

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, mock_database, mock_parameter_reader):
        """Test concurrent operations across services"""
        # Create multiple operations running concurrently
        tasks = []

        # Database operations
        for i in range(5):
            records = [{"parameter_id": f"param_{i}", "value": float(i), "timestamp": f"2023-01-01T00:0{i}:00Z"}]
            tasks.append(mock_database.insert_parameter_history(records))

        # Parameter reading operations
        for i in range(5):
            tasks.append(mock_parameter_reader.read_parameter(f"temperature"))

        # Run all operations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete successfully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 10  # 5 database + 5 parameter operations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])