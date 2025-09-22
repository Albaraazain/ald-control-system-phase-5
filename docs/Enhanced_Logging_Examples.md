# Enhanced Logging System - Code Examples

## Overview

This document provides practical code examples for using the enhanced service-specific logging system in the ALD Control System.

## Basic Usage Examples

### Command Flow Service

```python
# src/command_flow/new_module.py
from src.log_setup import get_command_flow_logger

logger = get_command_flow_logger()

async def process_command(command_id: str, command_type: str, payload: dict):
    """Process a command with proper logging."""
    logger.info(f"🔔 Processing {command_type} command: {command_id}")

    try:
        # Validate command
        if not payload:
            logger.warning(f"⚠️ Empty payload for command {command_id}")
            return False

        # Process command
        logger.debug(f"Command payload: {payload}")

        # Success
        logger.info(f"✅ Command {command_id} processed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Command {command_id} failed: {e}", exc_info=True)
        return False
```

### PLC Communication

```python
# src/plc/new_hardware_module.py
from src.log_setup import get_plc_logger

logger = get_plc_logger()

class AdvancedPLCOperations:
    def __init__(self):
        self.connection_attempts = 0

    async def read_parameter_with_retry(self, register: int, max_retries: int = 3) -> float:
        """Read parameter with retry logic and detailed logging."""

        for attempt in range(max_retries):
            try:
                logger.debug(f"Reading register {register}, attempt {attempt + 1}/{max_retries}")

                # Simulate read operation
                value = await self._read_register(register)

                logger.info(f"✅ Successfully read register {register}: {value}")
                return value

            except Exception as e:
                logger.warning(f"⚠️ Read attempt {attempt + 1} failed for register {register}: {e}")

                if attempt == max_retries - 1:
                    logger.error(f"❌ All {max_retries} read attempts failed for register {register}", exc_info=True)
                    raise

                await asyncio.sleep(1.0)  # Wait before retry
```

### Recipe Flow Service

```python
# src/recipe_flow/advanced_executor.py
from src.log_setup import get_recipe_flow_logger

logger = get_recipe_flow_logger()

class RecipeExecutor:
    def __init__(self):
        self.current_recipe_id = None

    async def execute_recipe(self, recipe_id: str, steps: list):
        """Execute recipe with comprehensive logging."""
        self.current_recipe_id = recipe_id

        logger.info(f"🚀 Starting recipe execution: {recipe_id} ({len(steps)} steps)")

        try:
            for step_index, step in enumerate(steps):
                step_name = step.get('name', f'Step_{step_index}')

                logger.info(f"📋 Executing step {step_index + 1}/{len(steps)}: {step_name}")

                start_time = time.time()
                await self._execute_step(step)
                execution_time = time.time() - start_time

                logger.info(f"✅ Step {step_name} completed in {execution_time:.2f}s")

            logger.info(f"🎉 Recipe {recipe_id} completed successfully")

        except Exception as e:
            logger.error(f"❌ Recipe {recipe_id} failed at step {step_index + 1}: {e}", exc_info=True)
            raise
```

### Data Collection Service

```python
# src/data_collection/enhanced_logger.py
from src.log_setup import get_data_collection_logger

logger = get_data_collection_logger()

class ParameterDataCollector:
    def __init__(self):
        self.collection_stats = {
            'total_records': 0,
            'failed_records': 0,
            'last_collection_time': None
        }

    async def collect_parameters(self, parameter_ids: list):
        """Collect parameters with performance monitoring."""

        start_time = time.time()
        collected_count = 0
        failed_count = 0

        logger.debug(f"Starting parameter collection for {len(parameter_ids)} parameters")

        for param_id in parameter_ids:
            try:
                value = await self._read_parameter(param_id)
                await self._store_parameter_value(param_id, value)

                collected_count += 1
                logger.debug(f"Collected parameter {param_id}: {value}")

            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to collect parameter {param_id}: {e}")

        collection_time = time.time() - start_time

        # Update stats
        self.collection_stats['total_records'] += collected_count
        self.collection_stats['failed_records'] += failed_count
        self.collection_stats['last_collection_time'] = time.time()

        # Log summary
        logger.info(
            f"📊 Parameter collection complete: "
            f"{collected_count} success, {failed_count} failed, "
            f"{collection_time:.2f}s duration"
        )

        if failed_count > 0:
            failure_rate = (failed_count / len(parameter_ids)) * 100
            if failure_rate > 10:
                logger.warning(f"⚠️ High failure rate: {failure_rate:.1f}%")
```

