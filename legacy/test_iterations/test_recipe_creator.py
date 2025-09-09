#!/usr/bin/env python3
"""
Test Recipe Creator - Uses Supabase MCP to create comprehensive test recipes

This module creates structured test recipes for simulation testing,
utilizing the new normalized database schema with type-specific configuration tables.
"""

import asyncio
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

from supabase import create_client, Client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestRecipeCreator:
    """Creates test recipes using Supabase MCP for comprehensive testing"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize the test recipe creator"""
        self.supabase = create_client(supabase_url, supabase_key)
        
    async def create_simple_test_recipe(self, recipe_name: str = "Simple Test Recipe") -> str:
        """Create a simple test recipe with valve and purge steps"""
        logger.info(f"Creating simple test recipe: {recipe_name}")
        
        # Create the main recipe record
        recipe_data = {
            'name': recipe_name,
            'description': 'Simple test recipe for simulation testing - valve + purge sequence',
            'version': 1,
            'is_public': True,
            'machine_type': 'atomic_layer_deposition',
            'substrate': 'silicon',
            'chamber_temperature_set_point': 150.0,
            'pressure_set_point': 0.1,
            'created_by': None  # System-created test recipe
        }
        
        recipe_response = self.supabase.table('recipes').insert(recipe_data).execute()
        
        if not recipe_response.data:
            raise ValueError("Failed to create test recipe")
            
        recipe_id = recipe_response.data[0]['id']
        logger.info(f"Created recipe with ID: {recipe_id}")
        
        # Define recipe steps
        steps = [
            {
                'name': 'Initial Valve Open',
                'description': 'Open valve 1 for initial setup',
                'type': 'valve',
                'sequence_number': 1,
                'valve_config': {
                    'valve_id': 'valve_1',
                    'valve_number': 1,
                    'duration_ms': 5000
                }
            },
            {
                'name': 'N2 Purge',
                'description': 'Purge with nitrogen for 3 seconds',
                'type': 'purge',
                'sequence_number': 2,
                'purge_config': {
                    'duration_ms': 3000,
                    'gas_type': 'N2',
                    'flow_rate': 100.0
                }
            },
            {
                'name': 'Final Valve Close',
                'description': 'Close all valves',
                'type': 'valve',
                'sequence_number': 3,
                'valve_config': {
                    'valve_id': 'valve_1',
                    'valve_number': 1,
                    'duration_ms': 1000
                }
            }
        ]
        
        # Create recipe steps and their configurations
        for step_data in steps:
            await self.create_recipe_step_with_config(recipe_id, step_data)
        
        # Create recipe parameters
        await self.create_recipe_parameters(recipe_id, {
            'temperature': {'value': 150.0, 'unit': 'C', 'type': 'process'},
            'pressure': {'value': 0.1, 'unit': 'Torr', 'type': 'process'},
            'flow_rate': {'value': 100.0, 'unit': 'sccm', 'type': 'gas'}
        })
        
        logger.info(f"Simple test recipe created successfully: {recipe_id}")
        return recipe_id
    
    async def create_loop_test_recipe(self, recipe_name: str = "Loop Test Recipe") -> str:
        """Create a test recipe with loop steps for complex testing"""
        logger.info(f"Creating loop test recipe: {recipe_name}")
        
        # Create the main recipe record
        recipe_data = {
            'name': recipe_name,
            'description': 'Complex test recipe with loops for simulation testing',
            'version': 1,
            'is_public': True,
            'machine_type': 'atomic_layer_deposition',
            'substrate': 'silicon',
            'chamber_temperature_set_point': 200.0,
            'pressure_set_point': 0.05,
            'created_by': None  # System-created test recipe
        }
        
        recipe_response = self.supabase.table('recipes').insert(recipe_data).execute()
        
        if not recipe_response.data:
            raise ValueError("Failed to create loop test recipe")
            
        recipe_id = recipe_response.data[0]['id']
        logger.info(f"Created loop recipe with ID: {recipe_id}")
        
        # Create initial pump step
        await self.create_recipe_step_with_config(recipe_id, {
            'name': 'Initial Pump',
            'description': 'Initial pump down',
            'type': 'valve',
            'sequence_number': 1,
            'valve_config': {
                'valve_id': 'valve_1',
                'valve_number': 1,
                'duration_ms': 2000
            }
        })
        
        # Create loop step
        loop_step_data = {
            'name': 'ALD Cycle Loop',
            'description': 'Main ALD process loop',
            'type': 'loop',
            'sequence_number': 2,
            'loop_config': {
                'iteration_count': 3
            }
        }
        
        loop_step_id = await self.create_recipe_step_with_config(recipe_id, loop_step_data)
        
        # Create sub-steps within the loop
        loop_substeps = [
            {
                'name': 'TMA Pulse',
                'description': 'Trimethylaluminum pulse',
                'type': 'valve',
                'sequence_number': 1,
                'parent_step_id': loop_step_id,
                'valve_config': {
                    'valve_id': 'valve_3',
                    'valve_number': 3,
                    'duration_ms': 500
                }
            },
            {
                'name': 'N2 Purge 1',
                'description': 'First nitrogen purge',
                'type': 'purge',
                'sequence_number': 2,
                'parent_step_id': loop_step_id,
                'purge_config': {
                    'duration_ms': 2000,
                    'gas_type': 'N2',
                    'flow_rate': 150.0
                }
            },
            {
                'name': 'H2O Pulse',
                'description': 'Water pulse',
                'type': 'valve',
                'sequence_number': 3,
                'parent_step_id': loop_step_id,
                'valve_config': {
                    'valve_id': 'valve_4',
                    'valve_number': 4,
                    'duration_ms': 500
                }
            },
            {
                'name': 'N2 Purge 2',
                'description': 'Second nitrogen purge',
                'type': 'purge',
                'sequence_number': 4,
                'parent_step_id': loop_step_id,
                'purge_config': {
                    'duration_ms': 2000,
                    'gas_type': 'N2',
                    'flow_rate': 150.0
                }
            }
        ]
        
        for substep in loop_substeps:
            await self.create_recipe_step_with_config(recipe_id, substep)
        
        # Create final vent step
        await self.create_recipe_step_with_config(recipe_id, {
            'name': 'Final Vent',
            'description': 'Vent chamber',
            'type': 'valve',
            'sequence_number': 3,
            'valve_config': {
                'valve_id': 'valve_5',
                'valve_number': 5,
                'duration_ms': 5000
            }
        })
        
        # Create recipe parameters
        await self.create_recipe_parameters(recipe_id, {
            'temperature': {'value': 200.0, 'unit': 'C', 'type': 'process'},
            'pressure': {'value': 0.05, 'unit': 'Torr', 'type': 'process'},
            'precursor_flow': {'value': 150.0, 'unit': 'sccm', 'type': 'gas'},
            'cycle_count': {'value': 3, 'unit': 'cycles', 'type': 'process'}
        })
        
        logger.info(f"Loop test recipe created successfully: {recipe_id}")
        return recipe_id
    
    async def create_error_scenario_recipe(self, recipe_name: str = "Error Scenario Test Recipe") -> str:
        """Create a recipe designed to test error handling scenarios"""
        logger.info(f"Creating error scenario test recipe: {recipe_name}")
        
        # Create the main recipe record
        recipe_data = {
            'name': recipe_name,
            'description': 'Test recipe designed to trigger error scenarios for robust testing',
            'version': 1,
            'is_public': True,
            'machine_type': 'atomic_layer_deposition',
            'substrate': 'test_substrate',
            'chamber_temperature_set_point': 300.0,  # High temperature to test limits
            'pressure_set_point': 0.001,  # Very low pressure
            'created_by': None  # System-created test recipe
        }
        
        recipe_response = self.supabase.table('recipes').insert(recipe_data).execute()
        
        if not recipe_response.data:
            raise ValueError("Failed to create error scenario test recipe")
            
        recipe_id = recipe_response.data[0]['id']
        logger.info(f"Created error scenario recipe with ID: {recipe_id}")
        
        # Define steps that might trigger various error conditions
        error_steps = [
            {
                'name': 'Rapid Valve Sequence',
                'description': 'Very short valve operations to test timing',
                'type': 'valve',
                'sequence_number': 1,
                'valve_config': {
                    'valve_id': 'valve_1',
                    'valve_number': 1,
                    'duration_ms': 100  # Very short duration
                }
            },
            {
                'name': 'Extended Purge',
                'description': 'Long purge to test timeout handling',
                'type': 'purge',
                'sequence_number': 2,
                'purge_config': {
                    'duration_ms': 10000,  # Long purge
                    'gas_type': 'N2',
                    'flow_rate': 500.0  # High flow rate
                }
            },
            {
                'name': 'Invalid Valve Test',
                'description': 'Test with valve number that might not exist',
                'type': 'valve',
                'sequence_number': 3,
                'valve_config': {
                    'valve_id': 'valve_99',
                    'valve_number': 99,  # Non-existent valve
                    'duration_ms': 1000
                }
            }
        ]
        
        # Create recipe steps and their configurations
        for step_data in error_steps:
            await self.create_recipe_step_with_config(recipe_id, step_data)
        
        # Create recipe parameters with edge case values
        await self.create_recipe_parameters(recipe_id, {
            'temperature': {'value': 300.0, 'unit': 'C', 'type': 'process'},
            'pressure': {'value': 0.001, 'unit': 'Torr', 'type': 'process'},
            'flow_rate': {'value': 500.0, 'unit': 'sccm', 'type': 'gas'},
            'timeout': {'value': 60.0, 'unit': 's', 'type': 'control'}
        })
        
        logger.info(f"Error scenario test recipe created successfully: {recipe_id}")
        return recipe_id
    
    async def create_recipe_step_with_config(self, recipe_id: str, step_data: Dict[str, Any]) -> str:
        """Create a recipe step with its associated configuration"""
        
        # Create the basic recipe step
        basic_step_data = {
            'recipe_id': recipe_id,
            'sequence_number': step_data['sequence_number'],
            'name': step_data['name'],
            'description': step_data.get('description'),
            'type': step_data['type'],
            'parent_step_id': step_data.get('parent_step_id')
        }
        
        step_response = self.supabase.table('recipe_steps').insert(basic_step_data).execute()
        
        if not step_response.data:
            raise ValueError(f"Failed to create recipe step: {step_data['name']}")
        
        step_id = step_response.data[0]['id']
        logger.debug(f"Created step '{step_data['name']}' with ID: {step_id}")
        
        # Create type-specific configuration
        step_type = step_data['type']
        
        if step_type == 'valve' and 'valve_config' in step_data:
            config = step_data['valve_config']
            valve_config_data = {
                'step_id': step_id,
                'valve_id': config['valve_id'],
                'valve_number': config['valve_number'],
                'duration_ms': config['duration_ms']
            }
            
            valve_response = self.supabase.table('valve_step_config').insert(valve_config_data).execute()
            if not valve_response.data:
                raise ValueError(f"Failed to create valve config for step: {step_data['name']}")
                
        elif step_type == 'purge' and 'purge_config' in step_data:
            config = step_data['purge_config']
            purge_config_data = {
                'step_id': step_id,
                'duration_ms': config['duration_ms'],
                'gas_type': config['gas_type'],
                'flow_rate': config['flow_rate']
            }
            
            purge_response = self.supabase.table('purge_step_config').insert(purge_config_data).execute()
            if not purge_response.data:
                raise ValueError(f"Failed to create purge config for step: {step_data['name']}")
                
        elif step_type == 'loop' and 'loop_config' in step_data:
            config = step_data['loop_config']
            loop_config_data = {
                'step_id': step_id,
                'iteration_count': config['iteration_count']
            }
            
            loop_response = self.supabase.table('loop_step_config').insert(loop_config_data).execute()
            if not loop_response.data:
                raise ValueError(f"Failed to create loop config for step: {step_data['name']}")
        
        return step_id
    
    async def create_recipe_parameters(self, recipe_id: str, parameters: Dict[str, Dict[str, Any]]):
        """Create recipe-level parameters"""
        
        for param_name, param_data in parameters.items():
            recipe_param_data = {
                'recipe_id': recipe_id,
                'parameter_name': param_name,
                'parameter_value': param_data['value'],
                'parameter_unit': param_data.get('unit'),
                'parameter_type': param_data.get('type'),
                'min_value': param_data.get('min_value'),
                'max_value': param_data.get('max_value'),
                'is_critical': param_data.get('is_critical', False),
                'tolerance_percentage': param_data.get('tolerance_percentage')
            }
            
            param_response = self.supabase.table('recipe_parameters').insert(recipe_param_data).execute()
            if not param_response.data:
                logger.warning(f"Failed to create recipe parameter: {param_name}")
            else:
                logger.debug(f"Created recipe parameter: {param_name}")
    
    async def create_all_test_recipes(self) -> Dict[str, str]:
        """Create all test recipes and return their IDs"""
        logger.info("Creating comprehensive test recipe suite")
        
        recipe_ids = {}
        
        try:
            # Create simple test recipe
            recipe_ids['simple'] = await self.create_simple_test_recipe("Simulation Test - Simple Recipe")
            
            # Create loop test recipe
            recipe_ids['loop'] = await self.create_loop_test_recipe("Simulation Test - Loop Recipe")
            
            # Create error scenario recipe
            recipe_ids['error'] = await self.create_error_scenario_recipe("Simulation Test - Error Scenarios")
            
            logger.info(f"Successfully created {len(recipe_ids)} test recipes")
            return recipe_ids
            
        except Exception as e:
            logger.error(f"Failed to create test recipes: {str(e)}")
            raise
    
    async def cleanup_test_recipes(self, recipe_ids: List[str]):
        """Clean up test recipes (optional, for test isolation)"""
        logger.info(f"Cleaning up {len(recipe_ids)} test recipes")
        
        for recipe_id in recipe_ids:
            try:
                # Note: Due to foreign key constraints, we need to delete in order:
                # 1. Recipe parameters
                # 2. Step configs (valve_step_config, purge_step_config, loop_step_config)
                # 3. Recipe steps
                # 4. Recipe
                
                # Delete recipe parameters
                self.supabase.table('recipe_parameters').delete().eq('recipe_id', recipe_id).execute()
                
                # Get all steps for this recipe
                steps_response = self.supabase.table('recipe_steps').select('id, type').eq('recipe_id', recipe_id).execute()
                
                if steps_response.data:
                    step_ids = [step['id'] for step in steps_response.data]
                    
                    # Delete step configs
                    for step_id in step_ids:
                        self.supabase.table('valve_step_config').delete().eq('step_id', step_id).execute()
                        self.supabase.table('purge_step_config').delete().eq('step_id', step_id).execute()
                        self.supabase.table('loop_step_config').delete().eq('step_id', step_id).execute()
                    
                    # Delete recipe steps
                    self.supabase.table('recipe_steps').delete().eq('recipe_id', recipe_id).execute()
                
                # Delete recipe
                self.supabase.table('recipes').delete().eq('id', recipe_id).execute()
                
                logger.debug(f"Cleaned up test recipe: {recipe_id}")
                
            except Exception as e:
                logger.warning(f"Failed to clean up recipe {recipe_id}: {str(e)}")

async def main():
    """Main entry point for test recipe creation"""
    # Supabase configuration
    SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
    SUPABASE_KEY = "your_supabase_key_here"  # This should be provided via environment variable
    
    try:
        creator = TestRecipeCreator(SUPABASE_URL, SUPABASE_KEY)
        
        # Create all test recipes
        recipe_ids = await creator.create_all_test_recipes()
        
        # Print results
        print("Test Recipe Creation Results:")
        print("=" * 40)
        for recipe_type, recipe_id in recipe_ids.items():
            print(f"{recipe_type.upper()}: {recipe_id}")
        
        # Save recipe IDs to file for later use
        with open('test_recipe_ids.json', 'w') as f:
            json.dump(recipe_ids, f, indent=2)
        
        print(f"\nRecipe IDs saved to: test_recipe_ids.json")
        return 0
        
    except Exception as e:
        logger.error(f"Test recipe creation failed: {str(e)}")
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)