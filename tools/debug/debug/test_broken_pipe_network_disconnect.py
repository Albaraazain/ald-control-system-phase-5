"""
Test script to simulate network disconnection and validate broken pipe error handling.
This test validates the fixes for errno 32 "broken pipe" errors in PLCCommunicator.
"""
import os
import sys
import asyncio
import subprocess
import time
import threading
from dotenv import load_dotenv

# Add parent directory to path to import from main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_setup import logger
from plc.manager import plc_manager


class NetworkDisconnectionTest:
    """Test network disconnection scenarios to validate broken pipe error handling."""

    def __init__(self):
        self.test_results = {
            'connection_established': False,
            'operations_before_disconnect': 0,
            'broken_pipe_errors_detected': 0,
            'successful_reconnections': 0,
            'operations_after_reconnect': 0,
            'total_test_duration': 0,
            'retry_attempts_logged': 0
        }
        self.plc_ip = None
        self.network_interface = None

    async def setup_test(self):
        """Setup test environment and establish initial PLC connection."""
        logger.info("🔧 Setting up network disconnection test...")

        # Initialize PLC and get connection info
        success = await plc_manager.initialize()
        if not success:
            logger.error("❌ Failed to establish initial PLC connection")
            return False

        # Get PLC IP for network manipulation
        if hasattr(plc_manager.plc, 'communicator') and hasattr(plc_manager.plc.communicator, '_current_ip'):
            self.plc_ip = plc_manager.plc.communicator._current_ip
        else:
            self.plc_ip = "192.168.1.11"  # Default fallback

        # Detect network interface (simplified - works on most systems)
        try:
            # Get the route to PLC IP to determine interface
            result = subprocess.run(['route', 'get', self.plc_ip], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'interface:' in line:
                    self.network_interface = line.split('interface:')[1].strip()
                    break
        except:
            # Fallback - try common interfaces
            for interface in ['en0', 'eth0', 'wlan0']:
                try:
                    subprocess.run(['ifconfig', interface], capture_output=True, check=True)
                    self.network_interface = interface
                    break
                except:
                    continue

        self.test_results['connection_established'] = True
        logger.info(f"✅ Test setup complete. PLC IP: {self.plc_ip}, Interface: {self.network_interface}")
        return True

    async def test_operations_before_disconnect(self):
        """Perform operations before network disconnection to establish baseline."""
        logger.info("📊 Testing operations before network disconnection...")

        operations_count = 0
        try:
            # Test reading various parameters
            for i in range(5):
                # Try reading a float value (common operation that fails with broken pipe)
                try:
                    # Use address 0 as test address - even if invalid, should get proper Modbus response
                    result = plc_manager.plc.communicator.read_float(0)
                    operations_count += 1
                    logger.debug(f"Read operation {i+1} completed: {result}")
                    await asyncio.sleep(0.5)  # Small delay between operations
                except Exception as e:
                    logger.warning(f"Operation {i+1} failed: {e}")

            self.test_results['operations_before_disconnect'] = operations_count
            logger.info(f"✅ Completed {operations_count} operations before disconnect")

        except Exception as e:
            logger.error(f"❌ Error during pre-disconnect operations: {e}")

    def simulate_network_disconnect(self, duration=10):
        """Simulate network disconnection by blocking PLC IP."""
        logger.info(f"🔌 Simulating network disconnection for {duration} seconds...")

        try:
            # Method 1: Block IP using firewall rules (requires sudo)
            # This is safer than bringing down the entire interface
            block_cmd = ['sudo', 'pfctl', '-f', '-']
            block_rules = f"""
block drop out to {self.plc_ip}
block drop in from {self.plc_ip}
"""

            # Apply blocking rules
            process = subprocess.Popen(block_cmd, stdin=subprocess.PIPE, text=True)
            process.communicate(input=block_rules)

            logger.info(f"🚫 Network traffic to {self.plc_ip} blocked")

            # Wait for the specified duration
            time.sleep(duration)

            # Remove blocking rules
            unblock_cmd = ['sudo', 'pfctl', '-f', '/etc/pf.conf']  # Restore default rules
            subprocess.run(unblock_cmd, check=True)

            logger.info(f"🔓 Network traffic to {self.plc_ip} restored")

        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ Firewall method failed: {e}")
            # Fallback method: Add routing rule to black hole the IP
            try:
                # Add route to nowhere
                subprocess.run(['sudo', 'route', 'add', self.plc_ip, '127.0.0.1'], check=True)
                logger.info(f"🚫 Route to {self.plc_ip} redirected to localhost")

                time.sleep(duration)

                # Remove the route
                subprocess.run(['sudo', 'route', 'delete', self.plc_ip], check=True)
                logger.info(f"🔓 Route to {self.plc_ip} restored")

            except subprocess.CalledProcessError as e2:
                logger.error(f"❌ Both network disconnection methods failed: {e2}")
                # Fallback: Just wait and let the test continue
                logger.warning("⚠️ Using sleep-only simulation (won't trigger actual network errors)")
                time.sleep(duration)

    async def test_operations_during_disconnect(self):
        """Test operations during network disconnection to trigger broken pipe errors."""
        logger.info("🔍 Testing operations during network disconnection...")

        broken_pipe_count = 0
        retry_attempts = 0

        # Start network disconnection in a separate thread
        disconnect_thread = threading.Thread(
            target=self.simulate_network_disconnect,
            args=(15,)  # 15 seconds disconnect
        )
        disconnect_thread.start()

        # Wait a moment for disconnection to take effect
        await asyncio.sleep(2)

        # Attempt operations during disconnection
        for i in range(10):
            try:
                logger.debug(f"Attempting operation {i+1} during disconnect...")

                # This should trigger broken pipe errors and retry logic
                result = plc_manager.plc.communicator.read_float(0)

                if result is None:
                    logger.debug(f"Operation {i+1} returned None (expected during disconnect)")
                else:
                    logger.info(f"Operation {i+1} succeeded despite disconnect: {result}")

            except Exception as e:
                error_str = str(e).lower()
                if 'broken pipe' in error_str or 'errno 32' in error_str:
                    broken_pipe_count += 1
                    logger.info(f"🎯 Broken pipe error detected (expected): {e}")
                elif 'attempt' in error_str or 'retry' in error_str:
                    retry_attempts += 1
                    logger.info(f"🔄 Retry attempt logged: {e}")
                else:
                    logger.debug(f"Other error during disconnect: {e}")

            await asyncio.sleep(1)  # Space out operations

        # Wait for disconnection to end
        disconnect_thread.join()

        self.test_results['broken_pipe_errors_detected'] = broken_pipe_count
        self.test_results['retry_attempts_logged'] = retry_attempts

        logger.info(f"📊 Disconnect test complete: {broken_pipe_count} broken pipe errors, {retry_attempts} retry attempts")

    async def test_connection_recovery(self):
        """Test connection recovery after network restoration."""
        logger.info("🔄 Testing connection recovery after network restoration...")

        reconnection_attempts = 0
        successful_operations = 0

        # Give the system time to detect network restoration
        await asyncio.sleep(3)

        # Test recovery over multiple attempts
        for attempt in range(5):
            try:
                logger.debug(f"Recovery attempt {attempt + 1}...")

                # Try to perform an operation
                result = plc_manager.plc.communicator.read_float(0)

                if result is not None or not (hasattr(result, 'isError') and result.isError()):
                    successful_operations += 1
                    reconnection_attempts += 1
                    logger.info(f"✅ Recovery successful on attempt {attempt + 1}")
                    break
                else:
                    logger.debug(f"Recovery attempt {attempt + 1} failed: {result}")

            except Exception as e:
                logger.debug(f"Recovery attempt {attempt + 1} error: {e}")

            await asyncio.sleep(2)  # Wait between recovery attempts

        self.test_results['successful_reconnections'] = reconnection_attempts
        self.test_results['operations_after_reconnect'] = successful_operations

        # Test sustained operations after recovery
        if successful_operations > 0:
            logger.info("🔄 Testing sustained operations after recovery...")
            for i in range(5):
                try:
                    result = plc_manager.plc.communicator.read_float(0)
                    if result is not None:
                        successful_operations += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Post-recovery operation {i+1} failed: {e}")

        self.test_results['operations_after_reconnect'] = successful_operations

    async def run_full_test(self):
        """Run the complete network disconnection test suite."""
        start_time = time.time()

        logger.info("🚀 Starting comprehensive network disconnection test...")
        logger.info("This test validates broken pipe error handling and recovery mechanisms")

        try:
            # Setup
            if not await self.setup_test():
                return False

            # Test operations before disconnect
            await self.test_operations_before_disconnect()

            # Test during disconnect (this should trigger broken pipe errors)
            await self.test_operations_during_disconnect()

            # Test recovery
            await self.test_connection_recovery()

            # Calculate test duration
            self.test_results['total_test_duration'] = time.time() - start_time

            # Report results
            self.report_test_results()

            return True

        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}", exc_info=True)
            return False

        finally:
            # Cleanup
            if plc_manager.is_connected():
                await plc_manager.disconnect()

    def report_test_results(self):
        """Report comprehensive test results."""
        logger.info("📊 NETWORK DISCONNECTION TEST RESULTS")
        logger.info("=" * 50)

        results = self.test_results

        logger.info(f"✅ Connection established: {results['connection_established']}")
        logger.info(f"📈 Operations before disconnect: {results['operations_before_disconnect']}")
        logger.info(f"🚫 Broken pipe errors detected: {results['broken_pipe_errors_detected']}")
        logger.info(f"🔄 Retry attempts logged: {results['retry_attempts_logged']}")
        logger.info(f"🔗 Successful reconnections: {results['successful_reconnections']}")
        logger.info(f"📈 Operations after reconnect: {results['operations_after_reconnect']}")
        logger.info(f"⏱️ Total test duration: {results['total_test_duration']:.2f} seconds")

        # Evaluation
        logger.info("\n🔍 TEST EVALUATION:")

        if results['broken_pipe_errors_detected'] > 0:
            logger.info("✅ Broken pipe errors successfully triggered and detected")
        else:
            logger.warning("⚠️ No broken pipe errors detected - network disconnect may not have worked")

        if results['retry_attempts_logged'] > 0:
            logger.info("✅ Retry logic is working - attempts logged during failures")
        else:
            logger.warning("⚠️ No retry attempts logged - retry logic may need review")

        if results['successful_reconnections'] > 0:
            logger.info("✅ Connection recovery working - successful reconnection detected")
        else:
            logger.error("❌ Connection recovery failed - may need manual intervention")

        if results['operations_after_reconnect'] >= 3:
            logger.info("✅ Sustained operations after recovery working well")
        elif results['operations_after_reconnect'] > 0:
            logger.warning("⚠️ Limited operations after recovery - may have intermittent issues")
        else:
            logger.error("❌ No operations successful after recovery - connection may not be stable")

        # Overall assessment
        logger.info("\n🎯 OVERALL ASSESSMENT:")
        critical_pass = (
            results['connection_established'] and
            results['operations_before_disconnect'] > 0 and
            (results['broken_pipe_errors_detected'] > 0 or results['retry_attempts_logged'] > 0) and
            results['operations_after_reconnect'] > 0
        )

        if critical_pass:
            logger.info("🟢 PASS: Broken pipe error handling appears to be working correctly")
        else:
            logger.error("🔴 FAIL: Critical issues detected in broken pipe error handling")


async def main():
    """Main test execution function."""
    # Load environment variables
    load_dotenv()

    # Create and run test
    test = NetworkDisconnectionTest()
    success = await test.run_full_test()

    if success:
        logger.info("🎉 Network disconnection test completed successfully")
    else:
        logger.error("💥 Network disconnection test failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())