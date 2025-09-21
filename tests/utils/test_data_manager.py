"""
Test Data Management System for ALD Control System CI/CD Pipeline.

This module provides comprehensive test data seeding, cleanup, and management
utilities for automated testing environments.
"""

import os
import json
import asyncio
import tempfile
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class TestDataSet:
    """Represents a complete test data set."""
    name: str
    description: str
    parameters: List[Dict[str, Any]]
    recipes: List[Dict[str, Any]]
    commands: List[Dict[str, Any]]
    machines: List[Dict[str, Any]]
    created_at: str

class TestDataManager:
    """Manages test data lifecycle for CI/CD testing."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(__file__).parent / "data"
        self.base_path.mkdir(exist_ok=True)
        self.current_dataset: Optional[TestDataSet] = None

    def create_minimal_dataset(self) -> TestDataSet:
        """Create minimal test dataset for unit tests."""
        return TestDataSet(
            name="minimal",
            description="Minimal dataset for fast unit tests",
            parameters=[
                {
                    "parameter_id": 1,
                    "name": "Test Parameter 1",
                    "modbus_address": 1001,
                    "data_type": "float",
                    "scaling_factor": 1.0,
                    "unit": "V"
                },
                {
                    "parameter_id": 2,
                    "name": "Test Parameter 2",
                    "modbus_address": 1002,
                    "data_type": "float",
                    "scaling_factor": 0.1,
                    "unit": "A"
                }
            ],
            recipes=[
                {
                    "recipe_id": 1,
                    "name": "Test Recipe",
                    "steps": [
                        {"type": "valve", "valve_id": 1, "state": "open", "duration": 1.0},
                        {"type": "parameter", "parameter_id": 1, "value": 50.0},
                        {"type": "purge", "duration": 2.0}
                    ]
                }
            ],
            commands=[
                {
                    "command_id": 1,
                    "command_type": "start_recipe",
                    "payload": {"recipe_id": 1},
                    "status": "pending",
                    "machine_id": "test-machine"
                }
            ],
            machines=[
                {
                    "machine_id": "test-machine",
                    "name": "Test Machine",
                    "location": "Test Lab",
                    "plc_hostname": "simulation",
                    "status": "active"
                }
            ],
            created_at=datetime.now().isoformat()
        )

    def create_integration_dataset(self) -> TestDataSet:
        """Create comprehensive dataset for integration tests."""
        return TestDataSet(
            name="integration",
            description="Comprehensive dataset for integration testing",
            parameters=[
                {
                    "parameter_id": i,
                    "name": f"Integration Parameter {i}",
                    "modbus_address": 1000 + i,
                    "data_type": "float",
                    "scaling_factor": 1.0 if i % 2 == 0 else 0.1,
                    "unit": "V" if i % 2 == 0 else "A"
                }
                for i in range(1, 21)  # 20 parameters
            ],
            recipes=[
                {
                    "recipe_id": 1,
                    "name": "Integration Recipe 1",
                    "steps": [
                        {"type": "valve", "valve_id": 1, "state": "open", "duration": 2.0},
                        {"type": "parameter", "parameter_id": 1, "value": 100.0},
                        {"type": "loop", "iterations": 3, "steps": [
                            {"type": "parameter", "parameter_id": 2, "value": 75.0},
                            {"type": "purge", "duration": 1.0}
                        ]},
                        {"type": "valve", "valve_id": 1, "state": "close", "duration": 1.0}
                    ]
                },
                {
                    "recipe_id": 2,
                    "name": "Integration Recipe 2",
                    "steps": [
                        {"type": "parameter", "parameter_id": 3, "value": 200.0},
                        {"type": "purge", "duration": 5.0}
                    ]
                }
            ],
            commands=[
                {
                    "command_id": i,
                    "command_type": "start_recipe" if i % 3 == 0 else "set_parameter",
                    "payload": {"recipe_id": 1} if i % 3 == 0 else {"parameter_id": i % 10 + 1, "value": 50.0 * i},
                    "status": "pending",
                    "machine_id": "test-machine-integration"
                }
                for i in range(1, 11)
            ],
            machines=[
                {
                    "machine_id": "test-machine-integration",
                    "name": "Integration Test Machine",
                    "location": "Integration Lab",
                    "plc_hostname": "simulation",
                    "status": "active"
                }
            ],
            created_at=datetime.now().isoformat()
        )

    def create_performance_dataset(self) -> TestDataSet:
        """Create large dataset for performance testing."""
        return TestDataSet(
            name="performance",
            description="Large dataset for performance and stress testing",
            parameters=[
                {
                    "parameter_id": i,
                    "name": f"Performance Parameter {i}",
                    "modbus_address": 1000 + i,
                    "data_type": "float",
                    "scaling_factor": 1.0,
                    "unit": "V"
                }
                for i in range(1, 501)  # 500 parameters
            ],
            recipes=[
                {
                    "recipe_id": i,
                    "name": f"Performance Recipe {i}",
                    "steps": [
                        {"type": "parameter", "parameter_id": j, "value": 100.0 + j}
                        for j in range(1, 51)  # 50 steps per recipe
                    ]
                }
                for i in range(1, 101)  # 100 recipes
            ],
            commands=[
                {
                    "command_id": i,
                    "command_type": "start_recipe",
                    "payload": {"recipe_id": (i % 100) + 1},
                    "status": "pending",
                    "machine_id": "test-machine-performance"
                }
                for i in range(1, 1001)  # 1000 commands
            ],
            machines=[
                {
                    "machine_id": "test-machine-performance",
                    "name": "Performance Test Machine",
                    "location": "Performance Lab",
                    "plc_hostname": "simulation",
                    "status": "active"
                }
            ],
            created_at=datetime.now().isoformat()
        )

    def create_security_dataset(self) -> TestDataSet:
        """Create dataset with security test scenarios."""
        malicious_inputs = [
            "'; DROP TABLE parameters; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "\x00\x01\x02\x03",
            "A" * 10000,
            "admin'; UNION SELECT * FROM users; --"
        ]

        return TestDataSet(
            name="security",
            description="Dataset for security testing with malicious inputs",
            parameters=[
                {
                    "parameter_id": i,
                    "name": f"Security Test Parameter {i}",
                    "modbus_address": 2000 + i,
                    "data_type": "string",
                    "scaling_factor": 1.0,
                    "unit": "test",
                    "malicious_input": malicious_inputs[i % len(malicious_inputs)]
                }
                for i in range(1, len(malicious_inputs) + 1)
            ],
            recipes=[
                {
                    "recipe_id": 1,
                    "name": "Security Test Recipe",
                    "steps": [
                        {"type": "parameter", "parameter_id": 1, "value": input_val}
                        for input_val in malicious_inputs[:5]
                    ]
                }
            ],
            commands=[
                {
                    "command_id": i,
                    "command_type": "set_parameter",
                    "payload": {
                        "parameter_id": 1,
                        "value": malicious_inputs[i % len(malicious_inputs)]
                    },
                    "status": "pending",
                    "machine_id": "test-machine-security"
                }
                for i in range(len(malicious_inputs))
            ],
            machines=[
                {
                    "machine_id": "test-machine-security",
                    "name": "Security Test Machine",
                    "location": "Security Lab",
                    "plc_hostname": "simulation",
                    "status": "active"
                }
            ],
            created_at=datetime.now().isoformat()
        )

    def save_dataset(self, dataset: TestDataSet) -> Path:
        """Save dataset to file."""
        file_path = self.base_path / f"{dataset.name}_dataset.json"
        with open(file_path, 'w') as f:
            json.dump(asdict(dataset), f, indent=2)
        logger.info(f"Saved dataset '{dataset.name}' to {file_path}")
        return file_path

    def load_dataset(self, name: str) -> TestDataSet:
        """Load dataset from file."""
        file_path = self.base_path / f"{name}_dataset.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset '{name}' not found at {file_path}")

        with open(file_path, 'r') as f:
            data = json.load(f)

        dataset = TestDataSet(**data)
        self.current_dataset = dataset
        logger.info(f"Loaded dataset '{name}' from {file_path}")
        return dataset

    async def seed_database(self, dataset: TestDataSet, database_service) -> bool:
        """Seed database with test dataset."""
        try:
            # Clear existing test data
            await self.cleanup_database(database_service)

            # Insert machines
            for machine in dataset.machines:
                await database_service.execute_query(
                    "INSERT INTO machines (machine_id, name, location, plc_hostname, status) VALUES (?, ?, ?, ?, ?)",
                    (machine["machine_id"], machine["name"], machine["location"],
                     machine["plc_hostname"], machine["status"])
                )

            # Insert parameters
            for param in dataset.parameters:
                await database_service.execute_query(
                    "INSERT INTO parameters (parameter_id, name, modbus_address, data_type, scaling_factor, unit) VALUES (?, ?, ?, ?, ?, ?)",
                    (param["parameter_id"], param["name"], param["modbus_address"],
                     param["data_type"], param["scaling_factor"], param["unit"])
                )

            # Insert recipes
            for recipe in dataset.recipes:
                await database_service.execute_query(
                    "INSERT INTO recipes (recipe_id, name, steps, created_at) VALUES (?, ?, ?, ?)",
                    (recipe["recipe_id"], recipe["name"], json.dumps(recipe["steps"]),
                     recipe.get("created_at", datetime.now().isoformat()))
                )

            # Insert commands
            for command in dataset.commands:
                await database_service.execute_query(
                    "INSERT INTO commands (command_id, command_type, payload, status, machine_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (command["command_id"], command["command_type"], json.dumps(command["payload"]),
                     command["status"], command["machine_id"],
                     command.get("created_at", datetime.now().isoformat()))
                )

            logger.info(f"Successfully seeded database with dataset '{dataset.name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to seed database with dataset '{dataset.name}': {e}")
            return False

    async def cleanup_database(self, database_service) -> bool:
        """Clean up test data from database."""
        try:
            # Delete in reverse dependency order
            cleanup_queries = [
                "DELETE FROM process_data_points WHERE machine_id LIKE 'test-%'",
                "DELETE FROM parameter_value_history WHERE machine_id LIKE 'test-%'",
                "DELETE FROM commands WHERE machine_id LIKE 'test-%'",
                "DELETE FROM recipes WHERE name LIKE 'Test %' OR name LIKE '%Test%'",
                "DELETE FROM parameters WHERE name LIKE 'Test %' OR name LIKE '%Test%'",
                "DELETE FROM machines WHERE machine_id LIKE 'test-%'"
            ]

            for query in cleanup_queries:
                await database_service.execute_query(query)

            logger.info("Successfully cleaned up test data from database")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup test data from database: {e}")
            return False

    def setup_test_environment(self, test_type: str = "minimal") -> TestDataSet:
        """Setup complete test environment for specified test type."""
        logger.info(f"Setting up test environment for: {test_type}")

        # Create appropriate dataset
        if test_type == "minimal":
            dataset = self.create_minimal_dataset()
        elif test_type == "integration":
            dataset = self.create_integration_dataset()
        elif test_type == "performance":
            dataset = self.create_performance_dataset()
        elif test_type == "security":
            dataset = self.create_security_dataset()
        else:
            raise ValueError(f"Unknown test type: {test_type}")

        # Save dataset
        self.save_dataset(dataset)
        self.current_dataset = dataset

        # Set environment variables
        os.environ.update({
            "TEST_DATASET": test_type,
            "TEST_MACHINE_ID": dataset.machines[0]["machine_id"],
            "TEST_DATA_PATH": str(self.base_path),
        })

        logger.info(f"Test environment setup complete for: {test_type}")
        return dataset

    def teardown_test_environment(self):
        """Teardown test environment and cleanup."""
        logger.info("Tearing down test environment")

        # Clean environment variables
        test_env_vars = [
            "TEST_DATASET", "TEST_MACHINE_ID", "TEST_DATA_PATH"
        ]
        for var in test_env_vars:
            os.environ.pop(var, None)

        self.current_dataset = None
        logger.info("Test environment teardown complete")

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate test data usage report."""
        if not self.current_dataset:
            return {"error": "No active dataset"}

        return {
            "dataset_name": self.current_dataset.name,
            "description": self.current_dataset.description,
            "statistics": {
                "parameters_count": len(self.current_dataset.parameters),
                "recipes_count": len(self.current_dataset.recipes),
                "commands_count": len(self.current_dataset.commands),
                "machines_count": len(self.current_dataset.machines),
            },
            "created_at": self.current_dataset.created_at,
            "data_path": str(self.base_path)
        }

