#!/usr/bin/env python
"""
Test script to verify the updated PLC parameter loading with component_parameter_definitions join.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_supabase
from log_setup import logger

async def test_parameter_loading():
    """Test loading parameters with the new database structure."""
    try:
        supabase = get_supabase()
        
        # Test the new query with join to component_parameter_definitions
        print("\n=== Testing component_parameters with definition join ===")
        result = supabase.table('component_parameters').select(
            '*, component_parameter_definitions!definition_id(name, unit, description)'
        ).execute()
        
        if result.data:
            print(f"Successfully loaded {len(result.data)} parameters")
            
            # Show a few examples
            print("\nSample parameters with definitions:")
            for i, param in enumerate(result.data[:3]):
                print(f"\nParameter {i+1}:")
                print(f"  ID: {param['id']}")
                print(f"  Component: {param.get('component_name', 'N/A')}")
                print(f"  Original name: {param.get('name', 'N/A')}")
                
                # Check if definition data is available
                definition = param.get('component_parameter_definitions', {})
                if definition:
                    print(f"  Definition data:")
                    print(f"    Name: {definition.get('name', 'N/A')}")
                    print(f"    Unit: {definition.get('unit', 'N/A')}")
                    print(f"    Description: {definition.get('description', 'N/A')}")
                else:
                    print("  No definition data linked")
                    
                print(f"  Modbus address: {param.get('modbus_address', 'N/A')}")
                print(f"  Data type: {param.get('data_type', 'N/A')}")
        else:
            print("No parameters found in database")
            
        # Test specifically for valve parameters
        print("\n=== Testing valve parameters ===")
        valve_params = []
        for param in result.data:
            definition = param.get('component_parameter_definitions', {})
            param_name = definition.get('name') if definition else param.get('name')
            
            if ((param_name == 'valve_state' or param.get('name') == 'valve_state') and 
                param.get('component_name', '').lower().startswith('valve')):
                valve_params.append(param)
        
        print(f"Found {len(valve_params)} valve parameters")
        
        # Test for purge parameters
        print("\n=== Testing purge parameters ===")
        purge_params = []
        for param in result.data:
            definition = param.get('component_parameter_definitions', {})
            param_name = definition.get('name') if definition else param.get('name', '')
            
            if ('purge' in param_name.lower() or
                'purge' in param.get('name', '').lower() or
                'purge' in param.get('component_name', '').lower() or
                param.get('operand') == 'W_Purge'):
                purge_params.append(param)
        
        print(f"Found {len(purge_params)} purge parameters")
        
        print("\n✅ All database queries working with new structure!")
        
    except Exception as e:
        print(f"\n❌ Error testing parameter loading: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_parameter_loading())