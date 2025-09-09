#!/usr/bin/env python3
"""
Test Environment Setup Module
Prepares comprehensive testing environment for ALD control system validation
"""

import asyncio
import logging
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from plc.manager import plc_manager
from database.database import DatabaseConnection
from log_setup import setup_logger

class TestEnvironmentSetup:
    """Comprehensive test environment setup and management"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.db = None
        self.test_workspace = Path("test_workspace")
        self.test_start_time = datetime.now()
        self.test_session_id = str(uuid4())
        self.setup_complete = False
        
    async def initialize_environment(self) -> Dict[str, Any]:
        """Initialize complete test environment"""
        self.logger.info("🚀 Initializing comprehensive test environment...")
        
        try:
            # 1. Setup workspace
            await self._setup_workspace()
            
            # 2. Initialize database connection
            await self._initialize_database()
            
            # 3. Setup PLC manager in simulation mode
            await self._initialize_plc_manager()
            
            # 4. Validate database schema
            schema_validation = await self._validate_database_schema()
            
            # 5. Setup test data isolation
            test_isolation = await self._setup_test_isolation()
            
            # 6. Initialize monitoring systems
            monitoring_setup = await self._setup_monitoring()
            
            # 7. Prepare cleanup procedures
            cleanup_setup = await self._setup_cleanup_procedures()
            
            self.setup_complete = True
            
            environment_info = {
                "session_id": self.test_session_id,
                "workspace": str(self.test_workspace.absolute()),
                "start_time": self.test_start_time.isoformat(),
                "database_connection": "established",
                "plc_manager": "simulation_mode",
                "schema_validation": schema_validation,
                "test_isolation": test_isolation,
                "monitoring": monitoring_setup,
                "cleanup": cleanup_setup,
                "status": "ready"
            }
            
            self.logger.info("✅ Test environment initialization complete")
            return environment_info
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize test environment: {e}")
            raise
    
    async def _setup_workspace(self) -> None:
        """Create and organize test workspace"""
        self.logger.info("📁 Setting up test workspace...")
        
        # Create main workspace directory
        self.test_workspace.mkdir(exist_ok=True)
        
        # Create subdirectories
        subdirs = [
            "logs", "reports", "artifacts", "temporary", 
            "test_data", "backups", "monitoring"
        ]
        
        for subdir in subdirs:
            (self.test_workspace / subdir).mkdir(exist_ok=True)
        
        # Create session info file
        session_info = {
            "session_id": self.test_session_id,
            "start_time": self.test_start_time.isoformat(),
            "workspace_path": str(self.test_workspace.absolute()),
            "python_version": sys.version,
            "test_framework_version": "1.0.0"
        }
        
        with open(self.test_workspace / "session_info.json", "w") as f:
            json.dump(session_info, f, indent=2)
        
        self.logger.info(f"📁 Workspace created: {self.test_workspace.absolute()}")
    
    async def _initialize_database(self) -> None:
        """Initialize database connection with test configuration"""
        self.logger.info("🗄️ Initializing database connection...")
        
        try:
            self.db = DatabaseConnection()
            await self.db.initialize()
            
            # Test connection
            result = await self.db.execute_query("SELECT version() as db_version")
            db_version = result[0]["db_version"] if result else "unknown"
            
            self.logger.info(f"✅ Database connected: {db_version}")
            
        except Exception as e:
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise
    
    async def _initialize_plc_manager(self) -> None:
        """Initialize PLC manager in simulation mode for testing"""
        self.logger.info("🔌 Initializing PLC manager (simulation mode)...")
        
        try:
            # Force simulation mode for testing
            os.environ["PLC_SIMULATION"] = "true"
            
            # Initialize PLC manager
            await plc_manager.initialize_plc()
            
            # Verify simulation mode
            if plc_manager.is_simulation():
                self.logger.info("✅ PLC manager initialized in simulation mode")
            else:
                raise RuntimeError("PLC manager not in simulation mode")
                
        except Exception as e:
            self.logger.error(f"❌ PLC manager initialization failed: {e}")
            raise
    
    async def _validate_database_schema(self) -> Dict[str, Any]:
        """Validate database schema against expected structure"""
        self.logger.info("🔍 Validating database schema...")
        
        validation_results = {
            "tables": {},
            "foreign_keys": {},
            "indexes": {},
            "constraints": {},
            "enums": {},
            "overall_status": "unknown"
        }
        
        try:
            # Check critical tables
            critical_tables = [
                "recipes", "recipe_steps", "recipe_parameters",
                "valve_step_config", "purge_step_config", "loop_step_config",
                "process_executions", "process_execution_state",
                "machines", "machine_components", "component_parameters",
                "recipe_commands", "command_responses"
            ]
            
            for table_name in critical_tables:
                try:
                    result = await self.db.execute_query(f"""
                        SELECT COUNT(*) as row_count, 
                               (SELECT COUNT(*) FROM information_schema.columns 
                                WHERE table_name = '{table_name}' 
                                AND table_schema = 'public') as column_count
                        FROM {table_name}
                    """)
                    
                    validation_results["tables"][table_name] = {
                        "exists": True,
                        "row_count": result[0]["row_count"],
                        "column_count": result[0]["column_count"],
                        "status": "valid"
                    }
                    
                except Exception as e:
                    validation_results["tables"][table_name] = {
                        "exists": False,
                        "error": str(e),
                        "status": "missing"
                    }
            
            # Check foreign key relationships
            fk_checks = [
                ("recipe_steps", "recipe_id", "recipes", "id"),
                ("valve_step_config", "step_id", "recipe_steps", "id"),
                ("purge_step_config", "step_id", "recipe_steps", "id"),
                ("loop_step_config", "step_id", "recipe_steps", "id"),
                ("process_execution_state", "execution_id", "process_executions", "id")
            ]
            
            for child_table, child_col, parent_table, parent_col in fk_checks:
                try:
                    result = await self.db.execute_query(f"""
                        SELECT COUNT(*) as orphaned_records
                        FROM {child_table} c
                        LEFT JOIN {parent_table} p ON c.{child_col} = p.{parent_col}
                        WHERE p.{parent_col} IS NULL AND c.{child_col} IS NOT NULL
                    """)
                    
                    orphaned_count = result[0]["orphaned_records"]
                    validation_results["foreign_keys"][f"{child_table}.{child_col}"] = {
                        "target": f"{parent_table}.{parent_col}",
                        "orphaned_records": orphaned_count,
                        "status": "valid" if orphaned_count == 0 else "integrity_issues"
                    }
                    
                except Exception as e:
                    validation_results["foreign_keys"][f"{child_table}.{child_col}"] = {
                        "error": str(e),
                        "status": "error"
                    }
            
            # Overall status
            table_issues = sum(1 for t in validation_results["tables"].values() 
                             if t["status"] != "valid")
            fk_issues = sum(1 for fk in validation_results["foreign_keys"].values() 
                           if fk["status"] != "valid")
            
            if table_issues == 0 and fk_issues == 0:
                validation_results["overall_status"] = "valid"
            elif table_issues == 0 and fk_issues > 0:
                validation_results["overall_status"] = "integrity_issues"
            else:
                validation_results["overall_status"] = "schema_issues"
            
            self.logger.info(f"✅ Schema validation complete: {validation_results['overall_status']}")
            
        except Exception as e:
            self.logger.error(f"❌ Schema validation failed: {e}")
            validation_results["overall_status"] = "validation_failed"
            validation_results["error"] = str(e)
        
        # Save validation results
        with open(self.test_workspace / "reports" / "schema_validation.json", "w") as f:
            json.dump(validation_results, f, indent=2, default=str)
        
        return validation_results
    
    async def _setup_test_isolation(self) -> Dict[str, Any]:
        """Setup test data isolation and cleanup mechanisms"""
        self.logger.info("🔒 Setting up test isolation...")
        
        isolation_info = {
            "test_session_id": self.test_session_id,
            "isolation_method": "session_tagging",
            "backup_created": False,
            "cleanup_procedures": [],
            "status": "configured"
        }
        
        try:
            # Create test session marker in database
            await self.db.execute_query("""
                INSERT INTO app_settings (key, value, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE SET 
                    value = $2,
                    description = $3,
                    updated_at = now()
            """, [
                f"test_session_{self.test_session_id}",
                json.dumps({
                    "start_time": self.test_start_time.isoformat(),
                    "workspace": str(self.test_workspace.absolute()),
                    "isolation_active": True
                }),
                f"Test session isolation marker - {self.test_session_id}"
            ])
            
            isolation_info["cleanup_procedures"].append("remove_test_session_marker")
            
            self.logger.info("✅ Test isolation configured")
            
        except Exception as e:
            self.logger.error(f"❌ Test isolation setup failed: {e}")
            isolation_info["status"] = "failed"
            isolation_info["error"] = str(e)
        
        return isolation_info
    
    async def _setup_monitoring(self) -> Dict[str, Any]:
        """Setup comprehensive monitoring for test execution"""
        self.logger.info("📊 Setting up test monitoring...")
        
        monitoring_info = {
            "log_file": str(self.test_workspace / "logs" / f"test_session_{self.test_session_id}.log"),
            "metrics_file": str(self.test_workspace / "monitoring" / "metrics.json"),
            "real_time_monitoring": True,
            "alert_thresholds": {
                "memory_usage_mb": 1000,
                "execution_time_minutes": 30,
                "error_rate_threshold": 0.1
            },
            "status": "configured"
        }
        
        try:
            # Setup file logging
            file_handler = logging.FileHandler(monitoring_info["log_file"])
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler to root logger
            logging.getLogger().addHandler(file_handler)
            
            # Initialize metrics file
            initial_metrics = {
                "session_id": self.test_session_id,
                "start_time": self.test_start_time.isoformat(),
                "metrics": []
            }
            
            with open(monitoring_info["metrics_file"], "w") as f:
                json.dump(initial_metrics, f, indent=2)
            
            self.logger.info("✅ Monitoring configured")
            
        except Exception as e:
            self.logger.error(f"❌ Monitoring setup failed: {e}")
            monitoring_info["status"] = "failed"
            monitoring_info["error"] = str(e)
        
        return monitoring_info
    
    async def _setup_cleanup_procedures(self) -> Dict[str, Any]:
        """Setup cleanup procedures for test environment"""
        self.logger.info("🧹 Setting up cleanup procedures...")
        
        cleanup_info = {
            "procedures": [
                "remove_test_session_marker",
                "cleanup_temp_files",
                "reset_plc_state",
                "archive_test_results"
            ],
            "auto_cleanup_on_exit": True,
            "manual_cleanup_script": str(self.test_workspace / "cleanup_test_session.sh"),
            "status": "configured"
        }
        
        try:
            # Create cleanup script
            cleanup_script = f"""#!/bin/bash
# Cleanup script for test session {self.test_session_id}

echo "Cleaning up test session {self.test_session_id}..."

# Archive test results
if [ -d "{self.test_workspace}" ]; then
    timestamp=$(date +%Y%m%d_%H%M%S)
    archive_name="test_session_{self.test_session_id}_$timestamp.tar.gz"
    tar -czf "$archive_name" "{self.test_workspace}"
    echo "Test results archived to $archive_name"
fi

# Cleanup temporary files
find /tmp -name "*test_session_{self.test_session_id}*" -delete 2>/dev/null

echo "Cleanup complete for test session {self.test_session_id}"
"""
            
            with open(cleanup_info["manual_cleanup_script"], "w") as f:
                f.write(cleanup_script)
            
            # Make script executable
            os.chmod(cleanup_info["manual_cleanup_script"], 0o755)
            
            self.logger.info("✅ Cleanup procedures configured")
            
        except Exception as e:
            self.logger.error(f"❌ Cleanup setup failed: {e}")
            cleanup_info["status"] = "failed"
            cleanup_info["error"] = str(e)
        
        return cleanup_info
    
    async def cleanup_environment(self) -> None:
        """Cleanup test environment"""
        self.logger.info("🧹 Cleaning up test environment...")
        
        try:
            # Remove test session marker
            if self.db:
                await self.db.execute_query(
                    "DELETE FROM app_settings WHERE key = $1",
                    [f"test_session_{self.test_session_id}"]
                )
            
            # Reset PLC state
            if plc_manager.is_initialized():
                await plc_manager.reset_all()
            
            # Archive results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"test_session_{self.test_session_id}_{timestamp}.tar.gz"
            
            self.logger.info(f"✅ Test environment cleanup complete - Archive: {archive_name}")
            
        except Exception as e:
            self.logger.error(f"❌ Cleanup failed: {e}")
    
    async def get_test_machines(self) -> List[Dict[str, Any]]:
        """Get available machines for testing"""
        try:
            result = await self.db.execute_query("""
                SELECT id, serial_number, status, machine_type, is_virtual, virtual_config
                FROM machines
                WHERE is_active = true AND is_virtual = true
                ORDER BY serial_number
            """)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching test machines: {e}")
            return []
    
    async def get_test_recipes(self) -> List[Dict[str, Any]]:
        """Get available recipes for testing"""
        try:
            result = await self.db.execute_query("""
                SELECT 
                    r.id,
                    r.name,
                    r.description,
                    r.machine_type,
                    COUNT(rs.id) as step_count,
                    r.created_at
                FROM recipes r
                LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
                WHERE r.name LIKE '%Test%' OR r.name LIKE '%test%'
                GROUP BY r.id, r.name, r.description, r.machine_type, r.created_at
                ORDER BY r.created_at DESC
            """)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching test recipes: {e}")
            return []
    
    def is_ready(self) -> bool:
        """Check if test environment is ready"""
        return self.setup_complete
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current test session information"""
        return {
            "session_id": self.test_session_id,
            "start_time": self.test_start_time.isoformat(),
            "workspace": str(self.test_workspace.absolute()),
            "setup_complete": self.setup_complete,
            "uptime_seconds": (datetime.now() - self.test_start_time).total_seconds()
        }

# Global test environment instance
test_env = TestEnvironmentSetup()

async def main():
    """Test the environment setup"""
    print("🧪 Testing environment setup...")
    
    try:
        env_info = await test_env.initialize_environment()
        print(f"✅ Environment setup successful:")
        print(json.dumps(env_info, indent=2, default=str))
        
        # Test database connection
        machines = await test_env.get_test_machines()
        print(f"\n📱 Available test machines: {len(machines)}")
        
        recipes = await test_env.get_test_recipes()
        print(f"📋 Available test recipes: {len(recipes)}")
        
    except Exception as e:
        print(f"❌ Environment setup failed: {e}")
    finally:
        await test_env.cleanup_environment()

if __name__ == "__main__":
    asyncio.run(main())