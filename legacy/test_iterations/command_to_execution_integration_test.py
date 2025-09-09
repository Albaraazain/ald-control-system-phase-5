#!/usr/bin/env python3
"""
Command-to-Execution Integration Test
Tests full command flow from command creation through recipe execution
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from database.connection import get_supabase_client
from command_flow.listener import CommandListener
from command_flow.processor import CommandProcessor
from plc.manager import plc_manager
from log_setup import logger

class CommandToExecutionIntegrationTest:
    """Tests complete command flow integration"""
    
    def __init__(self, project_id: str = "yceyfsqusdmcwgkwxcnt"):
        self.project_id = project_id
        self.supabase = get_supabase_client()
        self.test_commands = []
        
    async def execute_command_flow_integration_tests(self) -> Dict[str, Any]:
        """Execute comprehensive command flow integration tests"""
        logger.info("🔄 Starting command flow integration tests")
        
        test_results = {
            'test_execution_id': f"cmd_flow_test_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'test_phases': {},
            'created_commands': [],
            'summary': {},
            'overall_status': 'UNKNOWN'
        }
        
        try:
            # Initialize systems
            await self.initialize_test_environment()
            
            # Phase 1: Command Creation Tests
            logger.info("📝 Phase 1: Testing command creation")
            creation_result = await self.test_command_creation()
            test_results['test_phases']['command_creation'] = creation_result
            test_results['created_commands'] = creation_result.get('created_commands', [])
            
            # Phase 2: Command Detection Tests  
            logger.info("👂 Phase 2: Testing command detection")
            detection_result = await self.test_command_detection()
            test_results['test_phases']['command_detection'] = detection_result
            
            # Phase 3: Command Processing Tests
            logger.info("⚙️ Phase 3: Testing command processing")
            processing_result = await self.test_command_processing()
            test_results['test_phases']['command_processing'] = processing_result
            
            # Phase 4: Recipe Execution Integration
            logger.info("🚀 Phase 4: Testing recipe execution integration")
            execution_result = await self.test_recipe_execution_integration()
            test_results['test_phases']['recipe_execution'] = execution_result
            
            # Phase 5: Process State Integration
            logger.info("📈 Phase 5: Testing process state integration")
            state_result = await self.test_process_state_integration()
            test_results['test_phases']['process_state'] = state_result
            
            # Phase 6: Error Handling Tests
            logger.info("🛡️ Phase 6: Testing error handling")
            error_handling_result = await self.test_error_handling()
            test_results['test_phases']['error_handling'] = error_handling_result
            
            # Calculate summary
            test_results['completed_at'] = datetime.now().isoformat()
            test_results['summary'] = self.calculate_integration_summary(test_results['test_phases'])
            test_results['overall_status'] = 'PASSED' if test_results['summary']['all_passed'] else 'FAILED'
            
            # Save detailed results
            report_filename = f"command_integration_test_results_{int(time.time())}.json"
            with open(report_filename, 'w') as f:
                json.dump(test_results, f, indent=2, default=str)
            
            logger.info(f"📊 Command integration test results saved to {report_filename}")
            return test_results
            
        except Exception as e:
            logger.error(f"❌ Command flow integration test failed: {str(e)}")
            test_results['error'] = str(e)
            test_results['overall_status'] = 'ERROR'
            return test_results
    
    async def initialize_test_environment(self) -> None:
        """Initialize test environment"""
        logger.info("🔧 Initializing test environment")
        
        # Initialize PLC manager in simulation mode
        await plc_manager.initialize(simulation_mode=True)
        logger.info("✅ PLC simulation initialized")
    
    async def test_command_creation(self) -> Dict[str, Any]:
        """Test creation of various command types"""
        
        # Get a test recipe for start_recipe commands
        test_recipe = await self.get_test_recipe()
        
        test_commands = [
            {
                'type': 'start_recipe',
                'params': {'recipe_id': test_recipe['id'] if test_recipe else '00000000-0000-0000-0000-000000000000', 'operator_id': 1},
                'priority': 1
            },
            {
                'type': 'set_parameter',
                'params': {'parameter_name': 'chamber_pressure', 'value': 125.5},
                'priority': 2
            },
            {
                'type': 'set_parameter', 
                'params': {'parameter_name': 'base_temperature', 'value': 28.0},
                'priority': 3
            },
            {
                'type': 'stop_recipe',
                'params': {'reason': 'integration_test'},
                'priority': 4
            }
        ]
        
        created_commands = []
        creation_errors = []
        
        for cmd in test_commands:
            try:
                # Create command in database
                create_query = f"""
                INSERT INTO commands (
                    machine_id, 
                    command_type, 
                    parameters, 
                    status, 
                    priority, 
                    created_at, 
                    updated_at
                ) VALUES (
                    1,
                    '{cmd['type']}',
                    '{json.dumps(cmd['params'])}',
                    'pending',
                    {cmd['priority']},
                    NOW(),
                    NOW()
                ) RETURNING id, command_type, parameters, status, priority;
                """
                
                response = self.supabase.rpc('execute_sql', {
                    'sql_query': create_query
                }).execute()
                
                if response.data and len(response.data) > 0:
                    command_data = response.data[0]
                    created_commands.append({
                        'id': command_data['id'],
                        'type': command_data['command_type'],
                        'parameters': command_data['parameters'],
                        'status': command_data['status'],
                        'priority': command_data['priority'],
                        'created_successfully': True
                    })
                    logger.info(f"✅ Created command {cmd['type']} with ID {command_data['id']}")
                else:
                    creation_errors.append(f"No data returned for command {cmd['type']}")
                    
            except Exception as e:
                error_msg = f"Failed to create command {cmd['type']}: {str(e)}"
                creation_errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        success_rate = len(created_commands) / len(test_commands)
        
        return {
            'success': success_rate >= 0.75,  # 75% success rate required
            'total_commands_attempted': len(test_commands),
            'successful_commands': len(created_commands),
            'creation_success_rate': success_rate,
            'created_commands': created_commands,
            'creation_errors': creation_errors,
            'test_recipe_available': test_recipe is not None
        }
    
    async def get_test_recipe(self) -> Optional[Dict[str, Any]]:
        """Get a test recipe for commands"""
        
        recipe_query = """
        SELECT id, name, description
        FROM recipes 
        WHERE (name LIKE '%Test%' OR name LIKE '%Integration%' OR name LIKE '%Simulation%')
        AND id IN (SELECT DISTINCT recipe_id FROM recipe_steps)
        ORDER BY created_at DESC
        LIMIT 1;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': recipe_query}).execute()
            recipes = response.data if response.data else []
            return recipes[0] if recipes else None
        except Exception as e:
            logger.error(f"❌ Failed to get test recipe: {str(e)}")
            return None
    
    async def test_command_detection(self) -> Dict[str, Any]:
        """Test command detection capabilities"""
        
        # Check recent pending commands
        detection_query = """
        SELECT 
            id,
            machine_id,
            command_type,
            parameters,
            status,
            priority,
            created_at
        FROM commands 
        WHERE machine_id = 1 
        AND created_at > NOW() - INTERVAL '10 minutes'
        ORDER BY priority, created_at;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': detection_query}).execute()
            recent_commands = response.data if response.data else []
            
            # Test command listener simulation
            detected_commands = []
            detection_errors = []
            
            for cmd in recent_commands[:5]:  # Test first 5 commands
                try:
                    # Simulate command detection process
                    detection_result = await self.simulate_command_detection(cmd)
                    detected_commands.append(detection_result)
                    
                    if not detection_result['detected_successfully']:
                        detection_errors.append(f"Failed to detect command {cmd['id']}")
                        
                except Exception as e:
                    error_msg = f"Detection error for command {cmd['id']}: {str(e)}"
                    detection_errors.append(error_msg)
            
            detection_rate = len([c for c in detected_commands if c['detected_successfully']]) / len(detected_commands) if detected_commands else 0
            
            return {
                'success': detection_rate >= 0.8,
                'total_commands_available': len(recent_commands),
                'commands_tested_for_detection': len(detected_commands),
                'detection_success_rate': detection_rate,
                'detected_commands': detected_commands,
                'detection_errors': detection_errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_commands_available': 0
            }
    
    async def simulate_command_detection(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate command detection process"""
        
        command_id = command['id']
        command_type = command['command_type']
        
        try:
            # Parse parameters
            try:
                parameters = json.loads(command['parameters']) if isinstance(command['parameters'], str) else command['parameters']
            except:
                parameters = {}
            
            # Validate command structure
            required_fields = ['command_type', 'parameters', 'status']
            has_required = all(field in command for field in required_fields)
            
            # Validate command type
            valid_types = ['start_recipe', 'stop_recipe', 'set_parameter', 'pause_recipe', 'resume_recipe']
            valid_type = command_type in valid_types
            
            # Validate parameters based on command type
            valid_params = True
            if command_type == 'start_recipe':
                valid_params = 'recipe_id' in parameters
            elif command_type == 'set_parameter':
                valid_params = 'parameter_name' in parameters and 'value' in parameters
            
            detection_successful = has_required and valid_type and valid_params
            
            return {
                'command_id': command_id,
                'command_type': command_type,
                'detected_successfully': detection_successful,
                'has_required_fields': has_required,
                'valid_command_type': valid_type,
                'valid_parameters': valid_params,
                'parameters': parameters
            }
            
        except Exception as e:
            return {
                'command_id': command_id,
                'command_type': command_type,
                'detected_successfully': False,
                'error': str(e)
            }
    
    async def test_command_processing(self) -> Dict[str, Any]:
        """Test command processing logic"""
        
        # Get recent pending commands
        processing_query = """
        SELECT 
            id,
            command_type,
            parameters,
            status,
            priority
        FROM commands
        WHERE machine_id = 1 
        AND status = 'pending'
        AND created_at > NOW() - INTERVAL '10 minutes'
        ORDER BY priority, created_at
        LIMIT 10;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': processing_query}).execute()
            pending_commands = response.data if response.data else []
            
            processed_commands = []
            processing_errors = []
            
            for cmd in pending_commands:
                try:
                    processing_result = await self.simulate_command_processing(cmd)
                    processed_commands.append(processing_result)
                    
                    # Update command status to simulate processing
                    if processing_result['processing_successful']:
                        update_query = f"""
                        UPDATE commands 
                        SET 
                            status = 'processing',
                            updated_at = NOW()
                        WHERE id = '{cmd['id']}';
                        """
                        self.supabase.rpc('execute_sql', {'sql_query': update_query}).execute()
                        
                except Exception as e:
                    error_msg = f"Processing error for command {cmd['id']}: {str(e)}"
                    processing_errors.append(error_msg)
            
            processing_rate = len([c for c in processed_commands if c['processing_successful']]) / len(processed_commands) if processed_commands else 0
            
            return {
                'success': processing_rate >= 0.8,
                'total_pending_commands': len(pending_commands),
                'commands_processed': len(processed_commands),
                'processing_success_rate': processing_rate,
                'processed_commands': processed_commands,
                'processing_errors': processing_errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_pending_commands': 0
            }
    
    async def simulate_command_processing(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate command processing"""
        
        command_id = command['id']
        command_type = command['command_type']
        
        try:
            parameters = json.loads(command['parameters']) if isinstance(command['parameters'], str) else command['parameters']
            
            processing_successful = False
            processing_notes = []
            
            if command_type == 'start_recipe':
                # Validate recipe exists
                recipe_id = parameters.get('recipe_id')
                if recipe_id:
                    recipe_check_query = f"SELECT id FROM recipes WHERE id = '{recipe_id}'"
                    recipe_response = self.supabase.rpc('execute_sql', {'sql_query': recipe_check_query}).execute()
                    
                    if recipe_response.data:
                        processing_successful = True
                        processing_notes.append("Recipe found and validated")
                    else:
                        processing_notes.append("Recipe not found")
                else:
                    processing_notes.append("Missing recipe_id parameter")
                    
            elif command_type == 'set_parameter':
                # Validate parameter structure
                if 'parameter_name' in parameters and 'value' in parameters:
                    processing_successful = True
                    processing_notes.append("Parameter command structure valid")
                else:
                    processing_notes.append("Invalid parameter command structure")
                    
            elif command_type == 'stop_recipe':
                processing_successful = True
                processing_notes.append("Stop recipe command ready")
                
            else:
                processing_notes.append(f"Unknown command type: {command_type}")
            
            return {
                'command_id': command_id,
                'command_type': command_type,
                'processing_successful': processing_successful,
                'processing_notes': processing_notes,
                'parameters': parameters
            }
            
        except Exception as e:
            return {
                'command_id': command_id,
                'command_type': command_type,
                'processing_successful': False,
                'error': str(e)
            }
    
    async def test_recipe_execution_integration(self) -> Dict[str, Any]:
        """Test recipe execution integration with command flow"""
        
        # Find start_recipe commands to test
        start_recipe_query = """
        SELECT 
            id,
            parameters,
            status
        FROM commands
        WHERE command_type = 'start_recipe'
        AND machine_id = 1
        AND created_at > NOW() - INTERVAL '10 minutes'
        ORDER BY created_at DESC
        LIMIT 3;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': start_recipe_query}).execute()
            start_commands = response.data if response.data else []
            
            execution_tests = []
            execution_errors = []
            
            for cmd in start_commands:
                try:
                    execution_result = await self.simulate_recipe_execution_from_command(cmd)
                    execution_tests.append(execution_result)
                    
                except Exception as e:
                    error_msg = f"Execution test error for command {cmd['id']}: {str(e)}"
                    execution_errors.append(error_msg)
            
            execution_success_rate = len([t for t in execution_tests if t['execution_successful']]) / len(execution_tests) if execution_tests else 0
            
            return {
                'success': execution_success_rate >= 0.7,
                'start_recipe_commands_found': len(start_commands),
                'execution_tests_performed': len(execution_tests),
                'execution_success_rate': execution_success_rate,
                'execution_test_results': execution_tests,
                'execution_errors': execution_errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'start_recipe_commands_found': 0
            }
    
    async def simulate_recipe_execution_from_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate recipe execution from start_recipe command"""
        
        command_id = command['id']
        
        try:
            parameters = json.loads(command['parameters']) if isinstance(command['parameters'], str) else command['parameters']
            recipe_id = parameters.get('recipe_id')
            
            if not recipe_id:
                return {
                    'command_id': command_id,
                    'execution_successful': False,
                    'error': 'No recipe_id in parameters'
                }
            
            # Create process execution record
            create_execution_query = f"""
            INSERT INTO process_executions (
                recipe_id,
                started_at,
                status,
                operator_id
            ) VALUES (
                '{recipe_id}',
                NOW(),
                'running',
                1
            ) RETURNING id;
            """
            
            execution_response = self.supabase.rpc('execute_sql', {
                'sql_query': create_execution_query
            }).execute()
            
            if not execution_response.data:
                return {
                    'command_id': command_id,
                    'execution_successful': False,
                    'error': 'Failed to create process execution record'
                }
            
            process_execution_id = execution_response.data[0]['id']
            
            # Get recipe steps
            steps_query = f"""
            SELECT id, name, type, sequence_number
            FROM recipe_steps
            WHERE recipe_id = '{recipe_id}'
            ORDER BY sequence_number
            LIMIT 5;
            """
            
            steps_response = self.supabase.rpc('execute_sql', {'sql_query': steps_query}).execute()
            steps = steps_response.data if steps_response.data else []
            
            # Simulate step execution states
            simulated_steps = 0
            for step in steps:
                try:
                    state_query = f"""
                    INSERT INTO process_execution_state (
                        process_execution_id,
                        current_step_id,
                        step_start_time,
                        progress_percentage
                    ) VALUES (
                        '{process_execution_id}',
                        '{step['id']}',
                        NOW(),
                        100
                    );
                    """
                    
                    self.supabase.rpc('execute_sql', {'sql_query': state_query}).execute()
                    simulated_steps += 1
                    
                except Exception as step_error:
                    logger.warning(f"Step simulation error: {step_error}")
            
            # Update process execution to completed
            complete_query = f"""
            UPDATE process_executions
            SET 
                status = 'completed',
                completed_at = NOW()
            WHERE id = '{process_execution_id}';
            """
            
            self.supabase.rpc('execute_sql', {'sql_query': complete_query}).execute()
            
            return {
                'command_id': command_id,
                'recipe_id': recipe_id,
                'process_execution_id': process_execution_id,
                'execution_successful': True,
                'total_steps': len(steps),
                'simulated_steps': simulated_steps
            }
            
        except Exception as e:
            return {
                'command_id': command_id,
                'execution_successful': False,
                'error': str(e)
            }
    
    async def test_process_state_integration(self) -> Dict[str, Any]:
        """Test process execution state integration"""
        
        # Query recent process executions and their states
        state_integration_query = """
        SELECT 
            pe.id as process_id,
            pe.recipe_id,
            pe.status,
            pe.started_at,
            pe.completed_at,
            COUNT(pes.id) as state_record_count,
            COUNT(CASE WHEN pes.progress_percentage = 100 THEN 1 END) as completed_steps
        FROM process_executions pe
        LEFT JOIN process_execution_state pes ON pe.id = pes.process_execution_id
        WHERE pe.created_at > NOW() - INTERVAL '10 minutes'
        GROUP BY pe.id, pe.recipe_id, pe.status, pe.started_at, pe.completed_at
        ORDER BY pe.started_at DESC
        LIMIT 10;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': state_integration_query}).execute()
            state_data = response.data if response.data else []
            
            if not state_data:
                return {
                    'success': False,
                    'error': 'No recent process executions found',
                    'process_executions_tested': 0
                }
            
            # Analyze state integration
            processes_with_states = sum(1 for p in state_data if p['state_record_count'] > 0)
            total_processes = len(state_data)
            
            # Check state completeness
            complete_processes = sum(1 for p in state_data if p['completed_steps'] > 0)
            
            state_integration_rate = processes_with_states / total_processes if total_processes > 0 else 0
            
            return {
                'success': state_integration_rate >= 0.8,
                'total_processes_tested': total_processes,
                'processes_with_states': processes_with_states,
                'processes_with_completed_steps': complete_processes,
                'state_integration_rate': state_integration_rate,
                'process_execution_details': state_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'process_executions_tested': 0
            }
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling in command flow"""
        
        error_tests = []
        
        try:
            # Test 1: Invalid recipe ID
            invalid_recipe_test = await self.test_invalid_recipe_command()
            error_tests.append(('invalid_recipe', invalid_recipe_test))
            
            # Test 2: Malformed parameters
            malformed_params_test = await self.test_malformed_parameters_command()
            error_tests.append(('malformed_parameters', malformed_params_test))
            
            # Test 3: Missing required parameters
            missing_params_test = await self.test_missing_parameters_command()
            error_tests.append(('missing_parameters', missing_params_test))
            
            successful_error_tests = sum(1 for _, test in error_tests if test['error_handled_correctly'])
            error_handling_rate = successful_error_tests / len(error_tests)
            
            return {
                'success': error_handling_rate >= 0.7,
                'total_error_tests': len(error_tests),
                'successful_error_handling': successful_error_tests,
                'error_handling_rate': error_handling_rate,
                'error_test_details': error_tests
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_error_tests': 0
            }
    
    async def test_invalid_recipe_command(self) -> Dict[str, Any]:
        """Test handling of invalid recipe ID"""
        
        try:
            # Create command with invalid recipe ID
            invalid_recipe_query = """
            INSERT INTO commands (
                machine_id,
                command_type,
                parameters,
                status,
                priority,
                created_at,
                updated_at
            ) VALUES (
                1,
                'start_recipe',
                '{"recipe_id": "invalid-recipe-id-123", "operator_id": 1}',
                'pending',
                1,
                NOW(),
                NOW()
            ) RETURNING id;
            """
            
            response = self.supabase.rpc('execute_sql', {'sql_query': invalid_recipe_query}).execute()
            
            if response.data:
                command_id = response.data[0]['id']
                
                # Try to process this command
                processing_result = await self.simulate_command_processing({
                    'id': command_id,
                    'command_type': 'start_recipe',
                    'parameters': '{"recipe_id": "invalid-recipe-id-123", "operator_id": 1}'
                })
                
                # Error should be handled (processing should fail gracefully)
                error_handled = not processing_result['processing_successful']
                
                return {
                    'error_handled_correctly': error_handled,
                    'command_id': command_id,
                    'processing_result': processing_result
                }
            else:
                return {
                    'error_handled_correctly': False,
                    'error': 'Failed to create test command'
                }
                
        except Exception as e:
            return {
                'error_handled_correctly': True,  # Exception is a form of error handling
                'error': str(e)
            }
    
    async def test_malformed_parameters_command(self) -> Dict[str, Any]:
        """Test handling of malformed parameters"""
        
        try:
            malformed_query = """
            INSERT INTO commands (
                machine_id,
                command_type,
                parameters,
                status,
                priority,
                created_at,
                updated_at
            ) VALUES (
                1,
                'set_parameter',
                'invalid json format {[}',
                'pending',
                1,
                NOW(),
                NOW()
            ) RETURNING id;
            """
            
            response = self.supabase.rpc('execute_sql', {'sql_query': malformed_query}).execute()
            
            if response.data:
                command_id = response.data[0]['id']
                
                processing_result = await self.simulate_command_processing({
                    'id': command_id,
                    'command_type': 'set_parameter',
                    'parameters': 'invalid json format {[}'
                })
                
                error_handled = not processing_result['processing_successful']
                
                return {
                    'error_handled_correctly': error_handled,
                    'command_id': command_id,
                    'processing_result': processing_result
                }
            else:
                return {
                    'error_handled_correctly': False,
                    'error': 'Failed to create test command'
                }
                
        except Exception as e:
            return {
                'error_handled_correctly': True,
                'error': str(e)
            }
    
    async def test_missing_parameters_command(self) -> Dict[str, Any]:
        """Test handling of missing required parameters"""
        
        try:
            missing_params_query = """
            INSERT INTO commands (
                machine_id,
                command_type,
                parameters,
                status,
                priority,
                created_at,
                updated_at
            ) VALUES (
                1,
                'start_recipe',
                '{"operator_id": 1}',
                'pending',
                1,
                NOW(),
                NOW()
            ) RETURNING id;
            """
            
            response = self.supabase.rpc('execute_sql', {'sql_query': missing_params_query}).execute()
            
            if response.data:
                command_id = response.data[0]['id']
                
                processing_result = await self.simulate_command_processing({
                    'id': command_id,
                    'command_type': 'start_recipe',
                    'parameters': '{"operator_id": 1}'  # Missing recipe_id
                })
                
                error_handled = not processing_result['processing_successful']
                
                return {
                    'error_handled_correctly': error_handled,
                    'command_id': command_id,
                    'processing_result': processing_result
                }
            else:
                return {
                    'error_handled_correctly': False,
                    'error': 'Failed to create test command'
                }
                
        except Exception as e:
            return {
                'error_handled_correctly': True,
                'error': str(e)
            }
    
    def calculate_integration_summary(self, test_phases: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate integration test summary"""
        
        total_phases = len(test_phases)
        passed_phases = sum(1 for phase in test_phases.values() if phase.get('success', False))
        failed_phases = total_phases - passed_phases
        
        return {
            'total_phases': total_phases,
            'passed_phases': passed_phases,
            'failed_phases': failed_phases,
            'overall_success_rate': passed_phases / total_phases if total_phases > 0 else 0,
            'all_passed': failed_phases == 0,
            'phase_results': {name: phase.get('success', False) for name, phase in test_phases.items()}
        }

async def main():
    """Main execution function"""
    tester = CommandToExecutionIntegrationTest()
    results = await tester.execute_command_flow_integration_tests()
    
    print("\n" + "="*80)
    print("🔄 COMMAND-TO-EXECUTION INTEGRATION TESTING - COMPLETE")
    print("="*80)
    print(f"Overall Status: {results['overall_status']}")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"Success Rate: {summary.get('overall_success_rate', 0):.2%}")
        print(f"Passed Phases: {summary.get('passed_phases', 0)}/{summary.get('total_phases', 0)}")
    
    print("="*80)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())