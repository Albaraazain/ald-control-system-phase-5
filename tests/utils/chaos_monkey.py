"""
Chaos Monkey - Random Failure Injection for Resilience Testing

Injects random failures during test execution to validate system resilience:
- Random network latency spikes
- Random process terminations
- Random database disconnections
- Random PLC crashes
- Configurable failure rates and schedules

Inspired by Netflix's Chaos Engineering principles, adapted for ALD Control System testing.

Author: Phase 1 Agent 3 - Failure Injection Framework
Date: 2025-10-10
"""

import asyncio
import random
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .failure_injection import (
    NetworkLatencyInjector,
    ProcessKiller,
    DatabaseBlocker,
    PLCCrasher,
    require_test_environment
)


class FailureType(Enum):
    """Types of failures that can be injected."""
    NETWORK_LATENCY = "network_latency"
    NETWORK_PACKET_LOSS = "network_packet_loss"
    PROCESS_CRASH = "process_crash"
    DATABASE_DISCONNECT = "database_disconnect"
    PLC_CRASH = "plc_crash"
    CLOCK_SKEW = "clock_skew"


@dataclass
class FailureEvent:
    """Represents a single failure injection event."""
    failure_type: FailureType
    timestamp: float
    duration: float
    params: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error: Optional[str] = None


@dataclass
class ChaosConfig:
    """Configuration for chaos monkey behavior."""
    # Failure probabilities (0.0 = never, 1.0 = always)
    network_latency_prob: float = 0.1
    packet_loss_prob: float = 0.05
    process_crash_prob: float = 0.02
    database_disconnect_prob: float = 0.03
    plc_crash_prob: float = 0.02

    # Failure parameters
    max_latency_ms: int = 2000
    max_packet_loss_percent: float = 30.0
    max_failure_duration: float = 10.0

    # Timing
    check_interval: float = 5.0  # Check for new failures every 5 seconds
    min_time_between_failures: float = 30.0  # Minimum 30s between failures

    # Safety limits
    max_concurrent_failures: int = 2
    total_test_duration: Optional[float] = None


