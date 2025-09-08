"""
Real-time command testing framework for command listener functionality.
Tests command processing in a realistic environment with timing constraints.
"""

import asyncio
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from log_setup import logger
from config import MACHINE_ID, CommandStatus
from db import get_supabase
from mock_command_creator import MockCommandCreator
from plc.manager import get_plc_manager
from command_flow.listener import check_pending_commands


class RealTimeCommandTest:
    """Real-time integration test for command listener with actual PLC simulation."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.mock_creator = MockCommandCreator()
        self.plc_manager = None
        self.test_results = {
            "test_start_time": datetime.now().isoformat(),
            "simulation_tests": {},
            "timing_metrics": {},
            "command_flow_tests": {},
            "error_scenarios": {}
        }
        self.active_commands = {}
        self.monitoring_active = False
        
    async def setup_plc_simulation(self):
        """Setup PLC manager in simulation mode."""
        try:
            self.plc_manager = await get_plc_manager()
            logger.info("PLC Manager initialized for real-time testing")
            return True
        except Exception as e:
            logger.error(f"Failed to setup PLC simulation: {str(e)}")
            return False
    
    def start_command_monitoring(self):
        """Start monitoring command status changes in real-time."""
        self.monitoring_active = True
        
        def monitor_commands():
            while self.monitoring_active:
                try:
                    # Check status of active commands
                    for command_id in list(self.active_commands.keys()):
                        result = (
                            self.supabase.table("recipe_commands")
                            .select("status, updated_at, error_message")
                            .eq("id", command_id)
                            .single()
                            .execute()
                        )
                        
                        if result.data:
                            current_status = result.data['status']
                            previous_status = self.active_commands[command_id].get('last_status')
                            
                            if current_status != previous_status:
                                self.active_commands[command_id].update({
                                    'last_status': current_status,
                                    'status_change_time': datetime.now().isoformat(),
                                    'error_message': result.data.get('error_message')
                                })
                                
                                logger.info(f"Command {command_id} status changed: {previous_status} -> {current_status}")
                                
                                # Remove completed/error commands from active monitoring
                                if current_status in [CommandStatus.COMPLETED, CommandStatus.ERROR]:
                                    self.active_commands[command_id]['completed'] = True
                    
                    time.sleep(2)  # Check every 2 seconds
                    
                except Exception as e:
                    logger.error(f"Error in command monitoring: {str(e)}")
                    time.sleep(5)
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_commands, daemon=True)
        monitor_thread.start()
        
    def stop_command_monitoring(self):
        """Stop command monitoring."""
        self.monitoring_active = False
        
    async def test_simulation_command_flow(self) -> bool:
        """Test complete command flow with PLC simulation."""
        test_name = "simulation_command_flow"
        
        try:
            # Create a simple start_recipe command
            test_command = {
                "type": "start_recipe",
                "parameters": {
                    "recipe_id": self.mock_creator.test_recipe_ids[0],
                    "operator_id": "550e8400-e29b-41d4-a716-446655440000",
                    "description": "Real-time simulation test"
                },
                "machine_id": self.mock_creator.test_machine_ids[0],
                "status": "pending"
            }
            
            start_time = time.time()
            command_ids = self.mock_creator.insert_test_commands([test_command])
            
            if not command_ids:
                self.test_results["simulation_tests"][test_name] = {
                    "success": False,
                    "error": "Failed to create test command"
                }
                return False
            
            command_id = command_ids[0]
            
            # Track this command
            self.active_commands[command_id] = {
                "created_at": datetime.now().isoformat(),
                "test_name": test_name,
                "last_status": "pending"
            }
            
            # Simulate command detection and processing
            logger.info(f"Testing command detection for {command_id}")
            
            # Wait for command to be processed or timeout
            timeout = 30  # 30 second timeout
            elapsed = 0
            processed = False
            
            while elapsed < timeout and not processed:
                # Check if command was processed
                result = (
                    self.supabase.table("recipe_commands")
                    .select("status, updated_at")
                    .eq("id", command_id)
                    .single()
                    .execute()
                )
                
                if result.data:
                    status = result.data['status']
                    if status != "pending":
                        processed = True
                        processing_time = time.time() - start_time
                        
                        # Check if process execution was created
                        process_result = (
                            self.supabase.table("process_executions")
                            .select("id, status, recipe_id")
                            .eq("recipe_id", test_command["parameters"]["recipe_id"])
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                        )
                        
                        process_created = len(process_result.data) > 0
                        
                        self.test_results["simulation_tests"][test_name] = {
                            "success": True,
                            "command_id": command_id,
                            "final_status": status,
                            "processing_time_seconds": processing_time,
                            "process_execution_created": process_created,
                            "timeout": False
                        }
                        
                        # Cleanup
                        self.mock_creator.cleanup_test_commands([command_id])
                        return True
                
                await asyncio.sleep(1)
                elapsed += 1
            
            # Timeout case
            self.test_results["simulation_tests"][test_name] = {
                "success": False,
                "command_id": command_id,
                "error": "Command processing timeout",
                "timeout": True,
                "elapsed_seconds": elapsed
            }
            
            # Cleanup
            self.mock_creator.cleanup_test_commands([command_id])
            return False
            
        except Exception as e:
            self.test_results["simulation_tests"][test_name] = {
                "success": False,
                "error": str(e)
            }
            return False
    
    async def test_command_timing_constraints(self) -> bool:
        """Test command processing within timing constraints."""
        test_name = "timing_constraints"
        
        try:
            # Create multiple commands with different complexity
            test_commands = [
                {
                    "type": "set_parameter",
                    "parameters": {"parameter_name": "simple_param", "value": 1.0},
                    "machine_id": self.mock_creator.test_machine_ids[0],
                    "status": "pending"
                },
                {
                    "type": "set_parameter", 
                    "parameters": {"parameter_name": "complex_param", "value": 100.5},
                    "machine_id": self.mock_creator.test_machine_ids[0],
                    "status": "pending"
                }
            ]
            
            timing_results = []
            
            for i, command in enumerate(test_commands):
                start_time = time.time()
                command_ids = self.mock_creator.insert_test_commands([command])
                
                if command_ids:
                    command_id = command_ids[0]
                    
                    # Track command
                    self.active_commands[command_id] = {
                        "created_at": datetime.now().isoformat(),
                        "test_name": f"{test_name}_{i}",
                        "last_status": "pending"
                    }
                    
                    # Wait for processing
                    timeout = 15
                    elapsed = 0
                    
                    while elapsed < timeout:
                        result = (
                            self.supabase.table("recipe_commands")
                            .select("status")
                            .eq("id", command_id)
                            .single()
                            .execute()
                        )
                        
                        if result.data and result.data['status'] != "pending":
                            processing_time = time.time() - start_time
                            timing_results.append({
                                "command_type": command["type"],
                                "parameter_name": command["parameters"].get("parameter_name"),
                                "processing_time_ms": processing_time * 1000,
                                "status": result.data['status'],
                                "within_constraints": processing_time < 10  # 10 second constraint
                            })
                            break
                        
                        await asyncio.sleep(0.5)
                        elapsed += 0.5
                    
                    # Cleanup
                    self.mock_creator.cleanup_test_commands([command_id])
            
            # Analyze timing results
            avg_time = sum(r["processing_time_ms"] for r in timing_results) / len(timing_results) if timing_results else 0
            within_constraints = sum(1 for r in timing_results if r["within_constraints"])
            
            success = within_constraints >= len(timing_results) * 0.8  # 80% must meet constraints
            
            self.test_results["timing_metrics"][test_name] = {
                "success": success,
                "average_processing_time_ms": avg_time,
                "commands_within_constraints": within_constraints,
                "total_commands": len(timing_results),
                "constraint_compliance_percent": (within_constraints / len(timing_results) * 100) if timing_results else 0,
                "individual_results": timing_results
            }
            
            return success
            
        except Exception as e:
            self.test_results["timing_metrics"][test_name] = {
                "success": False,
                "error": str(e)
            }
            return False
    
    async def test_command_queue_processing(self) -> bool:
        """Test processing of queued commands in correct order."""
        test_name = "queue_processing"
        
        try:
            # Create commands with staggered timing
            queue_commands = []
            for i in range(5):
                queue_commands.append({
                    "type": "set_parameter",
                    "parameters": {
                        "parameter_name": f"queue_param_{i}",
                        "value": float(i),
                        "queue_position": i
                    },
                    "machine_id": self.mock_creator.test_machine_ids[0],
                    "status": "pending"
                })
            
            # Insert all commands quickly
            start_time = time.time()
            command_ids = self.mock_creator.insert_test_commands(queue_commands)
            
            if not command_ids:
                self.test_results["command_flow_tests"][test_name] = {
                    "success": False,
                    "error": "Failed to create queue test commands"
                }
                return False
            
            # Track all commands
            for i, command_id in enumerate(command_ids):
                self.active_commands[command_id] = {
                    "created_at": datetime.now().isoformat(),
                    "test_name": f"{test_name}_{i}",
                    "queue_position": i,
                    "last_status": "pending"
                }
            
            # Monitor processing order
            processed_order = []
            timeout = 45
            start_monitor = time.time()
            
            while len(processed_order) < len(command_ids) and (time.time() - start_monitor) < timeout:
                for command_id in command_ids:
                    if command_id not in processed_order:
                        result = (
                            self.supabase.table("recipe_commands")
                            .select("status, updated_at")
                            .eq("id", command_id)
                            .single()
                            .execute()
                        )
                        
                        if result.data and result.data['status'] in [CommandStatus.COMPLETED, CommandStatus.ERROR]:
                            processed_order.append(command_id)
                            logger.info(f"Command processed: {command_id} (position {len(processed_order)})")
                
                await asyncio.sleep(1)
            
            processing_time = time.time() - start_time
            
            # Analyze processing order and timing
            all_processed = len(processed_order) == len(command_ids)
            processing_efficiency = len(processed_order) / len(command_ids) if command_ids else 0
            
            success = all_processed and processing_efficiency >= 0.8
            
            self.test_results["command_flow_tests"][test_name] = {
                "success": success,
                "total_commands": len(command_ids),
                "processed_commands": len(processed_order),
                "processing_efficiency_percent": processing_efficiency * 100,
                "total_processing_time_seconds": processing_time,
                "average_time_per_command_ms": (processing_time / len(processed_order) * 1000) if processed_order else 0
            }
            
            # Cleanup
            self.mock_creator.cleanup_test_commands(command_ids)
            return success
            
        except Exception as e:
            self.test_results["command_flow_tests"][test_name] = {
                "success": False,
                "error": str(e)
            }
            return False
    
    async def test_error_recovery_scenarios(self) -> bool:
        """Test error handling and recovery scenarios."""
        test_name = "error_recovery"
        
        try:
            # Create commands that should fail
            error_commands = [
                {
                    "type": "start_recipe",
                    "parameters": {"recipe_id": "00000000-0000-0000-0000-000000000000"},  # Invalid recipe
                    "machine_id": self.mock_creator.test_machine_ids[0],
                    "status": "pending"
                },
                {
                    "type": "invalid_command_type",
                    "parameters": {"test": "value"},
                    "machine_id": self.mock_creator.test_machine_ids[0], 
                    "status": "pending"
                }
            ]
            
            error_results = []
            
            for i, command in enumerate(error_commands):
                command_ids = self.mock_creator.insert_test_commands([command])
                
                if command_ids:
                    command_id = command_ids[0]
                    
                    # Wait for error handling
                    timeout = 20
                    elapsed = 0
                    
                    while elapsed < timeout:
                        result = (
                            self.supabase.table("recipe_commands")
                            .select("status, error_message")
                            .eq("id", command_id)
                            .single()
                            .execute()
                        )
                        
                        if result.data:
                            status = result.data['status']
                            error_message = result.data.get('error_message')
                            
                            if status == CommandStatus.ERROR:
                                error_results.append({
                                    "command_id": command_id,
                                    "handled_gracefully": True,
                                    "has_error_message": bool(error_message),
                                    "error_message": error_message,
                                    "response_time_seconds": elapsed
                                })
                                break
                            elif status != "pending":
                                error_results.append({
                                    "command_id": command_id,
                                    "handled_gracefully": False,
                                    "unexpected_status": status,
                                    "response_time_seconds": elapsed
                                })
                                break
                        
                        await asyncio.sleep(1)
                        elapsed += 1
                    
                    # Cleanup
                    self.mock_creator.cleanup_test_commands([command_id])
            
            # Analyze error handling
            gracefully_handled = sum(1 for r in error_results if r.get("handled_gracefully", False))
            avg_response_time = sum(r["response_time_seconds"] for r in error_results) / len(error_results) if error_results else 0
            
            success = gracefully_handled >= len(error_commands) * 0.8  # 80% should be handled gracefully
            
            self.test_results["error_scenarios"][test_name] = {
                "success": success,
                "total_error_commands": len(error_commands),
                "gracefully_handled": gracefully_handled,
                "average_response_time_seconds": avg_response_time,
                "error_handling_rate_percent": (gracefully_handled / len(error_commands) * 100) if error_commands else 0,
                "detailed_results": error_results
            }
            
            return success
            
        except Exception as e:
            self.test_results["error_scenarios"][test_name] = {
                "success": False,
                "error": str(e)
            }
            return False
    
    async def run_real_time_test_suite(self) -> Dict[str, Any]:
        """Run complete real-time test suite."""
        logger.info("Starting real-time command listener test suite...")
        
        # Setup PLC simulation
        plc_setup = await self.setup_plc_simulation()
        if not plc_setup:
            logger.warning("PLC setup failed, continuing with database-only tests")
        
        # Start command monitoring
        self.start_command_monitoring()
        
        try:
            # Run all real-time tests
            test_functions = [
                self.test_simulation_command_flow,
                self.test_command_timing_constraints,
                self.test_command_queue_processing,
                self.test_error_recovery_scenarios
            ]
            
            test_results = {}
            
            for test_func in test_functions:
                test_name = test_func.__name__
                logger.info(f"Running real-time test: {test_name}")
                
                try:
                    result = await test_func()
                    test_results[test_name] = result
                    
                    # Small delay between tests
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Test {test_name} failed: {str(e)}")
                    test_results[test_name] = False
            
            # Calculate overall results
            passed_tests = sum(1 for result in test_results.values() if result)
            total_tests = len(test_results)
            success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            self.test_results.update({
                "test_end_time": datetime.now().isoformat(),
                "plc_simulation_available": plc_setup,
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": total_tests - passed_tests,
                    "success_rate_percent": success_rate
                },
                "individual_results": test_results
            })
            
            logger.info(f"Real-time test suite complete. Success rate: {success_rate:.1f}%")
            return self.test_results
            
        finally:
            self.stop_command_monitoring()
    
    def generate_real_time_report(self) -> str:
        """Generate comprehensive real-time test report."""
        report = f"""
