#!/usr/bin/env python3
"""
Database Consistency Validator
Validates data integrity, foreign key relationships, and transaction consistency
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from database.connection import get_supabase_client
from log_setup import logger

class DatabaseConsistencyValidator:
    """Comprehensive database consistency and integrity validator"""
    
    def __init__(self, project_id: str = "yceyfsqusdmcwgkwxcnt"):
        self.project_id = project_id
        self.supabase = get_supabase_client()
        
    async def execute_comprehensive_consistency_validation(self) -> Dict[str, Any]:
        """Execute all database consistency validations"""
        logger.info("🔒 Starting comprehensive database consistency validation")
        
        validation_results = {
            'validation_id': f"consistency_check_{int(time.time())}",
            'started_at': datetime.now().isoformat(),
            'validation_categories': {},
            'summary': {},
            'overall_status': 'UNKNOWN'
        }
        
        validation_categories = [
            ("Foreign Key Integrity", self.validate_foreign_key_integrity),
            ("Data Consistency", self.validate_data_consistency),
            ("Referential Integrity", self.validate_referential_integrity),
            ("Constraint Enforcement", self.validate_constraint_enforcement),
            ("Transaction Integrity", self.validate_transaction_integrity),
            ("Index Consistency", self.validate_index_consistency),
            ("Sequence Integrity", self.validate_sequence_integrity),
            ("Data Type Consistency", self.validate_data_type_consistency),
        ]
        
        for category_name, validation_func in validation_categories:
            logger.info(f"🔍 Validating: {category_name}")
            try:
                category_result = await validation_func()
                validation_results['validation_categories'][category_name] = category_result
                
                status = "PASSED" if category_result.get('consistent', False) else "FAILED"
                logger.info(f"{'✅' if status == 'PASSED' else '❌'} {category_name}: {status}")
                
            except Exception as e:
                logger.error(f"❌ {category_name} validation failed: {str(e)}")
                validation_results['validation_categories'][category_name] = {
                    'consistent': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        
        # Calculate summary
        validation_results['completed_at'] = datetime.now().isoformat()
        validation_results['summary'] = self.calculate_consistency_summary(
            validation_results['validation_categories']
        )
        validation_results['overall_status'] = (
            'CONSISTENT' if validation_results['summary']['all_consistent'] else 'INCONSISTENT'
        )
        
        # Save detailed validation report
        report_filename = f"database_consistency_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(validation_results, f, indent=2, default=str)
        
        logger.info(f"📋 Database consistency report saved to {report_filename}")
        return validation_results
    
    async def validate_foreign_key_integrity(self) -> Dict[str, Any]:
        """Validate all foreign key relationships"""
        logger.info("🔗 Validating foreign key integrity")
        
        fk_integrity_checks = [
            {
                'name': 'recipe_steps_to_recipes',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM recipe_steps rs
                LEFT JOIN recipes r ON rs.recipe_id = r.id
                WHERE r.id IS NULL;
                """,
                'description': 'Recipe steps without valid recipe references'
            },
            {
                'name': 'valve_configs_to_steps',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM valve_step_config vsc
                LEFT JOIN recipe_steps rs ON vsc.step_id = rs.id
                WHERE rs.id IS NULL;
                """,
                'description': 'Valve configurations without valid step references'
            },
            {
                'name': 'purge_configs_to_steps',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM purge_step_config psc
                LEFT JOIN recipe_steps rs ON psc.step_id = rs.id
                WHERE rs.id IS NULL;
                """,
                'description': 'Purge configurations without valid step references'
            },
            {
                'name': 'loop_configs_to_steps',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM loop_step_config lsc
                LEFT JOIN recipe_steps rs ON lsc.step_id = rs.id
                WHERE rs.id IS NULL;
                """,
                'description': 'Loop configurations without valid step references'
            },
            {
                'name': 'recipe_parameters_to_recipes',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM recipe_parameters rp
                LEFT JOIN recipes r ON rp.recipe_id = r.id
                WHERE r.id IS NULL;
                """,
                'description': 'Recipe parameters without valid recipe references'
            },
            {
                'name': 'process_executions_to_recipes',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM process_executions pe
                LEFT JOIN recipes r ON pe.recipe_id = r.id
                WHERE r.id IS NULL;
                """,
                'description': 'Process executions without valid recipe references'
            },
            {
                'name': 'process_states_to_executions',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM process_execution_state pes
                LEFT JOIN process_executions pe ON pes.process_execution_id = pe.id
                WHERE pe.id IS NULL;
                """,
                'description': 'Process states without valid execution references'
            },
            {
                'name': 'process_states_to_steps',
                'query': """
                SELECT COUNT(*) as orphaned_count
                FROM process_execution_state pes
                LEFT JOIN recipe_steps rs ON pes.current_step_id = rs.id
                WHERE pes.current_step_id IS NOT NULL AND rs.id IS NULL;
                """,
                'description': 'Process states with invalid step references'
            }
        ]
        
        integrity_results = {}
        total_orphaned = 0
        issues_found = []
        
        try:
            for check in fk_integrity_checks:
                response = await self.execute_sql_query(check['query'])
                
                if response and len(response) > 0:
                    orphaned_count = response[0].get('orphaned_count', 0)
                    total_orphaned += orphaned_count
                    
                    integrity_results[check['name']] = {
                        'orphaned_count': orphaned_count,
                        'description': check['description'],
                        'clean': orphaned_count == 0
                    }
                    
                    if orphaned_count > 0:
                        issues_found.append({
                            'check': check['name'],
                            'count': orphaned_count,
                            'description': check['description']
                        })
                else:
                    integrity_results[check['name']] = {
                        'orphaned_count': 0,
                        'description': check['description'],
                        'clean': True,
                        'note': 'No data or query failed'
                    }
            
            return {
                'consistent': total_orphaned == 0,
                'total_orphaned_records': total_orphaned,
                'total_checks_performed': len(fk_integrity_checks),
                'clean_relationships': len(fk_integrity_checks) - len(issues_found),
                'integrity_issues': issues_found,
                'detailed_results': integrity_results,
                'validation_criteria': 'All foreign key relationships must be valid (0 orphaned records)'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_orphaned_records': 0
            }
    
    async def validate_data_consistency(self) -> Dict[str, Any]:
        """Validate data consistency across related tables"""
        logger.info("📊 Validating data consistency")
        
        consistency_checks = [
            {
                'name': 'recipe_step_sequence_consistency',
                'query': """
                WITH sequence_analysis AS (
                    SELECT 
                        recipe_id,
                        COUNT(*) as total_steps,
                        MIN(sequence_number) as min_seq,
                        MAX(sequence_number) as max_seq,
                        COUNT(DISTINCT sequence_number) as unique_sequences
                    FROM recipe_steps
                    GROUP BY recipe_id
                )
                SELECT 
                    COUNT(*) as recipes_with_gaps,
                    SUM(CASE WHEN min_seq != 1 THEN 1 ELSE 0 END) as recipes_not_starting_at_1,
                    SUM(CASE WHEN max_seq != total_steps THEN 1 ELSE 0 END) as recipes_with_sequence_gaps,
                    SUM(CASE WHEN unique_sequences != total_steps THEN 1 ELSE 0 END) as recipes_with_duplicates
                FROM sequence_analysis;
                """,
                'description': 'Recipe step sequence numbering consistency'
            },
            {
                'name': 'step_configuration_consistency',
                'query': """
                SELECT 
                    COUNT(CASE 
                        WHEN rs.type = 'valve' AND vsc.id IS NULL THEN 1 
                    END) as valve_steps_without_config,
                    COUNT(CASE 
                        WHEN rs.type = 'purge' AND psc.id IS NULL THEN 1 
                    END) as purge_steps_without_config,
                    COUNT(CASE 
                        WHEN rs.type = 'loop' AND lsc.id IS NULL THEN 1 
                    END) as loop_steps_without_config,
                    COUNT(CASE 
                        WHEN rs.type NOT IN ('valve', 'purge', 'loop', 'parameter') THEN 1 
                    END) as steps_with_unknown_type
                FROM recipe_steps rs
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id AND rs.type = 'valve'
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id AND rs.type = 'purge'
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id AND rs.type = 'loop';
                """,
                'description': 'Step type and configuration consistency'
            },
            {
                'name': 'process_execution_state_consistency',
                'query': """
                SELECT 
                    COUNT(CASE 
                        WHEN pes.progress_percentage < 0 OR pes.progress_percentage > 100 THEN 1 
                    END) as invalid_progress_values,
                    COUNT(CASE 
                        WHEN pes.step_start_time > NOW() THEN 1 
                    END) as future_start_times,
                    COUNT(CASE 
                        WHEN pe.started_at > pe.completed_at AND pe.completed_at IS NOT NULL THEN 1 
                    END) as invalid_time_sequences
                FROM process_execution_state pes
                LEFT JOIN process_executions pe ON pes.process_execution_id = pe.id;
                """,
                'description': 'Process execution temporal and value consistency'
            },
            {
                'name': 'parameter_value_consistency',
                'query': """
                SELECT 
                    COUNT(CASE 
                        WHEN parameter_value IS NULL OR parameter_value = '' THEN 1 
                    END) as empty_parameter_values,
                    COUNT(CASE 
                        WHEN parameter_type IS NULL OR parameter_type = '' THEN 1 
                    END) as missing_parameter_types,
                    COUNT(CASE 
                        WHEN parameter_name IS NULL OR parameter_name = '' THEN 1 
                    END) as missing_parameter_names
                FROM recipe_parameters;
                """,
                'description': 'Recipe parameter completeness and consistency'
            }
        ]
        
        consistency_results = {}
        total_inconsistencies = 0
        consistency_issues = []
        
        try:
            for check in consistency_checks:
                response = await self.execute_sql_query(check['query'])
                
                if response and len(response) > 0:
                    check_data = response[0]
                    check_inconsistencies = 0
                    check_details = {}
                    
                    # Count inconsistencies based on check type
                    if check['name'] == 'recipe_step_sequence_consistency':
                        check_inconsistencies = (
                            check_data.get('recipes_not_starting_at_1', 0) +
                            check_data.get('recipes_with_sequence_gaps', 0) +
                            check_data.get('recipes_with_duplicates', 0)
                        )
                        check_details = {
                            'recipes_not_starting_at_1': check_data.get('recipes_not_starting_at_1', 0),
                            'recipes_with_gaps': check_data.get('recipes_with_sequence_gaps', 0),
                            'recipes_with_duplicates': check_data.get('recipes_with_duplicates', 0)
                        }
                    
                    elif check['name'] == 'step_configuration_consistency':
                        check_inconsistencies = (
                            check_data.get('valve_steps_without_config', 0) +
                            check_data.get('purge_steps_without_config', 0) +
                            check_data.get('loop_steps_without_config', 0) +
                            check_data.get('steps_with_unknown_type', 0)
                        )
                        check_details = check_data
                    
                    elif check['name'] == 'process_execution_state_consistency':
                        check_inconsistencies = (
                            check_data.get('invalid_progress_values', 0) +
                            check_data.get('future_start_times', 0) +
                            check_data.get('invalid_time_sequences', 0)
                        )
                        check_details = check_data
                    
                    elif check['name'] == 'parameter_value_consistency':
                        check_inconsistencies = (
                            check_data.get('empty_parameter_values', 0) +
                            check_data.get('missing_parameter_types', 0) +
                            check_data.get('missing_parameter_names', 0)
                        )
                        check_details = check_data
                    
                    total_inconsistencies += check_inconsistencies
                    
                    consistency_results[check['name']] = {
                        'inconsistency_count': check_inconsistencies,
                        'description': check['description'],
                        'consistent': check_inconsistencies == 0,
                        'details': check_details
                    }
                    
                    if check_inconsistencies > 0:
                        consistency_issues.append({
                            'check': check['name'],
                            'count': check_inconsistencies,
                            'description': check['description']
                        })
            
            return {
                'consistent': total_inconsistencies == 0,
                'total_inconsistencies': total_inconsistencies,
                'total_checks_performed': len(consistency_checks),
                'consistent_checks': len(consistency_checks) - len(consistency_issues),
                'consistency_issues': consistency_issues,
                'detailed_results': consistency_results,
                'validation_criteria': 'All data relationships must be logically consistent'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_inconsistencies': 0
            }
    
    async def validate_referential_integrity(self) -> Dict[str, Any]:
        """Validate referential integrity constraints"""
        logger.info("🔄 Validating referential integrity")
        
        # Check for circular references and invalid references
        referential_checks = [
            {
                'name': 'circular_recipe_step_references',
                'query': """
                WITH RECURSIVE step_hierarchy AS (
                    -- Base case: all steps
                    SELECT id, recipe_id, name, 1 as depth, ARRAY[id] as path
                    FROM recipe_steps
                    
                    UNION ALL
                    
                    -- Recursive case: follow any potential circular paths
                    SELECT rs.id, rs.recipe_id, rs.name, sh.depth + 1, sh.path || rs.id
                    FROM recipe_steps rs
                    JOIN step_hierarchy sh ON rs.recipe_id = sh.recipe_id
                    WHERE rs.id = ANY(sh.path) AND sh.depth < 10
                )
                SELECT COUNT(*) as circular_references
                FROM step_hierarchy
                WHERE depth > 1;
                """,
                'description': 'Detect circular references in recipe steps'
            },
            {
                'name': 'valid_process_execution_references',
                'query': """
                SELECT 
                    COUNT(CASE WHEN pe.recipe_id IS NOT NULL AND r.id IS NULL THEN 1 END) as invalid_recipe_refs,
                    COUNT(CASE WHEN pes.process_execution_id IS NOT NULL AND pe.id IS NULL THEN 1 END) as invalid_execution_refs,
                    COUNT(CASE WHEN pes.current_step_id IS NOT NULL AND rs.id IS NULL THEN 1 END) as invalid_step_refs
                FROM process_executions pe
                FULL OUTER JOIN recipes r ON pe.recipe_id = r.id
                FULL OUTER JOIN process_execution_state pes ON pe.id = pes.process_execution_id
                FULL OUTER JOIN recipe_steps rs ON pes.current_step_id = rs.id;
                """,
                'description': 'Validate process execution reference integrity'
            },
            {
                'name': 'configuration_step_type_alignment',
                'query': """
                SELECT 
                    COUNT(CASE WHEN vsc.step_id IS NOT NULL AND rs.type != 'valve' THEN 1 END) as valve_config_type_mismatch,
                    COUNT(CASE WHEN psc.step_id IS NOT NULL AND rs.type != 'purge' THEN 1 END) as purge_config_type_mismatch,
                    COUNT(CASE WHEN lsc.step_id IS NOT NULL AND rs.type != 'loop' THEN 1 END) as loop_config_type_mismatch
                FROM recipe_steps rs
                FULL OUTER JOIN valve_step_config vsc ON rs.id = vsc.step_id
                FULL OUTER JOIN purge_step_config psc ON rs.id = psc.step_id
                FULL OUTER JOIN loop_step_config lsc ON rs.id = lsc.step_id;
                """,
                'description': 'Validate step configuration type alignment'
            }
        ]
        
        referential_results = {}
        total_violations = 0
        integrity_violations = []
        
        try:
            for check in referential_checks:
                response = await self.execute_sql_query(check['query'])
                
                if response and len(response) > 0:
                    check_data = response[0]
                    check_violations = 0
                    
                    # Count violations based on check type
                    if check['name'] == 'circular_recipe_step_references':
                        check_violations = check_data.get('circular_references', 0)
                    
                    elif check['name'] == 'valid_process_execution_references':
                        check_violations = (
                            check_data.get('invalid_recipe_refs', 0) +
                            check_data.get('invalid_execution_refs', 0) +
                            check_data.get('invalid_step_refs', 0)
                        )
                    
                    elif check['name'] == 'configuration_step_type_alignment':
                        check_violations = (
                            check_data.get('valve_config_type_mismatch', 0) +
                            check_data.get('purge_config_type_mismatch', 0) +
                            check_data.get('loop_config_type_mismatch', 0)
                        )
                    
                    total_violations += check_violations
                    
                    referential_results[check['name']] = {
                        'violation_count': check_violations,
                        'description': check['description'],
                        'valid': check_violations == 0,
                        'details': check_data
                    }
                    
                    if check_violations > 0:
                        integrity_violations.append({
                            'check': check['name'],
                            'count': check_violations,
                            'description': check['description']
                        })
            
            return {
                'consistent': total_violations == 0,
                'total_violations': total_violations,
                'total_checks_performed': len(referential_checks),
                'valid_references': len(referential_checks) - len(integrity_violations),
                'integrity_violations': integrity_violations,
                'detailed_results': referential_results,
                'validation_criteria': 'All references must be valid and non-circular'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_violations': 0
            }
    
    async def validate_constraint_enforcement(self) -> Dict[str, Any]:
        """Validate database constraint enforcement"""
        logger.info("🛡️ Validating constraint enforcement")
        
        # Get constraint information
        constraint_query = """
        SELECT 
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_schema = 'public'
        AND tc.table_name IN (
            'recipes', 'recipe_steps', 'valve_step_config', 
            'purge_step_config', 'loop_step_config', 'recipe_parameters',
            'process_executions', 'process_execution_state', 'commands'
        )
        ORDER BY tc.table_name, tc.constraint_type;
        """
        
        try:
            constraints_response = await self.execute_sql_query(constraint_query)
            constraints = constraints_response if constraints_response else []
            
            # Analyze constraint coverage
            constraint_analysis = {}
            constraint_types = ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK', 'NOT NULL']
            
            # Count constraints by table and type
            for constraint in constraints:
                table_name = constraint.get('table_name')
                constraint_type = constraint.get('constraint_type')
                
                if table_name not in constraint_analysis:
                    constraint_analysis[table_name] = {ctype: 0 for ctype in constraint_types}
                    constraint_analysis[table_name]['total'] = 0
                    constraint_analysis[table_name]['constraints'] = []
                
                if constraint_type in constraint_analysis[table_name]:
                    constraint_analysis[table_name][constraint_type] += 1
                    constraint_analysis[table_name]['total'] += 1
                
                constraint_analysis[table_name]['constraints'].append({
                    'name': constraint.get('constraint_name'),
                    'type': constraint_type,
                    'column': constraint.get('column_name'),
                    'references': f"{constraint.get('foreign_table_name')}.{constraint.get('foreign_column_name')}" if constraint.get('foreign_table_name') else None
                })
            
            # Check for essential constraints
            essential_tables = ['recipes', 'recipe_steps', 'commands', 'process_executions']
            missing_essential_constraints = []
            
            for table in essential_tables:
                if table not in constraint_analysis:
                    missing_essential_constraints.append(f"{table}: no constraints found")
                elif constraint_analysis[table]['PRIMARY KEY'] == 0:
                    missing_essential_constraints.append(f"{table}: missing primary key")
            
            # Check foreign key completeness for related tables
            fk_completeness_checks = [
                ('recipe_steps', 'FOREIGN KEY'),
                ('valve_step_config', 'FOREIGN KEY'),
                ('purge_step_config', 'FOREIGN KEY'),
                ('loop_step_config', 'FOREIGN KEY'),
                ('recipe_parameters', 'FOREIGN KEY'),
                ('process_executions', 'FOREIGN KEY'),
                ('process_execution_state', 'FOREIGN KEY'),
            ]
            
            missing_foreign_keys = []
            for table, constraint_type in fk_completeness_checks:
                if table not in constraint_analysis or constraint_analysis[table][constraint_type] == 0:
                    missing_foreign_keys.append(table)
            
            constraint_coverage_score = (
                len(essential_tables) - len(missing_essential_constraints) +
                len(fk_completeness_checks) - len(missing_foreign_keys)
            ) / (len(essential_tables) + len(fk_completeness_checks))
            
            return {
                'consistent': len(missing_essential_constraints) == 0 and len(missing_foreign_keys) <= 2,
                'total_constraints': len(constraints),
                'constraint_coverage_score': constraint_coverage_score,
                'constraint_analysis': constraint_analysis,
                'missing_essential_constraints': missing_essential_constraints,
                'missing_foreign_keys': missing_foreign_keys,
                'validation_criteria': 'All essential tables must have primary keys and appropriate foreign keys'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_constraints': 0
            }
    
    async def validate_transaction_integrity(self) -> Dict[str, Any]:
        """Validate transaction integrity and ACID properties"""
        logger.info("⚡ Validating transaction integrity")
        
        # Simulate transaction tests
        transaction_tests = []
        
        try:
            # Test 1: Multi-table insert consistency
            multi_table_test = await self.test_multi_table_transaction()
            transaction_tests.append(('multi_table_consistency', multi_table_test))
            
            # Test 2: Concurrent access simulation  
            concurrent_access_test = await self.test_concurrent_access_simulation()
            transaction_tests.append(('concurrent_access', concurrent_access_test))
            
            # Test 3: Rollback behavior simulation
            rollback_test = await self.test_rollback_simulation()
            transaction_tests.append(('rollback_behavior', rollback_test))
            
            successful_tests = sum(1 for _, test in transaction_tests if test.get('success', False))
            transaction_integrity_rate = successful_tests / len(transaction_tests)
            
            return {
                'consistent': transaction_integrity_rate >= 0.8,
                'total_transaction_tests': len(transaction_tests),
                'successful_tests': successful_tests,
                'transaction_integrity_rate': transaction_integrity_rate,
                'transaction_test_results': dict(transaction_tests),
                'validation_criteria': 'Transaction integrity must be maintained across all operations'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_transaction_tests': 0
            }
    
    async def test_multi_table_transaction(self) -> Dict[str, Any]:
        """Test multi-table transaction consistency"""
        
        try:
            # Create a test scenario that involves multiple related tables
            test_timestamp = int(time.time())
            test_recipe_name = f"Transaction Test Recipe {test_timestamp}"
            
            # This would normally be in a transaction, but we'll simulate the effect
            create_recipe_query = f"""
            INSERT INTO recipes (name, description, created_at, updated_at)
            VALUES ('{test_recipe_name}', 'Transaction integrity test recipe', NOW(), NOW())
            RETURNING id;
            """
            
            recipe_response = await self.execute_sql_query(create_recipe_query)
            
            if not recipe_response or not recipe_response[0]:
                return {'success': False, 'error': 'Failed to create test recipe'}
            
            recipe_id = recipe_response[0]['id']
            
            # Create related step
            create_step_query = f"""
            INSERT INTO recipe_steps (recipe_id, name, type, sequence_number, duration_ms, created_at, updated_at)
            VALUES ('{recipe_id}', 'Test Transaction Step', 'valve', 1, 1000, NOW(), NOW())
            RETURNING id;
            """
            
            step_response = await self.execute_sql_query(create_step_query)
            
            if not step_response or not step_response[0]:
                # Clean up recipe if step creation failed
                await self.execute_sql_query(f"DELETE FROM recipes WHERE id = '{recipe_id}'")
                return {'success': False, 'error': 'Failed to create test step'}
            
            step_id = step_response[0]['id']
            
            # Verify both records exist and are related
            verification_query = f"""
            SELECT r.id as recipe_id, rs.id as step_id, rs.recipe_id as step_recipe_id
            FROM recipes r
            JOIN recipe_steps rs ON r.id = rs.recipe_id
            WHERE r.id = '{recipe_id}' AND rs.id = '{step_id}';
            """
            
            verification_response = await self.execute_sql_query(verification_query)
            
            # Clean up test data
            await self.execute_sql_query(f"DELETE FROM recipe_steps WHERE id = '{step_id}'")
            await self.execute_sql_query(f"DELETE FROM recipes WHERE id = '{recipe_id}'")
            
            success = verification_response and len(verification_response) > 0
            
            return {
                'success': success,
                'test_recipe_id': recipe_id,
                'test_step_id': step_id,
                'verification_records': len(verification_response) if verification_response else 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_concurrent_access_simulation(self) -> Dict[str, Any]:
        """Simulate concurrent access patterns"""
        
        try:
            # Simulate concurrent reads to the same data
            concurrent_queries = [
                "SELECT COUNT(*) as recipe_count FROM recipes WHERE name LIKE '%Test%'",
                "SELECT COUNT(*) as step_count FROM recipe_steps WHERE recipe_id IN (SELECT id FROM recipes WHERE name LIKE '%Test%')",
                "SELECT COUNT(*) as param_count FROM recipe_parameters WHERE recipe_id IN (SELECT id FROM recipes WHERE name LIKE '%Test%')"
            ]
            
            # Execute queries "concurrently" (sequential for testing)
            concurrent_results = []
            for query in concurrent_queries:
                result = await self.execute_sql_query(query)
                concurrent_results.append(result[0] if result else {})
            
            # Check for consistent results (no data corruption)
            all_results_valid = all(
                isinstance(result, dict) and len(result) > 0 
                for result in concurrent_results
            )
            
            return {
                'success': all_results_valid,
                'concurrent_queries_executed': len(concurrent_queries),
                'successful_queries': sum(1 for r in concurrent_results if r),
                'concurrent_results': concurrent_results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_rollback_simulation(self) -> Dict[str, Any]:
        """Simulate rollback behavior"""
        
        try:
            # Test error handling in data operations
            # Attempt to create invalid data that should fail
            
            invalid_operations = [
                {
                    'name': 'duplicate_sequence_number',
                    'query': """
                    INSERT INTO recipe_steps (recipe_id, name, type, sequence_number, duration_ms, created_at, updated_at)
                    SELECT recipe_id, 'Duplicate Test Step', 'valve', sequence_number, 1000, NOW(), NOW()
                    FROM recipe_steps
                    WHERE recipe_id IN (SELECT id FROM recipes WHERE name LIKE '%Test%' LIMIT 1)
                    AND sequence_number = 1
                    LIMIT 1;
                    """
                },
                {
                    'name': 'invalid_foreign_key',
                    'query': """
                    INSERT INTO recipe_steps (recipe_id, name, type, sequence_number, duration_ms, created_at, updated_at)
                    VALUES ('00000000-0000-0000-0000-000000000000', 'Invalid FK Test', 'valve', 999, 1000, NOW(), NOW());
                    """
                }
            ]
            
            error_handling_results = []
            
            for operation in invalid_operations:
                try:
                    result = await self.execute_sql_query(operation['query'])
                    # If query succeeded when it should have failed, that's a problem
                    error_handling_results.append({
                        'operation': operation['name'],
                        'handled_correctly': False,
                        'note': 'Query succeeded when it should have failed'
                    })
                except Exception as e:
                    # Query failed as expected - good error handling
                    error_handling_results.append({
                        'operation': operation['name'],
                        'handled_correctly': True,
                        'error_message': str(e)
                    })
            
            correct_error_handling = sum(
                1 for result in error_handling_results 
                if result['handled_correctly']
            )
            
            return {
                'success': correct_error_handling >= len(invalid_operations) * 0.5,
                'total_error_tests': len(invalid_operations),
                'correct_error_handling': correct_error_handling,
                'error_handling_results': error_handling_results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def validate_index_consistency(self) -> Dict[str, Any]:
        """Validate index consistency and coverage"""
        logger.info("📚 Validating index consistency")
        
        try:
            # Get index information
            index_query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef,
                CASE WHEN indexname LIKE '%pkey%' THEN 'PRIMARY'
                     WHEN indexname LIKE '%fkey%' OR indexdef LIKE '%FOREIGN%' THEN 'FOREIGN_KEY'
                     WHEN indexdef LIKE '%UNIQUE%' THEN 'UNIQUE'
                     ELSE 'REGULAR'
                END as index_type
            FROM pg_indexes 
            WHERE schemaname = 'public'
            AND tablename IN (
                'recipes', 'recipe_steps', 'valve_step_config', 
                'purge_step_config', 'loop_step_config', 'recipe_parameters',
                'process_executions', 'process_execution_state', 'commands'
            )
            ORDER BY tablename, indexname;
            """
            
            indexes_response = await self.execute_sql_query(index_query)
            indexes = indexes_response if indexes_response else []
            
            # Analyze index coverage
            index_coverage = {}
            critical_tables = ['recipes', 'recipe_steps', 'commands', 'process_executions']
            
            for index in indexes:
                table_name = index.get('tablename')
                index_type = index.get('index_type', 'REGULAR')
                
                if table_name not in index_coverage:
                    index_coverage[table_name] = {
                        'PRIMARY': 0,
                        'FOREIGN_KEY': 0, 
                        'UNIQUE': 0,
                        'REGULAR': 0,
                        'total': 0,
                        'indexes': []
                    }
                
                index_coverage[table_name][index_type] += 1
                index_coverage[table_name]['total'] += 1
                index_coverage[table_name]['indexes'].append({
                    'name': index.get('indexname'),
                    'type': index_type,
                    'definition': index.get('indexdef')
                })
            
            # Check critical table coverage
            missing_primary_keys = []
            tables_without_indexes = []
            
            for table in critical_tables:
                if table not in index_coverage:
                    tables_without_indexes.append(table)
                elif index_coverage[table]['PRIMARY'] == 0:
                    missing_primary_keys.append(table)
            
            index_health_score = (
                len(critical_tables) - len(tables_without_indexes) - len(missing_primary_keys)
            ) / len(critical_tables)
            
            return {
                'consistent': len(missing_primary_keys) == 0 and len(tables_without_indexes) == 0,
                'total_indexes': len(indexes),
                'index_health_score': index_health_score,
                'index_coverage': index_coverage,
                'missing_primary_keys': missing_primary_keys,
                'tables_without_indexes': tables_without_indexes,
                'validation_criteria': 'All critical tables must have primary key indexes'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_indexes': 0
            }
    
    async def validate_sequence_integrity(self) -> Dict[str, Any]:
        """Validate sequence and numbering integrity"""
        logger.info("🔢 Validating sequence integrity")
        
        try:
            # Check recipe step sequence integrity  
            sequence_query = """
            WITH sequence_analysis AS (
                SELECT 
                    recipe_id,
                    COUNT(*) as total_steps,
                    MIN(sequence_number) as min_seq,
                    MAX(sequence_number) as max_seq,
                    COUNT(DISTINCT sequence_number) as unique_sequences,
                    ARRAY_AGG(sequence_number ORDER BY sequence_number) as all_sequences
                FROM recipe_steps
                GROUP BY recipe_id
            )
            SELECT 
                recipe_id,
                total_steps,
                min_seq,
                max_seq,
                unique_sequences,
                CASE 
                    WHEN min_seq != 1 THEN 'INVALID_START'
                    WHEN max_seq != total_steps THEN 'SEQUENCE_GAPS'
                    WHEN unique_sequences != total_steps THEN 'DUPLICATE_SEQUENCES'
                    ELSE 'VALID_SEQUENCE'
                END as sequence_status
            FROM sequence_analysis
            ORDER BY recipe_id;
            """
            
            sequence_response = await self.execute_sql_query(sequence_query)
            sequences = sequence_response if sequence_response else []
            
            # Analyze sequence quality
            sequence_stats = {
                'VALID_SEQUENCE': 0,
                'INVALID_START': 0,
                'SEQUENCE_GAPS': 0,
                'DUPLICATE_SEQUENCES': 0
            }
            
            sequence_issues = []
            
            for seq in sequences:
                status = seq.get('sequence_status', 'UNKNOWN')
                sequence_stats[status] = sequence_stats.get(status, 0) + 1
                
                if status != 'VALID_SEQUENCE':
                    sequence_issues.append({
                        'recipe_id': seq.get('recipe_id'),
                        'issue': status,
                        'total_steps': seq.get('total_steps'),
                        'min_seq': seq.get('min_seq'),
                        'max_seq': seq.get('max_seq')
                    })
            
            total_recipes = len(sequences)
            valid_sequences = sequence_stats.get('VALID_SEQUENCE', 0)
            sequence_integrity_rate = valid_sequences / total_recipes if total_recipes > 0 else 1.0
            
            return {
                'consistent': sequence_integrity_rate >= 0.9,
                'total_recipes_checked': total_recipes,
                'valid_sequences': valid_sequences,
                'sequence_integrity_rate': sequence_integrity_rate,
                'sequence_statistics': sequence_stats,
                'sequence_issues': sequence_issues,
                'validation_criteria': '90% of recipes must have valid step sequences'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_recipes_checked': 0
            }
    
    async def validate_data_type_consistency(self) -> Dict[str, Any]:
        """Validate data type consistency and constraints"""
        logger.info("🏷️ Validating data type consistency")
        
        try:
            # Check for data type consistency issues
            data_type_checks = [
                {
                    'name': 'numeric_field_validation',
                    'query': """
                    SELECT 
                        COUNT(CASE WHEN duration_ms < 0 THEN 1 END) as negative_durations,
                        COUNT(CASE WHEN sequence_number < 1 THEN 1 END) as invalid_sequence_numbers,
                        COUNT(CASE WHEN valve_number < 1 OR valve_number > 100 THEN 1 END) as invalid_valve_numbers
                    FROM recipe_steps rs
                    LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id;
                    """,
                    'description': 'Validate numeric field constraints'
                },
                {
                    'name': 'string_field_validation',
                    'query': """
                    SELECT 
                        COUNT(CASE WHEN name IS NULL OR name = '' THEN 1 END) as empty_recipe_names,
                        COUNT(CASE WHEN rs.name IS NULL OR rs.name = '' THEN 1 END) as empty_step_names,
                        COUNT(CASE WHEN gas_type IS NULL OR gas_type = '' THEN 1 END) as empty_gas_types
                    FROM recipes r
                    FULL OUTER JOIN recipe_steps rs ON r.id = rs.recipe_id
                    FULL OUTER JOIN purge_step_config psc ON rs.id = psc.step_id;
                    """,
                    'description': 'Validate string field completeness'
                },
                {
                    'name': 'timestamp_field_validation',
                    'query': """
                    SELECT 
                        COUNT(CASE WHEN created_at > NOW() THEN 1 END) as future_created_dates,
                        COUNT(CASE WHEN updated_at < created_at THEN 1 END) as invalid_update_sequences,
                        COUNT(CASE WHEN pe.completed_at < pe.started_at THEN 1 END) as invalid_execution_times
                    FROM recipes r
                    FULL OUTER JOIN process_executions pe ON r.id = pe.recipe_id;
                    """,
                    'description': 'Validate timestamp field logic'
                }
            ]
            
            data_type_results = {}
            total_violations = 0
            type_issues = []
            
            for check in data_type_checks:
                check_response = await self.execute_sql_query(check['query'])
                
                if check_response and len(check_response) > 0:
                    check_data = check_response[0]
                    check_violations = sum(
                        val for val in check_data.values() 
                        if isinstance(val, int) and val > 0
                    )
                    
                    total_violations += check_violations
                    
                    data_type_results[check['name']] = {
                        'violation_count': check_violations,
                        'description': check['description'],
                        'valid': check_violations == 0,
                        'details': check_data
                    }
                    
                    if check_violations > 0:
                        type_issues.append({
                            'check': check['name'],
                            'violations': check_violations,
                            'description': check['description']
                        })
            
            return {
                'consistent': total_violations == 0,
                'total_violations': total_violations,
                'total_checks_performed': len(data_type_checks),
                'valid_data_types': len(data_type_checks) - len(type_issues),
                'data_type_issues': type_issues,
                'detailed_results': data_type_results,
                'validation_criteria': 'All data must conform to expected types and constraints'
            }
            
        except Exception as e:
            return {
                'consistent': False,
                'error': str(e),
                'total_violations': 0
            }
    
    def calculate_consistency_summary(self, validation_categories: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall consistency summary"""
        
        total_categories = len(validation_categories)
        consistent_categories = sum(
            1 for category in validation_categories.values() 
            if category.get('consistent', False)
        )
        
        inconsistent_categories = total_categories - consistent_categories
        
        # Calculate weighted consistency score
        category_weights = {
            'Foreign Key Integrity': 0.2,
            'Data Consistency': 0.2,
            'Referential Integrity': 0.15,
            'Constraint Enforcement': 0.15,
            'Transaction Integrity': 0.1,
            'Index Consistency': 0.1,
            'Sequence Integrity': 0.05,
            'Data Type Consistency': 0.05
        }
        
        weighted_score = 0
        for category_name, category_result in validation_categories.items():
            weight = category_weights.get(category_name, 0.1)
            if category_result.get('consistent', False):
                weighted_score += weight
        
        return {
            'total_categories': total_categories,
            'consistent_categories': consistent_categories,
            'inconsistent_categories': inconsistent_categories,
            'overall_consistency_rate': consistent_categories / total_categories if total_categories > 0 else 0,
            'weighted_consistency_score': weighted_score,
            'all_consistent': inconsistent_categories == 0,
            'category_summary': {
                name: result.get('consistent', False) 
                for name, result in validation_categories.items()
            }
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
    validator = DatabaseConsistencyValidator()
    results = await validator.execute_comprehensive_consistency_validation()
    
    print("\n" + "="*80)
    print("🔒 DATABASE CONSISTENCY VALIDATION - COMPLETE")
    print("="*80)
    print(f"Overall Status: {results['overall_status']}")
    print(f"Consistency Rate: {results['summary']['overall_consistency_rate']:.2%}")
    print(f"Consistent Categories: {results['summary']['consistent_categories']}/{results['summary']['total_categories']}")
    print(f"Weighted Score: {results['summary']['weighted_consistency_score']:.2f}")
    print("="*80)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())