#!/usr/bin/env python3
"""
Database Integration Validator
Validates all test recipes, step configurations, and database relationships
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from database.connection import get_supabase_client
from log_setup import logger

class DatabaseIntegrationValidator:
    """Comprehensive database integration validator"""
    
    def __init__(self, project_id: str = "yceyfsqusdmcwgkwxcnt"):
        self.project_id = project_id
        self.supabase = get_supabase_client()
        self.validation_results = {}
        
    async def execute_comprehensive_validation(self) -> Dict[str, Any]:
        """Execute all database validation checks"""
        logger.info("🔍 Starting comprehensive database validation")
        
        validation_tasks = [
            ("Recipe Creation Validation", self.validate_recipe_creation),
            ("Step Configuration Linkage", self.validate_step_configurations),
            ("Parameter Accessibility", self.validate_recipe_parameters),
            ("Process Execution Support", self.validate_process_execution_structure),
            ("Command Flow Integration", self.validate_command_flow_support),
            ("Data Relationships Integrity", self.validate_data_relationships),
            ("Index Performance", self.validate_index_performance),
            ("Constraint Enforcement", self.validate_constraint_enforcement),
        ]
        
        results = {
            'validation_id': f"db_validation_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'validations': {},
            'summary': {},
            'overall_status': 'UNKNOWN'
        }
        
        for task_name, task_func in validation_tasks:
            logger.info(f"📋 Executing: {task_name}")
            try:
                validation_result = await task_func()
                results['validations'][task_name] = validation_result
                logger.info(f"✅ {task_name}: {'PASSED' if validation_result.get('valid', False) else 'FAILED'}")
            except Exception as e:
                logger.error(f"❌ {task_name} failed: {str(e)}")
                results['validations'][task_name] = {
                    'valid': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        
        # Calculate summary
        total_validations = len(results['validations'])
        passed_validations = sum(1 for v in results['validations'].values() if v.get('valid', False))
        
        results['completed_at'] = datetime.now().isoformat()
        results['summary'] = {
            'total_validations': total_validations,
            'passed_validations': passed_validations,
            'failed_validations': total_validations - passed_validations,
            'success_rate': passed_validations / total_validations if total_validations > 0 else 0
        }
        results['overall_status'] = 'VALID' if passed_validations == total_validations else 'INVALID'
        
        # Save detailed validation report
        report_filename = f"database_validation_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📋 Database validation report saved to {report_filename}")
        return results
    
    async def validate_recipe_creation(self) -> Dict[str, Any]:
        """Validate all test recipes were created successfully"""
        logger.info("🧪 Validating recipe creation")
        
        recipe_validation_query = """
        WITH recipe_summary AS (
            SELECT 
                r.id,
                r.name,
                r.description,
                r.created_at,
                COUNT(rs.id) as total_steps,
                COUNT(CASE WHEN rs.type = 'valve' THEN 1 END) as valve_steps,
                COUNT(CASE WHEN rs.type = 'purge' THEN 1 END) as purge_steps,
                COUNT(CASE WHEN rs.type = 'loop' THEN 1 END) as loop_steps,
                COUNT(CASE WHEN rs.type = 'parameter' THEN 1 END) as parameter_steps,
                COUNT(rp.id) as parameter_count,
                MIN(rs.sequence_number) as min_sequence,
                MAX(rs.sequence_number) as max_sequence
            FROM recipes r
            LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
            LEFT JOIN recipe_parameters rp ON r.id = rp.recipe_id
            WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
            GROUP BY r.id, r.name, r.description, r.created_at
        )
        SELECT 
            *,
            CASE 
                WHEN total_steps = 0 THEN 'EMPTY_RECIPE'
                WHEN min_sequence != 1 THEN 'INVALID_SEQUENCE_START'
                WHEN max_sequence != total_steps THEN 'SEQUENCE_GAPS'
                WHEN total_steps > 0 AND parameter_count > 0 THEN 'COMPLETE'
                WHEN total_steps > 0 THEN 'MISSING_PARAMETERS'
                ELSE 'UNKNOWN'
            END as validation_status
        FROM recipe_summary
        ORDER BY created_at DESC;
        """
        
        try:
            response = await self.execute_sql_query(recipe_validation_query)
            recipes = response if response else []
            
            # Analyze recipe quality
            quality_stats = {
                'COMPLETE': 0,
                'MISSING_PARAMETERS': 0,
                'EMPTY_RECIPE': 0,
                'INVALID_SEQUENCE_START': 0,
                'SEQUENCE_GAPS': 0,
                'UNKNOWN': 0
            }
            
            total_recipes = len(recipes)
            complete_recipes = 0
            recipe_details = []
            
            for recipe in recipes:
                status = recipe.get('validation_status', 'UNKNOWN')
                quality_stats[status] = quality_stats.get(status, 0) + 1
                
                if status in ['COMPLETE', 'MISSING_PARAMETERS']:
                    complete_recipes += 1
                
                recipe_details.append({
                    'id': recipe.get('id'),
                    'name': recipe.get('name'),
                    'total_steps': recipe.get('total_steps', 0),
                    'parameter_count': recipe.get('parameter_count', 0),
                    'validation_status': status
                })
            
            success_rate = complete_recipes / total_recipes if total_recipes > 0 else 0
            
            return {
                'valid': success_rate >= 0.8,  # 80% of recipes should be complete
                'total_test_recipes': total_recipes,
                'complete_recipes': complete_recipes,
                'success_rate': success_rate,
                'quality_distribution': quality_stats,
                'recipe_details': recipe_details,
                'validation_criteria': 'At least 80% of recipes should be complete with steps'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'total_test_recipes': 0
            }
    
    async def validate_step_configurations(self) -> Dict[str, Any]:
        """Validate step configurations are properly linked"""
        logger.info("⚙️ Validating step configuration linkages")
        
        step_config_query = """
        WITH step_config_analysis AS (
            SELECT 
                rs.id as step_id,
                rs.name as step_name,
                rs.type as step_type,
                rs.recipe_id,
                r.name as recipe_name,
                -- Check if step has appropriate configuration
                CASE rs.type
                    WHEN 'valve' THEN 
                        CASE WHEN vsc.id IS NOT NULL THEN 'CONFIGURED' ELSE 'MISSING_CONFIG' END
                    WHEN 'purge' THEN 
                        CASE WHEN psc.id IS NOT NULL THEN 'CONFIGURED' ELSE 'MISSING_CONFIG' END
                    WHEN 'loop' THEN 
                        CASE WHEN lsc.id IS NOT NULL THEN 'CONFIGURED' ELSE 'MISSING_CONFIG' END
                    WHEN 'parameter' THEN 'NOT_REQUIRED'
                    ELSE 'UNKNOWN_TYPE'
                END as config_status,
                -- Configuration details
                vsc.valve_number,
                vsc.duration_ms as valve_duration,
                psc.gas_type,
                psc.duration_ms as purge_duration,
                lsc.iteration_count,
                lsc.inner_steps
            FROM recipe_steps rs
            JOIN recipes r ON rs.recipe_id = r.id
            LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id AND rs.type = 'valve'
            LEFT JOIN purge_step_config psc ON rs.id = psc.step_id AND rs.type = 'purge'  
            LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id AND rs.type = 'loop'
            WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
        )
        SELECT 
            config_status,
            step_type,
            COUNT(*) as step_count,
            COUNT(DISTINCT recipe_id) as affected_recipes
        FROM step_config_analysis
        GROUP BY config_status, step_type
        ORDER BY config_status, step_type;
        """
        
        detailed_config_query = """
        SELECT 
            rs.id as step_id,
            rs.name as step_name,
            rs.type as step_type,
            r.name as recipe_name,
            CASE rs.type
                WHEN 'valve' THEN 
                    CASE WHEN vsc.id IS NOT NULL THEN 
                        json_build_object('valve_number', vsc.valve_number, 'duration_ms', vsc.duration_ms)::text
                    ELSE 'NO_CONFIG' END
                WHEN 'purge' THEN 
                    CASE WHEN psc.id IS NOT NULL THEN 
                        json_build_object('gas_type', psc.gas_type, 'duration_ms', psc.duration_ms)::text
                    ELSE 'NO_CONFIG' END
                WHEN 'loop' THEN 
                    CASE WHEN lsc.id IS NOT NULL THEN 
                        json_build_object('iteration_count', lsc.iteration_count, 'inner_steps', lsc.inner_steps)::text
                    ELSE 'NO_CONFIG' END
                ELSE 'NOT_APPLICABLE'
            END as config_details
        FROM recipe_steps rs
        JOIN recipes r ON rs.recipe_id = r.id
        LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id AND rs.type = 'valve'
        LEFT JOIN purge_step_config psc ON rs.id = psc.step_id AND rs.type = 'purge'
        LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id AND rs.type = 'loop'
        WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
        AND rs.type IN ('valve', 'purge', 'loop')
        ORDER BY r.name, rs.sequence_number;
        """
        
        try:
            # Get configuration statistics
            config_stats_response = await self.execute_sql_query(step_config_query)
            config_stats = config_stats_response if config_stats_response else []
            
            # Get detailed configuration info
            detailed_response = await self.execute_sql_query(detailed_config_query)
            detailed_configs = detailed_response if detailed_response else []
            
            # Analyze configuration completeness
            total_configurable_steps = 0
            configured_steps = 0
            missing_configs = []
            
            for stat in config_stats:
                if stat.get('config_status') == 'CONFIGURED':
                    configured_steps += stat.get('step_count', 0)
                    total_configurable_steps += stat.get('step_count', 0)
                elif stat.get('config_status') == 'MISSING_CONFIG':
                    total_configurable_steps += stat.get('step_count', 0)
                    missing_configs.extend([{
                        'step_type': stat.get('step_type'),
                        'count': stat.get('step_count', 0),
                        'affected_recipes': stat.get('affected_recipes', 0)
                    }])
            
            configuration_rate = configured_steps / total_configurable_steps if total_configurable_steps > 0 else 1.0
            
            # Analyze detailed configurations for validity
            valid_configs = 0
            invalid_configs = []
            
            for config in detailed_configs:
                config_detail = config.get('config_details', 'NO_CONFIG')
                if config_detail != 'NO_CONFIG' and config_detail != 'NOT_APPLICABLE':
                    try:
                        # Try to parse config details if they're JSON
                        if config_detail.startswith('{'):
                            config_data = json.loads(config_detail)
                            # Basic validation of configuration data
                            if config.get('step_type') == 'valve' and 'valve_number' in config_data:
                                valid_configs += 1
                            elif config.get('step_type') == 'purge' and 'gas_type' in config_data:
                                valid_configs += 1
                            elif config.get('step_type') == 'loop' and 'iteration_count' in config_data:
                                valid_configs += 1
                            else:
                                invalid_configs.append(config)
                        else:
                            valid_configs += 1
                    except:
                        invalid_configs.append(config)
                else:
                    invalid_configs.append(config)
            
            return {
                'valid': configuration_rate >= 0.9,  # 90% configuration rate required
                'total_configurable_steps': total_configurable_steps,
                'configured_steps': configured_steps,
                'configuration_rate': configuration_rate,
                'valid_configurations': valid_configs,
                'invalid_configurations': len(invalid_configs),
                'missing_config_summary': missing_configs,
                'configuration_statistics': config_stats,
                'detailed_analysis': detailed_configs[:20],  # Limit for readability
                'validation_criteria': 'At least 90% of typed steps should have valid configurations'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'total_configurable_steps': 0
            }
    
    async def validate_recipe_parameters(self) -> Dict[str, Any]:
        """Validate recipe parameters are accessible and working"""
        logger.info("📊 Validating recipe parameter accessibility")
        
        parameter_validation_query = """
        WITH parameter_analysis AS (
            SELECT 
                r.id as recipe_id,
                r.name as recipe_name,
                COUNT(rp.id) as total_parameters,
                COUNT(CASE WHEN rp.parameter_type = 'float' THEN 1 END) as float_params,
                COUNT(CASE WHEN rp.parameter_type = 'integer' THEN 1 END) as int_params,
                COUNT(CASE WHEN rp.parameter_type = 'string' THEN 1 END) as string_params,
                COUNT(CASE WHEN rp.parameter_type = 'boolean' THEN 1 END) as bool_params,
                -- Check for common parameters
                COUNT(CASE WHEN rp.parameter_name LIKE '%temperature%' THEN 1 END) as temp_params,
                COUNT(CASE WHEN rp.parameter_name LIKE '%pressure%' THEN 1 END) as pressure_params,
                COUNT(CASE WHEN rp.parameter_name LIKE '%flow%' THEN 1 END) as flow_params,
                -- Check parameter value validity
                COUNT(CASE WHEN rp.parameter_value IS NOT NULL AND rp.parameter_value != '' THEN 1 END) as valid_values
            FROM recipes r
            LEFT JOIN recipe_parameters rp ON r.id = rp.recipe_id
            WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
            GROUP BY r.id, r.name
        )
        SELECT 
            *,
            CASE 
                WHEN total_parameters = 0 THEN 'NO_PARAMETERS'
                WHEN valid_values = total_parameters THEN 'ALL_VALID'
                WHEN valid_values > total_parameters * 0.8 THEN 'MOSTLY_VALID'
                ELSE 'MANY_INVALID'
            END as parameter_quality
        FROM parameter_analysis
        ORDER BY total_parameters DESC;
        """
        
        parameter_types_query = """
        SELECT 
            parameter_type,
            COUNT(*) as parameter_count,
            COUNT(CASE WHEN parameter_value IS NOT NULL AND parameter_value != '' THEN 1 END) as valid_count,
            -- Sample some parameter names and values
            string_agg(DISTINCT parameter_name, ', ') as sample_names
        FROM recipe_parameters rp
        JOIN recipes r ON rp.recipe_id = r.id
        WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
        GROUP BY parameter_type
        ORDER BY parameter_count DESC;
        """
        
        try:
            # Get parameter analysis
            param_analysis_response = await self.execute_sql_query(parameter_validation_query)
            param_analysis = param_analysis_response if param_analysis_response else []
            
            # Get parameter type distribution
            param_types_response = await self.execute_sql_query(parameter_types_query)
            param_types = param_types_response if param_types_response else []
            
            # Calculate overall parameter health
            total_recipes_with_params = 0
            recipes_with_good_params = 0
            total_parameters = 0
            valid_parameters = 0
            
            for recipe in param_analysis:
                recipe_param_count = recipe.get('total_parameters', 0)
                recipe_valid_count = recipe.get('valid_values', 0)
                
                total_parameters += recipe_param_count
                valid_parameters += recipe_valid_count
                
                if recipe_param_count > 0:
                    total_recipes_with_params += 1
                    quality = recipe.get('parameter_quality', 'NO_PARAMETERS')
                    if quality in ['ALL_VALID', 'MOSTLY_VALID']:
                        recipes_with_good_params += 1
            
            recipe_param_rate = recipes_with_good_params / total_recipes_with_params if total_recipes_with_params > 0 else 0
            overall_param_validity = valid_parameters / total_parameters if total_parameters > 0 else 0
            
            # Analyze parameter type distribution
            type_analysis = {}
            for param_type in param_types:
                type_name = param_type.get('parameter_type', 'unknown')
                type_analysis[type_name] = {
                    'total_count': param_type.get('parameter_count', 0),
                    'valid_count': param_type.get('valid_count', 0),
                    'validity_rate': param_type.get('valid_count', 0) / param_type.get('parameter_count', 1),
                    'sample_names': param_type.get('sample_names', '')
                }
            
            return {
                'valid': recipe_param_rate >= 0.8 and overall_param_validity >= 0.9,
                'total_recipes_with_parameters': total_recipes_with_params,
                'recipes_with_good_parameters': recipes_with_good_params,
                'recipe_parameter_success_rate': recipe_param_rate,
                'total_parameters': total_parameters,
                'valid_parameters': valid_parameters,
                'overall_parameter_validity': overall_param_validity,
                'parameter_type_analysis': type_analysis,
                'recipe_parameter_details': param_analysis,
                'validation_criteria': 'At least 80% of recipes should have good parameters, 90% of parameters should be valid'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'total_parameters': 0
            }
    
    async def validate_process_execution_structure(self) -> Dict[str, Any]:
        """Validate process execution state tracking structure"""
        logger.info("🎯 Validating process execution support structure")
        
        execution_structure_query = """
        -- Check if process execution tables exist and have proper structure
        SELECT 
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name IN ('process_executions', 'process_execution_state')
        ORDER BY table_name, ordinal_position;
        """
        
        execution_constraints_query = """
        -- Check foreign key relationships for process execution tables
        SELECT 
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' 
        AND tc.table_schema='public'
        AND tc.table_name IN ('process_executions', 'process_execution_state');
        """
        
        try:
            # Check table structure
            structure_response = await self.execute_sql_query(execution_structure_query)
            table_structure = structure_response if structure_response else []
            
            # Check constraints
            constraints_response = await self.execute_sql_query(execution_constraints_query)
            constraints = constraints_response if constraints_response else []
            
            # Analyze table structure completeness
            expected_process_execution_columns = {
                'id', 'recipe_id', 'started_at', 'completed_at', 'status', 'operator_id'
            }
            expected_execution_state_columns = {
                'id', 'process_execution_id', 'current_step_id', 'step_start_time', 
                'progress_percentage', 'loop_iteration', 'valve_number', 'duration_ms'
            }
            
            found_pe_columns = set()
            found_es_columns = set()
            
            for column in table_structure:
                table_name = column.get('table_name')
                column_name = column.get('column_name')
                
                if table_name == 'process_executions':
                    found_pe_columns.add(column_name)
                elif table_name == 'process_execution_state':
                    found_es_columns.add(column_name)
            
            pe_missing = expected_process_execution_columns - found_pe_columns
            es_missing = expected_execution_state_columns - found_es_columns
            
            # Check constraint completeness
            expected_constraints = [
                ('process_executions', 'recipe_id', 'recipes', 'id'),
                ('process_execution_state', 'process_execution_id', 'process_executions', 'id'),
                ('process_execution_state', 'current_step_id', 'recipe_steps', 'id')
            ]
            
            found_constraints = []
            for constraint in constraints:
                found_constraints.append((
                    constraint.get('table_name'),
                    constraint.get('column_name'),
                    constraint.get('foreign_table_name'),
                    constraint.get('foreign_column_name')
                ))
            
            missing_constraints = []
            for expected in expected_constraints:
                if expected not in found_constraints:
                    missing_constraints.append(expected)
            
            structure_valid = len(pe_missing) == 0 and len(es_missing) == 0
            constraints_valid = len(missing_constraints) == 0
            
            return {
                'valid': structure_valid and constraints_valid,
                'process_executions_table': {
                    'exists': len(found_pe_columns) > 0,
                    'expected_columns': list(expected_process_execution_columns),
                    'found_columns': list(found_pe_columns),
                    'missing_columns': list(pe_missing)
                },
                'process_execution_state_table': {
                    'exists': len(found_es_columns) > 0,
                    'expected_columns': list(expected_execution_state_columns),
                    'found_columns': list(found_es_columns),
                    'missing_columns': list(es_missing)
                },
                'foreign_key_constraints': {
                    'expected': expected_constraints,
                    'found': found_constraints,
                    'missing': missing_constraints
                },
                'table_structure_details': table_structure,
                'validation_criteria': 'Process execution tables must exist with all required columns and foreign keys'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'process_executions_table': {'exists': False},
                'process_execution_state_table': {'exists': False}
            }
    
    async def validate_command_flow_support(self) -> Dict[str, Any]:
        """Validate command flow integration support"""
        logger.info("🔄 Validating command flow integration support")
        
        command_structure_query = """
        -- Check commands table structure
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'commands'
        ORDER BY ordinal_position;
        """
        
        command_enum_query = """
        -- Check command type constraints or enums if they exist
        SELECT 
            constraint_name,
            constraint_type
        FROM information_schema.table_constraints
        WHERE table_schema = 'public' 
        AND table_name = 'commands'
        AND constraint_type IN ('CHECK', 'UNIQUE');
        """
        
        try:
            # Check commands table structure
            structure_response = await self.execute_sql_query(command_structure_query)
            command_structure = structure_response if structure_response else []
            
            # Check constraints
            constraints_response = await self.execute_sql_query(command_enum_query)
            command_constraints = constraints_response if constraints_response else []
            
            # Verify expected columns exist
            expected_command_columns = {
                'id', 'machine_id', 'command_type', 'parameters', 'status', 
                'priority', 'created_at', 'updated_at'
            }
            
            found_command_columns = {col.get('column_name') for col in command_structure}
            missing_command_columns = expected_command_columns - found_command_columns
            
            # Check if parameters column can handle JSON
            parameters_column = None
            for col in command_structure:
                if col.get('column_name') == 'parameters':
                    parameters_column = col
                    break
            
            json_support = False
            if parameters_column:
                data_type = parameters_column.get('data_type', '').lower()
                json_support = 'json' in data_type or 'text' in data_type
            
            structure_valid = len(missing_command_columns) == 0
            
            return {
                'valid': structure_valid and json_support,
                'commands_table': {
                    'exists': len(found_command_columns) > 0,
                    'expected_columns': list(expected_command_columns),
                    'found_columns': list(found_command_columns),
                    'missing_columns': list(missing_command_columns)
                },
                'json_parameter_support': json_support,
                'parameters_column_type': parameters_column.get('data_type') if parameters_column else None,
                'table_constraints': command_constraints,
                'command_structure_details': command_structure,
                'validation_criteria': 'Commands table must exist with all required columns and JSON parameter support'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'commands_table': {'exists': False}
            }
    
    async def validate_data_relationships(self) -> Dict[str, Any]:
        """Validate data relationship integrity"""
        logger.info("🔗 Validating data relationship integrity")
        
        relationship_queries = [
            {
                'name': 'recipe_to_steps_integrity',
                'query': """
                SELECT 
                    COUNT(*) as total_recipes,
                    COUNT(CASE WHEN step_count > 0 THEN 1 END) as recipes_with_steps,
                    AVG(step_count) as avg_steps_per_recipe
                FROM (
                    SELECT r.id, COUNT(rs.id) as step_count
                    FROM recipes r
                    LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
                    WHERE r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%'
                    GROUP BY r.id
                ) recipe_stats;
                """,
                'check': 'recipes_with_steps > 0'
            },
            {
                'name': 'step_to_config_integrity', 
                'query': """
                SELECT 
                    rs.type as step_type,
                    COUNT(rs.id) as total_steps,
                    COUNT(vsc.id + psc.id + lsc.id) as configured_steps
                FROM recipe_steps rs
                JOIN recipes r ON rs.recipe_id = r.id
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id AND rs.type = 'valve'
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id AND rs.type = 'purge'
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id AND rs.type = 'loop'
                WHERE (r.name LIKE '%Test%' OR r.name LIKE '%Integration%' OR r.name LIKE '%Simulation%')
                AND rs.type IN ('valve', 'purge', 'loop')
                GROUP BY rs.type
                ORDER BY rs.type;
                """,
                'check': 'configured_steps > 0'
            },
            {
                'name': 'orphaned_configurations',
                'query': """
                SELECT 
                    'valve_configs' as config_type,
                    COUNT(*) as total_configs,
                    COUNT(rs.id) as linked_configs,
                    COUNT(*) - COUNT(rs.id) as orphaned_configs
                FROM valve_step_config vsc
                LEFT JOIN recipe_steps rs ON vsc.step_id = rs.id
                UNION ALL
                SELECT 
                    'purge_configs',
                    COUNT(*), 
                    COUNT(rs.id),
                    COUNT(*) - COUNT(rs.id)
                FROM purge_step_config psc
                LEFT JOIN recipe_steps rs ON psc.step_id = rs.id
                UNION ALL
                SELECT 
                    'loop_configs',
                    COUNT(*),
                    COUNT(rs.id), 
                    COUNT(*) - COUNT(rs.id)
                FROM loop_step_config lsc
                LEFT JOIN recipe_steps rs ON lsc.step_id = rs.id;
                """,
                'check': 'orphaned_configs = 0'
            }
        ]
        
        relationship_results = {}
        overall_integrity = True
        
        try:
            for query_info in relationship_queries:
                response = await self.execute_sql_query(query_info['query'])
                result_data = response if response else []
                
                relationship_results[query_info['name']] = {
                    'data': result_data,
                    'check_passed': True  # Will implement specific checks based on data
                }
                
                # Specific integrity checks
                if query_info['name'] == 'recipe_to_steps_integrity' and result_data:
                    recipes_with_steps = result_data[0].get('recipes_with_steps', 0)
                    relationship_results[query_info['name']]['check_passed'] = recipes_with_steps > 0
                    if recipes_with_steps == 0:
                        overall_integrity = False
                
                elif query_info['name'] == 'orphaned_configurations' and result_data:
                    total_orphaned = sum(item.get('orphaned_configs', 0) for item in result_data)
                    relationship_results[query_info['name']]['check_passed'] = total_orphaned == 0
                    relationship_results[query_info['name']]['total_orphaned'] = total_orphaned
                    if total_orphaned > 0:
                        overall_integrity = False
            
            return {
                'valid': overall_integrity,
                'relationship_checks': relationship_results,
                'integrity_summary': {
                    'all_checks_passed': overall_integrity,
                    'total_checks': len(relationship_queries),
                    'passed_checks': sum(1 for r in relationship_results.values() if r.get('check_passed', False))
                },
                'validation_criteria': 'All data relationships must be consistent with no orphaned records'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'relationship_checks': {}
            }
    
    async def validate_index_performance(self) -> Dict[str, Any]:
        """Validate index performance for key queries"""
        logger.info("⚡ Validating index performance")
        
        # Check existing indexes
        index_query = """
        SELECT 
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes 
        WHERE schemaname = 'public'
        AND tablename IN ('recipes', 'recipe_steps', 'valve_step_config', 
                         'purge_step_config', 'loop_step_config', 'recipe_parameters',
                         'process_executions', 'process_execution_state', 'commands')
        ORDER BY tablename, indexname;
        """
        
        try:
            index_response = await self.execute_sql_query(index_query)
            indexes = index_response if index_response else []
            
            # Analyze index coverage for important tables
            index_analysis = {}
            important_tables = [
                'recipes', 'recipe_steps', 'valve_step_config', 
                'purge_step_config', 'loop_step_config', 'commands'
            ]
            
            for table in important_tables:
                table_indexes = [idx for idx in indexes if idx.get('tablename') == table]
                index_analysis[table] = {
                    'index_count': len(table_indexes),
                    'has_primary_key': any('pkey' in idx.get('indexname', '') for idx in table_indexes),
                    'indexes': [idx.get('indexname') for idx in table_indexes]
                }
            
            # Check if critical foreign key columns are indexed
            critical_indexes = [
                ('recipe_steps', 'recipe_id'),
                ('valve_step_config', 'step_id'), 
                ('purge_step_config', 'step_id'),
                ('loop_step_config', 'step_id'),
                ('recipe_parameters', 'recipe_id'),
                ('commands', 'machine_id'),
                ('commands', 'status')
            ]
            
            missing_critical_indexes = []
            for table, column in critical_indexes:
                # Simple check - look for indexes that might cover this column
                table_indexes = index_analysis.get(table, {}).get('indexes', [])
                column_indexed = any(column in idx.lower() for idx in table_indexes)
                
                if not column_indexed:
                    missing_critical_indexes.append(f"{table}.{column}")
            
            performance_acceptable = len(missing_critical_indexes) < 3  # Allow some missing indexes
            
            return {
                'valid': performance_acceptable,
                'total_indexes': len(indexes),
                'index_analysis_by_table': index_analysis,
                'missing_critical_indexes': missing_critical_indexes,
                'index_details': indexes,
                'validation_criteria': 'Most critical foreign key columns should be indexed'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'total_indexes': 0
            }
    
    async def validate_constraint_enforcement(self) -> Dict[str, Any]:
        """Validate constraint enforcement"""
        logger.info("🛡️ Validating constraint enforcement")
        
        constraint_query = """
        SELECT 
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS references_table,
            ccu.column_name AS references_column
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_schema = 'public'
        AND tc.table_name IN ('recipes', 'recipe_steps', 'valve_step_config', 
                             'purge_step_config', 'loop_step_config', 'recipe_parameters',
                             'process_executions', 'process_execution_state', 'commands')
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;
        """
        
        try:
            constraints_response = await self.execute_sql_query(constraint_query)
            constraints = constraints_response if constraints_response else []
            
            # Analyze constraint types by table
            constraint_analysis = {}
            constraint_types = ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK', 'NOT NULL']
            
            for constraint in constraints:
                table_name = constraint.get('table_name')
                constraint_type = constraint.get('constraint_type')
                
                if table_name not in constraint_analysis:
                    constraint_analysis[table_name] = {ctype: 0 for ctype in constraint_types}
                    constraint_analysis[table_name]['details'] = []
                
                if constraint_type in constraint_analysis[table_name]:
                    constraint_analysis[table_name][constraint_type] += 1
                
                constraint_analysis[table_name]['details'].append({
                    'name': constraint.get('constraint_name'),
                    'type': constraint_type,
                    'column': constraint.get('column_name'),
                    'references': f"{constraint.get('references_table')}.{constraint.get('references_column')}" if constraint.get('references_table') else None
                })
            
            # Check for essential constraints
            essential_checks = {
                'recipes_has_primary_key': constraint_analysis.get('recipes', {}).get('PRIMARY KEY', 0) > 0,
                'recipe_steps_has_foreign_key': constraint_analysis.get('recipe_steps', {}).get('FOREIGN KEY', 0) > 0,
                'commands_has_primary_key': constraint_analysis.get('commands', {}).get('PRIMARY KEY', 0) > 0,
            }
            
            all_essential_present = all(essential_checks.values())
            
            return {
                'valid': all_essential_present,
                'constraint_analysis': constraint_analysis,
                'essential_constraint_checks': essential_checks,
                'total_constraints': len(constraints),
                'constraint_details': constraints,
                'validation_criteria': 'Essential constraints (primary keys, foreign keys) must be present'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'constraint_analysis': {}
            }
    
    async def execute_sql_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute SQL query using Supabase client"""
        try:
            response = self.supabase.rpc('execute_sql', {'sql_query': query}).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"SQL query failed: {str(e)}")
            raise

async def main():
    """Main execution function for standalone running"""
    validator = DatabaseIntegrationValidator()
    results = await validator.execute_comprehensive_validation()
    
    print("\n" + "="*80)
    print("🔍 DATABASE INTEGRATION VALIDATION - COMPLETE")
    print("="*80)
    print(f"Overall Status: {results['overall_status']}")
    print(f"Success Rate: {results['summary']['success_rate']:.2%}")
    print(f"Validations Passed: {results['summary']['passed_validations']}/{results['summary']['total_validations']}")
    print("="*80)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())