# Real-Time Command Listener Test Report

## Test Summary
- **Test Start**: {self.test_results.get('test_start_time', 'N/A')}
- **Test End**: {self.test_results.get('test_end_time', 'N/A')}
- **PLC Simulation Available**: {self.test_results.get('plc_simulation_available', False)}
- **Total Tests**: {self.test_results.get('summary', {}).get('total_tests', 0)}
- **Passed Tests**: {self.test_results.get('summary', {}).get('passed_tests', 0)}
- **Failed Tests**: {self.test_results.get('summary', {}).get('failed_tests', 0)}
- **Success Rate**: {self.test_results.get('summary', {}).get('success_rate_percent', 0):.1f}%

## Simulation Tests
"""
        
        for test_name, test_data in self.test_results.get("simulation_tests", {}).items():
            status = "✅ PASSED" if test_data.get("success", False) else "❌ FAILED"
            report += f"\n### {test_name}\n"
            report += f"- **Status**: {status}\n"
            if test_data.get("processing_time_seconds"):
                report += f"- **Processing Time**: {test_data['processing_time_seconds']:.2f}s\n"
            if test_data.get("error"):
                report += f"- **Error**: {test_data['error']}\n"
        
        # Timing metrics
        report += f"\n## Timing Metrics\n"
        for test_name, test_data in self.test_results.get("timing_metrics", {}).items():
            status = "✅ PASSED" if test_data.get("success", False) else "❌ FAILED"
            report += f"\n### {test_name}\n"
            report += f"- **Status**: {status}\n"
            if test_data.get("average_processing_time_ms"):
                report += f"- **Average Processing Time**: {test_data['average_processing_time_ms']:.2f}ms\n"
            if test_data.get("constraint_compliance_percent"):
                report += f"- **Constraint Compliance**: {test_data['constraint_compliance_percent']:.1f}%\n"
        
        # Command flow tests
        report += f"\n## Command Flow Tests\n"
        for test_name, test_data in self.test_results.get("command_flow_tests", {}).items():
            status = "✅ PASSED" if test_data.get("success", False) else "❌ FAILED"
            report += f"\n### {test_name}\n"
            report += f"- **Status**: {status}\n"
            if test_data.get("processing_efficiency_percent"):
                report += f"- **Processing Efficiency**: {test_data['processing_efficiency_percent']:.1f}%\n"
        
        # Error scenarios
        report += f"\n## Error Recovery Tests\n"
        for test_name, test_data in self.test_results.get("error_scenarios", {}).items():
            status = "✅ PASSED" if test_data.get("success", False) else "❌ FAILED"
            report += f"\n### {test_name}\n"
            report += f"- **Status**: {status}\n"
            if test_data.get("error_handling_rate_percent"):
                report += f"- **Error Handling Rate**: {test_data['error_handling_rate_percent']:.1f}%\n"
        
        return report


async def main():
    """Run the real-time command test suite."""
    test_runner = RealTimeCommandTest()
    
    print("Starting Real-Time Command Listener Test Suite...")
    print("=" * 60)
    
    # Run real-time tests
    results = await test_runner.run_real_time_test_suite()
    
    # Generate and save report
    report = test_runner.generate_real_time_report()
    
    # Save results to files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON results
    results_filename = f"real_time_command_test_results_{timestamp}.json"
    with open(results_filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save markdown report
    report_filename = f"real_time_command_test_report_{timestamp}.md"
    with open(report_filename, 'w') as f:
        f.write(report)
    
    print(f"\nReal-Time Test Results Summary:")
    print(f"Success Rate: {results.get('summary', {}).get('success_rate_percent', 0):.1f}%")
    print(f"Results saved to: {results_filename}")
    print(f"Report saved to: {report_filename}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())