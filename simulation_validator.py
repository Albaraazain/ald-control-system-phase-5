#!/usr/bin/env python3
"""
Simulation Validator - Comprehensive validation of ALD control system execution

This module validates process execution state tracking, database consistency,
and proper implementation of the new normalized database schema.
"""

import asyncio
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import logging

from supabase import create_client, Client
from dataclasses import dataclass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Container for validation results"""
    validation_name: str
    passed: bool
    details: Dict[str, Any]
    errors: List[str]
    warnings: List[str]

class SimulationValidator:
    """Validates simulation execution and database state consistency"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize the simulation validator"""
        self.supabase = create_client(supabase_url, supabase_key)
        
    async def validate_process_execution_state(self, process_id: str) -> ValidationResult:
        """Validate process execution state record and consistency"""
        logger.info(f"Validating process execution state for process: {process_id}")
        
        errors = []
        warnings = []
        details = {}
        
        try:
            # Get process execution record
            process_response = self.supabase.table('process_executions').select('*').eq('id', process_id).execute()
            
            if not process_response.data:
                errors.append("Process execution record not found")
                return ValidationResult(
                    validation_name="Process Execution State",
                    passed=False,
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            process = process_response.data[0]
            details['process_status'] = process['status']
            details['process_start_time'] = process['start_time']
            details['process_end_time'] = process['end_time']
            
            # Get process execution state record
            state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
            
            if not state_response.data:
                errors.append("Process execution state record not found")
            else:
                state = state_response.data[0]
                details['state_record_exists'] = True
                details['current_step_index'] = state['current_step_index']
                details['total_overall_steps'] = state['total_overall_steps']
                details['progress'] = state['progress']
                details['process_metrics'] = state['process_metrics']
                
                # Validate state consistency
                if state['current_step_index'] is not None and state['total_overall_steps'] is not None:
                    if state['current_step_index'] > state['total_overall_steps']:
                        errors.append(f"Current step index ({state['current_step_index']}) exceeds total steps ({state['total_overall_steps']})")
                    
                    if state['current_step_index'] < 0:
                        errors.append(f"Current step index is negative: {state['current_step_index']}")
                
                # Validate progress data
                if state['progress']:
                    progress = state['progress']
                    if 'completed_steps' in progress and 'total_steps' in progress:
                        if progress['completed_steps'] > progress['total_steps']:
                            warnings.append(f"Completed steps ({progress['completed_steps']}) exceeds total ({progress['total_steps']})")
                
                # Validate step-specific data consistency
                if state['current_step_type'] == 'valve':
                    if not state['current_valve_number']:
                        warnings.append("Valve step active but no valve number recorded")
                    if not state['current_valve_duration_ms']:
                        warnings.append("Valve step active but no duration recorded")
                elif state['current_step_type'] == 'purge':
                    if not state['current_purge_duration_ms']:
                        warnings.append("Purge step active but no duration recorded")
                elif state['current_step_type'] == 'loop':
                    if not state['current_loop_count']:
                        warnings.append("Loop step active but no loop count recorded")
            
            # Get recipe and validate step count consistency
            recipe_response = self.supabase.table('recipes').select('*').eq('id', process['recipe_id']).execute()
            
            if recipe_response.data:
                recipe = recipe_response.data[0]
                details['recipe_name'] = recipe['name']
                
                # Get recipe steps
                steps_response = self.supabase.table('recipe_steps').select('*').eq('recipe_id', recipe['id']).order('sequence_number').execute()
                
                if steps_response.data:
                    recipe_step_count = len(steps_response.data)
                    details['recipe_step_count'] = recipe_step_count
                    
                    # Check if state tracking matches recipe structure
                    if state_response.data:
                        state = state_response.data[0]
                        if state['total_overall_steps'] and state['total_overall_steps'] < recipe_step_count:
                            warnings.append(f"Total steps in state ({state['total_overall_steps']}) less than recipe steps ({recipe_step_count})")
            
            passed = len(errors) == 0
            
        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
            passed = False
        
        return ValidationResult(
            validation_name="Process Execution State",
            passed=passed,
            details=details,
            errors=errors,
            warnings=warnings
        )
    
    async def validate_step_configuration_loading(self, process_id: str) -> ValidationResult:
        """Validate that step configurations are properly loaded with new schema"""
        logger.info(f"Validating step configuration loading for process: {process_id}")
        
        errors = []
        warnings = []
        details = {}
        
        try:
            # Get process execution record
            process_response = self.supabase.table('process_executions').select('*').eq('id', process_id).execute()
            
            if not process_response.data:
                errors.append("Process execution record not found")
                return ValidationResult(
                    validation_name="Step Configuration Loading",
                    passed=False,
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            process = process_response.data[0]
            recipe_id = process['recipe_id']
            
            # Get all recipe steps
            steps_response = self.supabase.table('recipe_steps').select('*').eq('recipe_id', recipe_id).order('sequence_number').execute()
            
            if not steps_response.data:
                errors.append("No recipe steps found")
                return ValidationResult(
                    validation_name="Step Configuration Loading",
                    passed=False,
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            steps = steps_response.data
            details['total_recipe_steps'] = len(steps)
            
            config_validation = {
                'valve_steps_validated': 0,
                'purge_steps_validated': 0,
                'loop_steps_validated': 0,
                'missing_configs': []
            }
            
            # Validate each step has proper configuration
            for step in steps:
                step_id = step['id']
                step_type = step['type']
                step_name = step['name']
                
                if step_type == 'valve':
                    # Check valve step config
                    valve_config_response = self.supabase.table('valve_step_config').select('*').eq('step_id', step_id).execute()
                    
                    if valve_config_response.data:
                        config = valve_config_response.data[0]
                        config_validation['valve_steps_validated'] += 1
                        
                        # Validate valve config fields
                        if not config['valve_number']:
                            warnings.append(f"Valve step '{step_name}' missing valve_number")
                        if not config['duration_ms'] or config['duration_ms'] <= 0:
                            warnings.append(f"Valve step '{step_name}' has invalid duration: {config['duration_ms']}")
                        if not config['valve_id']:
                            warnings.append(f"Valve step '{step_name}' missing valve_id")
                    else:
                        config_validation['missing_configs'].append(f"Valve config missing for step '{step_name}'")
                        errors.append(f"Valve step '{step_name}' missing configuration in valve_step_config table")
                
                elif step_type == 'purge':
                    # Check purge step config
                    purge_config_response = self.supabase.table('purge_step_config').select('*').eq('step_id', step_id).execute()
                    
                    if purge_config_response.data:
                        config = purge_config_response.data[0]
                        config_validation['purge_steps_validated'] += 1
                        
                        # Validate purge config fields
                        if not config['duration_ms'] or config['duration_ms'] <= 0:
                            warnings.append(f"Purge step '{step_name}' has invalid duration: {config['duration_ms']}")
                        if not config['gas_type']:
                            warnings.append(f"Purge step '{step_name}' missing gas_type")
                        if not config['flow_rate'] or config['flow_rate'] <= 0:
                            warnings.append(f"Purge step '{step_name}' has invalid flow_rate: {config['flow_rate']}")
                    else:
                        config_validation['missing_configs'].append(f"Purge config missing for step '{step_name}'")
                        errors.append(f"Purge step '{step_name}' missing configuration in purge_step_config table")
                
                elif step_type == 'loop':
                    # Check loop step config
                    loop_config_response = self.supabase.table('loop_step_config').select('*').eq('step_id', step_id).execute()
                    
                    if loop_config_response.data:
                        config = loop_config_response.data[0]
                        config_validation['loop_steps_validated'] += 1
                        
                        # Validate loop config fields
                        if not config['iteration_count'] or config['iteration_count'] <= 0:
                            warnings.append(f"Loop step '{step_name}' has invalid iteration_count: {config['iteration_count']}")
                    else:
                        config_validation['missing_configs'].append(f"Loop config missing for step '{step_name}'")
                        errors.append(f"Loop step '{step_name}' missing configuration in loop_step_config table")
                
                else:
                    warnings.append(f"Unknown step type '{step_type}' for step '{step_name}'")
            
            details['config_validation'] = config_validation
            passed = len(errors) == 0
            
        except Exception as e:
            errors.append(f"Configuration validation exception: {str(e)}")
            passed = False
        
        return ValidationResult(
            validation_name="Step Configuration Loading",
            passed=passed,
            details=details,
            errors=errors,
            warnings=warnings
        )
    
    async def validate_progress_tracking(self, process_id: str) -> ValidationResult:
        """Validate real-time progress tracking accuracy"""
        logger.info(f"Validating progress tracking for process: {process_id}")
        
        errors = []
        warnings = []
        details = {}
        
        try:
            # Get process execution state
            state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
            
            if not state_response.data:
                errors.append("Process execution state record not found")
                return ValidationResult(
                    validation_name="Progress Tracking",
                    passed=False,
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            state = state_response.data[0]
            
            # Validate progress structure
            if not state['progress']:
                warnings.append("No progress data recorded")
            else:
                progress = state['progress']
                details['progress_data'] = progress
                
                # Check required progress fields
                required_fields = ['total_steps', 'completed_steps']
                for field in required_fields:
                    if field not in progress:
                        errors.append(f"Missing required progress field: {field}")
                
                # Validate progress calculations
                if 'total_steps' in progress and 'completed_steps' in progress:
                    total = progress['total_steps']
                    completed = progress['completed_steps']
                    
                    if total <= 0:
                        errors.append(f"Invalid total_steps: {total}")
                    if completed < 0:
                        errors.append(f"Invalid completed_steps: {completed}")
                    if completed > total:
                        errors.append(f"completed_steps ({completed}) exceeds total_steps ({total})")
                    
                    # Calculate expected progress percentage
                    if total > 0:
                        expected_percentage = (completed / total) * 100
                        details['calculated_progress_percentage'] = expected_percentage
                        
                        if 'percentage' in progress:
                            recorded_percentage = progress['percentage']
                            if abs(recorded_percentage - expected_percentage) > 1.0:  # Allow 1% tolerance
                                warnings.append(f"Progress percentage mismatch: recorded {recorded_percentage}%, calculated {expected_percentage}%")
            
            # Validate step consistency
            if state['current_step_index'] is not None and state['total_overall_steps'] is not None:
                current_index = state['current_step_index']
                total_steps = state['total_overall_steps']
                
                details['current_step_index'] = current_index
                details['total_overall_steps'] = total_steps
                
                # Check index bounds
                if current_index < 0:
                    errors.append(f"Invalid current_step_index: {current_index}")
                if current_index > total_steps:
                    errors.append(f"current_step_index ({current_index}) exceeds total_overall_steps ({total_steps})")
                
                # Calculate expected overall progress
                if total_steps > 0:
                    overall_progress_percentage = (current_index / total_steps) * 100
                    details['overall_progress_percentage'] = overall_progress_percentage
            
            # Validate metrics data
            if state['process_metrics']:
                metrics = state['process_metrics']
                details['process_metrics'] = metrics
                
                # Check for timing consistency
                if 'start_time' in metrics and 'current_time' in metrics:
                    try:
                        start_time = datetime.fromisoformat(metrics['start_time'].replace('Z', '+00:00'))
                        current_time = datetime.fromisoformat(metrics['current_time'].replace('Z', '+00:00'))
                        
                        if current_time < start_time:
                            errors.append("Current time is before start time in metrics")
                        
                        duration = (current_time - start_time).total_seconds()
                        details['calculated_duration_seconds'] = duration
                        
                        if 'duration_seconds' in metrics:
                            recorded_duration = metrics['duration_seconds']
                            if abs(recorded_duration - duration) > 5.0:  # Allow 5 second tolerance
                                warnings.append(f"Duration mismatch: recorded {recorded_duration}s, calculated {duration}s")
                        
                    except (ValueError, TypeError) as e:
                        warnings.append(f"Invalid timestamp format in metrics: {str(e)}")
            
            passed = len(errors) == 0
            
        except Exception as e:
            errors.append(f"Progress tracking validation exception: {str(e)}")
            passed = False
        
        return ValidationResult(
            validation_name="Progress Tracking",
            passed=passed,
            details=details,
            errors=errors,
            warnings=warnings
        )
    
    async def validate_database_referential_integrity(self, process_id: str) -> ValidationResult:
        """Validate database referential integrity and foreign key constraints"""
        logger.info(f"Validating database referential integrity for process: {process_id}")
        
        errors = []
        warnings = []
        details = {}
        
        try:
            integrity_checks = {
                'process_execution_exists': False,
                'process_execution_state_linked': False,
                'recipe_exists': False,
                'recipe_steps_linked': False,
                'step_configs_linked': False,
                'machine_exists': False,
                'data_points_linked': False
            }
            
            # Check process execution record exists
            process_response = self.supabase.table('process_executions').select('*').eq('id', process_id).execute()
            
            if process_response.data:
                process = process_response.data[0]
                integrity_checks['process_execution_exists'] = True
                details['process'] = {
                    'id': process['id'],
                    'recipe_id': process['recipe_id'],
                    'machine_id': process['machine_id'],
                    'status': process['status']
                }
                
                # Check machine exists
                machine_response = self.supabase.table('machines').select('id, serial_number').eq('id', process['machine_id']).execute()
                
                if machine_response.data:
                    integrity_checks['machine_exists'] = True
                    details['machine'] = machine_response.data[0]
                else:
                    errors.append(f"Referenced machine {process['machine_id']} does not exist")
                
                # Check recipe exists
                recipe_response = self.supabase.table('recipes').select('id, name').eq('id', process['recipe_id']).execute()
                
                if recipe_response.data:
                    integrity_checks['recipe_exists'] = True
                    details['recipe'] = recipe_response.data[0]
                    
                    # Check recipe steps exist
                    steps_response = self.supabase.table('recipe_steps').select('id, type, name').eq('recipe_id', process['recipe_id']).execute()
                    
                    if steps_response.data:
                        integrity_checks['recipe_steps_linked'] = True
                        details['recipe_steps_count'] = len(steps_response.data)
                        
                        # Validate step configurations exist for each step
                        config_checks = {'valve': 0, 'purge': 0, 'loop': 0, 'missing': []}
                        
                        for step in steps_response.data:
                            step_type = step['type']
                            step_id = step['id']
                            step_name = step['name']
                            
                            if step_type == 'valve':
                                valve_config_response = self.supabase.table('valve_step_config').select('id').eq('step_id', step_id).execute()
                                if valve_config_response.data:
                                    config_checks['valve'] += 1
                                else:
                                    config_checks['missing'].append(f"Valve config for step '{step_name}'")
                            
                            elif step_type == 'purge':
                                purge_config_response = self.supabase.table('purge_step_config').select('id').eq('step_id', step_id).execute()
                                if purge_config_response.data:
                                    config_checks['purge'] += 1
                                else:
                                    config_checks['missing'].append(f"Purge config for step '{step_name}'")
                            
                            elif step_type == 'loop':
                                loop_config_response = self.supabase.table('loop_step_config').select('id').eq('step_id', step_id).execute()
                                if loop_config_response.data:
                                    config_checks['loop'] += 1
                                else:
                                    config_checks['missing'].append(f"Loop config for step '{step_name}'")
                        
                        details['step_config_checks'] = config_checks
                        integrity_checks['step_configs_linked'] = len(config_checks['missing']) == 0
                        
                        if config_checks['missing']:
                            for missing in config_checks['missing']:
                                errors.append(f"Missing step configuration: {missing}")
                    
                    else:
                        errors.append(f"No recipe steps found for recipe {process['recipe_id']}")
                else:
                    errors.append(f"Referenced recipe {process['recipe_id']} does not exist")
            else:
                errors.append(f"Process execution {process_id} does not exist")
            
            # Check process execution state linkage
            state_response = self.supabase.table('process_execution_state').select('id').eq('execution_id', process_id).execute()
            
            if state_response.data:
                integrity_checks['process_execution_state_linked'] = True
            else:
                errors.append("Process execution state record not linked")
            
            # Check process data points linkage
            data_points_response = self.supabase.table('process_data_points').select('count').eq('process_id', process_id).execute()
            
            if data_points_response.data:
                data_point_count = len(data_points_response.data)
                integrity_checks['data_points_linked'] = data_point_count > 0
                details['data_points_count'] = data_point_count
                
                if data_point_count == 0:
                    warnings.append("No process data points recorded")
            
            details['integrity_checks'] = integrity_checks
            passed = len(errors) == 0
            
        except Exception as e:
            errors.append(f"Referential integrity validation exception: {str(e)}")
            passed = False
        
        return ValidationResult(
            validation_name="Database Referential Integrity",
            passed=passed,
            details=details,
            errors=errors,
            warnings=warnings
        )
    
    async def validate_performance_metrics(self, process_id: str) -> ValidationResult:
        """Validate performance metrics and timing accuracy"""
        logger.info(f"Validating performance metrics for process: {process_id}")
        
        errors = []
        warnings = []
        details = {}
        
        try:
            # Get process execution with timing
            process_response = self.supabase.table('process_executions').select('*').eq('id', process_id).execute()
            
            if not process_response.data:
                errors.append("Process execution record not found")
                return ValidationResult(
                    validation_name="Performance Metrics",
                    passed=False,
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            process = process_response.data[0]
            
            # Validate timing data
            if process['start_time']:
                start_time = datetime.fromisoformat(process['start_time'].replace('Z', '+00:00'))
                details['process_start_time'] = process['start_time']
                
                if process['end_time']:
                    end_time = datetime.fromisoformat(process['end_time'].replace('Z', '+00:00'))
                    details['process_end_time'] = process['end_time']
                    
                    duration = (end_time - start_time).total_seconds()
                    details['process_duration_seconds'] = duration
                    
                    if duration < 0:
                        errors.append("Process end time is before start time")
                    elif duration == 0:
                        warnings.append("Process duration is zero seconds")
                    elif duration > 3600:  # More than 1 hour
                        warnings.append(f"Process duration is unusually long: {duration} seconds")
            
            # Get process execution state metrics
            state_response = self.supabase.table('process_execution_state').select('*').eq('execution_id', process_id).execute()
            
            if state_response.data:
                state = state_response.data[0]
                
                if state['process_metrics']:
                    metrics = state['process_metrics']
                    details['state_metrics'] = metrics
                    
                    # Validate metric consistency
                    if 'execution_start_time' in metrics and process['start_time']:
                        try:
                            metrics_start = datetime.fromisoformat(metrics['execution_start_time'].replace('Z', '+00:00'))
                            process_start = datetime.fromisoformat(process['start_time'].replace('Z', '+00:00'))
                            
                            time_diff = abs((metrics_start - process_start).total_seconds())
                            if time_diff > 60:  # More than 1 minute difference
                                warnings.append(f"Start time mismatch between process and state: {time_diff} seconds")
                        
                        except (ValueError, TypeError) as e:
                            warnings.append(f"Invalid timestamp in metrics: {str(e)}")
                    
                    # Check step timing metrics
                    if 'step_timings' in metrics and isinstance(metrics['step_timings'], list):
                        step_timings = metrics['step_timings']
                        details['step_timing_count'] = len(step_timings)
                        
                        total_step_duration = 0
                        for i, timing in enumerate(step_timings):
                            if 'duration_ms' in timing:
                                duration_ms = timing['duration_ms']
                                total_step_duration += duration_ms
                                
                                if duration_ms < 0:
                                    errors.append(f"Negative step duration at index {i}: {duration_ms}ms")
                                elif duration_ms > 300000:  # More than 5 minutes
                                    warnings.append(f"Very long step duration at index {i}: {duration_ms}ms")
                        
                        details['total_step_duration_ms'] = total_step_duration
                        
                        if total_step_duration > 0 and 'process_duration_seconds' in details:
                            expected_total_ms = details['process_duration_seconds'] * 1000
                            if abs(total_step_duration - expected_total_ms) > 10000:  # More than 10 second difference
                                warnings.append(f"Step duration sum ({total_step_duration}ms) doesn't match process duration ({expected_total_ms}ms)")
            
            # Check data point frequency
            data_points_response = self.supabase.table('process_data_points').select('timestamp').eq('process_id', process_id).order('timestamp').execute()
            
            if data_points_response.data and len(data_points_response.data) > 1:
                timestamps = [datetime.fromisoformat(dp['timestamp'].replace('Z', '+00:00')) for dp in data_points_response.data]
                
                # Calculate data point intervals
                intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]
                
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    max_interval = max(intervals)
                    min_interval = min(intervals)
                    
                    details['data_point_metrics'] = {
                        'total_points': len(timestamps),
                        'average_interval_seconds': avg_interval,
                        'max_interval_seconds': max_interval,
                        'min_interval_seconds': min_interval
                    }
                    
                    # Check for reasonable data collection frequency
                    if avg_interval > 60:  # More than 1 minute average
                        warnings.append(f"Data points collected infrequently: {avg_interval} seconds average")
                    
                    if max_interval > 300:  # More than 5 minutes gap
                        warnings.append(f"Large gap in data collection: {max_interval} seconds")
            
            passed = len(errors) == 0
            
        except Exception as e:
            errors.append(f"Performance metrics validation exception: {str(e)}")
            passed = False
        
        return ValidationResult(
            validation_name="Performance Metrics",
            passed=passed,
            details=details,
            errors=errors,
            warnings=warnings
        )
    
    async def run_comprehensive_validation(self, process_id: str) -> List[ValidationResult]:
        """Run all validation checks for a process execution"""
        logger.info(f"Running comprehensive validation for process: {process_id}")
        
        validation_results = []
        
        # Run all validation checks
        validations = [
            self.validate_process_execution_state(process_id),
            self.validate_step_configuration_loading(process_id),
            self.validate_progress_tracking(process_id),
            self.validate_database_referential_integrity(process_id),
            self.validate_performance_metrics(process_id)
        ]
        
        # Execute all validations
        results = await asyncio.gather(*validations, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Validation failed with exception: {str(result)}")
                validation_results.append(ValidationResult(
                    validation_name="Exception During Validation",
                    passed=False,
                    details={},
                    errors=[str(result)],
                    warnings=[]
                ))
            else:
                validation_results.append(result)
        
        return validation_results

async def main():
    """Main entry point for simulation validation"""
    if len(sys.argv) < 2:
        print("Usage: python simulation_validator.py <process_id>")
        sys.exit(1)
    
    process_id = sys.argv[1]
    
    # Supabase configuration
    SUPABASE_URL = "https://yceyfsqusdmcwgkwxcnt.supabase.co"
    SUPABASE_KEY = "your_supabase_key_here"  # This should be provided via environment variable
    
    try:
        validator = SimulationValidator(SUPABASE_URL, SUPABASE_KEY)
        validation_results = await validator.run_comprehensive_validation(process_id)
        
        # Print validation results
        print("=" * 80)
        print(f"VALIDATION RESULTS FOR PROCESS: {process_id}")
        print("=" * 80)
        
        total_validations = len(validation_results)
        passed_validations = sum(1 for result in validation_results if result.passed)
        failed_validations = total_validations - passed_validations
        
        print(f"Total Validations: {total_validations}")
        print(f"Passed: {passed_validations}")
        print(f"Failed: {failed_validations}")
        print(f"Success Rate: {(passed_validations / total_validations * 100):.1f}%")
        print()
        
        for result in validation_results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            print(f"{status} - {result.validation_name}")
            
            if result.errors:
                for error in result.errors:
                    print(f"   ERROR: {error}")
            
            if result.warnings:
                for warning in result.warnings:
                    print(f"   WARNING: {warning}")
            
            if result.details:
                print(f"   Details: {json.dumps(result.details, indent=2)}")
            print()
        
        # Save results to file
        results_data = {
            'process_id': process_id,
            'validation_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_validations': total_validations,
                'passed_validations': passed_validations,
                'failed_validations': failed_validations,
                'success_rate': (passed_validations / total_validations * 100) if total_validations > 0 else 0
            },
            'results': [
                {
                    'validation_name': result.validation_name,
                    'passed': result.passed,
                    'errors': result.errors,
                    'warnings': result.warnings,
                    'details': result.details
                }
                for result in validation_results
            ]
        }
        
        filename = f"validation_results_{process_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Validation results saved to: {filename}")
        
        return 0 if all(result.passed for result in validation_results) else 1
        
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)