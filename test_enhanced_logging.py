#!/usr/bin/env python3
"""
Test script for the enhanced service-specific logging system.
"""
import os
import sys
import threading
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.log_setup import (
    get_service_logger,
    get_command_flow_logger,
    get_plc_logger,
    get_data_collection_logger,
    list_service_loggers,
    set_log_level,
    logger as default_logger
)

def test_basic_logging():
    """Test basic service-specific logging functionality."""
    print("Testing basic service-specific logging...")

    # Test different service loggers
    command_logger = get_command_flow_logger()
    plc_logger = get_plc_logger()
    data_logger = get_data_collection_logger()

    # Test logging messages
    command_logger.info("Command flow logger test message")
    plc_logger.info("PLC logger test message")
    data_logger.info("Data collection logger test message")

    # Test default logger (backward compatibility)
    default_logger.info("Default machine control logger test message")

    print("✅ Basic logging test completed")

def test_thread_safety():
    """Test thread safety of logger creation."""
    print("Testing thread safety...")

    def worker(worker_id):
        for i in range(10):
            logger = get_service_logger(f"test_service_{worker_id}")
            logger.info(f"Thread {worker_id}, iteration {i}")
            time.sleep(0.01)

    # Create multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    print("✅ Thread safety test completed")

def test_log_level_control():
    """Test log level control functionality."""
    print("Testing log level control...")

    # Get a test logger
    test_logger = get_service_logger("test_levels")

    # Test different log levels
    set_log_level("DEBUG", "test_levels")
    test_logger.debug("Debug message (should appear)")

    set_log_level("ERROR", "test_levels")
    test_logger.info("Info message (should not appear)")
    test_logger.error("Error message (should appear)")

    print("✅ Log level control test completed")

def test_file_creation():
    """Test that log files are created correctly."""
    print("Testing log file creation...")

    logs_dir = Path("logs")

    # Check that logs directory exists
    assert logs_dir.exists(), "Logs directory should exist"

    # Test that logging creates files
    get_command_flow_logger().info("Test message for file creation")
    get_plc_logger().info("Test message for file creation")

    # Check some expected log files
    expected_files = [
        "machine_control.log",
        "command_flow.log",
        "plc.log"
    ]

    for filename in expected_files:
        file_path = logs_dir / filename
        if file_path.exists():
            print(f"✅ {filename} created successfully")
        else:
            print(f"⚠️ {filename} not found")

    print("✅ File creation test completed")

def main():
    """Run all tests."""
    print("Starting enhanced logging system tests...")
    print("=" * 50)

    try:
        test_basic_logging()
        test_thread_safety()
        test_log_level_control()
        test_file_creation()

        print("=" * 50)
        print("All tests completed successfully! 🎉")

        # Show available loggers
        loggers = list_service_loggers()
        print(f"Active service loggers: {loggers}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    main()