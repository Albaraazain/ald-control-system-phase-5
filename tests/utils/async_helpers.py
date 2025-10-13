"""
Async test helper utilities for multi-terminal testing.

This module provides utilities for waiting on conditions, timeouts,
event collection, and subprocess management in async test environments.
"""

import asyncio
import time
from typing import Any, Callable, List, Optional, TypeVar, Coroutine
from functools import wraps


T = TypeVar('T')


async def wait_for_condition(
    condition_func: Callable[[], Any],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: str = "Condition not met"
) -> bool:
    """
    Wait for a condition function to return True.

    Args:
        condition_func: Sync or async callable that returns truthy value when condition is met
        timeout: Maximum time to wait in seconds (default 5.0)
        interval: Polling interval in seconds (default 0.1)
        error_message: Custom error message for timeout

    Returns:
        True when condition is met

    Raises:
        TimeoutError: If condition not met within timeout period

    Example:
        >>> async def check_terminal_ready():
        ...     return os.path.exists('/tmp/terminal.lock')
        >>> await wait_for_condition(check_terminal_ready, timeout=10.0)
    """
    start_time = time.perf_counter()

    while True:
        # Execute condition function (sync or async)
        if asyncio.iscoroutinefunction(condition_func):
            result = await condition_func()
        else:
            result = condition_func()

        if result:
            return True

        elapsed = time.perf_counter() - start_time
        if elapsed > timeout:
            raise TimeoutError(
                f"{error_message} within {timeout}s (elapsed: {elapsed:.2f}s)"
            )

        await asyncio.sleep(interval)


async def wait_for_database_record(
    db_client: Any,
    table: str,
    condition: str,
    timeout: float = 5.0,
    error_message: Optional[str] = None
) -> bool:
    """
    Wait for a database record matching condition to appear.

    Args:
        db_client: Supabase client or database service
        table: Table name to query
        condition: SQL WHERE clause condition
        timeout: Maximum wait time in seconds
        error_message: Custom error message (auto-generated if None)

    Returns:
        True when record found

    Raises:
        TimeoutError: If record not found within timeout

    Example:
        >>> await wait_for_database_record(
        ...     db, 'parameter_control_commands',
        ...     "completed_at IS NOT NULL AND id = '123'",
        ...     timeout=10.0
        ... )
    """
    if error_message is None:
        error_message = f"Record in {table} with condition '{condition}' not found"

    async def check_record() -> bool:
        try:
            # Support both Supabase client and DatabaseService
            if hasattr(db_client, 'table'):
                # Supabase client
                result = await db_client.table(table).select("*").execute()
                return len(result.data) > 0
            elif hasattr(db_client, 'execute_query'):
                # DatabaseService
                result = await db_client.execute_query(
                    f"SELECT * FROM {table} WHERE {condition}"
                )
                return len(result) > 0
            else:
                raise ValueError(f"Unsupported database client type: {type(db_client)}")
        except Exception:
            return False

    return await wait_for_condition(
        check_record,
        timeout=timeout,
        error_message=error_message
    )


async def wait_for_terminal_log(
    log_file_path: str,
    search_string: str,
    timeout: float = 10.0,
    error_message: Optional[str] = None
) -> str:
    """
    Wait for specific log message to appear in terminal log file.

    Args:
        log_file_path: Path to log file
        search_string: String to search for in log
        timeout: Maximum wait time in seconds
        error_message: Custom error message

    Returns:
        The line containing the search string

    Raises:
        TimeoutError: If message not found within timeout
        FileNotFoundError: If log file doesn't exist

    Example:
        >>> line = await wait_for_terminal_log(
        ...     'logs/plc.log',
        ...     'PLC connection established',
        ...     timeout=5.0
        ... )
    """
    if error_message is None:
        error_message = f"Log message '{search_string}' not found in {log_file_path}"

    found_line = None

    async def check_log() -> bool:
        nonlocal found_line
        try:
            with open(log_file_path, 'r') as f:
                for line in f:
                    if search_string in line:
                        found_line = line.strip()
                        return True
            return False
        except FileNotFoundError:
            return False

    await wait_for_condition(
        check_log,
        timeout=timeout,
        error_message=error_message
    )

    return found_line