## Advanced Patterns

### Context Manager for Operation Logging

```python
from contextlib import asynccontextmanager
from src.log_setup import get_service_logger

@asynccontextmanager
async def log_operation(service_name: str, operation_name: str, **context):
    """Context manager for logging operations with timing."""
    logger = get_service_logger(service_name)

    start_time = time.time()
    context_str = ", ".join(f"{k}={v}" for k, v in context.items())

    logger.info(f"🔄 Starting {operation_name}" + (f" ({context_str})" if context_str else ""))

    try:
        yield logger
        duration = time.time() - start_time
        logger.info(f"✅ {operation_name} completed in {duration:.2f}s")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ {operation_name} failed after {duration:.2f}s: {e}", exc_info=True)
        raise

# Usage example
async def complex_recipe_operation(recipe_id: str):
    async with log_operation('recipe_flow', 'recipe_validation', recipe_id=recipe_id) as logger:
        # Validation logic here
        logger.debug("Validating recipe structure...")
        # ... validation code ...

    async with log_operation('recipe_flow', 'recipe_execution', recipe_id=recipe_id) as logger:
        # Execution logic here
        logger.debug("Executing recipe steps...")
        # ... execution code ...
```

### Performance Monitoring with Logging

```python
from src.log_setup import get_performance_logger
import psutil
import asyncio

logger = get_performance_logger()

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}

    async def monitor_system_resources(self):
        """Monitor and log system resource usage."""
        while True:
            try:
                # Collect metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Log performance metrics
                if cpu_percent > 80:
                    logger.warning(f"⚠️ High CPU usage: {cpu_percent:.1f}%")

                if memory.percent > 85:
                    logger.warning(f"⚠️ High memory usage: {memory.percent:.1f}%")

                if disk.percent > 90:
                    logger.warning(f"⚠️ High disk usage: {disk.percent:.1f}%")

                # Regular status log
                logger.debug(f"System status: CPU={cpu_percent:.1f}%, MEM={memory.percent:.1f}%, DISK={disk.percent:.1f}%")

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Performance monitoring error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on error
```

### Error Recovery with Logging

```python
from src.log_setup import get_service_logger
import asyncio

class ResilientService:
    def __init__(self, service_name: str):
        self.logger = get_service_logger(service_name)
        self.retry_count = 0
        self.max_retries = 3

    async def resilient_operation(self, operation_func, *args, **kwargs):
        """Execute operation with automatic retry and logging."""

        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Attempting operation, try {attempt + 1}/{self.max_retries}")

                result = await operation_func(*args, **kwargs)

                if attempt > 0:
                    self.logger.info(f"✅ Operation succeeded on attempt {attempt + 1}")

                return result

            except Exception as e:
                self.logger.warning(f"⚠️ Operation failed on attempt {attempt + 1}: {e}")

                if attempt == self.max_retries - 1:
                    self.logger.error(f"❌ Operation failed after {self.max_retries} attempts", exc_info=True)
                    raise

                # Exponential backoff
                wait_time = 2 ** attempt
                self.logger.debug(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
```

### Structured Logging for Complex Operations