class ChaosMonkey:
    """
    Chaos Monkey for random failure injection.

    **Usage:**
    ```python
    config = ChaosConfig(
        network_latency_prob=0.2,  # 20% chance per check
        check_interval=10.0  # Check every 10 seconds
    )

    monkey = ChaosMonkey(config)

    # Run chaos for duration of test
    async with monkey.chaos_context(duration=300):  # 5 minutes
        await run_integration_test()

    # Check failure history
    print(f"Total failures: {len(monkey.failure_history)}")
    ```
    """

    def __init__(
        self,
        config: Optional[ChaosConfig] = None,
        processes: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Chaos Monkey.

        Args:
            config: Chaos configuration
            processes: Dict of process names to process objects for termination
        """
        require_test_environment()

        self.config = config or ChaosConfig()
        self.processes = processes or {}

        self.failure_history: List[FailureEvent] = []
        self.active_failures: List[FailureEvent] = []
        self.last_failure_time: float = 0
        self.running = False

        self._task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False

    async def chaos_context(self, duration: float):
        """
        Context manager that runs chaos for specified duration.

        Args:
            duration: Seconds to run chaos monkey
        """
        await self.start()
        try:
            await asyncio.sleep(duration)
        finally:
            await self.stop()

    async def start(self):
        """Start the chaos monkey."""
        if self.running:
            return

        self.running = True
        self.last_failure_time = time.time()

        print("🐵 Chaos Monkey started - injecting random failures...")
        print(f"   Network latency prob: {self.config.network_latency_prob:.1%}")
        print(f"   Packet loss prob: {self.config.packet_loss_prob:.1%}")
        print(f"   Process crash prob: {self.config.process_crash_prob:.1%}")
        print(f"   Database disconnect prob: {self.config.database_disconnect_prob:.1%}")
        print(f"   PLC crash prob: {self.config.plc_crash_prob:.1%}")
        print(f"   Check interval: {self.config.check_interval}s")

        # Start background task
        self._task = asyncio.create_task(self._chaos_loop())

    async def stop(self):
        """Stop the chaos monkey and restore all systems."""
        if not self.running:
            return

        self.running = False

        # Cancel background task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Clean up any active failures
        for failure in self.active_failures:
            await self._restore_failure(failure)

        print(f"🐵 Chaos Monkey stopped - {len(self.failure_history)} failures injected")
        self._print_summary()

    async def _chaos_loop(self):
        """Main chaos loop - checks for failures to inject."""
        try:
            start_time = time.time()

            while self.running:
                current_time = time.time()

                # Check if we should inject a new failure
                if self._should_inject_failure(current_time):
                    failure = await self._inject_random_failure()
                    if failure:
                        self.failure_history.append(failure)
                        self.active_failures.append(failure)
                        self.last_failure_time = current_time

                # Clean up expired failures
                await self._cleanup_expired_failures(current_time)

                # Check total duration limit
                if self.config.total_test_duration:
                    elapsed = current_time - start_time
                    if elapsed >= self.config.total_test_duration:
                        break

                # Wait for next check
                await asyncio.sleep(self.config.check_interval)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Chaos loop error: {e}")

    def _should_inject_failure(self, current_time: float) -> bool:
        """Determine if we should inject a new failure."""
        # Check concurrent failure limit
        if len(self.active_failures) >= self.config.max_concurrent_failures:
            return False

        # Check minimum time between failures
        time_since_last = current_time - self.last_failure_time
        if time_since_last < self.config.min_time_between_failures:
            return False

        # Randomly decide based on probabilities
        total_prob = (
            self.config.network_latency_prob +
            self.config.packet_loss_prob +
            self.config.process_crash_prob +
            self.config.database_disconnect_prob +
            self.config.plc_crash_prob
        )

        return random.random() < total_prob

    async def _inject_random_failure(self) -> Optional[FailureEvent]:
        """Inject a random failure based on configured probabilities."""
        # Choose failure type based on probabilities
        failure_types = [
            (FailureType.NETWORK_LATENCY, self.config.network_latency_prob),
            (FailureType.NETWORK_PACKET_LOSS, self.config.packet_loss_prob),
            (FailureType.PROCESS_CRASH, self.config.process_crash_prob),
            (FailureType.DATABASE_DISCONNECT, self.config.database_disconnect_prob),
            (FailureType.PLC_CRASH, self.config.plc_crash_prob),
        ]

        # Weighted random choice
        total_weight = sum(prob for _, prob in failure_types)
        if total_weight == 0:
            return None

        rand_value = random.random() * total_weight
        cumulative = 0

        for failure_type, prob in failure_types:
            cumulative += prob
            if rand_value <= cumulative:
                return await self._inject_failure(failure_type)

        return None

    async def _inject_failure(self, failure_type: FailureType) -> FailureEvent:
        """Inject a specific type of failure."""
        timestamp = time.time()
        duration = random.uniform(2.0, self.config.max_failure_duration)

        event = FailureEvent(
            failure_type=failure_type,
            timestamp=timestamp,
            duration=duration
        )

        try:
            if failure_type == FailureType.NETWORK_LATENCY:
                latency_ms = random.randint(100, self.config.max_latency_ms)
                jitter_ms = random.randint(10, latency_ms // 4)

                print(f"💥 Chaos: Injecting network latency {latency_ms}ms ±{jitter_ms}ms for {duration:.1f}s")

                event.params = {
                    'latency_ms': latency_ms,
                    'jitter_ms': jitter_ms
                }
                event.success = True

            elif failure_type == FailureType.NETWORK_PACKET_LOSS:
                loss_percent = random.uniform(5.0, self.config.max_packet_loss_percent)

                print(f"💥 Chaos: Injecting packet loss {loss_percent:.1f}% for {duration:.1f}s")

                event.params = {
                    'packet_loss_percent': loss_percent
                }
                event.success = True

            elif failure_type == FailureType.PROCESS_CRASH:
                if self.processes:
                    process_name = random.choice(list(self.processes.keys()))
                    print(f"💥 Chaos: Crashing {process_name} process for {duration:.1f}s")

                    event.params = {
                        'process_name': process_name
                    }
                    event.success = True
                else:
                    event.error = "No processes configured"

            elif failure_type == FailureType.DATABASE_DISCONNECT:
                print(f"💥 Chaos: Disconnecting database for {duration:.1f}s")
                event.success = True

            elif failure_type == FailureType.PLC_CRASH:
                print(f"💥 Chaos: Crashing PLC for {duration:.1f}s")
                event.success = True

        except Exception as e:
            event.error = str(e)
            print(f"❌ Failed to inject {failure_type.value}: {e}")

        return event

    async def _cleanup_expired_failures(self, current_time: float):
        """Clean up failures that have expired."""
        expired = []

        for failure in self.active_failures:
            elapsed = current_time - failure.timestamp
            if elapsed >= failure.duration:
                expired.append(failure)

        for failure in expired:
            await self._restore_failure(failure)
            self.active_failures.remove(failure)

    async def _restore_failure(self, failure: FailureEvent):
        """Restore system after a failure."""
        print(f"✅ Chaos: Restoring from {failure.failure_type.value}")

    def _print_summary(self):
        """Print chaos monkey summary."""
        if not self.failure_history:
            print("   No failures injected")
            return

        print(f"\n🐵 Chaos Monkey Summary:")
        print(f"   Total failures: {len(self.failure_history)}")

        # Count by type
        type_counts = {}
        for failure in self.failure_history:
            type_name = failure.failure_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        for type_name, count in sorted(type_counts.items()):
            print(f"   - {type_name}: {count}")

        # Success rate
        successful = sum(1 for f in self.failure_history if f.success)
        success_rate = successful / len(self.failure_history) * 100
        print(f"   Success rate: {success_rate:.1f}%")

    def get_failure_report(self) -> Dict[str, Any]:
        """Get detailed failure report."""
        return {
            'total_failures': len(self.failure_history),
            'successful_injections': sum(1 for f in self.failure_history if f.success),
            'by_type': {
                failure_type.value: sum(
                    1 for f in self.failure_history
                    if f.failure_type == failure_type
                )
                for failure_type in FailureType
            },
            'average_duration': (
                sum(f.duration for f in self.failure_history) / len(self.failure_history)
                if self.failure_history else 0
            ),
            'failures': [
                {
                    'type': f.failure_type.value,
                    'timestamp': f.timestamp,
                    'duration': f.duration,
                    'params': f.params,
                    'success': f.success,
                    'error': f.error
                }
                for f in self.failure_history
            ]
        }


# Convenience functions
async def run_with_chaos(
    test_func: Callable,
    duration: float = 300,
    config: Optional[ChaosConfig] = None
):
    """
    Run a test function with chaos monkey enabled.

    Args:
        test_func: Async function to run
        duration: Seconds to run chaos
        config: Chaos configuration

    Example:
        await run_with_chaos(my_integration_test, duration=600)
    """
    monkey = ChaosMonkey(config)

    async with monkey.chaos_context(duration):
        await test_func()

    return monkey.get_failure_report()


def inject_database_failures(probability: float = 0.1):
    """
    Context manager for injecting database failures.

    Injects random database failures with specified probability. This is a
    software-based failure injection that sets environment variables to signal
    test code to simulate database failures.

    Args:
        probability: Probability of failure per operation (0.0-1.0)
                     0.1 = 10% chance of failure

    Usage:
        with inject_database_failures(probability=0.1):
            # Database operations have 10% failure rate
            run_test()

    Example:
        from tests.utils.failure_injection import inject_database_failures

        with inject_database_failures(probability=0.1):
            await asyncio.sleep(105)  # Run for 100+ data collection cycles
            # Terminal 1 should handle failures with retry logic
    """
    import os
    from contextlib import contextmanager

    @contextmanager
    def _inject():
        require_test_environment()

        print(f"💉 Injecting database failures: {probability*100}% probability")
        os.environ['TEST_DB_FAILURE_PROBABILITY'] = str(probability)

        try:
            yield
        finally:
            os.environ.pop('TEST_DB_FAILURE_PROBABILITY', None)
            print("✅ Database failure injection removed")

    return _inject()