async def run_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float = 5.0,
    error_message: Optional[str] = None
) -> T:
    """
    Run coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout: Maximum execution time in seconds
        error_message: Custom timeout error message

    Returns:
        Result from coroutine

    Raises:
        TimeoutError: If coroutine doesn't complete within timeout

    Example:
        >>> result = await run_with_timeout(
        ...     expensive_operation(),
        ...     timeout=30.0,
        ...     error_message="Operation took too long"
        ... )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        msg = error_message or f"Operation timed out after {timeout}s"
        raise TimeoutError(msg) from None


async def collect_events(
    event_queue: asyncio.Queue,
    count: int,
    timeout: float = 5.0
) -> List[Any]:
    """
    Collect N events from async queue with timeout.

    Args:
        event_queue: asyncio.Queue to collect from
        count: Number of events to collect
        timeout: Maximum total wait time

    Returns:
        List of collected events

    Raises:
        TimeoutError: If unable to collect all events within timeout

    Example:
        >>> events = await collect_events(event_queue, count=10, timeout=5.0)
        >>> assert len(events) == 10
    """
    events = []
    deadline = time.perf_counter() + timeout

    while len(events) < count:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError(
                f"Only collected {len(events)}/{count} events within {timeout}s"
            )

        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=remaining)
            events.append(event)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Only collected {len(events)}/{count} events within {timeout}s"
            ) from None

    return events


async def drain_queue(
    event_queue: asyncio.Queue,
    max_items: Optional[int] = None,
    timeout: float = 1.0
) -> List[Any]:
    """
    Drain all available items from queue (non-blocking after timeout).

    Args:
        event_queue: Queue to drain
        max_items: Maximum number of items to collect (None = unlimited)
        timeout: Maximum time to wait for new items

    Returns:
        List of all collected items

    Example:
        >>> all_events = await drain_queue(event_queue, timeout=0.5)
    """
    items = []
    deadline = time.perf_counter() + timeout

    while True:
        if max_items and len(items) >= max_items:
            break

        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break

        try:
            item = await asyncio.wait_for(event_queue.get(), timeout=remaining)
            items.append(item)
        except asyncio.TimeoutError:
            break

    return items


class AsyncSubprocessManager:
    """
    Manage async subprocess lifecycle with proper cleanup.

    Example:
        >>> async with AsyncSubprocessManager() as manager:
        ...     proc = await manager.start_subprocess(
        ...         ['python', 'main.py', '--terminal', '1'],
        ...         stdout=asyncio.subprocess.PIPE
        ...     )
        ...     await manager.wait_for_output(proc, 'Service started')
        # Subprocess automatically cleaned up on exit
    """

    def __init__(self):
        self.processes: List[asyncio.subprocess.Process] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup_all()

    async def start_subprocess(
        self,
        cmd: List[str],
        **kwargs
    ) -> asyncio.subprocess.Process:
        """
        Start subprocess and register for cleanup.

        Args:
            cmd: Command and arguments list
            **kwargs: Passed to asyncio.create_subprocess_exec

        Returns:
            Created process
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            **kwargs
        )
        self.processes.append(proc)
        return proc

    async def wait_for_output(
        self,
        proc: asyncio.subprocess.Process,
        expected_output: str,
        timeout: float = 10.0
    ) -> str:
        """
        Wait for specific output from subprocess stdout.

        Args:
            proc: Process to read from
            expected_output: String to search for
            timeout: Maximum wait time

        Returns:
            The line containing expected output

        Raises:
            TimeoutError: If output not seen within timeout
            ValueError: If process has no stdout pipe
        """
        if proc.stdout is None:
            raise ValueError("Process has no stdout pipe")

        async def check_output():
            line = await proc.stdout.readline()
            if not line:
                return False
            decoded = line.decode('utf-8').strip()
            return expected_output in decoded

        await wait_for_condition(
            check_output,
            timeout=timeout,
            error_message=f"Expected output '{expected_output}' not found"
        )

    async def cleanup_all(self):
        """Terminate and wait for all managed processes."""
        for proc in self.processes:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

        self.processes.clear()


def retry_on_exception(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry async function on specific exceptions.

    Args:
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        exceptions: Tuple of exception types to catch

    Example:
        >>> @retry_on_exception(max_attempts=3, delay=2.0)
        ... async def flaky_operation():
        ...     # May fail occasionally
        ...     return await unstable_api_call()
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay)
                    continue

            raise last_exception

        return wrapper
    return decorator


async def measure_execution_time(
    coro: Coroutine[Any, Any, T]
) -> tuple[T, float]:
    """
    Measure async coroutine execution time.

    Args:
        coro: Coroutine to measure

    Returns:
        Tuple of (result, execution_time_seconds)

    Example:
        >>> result, duration = await measure_execution_time(
        ...     expensive_operation()
        ... )
        >>> assert duration < 1.0, "Operation took too long"
    """
    start = time.perf_counter()
    result = await coro
    duration = time.perf_counter() - start
    return result, duration


async def run_concurrently(
    *coros: Coroutine[Any, Any, T],
    return_exceptions: bool = False
) -> List[T]:
    """
    Run multiple coroutines concurrently and gather results.

    Args:
        *coros: Coroutines to run concurrently
        return_exceptions: If True, exceptions are returned as results

    Returns:
        List of results in same order as input coroutines

    Example:
        >>> results = await run_concurrently(
        ...     fetch_user(1),
        ...     fetch_user(2),
        ...     fetch_user(3)
        ... )
    """
    return await asyncio.gather(*coros, return_exceptions=return_exceptions)


async def sleep_until(deadline: float):
    """
    Sleep until specific deadline (time.perf_counter() value).

    Args:
        deadline: Target perf_counter value to sleep until

    Example:
        >>> deadline = time.perf_counter() + 10.0
        >>> await sleep_until(deadline)
    """
    remaining = deadline - time.perf_counter()
    if remaining > 0:
        await asyncio.sleep(remaining)


async def timeout_after(seconds: float, error_message: Optional[str] = None):
    """
    Context manager that raises TimeoutError after specified seconds.

    This is a convenience wrapper around asyncio.wait_for that provides
    a context manager interface for timeout handling.

    Args:
        seconds: Timeout duration in seconds
        error_message: Custom error message for timeout

    Raises:
        TimeoutError: If timeout is exceeded

    Example:
        >>> async with timeout_after(5.0, "Operation took too long"):
        ...     await long_running_operation()
    """
    import contextlib

    @contextlib.asynccontextmanager
    async def _timeout():
        task = asyncio.current_task()
        timeout_handle = asyncio.get_event_loop().call_later(
            seconds,
            lambda: task.cancel() if task else None
        )

        try:
            yield
        except asyncio.CancelledError:
            msg = error_message or f"Operation timed out after {seconds}s"
            raise TimeoutError(msg) from None
        finally:
            timeout_handle.cancel()

    return _timeout()
