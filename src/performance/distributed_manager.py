"""
Distributed manager for horizontal scaling of parameter logging operations.

This module provides distributed coordination capabilities for scaling parameter logging
across multiple worker instances, processes, or even different machines.
"""
import asyncio
import time
import uuid
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
from src.log_setup import logger
from src.performance.load_balancer import performance_load_balancer


@dataclass
class WorkerInstance:
    """Represents a worker instance in the distributed system."""
    worker_id: str
    instance_type: str  # "local_process", "remote_instance", "container"
    capabilities: Set[str] = field(default_factory=set)  # "bulk_read", "real_plc", "simulation"
    max_concurrent_requests: int = 10
    assigned_parameters: Set[str] = field(default_factory=set)
    last_heartbeat: float = field(default_factory=time.time)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class DistributedTask:
    """Represents a distributed parameter reading task."""
    task_id: str
    parameter_ids: List[str]
    priority: int = 1  # 1=high, 2=normal, 3=low
    assigned_worker: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, float]] = None
    error: Optional[str] = None


class DistributedParameterManager:
    """
    Distributed manager for horizontal scaling of parameter logging operations.

    Features:
    - Worker discovery and registration
    - Dynamic load distribution based on capabilities
    - Fault tolerance with automatic failover
    - Parameter partitioning and assignment
    - Performance monitoring and optimization
    - Health checks and worker lifecycle management
    """

    def __init__(self):
        self.workers: Dict[str, WorkerInstance] = {}
        self.active_tasks: Dict[str, DistributedTask] = {}
        self.parameter_assignments: Dict[str, str] = {}  # parameter_id -> worker_id

        # Coordination settings
        self.heartbeat_interval = 10.0  # seconds - FIXED: Must be <25s for Supabase realtime
        self.heartbeat_timeout = 20.0  # seconds - FIXED: Must be <25s for Supabase realtime
        self.task_timeout = 30.0  # seconds
        self.max_retry_attempts = 3

        # Performance optimization
        self.parameter_locality_cache: Dict[str, Set[str]] = defaultdict(set)  # worker -> parameters
        self.load_balancing_enabled = True
        self.auto_scaling_enabled = True

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        """Start the distributed manager."""
        if self._is_running:
            logger.warning("Distributed manager is already running")
            return

        self._is_running = True

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Distributed parameter manager started")

    async def stop(self):
        """Stop the distributed manager."""
        if not self._is_running:
            return

        self._is_running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Distributed parameter manager stopped")

    async def register_worker(
        self,
        instance_type: str,
        capabilities: Set[str],
        max_concurrent: int = 10,
        worker_id: Optional[str] = None
    ) -> str:
        """
        Register a new worker instance.

        Args:
            instance_type: Type of worker instance
            capabilities: Set of capabilities this worker supports
            max_concurrent: Maximum concurrent requests this worker can handle
            worker_id: Optional specific worker ID

        Returns:
            str: Assigned worker ID
        """
        if not worker_id:
            worker_id = f"worker-{instance_type}-{uuid.uuid4().hex[:8]}"

        worker = WorkerInstance(
            worker_id=worker_id,
            instance_type=instance_type,
            capabilities=capabilities,
            max_concurrent_requests=max_concurrent
        )

        self.workers[worker_id] = worker

        # Register with load balancer
        await performance_load_balancer.register_worker(worker_id, initial_weight=1.0)

        logger.info(
            f"Registered worker {worker_id} (type: {instance_type}, "
            f"capabilities: {capabilities}, max_concurrent: {max_concurrent})"
        )

        return worker_id

    async def unregister_worker(self, worker_id: str) -> bool:
        """
        Unregister a worker instance.

        Args:
            worker_id: Worker to unregister

        Returns:
            bool: True if successful
        """
        if worker_id not in self.workers:
            logger.warning(f"Worker {worker_id} not found for unregistration")
            return False

        # Reassign parameters to other workers
        await self._reassign_worker_parameters(worker_id)

        # Unregister from load balancer
        await performance_load_balancer.unregister_worker(worker_id)

        # Remove worker
        del self.workers[worker_id]

        logger.info(f"Unregistered worker {worker_id}")
        return True

    async def distribute_parameter_reading(
        self,
        parameter_ids: List[str],
        priority: int = 1
    ) -> Dict[str, float]:
        """
        Distribute parameter reading across available workers.

        Args:
            parameter_ids: List of parameter IDs to read
            priority: Task priority (1=high, 2=normal, 3=low)

        Returns:
            Dict mapping parameter_id to value
        """
        if not parameter_ids:
            return {}

        # Create distributed tasks
        task_groups = await self._create_task_groups(parameter_ids, priority)

        if not task_groups:
            logger.error("Failed to create task groups for parameter reading")
            return {}

        # Execute tasks concurrently
        task_futures = []
        for task in task_groups:
            future = asyncio.create_task(self._execute_distributed_task(task))
            task_futures.append(future)

        # Wait for all tasks to complete
        results = await asyncio.gather(*task_futures, return_exceptions=True)

        # Combine results
        all_parameter_values = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in distributed task: {result}")
                continue

            if isinstance(result, dict):
                all_parameter_values.update(result)

        logger.debug(
            f"Distributed parameter reading completed: "
            f"{len(all_parameter_values)}/{len(parameter_ids)} parameters successful"
        )

        return all_parameter_values

    async def _create_task_groups(
        self,
        parameter_ids: List[str],
        priority: int
    ) -> List[DistributedTask]:
        """
        Create optimized task groups for parameter reading.

        Args:
            parameter_ids: Parameters to read
            priority: Task priority

        Returns:
            List of distributed tasks
        """
        # Group parameters by optimal worker assignment
        worker_assignments = await self._optimize_parameter_assignment(parameter_ids)

        tasks = []
        for worker_id, params in worker_assignments.items():
            if params:
                task = DistributedTask(
                    task_id=f"task-{uuid.uuid4().hex[:8]}",
                    parameter_ids=list(params),
                    priority=priority,
                    assigned_worker=worker_id
                )
                tasks.append(task)
                self.active_tasks[task.task_id] = task

        return tasks

    async def _optimize_parameter_assignment(
        self,
        parameter_ids: List[str]
    ) -> Dict[str, Set[str]]:
        """
        Optimize parameter assignment to workers based on capabilities and load.

        Args:
            parameter_ids: Parameters to assign

        Returns:
            Dict mapping worker_id to assigned parameters
        """
        assignments: Dict[str, Set[str]] = defaultdict(set)

        # Get available workers with bulk read capability
        bulk_read_workers = [
            worker_id for worker_id, worker in self.workers.items()
            if "bulk_read" in worker.capabilities and self._is_worker_healthy(worker_id)
        ]

        if not bulk_read_workers:
            logger.warning("No workers with bulk_read capability available")
            return assignments

        # Simple round-robin assignment for now
        # TODO: Implement more sophisticated assignment based on:
        # - Parameter locality (parameters from same PLC address ranges)
        # - Worker current load
        # - Historical performance
        # - Network proximity for remote workers

        for i, param_id in enumerate(parameter_ids):
            worker_id = bulk_read_workers[i % len(bulk_read_workers)]
            assignments[worker_id].add(param_id)

        return assignments

    async def _execute_distributed_task(self, task: DistributedTask) -> Dict[str, float]:
        """
        Execute a distributed task on the assigned worker.

        Args:
            task: Task to execute

        Returns:
            Dict mapping parameter_id to value
        """
        if not task.assigned_worker:
            logger.error(f"Task {task.task_id} has no assigned worker")
            return {}

        worker_id = task.assigned_worker
        task.started_at = time.time()

        try:
            # Record request start for load balancing
            await performance_load_balancer.record_request_start(worker_id)

            # Execute the actual parameter reading
            # For now, use the local high-performance logger
            # TODO: Implement remote worker communication for distributed instances
            result = await self._execute_local_bulk_read(task.parameter_ids)

            # Record successful completion
            response_time_ms = (time.time() - task.started_at) * 1000
            await performance_load_balancer.record_request_end(
                worker_id, success=True, response_time_ms=response_time_ms
            )

            task.completed_at = time.time()
            task.result = result

            return result

        except Exception as e:
            # Record failure
            response_time_ms = (time.time() - task.started_at) * 1000
            await performance_load_balancer.record_request_end(
                worker_id, success=False, response_time_ms=response_time_ms
            )

            task.error = str(e)
            logger.error(f"Task {task.task_id} failed on worker {worker_id}: {e}")

            # Attempt retry on different worker
            return await self._retry_task(task)

    async def _execute_local_bulk_read(self, parameter_ids: List[str]) -> Dict[str, float]:
        """
        Execute bulk parameter reading using local high-performance logger.

        Args:
            parameter_ids: Parameters to read

        Returns:
            Dict mapping parameter_id to value
        """
        # Import here to avoid circular dependencies
        from src.data_collection.high_performance_logger import high_performance_parameter_logger

        # Use the existing bulk read implementation
        # This will be replaced with proper worker communication in distributed setups
        if hasattr(high_performance_parameter_logger, '_bulk_read_parameters'):
            # Filter to only requested parameters
            all_values = await high_performance_parameter_logger._bulk_read_parameters()
            return {
                param_id: value for param_id, value in all_values.items()
                if param_id in parameter_ids
            }
        else:
            logger.error("High-performance logger not available for bulk reading")
            return {}

    async def _retry_task(self, task: DistributedTask) -> Dict[str, float]:
        """
        Retry a failed task on a different worker.

        Args:
            task: Failed task to retry

        Returns:
            Dict mapping parameter_id to value
        """
        # Simple retry logic - could be enhanced with exponential backoff
        logger.info(f"Retrying task {task.task_id}")

        # Select a different worker
        new_worker = await performance_load_balancer.select_worker()
        if new_worker and new_worker != task.assigned_worker:
            task.assigned_worker = new_worker
            return await self._execute_distributed_task(task)

        logger.error(f"No alternative worker available for task {task.task_id}")
        return {}

    def _is_worker_healthy(self, worker_id: str) -> bool:
        """
        Check if a worker is healthy and responsive.

        Args:
            worker_id: Worker to check

        Returns:
            bool: True if worker is healthy
        """
        if worker_id not in self.workers:
            return False

        worker = self.workers[worker_id]
        current_time = time.time()

        # Check heartbeat timeout
        if current_time - worker.last_heartbeat > self.heartbeat_timeout:
            logger.warning(f"Worker {worker_id} heartbeat timeout")
            return False

        return True

    async def _reassign_worker_parameters(self, worker_id: str):
        """
        Reassign parameters from a failed worker to other workers.

        Args:
            worker_id: Worker that failed
        """
        if worker_id not in self.workers:
            return

        worker = self.workers[worker_id]
        parameters_to_reassign = worker.assigned_parameters.copy()

        if not parameters_to_reassign:
            return

        logger.info(f"Reassigning {len(parameters_to_reassign)} parameters from worker {worker_id}")

        # Find alternative workers
        alternative_workers = [
            w_id for w_id, w in self.workers.items()
            if w_id != worker_id and self._is_worker_healthy(w_id)
        ]

        if not alternative_workers:
            logger.error("No alternative workers available for parameter reassignment")
            return

        # Distribute parameters among alternative workers
        for i, param_id in enumerate(parameters_to_reassign):
            new_worker_id = alternative_workers[i % len(alternative_workers)]
            self.workers[new_worker_id].assigned_parameters.add(param_id)
            self.parameter_assignments[param_id] = new_worker_id

        # Clear assignments from failed worker
        worker.assigned_parameters.clear()

    async def _heartbeat_loop(self):
        """Background task for worker heartbeat monitoring."""
        while self._is_running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._check_worker_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self):
        """Background task for cleaning up completed tasks."""
        while self._is_running:
            try:
                await asyncio.sleep(60.0)  # Cleanup every minute
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _check_worker_heartbeats(self):
        """Check worker heartbeats and handle timeouts."""
        current_time = time.time()
        failed_workers = []

        for worker_id, worker in self.workers.items():
            if current_time - worker.last_heartbeat > self.heartbeat_timeout:
                failed_workers.append(worker_id)

        for worker_id in failed_workers:
            logger.warning(f"Worker {worker_id} heartbeat timeout, marking as failed")
            await self._reassign_worker_parameters(worker_id)

    async def _cleanup_completed_tasks(self):
        """Clean up old completed tasks."""
        current_time = time.time()
        cleanup_age = 300.0  # 5 minutes

        completed_tasks = [
            task_id for task_id, task in self.active_tasks.items()
            if (task.completed_at and current_time - task.completed_at > cleanup_age) or
               (task.error and current_time - task.created_at > cleanup_age)
        ]

        for task_id in completed_tasks:
            del self.active_tasks[task_id]

        if completed_tasks:
            logger.debug(f"Cleaned up {len(completed_tasks)} completed tasks")

    def get_distributed_status(self) -> Dict[str, Any]:
        """Get comprehensive distributed manager status."""
        return {
            'is_running': self._is_running,
            'total_workers': len(self.workers),
            'healthy_workers': len([w for w in self.workers if self._is_worker_healthy(w)]),
            'active_tasks': len(self.active_tasks),
            'parameter_assignments': len(self.parameter_assignments),
            'workers': {
                worker_id: {
                    'instance_type': worker.instance_type,
                    'capabilities': list(worker.capabilities),
                    'assigned_parameters': len(worker.assigned_parameters),
                    'last_heartbeat_age': time.time() - worker.last_heartbeat,
                    'is_healthy': self._is_worker_healthy(worker_id)
                }
                for worker_id, worker in self.workers.items()
            },
            'load_balancer_status': performance_load_balancer.get_load_balancer_status()
        }


# Global distributed manager instance
distributed_parameter_manager = DistributedParameterManager()