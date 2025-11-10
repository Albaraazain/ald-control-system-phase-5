"""
Global error handlers and exception catchers for terminal services.

Provides utilities to catch and log uncaught exceptions,
ensuring terminals record errors before crashing.
"""
import sys
import traceback
import asyncio
import functools
from typing import Callable, TypeVar, Optional, Any
from contextlib import asynccontextmanager

T = TypeVar('T')

def setup_global_exception_handler(registry=None, logger=None):
    """
    Setup global exception handler to catch uncaught exceptions.

    Args:
        registry: TerminalRegistry instance to record errors
        logger: Logger instance for error logging
    """
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow KeyboardInterrupt to propagate normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        if logger:
            logger.critical(
                f"🔥 UNCAUGHT EXCEPTION - Terminal will crash!\n"
                f"Exception Type: {exc_type.__name__}\n"
                f"Exception Value: {exc_value}\n"
                f"Traceback:\n{error_msg}"
            )

        if registry:
            try:
                # Record error before crash
                registry.record_error(f"UNCAUGHT: {exc_type.__name__}: {exc_value}")
            except Exception as e:
                if logger:
                    logger.error(f"Failed to record uncaught exception: {e}")

        # Call original exception hook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_hook


def setup_asyncio_exception_handler(registry=None, logger=None):
    """
    Setup asyncio exception handler for unhandled task exceptions.

    Args:
        registry: TerminalRegistry instance to record errors
        logger: Logger instance for error logging
    """
    def asyncio_exception_handler(loop, context):
        """Handle asyncio task exceptions"""
        exc = context.get('exception')
        if exc:
            error_msg = f"{type(exc).__name__}: {exc}"
        else:
            error_msg = context.get('message', 'Unknown asyncio error')

        if logger:
            logger.error(
                f"🔥 ASYNCIO EXCEPTION:\n"
                f"Message: {error_msg}\n"
                f"Context: {context}"
            )

        if registry:
            try:
                registry.record_error(f"ASYNCIO: {error_msg}")
            except Exception as e:
                if logger:
                    logger.error(f"Failed to record asyncio exception: {e}")

        # Call default handler
        loop.default_exception_handler(context)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(asyncio_exception_handler)


def with_error_logging(registry=None, logger=None):
    """
    Decorator that logs exceptions to registry before re-raising.

    Example:
        @with_error_logging(registry=my_registry, logger=my_logger)
        async def risky_operation():
            # ... code that might fail
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Log error
                error_msg = f"{func.__name__}: {type(e).__name__}: {e}"

                if logger:
                    logger.error(f"❌ Error in {func.__name__}: {e}", exc_info=True)

                if registry:
                    try:
                        registry.record_error(error_msg)
                    except Exception as record_err:
                        if logger:
                            logger.error(f"Failed to record error: {record_err}")

                # Re-raise original exception
                raise

        return wrapper
    return decorator


@asynccontextmanager
async def safe_operation(operation_name: str, registry=None, logger=None, reraise: bool = True):
    """
    Context manager for safe operations with error logging.

    Example:
        async with safe_operation("database_query", registry=registry):
            result = await supabase.table('data').select('*').execute()
    """
    try:
        yield
    except Exception as e:
        error_msg = f"{operation_name}: {type(e).__name__}: {e}"

        if logger:
            logger.error(f"❌ Error in {operation_name}: {e}", exc_info=True)

        if registry:
            try:
                registry.record_error(error_msg)
            except Exception as record_err:
                if logger:
                    logger.error(f"Failed to record error: {record_err}")

        if reraise:
            raise


class ErrorThresholdMonitor:
    """
    Monitor error rates and trigger alerts/actions when threshold exceeded.

    Example:
        monitor = ErrorThresholdMonitor(threshold=10, window_seconds=60)

        if monitor.record_error():
            # Too many errors!
            await notify_admin()
    """

    def __init__(self, threshold: int = 10, window_seconds: float = 60.0):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.error_timestamps: list[float] = []

    def record_error(self) -> bool:
        """
        Record an error occurrence.

        Returns:
            bool: True if error threshold exceeded
        """
        import time
        now = time.time()

        # Add new error
        self.error_timestamps.append(now)

        # Remove old errors outside window
        cutoff = now - self.window_seconds
        self.error_timestamps = [
            ts for ts in self.error_timestamps
            if ts > cutoff
        ]

        # Check threshold
        return len(self.error_timestamps) >= self.threshold

    def get_error_rate(self) -> float:
        """Get current error rate (errors per second)"""
        if not self.error_timestamps:
            return 0.0
        return len(self.error_timestamps) / self.window_seconds

    def reset(self):
        """Reset error tracking"""
        self.error_timestamps.clear()
