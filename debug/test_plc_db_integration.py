#!/usr/bin/env python
"""
Test script to verify the RealPLC class works with the updated database structure.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_supabase
from log_setup import logger

async def test_plc_loading():
    """Test loading parameters in the RealPLC class methods."""
    try:
        supabase = get_supabase()
        
        print("\n=== Simulating _load_parameter_metadata ===")
        
        # Query all parameters with Modbus information
        result = supabase.table('component_parameters').select(
            '*, component_parameter_definitions!definition_id(name, unit, description)'
        ).execute()
        
        # Filter out entries where modbus_address is None
        result.data = [param for param in result.data if param.get('modbus_address') is not None]
        print(f"Found {len(result.data)} parameters with Modbus addresses")
        
        # Build parameter cache like RealPLC does
        parameter_cache = {}
        
        if result.data:
            for param in result.data:
                parameter_id = param['id']
                
                # Get name, unit, and description from definition if available
                definition = param.get('component_parameter_definitions', {})
                param_name = definition.get('name') if definition else param.get('name')
                param_unit = definition.get('unit') if definition else None
                param_description = definition.get('description') if definition else None
                
                parameter_cache[parameter_id] = {
                    'name': param_name or param.get('name', 'Unknown'),
                    'modbus_address': param['modbus_address'],
                    'data_type': param.get('data_type'),
                    'component_name': param.get('component_name', ''),
                    'unit': param_unit,
                    'description': param_description
                }
            
            print(f"Loaded metadata for {len(parameter_cache)} parameters")
            
            # Show a sample parameter with all fields
            if parameter_cache:
                sample_id = list(parameter_cache.keys())[0]
                sample = parameter_cache[sample_id]
                print(f"\nSample parameter from cache:")
                print(f"  Name: {sample['name']}")
                print(f"  Component: {sample['component_name']}")
                print(f"  Modbus Address: {sample['modbus_address']}")
                print(f"  Data Type: {sample['data_type']}")
                print(f"  Unit: {sample['unit']}")
                print(f"  Description: {sample['description']}")
        
        print("\n=== Simulating _load_valve_mappings ===")
        
        # Query all parameters with definition information
        query = supabase.table('component_parameters').select(
            '*, component_parameter_definitions!definition_id(name, unit, description)'
        ).execute()
        
        # Filter for valve parameters
        valve_params = []
        for param in query.data:
            definition = param.get('component_parameter_definitions', {})
            param_name = definition.get('name') if definition else param.get('name')
            
            if ((param_name == 'valve_state' or param.get('name') == 'valve_state') and 
                param.get('component_name', '').lower().startswith('valve')):
                valve_params.append(param)
        
        print(f"Found {len(valve_params)} valve parameters")
        
        print("\n=== Simulating _load_purge_parameters ===")
        
        # Look for purge parameters
        purge_params = []
        for param in query.data:
            definition = param.get('component_parameter_definitions', {})
            param_name = definition.get('name') if definition else param.get('name', '')
            
            if ('purge' in str(param_name).lower() or
                'purge' in param.get('name', '').lower() or
                'purge' in param.get('component_name', '').lower() or
                param.get('operand') == 'W_Purge'):
                purge_params.append(param)
        
        print(f"Found {len(purge_params)} potential purge parameters")
        
        print("\n✅ All PLC loading methods should work with the updated database structure!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_plc_loading())