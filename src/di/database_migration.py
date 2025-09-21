# File: src/di/database_migration.py
"""
Database migration utilities for zero-downtime schema changes.
Provides safe migration procedures with rollback capabilities.
"""
import asyncio
import time
import json
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
import uuid
from contextlib import asynccontextmanager

from src.log_setup import logger

class MigrationState(Enum):
    """Database migration states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class ValidationResult(Enum):
    """Data validation results"""
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"

@dataclass
class MigrationStep:
    """Individual migration step"""
    step_id: str
    name: str
    forward_sql: str
    rollback_sql: str
    validation_query: Optional[str] = None
    timeout_seconds: int = 300
    critical: bool = True
    depends_on: List[str] = field(default_factory=list)

@dataclass
class MigrationPlan:
    """Complete migration plan"""
    migration_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    steps: List[MigrationStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    target_schema_version: str = "1.0.0"
    rollback_timeout_seconds: int = 600
    enable_dual_write: bool = True
    validation_queries: List[str] = field(default_factory=list)

@dataclass
class MigrationResult:
    """Migration execution result"""
    migration_id: str
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    state: MigrationState = MigrationState.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False

class DatabaseMigrationManager:
    """
    Manager for database migrations with zero-downtime capabilities.

    Features:
    - Schema versioning
    - Dual-write pattern during migrations
    - Automated rollback on failures
    - Data consistency validation
    - Performance impact monitoring
    """

    def __init__(self, db_connection_factory: Callable):
        self.db_connection_factory = db_connection_factory
        self._migration_history: Dict[str, MigrationResult] = {}
        self._schema_version: str = "0.0.0"
        self._dual_write_active: bool = False
        self._validation_cache: Dict[str, Any] = {}

    async def execute_migration(
        self,
        migration_plan: MigrationPlan,
        dry_run: bool = False
    ) -> MigrationResult:
        """
        Execute a database migration plan.

        Args:
            migration_plan: Migration plan to execute
            dry_run: If True, validate but don't execute

        Returns:
            Migration result
        """
        result = MigrationResult(migration_id=migration_plan.migration_id)
        result.start_time = time.time()

        logger.info(f"Starting migration: {migration_plan.name} (ID: {migration_plan.migration_id})")

        try:
            result.state = MigrationState.RUNNING

            # Pre-migration validation
            if not await self._validate_migration_plan(migration_plan):
                raise ValueError("Migration plan validation failed")

            # Execute migration steps
            if not dry_run:
                await self._execute_migration_steps(migration_plan, result)
            else:
                logger.info("Dry run mode - migration validated but not executed")
                result.state = MigrationState.COMPLETED

            # Post-migration validation
            if not dry_run and migration_plan.validation_queries:
                if not await self._validate_migration_results(migration_plan):
                    raise ValueError("Post-migration validation failed")

            result.state = MigrationState.COMPLETED
            result.end_time = time.time()

            # Update schema version
            if not dry_run:
                self._schema_version = migration_plan.target_schema_version

            logger.info(f"Migration completed successfully: {migration_plan.name}")

        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            result.state = MigrationState.FAILED
            result.error_message = str(e)
            result.end_time = time.time()

            # Attempt rollback if not in dry run mode
            if not dry_run:
                try:
                    await self._rollback_migration(migration_plan, result)
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {str(rollback_error)}")

        finally:
            self._migration_history[migration_plan.migration_id] = result

        return result

    async def _validate_migration_plan(self, migration_plan: MigrationPlan) -> bool:
        """Validate migration plan before execution"""
        logger.info("Validating migration plan...")

        try:
            # Check dependencies
            step_ids = {step.step_id for step in migration_plan.steps}
            for step in migration_plan.steps:
                for dep in step.depends_on:
                    if dep not in step_ids:
                        logger.error(f"Step {step.step_id} depends on non-existent step: {dep}")
                        return False

            # Validate SQL syntax (basic check)
            for step in migration_plan.steps:
                if not step.forward_sql.strip():
                    logger.error(f"Step {step.step_id} has empty forward SQL")
                    return False
                if not step.rollback_sql.strip():
                    logger.error(f"Step {step.step_id} has empty rollback SQL")
                    return False

            # Check for potential breaking changes
            for step in migration_plan.steps:
                if await self._is_breaking_change(step):
                    logger.warning(f"Step {step.step_id} may be a breaking change")

            logger.info("Migration plan validation passed")
            return True

        except Exception as e:
            logger.error(f"Migration plan validation failed: {str(e)}")
            return False

    async def _is_breaking_change(self, step: MigrationStep) -> bool:
        """Check if a migration step represents a breaking change"""
        sql = step.forward_sql.upper()
        breaking_patterns = [
            'DROP TABLE',
            'DROP COLUMN',
            'ALTER TABLE',  # Could be breaking depending on specifics
            'RENAME TABLE',
            'RENAME COLUMN'
        ]

        return any(pattern in sql for pattern in breaking_patterns)

    async def _execute_migration_steps(
        self,
        migration_plan: MigrationPlan,
        result: MigrationResult
    ):
        """Execute migration steps in dependency order"""
        # Calculate execution order
        execution_order = self._calculate_execution_order(migration_plan.steps)

        # Enable dual-write if requested
        if migration_plan.enable_dual_write:
            await self._enable_dual_write_mode()

        try:
            for step in execution_order:
                logger.info(f"Executing migration step: {step.name}")
                step_result = await self._execute_migration_step(step)
                result.step_results[step.step_id] = step_result

                if not step_result.get('success', False) and step.critical:
                    raise RuntimeError(f"Critical migration step failed: {step.name}")

        finally:
            # Disable dual-write mode
            if migration_plan.enable_dual_write:
                await self._disable_dual_write_mode()

    def _calculate_execution_order(self, steps: List[MigrationStep]) -> List[MigrationStep]:
        """Calculate step execution order based on dependencies"""
        # Topological sort implementation
        remaining_steps = steps.copy()
        execution_order = []

        while remaining_steps:
            # Find steps with no unresolved dependencies
            ready_steps = []
            for step in remaining_steps:
                dependencies_met = all(
                    dep in [s.step_id for s in execution_order]
                    for dep in step.depends_on
                )
                if dependencies_met:
                    ready_steps.append(step)

            if not ready_steps:
                # Circular dependency or missing dependency
                raise ValueError("Circular or missing dependencies detected in migration steps")

            # Execute ready steps (could be parallelized in the future)
            for step in ready_steps:
                execution_order.append(step)
                remaining_steps.remove(step)

        return execution_order

    async def _execute_migration_step(self, step: MigrationStep) -> Dict[str, Any]:
        """Execute a single migration step"""
        step_result = {
            'step_id': step.step_id,
            'start_time': time.time(),
            'success': False,
            'error': None,
            'affected_rows': 0,
            'execution_time_ms': 0
        }

        try:
            # Get database connection
            async with self._get_db_connection() as db:
                start_time = time.perf_counter()

                # Execute the SQL with timeout
                result = await asyncio.wait_for(
                    self._execute_sql(db, step.forward_sql),
                    timeout=step.timeout_seconds
                )

                execution_time = (time.perf_counter() - start_time) * 1000
                step_result['execution_time_ms'] = execution_time
                step_result['affected_rows'] = result.get('affected_rows', 0)

                # Validate result if validation query provided
                if step.validation_query:
                    validation_result = await self._execute_sql(db, step.validation_query)
                    step_result['validation_result'] = validation_result

                step_result['success'] = True
                logger.info(
                    f"Step {step.step_id} completed in {execution_time:.2f}ms, "
                    f"affected {step_result['affected_rows']} rows"
                )

        except asyncio.TimeoutError:
            step_result['error'] = f"Step timed out after {step.timeout_seconds} seconds"
            logger.error(f"Migration step {step.step_id} timed out")
        except Exception as e:
            step_result['error'] = str(e)
            logger.error(f"Migration step {step.step_id} failed: {str(e)}")
        finally:
            step_result['end_time'] = time.time()

        return step_result

    async def _validate_migration_results(self, migration_plan: MigrationPlan) -> bool:
        """Validate migration results using validation queries"""
        logger.info("Validating migration results...")

        try:
            async with self._get_db_connection() as db:
                for query in migration_plan.validation_queries:
                    result = await self._execute_sql(db, query)

                    # Basic validation - query should not return empty result
                    if not result or not result.get('rows'):
                        logger.warning(f"Validation query returned empty result: {query}")
                        return False

            logger.info("Migration result validation passed")
            return True

        except Exception as e:
            logger.error(f"Migration result validation failed: {str(e)}")
            return False

    async def _rollback_migration(
        self,
        migration_plan: MigrationPlan,
        result: MigrationResult
    ):
        """Rollback migration by executing rollback SQL in reverse order"""
        logger.info(f"Rolling back migration: {migration_plan.name}")

        try:
            # Get executed steps in reverse order
            executed_steps = [
                step for step in migration_plan.steps
                if step.step_id in result.step_results
                and result.step_results[step.step_id].get('success', False)
            ]

            rollback_order = list(reversed(executed_steps))

            async with self._get_db_connection() as db:
                for step in rollback_order:
                    try:
                        logger.info(f"Rolling back step: {step.name}")
                        await self._execute_sql(db, step.rollback_sql)
                    except Exception as e:
                        logger.error(f"Failed to rollback step {step.step_id}: {str(e)}")
                        # Continue with other rollback steps

            result.rollback_performed = True
            result.state = MigrationState.ROLLED_BACK
            logger.info("Migration rollback completed")

        except Exception as e:
            logger.error(f"Migration rollback failed: {str(e)}")
            raise

    @asynccontextmanager
    async def _get_db_connection(self):
        """Get database connection from factory"""
        try:
            connection = await self.db_connection_factory()
            yield connection
        except Exception as e:
            logger.error(f"Failed to get database connection: {str(e)}")
            raise
        finally:
            # Connection cleanup would go here
            pass

    async def _execute_sql(self, db, sql: str) -> Dict[str, Any]:
        """Execute SQL and return result"""
        # This is a placeholder - actual implementation would depend on the database interface
        try:
            # For Supabase/PostgreSQL, this might be:
            # result = await db.execute(sql)

            # Placeholder implementation
            logger.debug(f"Executing SQL: {sql[:100]}...")

            return {
                'success': True,
                'affected_rows': 0,
                'rows': []
            }

        except Exception as e:
            logger.error(f"SQL execution failed: {str(e)}")
            raise

    async def _enable_dual_write_mode(self):
        """Enable dual-write mode for zero-downtime migrations"""
        if self._dual_write_active:
            return

        logger.info("Enabling dual-write mode for zero-downtime migration")
        self._dual_write_active = True

        # Implementation would configure the application to write to both old and new schemas
        # This ensures data consistency during the migration

    async def _disable_dual_write_mode(self):
        """Disable dual-write mode after migration completion"""
        if not self._dual_write_active:
            return

        logger.info("Disabling dual-write mode")
        self._dual_write_active = False

    def create_migration_plan(
        self,
        name: str,
        description: str = "",
        target_version: str = "1.0.0"
    ) -> MigrationPlan:
        """Create a new migration plan"""
        return MigrationPlan(
            name=name,
            description=description,
            target_schema_version=target_version
        )

    def add_migration_step(
        self,
        plan: MigrationPlan,
        name: str,
        forward_sql: str,
        rollback_sql: str,
        validation_query: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        critical: bool = True
    ) -> str:
        """Add a migration step to a plan"""
        step_id = str(uuid.uuid4())
        step = MigrationStep(
            step_id=step_id,
            name=name,
            forward_sql=forward_sql,
            rollback_sql=rollback_sql,
            validation_query=validation_query,
            depends_on=depends_on or [],
            critical=critical
        )

        plan.steps.append(step)
        return step_id

    def get_migration_history(self) -> List[MigrationResult]:
        """Get migration execution history"""
        return list(self._migration_history.values())

    def get_schema_version(self) -> str:
        """Get current schema version"""
        return self._schema_version

    def is_dual_write_active(self) -> bool:
        """Check if dual-write mode is active"""
        return self._dual_write_active

# Predefined migration plans for common ALD system updates
def create_component_parameter_id_migration() -> MigrationPlan:
    """Create migration plan for adding component_parameter_id column"""
    plan = MigrationPlan(
        name="Add component_parameter_id column",
        description="Add component_parameter_id column to parameter_value_history table",
        target_schema_version="1.1.0"
    )

    # Add the column
    manager = DatabaseMigrationManager(None)  # Factory will be set later
    manager.add_migration_step(
        plan,
        "Add component_parameter_id column",
        """
        ALTER TABLE parameter_value_history
        ADD COLUMN component_parameter_id UUID REFERENCES component_parameters(id);
        """,
        """
        ALTER TABLE parameter_value_history
        DROP COLUMN component_parameter_id;
        """,
        validation_query="SELECT component_parameter_id FROM parameter_value_history LIMIT 1;",
        critical=True
    )

    # Create index for performance
    manager.add_migration_step(
        plan,
        "Create index on component_parameter_id",
        """
        CREATE INDEX CONCURRENTLY idx_parameter_value_history_component_parameter_id
        ON parameter_value_history(component_parameter_id);
        """,
        """
        DROP INDEX idx_parameter_value_history_component_parameter_id;
        """,
        depends_on=[plan.steps[0].step_id],
        critical=False
    )

    return plan

def create_step_execution_history_migration() -> MigrationPlan:
    """Create migration plan for step execution history triggers"""
    plan = MigrationPlan(
        name="Add step execution history triggers",
        description="Add triggers for step execution history tracking",
        target_schema_version="1.2.0"
    )

    manager = DatabaseMigrationManager(None)

    # Create trigger function
    manager.add_migration_step(
        plan,
        "Create step execution history trigger function",
        """
        CREATE OR REPLACE FUNCTION update_step_execution_history()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO step_execution_history (step_id, execution_time, status, metadata)
            VALUES (NEW.id, NOW(), NEW.status, NEW.metadata);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
        """
        DROP FUNCTION IF EXISTS update_step_execution_history();
        """,
        critical=True
    )

    # Create the trigger
    manager.add_migration_step(
        plan,
        "Create step execution history trigger",
        """
        CREATE TRIGGER step_execution_history_trigger
        AFTER INSERT OR UPDATE ON recipe_steps
        FOR EACH ROW EXECUTE FUNCTION update_step_execution_history();
        """,
        """
        DROP TRIGGER IF EXISTS step_execution_history_trigger ON recipe_steps;
        """,
        depends_on=[plan.steps[0].step_id],
        critical=True
    )

    return plan

# Global migration manager instance
_migration_manager: Optional[DatabaseMigrationManager] = None

def get_migration_manager(db_connection_factory: Optional[Callable] = None) -> DatabaseMigrationManager:
    """Get the global migration manager instance"""
    global _migration_manager
    if _migration_manager is None:
        if db_connection_factory is None:
            raise RuntimeError("Database connection factory required for first-time initialization")
        _migration_manager = DatabaseMigrationManager(db_connection_factory)
    return _migration_manager

async def execute_system_migrations(db_connection_factory: Callable) -> bool:
    """Execute all system migrations"""
    manager = get_migration_manager(db_connection_factory)

    migrations = [
        create_component_parameter_id_migration(),
        create_step_execution_history_migration()
    ]

    for migration in migrations:
        logger.info(f"Executing migration: {migration.name}")
        result = await manager.execute_migration(migration)

        if result.state != MigrationState.COMPLETED:
            logger.error(f"Migration failed: {migration.name}")
            return False

    logger.info("All system migrations completed successfully")
    return True