```python
from src.log_setup import get_service_logger
import json

def log_structured_event(service_name: str, event_type: str, **event_data):
    """Log structured events for better analysis."""
    logger = get_service_logger(service_name)

    event = {
        'event_type': event_type,
        'timestamp': time.time(),
        **event_data
    }

    # Log as both human-readable and structured
    human_readable = f"{event_type}: " + ", ".join(f"{k}={v}" for k, v in event_data.items())
    structured = json.dumps(event, default=str)

    logger.info(f"📋 {human_readable}")
    logger.debug(f"Structured: {structured}")

# Usage examples
async def recipe_step_execution():
    # Log recipe step start
    log_structured_event(
        'recipe_flow',
        'step_started',
        step_name='valve_open',
        step_index=1,
        recipe_id='recipe_123',
        expected_duration=5.0
    )

    # ... step execution ...

    # Log recipe step completion
    log_structured_event(
        'recipe_flow',
        'step_completed',
        step_name='valve_open',
        step_index=1,
        recipe_id='recipe_123',
        actual_duration=4.8,
        status='success'
    )
```

## Migration Examples

### Converting Legacy Code

**Before (Legacy):**
```python
from src.log_setup import logger

def process_valve_operation(valve_id: int, action: str):
    logger.info(f"Processing valve {valve_id} action: {action}")
    # ... operation code ...
    logger.info(f"Valve {valve_id} operation completed")
```

**After (Service-Specific):**
```python
from src.log_setup import get_step_flow_logger

logger = get_step_flow_logger()

def process_valve_operation(valve_id: int, action: str):
    logger.info(f"🔧 Processing valve {valve_id} action: {action}")
    # ... operation code ...
    logger.info(f"✅ Valve {valve_id} operation completed")
```

### Gradual Migration Strategy

```python
# src/utils/logging_migration.py
from src.log_setup import logger as legacy_logger, get_service_logger

def get_logger_for_module(module_name: str, use_service_specific: bool = True):
    """Helper function for gradual migration to service-specific logging."""

    if not use_service_specific:
        return legacy_logger

    # Map module names to services
    service_mapping = {
        'command': 'command_flow',
        'recipe': 'recipe_flow',
        'step': 'step_flow',
        'plc': 'plc',
        'data': 'data_collection',
        'monitor': 'connection_monitor',
    }

    # Determine service from module name
    for key, service in service_mapping.items():
        if key in module_name.lower():
            return get_service_logger(service)

    # Default to legacy logger if no mapping found
    return legacy_logger

# Usage in existing modules
logger = get_logger_for_module(__name__)
```

## Testing with Service Loggers

```python
# tests/test_logging.py
import unittest
from unittest.mock import patch, MagicMock
from src.log_setup import get_service_logger

class TestServiceLogging(unittest.TestCase):

    def test_service_logger_creation(self):
        """Test that service loggers are created correctly."""
        logger = get_service_logger('command_flow')
        self.assertEqual(logger.name, 'machine_control.command_flow')

    @patch('src.log_setup.logging.handlers.RotatingFileHandler')
    def test_log_file_creation(self, mock_handler):
        """Test that log files are created with correct configuration."""
        logger = get_service_logger('test_service')

        # Verify file handler was created
        mock_handler.assert_called()

        # Check handler configuration
        call_args = mock_handler.call_args
        self.assertTrue(str(call_args[0][0]).endswith('test_service.log'))

    def test_service_specific_logging(self):
        """Test that different services log to different files."""

        with patch('builtins.open', create=True) as mock_open:
            command_logger = get_service_logger('command_flow')
            plc_logger = get_service_logger('plc')

            command_logger.info("Command test message")
            plc_logger.info("PLC test message")

            # Verify different loggers were used
            self.assertNotEqual(command_logger, plc_logger)
```

## Best Practices Summary

1. **Use appropriate service loggers** for your module's domain
2. **Include emojis for visual scanning** (✅, ⚠️, ❌, 🔧, 📊, etc.)
3. **Provide context in messages** (IDs, timestamps, relevant parameters)
4. **Use structured logging** for complex events that need analysis
5. **Implement retry logic with logging** for resilient operations
6. **Monitor performance metrics** and log warnings for thresholds
7. **Use context managers** for timing operations
8. **Test logging behavior** in unit tests
9. **Migrate gradually** from legacy logging to service-specific logging
10. **Never log sensitive information** (passwords, API keys, personal data)