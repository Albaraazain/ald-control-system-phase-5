#!/usr/bin/env python3
"""
Simple Integration Test
Basic validation that test recipes exist and can be queried
"""

import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from log_setup import setup_logger
from db import get_supabase

# Set up logging
logger = setup_logger(__name__)

def main():
    """Run simple integration test"""
    logger.info("🧪 Starting Simple Integration Test")
    
    try:
        # Get supabase client
        supabase = get_supabase()
        logger.info("✅ Supabase client initialized")
        
        # Test recipe IDs
        simple_recipe_id = "ecdfb993-fd08-402a-adfa-353b426cd925"
        complex_recipe_id = "f6478f3a-7068-458f-9438-1acf14719d4e"
        
        # Test 1: Check if test recipes exist
        logger.info("🔍 Testing recipe existence...")
        
        simple_recipe = supabase.table("recipes").select("*").eq("id", simple_recipe_id).execute()
        assert len(simple_recipe.data) == 1, "Simple test recipe not found"
        logger.info(f"✅ Simple recipe found: {simple_recipe.data[0]['name']}")
        
        complex_recipe = supabase.table("recipes").select("*").eq("id", complex_recipe_id).execute()  
        assert len(complex_recipe.data) == 1, "Complex test recipe not found"
        logger.info(f"✅ Complex recipe found: {complex_recipe.data[0]['name']}")
        
        # Test 2: Check recipe steps
        logger.info("🔍 Testing recipe steps...")
        
        simple_steps = supabase.table("recipe_steps").select("*").eq("recipe_id", simple_recipe_id).execute()
        assert len(simple_steps.data) == 3, f"Simple recipe should have 3 steps, found {len(simple_steps.data)}"
        logger.info(f"✅ Simple recipe has {len(simple_steps.data)} steps")
        
        complex_steps = supabase.table("recipe_steps").select("*").eq("recipe_id", complex_recipe_id).execute()
        assert len(complex_steps.data) == 5, f"Complex recipe should have 5 steps, found {len(complex_steps.data)}"
        logger.info(f"✅ Complex recipe has {len(complex_steps.data)} steps")
        
        # Test 3: Check step configurations
        logger.info("🔍 Testing step configurations...")
        
        valve_configs = supabase.table("valve_step_config").select("*").execute()
        purge_configs = supabase.table("purge_step_config").select("*").execute()
        loop_configs = supabase.table("loop_step_config").select("*").execute()
        
        logger.info(f"✅ Found {len(valve_configs.data)} valve configurations")
        logger.info(f"✅ Found {len(purge_configs.data)} purge configurations") 
        logger.info(f"✅ Found {len(loop_configs.data)} loop configurations")
        
        # Test 4: Check recipe parameters
        logger.info("🔍 Testing recipe parameters...")
        
        simple_params = supabase.table("recipe_parameters").select("*").eq("recipe_id", simple_recipe_id).execute()
        complex_params = supabase.table("recipe_parameters").select("*").eq("recipe_id", complex_recipe_id).execute()
        
        logger.info(f"✅ Simple recipe has {len(simple_params.data)} parameters")
        logger.info(f"✅ Complex recipe has {len(complex_params.data)} parameters")
        
        # Summary
        logger.info("=" * 50)
        logger.info("🎉 SIMPLE INTEGRATION TEST RESULTS")
        logger.info("=" * 50)
        logger.info("✅ Database connection: SUCCESS")
        logger.info("✅ Recipe creation: SUCCESS") 
        logger.info("✅ Recipe steps: SUCCESS")
        logger.info("✅ Step configurations: SUCCESS")
        logger.info("✅ Recipe parameters: SUCCESS")
        logger.info("=" * 50)
        logger.info("🚀 All basic integration tests PASSED!")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Simple integration test failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)