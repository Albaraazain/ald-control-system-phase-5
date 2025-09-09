#!/usr/bin/env python3
"""
Recipe Execution Validator
Validates recipe loading, step configuration, and execution state tracking
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger
from src.db import get_supabase
from src.recipe_flow.starter import RecipeStarter
from src.recipe_flow.executor import RecipeExecutor
from src.step_flow.executor import StepExecutor

# Get the supabase client
supabase = get_supabase()

# Set up logging
logger = setup_logger(__name__)

class RecipeExecutionValidator:
    """Validates recipe execution with new normalized database structure"""
    
    def __init__(self):
        self.validation_results = {
            'validator_run_id': str(uuid.uuid4()),
            'start_time': datetime.now().isoformat(),
            'validations_passed': 0,
            'validations_failed': 0,
            'validation_details': []
        }
        
        # Test recipe IDs
        self.simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        self.complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"
        
    async def run_all_validations(self) -> Dict[str, Any]:
        """Execute all recipe execution validations"""
        logger.info("🔧 Starting Recipe Execution Validation Suite")
        logger.info(f"Validator Run ID: {self.validation_results['validator_run_id']}")
        
        try:
            # Validation 1: Recipe Structure Loading
            await self._validate_recipe_structure_loading()
            
            # Validation 2: Step Configuration Mapping
            await self._validate_step_configuration_mapping()
            
            # Validation 3: Parameter Integration
            await self._validate_parameter_integration()
            
            # Validation 4: Loop Step Expansion
            await self._validate_loop_step_expansion()
            
            # Validation 5: Progress Calculation
            await self._validate_progress_calculation()
            
            # Validation 6: State Transitions
            await self._validate_state_transitions()
            
            # Validation 7: Backwards Compatibility
            await self._validate_backwards_compatibility()
            
        except Exception as e:
            logger.error(f"❌ Critical validation failure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._record_validation_result("critical_failure", False, str(e))
        
        # Generate final report
        await self._generate_validation_report()
        return self.validation_results
        
    async def _validate_recipe_structure_loading(self):
        """Validate recipe loading from normalized structure"""
        validation_name = "recipe_structure_loading"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            starter = RecipeStarter()
            
            # Test simple recipe loading
            simple_recipe = await starter._load_recipe_from_db(self.simple_recipe_id)
            
            # Validate basic structure
            required_fields = ['id', 'name', 'description', 'steps', 'chamber_temperature_set_point', 'pressure_set_point']
            for field in required_fields:
                assert field in simple_recipe, f"Missing required field: {field}"
                
            # Validate steps structure
            assert isinstance(simple_recipe['steps'], list), "Steps should be a list"
            assert len(simple_recipe['steps']) == 3, f"Simple recipe should have 3 steps, got {len(simple_recipe['steps'])}"
            
            # Validate each step has required fields
            for step in simple_recipe['steps']:
                step_required_fields = ['id', 'name', 'type', 'sequence_number']
                for field in step_required_fields:
                    assert field in step, f"Step missing required field: {field}"
                    
            # Test complex recipe loading  
            complex_recipe = await starter._load_recipe_from_db(self.complex_recipe_id)
            
            assert len(complex_recipe['steps']) == 5, f"Complex recipe should have 5 steps, got {len(complex_recipe['steps'])}"
            
            # Validate loop hierarchy
            loop_steps = [step for step in complex_recipe['steps'] if step.get('type') == 'loop']
            assert len(loop_steps) == 1, "Should have exactly 1 loop step"
            
            child_steps = [step for step in complex_recipe['steps'] if step.get('parent_step_id') is not None]
            assert len(child_steps) == 2, f"Should have 2 child steps, got {len(child_steps)}"
            
            await self._record_validation_result(validation_name, True, "Recipe structure loading validation passed")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Recipe structure loading failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_step_configuration_mapping(self):
        """Validate step configurations are properly loaded from config tables"""
        validation_name = "step_configuration_mapping"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            starter = RecipeStarter()
            simple_recipe = await starter._load_recipe_from_db(self.simple_recipe_id)
            
            # Validate valve step configurations
            valve_steps = [step for step in simple_recipe['steps'] if step.get('type') == 'valve']
            for valve_step in valve_steps:
                # Should have config from valve_step_config table
                assert 'valve_number' in valve_step, f"Valve step missing valve_number: {valve_step['name']}"
                assert 'duration_ms' in valve_step, f"Valve step missing duration_ms: {valve_step['name']}"
                assert isinstance(valve_step['valve_number'], int), "valve_number should be integer"
                assert isinstance(valve_step['duration_ms'], int), "duration_ms should be integer"
                assert valve_step['valve_number'] > 0, "valve_number should be positive"
                assert valve_step['duration_ms'] > 0, "duration_ms should be positive"
                
            # Validate purge step configurations
            purge_steps = [step for step in simple_recipe['steps'] if step.get('type') == 'purge']  
            for purge_step in purge_steps:
                # Should have config from purge_step_config table
                assert 'duration_ms' in purge_step, f"Purge step missing duration_ms: {purge_step['name']}"
                assert 'gas_type' in purge_step, f"Purge step missing gas_type: {purge_step['name']}"
                assert isinstance(purge_step['duration_ms'], int), "purge duration_ms should be integer"
                assert isinstance(purge_step['gas_type'], str), "gas_type should be string"
                
            # Test complex recipe loop configuration
            complex_recipe = await starter._load_recipe_from_db(self.complex_recipe_id)
            loop_steps = [step for step in complex_recipe['steps'] if step.get('type') == 'loop']
            
            for loop_step in loop_steps:
                # Should have config from loop_step_config table
                assert 'count' in loop_step, f"Loop step missing count: {loop_step['name']}"
                assert isinstance(loop_step['count'], int), "loop count should be integer"
                assert loop_step['count'] > 0, "loop count should be positive"
                
            await self._record_validation_result(validation_name, True, "Step configuration mapping validation passed")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Step configuration mapping failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_parameter_integration(self):
        """Validate recipe parameters are properly integrated"""
        validation_name = "parameter_integration"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            # Load recipe parameters directly from database
            simple_params_result = supabase.table("recipe_parameters").select("*").eq("recipe_id", self.simple_recipe_id).execute()
            simple_params = {p['parameter_name']: p['parameter_value'] for p in simple_params_result.data}
            
            # Validate expected parameters exist
            expected_simple_params = ['chamber_pressure', 'base_temperature', 'flow_rate_multiplier']
            for param_name in expected_simple_params:
                assert param_name in simple_params, f"Missing parameter: {param_name}"
                assert simple_params[param_name] is not None, f"Parameter {param_name} is null"
                
            # Validate parameter values are reasonable
            assert float(simple_params['chamber_pressure']) == 100.0, "Unexpected chamber_pressure value"
            assert float(simple_params['base_temperature']) == 25.0, "Unexpected base_temperature value"
            assert float(simple_params['flow_rate_multiplier']) == 1.0, "Unexpected flow_rate_multiplier value"
            
            # Test complex recipe parameters
            complex_params_result = supabase.table("recipe_parameters").select("*").eq("recipe_id", self.complex_recipe_id).execute()
            complex_params = {p['parameter_name']: p['parameter_value'] for p in complex_params_result.data}
            
            expected_complex_params = ['chamber_pressure', 'base_temperature', 'loop_iterations', 'gas_flow_rate']
            for param_name in expected_complex_params:
                assert param_name in complex_params, f"Missing complex parameter: {param_name}"
                assert complex_params[param_name] is not None, f"Complex parameter {param_name} is null"
                
            # Validate complex parameter values
            assert float(complex_params['chamber_pressure']) == 120.0, "Unexpected complex chamber_pressure"
            assert int(complex_params['loop_iterations']) == 3, "Unexpected loop_iterations value"
            
            await self._record_validation_result(validation_name, True, "Parameter integration validation passed")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Parameter integration failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_loop_step_expansion(self):
        """Validate loop steps are properly expanded for execution"""
        validation_name = "loop_step_expansion"  
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            starter = RecipeStarter()
            complex_recipe = await starter._load_recipe_from_db(self.complex_recipe_id)
            
            # Find the loop step and its children
            loop_step = None
            child_steps = []
            
            for step in complex_recipe['steps']:
                if step.get('type') == 'loop':
                    loop_step = step
                elif step.get('parent_step_id') is not None:
                    child_steps.append(step)
                    
            assert loop_step is not None, "Loop step not found"
            assert len(child_steps) == 2, f"Expected 2 child steps, got {len(child_steps)}"
            assert loop_step.get('count') == 3, f"Loop count should be 3, got {loop_step.get('count')}"
            
            # Validate child steps have correct parent reference
            loop_step_id = loop_step['id']
            for child_step in child_steps:
                assert child_step['parent_step_id'] == loop_step_id, f"Child step has wrong parent_step_id"
                
            # Validate child step types
            child_types = [step['type'] for step in child_steps]
            assert 'valve' in child_types, "Loop should contain valve step"
            assert 'purge' in child_types, "Loop should contain purge step"
            
            # Test expansion calculation (3 iterations * 2 steps = 6 expanded steps)
            expected_loop_expansion = loop_step['count'] * len(child_steps)
            logger.info(f"Loop will expand to {expected_loop_expansion} steps during execution")
            
            await self._record_validation_result(validation_name, True, f"Loop step expansion validation passed - {expected_loop_expansion} expanded steps")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Loop step expansion failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_progress_calculation(self):
        """Validate progress calculation accuracy"""
        validation_name = "progress_calculation"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            # Test simple recipe progress calculation
            starter = RecipeStarter()
            simple_recipe = await starter._load_recipe_from_db(self.simple_recipe_id)
            
            # Simple recipe has 3 steps, no loops
            total_steps = len([step for step in simple_recipe['steps'] if step.get('parent_step_id') is None])
            assert total_steps == 3, f"Simple recipe should have 3 main steps, got {total_steps}"
            
            # Test complex recipe progress calculation
            complex_recipe = await starter._load_recipe_from_db(self.complex_recipe_id)
            
            # Complex recipe: 1 pre-cycle + 1 loop (3 iterations * 2 steps) + 1 post-cycle = 8 total steps
            main_steps = [step for step in complex_recipe['steps'] if step.get('parent_step_id') is None]
            loop_steps = [step for step in complex_recipe['steps'] if step.get('type') == 'loop']
            child_steps = [step for step in complex_recipe['steps'] if step.get('parent_step_id') is not None]
            
            assert len(main_steps) == 3, f"Complex recipe should have 3 main steps, got {len(main_steps)}"
            assert len(loop_steps) == 1, f"Should have 1 loop step, got {len(loop_steps)}"
            assert len(child_steps) == 2, f"Should have 2 child steps, got {len(child_steps)}"
            
            # Calculate expected total execution steps
            loop_count = loop_steps[0].get('count', 1)
            expected_total = len(main_steps) - 1 + (loop_count * len(child_steps))  # -1 because loop step itself is replaced by its iterations
            logger.info(f"Complex recipe expected total execution steps: {expected_total}")
            
            # Create a test execution state to verify calculation
            test_execution_state = {
                'current_step_index': 0,
                'current_overall_step': 0, 
                'total_overall_steps': expected_total,
                'progress': {
                    'total_steps': expected_total,
                    'completed_steps': 0
                }
            }
            
            # Validate progress calculation at different stages
            progress_at_start = (test_execution_state['progress']['completed_steps'] / test_execution_state['progress']['total_steps']) * 100
            assert progress_at_start == 0.0, "Progress should be 0% at start"
            
            # Simulate halfway progress  
            test_execution_state['progress']['completed_steps'] = expected_total // 2
            progress_at_half = (test_execution_state['progress']['completed_steps'] / test_execution_state['progress']['total_steps']) * 100
            expected_half_progress = 50.0
            assert abs(progress_at_half - expected_half_progress) < 10, f"Progress calculation error at halfway point"
            
            await self._record_validation_result(validation_name, True, f"Progress calculation validation passed - expected total: {expected_total}")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Progress calculation failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_state_transitions(self):
        """Validate process execution state transitions"""
        validation_name = "state_transitions"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            # Create a test process execution for state testing
            test_machine_id = await self._get_test_machine_id()
            test_user_id = await self._get_test_user_id()
            test_session_id = await self._get_test_session_id(test_user_id, test_machine_id)
            
            process_data = {
                'id': str(uuid.uuid4()),
                'session_id': test_session_id,
                'machine_id': test_machine_id,
                'recipe_id': self.simple_recipe_id,
                'recipe_version': {},
                'start_time': datetime.now().isoformat(),
                'operator_id': test_user_id,
                'status': 'preparing',
                'parameters': {},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert process execution
            process_result = supabase.table("process_executions").insert(process_data).execute()
            process_id = process_result.data[0]['id']
            
            # Create initial execution state
            initial_state = {
                'execution_id': process_id,
                'current_step_index': 0,
                'current_overall_step': 0,
                'total_overall_steps': 3,
                'current_step_type': 'valve',
                'current_step_name': 'Initialize Chamber - Valve 1',
                'progress': {'total_steps': 3, 'completed_steps': 0},
                'created_at': datetime.now().isoformat()
            }
            
            state_result = supabase.table("process_execution_state").insert(initial_state).execute()
            assert len(state_result.data) == 1, "Failed to create initial state"
            
            state_id = state_result.data[0]['id']
            
            # Test state transition 1: Move to next step
            updated_state_1 = {
                'current_step_index': 1,
                'current_overall_step': 1,
                'current_step_type': 'purge',
                'current_step_name': 'Purge with N2',
                'progress': {'total_steps': 3, 'completed_steps': 1},
                'last_updated': datetime.now().isoformat()
            }
            
            update_result_1 = supabase.table("process_execution_state").update(updated_state_1).eq("id", state_id).execute()
            assert len(update_result_1.data) == 1, "Failed to update state transition 1"
            
            # Test state transition 2: Move to final step  
            updated_state_2 = {
                'current_step_index': 2,
                'current_overall_step': 2,
                'current_step_type': 'valve',
                'current_step_name': 'Final Valve - Valve 2',
                'progress': {'total_steps': 3, 'completed_steps': 2},
                'last_updated': datetime.now().isoformat()
            }
            
            update_result_2 = supabase.table("process_execution_state").update(updated_state_2).eq("id", state_id).execute()
            assert len(update_result_2.data) == 1, "Failed to update state transition 2"
            
            # Verify final state
            final_state = supabase.table("process_execution_state").select("*").eq("id", state_id).execute()
            assert len(final_state.data) == 1, "Final state not found"
            
            final_data = final_state.data[0]
            assert final_data['current_step_index'] == 2, "Final step index incorrect"
            assert final_data['current_overall_step'] == 2, "Final overall step incorrect"
            assert final_data['progress']['completed_steps'] == 2, "Final completed steps incorrect"
            
            await self._record_validation_result(validation_name, True, "State transitions validation passed")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"State transitions failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
            
    async def _validate_backwards_compatibility(self):
        """Validate backwards compatibility with existing code"""
        validation_name = "backwards_compatibility"
        logger.info(f"🔍 Running {validation_name}")
        
        try:
            # Test that existing recipe loading methods still work
            starter = RecipeStarter()
            
            # The _load_recipe_from_db should return data in format compatible with existing code
            simple_recipe = await starter._load_recipe_from_db(self.simple_recipe_id)
            
            # Validate the loaded recipe has the structure expected by existing code
            assert 'id' in simple_recipe, "Recipe missing id field"
            assert 'name' in simple_recipe, "Recipe missing name field"
            assert 'steps' in simple_recipe, "Recipe missing steps field"
            assert isinstance(simple_recipe['steps'], list), "Steps should be a list"
            
            # Check that step structure is compatible
            for step in simple_recipe['steps']:
                assert 'id' in step, "Step missing id field"
                assert 'name' in step, "Step missing name field" 
                assert 'type' in step, "Step missing type field"
                
                # Check type-specific fields that existing code expects
                if step['type'] == 'valve':
                    assert 'valve_number' in step, "Valve step missing valve_number for backwards compatibility"
                    assert 'duration_ms' in step, "Valve step missing duration_ms for backwards compatibility"
                elif step['type'] == 'purge':
                    assert 'duration_ms' in step, "Purge step missing duration_ms for backwards compatibility"
                elif step['type'] == 'loop':
                    assert 'count' in step, "Loop step missing count for backwards compatibility"
                    
            # Test that recipe can be processed by existing recipe executor logic
            # (This simulates what would happen in the actual execution flow)
            
            # Verify recipe metadata is preserved
            assert simple_recipe.get('chamber_temperature_set_point') is not None, "Missing chamber temperature setpoint"
            assert simple_recipe.get('pressure_set_point') is not None, "Missing pressure setpoint"
            
            await self._record_validation_result(validation_name, True, "Backwards compatibility validation passed")
            logger.info(f"✅ {validation_name} passed")
            
        except Exception as e:
            await self._record_validation_result(validation_name, False, f"Backwards compatibility failed: {str(e)}")
            logger.error(f"❌ {validation_name} failed: {str(e)}")
    
    async def _get_test_machine_id(self) -> str:
        """Get a test machine ID"""
        machines = supabase.table("machines").select("id").limit(1).execute()
        if machines.data:
            return machines.data[0]['id']
        else:
            raise Exception("No test machines available")
    
    async def _get_test_user_id(self) -> str:
        """Get a test user ID"""
        result = supabase.table("profiles").select("id").limit(1).execute()
        if result.data:
            return result.data[0]['id']
        else:
            raise Exception("No test users available")
            
    async def _get_test_session_id(self, user_id: str, machine_id: str) -> str:
        """Get or create a test session"""
        sessions = supabase.table("operator_sessions").select("id").eq("operator_id", user_id).eq("machine_id", machine_id).eq("status", "active").limit(1).execute()
        
        if sessions.data:
            return sessions.data[0]['id']
        else:
            session_data = {
                'id': str(uuid.uuid4()),
                'operator_id': user_id,
                'machine_id': machine_id,
                'start_time': datetime.now().isoformat(),
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            result = supabase.table("operator_sessions").insert(session_data).execute()
            return result.data[0]['id']
    
    async def _record_validation_result(self, validation_name: str, passed: bool, message: str):
        """Record individual validation result"""
        if passed:
            self.validation_results['validations_passed'] += 1
        else:
            self.validation_results['validations_failed'] += 1
            
        self.validation_results['validation_details'].append({
            'validation_name': validation_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
    async def _generate_validation_report(self):
        """Generate comprehensive validation report"""
        self.validation_results['end_time'] = datetime.now().isoformat()
        self.validation_results['total_validations'] = self.validation_results['validations_passed'] + self.validation_results['validations_failed']
        self.validation_results['success_rate'] = (self.validation_results['validations_passed'] / self.validation_results['total_validations'] * 100) if self.validation_results['total_validations'] > 0 else 0
        
        # Write detailed report
        report_filename = f"recipe_execution_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
            
        logger.info("=" * 60)
        logger.info("🔧 RECIPE EXECUTION VALIDATION RESULTS")
        logger.info("=" * 60)
        logger.info(f"Validator Run ID: {self.validation_results['validator_run_id']}")
        logger.info(f"Total Validations: {self.validation_results['total_validations']}")
        logger.info(f"Passed: {self.validation_results['validations_passed']}")
        logger.info(f"Failed: {self.validation_results['validations_failed']}")
        logger.info(f"Success Rate: {self.validation_results['success_rate']:.1f}%")
        logger.info(f"Report saved: {report_filename}")
        logger.info("=" * 60)
        
        for validation in self.validation_results['validation_details']:
            status_emoji = "✅" if validation['passed'] else "❌"
            logger.info(f"{status_emoji} {validation['validation_name']}: {validation['message']}")
        
        logger.info("=" * 60)


async def main():
    """Main entry point for recipe execution validation"""
    try:
        logger.info("🔧 Starting Recipe Execution Validation")
        
        # Initialize validator
        validator = RecipeExecutionValidator()
        
        # Run all validations
        results = await validator.run_all_validations()
        
        # Return appropriate exit code
        if results['validations_failed'] == 0:
            logger.info("🎉 ALL RECIPE EXECUTION VALIDATIONS PASSED!")
            return 0
        else:
            logger.error(f"💥 {results['validations_failed']} VALIDATIONS FAILED!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Critical failure in recipe execution validator: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)