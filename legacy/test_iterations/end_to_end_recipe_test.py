#!/usr/bin/env python3
"""
End-to-End Recipe Test
Tests complete recipe flow from database loading through execution simulation
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
from plc.manager import plc_manager
from recipe_flow.executor import RecipeExecutor
from step_flow.executor import StepExecutor
from log_setup import logger

class EndToEndRecipeTest:
    """Complete end-to-end recipe execution testing"""
    
    def __init__(self, project_id: str = "yceyfsqusdmcwgkwxcnt"):
        self.project_id = project_id
        self.supabase = get_supabase_client()
        self.test_results = {}
        self.test_recipes = []
        
    async def execute_comprehensive_e2e_tests(self) -> Dict[str, Any]:
        """Execute all end-to-end tests"""
        logger.info("🚀 Starting comprehensive end-to-end recipe tests")
        
        test_results = {
            'test_execution_id': f"e2e_test_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'tests_executed': [],
            'summary': {},
            'overall_status': 'UNKNOWN'
        }
        
        try:
            # Initialize PLC manager in simulation mode
            await self.initialize_plc_simulation()
            
            # Load test recipes
            test_recipes = await self.load_test_recipes()
            if not test_recipes:
                raise Exception("No test recipes found in database")
            
            test_results['total_test_recipes'] = len(test_recipes)
            logger.info(f"📋 Found {len(test_recipes)} test recipes for execution")
            
            # Execute tests for each recipe
            for recipe in test_recipes:
                logger.info(f"🧪 Testing recipe: {recipe['name']}")
                recipe_test_result = await self.test_recipe_execution(recipe)
                test_results['tests_executed'].append(recipe_test_result)
                
                # Short pause between recipe tests
                await asyncio.sleep(2)
            
            # Generate summary
            test_results['completed_at'] = datetime.now().isoformat()
            test_results['summary'] = self.calculate_test_summary(test_results['tests_executed'])
            test_results['overall_status'] = 'PASSED' if test_results['summary']['all_passed'] else 'FAILED'
            
            # Save detailed results
            report_filename = f"end_to_end_test_results_{int(time.time())}.json"
            with open(report_filename, 'w') as f:
                json.dump(test_results, f, indent=2, default=str)
            
            logger.info(f"📊 End-to-end test results saved to {report_filename}")
            return test_results
            
        except Exception as e:
            logger.error(f"❌ End-to-end test execution failed: {str(e)}")
            test_results['error'] = str(e)
            test_results['overall_status'] = 'ERROR'
            return test_results
    
    async def initialize_plc_simulation(self) -> None:
        """Initialize PLC manager in simulation mode"""
        logger.info("🔧 Initializing PLC simulation mode")
        
        try:
            # Initialize the PLC manager in simulation mode
            await plc_manager.initialize(simulation_mode=True)
            logger.info("✅ PLC simulation mode initialized successfully")
        except Exception as e:
            logger.error(f"❌ PLC simulation initialization failed: {str(e)}")
            raise
    
    async def load_test_recipes(self) -> List[Dict[str, Any]]:
        """Load all test recipes from database"""
        logger.info("📚 Loading test recipes from database")
        
        recipe_query = """
        SELECT 
            r.id,
            r.name,
            r.description,
            r.created_at,
            COUNT(rs.id) as total_steps,
            COUNT(CASE WHEN rs.type = 'valve' THEN 1 END) as valve_steps,
            COUNT(CASE WHEN rs.type = 'purge' THEN 1 END) as purge_steps,
            COUNT(CASE WHEN rs.type = 'loop' THEN 1 END) as loop_steps,
            COUNT(CASE WHEN rs.type = 'parameter' THEN 1 END) as parameter_steps
        FROM recipes r
        LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
        WHERE (r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%')
        AND r.id IN (
            SELECT DISTINCT recipe_id 
            FROM recipe_steps 
            WHERE recipe_id = r.id
        )
        GROUP BY r.id, r.name, r.description, r.created_at
        HAVING COUNT(rs.id) > 0
        ORDER BY r.created_at DESC;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': recipe_query}).execute()
            recipes = response.data if response.data else []
            
            logger.info(f"📋 Loaded {len(recipes)} test recipes")
            return recipes
            
        except Exception as e:
            logger.error(f"❌ Failed to load test recipes: {str(e)}")
            return []
    
    async def test_recipe_execution(self, recipe: Dict[str, Any]) -> Dict[str, Any]:
        """Test complete recipe execution"""
        recipe_test_start = datetime.now()
        recipe_id = recipe['id']
        recipe_name = recipe['name']
        
        test_result = {
            'recipe_id': recipe_id,
            'recipe_name': recipe_name,
            'started_at': recipe_test_start.isoformat(),
            'test_phases': {},
            'overall_success': False,
            'errors': []
        }
        
        try:
            # Phase 1: Load recipe steps and configurations
            logger.info(f"📋 Phase 1: Loading recipe steps for {recipe_name}")
            steps_result = await self.load_and_validate_recipe_steps(recipe_id)
            test_result['test_phases']['step_loading'] = steps_result
            
            if not steps_result['success']:
                test_result['errors'].append("Step loading failed")
                return test_result
            
            # Phase 2: Load recipe parameters
            logger.info(f"📊 Phase 2: Loading recipe parameters for {recipe_name}")
            params_result = await self.load_and_validate_recipe_parameters(recipe_id)
            test_result['test_phases']['parameter_loading'] = params_result
            
            # Phase 3: Simulate recipe execution initialization
            logger.info(f"🚀 Phase 3: Simulating recipe execution for {recipe_name}")
            execution_result = await self.simulate_recipe_execution(recipe_id, steps_result['steps'])
            test_result['test_phases']['execution_simulation'] = execution_result
            
            # Phase 4: Test process state tracking
            logger.info(f"📈 Phase 4: Testing process state tracking for {recipe_name}")
            state_tracking_result = await self.test_process_state_tracking(recipe_id)
            test_result['test_phases']['state_tracking'] = state_tracking_result
            
            # Phase 5: Test step configuration loading
            logger.info(f"⚙️ Phase 5: Testing step configuration loading for {recipe_name}")
            config_loading_result = await self.test_step_configuration_loading(steps_result['steps'])
            test_result['test_phases']['config_loading'] = config_loading_result
            
            # Determine overall success
            all_phases_passed = all(
                phase.get('success', False) for phase in test_result['test_phases'].values()
            )
            test_result['overall_success'] = all_phases_passed
            
            if all_phases_passed:
                logger.info(f"✅ Recipe {recipe_name} passed all test phases")
            else:
                logger.warning(f"⚠️ Recipe {recipe_name} had some test phase failures")
                
        except Exception as e:
            logger.error(f"❌ Recipe test failed for {recipe_name}: {str(e)}")
            test_result['errors'].append(str(e))
            test_result['overall_success'] = False
        
        test_result['completed_at'] = datetime.now().isoformat()
        test_result['duration_seconds'] = (datetime.now() - recipe_test_start).total_seconds()
        
        return test_result
    
    async def load_and_validate_recipe_steps(self, recipe_id: str) -> Dict[str, Any]:
        """Load and validate recipe steps from database"""
        
        steps_query = f"""
        SELECT 
            rs.id,
            rs.name,
            rs.type,
            rs.sequence_number,
            rs.duration_ms,
            rs.recipe_id,
            -- Valve configuration
            vsc.valve_number,
            vsc.duration_ms as valve_duration_ms,
            -- Purge configuration
            psc.gas_type,
            psc.duration_ms as purge_duration_ms,
            psc.flow_rate as purge_flow_rate,
            -- Loop configuration
            lsc.iteration_count,
            lsc.inner_steps
        FROM recipe_steps rs
        LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id AND rs.type = 'valve'
        LEFT JOIN purge_step_config psc ON rs.id = psc.step_id AND rs.type = 'purge'
        LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id AND rs.type = 'loop'
        WHERE rs.recipe_id = '{recipe_id}'
        ORDER BY rs.sequence_number;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': steps_query}).execute()
            steps = response.data if response.data else []
            
            if not steps:
                return {
                    'success': False,
                    'error': 'No steps found for recipe',
                    'steps': []
                }
            
            # Validate step completeness
            configured_steps = 0
            unconfigured_steps = []
            
            for step in steps:
                step_type = step['type']
                has_config = False
                
                if step_type == 'valve' and step['valve_number'] is not None:
                    has_config = True
                elif step_type == 'purge' and step['gas_type'] is not None:
                    has_config = True
                elif step_type == 'loop' and step['iteration_count'] is not None:
                    has_config = True
                elif step_type == 'parameter':
                    has_config = True  # Parameter steps don't need configuration
                
                if has_config:
                    configured_steps += 1
                else:
                    unconfigured_steps.append(step['name'])
            
            configuration_rate = configured_steps / len(steps) if steps else 0
            
            return {
                'success': configuration_rate >= 0.8,  # 80% configuration rate required
                'total_steps': len(steps),
                'configured_steps': configured_steps,
                'configuration_rate': configuration_rate,
                'unconfigured_steps': unconfigured_steps,
                'steps': steps
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'steps': []
            }
    
    async def load_and_validate_recipe_parameters(self, recipe_id: str) -> Dict[str, Any]:
        """Load and validate recipe parameters"""
        
        params_query = f"""
        SELECT 
            parameter_name,
            parameter_value,
            parameter_type,
            created_at
        FROM recipe_parameters
        WHERE recipe_id = '{recipe_id}'
        ORDER BY parameter_name;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': params_query}).execute()
            parameters = response.data if response.data else []
            
            # Validate parameter completeness
            valid_parameters = 0
            invalid_parameters = []
            
            for param in parameters:
                if param['parameter_value'] and param['parameter_value'].strip():
                    valid_parameters += 1
                else:
                    invalid_parameters.append(param['parameter_name'])
            
            validity_rate = valid_parameters / len(parameters) if parameters else 1.0
            
            return {
                'success': validity_rate >= 0.9,  # 90% parameter validity required
                'total_parameters': len(parameters),
                'valid_parameters': valid_parameters,
                'validity_rate': validity_rate,
                'invalid_parameters': invalid_parameters,
                'parameters': parameters
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'parameters': []
            }
    
    async def simulate_recipe_execution(self, recipe_id: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate recipe execution with new database schema"""
        
        try:
            # Create simulated process execution record
            create_process_execution_query = f"""
            INSERT INTO process_executions (
                recipe_id, 
                started_at, 
                status, 
                operator_id
            ) VALUES (
                '{recipe_id}',
                '{datetime.now().isoformat()}',
                'running',
                1
            ) RETURNING id;
            """
            
            response = self.supabase.rpc('execute_sql', {
                'sql_query': create_process_execution_query
            }).execute()
            
            if not response.data:
                raise Exception("Failed to create process execution record")
            
            process_execution_id = response.data[0]['id']
            
            # Simulate executing each step
            executed_steps = 0
            step_execution_results = []
            
            for step in steps[:5]:  # Limit to first 5 steps for simulation
                step_result = await self.simulate_step_execution(
                    process_execution_id, step
                )
                step_execution_results.append(step_result)
                
                if step_result['success']:
                    executed_steps += 1
                
                # Small delay to simulate step duration
                await asyncio.sleep(0.1)
            
            # Update process execution status
            update_process_query = f"""
            UPDATE process_executions 
            SET 
                status = 'completed',
                completed_at = '{datetime.now().isoformat()}'
            WHERE id = '{process_execution_id}';
            """
            
            self.supabase.rpc('execute_sql', {'sql_query': update_process_query}).execute()
            
            execution_rate = executed_steps / min(len(steps), 5)
            
            return {
                'success': execution_rate >= 0.8,
                'process_execution_id': process_execution_id,
                'total_steps_simulated': min(len(steps), 5),
                'executed_steps': executed_steps,
                'execution_rate': execution_rate,
                'step_results': step_execution_results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'executed_steps': 0
            }
    
    async def simulate_step_execution(self, process_execution_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate individual step execution"""
        
        step_id = step['id']
        step_type = step['type']
        
        try:
            # Create process execution state record
            create_state_query = f"""
            INSERT INTO process_execution_state (
                process_execution_id,
                current_step_id,
                step_start_time,
                progress_percentage,
                valve_number,
                duration_ms
            ) VALUES (
                '{process_execution_id}',
                '{step_id}',
                '{datetime.now().isoformat()}',
                0,
                {step.get('valve_number', 'NULL')},
                {step.get('duration_ms', step.get('valve_duration_ms', step.get('purge_duration_ms', 1000)))}
            ) RETURNING id;
            """
            
            response = self.supabase.rpc('execute_sql', {
                'sql_query': create_state_query
            }).execute()
            
            if not response.data:
                raise Exception(f"Failed to create state record for step {step['name']}")
            
            state_id = response.data[0]['id']
            
            # Simulate step progress updates
            for progress in [25, 50, 75, 100]:
                update_progress_query = f"""
                UPDATE process_execution_state
                SET progress_percentage = {progress}
                WHERE id = '{state_id}';
                """
                
                self.supabase.rpc('execute_sql', {
                    'sql_query': update_progress_query
                }).execute()
                
                await asyncio.sleep(0.05)  # Small delay for simulation
            
            return {
                'success': True,
                'step_id': step_id,
                'step_name': step['name'],
                'step_type': step_type,
                'state_id': state_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'step_id': step_id,
                'error': str(e)
            }
    
    async def test_process_state_tracking(self, recipe_id: str) -> Dict[str, Any]:
        """Test process execution state tracking"""
        
        # Query recent process executions for this recipe
        state_query = f"""
        SELECT 
            pe.id as process_execution_id,
            pe.recipe_id,
            pe.status as process_status,
            pe.started_at,
            pe.completed_at,
            pes.id as state_id,
            pes.current_step_id,
            pes.progress_percentage,
            pes.valve_number,
            pes.duration_ms,
            rs.name as step_name,
            rs.type as step_type
        FROM process_executions pe
        LEFT JOIN process_execution_state pes ON pe.id = pes.process_execution_id
        LEFT JOIN recipe_steps rs ON pes.current_step_id = rs.id
        WHERE pe.recipe_id = '{recipe_id}'
        AND pe.created_at > NOW() - INTERVAL '1 hour'
        ORDER BY pe.started_at DESC, pes.step_start_time DESC
        LIMIT 20;
        """
        
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': state_query}).execute()
            state_records = response.data if response.data else []
            
            if not state_records:
                return {
                    'success': False,
                    'error': 'No process execution state records found',
                    'state_records_count': 0
                }
            
            # Analyze state tracking completeness
            processes_with_states = set()
            complete_state_records = 0
            
            for record in state_records:
                if record['state_id']:
                    processes_with_states.add(record['process_execution_id'])
                    if record['progress_percentage'] == 100:
                        complete_state_records += 1
            
            return {
                'success': len(processes_with_states) > 0,
                'total_state_records': len(state_records),
                'processes_with_states': len(processes_with_states),
                'complete_state_records': complete_state_records,
                'state_tracking_active': len(processes_with_states) > 0,
                'sample_records': state_records[:5]  # Include sample for verification
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'state_records_count': 0
            }
    
    async def test_step_configuration_loading(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test step configuration loading capabilities"""
        
        try:
            config_tests = []
            successful_configs = 0
            
            for step in steps[:10]:  # Test first 10 steps
                step_type = step['type']
                config_test = {
                    'step_id': step['id'],
                    'step_name': step['name'],
                    'step_type': step_type,
                    'config_loaded': False,
                    'config_data': None
                }
                
                # Test configuration loading based on step type
                if step_type == 'valve' and step['valve_number'] is not None:
                    config_test['config_loaded'] = True
                    config_test['config_data'] = {
                        'valve_number': step['valve_number'],
                        'duration_ms': step['valve_duration_ms']
                    }
                    successful_configs += 1
                    
                elif step_type == 'purge' and step['gas_type'] is not None:
                    config_test['config_loaded'] = True
                    config_test['config_data'] = {
                        'gas_type': step['gas_type'],
                        'duration_ms': step['purge_duration_ms'],
                        'flow_rate': step['purge_flow_rate']
                    }
                    successful_configs += 1
                    
                elif step_type == 'loop' and step['iteration_count'] is not None:
                    config_test['config_loaded'] = True
                    config_test['config_data'] = {
                        'iteration_count': step['iteration_count'],
                        'inner_steps': step['inner_steps']
                    }
                    successful_configs += 1
                    
                elif step_type == 'parameter':
                    config_test['config_loaded'] = True
                    config_test['config_data'] = {'type': 'parameter_step'}
                    successful_configs += 1
                
                config_tests.append(config_test)
            
            config_success_rate = successful_configs / len(config_tests) if config_tests else 0
            
            return {
                'success': config_success_rate >= 0.8,
                'total_configs_tested': len(config_tests),
                'successful_configs': successful_configs,
                'config_success_rate': config_success_rate,
                'configuration_tests': config_tests
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_configs_tested': 0
            }
    
    def calculate_test_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for all test results"""
        
        total_recipes = len(test_results)
        successful_recipes = sum(1 for result in test_results if result['overall_success'])
        failed_recipes = total_recipes - successful_recipes
        
        # Phase success statistics
        phase_stats = {}
        all_phases = set()
        
        for result in test_results:
            for phase_name, phase_result in result['test_phases'].items():
                all_phases.add(phase_name)
                if phase_name not in phase_stats:
                    phase_stats[phase_name] = {'passed': 0, 'failed': 0}
                
                if phase_result.get('success', False):
                    phase_stats[phase_name]['passed'] += 1
                else:
                    phase_stats[phase_name]['failed'] += 1
        
        return {
            'total_recipes_tested': total_recipes,
            'successful_recipes': successful_recipes,
            'failed_recipes': failed_recipes,
            'overall_success_rate': successful_recipes / total_recipes if total_recipes > 0 else 0,
            'all_passed': failed_recipes == 0,
            'phase_statistics': phase_stats,
            'total_phases_tested': len(all_phases)
        }

async def main():
    """Main execution function"""
    tester = EndToEndRecipeTest()
    results = await tester.execute_comprehensive_e2e_tests()
    
    print("\n" + "="*80)
    print("🎯 END-TO-END RECIPE TESTING - COMPLETE")
    print("="*80)
    print(f"Overall Status: {results['overall_status']}")
    print(f"Recipes Tested: {results.get('total_test_recipes', 0)}")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"Success Rate: {summary.get('overall_success_rate', 0):.2%}")
        print(f"Successful Recipes: {summary.get('successful_recipes', 0)}")
        print(f"Failed Recipes: {summary.get('failed_recipes', 0)}")
    
    print("="*80)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())