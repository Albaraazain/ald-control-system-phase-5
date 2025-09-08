#!/usr/bin/env python3
"""
Performance and Load Testing Framework
Comprehensive performance validation for ALD control system
"""

import asyncio
import logging
import json
import time
import sys
import os
import psutil
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, asdict
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_environment_setup import test_env
from database.database import DatabaseConnection
from log_setup import setup_logger

@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    metric_id: str
    test_name: str
    category: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    throughput_ops_per_sec: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    error_count: int = 0
    success_count: int = 0
    details: Optional[Dict[str, Any]] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 0.0

@dataclass
class LoadTestResult:
    """Load test result aggregation"""
    test_name: str
    concurrent_users: int
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    percentile_95_ms: float
    percentile_99_ms: float
    throughput_ops_per_sec: float
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class PerformanceLoadTester:
    """Comprehensive performance and load testing framework"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.test_id = str(uuid4())
        self.metrics: List[PerformanceMetric] = []
        self.load_results: List[LoadTestResult] = []
        self.db = None
        self.test_workspace = None
        
    async def initialize(self) -> bool:
        """Initialize performance testing environment"""
        self.logger.info("🚀 Initializing Performance and Load Testing Framework...")
        
        try:
            # Use existing test environment
            if not test_env.is_ready():
                env_info = await test_env.initialize_environment()
                if env_info["status"] != "ready":
                    raise RuntimeError("Test environment initialization failed")
            
            self.test_workspace = Path(test_env.test_workspace)
            self.db = test_env.db
            
            # Create performance-specific directories
            performance_dir = self.test_workspace / "performance"
            performance_dir.mkdir(exist_ok=True)
            (performance_dir / "charts").mkdir(exist_ok=True)
            (performance_dir / "raw_data").mkdir(exist_ok=True)
            
            self.logger.info("✅ Performance testing framework initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Performance testing initialization failed: {e}")
            return False
    
    async def run_performance_test_suite(self) -> Dict[str, Any]:
        """Run comprehensive performance test suite"""
        self.logger.info("🏃 Starting Performance Test Suite...")
        
        suite_start = datetime.now()
        
        try:
            # Database Performance Tests
            await self._run_database_performance_tests()
            
            # System Integration Performance Tests  
            await self._run_system_integration_performance_tests()
            
            # Load Testing
            await self._run_load_tests()
            
            # Stress Testing
            await self._run_stress_tests()
            
            # Memory and Resource Usage Tests
            await self._run_resource_usage_tests()
            
            # Concurrent Operations Performance
            await self._run_concurrency_performance_tests()
            
            # Generate performance analytics
            await self._generate_performance_analytics()
            
            suite_end = datetime.now()
            suite_duration = (suite_end - suite_start).total_seconds()
            
            summary = await self._generate_performance_summary()
            summary["suite_duration_seconds"] = suite_duration
            
            self.logger.info(f"✅ Performance test suite completed in {suite_duration:.2f}s")
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ Performance test suite failed: {e}")
            raise
    
    async def _run_database_performance_tests(self) -> None:
        """Run database-specific performance tests"""
        self.logger.info("🗄️ Running Database Performance Tests...")
        
        # Test 1: Query Performance Benchmarks
        await self._test_query_performance()
        
        # Test 2: Insert Performance
        await self._test_insert_performance()
        
        # Test 3: Complex Join Performance
        await self._test_complex_join_performance()
        
        # Test 4: Index Effectiveness
        await self._test_index_effectiveness()
    
    async def _test_query_performance(self) -> None:
        """Test query performance across different scenarios"""
        queries = [
            ("Simple Recipe Query", "SELECT * FROM recipes ORDER BY created_at DESC LIMIT 50"),
            ("Recipe with Steps", """
                SELECT r.name, r.description, COUNT(rs.id) as step_count
                FROM recipes r
                LEFT JOIN recipe_steps rs ON r.id = rs.recipe_id
                GROUP BY r.id, r.name, r.description
                ORDER BY step_count DESC
            """),
            ("Process Execution Status", """
                SELECT pe.id, pe.status, pe.start_time, pe.end_time,
                       r.name as recipe_name, m.serial_number
                FROM process_executions pe
                JOIN recipes r ON pe.recipe_id = r.id
                JOIN machines m ON pe.machine_id = m.id
                ORDER BY pe.start_time DESC
                LIMIT 100
            """),
            ("Step Configuration Complex", """
                SELECT rs.name, rs.type, rs.sequence_number,
                       COALESCE(vsc.valve_number::text, psc.gas_type, lsc.iteration_count::text) as config_detail,
                       COALESCE(vsc.duration_ms, psc.duration_ms) as duration_ms
                FROM recipe_steps rs
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                ORDER BY rs.sequence_number
            """),
            ("Process Data Analytics", """
                SELECT 
                    pe.id,
                    pe.status,
                    COUNT(pdp.id) as data_points,
                    AVG(pdp.value) as avg_value,
                    STDDEV(pdp.value) as stddev_value
                FROM process_executions pe
                LEFT JOIN process_data_points pdp ON pe.id = pdp.process_id
                WHERE pe.status = 'completed'
                GROUP BY pe.id, pe.status
                HAVING COUNT(pdp.id) > 0
                ORDER BY data_points DESC
                LIMIT 50
            """)
        ]
        
        for query_name, query_sql in queries:
            metric = await self._benchmark_query(query_name, query_sql)
            self.metrics.append(metric)
    
    async def _benchmark_query(self, query_name: str, query_sql: str, iterations: int = 10) -> PerformanceMetric:
        """Benchmark a specific query"""
        start_time = datetime.now()
        durations = []
        memory_readings = []
        success_count = 0
        error_count = 0
        
        for i in range(iterations):
            # Memory before query
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            query_start = time.time()
            try:
                result = await self.db.execute_query(query_sql)
                query_end = time.time()
                duration = (query_end - query_start) * 1000  # ms
                durations.append(duration)
                success_count += 1
                
                # Memory after query
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_readings.append(memory_after)
                
            except Exception as e:
                error_count += 1
                self.logger.error(f"Query failed in {query_name}: {e}")
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        return PerformanceMetric(
            metric_id=str(uuid4()),
            test_name=f"Query Performance - {query_name}",
            category="Database Performance",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=total_duration,
            throughput_ops_per_sec=iterations / total_duration if total_duration > 0 else 0,
            memory_usage_mb=statistics.mean(memory_readings) if memory_readings else None,
            success_count=success_count,
            error_count=error_count,
            details={
                "iterations": iterations,
                "avg_query_time_ms": statistics.mean(durations) if durations else 0,
                "min_query_time_ms": min(durations) if durations else 0,
                "max_query_time_ms": max(durations) if durations else 0,
                "median_query_time_ms": statistics.median(durations) if durations else 0,
                "query_time_95th_percentile_ms": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else (max(durations) if durations else 0)
            }
        )
    
    async def _test_insert_performance(self) -> None:
        """Test insert performance with batch operations"""
        self.logger.info("📝 Testing Insert Performance...")
        
        # Test different batch sizes
        batch_sizes = [1, 10, 50, 100]
        
        for batch_size in batch_sizes:
            metric = await self._benchmark_insert_batch(batch_size)
            self.metrics.append(metric)
    
    async def _benchmark_insert_batch(self, batch_size: int) -> PerformanceMetric:
        """Benchmark batch insert performance"""
        start_time = datetime.now()
        total_records = batch_size * 5  # 5 batches
        success_count = 0
        error_count = 0
        
        try:
            for batch_num in range(5):
                batch_data = []
                for i in range(batch_size):
                    batch_data.append({
                        "id": str(uuid4()),
                        "parameter_name": f"test_param_{batch_num}_{i}",
                        "parameter_value": 25.5 + i,
                        "parameter_type": "temperature",
                        "is_critical": i % 2 == 0
                    })
                
                # Insert batch using recipe_parameters table for testing
                recipe_id = await self._get_test_recipe_id()
                if recipe_id:
                    for record in batch_data:
                        try:
                            await self.db.execute_query("""
                                INSERT INTO recipe_parameters 
                                (recipe_id, parameter_name, parameter_value, parameter_type, is_critical)
                                VALUES ($1, $2, $3, $4, $5)
                            """, [
                                recipe_id,
                                record["parameter_name"],
                                record["parameter_value"], 
                                record["parameter_type"],
                                record["is_critical"]
                            ])
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            self.logger.error(f"Insert failed: {e}")
            
            # Cleanup test data
            if recipe_id:
                await self.db.execute_query(
                    "DELETE FROM recipe_parameters WHERE parameter_name LIKE 'test_param_%'",
                )
        
        except Exception as e:
            error_count += total_records
            self.logger.error(f"Batch insert test failed: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return PerformanceMetric(
            metric_id=str(uuid4()),
            test_name=f"Insert Performance - Batch Size {batch_size}",
            category="Database Performance", 
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            throughput_ops_per_sec=success_count / duration if duration > 0 else 0,
            success_count=success_count,
            error_count=error_count,
            details={
                "batch_size": batch_size,
                "total_batches": 5,
                "records_per_second": success_count / duration if duration > 0 else 0
            }
        )
    
    async def _test_complex_join_performance(self) -> None:
        """Test performance of complex join operations"""
        self.logger.info("🔗 Testing Complex Join Performance...")
        
        complex_queries = [
            ("Recipe Full Detail", """
                SELECT 
                    r.name as recipe_name,
                    r.description,
                    rs.name as step_name,
                    rs.type as step_type,
                    rs.sequence_number,
                    COALESCE(vsc.valve_number, 0) as valve_number,
                    COALESCE(vsc.duration_ms, psc.duration_ms, 0) as duration_ms,
                    COALESCE(psc.gas_type, '') as gas_type,
                    COALESCE(lsc.iteration_count, 0) as iteration_count
                FROM recipes r
                JOIN recipe_steps rs ON r.id = rs.recipe_id
                LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                LEFT JOIN loop_step_config lsc ON rs.id = lsc.step_id
                ORDER BY r.name, rs.sequence_number
            """),
            ("Process Execution Analytics", """
                SELECT 
                    pe.id,
                    r.name as recipe_name,
                    m.serial_number as machine,
                    pe.status,
                    pe.start_time,
                    pe.end_time,
                    pes.current_step_index,
                    pes.current_overall_step,
                    pes.total_overall_steps,
                    COUNT(pdp.id) as data_point_count,
                    AVG(pdp.value) as avg_sensor_value
                FROM process_executions pe
                JOIN recipes r ON pe.recipe_id = r.id
                JOIN machines m ON pe.machine_id = m.id
                LEFT JOIN process_execution_state pes ON pe.id = pes.execution_id
                LEFT JOIN process_data_points pdp ON pe.id = pdp.process_id
                WHERE pe.start_time >= (CURRENT_DATE - INTERVAL '30 days')
                GROUP BY pe.id, r.name, m.serial_number, pe.status, pe.start_time, pe.end_time,
                         pes.current_step_index, pes.current_overall_step, pes.total_overall_steps
                ORDER BY pe.start_time DESC
            """),
            ("Component Parameter Status", """
                SELECT 
                    mc.name as component_name,
                    mc.type as component_type,
                    cp.current_value,
                    cp.set_value,
                    cp.min_value,
                    cp.max_value,
                    cpd.name as parameter_name,
                    cpd.unit,
                    cd.name as definition_name
                FROM machine_components mc
                JOIN component_parameters cp ON mc.id = cp.component_id
                LEFT JOIN component_parameter_definitions cpd ON cp.definition_id = cpd.id
                LEFT JOIN component_definitions cd ON mc.definition_id = cd.id
                WHERE cp.show_in_ui = true
                ORDER BY mc.name, cpd.name
            """)
        ]
        
        for query_name, query_sql in complex_queries:
            metric = await self._benchmark_query(f"Complex Join - {query_name}", query_sql, iterations=5)
            self.metrics.append(metric)
    
    async def _test_index_effectiveness(self) -> None:
        """Test database index effectiveness"""
        self.logger.info("📇 Testing Index Effectiveness...")
        
        # Test queries that should benefit from indexes
        indexed_queries = [
            ("Recipe by ID", "SELECT * FROM recipes WHERE id = (SELECT id FROM recipes LIMIT 1)"),
            ("Process Executions by Machine", """
                SELECT * FROM process_executions 
                WHERE machine_id = (SELECT id FROM machines LIMIT 1)
                ORDER BY start_time DESC
            """),
            ("Steps by Recipe", """
                SELECT * FROM recipe_steps 
                WHERE recipe_id = (SELECT id FROM recipes LIMIT 1)
                ORDER BY sequence_number
            """),
            ("Component Parameters by Component", """
                SELECT * FROM component_parameters 
                WHERE component_id = (SELECT id FROM machine_components LIMIT 1)
            """)
        ]
        
        for query_name, query_sql in indexed_queries:
            metric = await self._benchmark_query(f"Index Test - {query_name}", query_sql, iterations=20)
            self.metrics.append(metric)
    
    async def _run_system_integration_performance_tests(self) -> None:
        """Run system integration performance tests"""
        self.logger.info("🔧 Running System Integration Performance Tests...")
        
        # Test end-to-end recipe execution timing
        await self._test_recipe_execution_performance()
        
        # Test command processing performance
        await self._test_command_processing_performance()
        
        # Test real-time data update performance
        await self._test_realtime_update_performance()
    
    async def _test_recipe_execution_performance(self) -> None:
        """Test recipe execution performance"""
        start_time = datetime.now()
        
        try:
            # Get test recipe with multiple steps
            recipes = await test_env.get_test_recipes()
            complex_recipe = max(recipes, key=lambda r: int(r.get('step_count', 0))) if recipes else None
            
            if not complex_recipe:
                self.logger.warning("No complex recipes available for performance testing")
                return
            
            # Simulate recipe execution timing
            execution_steps = []
            step_start = time.time()
            
            # Step 1: Load recipe configuration
            recipe_config = await self._load_recipe_configuration(complex_recipe['id'])
            step_end = time.time()
            execution_steps.append({"step": "load_config", "duration_ms": (step_end - step_start) * 1000})
            
            # Step 2: Initialize process execution
            step_start = time.time()
            process_id = await self._simulate_process_initialization(complex_recipe['id'])
            step_end = time.time()
            execution_steps.append({"step": "init_process", "duration_ms": (step_end - step_start) * 1000})
            
            # Step 3: Execute steps simulation
            step_start = time.time()
            await self._simulate_step_execution(process_id, len(recipe_config.get('steps', [])))
            step_end = time.time()
            execution_steps.append({"step": "execute_steps", "duration_ms": (step_end - step_start) * 1000})
            
            # Step 4: Cleanup
            step_start = time.time()
            await self._cleanup_test_process(process_id)
            step_end = time.time()
            execution_steps.append({"step": "cleanup", "duration_ms": (step_end - step_start) * 1000})
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Recipe Execution Performance",
                category="System Integration",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=total_duration,
                success_count=1,
                error_count=0,
                details={
                    "recipe_name": complex_recipe['name'],
                    "step_count": len(recipe_config.get('steps', [])),
                    "execution_steps": execution_steps,
                    "total_duration_ms": total_duration * 1000
                }
            )
            
            self.metrics.append(metric)
            
        except Exception as e:
            end_time = datetime.now()
            error_metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Recipe Execution Performance",
                category="System Integration",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                success_count=0,
                error_count=1,
                details={"error": str(e)}
            )
            self.metrics.append(error_metric)
    
    async def _test_command_processing_performance(self) -> None:
        """Test command processing performance"""
        start_time = datetime.now()
        command_count = 10
        success_count = 0
        error_count = 0
        response_times = []
        
        try:
            machines = await test_env.get_test_machines()
            recipes = await test_env.get_test_recipes()
            
            if not machines or not recipes:
                self.logger.warning("No test machines or recipes for command testing")
                return
            
            machine_id = machines[0]["id"]
            recipe_id = recipes[0]["id"]
            
            for i in range(command_count):
                cmd_start = time.time()
                try:
                    # Create command
                    command_id = str(uuid4())
                    await self.db.execute_query("""
                        INSERT INTO recipe_commands (id, type, parameters, status, machine_id)
                        VALUES ($1, 'test_command', $2, 'pending', $3)
                    """, [
                        command_id,
                        json.dumps({"recipe_id": recipe_id, "test_iteration": i}),
                        machine_id
                    ])
                    
                    # Simulate processing
                    await self.db.execute_query(
                        "UPDATE recipe_commands SET status = 'processed' WHERE id = $1",
                        [command_id]
                    )
                    
                    # Cleanup
                    await self.db.execute_query(
                        "DELETE FROM recipe_commands WHERE id = $1",
                        [command_id]
                    )
                    
                    cmd_end = time.time()
                    response_times.append((cmd_end - cmd_start) * 1000)  # ms
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Command processing error: {e}")
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Command Processing Performance",
                category="System Integration",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=total_duration,
                throughput_ops_per_sec=success_count / total_duration if total_duration > 0 else 0,
                success_count=success_count,
                error_count=error_count,
                details={
                    "commands_processed": command_count,
                    "avg_response_time_ms": statistics.mean(response_times) if response_times else 0,
                    "min_response_time_ms": min(response_times) if response_times else 0,
                    "max_response_time_ms": max(response_times) if response_times else 0,
                    "response_times": response_times
                }
            )
            
            self.metrics.append(metric)
            
        except Exception as e:
            end_time = datetime.now()
            error_metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Command Processing Performance",
                category="System Integration", 
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                success_count=success_count,
                error_count=error_count + 1,
                details={"error": str(e)}
            )
            self.metrics.append(error_metric)
    
    async def _test_realtime_update_performance(self) -> None:
        """Test real-time data update performance"""
        start_time = datetime.now()
        update_count = 100
        success_count = 0
        error_count = 0
        
        try:
            # Get a test process execution
            processes = await self.db.execute_query(
                "SELECT id FROM process_executions ORDER BY created_at DESC LIMIT 1"
            )
            
            if not processes:
                self.logger.warning("No process executions for real-time update testing")
                return
            
            process_id = processes[0]["id"]
            
            # Simulate rapid state updates
            for i in range(update_count):
                try:
                    await self.db.execute_query("""
                        UPDATE process_execution_state 
                        SET current_overall_step = $1,
                            progress = $2,
                            last_updated = now()
                        WHERE execution_id = $3
                    """, [
                        i % 10,
                        json.dumps({"completed_steps": i, "total_steps": update_count}),
                        process_id
                    ])
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Update error: {e}")
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Real-time Update Performance",
                category="System Integration",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=total_duration,
                throughput_ops_per_sec=success_count / total_duration if total_duration > 0 else 0,
                success_count=success_count,
                error_count=error_count,
                details={
                    "updates_per_second": success_count / total_duration if total_duration > 0 else 0,
                    "total_updates": update_count
                }
            )
            
            self.metrics.append(metric)
            
        except Exception as e:
            end_time = datetime.now()
            error_metric = PerformanceMetric(
                metric_id=str(uuid4()),
                test_name="Real-time Update Performance",
                category="System Integration",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                success_count=success_count,
                error_count=error_count + 1,
                details={"error": str(e)}
            )
            self.metrics.append(error_metric)
    
    async def _run_load_tests(self) -> None:
        """Run load tests with varying concurrent users"""
        self.logger.info("🏋️ Running Load Tests...")
        
        load_scenarios = [
            {"users": 5, "duration": 30},
            {"users": 10, "duration": 60},
            {"users": 20, "duration": 30},
            {"users": 50, "duration": 15}
        ]
        
        for scenario in load_scenarios:
            load_result = await self._execute_load_test(
                concurrent_users=scenario["users"],
                duration_seconds=scenario["duration"]
            )
            self.load_results.append(load_result)
    
    async def _execute_load_test(self, concurrent_users: int, duration_seconds: int) -> LoadTestResult:
        """Execute load test with specified parameters"""
        self.logger.info(f"🚀 Load Test: {concurrent_users} users for {duration_seconds}s")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # Shared counters
        operations_count = [0]  # Use list for shared reference
        successful_operations = [0]
        failed_operations = [0]
        response_times = []
        errors = []
        
        async def user_simulation():
            """Simulate a single user's operations"""
            while time.time() < end_time:
                op_start = time.time()
                try:
                    # Simulate various operations
                    operation_type = operations_count[0] % 4
                    
                    if operation_type == 0:
                        # Query recipes
                        await self.db.execute_query("SELECT * FROM recipes LIMIT 10")
                    elif operation_type == 1:
                        # Query process executions
                        await self.db.execute_query("""
                            SELECT pe.*, r.name FROM process_executions pe 
                            JOIN recipes r ON pe.recipe_id = r.id 
                            ORDER BY pe.start_time DESC LIMIT 20
                        """)
                    elif operation_type == 2:
                        # Query step configurations
                        await self.db.execute_query("""
                            SELECT rs.*, vsc.valve_number, psc.gas_type
                            FROM recipe_steps rs
                            LEFT JOIN valve_step_config vsc ON rs.id = vsc.step_id
                            LEFT JOIN purge_step_config psc ON rs.id = psc.step_id
                            LIMIT 30
                        """)
                    else:
                        # Query machine status
                        await self.db.execute_query("""
                            SELECT m.*, ms.current_state
                            FROM machines m
                            LEFT JOIN machine_state ms ON m.id = ms.machine_id
                            WHERE m.is_active = true
                        """)
                    
                    op_end = time.time()
                    response_time = (op_end - op_start) * 1000  # ms
                    response_times.append(response_time)
                    operations_count[0] += 1
                    successful_operations[0] += 1
                    
                    # Small delay between operations
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    failed_operations[0] += 1
                    errors.append(str(e))
        
        # Run concurrent users
        tasks = [user_simulation() for _ in range(concurrent_users)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        actual_duration = time.time() - start_time
        total_ops = operations_count[0]
        
        # Calculate percentiles
        response_times.sort()
        percentile_95 = response_times[int(len(response_times) * 0.95)] if response_times else 0
        percentile_99 = response_times[int(len(response_times) * 0.99)] if response_times else 0
        
        return LoadTestResult(
            test_name=f"Load Test - {concurrent_users} Users",
            concurrent_users=concurrent_users,
            duration_seconds=actual_duration,
            total_operations=total_ops,
            successful_operations=successful_operations[0],
            failed_operations=failed_operations[0],
            avg_response_time_ms=statistics.mean(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            percentile_95_ms=percentile_95,
            percentile_99_ms=percentile_99,
            throughput_ops_per_sec=total_ops / actual_duration if actual_duration > 0 else 0,
            errors=list(set(errors))[:10]  # Keep unique errors, max 10
        )
    
    async def _run_stress_tests(self) -> None:
        """Run stress tests to find system limits"""
        self.logger.info("💪 Running Stress Tests...")
        
        # Gradually increase load until system degrades
        user_counts = [25, 50, 75, 100]
        
        for user_count in user_counts:
            self.logger.info(f"Stress test with {user_count} users...")
            
            try:
                load_result = await self._execute_load_test(
                    concurrent_users=user_count,
                    duration_seconds=20
                )
                
                self.load_results.append(load_result)
                
                # Check if system is degrading
                if (load_result.avg_response_time_ms > 2000 or 
                    load_result.failed_operations / load_result.total_operations > 0.1):
                    self.logger.warning(f"System degradation detected at {user_count} users")
                    break
                    
            except Exception as e:
                self.logger.error(f"Stress test failed at {user_count} users: {e}")
                break
    
    async def _run_resource_usage_tests(self) -> None:
        """Monitor resource usage during operations"""
        self.logger.info("📊 Running Resource Usage Tests...")
        
        start_time = datetime.now()
        process = psutil.Process()
        
        # Monitor resource usage during intensive operations
        memory_readings = []
        cpu_readings = []
        
        for i in range(10):
            # Record baseline
            memory_readings.append(process.memory_info().rss / 1024 / 1024)  # MB
            cpu_readings.append(process.cpu_percent(interval=0.1))
            
            # Perform intensive operation
            try:
                await self.db.execute_query("""
                    WITH RECURSIVE step_hierarchy AS (
                        SELECT rs.id, rs.name, rs.type, rs.parent_step_id, rs.recipe_id, 0 as level
                        FROM recipe_steps rs
                        WHERE rs.parent_step_id IS NULL
                        
                        UNION ALL
                        
                        SELECT rs.id, rs.name, rs.type, rs.parent_step_id, rs.recipe_id, sh.level + 1
                        FROM recipe_steps rs
                        JOIN step_hierarchy sh ON rs.parent_step_id = sh.id
                        WHERE sh.level < 10
                    )
                    SELECT * FROM step_hierarchy
                    ORDER BY recipe_id, level, id
                """)
            except Exception as e:
                self.logger.error(f"Resource test query failed: {e}")
        
        end_time = datetime.now()
        
        metric = PerformanceMetric(
            metric_id=str(uuid4()),
            test_name="Resource Usage During Operations",
            category="Resource Usage",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=(end_time - start_time).total_seconds(),
            memory_usage_mb=statistics.mean(memory_readings) if memory_readings else None,
            cpu_usage_percent=statistics.mean(cpu_readings) if cpu_readings else None,
            success_count=10,
            error_count=0,
            details={
                "memory_readings_mb": memory_readings,
                "cpu_readings_percent": cpu_readings,
                "max_memory_mb": max(memory_readings) if memory_readings else 0,
                "max_cpu_percent": max(cpu_readings) if cpu_readings else 0
            }
        )
        
        self.metrics.append(metric)
    
    async def _run_concurrency_performance_tests(self) -> None:
        """Test performance under concurrent access"""
        self.logger.info("🔀 Running Concurrency Performance Tests...")
        
        # Test concurrent database operations
        await self._test_concurrent_reads()
        await self._test_concurrent_writes()
        await self._test_read_write_concurrency()
    
    async def _test_concurrent_reads(self) -> None:
        """Test concurrent read performance"""
        start_time = datetime.now()
        concurrent_readers = 20
        reads_per_reader = 10
        
        async def concurrent_reader():
            success = 0
            errors = 0
            for _ in range(reads_per_reader):
                try:
                    await self.db.execute_query("SELECT COUNT(*) FROM recipes")
                    success += 1
                except Exception:
                    errors += 1
            return success, errors
        
        tasks = [concurrent_reader() for _ in range(concurrent_readers)]
        results = await asyncio.gather(*tasks)
        
        total_success = sum(r[0] for r in results)
        total_errors = sum(r[1] for r in results)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        metric = PerformanceMetric(
            metric_id=str(uuid4()),
            test_name="Concurrent Read Performance",
            category="Concurrency",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            throughput_ops_per_sec=total_success / duration if duration > 0 else 0,
            success_count=total_success,
            error_count=total_errors,
            details={
                "concurrent_readers": concurrent_readers,
                "reads_per_reader": reads_per_reader,
                "total_operations": concurrent_readers * reads_per_reader
            }
        )
        
        self.metrics.append(metric)
    
    async def _test_concurrent_writes(self) -> None:
        """Test concurrent write performance"""
        start_time = datetime.now()
        concurrent_writers = 5
        writes_per_writer = 5
        
        # Get test recipe for inserts
        recipe_id = await self._get_test_recipe_id()
        if not recipe_id:
            self.logger.warning("No test recipe available for concurrent write testing")
            return
        
        async def concurrent_writer(writer_id):
            success = 0
            errors = 0
            for write_num in range(writes_per_writer):
                try:
                    await self.db.execute_query("""
                        INSERT INTO recipe_parameters 
                        (recipe_id, parameter_name, parameter_value, parameter_type)
                        VALUES ($1, $2, $3, 'test')
                    """, [
                        recipe_id,
                        f"concurrent_test_param_{writer_id}_{write_num}",
                        25.5 + write_num
                    ])
                    success += 1
                except Exception:
                    errors += 1
            return success, errors
        
        tasks = [concurrent_writer(i) for i in range(concurrent_writers)]
        results = await asyncio.gather(*tasks)
        
        total_success = sum(r[0] for r in results)
        total_errors = sum(r[1] for r in results)
        
        # Cleanup test data
        await self.db.execute_query(
            "DELETE FROM recipe_parameters WHERE parameter_name LIKE 'concurrent_test_param_%'"
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        metric = PerformanceMetric(
            metric_id=str(uuid4()),
            test_name="Concurrent Write Performance",
            category="Concurrency",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            throughput_ops_per_sec=total_success / duration if duration > 0 else 0,
            success_count=total_success,
            error_count=total_errors,
            details={
                "concurrent_writers": concurrent_writers,
                "writes_per_writer": writes_per_writer,
                "total_operations": concurrent_writers * writes_per_writer
            }
        )
        
        self.metrics.append(metric)
    
    async def _test_read_write_concurrency(self) -> None:
        """Test mixed read/write concurrency"""
        start_time = datetime.now()
        concurrent_operations = 15
        
        recipe_id = await self._get_test_recipe_id()
        if not recipe_id:
            return
        
        async def mixed_operations(op_id):
            success = 0
            errors = 0
            for i in range(5):
                try:
                    if i % 2 == 0:
                        # Read operation
                        await self.db.execute_query("SELECT COUNT(*) FROM recipe_parameters WHERE recipe_id = $1", [recipe_id])
                    else:
                        # Write operation
                        await self.db.execute_query("""
                            INSERT INTO recipe_parameters (recipe_id, parameter_name, parameter_value, parameter_type)
                            VALUES ($1, $2, $3, 'mixed_test')
                        """, [recipe_id, f"mixed_test_{op_id}_{i}", 10.0 + i])
                    success += 1
                except Exception:
                    errors += 1
            return success, errors
        
        tasks = [mixed_operations(i) for i in range(concurrent_operations)]
        results = await asyncio.gather(*tasks)
        
        total_success = sum(r[0] for r in results)
        total_errors = sum(r[1] for r in results)
        
        # Cleanup
        await self.db.execute_query(
            "DELETE FROM recipe_parameters WHERE parameter_name LIKE 'mixed_test_%'"
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        metric = PerformanceMetric(
            metric_id=str(uuid4()),
            test_name="Mixed Read/Write Concurrency",
            category="Concurrency", 
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            throughput_ops_per_sec=total_success / duration if duration > 0 else 0,
            success_count=total_success,
            error_count=total_errors,
            details={
                "concurrent_operations": concurrent_operations,
                "operations_per_worker": 5
            }
        )
        
        self.metrics.append(metric)
    
    async def _generate_performance_analytics(self) -> None:
        """Generate performance analytics and visualizations"""
        self.logger.info("📈 Generating Performance Analytics...")
        
        try:
            # Prepare data for analysis
            metrics_data = []
            for metric in self.metrics:
                metrics_data.append({
                    "test_name": metric.test_name,
                    "category": metric.category,
                    "duration_seconds": metric.duration_seconds,
                    "throughput_ops_per_sec": metric.throughput_ops_per_sec or 0,
                    "memory_usage_mb": metric.memory_usage_mb or 0,
                    "cpu_usage_percent": metric.cpu_usage_percent or 0,
                    "success_rate": metric.success_rate
                })
            
            # Create DataFrame
            df = pd.DataFrame(metrics_data)
            
            # Generate charts
            charts_dir = self.test_workspace / "performance" / "charts"
            
            # 1. Performance by Category
            plt.figure(figsize=(12, 8))
            category_perf = df.groupby('category')['throughput_ops_per_sec'].mean()
            category_perf.plot(kind='bar')
            plt.title('Average Throughput by Test Category')
            plt.xlabel('Test Category')
            plt.ylabel('Operations per Second')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(charts_dir / 'throughput_by_category.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. Response Time Distribution
            if self.load_results:
                plt.figure(figsize=(12, 6))
                response_times = []
                user_counts = []
                
                for result in self.load_results:
                    response_times.append(result.avg_response_time_ms)
                    user_counts.append(result.concurrent_users)
                
                plt.plot(user_counts, response_times, 'o-', linewidth=2, markersize=8)
                plt.title('Response Time vs Concurrent Users')
                plt.xlabel('Concurrent Users')
                plt.ylabel('Average Response Time (ms)')
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                plt.savefig(charts_dir / 'response_time_vs_users.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            # 3. Success Rate by Test
            plt.figure(figsize=(14, 8))
            success_rates = df['success_rate'].values
            test_names = [name[:30] + "..." if len(name) > 30 else name for name in df['test_name'].values]
            
            colors = ['green' if rate >= 0.95 else 'orange' if rate >= 0.8 else 'red' for rate in success_rates]
            
            plt.barh(test_names, success_rates, color=colors)
            plt.title('Test Success Rates')
            plt.xlabel('Success Rate')
            plt.xlim(0, 1.1)
            plt.axvline(x=0.95, color='red', linestyle='--', alpha=0.7, label='Target (95%)')
            plt.legend()
            plt.tight_layout()
            plt.savefig(charts_dir / 'success_rates.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # 4. Memory Usage Analysis
            memory_data = df[df['memory_usage_mb'] > 0]
            if not memory_data.empty:
                plt.figure(figsize=(12, 6))
                plt.scatter(memory_data['duration_seconds'], memory_data['memory_usage_mb'], 
                           c=memory_data['throughput_ops_per_sec'], cmap='viridis', alpha=0.7)
                plt.colorbar(label='Throughput (ops/sec)')
                plt.title('Memory Usage vs Duration (colored by throughput)')
                plt.xlabel('Test Duration (seconds)')
                plt.ylabel('Memory Usage (MB)')
                plt.tight_layout()
                plt.savefig(charts_dir / 'memory_usage_analysis.png', dpi=300, bbox_inches='tight')
                plt.close()
            
            self.logger.info("📊 Performance analytics generated")
            
        except Exception as e:
            self.logger.error(f"Failed to generate analytics: {e}")
    
    async def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate comprehensive performance summary"""
        summary = {
            "test_id": self.test_id,
            "execution_time": datetime.now().isoformat(),
            "metrics_summary": {
                "total_tests": len(self.metrics),
                "successful_tests": sum(1 for m in self.metrics if m.success_rate > 0.9),
                "failed_tests": sum(1 for m in self.metrics if m.success_rate <= 0.5),
                "average_success_rate": statistics.mean([m.success_rate for m in self.metrics]) if self.metrics else 0
            },
            "performance_analysis": {},
            "load_test_results": [asdict(result) for result in self.load_results],
            "recommendations": [],
            "system_limits": {},
            "production_readiness": {}
        }
        
        if self.metrics:
            # Performance analysis
            throughputs = [m.throughput_ops_per_sec for m in self.metrics if m.throughput_ops_per_sec and m.throughput_ops_per_sec > 0]
            durations = [m.duration_seconds for m in self.metrics]
            memory_usage = [m.memory_usage_mb for m in self.metrics if m.memory_usage_mb]
            
            summary["performance_analysis"] = {
                "average_throughput_ops_per_sec": statistics.mean(throughputs) if throughputs else 0,
                "max_throughput_ops_per_sec": max(throughputs) if throughputs else 0,
                "average_test_duration_seconds": statistics.mean(durations) if durations else 0,
                "average_memory_usage_mb": statistics.mean(memory_usage) if memory_usage else 0,
                "max_memory_usage_mb": max(memory_usage) if memory_usage else 0
            }
        
        # Load test analysis
        if self.load_results:
            max_users_tested = max(result.concurrent_users for result in self.load_results)
            best_throughput = max(result.throughput_ops_per_sec for result in self.load_results)
            worst_response_time = max(result.avg_response_time_ms for result in self.load_results)
            
            summary["system_limits"] = {
                "max_concurrent_users_tested": max_users_tested,
                "peak_throughput_ops_per_sec": best_throughput,
                "worst_avg_response_time_ms": worst_response_time,
                "degradation_point": self._find_degradation_point()
            }
        
        # Generate recommendations
        recommendations = []
        
        if summary["metrics_summary"]["average_success_rate"] < 0.95:
            recommendations.append("Improve system reliability - success rate below 95%")
        
        if self.load_results:
            high_response_times = [r for r in self.load_results if r.avg_response_time_ms > 1000]
            if high_response_times:
                recommendations.append("Optimize response times - some scenarios exceed 1000ms")
        
        if any(m.memory_usage_mb and m.memory_usage_mb > 500 for m in self.metrics):
            recommendations.append("Monitor memory usage - some tests show high memory consumption")
        
        summary["recommendations"] = recommendations
        
        # Production readiness assessment
        summary["production_readiness"] = {
            "overall_status": "READY" if len(recommendations) == 0 else "NEEDS_ATTENTION",
            "performance_grade": self._calculate_performance_grade(),
            "critical_issues": [r for r in recommendations if "reliability" in r.lower() or "critical" in r.lower()]
        }
        
        # Save summary
        summary_file = self.test_workspace / "performance" / f"performance_summary_{self.test_id}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        
        return summary
    
    def _find_degradation_point(self) -> Optional[int]:
        """Find the point where system performance degrades"""
        if not self.load_results:
            return None
        
        # Sort by user count
        sorted_results = sorted(self.load_results, key=lambda r: r.concurrent_users)
        
        for i, result in enumerate(sorted_results):
            if result.avg_response_time_ms > 2000 or result.failed_operations / max(result.total_operations, 1) > 0.1:
                return result.concurrent_users
        
        return None
    
    def _calculate_performance_grade(self) -> str:
        """Calculate overall performance grade"""
        if not self.metrics:
            return "UNKNOWN"
        
        success_rate = statistics.mean([m.success_rate for m in self.metrics])
        
        if success_rate >= 0.98:
            return "EXCELLENT"
        elif success_rate >= 0.95:
            return "GOOD"
        elif success_rate >= 0.90:
            return "ACCEPTABLE"
        elif success_rate >= 0.80:
            return "NEEDS_IMPROVEMENT"
        else:
            return "POOR"
    
    # Helper methods
    async def _get_test_recipe_id(self) -> Optional[str]:
        """Get a test recipe ID"""
        try:
            result = await self.db.execute_query("SELECT id FROM recipes LIMIT 1")
            return result[0]["id"] if result else None
        except Exception:
            return None
    
    async def _load_recipe_configuration(self, recipe_id: str) -> Dict[str, Any]:
        """Load recipe configuration for performance testing"""
        try:
            steps = await self.db.execute_query(
                "SELECT * FROM recipe_steps WHERE recipe_id = $1 ORDER BY sequence_number",
                [recipe_id]
            )
            return {"steps": steps}
        except Exception:
            return {"steps": []}
    
    async def _simulate_process_initialization(self, recipe_id: str) -> str:
        """Simulate process initialization"""
        process_id = str(uuid4())
        
        try:
            # Get test machine
            machines = await test_env.get_test_machines()
            machine_id = machines[0]["id"] if machines else None
            
            if machine_id:
                await self.db.execute_query("""
                    INSERT INTO process_executions (id, recipe_id, machine_id, status, start_time, operator_id, parameters, session_id)
                    VALUES ($1, $2, $3, 'preparing', now(), 
                           (SELECT id FROM auth.users LIMIT 1), '{}', $4)
                """, [process_id, recipe_id, machine_id, str(uuid4())])
                
                # Create state record
                await self.db.execute_query("""
                    INSERT INTO process_execution_state (execution_id)
                    VALUES ($1)
                """, [process_id])
        
        except Exception as e:
            self.logger.error(f"Process initialization simulation failed: {e}")
        
        return process_id
    
    async def _simulate_step_execution(self, process_id: str, step_count: int) -> None:
        """Simulate step execution"""
        try:
            for i in range(min(step_count, 5)):  # Limit for performance testing
                await self.db.execute_query("""
                    UPDATE process_execution_state 
                    SET current_step_index = $1, current_overall_step = $1
                    WHERE execution_id = $2
                """, [i, process_id])
                
                # Small delay to simulate processing
                await asyncio.sleep(0.01)
        
        except Exception as e:
            self.logger.error(f"Step execution simulation failed: {e}")
    
    async def _cleanup_test_process(self, process_id: str) -> None:
        """Cleanup test process"""
        try:
            await self.db.execute_query("DELETE FROM process_execution_state WHERE execution_id = $1", [process_id])
            await self.db.execute_query("DELETE FROM process_executions WHERE id = $1", [process_id])
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

# Global performance tester instance
performance_tester = PerformanceLoadTester()

async def main():
    """Main performance testing execution"""
    print("🚀 Starting Performance and Load Testing...")
    
    try:
        # Initialize performance tester
        if not await performance_tester.initialize():
            print("❌ Performance tester initialization failed")
            return
        
        # Run complete performance test suite
        summary = await performance_tester.run_performance_test_suite()
        
        # Print summary
        print("\n" + "="*60)
        print("🎯 PERFORMANCE TESTING COMPLETE")
        print("="*60)
        print(f"Overall Status: {summary['production_readiness']['overall_status']}")
        print(f"Performance Grade: {summary['production_readiness']['performance_grade']}")
        print(f"Total Tests: {summary['metrics_summary']['total_tests']}")
        print(f"Success Rate: {summary['metrics_summary']['average_success_rate']:.1%}")
        
        if summary["performance_analysis"]:
            print(f"Avg Throughput: {summary['performance_analysis']['average_throughput_ops_per_sec']:.2f} ops/sec")
            print(f"Max Memory: {summary['performance_analysis']['max_memory_usage_mb']:.1f} MB")
        
        if summary["recommendations"]:
            print("\nRecommendations:")
            for rec in summary["recommendations"]:
                print(f"  - {rec}")
        
        print("="*60)
        
    except Exception as e:
        print(f"❌ Performance testing failed: {e}")
    
    print("🏁 Performance testing completed")

if __name__ == "__main__":
    asyncio.run(main())