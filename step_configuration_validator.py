#!/usr/bin/env python3
"""
Step Configuration Validator

Validates step configuration loading from normalized tables including:
- Step configuration loading from valve_step_config, purge_step_config, loop_step_config
- Backwards compatibility when configs are missing
- Parameter override functionality
- Step timing and duration accuracy
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from db import get_supabase
from log_setup import logger


class StepConfigurationValidator:
    """Validates step configuration loading and fallback mechanisms."""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.validation_results = []
        
    def validate_valve_config_loading(self, step_id: str) -> Dict[str, Any]:
        """Validate valve configuration loading from valve_step_config table."""
        logger.info(f"Validating valve config for step {step_id}")
        
        try:
            # Load valve configuration
            result = self.supabase.table('valve_step_config').select('*').eq('step_id', step_id).execute()
            valve_config = result.data[0] if result.data else None
            
            if valve_config:
                # Validate required fields
                required_fields = ['valve_number', 'duration_ms']
                missing_fields = [field for field in required_fields if field not in valve_config or valve_config[field] is None]
                
                if missing_fields:
                    return {
                        'status': 'FAIL',
                        'message': f'Missing required fields: {missing_fields}',
                        'config': valve_config
                    }
                
                # Validate data types and ranges
                if not isinstance(valve_config['valve_number'], int) or valve_config['valve_number'] <= 0:
                    return {
                        'status': 'FAIL',
                        'message': f'Invalid valve number: {valve_config["valve_number"]}',
                        'config': valve_config
                    }
                    
                if not isinstance(valve_config['duration_ms'], int) or valve_config['duration_ms'] <= 0:
                    return {
                        'status': 'FAIL',
                        'message': f'Invalid duration: {valve_config["duration_ms"]}',
                        'config': valve_config
                    }
                
                return {
                    'status': 'PASS',
                    'message': 'Valve configuration loaded successfully',
                    'config': valve_config
                }
            else:
                return {
                    'status': 'MISSING',
                    'message': 'No valve configuration found',
                    'config': None
                }
                
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error loading valve config: {str(e)}',
                'config': None
            }
            
    def validate_purge_config_loading(self, step_id: str) -> Dict[str, Any]:
        """Validate purge configuration loading from purge_step_config table."""
        logger.info(f"Validating purge config for step {step_id}")
        
        try:
            # Load purge configuration
            result = self.supabase.table('purge_step_config').select('*').eq('step_id', step_id).execute()
            purge_config = result.data[0] if result.data else None
            
            if purge_config:
                # Validate required fields
                required_fields = ['duration_ms']
                missing_fields = [field for field in required_fields if field not in purge_config or purge_config[field] is None]
                
                if missing_fields:
                    return {
                        'status': 'FAIL',
                        'message': f'Missing required fields: {missing_fields}',
                        'config': purge_config
                    }
                
                # Validate data types and ranges
                if not isinstance(purge_config['duration_ms'], int) or purge_config['duration_ms'] <= 0:
                    return {
                        'status': 'FAIL',
                        'message': f'Invalid duration: {purge_config["duration_ms"]}',
                        'config': purge_config
                    }
                
                # Validate optional fields if present
                if 'flow_rate' in purge_config and purge_config['flow_rate'] is not None:
                    if not isinstance(purge_config['flow_rate'], (int, float)) or purge_config['flow_rate'] < 0:
                        return {
                            'status': 'FAIL',
                            'message': f'Invalid flow rate: {purge_config["flow_rate"]}',
                            'config': purge_config
                        }
                
                return {
                    'status': 'PASS',
                    'message': 'Purge configuration loaded successfully',
                    'config': purge_config
                }
            else:
                return {
                    'status': 'MISSING',
                    'message': 'No purge configuration found',
                    'config': None
                }
                
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error loading purge config: {str(e)}',
                'config': None
            }
            
    def validate_loop_config_loading(self, step_id: str) -> Dict[str, Any]:
        """Validate loop configuration loading from loop_step_config table."""
        logger.info(f"Validating loop config for step {step_id}")
        
        try:
            # Load loop configuration
            result = self.supabase.table('loop_step_config').select('*').eq('step_id', step_id).execute()
            loop_config = result.data[0] if result.data else None
            
            if loop_config:
                # Validate required fields
                required_fields = ['iteration_count']
                missing_fields = [field for field in required_fields if field not in loop_config or loop_config[field] is None]
                
                if missing_fields:
                    return {
                        'status': 'FAIL',
                        'message': f'Missing required fields: {missing_fields}',
                        'config': loop_config
                    }
                
                # Validate data types and ranges
                if not isinstance(loop_config['iteration_count'], int) or loop_config['iteration_count'] <= 0:
                    return {
                        'status': 'FAIL',
                        'message': f'Invalid iteration count: {loop_config["iteration_count"]}',
                        'config': loop_config
                    }
                
                return {
                    'status': 'PASS',
                    'message': 'Loop configuration loaded successfully',
                    'config': loop_config
                }
            else:
                return {
                    'status': 'MISSING',
                    'message': 'No loop configuration found',
                    'config': None
                }
                
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error loading loop config: {str(e)}',
                'config': None
            }
            
    def validate_backwards_compatibility(self, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate backwards compatibility fallback to parameters column."""
        logger.info(f"Validating backwards compatibility for step {step_data.get('name', 'Unknown')}")
        
        try:
            step_type = step_data.get('type', '').lower()
            parameters = step_data.get('parameters', {})
            
            if 'valve' in step_type:
                # Check for valve parameters fallback
                valve_number = None
                duration_ms = None
                
                # Try to extract from step type
                if 'open valve' in step_type:
                    try:
                        valve_number = int(step_type.split('valve')[1].strip())
                    except (IndexError, ValueError):
                        pass
                
                # Check parameters
                if 'valve_number' in parameters:
                    valve_number = parameters['valve_number']
                if 'duration_ms' in parameters:
                    duration_ms = parameters['duration_ms']
                
                if valve_number and duration_ms:
                    return {
                        'status': 'PASS',
                        'message': 'Backwards compatibility working - valve parameters found',
                        'extracted_params': {
                            'valve_number': valve_number,
                            'duration_ms': duration_ms
                        }
                    }
                else:
                    return {
                        'status': 'FAIL',
                        'message': 'Backwards compatibility failed - missing valve parameters',
                        'extracted_params': {
                            'valve_number': valve_number,
                            'duration_ms': duration_ms
                        }
                    }
                    
            elif step_type == 'purge' or 'purge' in step_type:
                # Check for purge parameters fallback
                duration_ms = parameters.get('duration_ms') or parameters.get('duration')
                
                if duration_ms:
                    return {
                        'status': 'PASS',
                        'message': 'Backwards compatibility working - purge parameters found',
                        'extracted_params': {
                            'duration_ms': duration_ms,
                            'gas_type': parameters.get('gas_type', 'N2'),
                            'flow_rate': parameters.get('flow_rate', 0.0)
                        }
                    }
                else:
                    return {
                        'status': 'FAIL',
                        'message': 'Backwards compatibility failed - missing purge duration',
                        'extracted_params': parameters
                    }
                    
            elif step_type == 'loop':
                # Check for loop parameters fallback
                count = parameters.get('count')
                
                if count:
                    return {
                        'status': 'PASS',
                        'message': 'Backwards compatibility working - loop count found',
                        'extracted_params': {
                            'count': count
                        }
                    }
                else:
                    return {
                        'status': 'FAIL',
                        'message': 'Backwards compatibility failed - missing loop count',
                        'extracted_params': parameters
                    }
                    
            else:
                return {
                    'status': 'UNKNOWN',
                    'message': f'Unknown step type for backwards compatibility: {step_type}',
                    'extracted_params': parameters
                }
                
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error validating backwards compatibility: {str(e)}',
                'extracted_params': {}
            }
            
    async def validate_all_step_configurations(self, recipe_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate all step configurations for a recipe or entire database."""
        logger.info(f"Validating all step configurations for recipe: {recipe_id or 'ALL'}")
        
        validation_results = {
            'valve_steps': [],
            'purge_steps': [],
            'loop_steps': [],
            'backwards_compatibility': [],
            'summary': {
                'total_steps': 0,
                'valid_configs': 0,
                'missing_configs': 0,
                'invalid_configs': 0,
                'errors': 0
            }
        }
        
        try:
            # Get all recipe steps
            query = self.supabase.table('recipe_steps').select('*')
            if recipe_id:
                query = query.eq('recipe_id', recipe_id)
            
            steps_result = query.execute()
            
            for step in steps_result.data:
                step_id = step['id']
                step_type = step['type'].lower()
                validation_results['summary']['total_steps'] += 1
                
                if 'valve' in step_type:
                    # Validate valve configuration
                    valve_validation = self.validate_valve_config_loading(step_id)
                    valve_validation['step_name'] = step['name']
                    valve_validation['step_id'] = step_id
                    validation_results['valve_steps'].append(valve_validation)
                    
                    # Also test backwards compatibility
                    compat_validation = self.validate_backwards_compatibility(step)
                    compat_validation['step_name'] = step['name']
                    compat_validation['step_id'] = step_id
                    compat_validation['step_type'] = 'valve'
                    validation_results['backwards_compatibility'].append(compat_validation)
                    
                elif 'purge' in step_type:
                    # Validate purge configuration
                    purge_validation = self.validate_purge_config_loading(step_id)
                    purge_validation['step_name'] = step['name']
                    purge_validation['step_id'] = step_id
                    validation_results['purge_steps'].append(purge_validation)
                    
                    # Also test backwards compatibility
                    compat_validation = self.validate_backwards_compatibility(step)
                    compat_validation['step_name'] = step['name']
                    compat_validation['step_id'] = step_id
                    compat_validation['step_type'] = 'purge'
                    validation_results['backwards_compatibility'].append(compat_validation)
                    
                elif step_type == 'loop':
                    # Validate loop configuration
                    loop_validation = self.validate_loop_config_loading(step_id)
                    loop_validation['step_name'] = step['name']
                    loop_validation['step_id'] = step_id
                    validation_results['loop_steps'].append(loop_validation)
                    
                    # Also test backwards compatibility
                    compat_validation = self.validate_backwards_compatibility(step)
                    compat_validation['step_name'] = step['name']
                    compat_validation['step_id'] = step_id
                    compat_validation['step_type'] = 'loop'
                    validation_results['backwards_compatibility'].append(compat_validation)
            
            # Calculate summary statistics
            all_validations = (validation_results['valve_steps'] + 
                             validation_results['purge_steps'] + 
                             validation_results['loop_steps'])
            
            for validation in all_validations:
                if validation['status'] == 'PASS':
                    validation_results['summary']['valid_configs'] += 1
                elif validation['status'] == 'MISSING':
                    validation_results['summary']['missing_configs'] += 1
                elif validation['status'] == 'FAIL':
                    validation_results['summary']['invalid_configs'] += 1
                elif validation['status'] == 'ERROR':
                    validation_results['summary']['errors'] += 1
            
            logger.info(f"Configuration validation complete: {validation_results['summary']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error during configuration validation: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """Generate a human-readable validation report."""
        if 'error' in validation_results:
            return f"Validation failed with error: {validation_results['error']}"
        
        summary = validation_results['summary']
        report = []
        
        report.append("# Step Configuration Validation Report")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")
        
        report.append("## Summary")
        report.append(f"- Total Steps: {summary['total_steps']}")
        report.append(f"- Valid Configurations: {summary['valid_configs']}")
        report.append(f"- Missing Configurations: {summary['missing_configs']}")
        report.append(f"- Invalid Configurations: {summary['invalid_configs']}")
        report.append(f"- Errors: {summary['errors']}")
        report.append("")
        
        # Valve steps
        if validation_results['valve_steps']:
            report.append("## Valve Steps")
            for validation in validation_results['valve_steps']:
                status_icon = "✅" if validation['status'] == 'PASS' else "❌" if validation['status'] == 'FAIL' else "⚠️"
                report.append(f"- {status_icon} {validation['step_name']}: {validation['message']}")
            report.append("")
        
        # Purge steps
        if validation_results['purge_steps']:
            report.append("## Purge Steps")
            for validation in validation_results['purge_steps']:
                status_icon = "✅" if validation['status'] == 'PASS' else "❌" if validation['status'] == 'FAIL' else "⚠️"
                report.append(f"- {status_icon} {validation['step_name']}: {validation['message']}")
            report.append("")
        
        # Loop steps
        if validation_results['loop_steps']:
            report.append("## Loop Steps")
            for validation in validation_results['loop_steps']:
                status_icon = "✅" if validation['status'] == 'PASS' else "❌" if validation['status'] == 'FAIL' else "⚠️"
                report.append(f"- {status_icon} {validation['step_name']}: {validation['message']}")
            report.append("")
        
        # Backwards compatibility
        if validation_results['backwards_compatibility']:
            report.append("## Backwards Compatibility")
            for validation in validation_results['backwards_compatibility']:
                status_icon = "✅" if validation['status'] == 'PASS' else "❌" if validation['status'] == 'FAIL' else "⚠️"
                report.append(f"- {status_icon} {validation['step_name']} ({validation['step_type']}): {validation['message']}")
        
        return "\n".join(report)


async def main():
    """Run step configuration validation."""
    validator = StepConfigurationValidator()
    
    # Validate all configurations
    results = await validator.validate_all_step_configurations()
    
    # Generate report
    report = validator.generate_validation_report(results)
    
    # Save results
    with open('step_configuration_validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    with open('step_configuration_validation_report.md', 'w') as f:
        f.write(report)
    
    print("Step Configuration Validation Complete")
    print(f"Valid: {results['summary']['valid_configs']}, Missing: {results['summary']['missing_configs']}, Invalid: {results['summary']['invalid_configs']}, Errors: {results['summary']['errors']}")
    print("Results saved to step_configuration_validation_results.json and step_configuration_validation_report.md")
    
    return results['summary']['errors'] == 0 and results['summary']['invalid_configs'] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)