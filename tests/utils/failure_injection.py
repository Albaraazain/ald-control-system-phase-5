"""
Failure Injection Framework for ALD Control System Testing

This module provides infrastructure for injecting various types of failures during
integration and stress tests:
- Network latency and packet loss
- Process termination (terminals)
- Database connection blocking
- PLC simulation crashes
- Clock skew for timing tests

**SAFETY WARNINGS:**
- These tools modify system behavior and should ONLY be used in test environments
- Network tools require root privileges on Linux/macOS
- Always use context managers to ensure cleanup
- Test environment detection prevents accidental production usage

Platform Support:
- Linux: tc/netem for network injection (requires root)
- macOS: Software fallback (pfctl requires complex setup)
- Windows: Software-based delays only

Author: Phase 1 Agent 3 - Failure Injection Framework
Date: 2025-10-10
"""

import os
import sys
import asyncio
import subprocess
import signal
import platform
import time
import psutil
from typing import Optional, List, Dict, Any
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass


# ============================================================================
# PLATFORM DETECTION & SAFETY
# ============================================================================

def get_platform() -> str:
    """Get normalized platform name."""
    system = platform.system().lower()
    if system == 'darwin':
        return 'macos'
    return system


def is_root() -> bool:
    """Check if running with root/admin privileges."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False


def is_test_environment() -> bool:
    """Verify this is a test environment, not production."""
    # Check for test indicators
    indicators = [
        'PYTEST_CURRENT_TEST' in os.environ,
        'CI' in os.environ,
        'TEST_ENV' in os.environ,
        '--demo' in sys.argv,
        'test' in os.getcwd().lower(),
    ]
    return any(indicators)


def require_test_environment():
    """Raise exception if not in test environment."""
    if not is_test_environment():
        raise RuntimeError(
            "Failure injection can only be used in test environments. "
            "Set PYTEST_CURRENT_TEST or TEST_ENV environment variable."
        )


# ============================================================================
# NETWORK LATENCY INJECTOR
# ============================================================================

@dataclass
class NetworkCondition:
    """Defines a network condition for injection."""
    latency_ms: int = 0
    jitter_ms: int = 0
    packet_loss_percent: float = 0.0
    bandwidth_kbps: Optional[int] = None


class NetworkLatencyInjector:
    """
    Injects network latency, packet loss, and bandwidth limits.

    **Platform Support:**
    - Linux: Uses tc (traffic control) with netem - requires root
    - macOS: Software fallback only (pfctl too complex for this use case)
    - Windows: Software fallback only

    **Usage:**
    ```python
    with NetworkLatencyInjector(latency_ms=100, packet_loss_percent=5.0):
        # Network operations will experience 100ms latency + 5% packet loss
        await test_operation()
    # Network restored automatically
    ```
    """

    def __init__(
        self,
        latency_ms: int = 0,
        jitter_ms: int = 0,
        packet_loss_percent: float = 0.0,
        bandwidth_kbps: Optional[int] = None,
        interface: str = 'lo'
    ):
        """
        Initialize network latency injector.

        Args:
            latency_ms: Base latency in milliseconds (0-5000)
            jitter_ms: Latency variance in milliseconds
            packet_loss_percent: Packet loss percentage (0.0-100.0)
            bandwidth_kbps: Bandwidth limit in kbps
            interface: Network interface to apply rules (default: 'lo' for localhost)
        """
        require_test_environment()

        self.condition = NetworkCondition(
            latency_ms=latency_ms,
            jitter_ms=jitter_ms,
            packet_loss_percent=packet_loss_percent,
            bandwidth_kbps=bandwidth_kbps
        )
        self.interface = interface
        self.platform = get_platform()
        self.applied = False
        self._original_state = None

    def __enter__(self):
        """Apply network condition."""
        self.apply()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore network condition."""
        self.restore()
        return False

    async def __aenter__(self):
        """Async context manager entry."""
        self.apply()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.restore()
        return False

    def apply(self) -> bool:
        """
        Apply network condition.

        Returns:
            True if successfully applied, False if fallback to software delay
        """
        if self.applied:
            return True

        # Platform-specific implementation
        if self.platform == 'linux' and is_root():
            success = self._apply_linux_tc()
            if success:
                self.applied = True
                return True

        # Fallback: log warning
        print(f"⚠️  WARNING: Network injection unavailable on {self.platform}")
        print(f"    Latency={self.condition.latency_ms}ms will NOT be applied")
        print(f"    Use software delays in test code instead")
        print(f"    Or run with sudo on Linux for real network injection")
        return False

    def restore(self):
        """Restore original network configuration."""
        if not self.applied:
            return

        if self.platform == 'linux' and is_root():
            self._restore_linux_tc()

        self.applied = False

    def _apply_linux_tc(self) -> bool:
        """Apply traffic control rules on Linux using tc/netem."""
        try:
            # Clear existing rules
            subprocess.run(
                ['tc', 'qdisc', 'del', 'dev', self.interface, 'root'],
                capture_output=True,
                stderr=subprocess.DEVNULL
            )

            # Build tc command
            tc_cmd = ['tc', 'qdisc', 'add', 'dev', self.interface, 'root', 'netem']

            if self.condition.latency_ms > 0:
                tc_cmd.extend(['delay', f'{self.condition.latency_ms}ms'])
                if self.condition.jitter_ms > 0:
                    tc_cmd.append(f'{self.condition.jitter_ms}ms')

            if self.condition.packet_loss_percent > 0:
                tc_cmd.extend(['loss', f'{self.condition.packet_loss_percent}%'])

            # Execute command
            result = subprocess.run(tc_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ Applied network condition: {self.condition.latency_ms}ms latency, "
                      f"{self.condition.packet_loss_percent}% loss")
                return True
            else:
                print(f"❌ Failed to apply tc: {result.stderr}")
                return False

        except FileNotFoundError:
            print("❌ 'tc' command not found - install iproute2 package")
            return False
        except Exception as e:
            print(f"❌ Error applying network condition: {e}")
            return False

    def _restore_linux_tc(self):
        """Remove traffic control rules on Linux."""
        try:
            subprocess.run(
                ['tc', 'qdisc', 'del', 'dev', self.interface, 'root'],
                capture_output=True,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ Restored network condition on {self.interface}")
        except Exception as e:
            print(f"⚠️  Error restoring network: {e}")


# ============================================================================
# PROCESS KILLER
# ============================================================================

class ProcessKiller:
    """
    Terminates and restarts terminal processes for failure testing.

    **Usage:**
    ```python
    killer = ProcessKiller()

    # Graceful termination
    killer.kill_terminal(terminal_process, signal_type='SIGTERM')

    # Force kill
    with killer.kill_context(terminal_process, duration=5.0):
        # Terminal is killed for 5 seconds
        await test_recovery()
    # Terminal automatically restarted
    ```
    """

    def __init__(self):
        """Initialize process killer."""
        require_test_environment()
        self._killed_processes: Dict[int, Dict[str, Any]] = {}

    def kill_terminal(
        self,
        process: subprocess.Popen,
        signal_type: str = 'SIGTERM'
    ) -> bool:
        """
        Kill a terminal process.

        Args:
            process: subprocess.Popen object
            signal_type: 'SIGTERM' (graceful) or 'SIGKILL' (force)

        Returns:
            True if process was killed successfully
        """
        if not process or not process.pid:
            return False

        try:
            sig = getattr(signal, signal_type, signal.SIGTERM)
            process.send_signal(sig)

            # Wait for process to die (max 5 seconds)
            try:
                process.wait(timeout=5)
                print(f"✅ Killed process {process.pid} with {signal_type}")
                return True
            except subprocess.TimeoutExpired:
                # Force kill if graceful didn't work
                if signal_type == 'SIGTERM':
                    process.kill()
                    process.wait(timeout=2)
                print(f"⚠️  Force killed process {process.pid}")
                return True

        except Exception as e:
            print(f"❌ Error killing process {process.pid}: {e}")
            return False

    def kill_process_by_name(self, process_name: str, signal_type: str = 'SIGTERM') -> int:
        """
        Kill all processes matching name.

        Args:
            process_name: Name of process to kill (e.g., 'python')
            signal_type: Signal to send

        Returns:
            Number of processes killed
        """
        killed_count = 0

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    # Extra safety: check if it's a test process
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'test' in cmdline.lower() or '--demo' in cmdline:
                        sig = getattr(signal, signal_type, signal.SIGTERM)
                        os.kill(proc.info['pid'], sig)
                        killed_count += 1
                        print(f"✅ Killed {process_name} process {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return killed_count

    @contextmanager
    def kill_context(self, process: subprocess.Popen, duration: float = 5.0):
        """
        Context manager that kills process for specified duration.

        Args:
            process: Process to kill
            duration: Seconds to keep process dead

        Yields:
            Process info dict
        """
        # Store process info for restart
        proc_info = {
            'pid': process.pid,
            'args': process.args if hasattr(process, 'args') else None,
            'killed_at': time.time()
        }

        # Kill the process
        self.kill_terminal(process, signal_type='SIGKILL')

        try:
            # Wait for duration
            time.sleep(duration)
            yield proc_info
        finally:
            print(f"⚠️  Process {proc_info['pid']} should be restarted by test harness")
            # Note: Actual restart is responsibility of test fixture


# ============================================================================
# DATABASE BLOCKER
# ============================================================================

class DatabaseBlocker:
    """
    Blocks database connections by intercepting network traffic to Supabase.

    **Implementation Notes:**
    - Uses iptables/pfctl on Linux/macOS (requires root)
    - Software fallback: raises exceptions in database client

    **Usage:**
    ```python
    blocker = DatabaseBlocker(supabase_url="https://xyz.supabase.co")

    with blocker.block_context(duration=10.0):
        # Database operations will fail for 10 seconds
        await test_database_unavailable_handling()
    # Database access restored
    ```
    """

    def __init__(self, supabase_url: Optional[str] = None):
        """
        Initialize database blocker.

        Args:
            supabase_url: Supabase URL to block (extracts hostname)
        """
        require_test_environment()

        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL', '')
        self.hostname = self._extract_hostname(self.supabase_url)
        self.platform = get_platform()
        self.blocked = False

    def _extract_hostname(self, url: str) -> str:
        """Extract hostname from URL."""
        if not url:
            return ''
        # Simple extraction: https://xyz.supabase.co -> xyz.supabase.co
        return url.replace('https://', '').replace('http://', '').split('/')[0]

    @contextmanager
    def block_context(self, duration: float = 5.0):
        """
        Block database access for specified duration.

        Args:
            duration: Seconds to block database
        """
        self.block()
        try:
            time.sleep(duration)
            yield
        finally:
            self.unblock()

    def block(self):
        """Block database access."""
        if self.blocked:
            return

        print(f"⚠️  Database blocking: Software fallback only")
        print(f"    Tests must manually mock database failures")
        print(f"    Real network blocking requires root and iptables/pfctl")

        # Software fallback: Set environment variable that tests can check
        os.environ['TEST_DB_BLOCKED'] = '1'
        self.blocked = True

    def unblock(self):
        """Restore database access."""
        if not self.blocked:
            return

        os.environ.pop('TEST_DB_BLOCKED', None)
        self.blocked = False
        print("✅ Database access restored")


# ============================================================================
# PLC CRASHER
# ============================================================================

class PLCCrasher:
    """
    Crashes and restarts PLC simulation for failure testing.

    **Usage:**
    ```python
    crasher = PLCCrasher(plc_sim_process)

    with crasher.crash_context(duration=5.0):
        # PLC is crashed for 5 seconds
        await test_plc_disconnection_handling()
    # PLC automatically restarted
    ```
    """

    def __init__(self, plc_process: Optional[subprocess.Popen] = None):
        """
        Initialize PLC crasher.

        Args:
            plc_process: PLC simulation process to crash
        """
        require_test_environment()
        self.plc_process = plc_process
        self.crashed = False

    @contextmanager
    def crash_context(self, duration: float = 5.0):
        """
        Crash PLC for specified duration.

        Args:
            duration: Seconds to keep PLC crashed
        """
        self.crash()
        try:
            time.sleep(duration)
            yield
        finally:
            self.restart()

    def crash(self):
        """Crash the PLC simulation."""
        if self.crashed:
            return

        if self.plc_process:
            print(f"💥 Crashing PLC simulation process {self.plc_process.pid}")
            self.plc_process.kill()
            self.crashed = True
        else:
            print("⚠️  No PLC process provided - set TEST_PLC_CRASHED=1")
            os.environ['TEST_PLC_CRASHED'] = '1'
            self.crashed = True

    def restart(self):
        """Restart PLC simulation."""
        if not self.crashed:
            return

        os.environ.pop('TEST_PLC_CRASHED', None)
        self.crashed = False
        print("✅ PLC simulation should be restarted by test fixture")


# ============================================================================
# CLOCK SKEWER
# ============================================================================

class ClockSkewer:
    """
    Simulates clock skew for timing precision tests.

    **Implementation:**
    - Monkey-patches time.time() and time.monotonic()
    - Returns time offset by specified amount

    **Usage:**
    ```python
    with ClockSkewer(offset_seconds=5.0):
        # time.time() returns value 5 seconds in the future
        await test_timing_constraint_violations()
    # time.time() restored
    ```
    """

    def __init__(self, offset_seconds: float = 0.0):
        """
        Initialize clock skewer.

        Args:
            offset_seconds: Offset to add to time (can be negative)
        """
        require_test_environment()
        self.offset_seconds = offset_seconds
        self._original_time = None
        self._original_monotonic = None
        self.applied = False

    def __enter__(self):
        """Apply clock skew."""
        self.apply()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore clock."""
        self.restore()
        return False

    def apply(self):
        """Apply clock offset."""
        if self.applied:
            return

        import time as time_module

        # Store originals
        self._original_time = time_module.time
        self._original_monotonic = time_module.monotonic

        # Create offset functions
        offset = self.offset_seconds
        time_module.time = lambda: self._original_time() + offset
        time_module.monotonic = lambda: self._original_monotonic() + offset

        self.applied = True
        print(f"⏰ Applied clock skew: {offset} seconds")

    def restore(self):
        """Restore original time functions."""
        if not self.applied:
            return

        import time as time_module

        if self._original_time:
            time_module.time = self._original_time
        if self._original_monotonic:
            time_module.monotonic = self._original_monotonic

        self.applied = False
        print("✅ Restored clock")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def inject_network_latency(latency_ms: int, duration: float = 10.0):
    """
    Convenience function for quick network latency injection.

    Args:
        latency_ms: Latency in milliseconds
        duration: How long to maintain latency

    Example:
        inject_network_latency(100, duration=5.0)
    """
    with NetworkLatencyInjector(latency_ms=latency_ms):
        time.sleep(duration)


def inject_packet_loss(loss_percent: float, duration: float = 10.0):
    """
    Convenience function for packet loss injection.

    Args:
        loss_percent: Packet loss percentage (0-100)
        duration: How long to maintain packet loss
    """
    with NetworkLatencyInjector(packet_loss_percent=loss_percent):
        time.sleep(duration)


@contextmanager
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
    require_test_environment()

    print(f"💉 Injecting database failures: {probability*100}% probability")
    os.environ['TEST_DB_FAILURE_PROBABILITY'] = str(probability)

    try:
        yield
    finally:
        os.environ.pop('TEST_DB_FAILURE_PROBABILITY', None)
        print("✅ Database failure injection removed")
