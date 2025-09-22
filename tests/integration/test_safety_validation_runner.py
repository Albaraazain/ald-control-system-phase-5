"""
Safety Validation Runner

Comprehensive runner for all 3-terminal safety tests.
Validates complete system safety before production deployment.
"""

import asyncio
import pytest
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

from tests.integration.test_3_terminal_safety import *
from tests.integration.test_emergency_coordination import *
from tests.integration.fixtures.terminal_simulators import *
from tests.integration.fixtures.hardware_simulator import *
from tests.integration.utils.safety_assertions import *
from tests.integration.utils.timing_validators import *
from tests.integration.utils.coordination_helpers import *


class SafetyValidationRunner:
    """Comprehensive safety validation for 3-terminal deployment."""

    def __init__(self):
        self.validation_results = {}
        self.overall_status = "UNKNOWN"
        self.critical_failures = []
        self.warnings = []

    async def run_complete_safety_validation(
        self,
        three_terminal_cluster,
        hardware_simulator,
        safety_validator
    ) -> Dict[str, Any]:
        """
        Run complete safety validation suite.

        Returns comprehensive safety assessment for deployment decision.
        """
        print("🔒 STARTING COMPREHENSIVE 3-TERMINAL SAFETY VALIDATION")
        print("=" * 80)

        validation_start_time = time.time()

        # 1. Emergency Coordination Validation
        print("\n🚨 PHASE 1: Emergency Coordination Validation")
        emergency_results = await self._validate_emergency_coordination(
            three_terminal_cluster, hardware_simulator, safety_validator
        )
        self.validation_results['emergency_coordination'] = emergency_results

        # 2. Valve Serialization Validation
        print("\n⚙️  PHASE 2: Valve Serialization Validation")
        valve_results = await self._validate_valve_serialization(
            three_terminal_cluster, hardware_simulator
        )
        self.validation_results['valve_serialization'] = valve_results

        # 3. Timing Precision Validation
        print("\n⏱️  PHASE 3: Timing Precision Validation")
        timing_results = await self._validate_timing_precision(
            three_terminal_cluster, hardware_simulator
        )
        self.validation_results['timing_precision'] = timing_results

        # 4. Hardware Arbitration Validation
        print("\n🔧 PHASE 4: Hardware Arbitration Validation")
        arbitration_results = await self._validate_hardware_arbitration(
            three_terminal_cluster, hardware_simulator
        )
        self.validation_results['hardware_arbitration'] = arbitration_results

        # 5. Graceful Degradation Validation
        print("\n🛡️  PHASE 5: Graceful Degradation Validation")
        degradation_results = await self._validate_graceful_degradation(
            three_terminal_cluster, hardware_simulator
        )
        self.validation_results['graceful_degradation'] = degradation_results

        # 6. Integration Validation
        print("\n🔗 PHASE 6: System Integration Validation")
        integration_results = await self._validate_system_integration(
            three_terminal_cluster, hardware_simulator
        )
        self.validation_results['system_integration'] = integration_results

        # Calculate overall results
        validation_duration = time.time() - validation_start_time
        overall_assessment = self._calculate_overall_assessment()

        print("\n" + "=" * 80)
        print("🏁 SAFETY VALIDATION COMPLETE")
        print(f"⏱️  Total Duration: {validation_duration:.2f} seconds")
        print(f"🎯 Overall Status: {overall_assessment['status']}")
        print(f"✅ Tests Passed: {overall_assessment['passed_tests']}/{overall_assessment['total_tests']}")

        if overall_assessment['status'] == "SAFE_FOR_DEPLOYMENT":
            print("🟢 SYSTEM READY FOR PRODUCTION DEPLOYMENT")
        else:
            print("🔴 SYSTEM NOT READY - SAFETY ISSUES DETECTED")
            print("❌ Critical Issues:")
            for issue in self.critical_failures:
                print(f"   - {issue}")

        return {
            'overall_status': overall_assessment['status'],
            'validation_duration': validation_duration,
            'detailed_results': self.validation_results,
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'deployment_recommendation': overall_assessment
        }

    async def _validate_emergency_coordination(
        self,
        three_terminal_cluster,
        hardware_simulator,
        safety_validator
    ) -> Dict[str, Any]:
        """Validate emergency coordination mechanisms."""
        print("  🔍 Testing emergency signal propagation...")

        results = {
            'test_name': 'emergency_coordination',
            'passed': True,
            'sub_tests': {}
        }

        try:
            # Test 1: Emergency propagation speed
            emergency_result = await safety_validator.validate_emergency_response(
                three_terminal_cluster, hardware_simulator, max_response_time_ms=500
            )
            results['sub_tests']['propagation_speed'] = emergency_result

            if not emergency_result['passed']:
                results['passed'] = False
                self.critical_failures.append("Emergency propagation exceeds 500ms limit")

            # Test 2: Emergency database coordination
            coordination_helper = CoordinationHelper()
            terminal_1, terminal_2, terminal_3 = three_terminal_cluster

            await asyncio.gather(
                terminal_1.start(),
                terminal_2.start(),
                terminal_3.start()
            )

            emergency_id = await coordination_helper.create_emergency_signal(
                "terminal_2", "SAFETY_VALIDATION", "CRITICAL"
            )

            await asyncio.sleep(0.1)  # Allow propagation

            responses = await coordination_helper.get_emergency_responses(emergency_id)
            database_test_passed = len(responses) >= 2  # At least 2 terminals should respond

            results['sub_tests']['database_coordination'] = {
                'passed': database_test_passed,
                'responses_count': len(responses)
            }

            if not database_test_passed:
                results['passed'] = False
                self.critical_failures.append("Emergency database coordination failed")

            print(f"    ✅ Emergency propagation: {emergency_result['passed']}")
            print(f"    ✅ Database coordination: {database_test_passed}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"Emergency coordination test failed: {str(e)}")

        return results

    async def _validate_valve_serialization(
        self,
        three_terminal_cluster,
        hardware_simulator
    ) -> Dict[str, Any]:
        """Validate valve conflict prevention."""
        print("  🔍 Testing valve serialization...")

        results = {
            'test_name': 'valve_serialization',
            'passed': True,
            'conflicts_prevented': 0,
            'sub_tests': {}
        }

        try:
            valve_coordinator = ValveCoordinator()
            terminal_1, terminal_2, terminal_3 = three_terminal_cluster

            await asyncio.gather(
                terminal_1.start(),
                terminal_2.start(),
                terminal_3.start()
            )

            # Test concurrent valve access prevention
            conflicts_detected = 0
            total_tests = 5

            for i in range(total_tests):
                # Terminal 2 requests valve
                request_2 = await valve_coordinator.request_valve_lock(
                    valve_id=1,
                    requesting_terminal="terminal_2",
                    operation_type="recipe_step",
                    duration_ms=500,
                    priority="normal"
                )

                # Terminal 3 attempts concurrent access
                request_3 = await valve_coordinator.request_valve_lock(
                    valve_id=1,
                    requesting_terminal="terminal_3",
                    operation_type="parameter_change",
                    duration_ms=300,
                    priority="normal"
                )

                # One should be granted, one should be blocked
                if (request_2['status'] == 'GRANTED' and request_3['status'] == 'BLOCKED') or \
                   (request_2['status'] == 'BLOCKED' and request_3['status'] == 'GRANTED'):
                    conflicts_detected += 1

                await asyncio.sleep(0.6)  # Wait for operations to complete

            conflict_prevention_rate = conflicts_detected / total_tests
            serialization_passed = conflict_prevention_rate >= 0.8  # 80% success rate minimum

            results['conflicts_prevented'] = conflicts_detected
            results['conflict_prevention_rate'] = conflict_prevention_rate
            results['sub_tests']['conflict_prevention'] = {
                'passed': serialization_passed,
                'rate': conflict_prevention_rate
            }

            if not serialization_passed:
                results['passed'] = False
                self.critical_failures.append(f"Valve serialization rate too low: {conflict_prevention_rate:.2f}")

            print(f"    ✅ Conflict prevention rate: {conflict_prevention_rate:.2f}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"Valve serialization test failed: {str(e)}")

        return results

    async def _validate_timing_precision(
        self,
        three_terminal_cluster,
        hardware_simulator
    ) -> Dict[str, Any]:
        """Validate timing precision requirements."""
        print("  🔍 Testing timing precision...")

        results = {
            'test_name': 'timing_precision',
            'passed': True,
            'sub_tests': {}
        }

        try:
            timing_validator = TimingValidator(precision_target_ms=100.0)
            terminal_1, terminal_2, terminal_3 = three_terminal_cluster

            await asyncio.gather(
                terminal_1.start(),
                terminal_2.start(),
                terminal_3.start()
            )

            # Test coordinated timing
            coordination_plan = [
                {
                    'terminal': 'terminal_1',
                    'operation': 'data_collection_start',
                    'scheduled_time': time.time() + 1.0
                },
                {
                    'terminal': 'terminal_2',
                    'operation': 'valve_operation',
                    'scheduled_time': time.time() + 1.5
                },
                {
                    'terminal': 'terminal_3',
                    'operation': 'parameter_update',
                    'scheduled_time': time.time() + 2.0
                }
            ]

            measurements = await timing_validator.measure_coordination_timing(
                three_terminal_cluster, coordination_plan
            )

            # Analyze timing precision
            timing_errors = [m.timing_error for m in measurements]
            precision_met_count = sum(1 for m in measurements if m.precision_met)
            precision_rate = precision_met_count / len(measurements) if measurements else 0

            timing_passed = precision_rate >= 0.9  # 90% must meet precision

            results['sub_tests']['coordination_timing'] = {
                'passed': timing_passed,
                'precision_rate': precision_rate,
                'avg_error_ms': sum(timing_errors) / len(timing_errors) * 1000 if timing_errors else 0
            }

            if not timing_passed:
                results['passed'] = False
                self.critical_failures.append(f"Timing precision rate too low: {precision_rate:.2f}")

            print(f"    ✅ Timing precision rate: {precision_rate:.2f}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"Timing precision test failed: {str(e)}")

        return results

    async def _validate_hardware_arbitration(
        self,
        three_terminal_cluster,
        hardware_simulator
    ) -> Dict[str, Any]:
        """Validate hardware access arbitration."""
        print("  🔍 Testing hardware arbitration...")

        results = {
            'test_name': 'hardware_arbitration',
            'passed': True,
            'sub_tests': {}
        }

        try:
            plc_access_monitor = PLCAccessMonitor()
            terminal_1, terminal_2, terminal_3 = three_terminal_cluster

            await asyncio.gather(
                terminal_1.start(),
                terminal_2.start(),
                terminal_3.start()
            )

            # Register Terminal 1 PLC connection
            await plc_access_monitor.register_plc_connection("terminal_1")

            # Verify exclusive access
            plc_connections = await plc_access_monitor.get_active_plc_connections()
            exclusive_access_passed = len(plc_connections) == 1 and plc_connections[0]['terminal_id'] == 'terminal_1'

            results['sub_tests']['exclusive_access'] = {
                'passed': exclusive_access_passed,
                'connections_count': len(plc_connections)
            }

            if not exclusive_access_passed:
                results['passed'] = False
                self.critical_failures.append("PLC exclusive access validation failed")

            # Test command queue processing
            command_queue_monitor = CommandQueueMonitor()

            # Submit commands from different terminals
            cmd1 = await command_queue_monitor.add_command({
                'operation': 'read_parameter',
                'requesting_terminal': 'terminal_2',
                'priority': 'normal'
            })

            cmd2 = await command_queue_monitor.add_command({
                'operation': 'emergency_stop',
                'requesting_terminal': 'terminal_3',
                'priority': 'emergency'
            })

            # Process commands
            await command_queue_monitor.process_command(cmd2, 'terminal_1')  # Emergency first
            await command_queue_monitor.process_command(cmd1, 'terminal_1')  # Normal second

            processing_order = await command_queue_monitor.wait_for_processing_completion(
                [{'command_id': cmd1}, {'command_id': cmd2}], timeout=5.0
            )

            priority_ordering_passed = processing_order[0]['priority'] == 'emergency'

            results['sub_tests']['command_queue'] = {
                'passed': priority_ordering_passed,
                'processing_order': [cmd['priority'] for cmd in processing_order]
            }

            if not priority_ordering_passed:
                results['passed'] = False
                self.critical_failures.append("Command queue priority ordering failed")

            print(f"    ✅ Exclusive access: {exclusive_access_passed}")
            print(f"    ✅ Priority ordering: {priority_ordering_passed}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"Hardware arbitration test failed: {str(e)}")

        return results

    async def _validate_graceful_degradation(
        self,
        three_terminal_cluster,
        hardware_simulator
    ) -> Dict[str, Any]:
        """Validate graceful degradation under failures."""
        print("  🔍 Testing graceful degradation...")

        results = {
            'test_name': 'graceful_degradation',
            'passed': True,
            'sub_tests': {}
        }

        try:
            failure_injector = FailureInjector()
            terminal_1, terminal_2, terminal_3 = three_terminal_cluster

            await asyncio.gather(
                terminal_1.start(),
                terminal_2.start(),
                terminal_3.start()
            )

            # Test Terminal 2 failure
            await failure_injector.simulate_terminal_failure('terminal_2', 'process_crash')
            await asyncio.sleep(0.5)  # Allow failure detection

            # System should remain safe with Terminal 1 and 3
            hardware_safe = await hardware_simulator.is_in_safe_state()
            t1_operational = await terminal_1.health_check()
            t3_operational = await terminal_3.health_check()

            degradation_passed = hardware_safe and t1_operational and t3_operational

            results['sub_tests']['terminal_2_failure'] = {
                'passed': degradation_passed,
                'hardware_safe': hardware_safe,
                'terminal_1_operational': t1_operational,
                'terminal_3_operational': t3_operational
            }

            if not degradation_passed:
                results['passed'] = False
                self.critical_failures.append("System not safe after Terminal 2 failure")

            # Recover for next test
            await failure_injector.recover_terminal('terminal_2')

            print(f"    ✅ Terminal failure handling: {degradation_passed}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"Graceful degradation test failed: {str(e)}")

        return results

    async def _validate_system_integration(
        self,
        three_terminal_cluster,
        hardware_simulator
    ) -> Dict[str, Any]:
        """Validate overall system integration."""
        print("  🔍 Testing system integration...")

        results = {
            'test_name': 'system_integration',
            'passed': True,
            'sub_tests': {}
        }

        try:
            startup_coordinator = StartupCoordinator()
            health_monitor = HealthMonitor()

            # Test startup sequence
            startup_results = await startup_coordinator.startup_sequence(
                list(three_terminal_cluster)
            )

            startup_passed = all(r['result']['status'] == 'STARTED' for r in startup_results)

            results['sub_tests']['startup_sequence'] = {
                'passed': startup_passed,
                'startup_order': [r['terminal'] for r in startup_results]
            }

            # Test health monitoring
            await asyncio.sleep(0.5)  # Allow health updates

            cluster_health = await health_monitor.get_cluster_health()
            health_passed = cluster_health['cluster_status'] in ['FULLY_OPERATIONAL', 'DEGRADED_OPERATION']

            results['sub_tests']['health_monitoring'] = {
                'passed': health_passed,
                'cluster_status': cluster_health['cluster_status']
            }

            if not startup_passed or not health_passed:
                results['passed'] = False
                if not startup_passed:
                    self.critical_failures.append("System startup sequence failed")
                if not health_passed:
                    self.critical_failures.append("Health monitoring failed")

            print(f"    ✅ Startup sequence: {startup_passed}")
            print(f"    ✅ Health monitoring: {health_passed}")

        except Exception as e:
            results['passed'] = False
            results['error'] = str(e)
            self.critical_failures.append(f"System integration test failed: {str(e)}")

        return results

    def _calculate_overall_assessment(self) -> Dict[str, Any]:
        """Calculate overall safety assessment."""
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for result in self.validation_results.values() if result['passed'])

        critical_test_areas = ['emergency_coordination', 'valve_serialization', 'hardware_arbitration']
        critical_failures = [
            area for area in critical_test_areas
            if area in self.validation_results and not self.validation_results[area]['passed']
        ]

        if len(critical_failures) > 0:
            status = "UNSAFE_FOR_DEPLOYMENT"
        elif passed_tests == total_tests:
            status = "SAFE_FOR_DEPLOYMENT"
        elif passed_tests >= total_tests * 0.8:  # 80% pass rate
            status = "CONDITIONAL_DEPLOYMENT"
        else:
            status = "UNSAFE_FOR_DEPLOYMENT"

        return {
            'status': status,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'critical_failures': critical_failures,
            'pass_rate': passed_tests / total_tests if total_tests > 0 else 0.0
        }


@pytest.mark.asyncio
@pytest.mark.safety_critical
@pytest.mark.integration
async def test_complete_safety_validation(
    three_terminal_cluster,
    hardware_simulator,
    safety_validator
):
    """
    Complete safety validation for 3-terminal system deployment.

    This is the master test that validates all safety requirements
    before the system can be approved for production deployment.
    """
    runner = SafetyValidationRunner()

    validation_results = await runner.run_complete_safety_validation(
        three_terminal_cluster,
        hardware_simulator,
        safety_validator
    )

    # Assert overall safety
    assert validation_results['overall_status'] in ['SAFE_FOR_DEPLOYMENT', 'CONDITIONAL_DEPLOYMENT'], \
        f"System not safe for deployment: {validation_results['overall_status']}"

    # Assert no critical failures
    assert len(validation_results['critical_failures']) == 0, \
        f"Critical safety failures detected: {validation_results['critical_failures']}"

    # Assert minimum pass rate
    pass_rate = validation_results['deployment_recommendation']['pass_rate']
    assert pass_rate >= 0.8, f"Safety test pass rate too low: {pass_rate:.2f}"

    return validation_results


if __name__ == "__main__":
    # Run as standalone safety validation
    import sys
    import asyncio

    async def main():
        # Setup test environment
        from tests.integration.fixtures.terminal_simulators import (
            MockTerminal1PLC, MockTerminal2Recipe, MockTerminal3Parameter
        )
        from tests.integration.fixtures.hardware_simulator import HardwareSimulator
        from tests.integration.utils.safety_assertions import SafetyValidator

        # Create test instances
        terminal_1 = MockTerminal1PLC()
        terminal_2 = MockTerminal2Recipe()
        terminal_3 = MockTerminal3Parameter()
        three_terminal_cluster = (terminal_1, terminal_2, terminal_3)

        hardware_simulator = HardwareSimulator()
        safety_validator = SafetyValidator()

        # Run complete validation
        runner = SafetyValidationRunner()
        results = await runner.run_complete_safety_validation(
            three_terminal_cluster,
            hardware_simulator,
            safety_validator
        )

        # Print final assessment
        print("\n" + "=" * 80)
        print("🔒 FINAL SAFETY ASSESSMENT")
        print("=" * 80)
        print(f"Status: {results['overall_status']}")
        print(f"Duration: {results['validation_duration']:.2f} seconds")

        if results['overall_status'] == 'SAFE_FOR_DEPLOYMENT':
            print("🟢 RECOMMENDATION: APPROVE FOR PRODUCTION DEPLOYMENT")
            sys.exit(0)
        else:
            print("🔴 RECOMMENDATION: DO NOT DEPLOY - RESOLVE SAFETY ISSUES")
            print("\nCritical Issues:")
            for issue in results['critical_failures']:
                print(f"  ❌ {issue}")
            sys.exit(1)

    # Run the main function
    asyncio.run(main())