# Utility functions for CI/CD scripts
async def setup_ci_test_data(test_type: str = "minimal") -> TestDataManager:
    """Setup test data for CI/CD environment."""
    manager = TestDataManager()
    dataset = manager.setup_test_environment(test_type)

    # Try to seed database if available
    try:
        from abstractions.interfaces import IDatabaseService
        # Actual database seeding would happen here in real scenario
        logger.info("Database seeding skipped in CI environment")
    except ImportError:
        logger.info("Database service not available for seeding")

    return manager

def cleanup_ci_test_data(manager: TestDataManager):
    """Cleanup test data in CI/CD environment."""
    if manager:
        manager.teardown_test_environment()
    logger.info("CI test data cleanup complete")

if __name__ == "__main__":
    # CLI interface for test data management
    import argparse

    parser = argparse.ArgumentParser(description="Manage test data for ALD Control System")
    parser.add_argument("action", choices=["setup", "cleanup", "report"],
                       help="Action to perform")
    parser.add_argument("--type", choices=["minimal", "integration", "performance", "security"],
                       default="minimal", help="Type of test dataset")

    args = parser.parse_args()

    manager = TestDataManager()

    if args.action == "setup":
        dataset = manager.setup_test_environment(args.type)
        print(f"Setup complete: {dataset.name}")

    elif args.action == "cleanup":
        manager.teardown_test_environment()
        print("Cleanup complete")

    elif args.action == "report":
        report = manager.generate_test_report()
        print(json.dumps(report, indent=2))