"""
Terminal-related test fixtures for multi-terminal testing.

Provides fixtures for:
- Terminal launcher (start terminal processes)
- Multi-terminal orchestration
- Terminal health monitoring via fcntl locks
- Terminal log capture and parsing
- Graceful terminal shutdown
"""

import pytest
import pytest_asyncio
import asyncio
import os
import signal
from typing import Dict, List, Optional
from pathlib import Path


@pytest_asyncio.fixture
async def terminal_launcher():
    """
    Launch individual terminal processes for testing.

    Returns:
        TerminalLauncher: Utility for launching and managing terminals

    Example:
        async def test_terminal1(terminal_launcher):
            proc = await terminal_launcher.launch_terminal(1)
            await terminal_launcher.wait_for_ready(proc)
            await terminal_launcher.stop_terminal(proc)
    """
    class TerminalLauncher:
        def __init__(self):
            self.processes = []

        async def launch_terminal(
            self,
            terminal_number: int,
            demo_mode: bool = True,
            capture_output: bool = True
        ) -> asyncio.subprocess.Process:
            """Launch a terminal process."""
            cmd = [
                'python', 'main.py',
                '--terminal', str(terminal_number)
            ]

            if demo_mode:
                cmd.append('--demo')

            kwargs = {}
            if capture_output:
                kwargs['stdout'] = asyncio.subprocess.PIPE
                kwargs['stderr'] = asyncio.subprocess.PIPE

            proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
            self.processes.append(proc)
            return proc

        async def wait_for_ready(
            self,
            proc: asyncio.subprocess.Process,
            timeout: float = 30.0
        ):
            """Wait for terminal to be ready (check lock file)."""
            # In real implementation, check fcntl lock files
            await asyncio.sleep(2.0)  # Simple delay for now

        async def stop_terminal(self, proc: asyncio.subprocess.Process):
            """Gracefully stop terminal process."""
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

        async def cleanup_all(self):
            """Stop all running terminals."""
            for proc in self.processes:
                await self.stop_terminal(proc)
            self.processes.clear()

    launcher = TerminalLauncher()
    yield launcher
    await launcher.cleanup_all()


@pytest_asyncio.fixture
async def three_terminals(terminal_launcher):
    """
    Launch all 3 terminals simultaneously for integration testing.

    Returns:
        dict: Dict with terminal processes {1: proc1, 2: proc2, 3: proc3}

    Example:
        @pytest.mark.serial
        async def test_all_terminals(three_terminals):
            # All 3 terminals are running
            assert 1 in three_terminals
            assert 2 in three_terminals
            assert 3 in three_terminals
    """
    terminals = {}

    # Launch all 3 terminals
    terminals[1] = await terminal_launcher.launch_terminal(1, demo_mode=True)
    terminals[2] = await terminal_launcher.launch_terminal(2, demo_mode=True)
    terminals[3] = await terminal_launcher.launch_terminal(3, demo_mode=True)

    # Wait for all to be ready
    for proc in terminals.values():
        await terminal_launcher.wait_for_ready(proc)

    yield terminals

    # Cleanup handled by terminal_launcher fixture


@pytest.fixture
def terminal_health_monitor():
    """
    Monitor terminal health via lock files and process status.

    Returns:
        TerminalHealthMonitor: Health monitoring utilities

    Example:
        async def test_terminal_health(terminal_launcher, terminal_health_monitor):
            proc = await terminal_launcher.launch_terminal(1)
            assert terminal_health_monitor.is_process_alive(proc)
    """
    class TerminalHealthMonitor:
        @staticmethod
        def is_process_alive(proc: asyncio.subprocess.Process) -> bool:
            """Check if process is still running."""
            return proc.returncode is None

        @staticmethod
        def check_lock_file_exists(terminal_number: int) -> bool:
            """Check if terminal lock file exists."""
            lock_path = Path(f'/tmp/terminal{terminal_number}.lock')
            return lock_path.exists()

        @staticmethod
        async def wait_for_lock_file(
            terminal_number: int,
            timeout: float = 10.0
        ) -> bool:
            """Wait for terminal lock file to appear."""
            from tests.utils.async_helpers import wait_for_condition

            await wait_for_condition(
                lambda: TerminalHealthMonitor.check_lock_file_exists(terminal_number),
                timeout=timeout,
                error_message=f"Terminal {terminal_number} lock file not created"
            )
            return True

    return TerminalHealthMonitor()


@pytest_asyncio.fixture
async def terminal_log_capture():
    """
    Capture and parse terminal log output.

    Returns:
        TerminalLogCapture: Log capture utilities

    Example:
        async def test_terminal_logs(terminal_launcher, terminal_log_capture):
            proc = await terminal_launcher.launch_terminal(1, capture_output=True)
            logs = await terminal_log_capture.get_logs(proc, lines=10)
            assert 'Service started' in logs
    """
    class TerminalLogCapture:
        @staticmethod
        async def get_logs(
            proc: asyncio.subprocess.Process,
            lines: int = 100
        ) -> str:
            """Get stdout/stderr from process."""
            if proc.stdout is None:
                return ""

            output_lines = []
            try:
                for _ in range(lines):
                    line = await asyncio.wait_for(
                        proc.stdout.readline(),
                        timeout=0.1
                    )
                    if not line:
                        break
                    output_lines.append(line.decode('utf-8'))
            except asyncio.TimeoutError:
                pass

            return ''.join(output_lines)

        @staticmethod
        async def search_logs(
            proc: asyncio.subprocess.Process,
            search_string: str,
            timeout: float = 10.0
        ) -> bool:
            """Search for string in process output."""
            deadline = asyncio.get_event_loop().time() + timeout

            while asyncio.get_event_loop().time() < deadline:
                if proc.stdout is None:
                    return False

                try:
                    line = await asyncio.wait_for(
                        proc.stdout.readline(),
                        timeout=0.5
                    )
                    if not line:
                        continue

                    decoded = line.decode('utf-8')
                    if search_string in decoded:
                        return True
                except asyncio.TimeoutError:
                    continue

            return False

    return TerminalLogCapture()
