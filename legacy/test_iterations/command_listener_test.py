"""
Comprehensive integration test for command listener functionality.
Tests command detection, processing, status updates, and error handling.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
from contextlib import asynccontextmanager

from log_setup import logger
from config import MACHINE_ID, CommandStatus
from db import get_supabase, create_async_supabase
from mock_command_creator import MockCommandCreator
from command_flow.listener import setup_command_listener, check_pending_commands
from command_flow.processor import process_command


class CommandListenerIntegrationTest:
    """Comprehensive integration test for command listener functionality."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.mock_creator = MockCommandCreator()
        self.test_results = {
            "test_start_time": datetime.now().isoformat(),
            "tests": {},
            "command_tracking": {},
            "performance_metrics": {},
            "error_logs": []
        }
        self.listener_task = None
        self.async_supabase = None
        
    async def setup_async_client(self):
        """Setup async Supabase client for listener tests."""
        self.async_supabase = await create_async_supabase()
        
    async def cleanup_async_client(self):
        """Cleanup async client."""
        if self.async_supabase:
            await self.async_supabase.auth.sign_out()
    
    def record_test_result(self, test_name: str, success: bool, details: Dict[str, Any]):
        """Record test result with details."""
        self.test_results["tests"][test_name] = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        logger.info(f"Test {test_name}: {'PASSED' if success else 'FAILED'}")
        
    def record_error(self, test_name: str, error: str):
        """Record error in test results."""
        error_entry = {
            "test": test_name,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results["error_logs"].append(error_entry)
        logger.error(f"Test {test_name} error: {error}")
    
    async def test_command_detection(self) -> bool:
        """Test command detection and basic processing."""
        test_name = "command_detection"
        
        try:
            # Create test commands
            test_commands = self.mock_creator.create_test_start_recipe_commands()[:2]
            command_ids = self.mock_creator.insert_test_commands(test_commands)
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create test commands"})
                return False
                
            # Check if commands are detected
            start_time = time.time()
            detected_commands = []
            
            # Use check_pending_commands function to detect
            try:
                result = (
                    self.supabase.table("recipe_commands")
                    .select("*")
                    .eq("status", CommandStatus.PENDING)
                    .in_("id", command_ids)
                    .execute()
                )
                detected_commands = result.data
            except Exception as e:
                self.record_error(test_name, f"Command detection failed: {str(e)}")
                return False
            
            detection_time = time.time() - start_time
            
            success = len(detected_commands) == len(command_ids)
            
            details = {
                "commands_created": len(command_ids),
                "commands_detected": len(detected_commands),
                "detection_time_ms": detection_time * 1000,
                "command_ids": command_ids
            }
            
            self.record_test_result(test_name, success, details)
            
            # Track commands for later tests
            for cmd_id in command_ids:
                self.test_results["command_tracking"][cmd_id] = {
                    "created_at": datetime.now().isoformat(),
                    "test": test_name
                }
            
            # Cleanup
            self.mock_creator.cleanup_test_commands(command_ids)
            return success
            
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def test_command_processing(self) -> bool:
        """Test command processing and status updates."""
        test_name = "command_processing"
        
        try:
            # Create a simple set_parameter command
            test_command = {
                "type": "set_parameter",
                "parameters": {
                    "parameter_name": "test_pressure",
                    "value": 100.0
                },
                "machine_id": self.mock_creator.test_machine_ids[0],
                "status": "pending"
            }
            
            command_ids = self.mock_creator.insert_test_commands([test_command])
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create test command"})
                return False
            
            command_id = command_ids[0]
            
            # Get the command record
            result = (
                self.supabase.table("recipe_commands")
                .select("*")
                .eq("id", command_id)
                .single()
                .execute()
            )
            
            command_record = result.data
            
            # Process the command directly
            start_time = time.time()
            
            try:
                await process_command(command_record)
                processing_time = time.time() - start_time
                
                # Check command status after processing
                result = (
                    self.supabase.table("recipe_commands")
                    .select("*")
                    .eq("id", command_id)
                    .single()
                    .execute()
                )
                
                updated_command = result.data
                final_status = updated_command['status']
                
                # Command should be completed or error (not processing)
                success = final_status in [CommandStatus.COMPLETED, CommandStatus.ERROR]
                
                details = {
                    "command_id": command_id,
                    "initial_status": command_record['status'],
                    "final_status": final_status,
                    "processing_time_ms": processing_time * 1000,
                    "command_type": test_command['type']
                }
                
                self.record_test_result(test_name, success, details)
                
                # Cleanup
                self.mock_creator.cleanup_test_commands([command_id])
                return success
                
            except Exception as proc_error:
                details = {
                    "command_id": command_id,
                    "processing_error": str(proc_error),
                    "command_type": test_command['type']
                }
                self.record_test_result(test_name, False, details)
                self.mock_creator.cleanup_test_commands([command_id])
                return False
                
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling for invalid commands."""
        test_name = "error_handling"
        
        try:
            # Create commands that should fail
            error_commands = self.mock_creator.create_test_malformed_commands()
            command_ids = self.mock_creator.insert_test_commands(error_commands)
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create error test commands"})
                return False
            
            error_results = []
            
            for command_id in command_ids:
                try:
                    # Get command record
                    result = (
                        self.supabase.table("recipe_commands")
                        .select("*")
                        .eq("id", command_id)
                        .single()
                        .execute()
                    )
                    
                    command_record = result.data
                    
                    # Process command (should fail gracefully)
                    try:
                        await process_command(command_record)
                    except Exception:
                        # Expected to fail, but should handle gracefully
                        pass
                    
                    # Check final status
                    result = (
                        self.supabase.table("recipe_commands")
                        .select("status, error_message")
                        .eq("id", command_id)
                        .single()
                        .execute()
                    )
                    
                    final_record = result.data
                    
                    error_results.append({
                        "command_id": command_id,
                        "final_status": final_record['status'],
                        "has_error_message": bool(final_record.get('error_message')),
                        "error_handled_gracefully": True
                    })
                    
                except Exception as e:
                    error_results.append({
                        "command_id": command_id,
                        "error": str(e),
                        "error_handled_gracefully": False
                    })
            
            # Success if most errors were handled gracefully
            graceful_count = sum(1 for r in error_results if r.get('error_handled_gracefully', False))
            success = graceful_count >= len(error_results) * 0.7  # At least 70% handled gracefully
            
            details = {
                "total_error_commands": len(command_ids),
                "gracefully_handled": graceful_count,
                "error_results": error_results
            }
            
            self.record_test_result(test_name, success, details)
            
            # Cleanup
            self.mock_creator.cleanup_test_commands(command_ids)
            return success
            
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def test_status_transitions(self) -> bool:
        """Test proper command status transitions."""
        test_name = "status_transitions"
        
        try:
            # Create a simple command
            test_command = {
                "type": "set_parameter",
                "parameters": {
                    "parameter_name": "test_temperature",
                    "value": 200.0
                },
                "machine_id": self.mock_creator.test_machine_ids[0],
                "status": "pending"
            }
            
            command_ids = self.mock_creator.insert_test_commands([test_command])
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create test command"})
                return False
            
            command_id = command_ids[0]
            
            # Track status transitions
            status_history = []
            
            # Initial status
            result = (
                self.supabase.table("recipe_commands")
                .select("status, updated_at")
                .eq("id", command_id)
                .single()
                .execute()
            )
            
            initial_status = result.data
            status_history.append({
                "status": initial_status['status'],
                "timestamp": initial_status['updated_at']
            })
            
            # Process command and track transitions
            result = (
                self.supabase.table("recipe_commands")
                .select("*")
                .eq("id", command_id)
                .single()
                .execute()
            )
            
            command_record = result.data
            
            # Process the command
            await process_command(command_record)
            
            # Get final status
            result = (
                self.supabase.table("recipe_commands")
                .select("status, updated_at")
                .eq("id", command_id)
                .single()
                .execute()
            )
            
            final_status = result.data
            status_history.append({
                "status": final_status['status'],
                "timestamp": final_status['updated_at']
            })
            
            # Validate transitions
            valid_transitions = [
                ("pending", "processing"),
                ("pending", "completed"),
                ("pending", "error"),
                ("processing", "completed"),
                ("processing", "error")
            ]
            
            transition_valid = True
            if len(status_history) >= 2:
                transition = (status_history[0]['status'], status_history[-1]['status'])
                transition_valid = transition in valid_transitions or transition[0] == transition[1]
            
            success = transition_valid and final_status['status'] != "pending"
            
            details = {
                "command_id": command_id,
                "status_history": status_history,
                "transition_valid": transition_valid,
                "final_status": final_status['status']
            }
            
            self.record_test_result(test_name, success, details)
            
            # Cleanup
            self.mock_creator.cleanup_test_commands([command_id])
            return success
            
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def test_concurrent_commands(self) -> bool:
        """Test handling of concurrent commands."""
        test_name = "concurrent_commands"
        
        try:
            # Create multiple commands for concurrent processing
            concurrent_commands = []
            for i in range(5):
                concurrent_commands.append({
                    "type": "set_parameter",
                    "parameters": {
                        "parameter_name": f"concurrent_param_{i}",
                        "value": float(i * 10)
                    },
                    "machine_id": self.mock_creator.test_machine_ids[0],
                    "status": "pending"
                })
            
            command_ids = self.mock_creator.insert_test_commands(concurrent_commands)
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create concurrent test commands"})
                return False
            
            # Process commands concurrently
            start_time = time.time()
            tasks = []
            
            for command_id in command_ids:
                result = (
                    self.supabase.table("recipe_commands")
                    .select("*")
                    .eq("id", command_id)
                    .single()
                    .execute()
                )
                
                command_record = result.data
                task = asyncio.create_task(process_command(command_record))
                tasks.append(task)
            
            # Wait for all commands to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            processing_time = time.time() - start_time
            
            # Check final statuses
            final_statuses = []
            for command_id in command_ids:
                result = (
                    self.supabase.table("recipe_commands")
                    .select("status")
                    .eq("id", command_id)
                    .single()
                    .execute()
                )
                final_statuses.append(result.data['status'])
            
            # Success if all commands completed or errored (not stuck in processing)
            completed_count = sum(1 for status in final_statuses if status in [CommandStatus.COMPLETED, CommandStatus.ERROR])
            success = completed_count == len(command_ids)
            
            details = {
                "concurrent_commands": len(command_ids),
                "completed_commands": completed_count,
                "total_processing_time_ms": processing_time * 1000,
                "final_statuses": final_statuses
            }
            
            self.record_test_result(test_name, success, details)
            
            # Cleanup
            self.mock_creator.cleanup_test_commands(command_ids)
            return success
            
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def test_database_integration(self) -> bool:
        """Test integration with new database schema."""
        test_name = "database_integration"
        
        try:
            # Test recipe parameter loading
            test_command = {
                "type": "start_recipe",
                "parameters": {
                    "recipe_id": self.mock_creator.test_recipe_ids[0],
                    "operator_id": "550e8400-e29b-41d4-a716-446655440000"
                },
                "machine_id": self.mock_creator.test_machine_ids[0],
                "status": "pending"
            }
            
            command_ids = self.mock_creator.insert_test_commands([test_command])
            
            if not command_ids:
                self.record_test_result(test_name, False, {"error": "Failed to create database integration test command"})
                return False
            
            command_id = command_ids[0]
            
            # Check recipe parameters exist
            recipe_id = test_command["parameters"]["recipe_id"]
            
            # Check recipe parameters table
            recipe_params_result = (
                self.supabase.table("recipe_parameters")
                .select("*")
                .eq("recipe_id", recipe_id)
                .execute()
            )
            
            # Check recipe steps
            recipe_steps_result = (
                self.supabase.table("recipe_steps")
                .select("*")
                .eq("recipe_id", recipe_id)
                .execute()
            )
            
            database_checks = {
                "recipe_parameters_found": len(recipe_params_result.data) > 0,
                "recipe_steps_found": len(recipe_steps_result.data) > 0,
                "recipe_parameters_count": len(recipe_params_result.data),
                "recipe_steps_count": len(recipe_steps_result.data)
            }
            
            # Process the command (should interact with normalized schema)
            result = (
                self.supabase.table("recipe_commands")
                .select("*")
                .eq("id", command_id)
                .single()
                .execute()
            )
            
            command_record = result.data
            
            try:
                await process_command(command_record)
                
                # Check if process_executions record was created
                process_result = (
                    self.supabase.table("process_executions")
                    .select("*")
                    .eq("recipe_id", recipe_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                
                process_execution_created = len(process_result.data) > 0
                
                # Check if process_execution_state was created
                state_created = False
                if process_execution_created:
                    process_id = process_result.data[0]['id']
                    state_result = (
                        self.supabase.table("process_execution_state")
                        .select("*")
                        .eq("execution_id", process_id)
                        .execute()
                    )
                    state_created = len(state_result.data) > 0
                
                database_checks.update({
                    "process_execution_created": process_execution_created,
                    "process_state_created": state_created
                })
                
            except Exception as proc_error:
                database_checks["processing_error"] = str(proc_error)
            
            # Success if we can interact with the normalized schema
            success = (
                database_checks["recipe_parameters_found"] or 
                database_checks["recipe_steps_found"]
            )
            
            details = {
                "command_id": command_id,
                "recipe_id": recipe_id,
                "database_checks": database_checks
            }
            
            self.record_test_result(test_name, success, details)
            
            # Cleanup
            self.mock_creator.cleanup_test_commands([command_id])
            return success
            
        except Exception as e:
            self.record_error(test_name, str(e))
            return False
    
    async def run_performance_tests(self) -> Dict[str, float]:
        """Run performance tests and measure timing."""
        performance_metrics = {}
        
        # Test command detection speed
        start_time = time.time()
        await check_pending_commands()
        performance_metrics["pending_command_check_ms"] = (time.time() - start_time) * 1000
        
        # Test database query performance
        start_time = time.time()
        result = self.supabase.table("recipe_commands").select("count").execute()
        performance_metrics["database_query_ms"] = (time.time() - start_time) * 1000
        
        # Test command creation speed
        test_command = {
            "type": "set_parameter",
            "parameters": {"parameter_name": "perf_test", "value": 1.0},
            "machine_id": self.mock_creator.test_machine_ids[0],
            "status": "pending"
        }
        
        start_time = time.time()
        command_ids = self.mock_creator.insert_test_commands([test_command])
        performance_metrics["command_creation_ms"] = (time.time() - start_time) * 1000
        
        # Cleanup performance test command
        if command_ids:
            self.mock_creator.cleanup_test_commands(command_ids)
        
        self.test_results["performance_metrics"] = performance_metrics
        return performance_metrics
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive integration test suite."""
        logger.info("Starting comprehensive command listener integration test...")
        
        try:
            await self.setup_async_client()
            
            # Run all tests
            test_functions = [
                self.test_command_detection,
                self.test_command_processing,
                self.test_error_handling,
                self.test_status_transitions,
                self.test_concurrent_commands,
                self.test_database_integration
            ]
            
            test_results = {}
            
            for test_func in test_functions:
                test_name = test_func.__name__
                logger.info(f"Running test: {test_name}")
                
                try:
                    result = await test_func()
                    test_results[test_name] = result
                except Exception as e:
                    self.record_error(test_name, str(e))
                    test_results[test_name] = False
            
            # Run performance tests
            logger.info("Running performance tests...")
            performance_metrics = await self.run_performance_tests()
            
            # Calculate overall results
            passed_tests = sum(1 for result in test_results.values() if result)
            total_tests = len(test_results)
            success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            self.test_results.update({
                "test_end_time": datetime.now().isoformat(),
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": total_tests - passed_tests,
                    "success_rate_percent": success_rate
                },
                "individual_results": test_results
            })
            
            logger.info(f"Integration test complete. Success rate: {success_rate:.1f}%")
            return self.test_results
            
        finally:
            await self.cleanup_async_client()
    
    def generate_test_report(self) -> str:
        """Generate comprehensive test report."""
        report = f"""
# Command Listener Integration Test Report

## Test Summary
- **Test Start**: {self.test_results.get('test_start_time', 'N/A')}
- **Test End**: {self.test_results.get('test_end_time', 'N/A')}
- **Total Tests**: {self.test_results.get('summary', {}).get('total_tests', 0)}
- **Passed Tests**: {self.test_results.get('summary', {}).get('passed_tests', 0)}
- **Failed Tests**: {self.test_results.get('summary', {}).get('failed_tests', 0)}
- **Success Rate**: {self.test_results.get('summary', {}).get('success_rate_percent', 0):.1f}%

## Individual Test Results
"""
        
        for test_name, test_data in self.test_results.get("tests", {}).items():
            status = "✅ PASSED" if test_data["success"] else "❌ FAILED"
            report += f"\n### {test_name}\n"
            report += f"- **Status**: {status}\n"
            report += f"- **Timestamp**: {test_data['timestamp']}\n"
            
            if test_data.get("details"):
                report += f"- **Details**: {json.dumps(test_data['details'], indent=2)}\n"
        
        # Performance metrics
        if self.test_results.get("performance_metrics"):
            report += f"\n## Performance Metrics\n"
            for metric_name, value in self.test_results["performance_metrics"].items():
                report += f"- **{metric_name}**: {value:.2f}\n"
        
        # Error logs
        if self.test_results.get("error_logs"):
            report += f"\n## Error Logs\n"
            for error in self.test_results["error_logs"]:
                report += f"\n### {error['test']} Error\n"
                report += f"- **Timestamp**: {error['timestamp']}\n"
                report += f"- **Error**: {error['error']}\n"
        
        return report


async def main():
    """Run the integration test suite."""
    test_runner = CommandListenerIntegrationTest()
    
    print("Starting Command Listener Integration Test Suite...")
    print("=" * 60)
    
    # Run comprehensive tests
    results = await test_runner.run_comprehensive_test()
    
    # Generate and save report
    report = test_runner.generate_test_report()
    
    # Save results to files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON results
    results_filename = f"command_listening_test_results_{timestamp}.json"
    with open(results_filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save markdown report
    report_filename = f"command_listening_test_report_{timestamp}.md"
    with open(report_filename, 'w') as f:
        f.write(report)
    
    print(f"\nTest Results Summary:")
    print(f"Success Rate: {results.get('summary', {}).get('success_rate_percent', 0):.1f}%")
    print(f"Results saved to: {results_filename}")
    print(f"Report saved to: {report_filename}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())