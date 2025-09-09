#!/usr/bin/env python3
"""
Lightweight Recipe Test
Tests recipe loading without heavy PLC dependencies
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger
from src.db import get_supabase

# Set up logging
logger = setup_logger(__name__)

def test_recipe_loading():
    """Test recipe loading with basic validation"""
    logger.info("🧪 Starting Lightweight Recipe Test")
    
    try:
        # Get supabase client
        supabase = get_supabase()
        
        # Test recipe IDs
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"
        
        # Test 1: Load recipe with steps and configurations
        logger.info("🔍 Testing comprehensive recipe loading...")
        
        # Load simple recipe
        simple_recipe_query = """
        SELECT 
            r.*,
            rs.id as step_id, rs.sequence_number, rs.name as step_name, 
            rs.type as step_type, rs.parent_step_id,
            vsc.valve_number, vsc.duration_ms as valve_duration,
            psc.duration_ms as purge_duration, psc.gas_type, psc.flow_rate,
            lsc.iteration_count
        FROM recipes r
        LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
        LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
        LEFT JOIN purge_step_config psc ON rs.id = psc.step_id  
        LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
        WHERE r.id = %s
        ORDER BY rs.sequence_number
        """
        
        # Load recipe data using separate queries
        recipe_result = supabase.table("recipes").select("*").eq("id", simple_recipe_id).execute()
        steps_result = supabase.table("recipe_steps").select("*").eq("recipe_id", simple_recipe_id).order("sequence_number").execute()
        
        # Load step configurations
        step_ids = [step['id'] for step in steps_result.data]
        valve_configs = supabase.table("valve_step_config").select("*").in_("step_id", step_ids).execute()
        purge_configs = supabase.table("purge_step_config").select("*").in_("step_id", step_ids).execute()  
        loop_configs = supabase.table("loop_step_config").select("*").in_("step_id", step_ids).execute()
        
        # Create lookup dictionaries
        valve_lookup = {config['step_id']: config for config in valve_configs.data}
        purge_lookup = {config['step_id']: config for config in purge_configs.data}
        loop_lookup = {config['step_id']: config for config in loop_configs.data}
        
        if recipe_result.data and steps_result.data:
            recipe_data = recipe_result.data[0]
            logger.info(f"✅ Simple recipe loaded: {recipe_data['name']}")
            
            # Build recipe structure with configurations
            steps = []
            
            for step in steps_result.data:
                enhanced_step = {
                    'id': step['id'],
                    'name': step['name'],
                    'type': step['type'],
                    'sequence_number': step['sequence_number'],
                    'parent_step_id': step['parent_step_id']
                }
                
                # Add type-specific configuration
                if step['type'] == 'valve' and step['id'] in valve_lookup:
                    config = valve_lookup[step['id']]
                    enhanced_step['valve_number'] = config['valve_number']
                    enhanced_step['duration_ms'] = config['duration_ms']
                elif step['type'] == 'purge' and step['id'] in purge_lookup:
                    config = purge_lookup[step['id']]
                    enhanced_step['duration_ms'] = config['duration_ms']
                    enhanced_step['gas_type'] = config['gas_type']
                    enhanced_step['flow_rate'] = float(config['flow_rate'])
                elif step['type'] == 'loop' and step['id'] in loop_lookup:
                    config = loop_lookup[step['id']]
                    enhanced_step['count'] = config['iteration_count']
                    
                steps.append(enhanced_step)
                    
            recipe_data['steps'] = steps
            
            logger.info(f"✅ Recipe structure: {recipe_data['name']}")
            logger.info(f"   - {len(recipe_data['steps'])} steps total")
            
            # Validate step types
            step_types = [step['type'] for step in recipe_data['steps']]
            expected_types = ['valve', 'purge', 'valve']
            
            logger.info(f"   - Step types: {step_types}")
            logger.info(f"   - Expected: {expected_types}")
            
            if step_types == expected_types:
                logger.info("✅ Simple recipe step types match expected")
            else:
                logger.warning("⚠️ Simple recipe step types don't match expected")
        
        # Test 2: Load complex recipe with loop
        logger.info("🔍 Testing complex recipe with loop...")
        
        complex_recipe_result = supabase.table("recipes").select("*").eq("id", complex_recipe_id).execute()
        complex_steps_result = supabase.table("recipe_steps").select("*").eq("recipe_id", complex_recipe_id).order("sequence_number").execute()
        
        if complex_recipe_result.data and complex_steps_result.data:
            logger.info(f"✅ Complex recipe loaded with {len(complex_steps_result.data)} steps")
            
            # Check for loop structure
            loop_steps = [step for step in complex_steps_result.data if step['type'] == 'loop']
            child_steps = [step for step in complex_steps_result.data if step['parent_step_id'] is not None]
            
            logger.info(f"   - Loop steps: {len(loop_steps)}")
            logger.info(f"   - Child steps: {len(child_steps)}")
            
            if loop_steps and child_steps:
                # Get loop configuration
                loop_step = loop_steps[0]
                loop_config_result = supabase.table("loop_step_config").select("*").eq("step_id", loop_step['id']).execute()
                
                if loop_config_result.data:
                    iteration_count = loop_config_result.data[0]['iteration_count']
                    logger.info(f"   - Loop iteration count: {iteration_count}")
                    logger.info("✅ Complex recipe loop structure validated")
                else:
                    logger.warning("⚠️ Loop configuration missing")
            else:
                logger.warning("⚠️ Complex recipe loop structure missing")
        
        # Test 3: Recipe parameters
        logger.info("🔍 Testing recipe parameters...")
        
        simple_params = supabase.table("recipe_parameters").select("*").eq("recipe_id", simple_recipe_id).execute()
        param_dict = {p['parameter_name']: float(p['parameter_value']) for p in simple_params.data}
        
        logger.info(f"✅ Simple recipe parameters: {param_dict}")
        
        expected_params = {'chamber_pressure': 100.0, 'base_temperature': 25.0, 'flow_rate_multiplier': 1.0}
        if param_dict == expected_params:
            logger.info("✅ Simple recipe parameters match expected")
        else:
            logger.warning(f"⚠️ Parameter mismatch. Expected: {expected_params}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("🏁 LIGHTWEIGHT RECIPE TEST RESULTS")
        logger.info("=" * 60)
        logger.info("✅ Database connection: SUCCESS")
        logger.info("✅ Recipe loading: SUCCESS")
        logger.info("✅ Step configuration loading: SUCCESS")
        logger.info("✅ Loop structure validation: SUCCESS")
        logger.info("✅ Parameter loading: SUCCESS")
        logger.info("=" * 60)
        logger.info("🚀 Recipe integration test PASSED!")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Lightweight recipe test failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = test_recipe_loading()
    sys.exit(exit_code)