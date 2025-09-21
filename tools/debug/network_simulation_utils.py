"""
Network Simulation Utilities for Latency Stress Testing

Provides utilities for:
- Network latency simulation using tc/netem
- Packet loss and jitter simulation
- Bandwidth throttling
- Timeout configuration recommendations
- Network condition monitoring
"""
import os
import sys
import subprocess
import time
import socket
import threading
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.log_setup import logger


@dataclass
class NetworkMonitoringResult:
    """Results from network monitoring."""
    timestamp: float
    latency_ms: float
    packet_loss_percent: float
    bandwidth_kbps: float
    jitter_ms: float
    connection_successful: bool
    error_message: Optional[str] = None


class NetworkSimulationManager:
    """Manages network simulation and monitoring for stress testing."""

    def __init__(self):
        self.active_rules = []
        self.monitoring_active = False
        self.monitoring_results = []

    def check_privileges(self) -> bool:
        """Check if running with sufficient privileges for network manipulation."""
        try:
            result = subprocess.run(['id', '-u'], capture_output=True, text=True)
            return result.stdout.strip() == '0'
        except:
            return False

    def check_tc_availability(self) -> bool:
        """Check if tc (traffic control) is available."""
        try:
            result = subprocess.run(['which', 'tc'], capture_output=True)
            return result.returncode == 0
        except:
            return False

    def get_network_interfaces(self) -> List[str]:
        """Get list of available network interfaces."""
        interfaces = []
        try:
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if ': ' in line and not line.strip().startswith(' '):
                    interface = line.split(': ')[1].split('@')[0]
                    interfaces.append(interface)
        except:
            # Fallback to common interfaces
            interfaces = ['lo', 'eth0', 'wlan0', 'enp0s3']

        return [iface for iface in interfaces if iface not in ['', 'sit0']]

    def clear_all_tc_rules(self, interface: str = 'lo'):
        """Clear all tc rules on specified interface."""
        try:
            subprocess.run(['tc', 'qdisc', 'del', 'dev', interface, 'root'],
                         capture_output=True, stderr=subprocess.DEVNULL)
            if interface in self.active_rules:
                self.active_rules.remove(interface)
            logger.info(f"✅ Cleared tc rules on {interface}")
        except Exception as e:
            logger.debug(f"Note: tc clear on {interface} - {e}")

    def apply_latency(self, latency_ms: int, jitter_ms: int = 0, interface: str = 'lo') -> bool:
        """Apply network latency using tc netem."""
        if not self.check_privileges():
            logger.error("❌ Root privileges required for network simulation")
            return False

        if not self.check_tc_availability():
            logger.error("❌ tc (traffic control) not available")
            return False

        try:
            # Clear existing rules
            self.clear_all_tc_rules(interface)

            # Build tc command
            cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem', 'delay', f'{latency_ms}ms']

            if jitter_ms > 0:
                cmd.append(f'{jitter_ms}ms')

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.active_rules.append(interface)
                logger.info(f"✅ Applied {latency_ms}ms latency (±{jitter_ms}ms jitter) to {interface}")
                return True
            else:
                logger.error(f"❌ Failed to apply latency: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Error applying latency: {e}")
            return False

    def apply_packet_loss(self, loss_percent: float, interface: str = 'lo') -> bool:
        """Apply packet loss using tc netem."""
        if not self.check_privileges():
            logger.error("❌ Root privileges required for network simulation")
            return False

        try:
            # Clear existing rules
            self.clear_all_tc_rules(interface)

            cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem', 'loss', f'{loss_percent}%']

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.active_rules.append(interface)
                logger.info(f"✅ Applied {loss_percent}% packet loss to {interface}")
                return True
            else:
                logger.error(f"❌ Failed to apply packet loss: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Error applying packet loss: {e}")
            return False

    def apply_bandwidth_limit(self, bandwidth_kbps: int, interface: str = 'lo') -> bool:
        """Apply bandwidth limiting using tc tbf."""
        if not self.check_privileges():
            logger.error("❌ Root privileges required for network simulation")
            return False

        try:
            # Clear existing rules
            self.clear_all_tc_rules(interface)

            # Calculate burst and latency based on bandwidth
            burst_kb = max(32, bandwidth_kbps // 8)  # At least 32KB burst
            latency_ms = 50

            cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'root', 'tbf',
                   'rate', f'{bandwidth_kbps}kbit',
                   'burst', f'{burst_kb}kbit',
                   'latency', f'{latency_ms}ms']

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.active_rules.append(interface)
                logger.info(f"✅ Applied {bandwidth_kbps}kbps bandwidth limit to {interface}")
                return True
            else:
                logger.error(f"❌ Failed to apply bandwidth limit: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Error applying bandwidth limit: {e}")
            return False

    def apply_complex_condition(self, latency_ms: int, jitter_ms: int = 0,
                              loss_percent: float = 0, bandwidth_kbps: Optional[int] = None,
                              interface: str = 'lo') -> bool:
        """Apply complex network condition with multiple constraints."""
        if not self.check_privileges():
            logger.error("❌ Root privileges required for network simulation")
            return False

        try:
            # Clear existing rules
            self.clear_all_tc_rules(interface)

            # Build netem command
            netem_cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'root', 'handle', '1:', 'netem']

            if latency_ms > 0:
                netem_cmd.extend(['delay', f'{latency_ms}ms'])
                if jitter_ms > 0:
                    netem_cmd.append(f'{jitter_ms}ms')

            if loss_percent > 0:
                netem_cmd.extend(['loss', f'{loss_percent}%'])

            # Apply netem rules
            result = subprocess.run(netem_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"❌ Failed to apply netem rules: {result.stderr}")
                return False

            # Apply bandwidth limiting if specified
            if bandwidth_kbps:
                burst_kb = max(32, bandwidth_kbps // 8)
                tbf_cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'parent', '1:1', 'handle', '10:', 'tbf',
                          'rate', f'{bandwidth_kbps}kbit', 'burst', f'{burst_kb}kbit', 'latency', '50ms']

                result = subprocess.run(tbf_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"⚠️ Failed to apply bandwidth limit: {result.stderr}")

            self.active_rules.append(interface)
            logger.info(f"✅ Applied complex condition to {interface}: {latency_ms}ms±{jitter_ms}ms, {loss_percent}% loss, {bandwidth_kbps}kbps")
            return True

        except Exception as e:
            logger.error(f"❌ Error applying complex condition: {e}")
            return False

    @contextmanager
    def network_condition(self, latency_ms: int, jitter_ms: int = 0,
                         loss_percent: float = 0, bandwidth_kbps: Optional[int] = None,
                         interface: str = 'lo'):
        """Context manager for temporary network conditions."""
        applied = self.apply_complex_condition(latency_ms, jitter_ms, loss_percent, bandwidth_kbps, interface)
        try:
            yield applied
        finally:
            if applied:
                self.clear_all_tc_rules(interface)

    def measure_actual_latency(self, host: str = '127.0.0.1', port: int = 22, timeout: float = 5.0) -> float:
        """Measure actual network latency to a host/port."""
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            result = sock.connect_ex((host, port))
            end_time = time.time()

            sock.close()

            if result == 0:
                return (end_time - start_time) * 1000  # Convert to milliseconds
            else:
                return -1  # Connection failed

        except Exception:
            return -1

    def ping_test(self, host: str = '127.0.0.1', count: int = 5) -> Dict:
        """Perform ping test and return statistics."""
        try:
            cmd = ['ping', '-c', str(count), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                output = result.stdout

                # Parse ping statistics
                stats = {
                    'packets_transmitted': 0,
                    'packets_received': 0,
                    'packet_loss_percent': 0.0,
                    'min_ms': 0.0,
                    'avg_ms': 0.0,
                    'max_ms': 0.0,
                    'stddev_ms': 0.0
                }

                for line in output.split('\n'):
                    if 'packets transmitted' in line:
                        parts = line.split()
                        stats['packets_transmitted'] = int(parts[0])
                        stats['packets_received'] = int(parts[3])
                        # Extract packet loss percentage
                        for part in parts:
                            if '%' in part and 'packet' not in part:
                                stats['packet_loss_percent'] = float(part.replace('%', ''))

                    elif 'min/avg/max/stddev' in line or 'min/avg/max/mdev' in line:
                        # Extract timing statistics
                        times_part = line.split('=')[1].strip()
                        times = times_part.split('/')
                        if len(times) >= 4:
                            stats['min_ms'] = float(times[0])
                            stats['avg_ms'] = float(times[1])
                            stats['max_ms'] = float(times[2])
                            stats['stddev_ms'] = float(times[3].split()[0])

                return stats
            else:
                return {'error': f"Ping failed: {result.stderr}"}

        except Exception as e:
            return {'error': f"Ping test failed: {e}"}

    def start_network_monitoring(self, host: str = '127.0.0.1', port: int = 22, interval: float = 1.0):
        """Start continuous network monitoring."""
        if self.monitoring_active:
            logger.warning("Network monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_results = []

        def monitor_loop():
            while self.monitoring_active:
                start_time = time.time()

                # Measure latency
                latency = self.measure_actual_latency(host, port, timeout=2.0)

                # Perform quick ping test
                ping_stats = self.ping_test(host, count=1)

                result = NetworkMonitoringResult(
                    timestamp=start_time,
                    latency_ms=latency,
                    packet_loss_percent=ping_stats.get('packet_loss_percent', 0.0),
                    bandwidth_kbps=0.0,  # Would need additional tools to measure
                    jitter_ms=ping_stats.get('stddev_ms', 0.0),
                    connection_successful=latency > 0,
                    error_message=ping_stats.get('error', None)
                )

                self.monitoring_results.append(result)

                # Keep only last 100 results
                if len(self.monitoring_results) > 100:
                    self.monitoring_results = self.monitoring_results[-100:]

                time.sleep(interval)

        monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitoring_thread.start()
        logger.info(f"✅ Started network monitoring ({host}:{port})")

    def stop_network_monitoring(self):
        """Stop network monitoring."""
        self.monitoring_active = False
        logger.info("✅ Stopped network monitoring")

    def get_monitoring_stats(self) -> Dict:
        """Get current monitoring statistics."""
        if not self.monitoring_results:
            return {'error': 'No monitoring data available'}

        recent_results = [r for r in self.monitoring_results if r.connection_successful]

        if not recent_results:
            return {'error': 'No successful connections in monitoring data'}

        latencies = [r.latency_ms for r in recent_results]
        packet_losses = [r.packet_loss_percent for r in recent_results]
        jitters = [r.jitter_ms for r in recent_results]

        return {
            'sample_count': len(recent_results),
            'avg_latency_ms': sum(latencies) / len(latencies),
            'min_latency_ms': min(latencies),
            'max_latency_ms': max(latencies),
            'avg_packet_loss_percent': sum(packet_losses) / len(packet_losses),
            'avg_jitter_ms': sum(jitters) / len(jitters),
            'connection_success_rate': len(recent_results) / len(self.monitoring_results)
        }

    def cleanup(self):
        """Cleanup all network simulation rules."""
        interfaces = self.get_network_interfaces()
        for interface in interfaces:
            self.clear_all_tc_rules(interface)

        self.stop_network_monitoring()
        logger.info("✅ Network simulation cleanup completed")


class TimeoutConfigurationAnalyzer:
    """Analyzes and recommends timeout configurations based on network conditions."""

    def __init__(self):
        self.baseline_measurements = {}
        self.recommendations = {}

    def measure_baseline_performance(self, plc_manager, database) -> Dict:
        """Measure baseline performance without network simulation."""
        logger.info("📊 Measuring baseline performance...")

        baseline = {
            'plc_connection_time_ms': 0,
            'plc_read_time_ms': 0,
            'database_query_time_ms': 0,
            'database_insert_time_ms': 0,
            'total_logging_cycle_time_ms': 0
        }

        try:
            # Measure PLC connection time
            if not plc_manager.is_connected():
                start = time.time()
                success = asyncio.run(plc_manager.initialize())
                if success:
                    baseline['plc_connection_time_ms'] = (time.time() - start) * 1000

            # Measure PLC read time
            if plc_manager.is_connected():
                start = time.time()
                params = asyncio.run(plc_manager.read_all_parameters())
                baseline['plc_read_time_ms'] = (time.time() - start) * 1000

            # Measure database query time
            start = time.time()
            supabase = database.get_supabase()
            result = supabase.table('machines').select('id').limit(1).execute()
            baseline['database_query_time_ms'] = (time.time() - start) * 1000

            # Measure database insert time
            start = time.time()
            test_data = {'parameter_id': 'test', 'value': 123.45, 'timestamp': 'now()'}
            supabase.table('parameter_value_history').insert([test_data]).execute()
            baseline['database_insert_time_ms'] = (time.time() - start) * 1000

            # Calculate total logging cycle time
            baseline['total_logging_cycle_time_ms'] = (
                baseline['plc_read_time_ms'] +
                baseline['database_query_time_ms'] +
                baseline['database_insert_time_ms']
            )

            self.baseline_measurements = baseline
            logger.info(f"📊 Baseline total cycle time: {baseline['total_logging_cycle_time_ms']:.1f}ms")

        except Exception as e:
            logger.error(f"❌ Baseline measurement failed: {e}")

        return baseline

    def calculate_timeout_recommendations(self, network_conditions: List) -> Dict:
        """Calculate timeout recommendations based on network conditions and baseline."""
        if not self.baseline_measurements:
            logger.warning("⚠️ No baseline measurements available")
            return {}

        baseline_total = self.baseline_measurements['total_logging_cycle_time_ms']

        recommendations = {
            'baseline_cycle_time_ms': baseline_total,
            'recommended_timeouts': {},
            'adaptive_strategies': {}
        }

        # For each network condition, calculate appropriate timeouts
        for condition in network_conditions:
            condition_name = condition.name

            # Calculate expected latency impact
            expected_latency_impact = condition.latency_ms * 2  # Round-trip
            if condition.packet_loss_percent > 0:
                # Packet loss increases effective latency due to retries
                expected_latency_impact *= (1 + condition.packet_loss_percent / 100 * 3)

            # Calculate recommended timeouts with safety margins
            recommended_connection_timeout = max(10, (expected_latency_impact + 5000) / 1000)  # At least 10s
            recommended_operation_timeout = max(5, (baseline_total + expected_latency_impact + 2000) / 1000)  # At least 5s
            recommended_retry_delay = max(0.5, expected_latency_impact / 2000)  # At least 0.5s

            recommendations['recommended_timeouts'][condition_name] = {
                'connection_timeout_s': recommended_connection_timeout,
                'operation_timeout_s': recommended_operation_timeout,
                'retry_delay_s': recommended_retry_delay,
                'max_retries': 3 if condition.packet_loss_percent > 10 else 2,
                'expected_cycle_time_ms': baseline_total + expected_latency_impact
            }

            # Adaptive strategies
            if expected_latency_impact > 2000:  # High latency conditions
                recommendations['adaptive_strategies'][condition_name] = [
                    "Increase batch sizes to amortize latency",
                    "Implement connection pooling",
                    "Add circuit breaker pattern",
                    "Consider async/parallel operations",
                    "Implement exponential backoff"
                ]
            elif condition.packet_loss_percent > 20:  # High packet loss
                recommendations['adaptive_strategies'][condition_name] = [
                    "Implement aggressive retry logic",
                    "Add connection health monitoring",
                    "Consider alternative connection paths",
                    "Implement request deduplication"
                ]

        self.recommendations = recommendations
        return recommendations

    def generate_configuration_report(self) -> str:
        """Generate timeout configuration report."""
        if not self.recommendations:
            return "No recommendations available. Run calculate_timeout_recommendations() first."

        report = []
        report.append("⚙️ TIMEOUT CONFIGURATION RECOMMENDATIONS")
        report.append("=" * 60)

        baseline = self.recommendations.get('baseline_cycle_time_ms', 0)
        report.append(f"Baseline logging cycle time: {baseline:.1f}ms")
        report.append("")

        # Current configuration issues
        report.append("🚨 CURRENT CONFIGURATION ISSUES:")
        if baseline > 1000:
            report.append("  ❌ Baseline cycle time exceeds 1-second logging target")
        if baseline > 800:
            report.append("  ⚠️ Little headroom for network latency")
        if baseline < 500:
            report.append("  ✅ Good baseline performance with latency headroom")
        report.append("")

        # Timeout recommendations by condition
        report.append("⏱️ RECOMMENDED TIMEOUT CONFIGURATIONS:")
        for condition_name, timeouts in self.recommendations.get('recommended_timeouts', {}).items():
            report.append(f"  {condition_name}:")
            report.append(f"    Connection timeout: {timeouts['connection_timeout_s']:.1f}s")
            report.append(f"    Operation timeout: {timeouts['operation_timeout_s']:.1f}s")
            report.append(f"    Retry delay: {timeouts['retry_delay_s']:.1f}s")
            report.append(f"    Max retries: {timeouts['max_retries']}")
            report.append(f"    Expected cycle time: {timeouts['expected_cycle_time_ms']:.1f}ms")
            report.append("")

        # Adaptive strategies
        report.append("🔄 ADAPTIVE STRATEGIES:")
        for condition_name, strategies in self.recommendations.get('adaptive_strategies', {}).items():
            report.append(f"  {condition_name}:")
            for strategy in strategies:
                report.append(f"    • {strategy}")
            report.append("")

        # Implementation recommendations
        report.append("🛠️ IMPLEMENTATION RECOMMENDATIONS:")
        report.append("  1. Configuration Management:")
        report.append("     • Make timeouts configurable per network condition")
        report.append("     • Implement runtime timeout adjustment")
        report.append("     • Add timeout monitoring and alerting")
        report.append("")
        report.append("  2. Architectural Improvements:")
        report.append("     • Implement async/await parallel operations")
        report.append("     • Add connection pooling for database")
        report.append("     • Implement circuit breaker patterns")
        report.append("     • Add performance monitoring")
        report.append("")
        report.append("  3. Error Handling:")
        report.append("     • Distinguish timeout vs connection errors")
        report.append("     • Implement exponential backoff")
        report.append("     • Add retry logic with jitter")
        report.append("     • Implement graceful degradation")

        return "\n".join(report)


def main():
    """Main function for testing network simulation utilities."""
    import asyncio
    from src.plc.manager import plc_manager
    from src import db

    # Create simulation manager
    sim_manager = NetworkSimulationManager()
    timeout_analyzer = TimeoutConfigurationAnalyzer()

    logger.info("🧪 Testing Network Simulation Utilities")

    # Check capabilities
    logger.info(f"Root privileges: {sim_manager.check_privileges()}")
    logger.info(f"TC available: {sim_manager.check_tc_availability()}")
    logger.info(f"Network interfaces: {sim_manager.get_network_interfaces()}")

    # Test baseline measurements
    baseline = timeout_analyzer.measure_baseline_performance(plc_manager, db)
    logger.info(f"Baseline measurements: {baseline}")

    # Test simple latency application
    if sim_manager.check_privileges() and sim_manager.check_tc_availability():
        logger.info("🚀 Testing network simulation...")

        # Test 500ms latency
        with sim_manager.network_condition(latency_ms=500, jitter_ms=50) as applied:
            if applied:
                logger.info("Testing under 500ms latency condition...")
                time.sleep(5)

                # Measure actual latency
                actual_latency = sim_manager.measure_actual_latency()
                logger.info(f"Measured latency: {actual_latency:.1f}ms")

    # Cleanup
    sim_manager.cleanup()


if __name__ == "__main__":
    main()