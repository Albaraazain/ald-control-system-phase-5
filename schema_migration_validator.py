#!/usr/bin/env python3
"""
Schema Migration Validation Framework
Validates database migration completeness and backward compatibility
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from uuid import uuid4
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_environment_setup import test_env
from database.database import DatabaseConnection
from log_setup import setup_logger

@dataclass
class MigrationValidationResult:
    """Migration validation result structure"""
    validation_id: str
    validation_name: str
    category: str
    status: str  # passed, failed, warning
    timestamp: datetime
    details: Dict[str, Any]
    issues: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []

@dataclass
class SchemaComparisonResult:
    """Schema comparison result structure"""
    table_name: str
    comparison_type: str  # structure, data, constraints
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    changes_detected: List[str]
    compatibility_issues: List[str] = None
    
    def __post_init__(self):
        if self.compatibility_issues is None:
            self.compatibility_issues = []

class SchemaMigrationValidator:
    """Comprehensive schema migration validation"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.validator_id = str(uuid4())
        self.validation_results: List[MigrationValidationResult] = []
        self.schema_comparisons: List[SchemaComparisonResult] = []
        self.db = None
        self.test_workspace = None
        
    async def initialize(self) -> bool:
        """Initialize migration validator"""
        self.logger.info("🚀 Initializing Schema Migration Validator...")
        
        try:
            # Use existing test environment
            if not test_env.is_ready():
                env_info = await test_env.initialize_environment()
                if env_info["status"] != "ready":
                    raise RuntimeError("Test environment initialization failed")
            
            self.test_workspace = Path(test_env.test_workspace)
            self.db = test_env.db
            
            # Create migration validation directories
            migration_dir = self.test_workspace / "migration_validation"
            migration_dir.mkdir(exist_ok=True)
            (migration_dir / "schema_snapshots").mkdir(exist_ok=True)
            (migration_dir / "validation_reports").mkdir(exist_ok=True)
            (migration_dir / "compatibility_tests").mkdir(exist_ok=True)
            
            self.logger.info("✅ Schema migration validator initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Migration validator initialization failed: {e}")
            return False
    
    async def validate_complete_migration(self) -> Dict[str, Any]:
        """Run complete migration validation suite"""
        self.logger.info("🔍 Starting Complete Migration Validation...")
        
        validation_start = datetime.now()
        
        try:
            # 1. Schema Structure Validation
            await self._validate_schema_structure()
            
            # 2. Data Migration Validation
            await self._validate_data_migration()
            
            # 3. Foreign Key and Constraint Validation
            await self._validate_constraints_and_relationships()
            
            # 4. Index and Performance Validation
            await self._validate_indexes_and_performance()
            
            # 5. Backward Compatibility Testing
            await self._validate_backward_compatibility()
            
            # 6. Code Integration Validation
            await self._validate_code_integration()
            
            # 7. Migration Completeness Check
            await self._validate_migration_completeness()
            
            # 8. Rollback Capability Testing
            await self._validate_rollback_capability()
            
            # Generate comprehensive migration report
            migration_report = await self._generate_migration_report()
            
            validation_end = datetime.now()
            validation_duration = (validation_end - validation_start).total_seconds()
            
            migration_report["validation_duration_seconds"] = validation_duration
            migration_report["validation_timestamp"] = validation_end.isoformat()
            
            self.logger.info(f"✅ Migration validation completed in {validation_duration:.2f}s")
            return migration_report
            
        except Exception as e:
            self.logger.error(f"❌ Migration validation failed: {e}")
            raise
    
    async def _validate_schema_structure(self) -> None:
        """Validate schema structure after migration"""
        self.logger.info("🏗️ Validating Schema Structure...")
        
        # Expected new tables from migration
        expected_new_tables = {
            "valve_step_config",
            "purge_step_config", 
            "loop_step_config",
            "process_execution_state",
            "recipe_parameters"
        }
        
        # Validate new tables exist
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="New Tables Creation",
            category="Schema Structure",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            existing_tables = await self._get_existing_tables()
            missing_tables = expected_new_tables - existing_tables
            
            validation_result.details = {
                "expected_tables": list(expected_new_tables),
                "existing_tables": list(existing_tables),
                "missing_tables": list(missing_tables)
            }
            
            if missing_tables:
                validation_result.status = "failed"
                validation_result.issues = [f"Missing table: {table}" for table in missing_tables]
            else:
                validation_result.status = "passed"
            
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
        
        # Validate table structures
        await self._validate_table_structures()
        
        # Validate column definitions
        await self._validate_column_definitions()
    
    async def _validate_table_structures(self) -> None:
        """Validate individual table structures"""
        expected_structures = {
            "valve_step_config": {
                "required_columns": ["id", "step_id", "valve_number", "duration_ms"],
                "unique_constraints": ["step_id"],
                "foreign_keys": [("step_id", "recipe_steps", "id")]
            },
            "purge_step_config": {
                "required_columns": ["id", "step_id", "duration_ms", "gas_type", "flow_rate"],
                "unique_constraints": ["step_id"],
                "foreign_keys": [("step_id", "recipe_steps", "id")]
            },
            "loop_step_config": {
                "required_columns": ["id", "step_id", "iteration_count"],
                "unique_constraints": ["step_id"],
                "foreign_keys": [("step_id", "recipe_steps", "id")]
            },
            "process_execution_state": {
                "required_columns": ["id", "execution_id", "current_step_index", "progress"],
                "unique_constraints": ["execution_id"],
                "foreign_keys": [("execution_id", "process_executions", "id")]
            },
            "recipe_parameters": {
                "required_columns": ["id", "recipe_id", "parameter_name", "parameter_value"],
                "foreign_keys": [("recipe_id", "recipes", "id")]
            }
        }
        
        for table_name, expected_structure in expected_structures.items():
            validation_result = MigrationValidationResult(
                validation_id=str(uuid4()),
                validation_name=f"Table Structure - {table_name}",
                category="Schema Structure",
                status="pending",
                timestamp=datetime.now(),
                details={}
            )
            
            try:
                # Check columns
                table_columns = await self._get_table_columns(table_name)
                missing_columns = set(expected_structure["required_columns"]) - set(table_columns.keys())
                
                # Check constraints if table exists
                constraints_valid = True
                constraint_issues = []
                
                if not missing_columns:
                    # Check unique constraints
                    if "unique_constraints" in expected_structure:
                        for constraint_col in expected_structure["unique_constraints"]:
                            is_unique = await self._check_unique_constraint(table_name, constraint_col)
                            if not is_unique:
                                constraints_valid = False
                                constraint_issues.append(f"Missing unique constraint on {constraint_col}")
                    
                    # Check foreign keys
                    if "foreign_keys" in expected_structure:
                        for fk_col, ref_table, ref_col in expected_structure["foreign_keys"]:
                            fk_exists = await self._check_foreign_key(table_name, fk_col, ref_table, ref_col)
                            if not fk_exists:
                                constraints_valid = False
                                constraint_issues.append(f"Missing foreign key {fk_col} -> {ref_table}.{ref_col}")
                
                validation_result.details = {
                    "expected_columns": expected_structure["required_columns"],
                    "actual_columns": list(table_columns.keys()),
                    "missing_columns": list(missing_columns),
                    "constraint_issues": constraint_issues
                }
                
                if missing_columns or not constraints_valid:
                    validation_result.status = "failed"
                    validation_result.issues = (
                        [f"Missing column: {col}" for col in missing_columns] + 
                        constraint_issues
                    )
                else:
                    validation_result.status = "passed"
                
            except Exception as e:
                validation_result.status = "failed"
                validation_result.issues = [str(e)]
            
            self.validation_results.append(validation_result)
    
    async def _validate_column_definitions(self) -> None:
        """Validate column definitions and data types"""
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Column Definitions and Data Types",
            category="Schema Structure",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            column_checks = []
            
            # Check critical column types
            critical_columns = [
                ("valve_step_config", "valve_number", "integer"),
                ("valve_step_config", "duration_ms", "integer"),
                ("purge_step_config", "duration_ms", "integer"),
                ("purge_step_config", "flow_rate", "numeric"),
                ("loop_step_config", "iteration_count", "integer"),
                ("process_execution_state", "current_step_index", "integer"),
                ("recipe_parameters", "parameter_value", "numeric")
            ]
            
            type_issues = []
            
            for table_name, column_name, expected_type in critical_columns:
                actual_type = await self._get_column_type(table_name, column_name)
                if actual_type and not self._types_compatible(actual_type, expected_type):
                    type_issues.append(f"{table_name}.{column_name}: expected {expected_type}, got {actual_type}")
                
                column_checks.append({
                    "table": table_name,
                    "column": column_name,
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "compatible": actual_type and self._types_compatible(actual_type, expected_type)
                })
            
            validation_result.details = {
                "column_checks": column_checks,
                "type_issues": type_issues
            }
            
            if type_issues:
                validation_result.status = "failed"
                validation_result.issues = type_issues
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_data_migration(self) -> None:
        """Validate data migration completeness and accuracy"""
        self.logger.info("📊 Validating Data Migration...")
        
        # Check that old data was properly migrated to new structure
        await self._validate_recipe_step_config_migration()
        await self._validate_process_execution_state_migration()
        await self._validate_recipe_parameters_migration()
    
    async def _validate_recipe_step_config_migration(self) -> None:
        """Validate recipe step configuration migration"""
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Recipe Step Configuration Migration",
            category="Data Migration",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Count recipe steps by type
            step_counts = await self.db.execute_query("""
                SELECT 
                    rs.type,
                    COUNT(rs.id) as step_count,
                    COUNT(CASE WHEN rs.type = 'valve' THEN vsc.step_id END) as valve_configs,
                    COUNT(CASE WHEN rs.type = 'purge' THEN psc.step_id END) as purge_configs,
                    COUNT(CASE WHEN rs.type = 'loop' THEN lsc.step_id END) as loop_configs
                FROM recipe_steps rs
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                GROUP BY rs.type
            """)
            
            migration_issues = []
            config_summary = {}
            
            for row in step_counts:
                step_type = row["type"]
                step_count = row["step_count"]
                config_summary[step_type] = {
                    "total_steps": step_count,
                    "valve_configs": row["valve_configs"],
                    "purge_configs": row["purge_configs"], 
                    "loop_configs": row["loop_configs"]
                }
                
                # Check if steps have appropriate configurations
                if step_type == "valve" and row["valve_configs"] < step_count:
                    migration_issues.append(f"{step_count - row['valve_configs']} valve steps missing configurations")
                elif step_type == "purge" and row["purge_configs"] < step_count:
                    migration_issues.append(f"{step_count - row['purge_configs']} purge steps missing configurations")
                elif step_type == "loop" and row["loop_configs"] < step_count:
                    migration_issues.append(f"{step_count - row['loop_configs']} loop steps missing configurations")
            
            validation_result.details = {
                "configuration_summary": config_summary,
                "migration_issues": migration_issues
            }
            
            if migration_issues:
                validation_result.status = "failed"
                validation_result.issues = migration_issues
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_process_execution_state_migration(self) -> None:
        """Validate process execution state migration"""
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Process Execution State Migration",
            category="Data Migration",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Check that all process executions have state records
            state_coverage = await self.db.execute_query("""
                SELECT 
                    COUNT(pe.id) as total_executions,
                    COUNT(pes.execution_id) as executions_with_state,
                    COUNT(pe.id) - COUNT(pes.execution_id) as missing_state_records
                FROM process_executions pe
                LEFT JOIN process_execution_state pes ON pe.id = pes.execution_id
            """)
            
            if state_coverage:
                total = state_coverage[0]["total_executions"]
                with_state = state_coverage[0]["executions_with_state"]
                missing = state_coverage[0]["missing_state_records"]
                
                validation_result.details = {
                    "total_executions": total,
                    "executions_with_state": with_state,
                    "missing_state_records": missing,
                    "coverage_percentage": (with_state / total * 100) if total > 0 else 100
                }
                
                if missing > 0:
                    validation_result.status = "failed"
                    validation_result.issues = [f"{missing} process executions missing state records"]
                    validation_result.recommendations = [
                        "Run state record creation migration for missing executions"
                    ]
                else:
                    validation_result.status = "passed"
            else:
                validation_result.status = "failed"
                validation_result.issues = ["Could not retrieve process execution state coverage"]
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_recipe_parameters_migration(self) -> None:
        """Validate recipe parameters migration"""
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Recipe Parameters Migration",
            category="Data Migration",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Check recipe parameters structure
            param_analysis = await self.db.execute_query("""
                SELECT 
                    COUNT(*) as total_parameters,
                    COUNT(DISTINCT recipe_id) as recipes_with_parameters,
                    COUNT(DISTINCT parameter_name) as unique_parameter_names,
                    AVG(parameter_value) as avg_parameter_value,
                    MIN(parameter_value) as min_parameter_value,
                    MAX(parameter_value) as max_parameter_value
                FROM recipe_parameters
            """)
            
            # Check for critical parameters
            critical_params = await self.db.execute_query("""
                SELECT parameter_name, COUNT(*) as usage_count
                FROM recipe_parameters
                WHERE is_critical = true
                GROUP BY parameter_name
                ORDER BY usage_count DESC
            """)
            
            if param_analysis:
                analysis = param_analysis[0]
                
                validation_result.details = {
                    "total_parameters": analysis["total_parameters"],
                    "recipes_with_parameters": analysis["recipes_with_parameters"],
                    "unique_parameter_names": analysis["unique_parameter_names"],
                    "parameter_value_range": {
                        "min": float(analysis["min_parameter_value"]) if analysis["min_parameter_value"] else None,
                        "max": float(analysis["max_parameter_value"]) if analysis["max_parameter_value"] else None,
                        "avg": float(analysis["avg_parameter_value"]) if analysis["avg_parameter_value"] else None
                    },
                    "critical_parameters": [{"name": cp["parameter_name"], "count": cp["usage_count"]} for cp in critical_params]
                }
                
                # Validate that parameters exist
                if analysis["total_parameters"] == 0:
                    validation_result.status = "warning"
                    validation_result.issues = ["No recipe parameters found - may indicate incomplete migration"]
                else:
                    validation_result.status = "passed"
            else:
                validation_result.status = "failed"
                validation_result.issues = ["Could not analyze recipe parameters"]
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_constraints_and_relationships(self) -> None:
        """Validate foreign keys and constraints"""
        self.logger.info("🔗 Validating Constraints and Relationships...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Foreign Key and Constraint Validation",
            category="Schema Integrity",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Critical foreign key relationships to validate
            critical_relationships = [
                ("valve_step_config", "step_id", "recipe_steps", "id"),
                ("purge_step_config", "step_id", "recipe_steps", "id"),
                ("loop_step_config", "step_id", "recipe_steps", "id"),
                ("process_execution_state", "execution_id", "process_executions", "id"),
                ("recipe_parameters", "recipe_id", "recipes", "id"),
                ("component_parameters", "definition_id", "component_parameter_definitions", "id")
            ]
            
            relationship_status = []
            integrity_issues = []
            
            for child_table, child_col, parent_table, parent_col in critical_relationships:
                try:
                    # Check for orphaned records
                    orphaned_result = await self.db.execute_query(f"""
                        SELECT COUNT(*) as orphaned_count
                        FROM {child_table} c
                        LEFT JOIN {parent_table} p ON c.{child_col} = p.{parent_col}
                        WHERE p.{parent_col} IS NULL AND c.{child_col} IS NOT NULL
                    """)
                    
                    orphaned_count = orphaned_result[0]["orphaned_count"] if orphaned_result else 0
                    
                    # Check constraint exists
                    constraint_exists = await self._check_foreign_key(child_table, child_col, parent_table, parent_col)
                    
                    relationship_info = {
                        "child_table": child_table,
                        "child_column": child_col,
                        "parent_table": parent_table,
                        "parent_column": parent_col,
                        "constraint_exists": constraint_exists,
                        "orphaned_records": orphaned_count,
                        "status": "valid" if constraint_exists and orphaned_count == 0 else "issues"
                    }
                    
                    relationship_status.append(relationship_info)
                    
                    if not constraint_exists:
                        integrity_issues.append(f"Missing FK constraint: {child_table}.{child_col} -> {parent_table}.{parent_col}")
                    if orphaned_count > 0:
                        integrity_issues.append(f"Found {orphaned_count} orphaned records in {child_table}.{child_col}")
                        
                except Exception as e:
                    integrity_issues.append(f"Error checking {child_table}.{child_col}: {str(e)}")
            
            validation_result.details = {
                "relationships_checked": len(critical_relationships),
                "relationship_status": relationship_status,
                "integrity_issues": integrity_issues
            }
            
            if integrity_issues:
                validation_result.status = "failed"
                validation_result.issues = integrity_issues
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_indexes_and_performance(self) -> None:
        """Validate indexes and performance implications"""
        self.logger.info("📇 Validating Indexes and Performance...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Index and Performance Validation",
            category="Performance",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Check for critical indexes
            expected_indexes = {
                "valve_step_config": ["step_id"],
                "purge_step_config": ["step_id"],
                "loop_step_config": ["step_id"],
                "process_execution_state": ["execution_id"],
                "recipe_parameters": ["recipe_id"],
                "recipe_steps": ["recipe_id", "sequence_number"],
                "process_executions": ["machine_id", "recipe_id", "status"]
            }
            
            index_status = []
            performance_issues = []
            
            for table_name, expected_cols in expected_indexes.items():
                table_indexes = await self._get_table_indexes(table_name)
                
                for col in expected_cols:
                    has_index = any(col in idx["columns"] for idx in table_indexes)
                    
                    index_info = {
                        "table": table_name,
                        "column": col,
                        "has_index": has_index,
                        "index_type": next((idx["type"] for idx in table_indexes if col in idx["columns"]), None)
                    }
                    
                    index_status.append(index_info)
                    
                    if not has_index:
                        performance_issues.append(f"Missing index on {table_name}.{col}")
            
            # Test query performance on new tables
            performance_tests = await self._run_performance_spot_checks()
            
            validation_result.details = {
                "index_status": index_status,
                "performance_issues": performance_issues,
                "performance_tests": performance_tests
            }
            
            if performance_issues:
                validation_result.status = "warning"
                validation_result.issues = performance_issues
                validation_result.recommendations = [
                    "Consider adding indexes for frequently queried columns",
                    "Monitor query performance in production"
                ]
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_backward_compatibility(self) -> None:
        """Validate backward compatibility with existing code"""
        self.logger.info("🔄 Validating Backward Compatibility...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Backward Compatibility",
            category="Compatibility",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            compatibility_checks = []
            
            # Check that old table structures still exist or are properly handled
            legacy_tables = ["recipes", "recipe_steps", "process_executions", "machines"]
            
            for table in legacy_tables:
                exists = await self._table_exists(table)
                compatibility_checks.append({
                    "table": table,
                    "exists": exists,
                    "type": "legacy_table"
                })
            
            # Check that critical views/functions still work
            legacy_queries = [
                ("Recipe Basic Query", "SELECT id, name, description FROM recipes LIMIT 1"),
                ("Recipe with Steps", """
                    SELECT r.name, COUNT(rs.id) as step_count
                    FROM recipes r
                    LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
                    GROUP BY r.id, r.name
                    LIMIT 1
                """),
                ("Process Status Query", """
                    SELECT pe.status, COUNT(*) as count
                    FROM process_executions pe
                    GROUP BY pe.status
                """)
            ]
            
            query_compatibility = []
            
            for query_name, query_sql in legacy_queries:
                try:
                    await self.db.execute_query(query_sql)
                    query_compatibility.append({
                        "query": query_name,
                        "compatible": True,
                        "error": None
                    })
                except Exception as e:
                    query_compatibility.append({
                        "query": query_name,
                        "compatible": False,
                        "error": str(e)
                    })
            
            validation_result.details = {
                "table_compatibility": compatibility_checks,
                "query_compatibility": query_compatibility,
                "compatibility_summary": {
                    "tables_compatible": sum(1 for c in compatibility_checks if c["exists"]),
                    "queries_compatible": sum(1 for q in query_compatibility if q["compatible"]),
                    "total_tables_checked": len(compatibility_checks),
                    "total_queries_checked": len(query_compatibility)
                }
            }
            
            compatibility_issues = [q for q in query_compatibility if not q["compatible"]]
            
            if compatibility_issues:
                validation_result.status = "failed"
                validation_result.issues = [f"Query compatibility issue: {issue['query']} - {issue['error']}" 
                                          for issue in compatibility_issues]
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_code_integration(self) -> None:
        """Validate that application code works with new schema"""
        self.logger.info("💻 Validating Code Integration...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Application Code Integration",
            category="Code Integration",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            # Test code patterns that should work with new schema
            code_tests = []
            
            # Test 1: Recipe step loading pattern
            try:
                result = await self.db.execute_query("""
                    SELECT rs.*, vsc.valve_number, vsc.duration_ms as valve_duration,
                           psc.gas_type, psc.duration_ms as purge_duration,
                           lsc.iteration_count
                    FROM recipe_steps rs
                    LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                    LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                    LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                    WHERE rs.recipe_id = (SELECT id FROM recipes LIMIT 1)
                    ORDER BY rs.sequence_number
                """)
                
                code_tests.append({
                    "test": "recipe_step_loading_pattern",
                    "success": True,
                    "result_count": len(result) if result else 0
                })
                
            except Exception as e:
                code_tests.append({
                    "test": "recipe_step_loading_pattern",
                    "success": False,
                    "error": str(e)
                })
            
            # Test 2: Process state update pattern
            try:
                # Find a test process execution
                process_result = await self.db.execute_query("SELECT id FROM process_executions LIMIT 1")
                if process_result:
                    process_id = process_result[0]["id"]
                    
                    await self.db.execute_query("""
                        UPDATE process_execution_state 
                        SET current_step_index = 1,
                            progress = '{"test": true}',
                            last_updated = now()
                        WHERE execution_id = $1
                    """, [process_id])
                    
                    code_tests.append({
                        "test": "process_state_update_pattern",
                        "success": True
                    })
                else:
                    code_tests.append({
                        "test": "process_state_update_pattern",
                        "success": False,
                        "error": "No process executions available for testing"
                    })
                    
            except Exception as e:
                code_tests.append({
                    "test": "process_state_update_pattern",
                    "success": False,
                    "error": str(e)
                })
            
            # Test 3: Recipe parameter access pattern
            try:
                result = await self.db.execute_query("""
                    SELECT parameter_name, parameter_value, parameter_unit
                    FROM recipe_parameters
                    WHERE recipe_id = (SELECT id FROM recipes LIMIT 1)
                """)
                
                code_tests.append({
                    "test": "recipe_parameter_access_pattern",
                    "success": True,
                    "parameter_count": len(result) if result else 0
                })
                
            except Exception as e:
                code_tests.append({
                    "test": "recipe_parameter_access_pattern",
                    "success": False,
                    "error": str(e)
                })
            
            validation_result.details = {
                "code_tests": code_tests,
                "successful_tests": sum(1 for t in code_tests if t["success"]),
                "failed_tests": sum(1 for t in code_tests if not t["success"]),
                "total_tests": len(code_tests)
            }
            
            failed_tests = [t for t in code_tests if not t["success"]]
            
            if failed_tests:
                validation_result.status = "failed"
                validation_result.issues = [f"Code test failed: {test['test']} - {test.get('error', 'Unknown error')}" 
                                          for test in failed_tests]
                validation_result.recommendations = [
                    "Review application code for compatibility with new schema",
                    "Update data access patterns to use new table structure"
                ]
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_migration_completeness(self) -> None:
        """Validate overall migration completeness"""
        self.logger.info("✅ Validating Migration Completeness...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Migration Completeness Check",
            category="Migration Completeness",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            completeness_checks = {}
            
            # Check migration audit records
            migration_audit = await self.db.execute_query("""
                SELECT migration_name, executed_at, records_affected
                FROM migration_audit
                ORDER BY executed_at DESC
            """)
            
            completeness_checks["migration_audit"] = {
                "migration_count": len(migration_audit),
                "migrations": migration_audit
            }
            
            # Check for archived old data
            archived_data = await self.db.execute_query("""
                SELECT COUNT(*) as archived_count
                FROM recipe_step_configs_archive
            """)
            
            if archived_data:
                completeness_checks["data_archival"] = {
                    "archived_records": archived_data[0]["archived_count"]
                }
            
            # Verify no orphaned data
            orphaned_checks = []
            
            # Check for steps without configurations
            orphaned_steps = await self.db.execute_query("""
                SELECT COUNT(*) as orphaned_count
                FROM recipe_steps rs
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                WHERE rs.type IN ('valve', 'purge', 'loop')
                AND vsc.step_id IS NULL
                AND psc.step_id IS NULL
                AND lsc.step_id IS NULL
            """)
            
            if orphaned_steps:
                orphaned_checks.append({
                    "check": "steps_without_config",
                    "count": orphaned_steps[0]["orphaned_count"]
                })
            
            completeness_checks["orphaned_data_checks"] = orphaned_checks
            
            validation_result.details = completeness_checks
            
            # Determine status based on checks
            issues = []
            if orphaned_checks and any(check["count"] > 0 for check in orphaned_checks):
                issues.append("Found orphaned data that may indicate incomplete migration")
            
            if len(migration_audit) == 0:
                issues.append("No migration audit records found")
            
            if issues:
                validation_result.status = "warning"
                validation_result.issues = issues
                validation_result.recommendations = [
                    "Review migration logs for completeness",
                    "Investigate orphaned data and complete migration if necessary"
                ]
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _validate_rollback_capability(self) -> None:
        """Validate rollback capability"""
        self.logger.info("🔄 Validating Rollback Capability...")
        
        validation_result = MigrationValidationResult(
            validation_id=str(uuid4()),
            validation_name="Rollback Capability",
            category="Rollback",
            status="pending",
            timestamp=datetime.now(),
            details={}
        )
        
        try:
            rollback_checks = {}
            
            # Check if archived data exists for rollback
            archived_tables = ["recipe_step_configs_archive"]
            
            archive_status = []
            for table in archived_tables:
                try:
                    count_result = await self.db.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    count = count_result[0]["count"] if count_result else 0
                    
                    archive_status.append({
                        "table": table,
                        "exists": True,
                        "record_count": count
                    })
                    
                except Exception as e:
                    archive_status.append({
                        "table": table,
                        "exists": False,
                        "error": str(e)
                    })
            
            rollback_checks["archive_status"] = archive_status
            
            # Check migration reversibility
            reversibility_checks = []
            
            # Can we recreate old structure from new?
            try:
                # Test query that simulates old structure from new tables
                test_result = await self.db.execute_query("""
                    SELECT 
                        rs.id,
                        rs.recipe_id,
                        rs.sequence_number,
                        rs.name,
                        rs.type,
                        CASE 
                            WHEN rs.type = 'valve' THEN 
                                json_build_object('valve_number', vsc.valve_number, 'duration_ms', vsc.duration_ms)
                            WHEN rs.type = 'purge' THEN
                                json_build_object('duration_ms', psc.duration_ms, 'gas_type', psc.gas_type)
                            WHEN rs.type = 'loop' THEN
                                json_build_object('iteration_count', lsc.iteration_count)
                            ELSE NULL
                        END as config
                    FROM recipe_steps rs
                    LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                    LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                    LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                    LIMIT 5
                """)
                
                reversibility_checks.append({
                    "check": "config_reconstruction",
                    "success": True,
                    "sample_count": len(test_result) if test_result else 0
                })
                
            except Exception as e:
                reversibility_checks.append({
                    "check": "config_reconstruction",
                    "success": False,
                    "error": str(e)
                })
            
            rollback_checks["reversibility_checks"] = reversibility_checks
            
            validation_result.details = rollback_checks
            
            # Assess rollback capability
            issues = []
            
            missing_archives = [status for status in archive_status if not status["exists"]]
            if missing_archives:
                issues.append(f"Missing archive tables: {[s['table'] for s in missing_archives]}")
            
            failed_reversibility = [check for check in reversibility_checks if not check["success"]]
            if failed_reversibility:
                issues.append("Cannot reconstruct old structure from new schema")
            
            if issues:
                validation_result.status = "warning"
                validation_result.issues = issues
                validation_result.recommendations = [
                    "Ensure proper backup procedures before migration",
                    "Test rollback procedures in non-production environment"
                ]
            else:
                validation_result.status = "passed"
                
        except Exception as e:
            validation_result.status = "failed"
            validation_result.issues = [str(e)]
        
        self.validation_results.append(validation_result)
    
    async def _generate_migration_report(self) -> Dict[str, Any]:
        """Generate comprehensive migration validation report"""
        self.logger.info("📊 Generating Migration Validation Report...")
        
        # Categorize results
        results_by_category = {}
        for result in self.validation_results:
            category = result.category
            if category not in results_by_category:
                results_by_category[category] = []
            results_by_category[category].append(asdict(result))
        
        # Calculate summary statistics
        total_validations = len(self.validation_results)
        passed_validations = sum(1 for r in self.validation_results if r.status == "passed")
        failed_validations = sum(1 for r in self.validation_results if r.status == "failed")
        warning_validations = sum(1 for r in self.validation_results if r.status == "warning")
        
        # Generate recommendations
        recommendations = []
        critical_issues = []
        
        for result in self.validation_results:
            if result.status == "failed":
                critical_issues.extend(result.issues)
                recommendations.extend(result.recommendations)
            elif result.status == "warning":
                recommendations.extend(result.recommendations)
        
        # Remove duplicates
        recommendations = list(set(recommendations))
        critical_issues = list(set(critical_issues))
        
        # Migration status assessment
        if failed_validations > 0:
            migration_status = "FAILED"
            migration_assessment = "Migration validation failed - critical issues must be resolved"
        elif warning_validations > 0:
            migration_status = "WARNINGS"
            migration_assessment = "Migration completed with warnings - review recommendations"
        else:
            migration_status = "PASSED"
            migration_assessment = "Migration validation passed - schema migration successful"
        
        # Production readiness
        production_ready = (failed_validations == 0 and warning_validations <= 2)
        
        report = {
            "validator_id": self.validator_id,
            "validation_timestamp": datetime.now().isoformat(),
            "migration_status": migration_status,
            "migration_assessment": migration_assessment,
            "production_ready": production_ready,
            "summary": {
                "total_validations": total_validations,
                "passed": passed_validations,
                "failed": failed_validations,
                "warnings": warning_validations,
                "success_rate": passed_validations / total_validations if total_validations > 0 else 0
            },
            "results_by_category": results_by_category,
            "critical_issues": critical_issues,
            "recommendations": recommendations,
            "detailed_results": [asdict(r) for r in self.validation_results],
            "next_steps": self._generate_next_steps(migration_status, critical_issues, recommendations)
        }
        
        # Save report
        report_file = self.test_workspace / "migration_validation" / f"migration_validation_report_{self.validator_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"📋 Migration validation report saved: {report_file}")
        
        return report
    
    def _generate_next_steps(self, status: str, critical_issues: List[str], recommendations: List[str]) -> List[str]:
        """Generate next steps based on validation results"""
        next_steps = []
        
        if status == "FAILED":
            next_steps.append("🚫 DO NOT DEPLOY TO PRODUCTION")
            next_steps.append("🔧 Resolve all critical issues before proceeding")
            for issue in critical_issues[:3]:  # Top 3 issues
                next_steps.append(f"   - Fix: {issue}")
        
        elif status == "WARNINGS":
            next_steps.append("⚠️ Review warnings before production deployment")
            next_steps.append("📋 Address high-priority recommendations")
            for rec in recommendations[:3]:  # Top 3 recommendations
                next_steps.append(f"   - Consider: {rec}")
        
        else:
            next_steps.append("✅ Migration validation successful")
            next_steps.append("🚀 Ready for production deployment")
            next_steps.append("📊 Monitor system performance post-deployment")
        
        next_steps.extend([
            "📝 Update documentation with schema changes",
            "🧪 Run additional integration tests in staging",
            "📋 Prepare rollback procedures if needed"
        ])
        
        return next_steps
    
    # Helper methods
    async def _get_existing_tables(self) -> Set[str]:
        """Get set of existing table names"""
        result = await self.db.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        
        return {row["table_name"] for row in result}
    
    async def _get_table_columns(self, table_name: str) -> Dict[str, str]:
        """Get table columns with their data types"""
        result = await self.db.execute_query("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
            ORDER BY ordinal_position
        """, [table_name])
        
        return {row["column_name"]: row["data_type"] for row in result}
    
    async def _check_unique_constraint(self, table_name: str, column_name: str) -> bool:
        """Check if column has unique constraint"""
        result = await self.db.execute_query("""
            SELECT COUNT(*) as constraint_count
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = $1 
            AND tc.constraint_type = 'UNIQUE'
            AND kcu.column_name = $2
            AND tc.table_schema = 'public'
        """, [table_name, column_name])
        
        return result[0]["constraint_count"] > 0 if result else False
    
    async def _check_foreign_key(self, child_table: str, child_col: str, parent_table: str, parent_col: str) -> bool:
        """Check if foreign key constraint exists"""
        result = await self.db.execute_query("""
            SELECT COUNT(*) as fk_count
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu ON rc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
            WHERE kcu.table_name = $1 
            AND kcu.column_name = $2
            AND ccu.table_name = $3
            AND ccu.column_name = $4
            AND kcu.table_schema = 'public'
        """, [child_table, child_col, parent_table, parent_col])
        
        return result[0]["fk_count"] > 0 if result else False
    
    async def _get_column_type(self, table_name: str, column_name: str) -> Optional[str]:
        """Get column data type"""
        result = await self.db.execute_query("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = $1 AND column_name = $2 AND table_schema = 'public'
        """, [table_name, column_name])
        
        return result[0]["data_type"] if result else None
    
    def _types_compatible(self, actual_type: str, expected_type: str) -> bool:
        """Check if data types are compatible"""
        type_mappings = {
            "integer": ["integer", "int4", "int"],
            "numeric": ["numeric", "decimal", "real", "double precision", "float8"],
            "text": ["text", "character varying", "varchar", "character", "char"],
            "boolean": ["boolean", "bool"],
            "uuid": ["uuid"],
            "timestamp": ["timestamp with time zone", "timestamptz", "timestamp"],
            "jsonb": ["jsonb", "json"]
        }
        
        for expected, compatible_types in type_mappings.items():
            if expected_type == expected and actual_type in compatible_types:
                return True
        
        return actual_type == expected_type
    
    async def _get_table_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table indexes"""
        result = await self.db.execute_query("""
            SELECT 
                indexname,
                indexdef,
                CASE 
                    WHEN indexdef LIKE '%UNIQUE%' THEN 'unique'
                    ELSE 'regular'
                END as index_type
            FROM pg_indexes
            WHERE tablename = $1 AND schemaname = 'public'
        """, [table_name])
        
        indexes = []
        for row in result:
            # Extract column names from index definition
            indexdef = row["indexdef"]
            # Simple extraction - could be enhanced for complex indexes
            start = indexdef.find("(") + 1
            end = indexdef.find(")")
            columns_str = indexdef[start:end] if start > 0 and end > start else ""
            columns = [col.strip() for col in columns_str.split(",")]
            
            indexes.append({
                "name": row["indexname"],
                "type": row["index_type"],
                "columns": columns,
                "definition": indexdef
            })
        
        return indexes
    
    async def _run_performance_spot_checks(self) -> List[Dict[str, Any]]:
        """Run performance spot checks on new schema"""
        performance_tests = []
        
        test_queries = [
            ("Step Config Join", """
                SELECT rs.name, vsc.valve_number, psc.gas_type, lsc.iteration_count
                FROM recipe_steps rs
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                LIMIT 100
            """),
            ("Process State Query", """
                SELECT pe.status, pes.current_step_index, pes.progress
                FROM process_executions pe
                JOIN process_execution_state pes ON pe.id = pes.execution_id
                ORDER BY pe.start_time DESC
                LIMIT 50
            """)
        ]
        
        for query_name, query_sql in test_queries:
            start_time = time.time()
            try:
                result = await self.db.execute_query(query_sql)
                end_time = time.time()
                
                performance_tests.append({
                    "query": query_name,
                    "duration_ms": (end_time - start_time) * 1000,
                    "result_count": len(result) if result else 0,
                    "status": "success"
                })
                
            except Exception as e:
                performance_tests.append({
                    "query": query_name,
                    "duration_ms": 0,
                    "status": "failed",
                    "error": str(e)
                })
        
        return performance_tests
    
    async def _table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        result = await self.db.execute_query("""
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_name = $1 AND table_schema = 'public'
        """, [table_name])
        
        return result[0]["count"] > 0 if result else False

# Global migration validator instance  
migration_validator = SchemaMigrationValidator()

async def main():
    """Main migration validation execution"""
    print("🔍 Starting Schema Migration Validation...")
    
    try:
        # Initialize migration validator
        if not await migration_validator.initialize():
            print("❌ Migration validator initialization failed")
            return
        
        # Run complete migration validation
        report = await migration_validator.validate_complete_migration()
        
        # Print summary
        print("\n" + "="*60)
        print("🎯 SCHEMA MIGRATION VALIDATION COMPLETE")
        print("="*60)
        print(f"Migration Status: {report['migration_status']}")
        print(f"Production Ready: {'✅ YES' if report['production_ready'] else '❌ NO'}")
        print(f"Total Validations: {report['summary']['total_validations']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Warnings: {report['summary']['warnings']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1%}")
        
        if report["critical_issues"]:
            print(f"\n🚨 Critical Issues ({len(report['critical_issues'])}):")
            for issue in report["critical_issues"][:5]:  # Show first 5
                print(f"  - {issue}")
        
        if report["recommendations"]:
            print(f"\n💡 Recommendations ({len(report['recommendations'])}):")
            for rec in report["recommendations"][:3]:  # Show first 3
                print(f"  - {rec}")
        
        print(f"\n📋 Next Steps:")
        for step in report["next_steps"]:
            print(f"  {step}")
        
        print("="*60)
        print(report['migration_assessment'])
        print("="*60)
        
    except Exception as e:
        print(f"❌ Migration validation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import time
    asyncio.run(main())