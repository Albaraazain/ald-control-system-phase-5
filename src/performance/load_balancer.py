"""
Load balancer for distributed parameter reading and horizontal scaling.

This module provides load balancing capabilities for high-performance parameter logging,
enabling horizontal scaling across multiple worker processes or instances.
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import statistics
from src.log_setup import logger


@dataclass
class WorkerMetrics:
    """Metrics for a worker instance."""
    worker_id: str
    active_requests: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    last_request_time: float = 0.0
    health_status: str = "healthy"  # healthy, degraded, failed
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0


@dataclass
class LoadBalancerMetrics:
    """Overall load balancer metrics."""
    total_workers: int = 0
    healthy_workers: int = 0
    total_requests: int = 0
    requests_per_second: float = 0.0
    avg_response_time_ms: float = 0.0
    load_distribution_variance: float = 0.0
    last_updated: float = field(default_factory=time.time)


class PerformanceLoadBalancer:
    """
    High-performance load balancer for distributed parameter reading.

    Features:
    - Multiple load balancing algorithms (round-robin, least-connections, weighted)
    - Health monitoring and automatic failover
    - Performance-based worker selection
    - Circuit breaker pattern for failed workers
    - Real-time metrics and monitoring
    """

    def __init__(self, algorithm: str = "weighted_performance"):
        """
        Initialize the load balancer.

        Args:
            algorithm: Load balancing algorithm
                      ("round_robin", "least_connections", "weighted_performance")
        """
        self.algorithm = algorithm
        self.workers: Dict[str, WorkerMetrics] = {}
        self.worker_queue: List[str] = []
        self.current_worker_index = 0

        # Performance tracking
        self.metrics = LoadBalancerMetrics()
        self.request_times: List[float] = []
        self.max_request_history = 1000

        # Health monitoring
        self.health_check_interval = 30.0  # seconds
        self.circuit_breaker_threshold = 5  # consecutive failures
        self.circuit_breaker_timeout = 60.0  # seconds
        self.failed_workers: Dict[str, float] = {}  # worker_id -> failure_time

        # Performance tuning
        self.performance_weights: Dict[str, float] = {}
        self.load_balancing_lock = asyncio.Lock()

    async def register_worker(self, worker_id: str, initial_weight: float = 1.0) -> bool:
        """
        Register a new worker instance.

        Args:
            worker_id: Unique identifier for the worker
            initial_weight: Initial performance weight (higher = more capable)

        Returns:
            bool: True if registration successful
        """
        async with self.load_balancing_lock:
            if worker_id in self.workers:
                logger.warning(f"Worker {worker_id} already registered, updating")

            self.workers[worker_id] = WorkerMetrics(worker_id=worker_id)
            self.performance_weights[worker_id] = initial_weight

            # Update worker queue for round-robin
            if worker_id not in self.worker_queue:
                self.worker_queue.append(worker_id)

            # Remove from failed workers if recovering
            if worker_id in self.failed_workers:
                del self.failed_workers[worker_id]
                logger.info(f"Worker {worker_id} recovered and re-registered")

            self._update_metrics()
            logger.info(f"Registered worker {worker_id} with weight {initial_weight}")
            return True

    async def unregister_worker(self, worker_id: str) -> bool:
        """
        Unregister a worker instance.

        Args:
            worker_id: Worker to unregister

        Returns:
            bool: True if unregistration successful
        """
        async with self.load_balancing_lock:
            if worker_id not in self.workers:
                logger.warning(f"Worker {worker_id} not found for unregistration")
                return False

            del self.workers[worker_id]
            if worker_id in self.performance_weights:
                del self.performance_weights[worker_id]
            if worker_id in self.worker_queue:
                self.worker_queue.remove(worker_id)
            if worker_id in self.failed_workers:
                del self.failed_workers[worker_id]

            self._update_metrics()
            logger.info(f"Unregistered worker {worker_id}")
            return True

    async def select_worker(self, request_context: Optional[Dict] = None) -> Optional[str]:
        """
        Select the best worker for a request based on the configured algorithm.

        Args:
            request_context: Optional context for request-specific routing

        Returns:
            str: Selected worker ID, or None if no workers available
        """
        async with self.load_balancing_lock:
            healthy_workers = self._get_healthy_workers()

            if not healthy_workers:
                logger.error("No healthy workers available for load balancing")
                return None

            if self.algorithm == "round_robin":
                return self._select_round_robin(healthy_workers)
            elif self.algorithm == "least_connections":
                return self._select_least_connections(healthy_workers)
            elif self.algorithm == "weighted_performance":
                return self._select_weighted_performance(healthy_workers)
            else:
                logger.warning(f"Unknown algorithm {self.algorithm}, using round_robin")
                return self._select_round_robin(healthy_workers)

    def _get_healthy_workers(self) -> List[str]:
        """Get list of healthy workers, excluding circuit breaker failures."""
        current_time = time.time()
        healthy_workers = []

        for worker_id in self.workers:
            # Check circuit breaker status
            if worker_id in self.failed_workers:
                failure_time = self.failed_workers[worker_id]
                if current_time - failure_time < self.circuit_breaker_timeout:
                    continue  # Still in circuit breaker timeout
                else:
                    # Timeout expired, try to recover
                    del self.failed_workers[worker_id]
                    self.workers[worker_id].health_status = "healthy"
                    logger.info(f"Worker {worker_id} circuit breaker timeout expired, attempting recovery")

            # Check worker health status
            worker = self.workers[worker_id]
            if worker.health_status in ["healthy", "degraded"]:
                healthy_workers.append(worker_id)

        return healthy_workers

    def _select_round_robin(self, healthy_workers: List[str]) -> str:
        """Round-robin selection algorithm."""
        if not healthy_workers:
            return None

        # Filter worker queue to only include healthy workers
        healthy_queue = [w for w in self.worker_queue if w in healthy_workers]

        if not healthy_queue:
            return healthy_workers[0]  # Fallback to first healthy worker

        # Select next worker in round-robin fashion
        selected = healthy_queue[self.current_worker_index % len(healthy_queue)]
        self.current_worker_index = (self.current_worker_index + 1) % len(healthy_queue)

        return selected

    def _select_least_connections(self, healthy_workers: List[str]) -> str:
        """Least connections selection algorithm."""
        if not healthy_workers:
            return None

        # Find worker with least active requests
        min_connections = float('inf')
        selected_worker = None

        for worker_id in healthy_workers:
            worker = self.workers[worker_id]
            if worker.active_requests < min_connections:
                min_connections = worker.active_requests
                selected_worker = worker_id

        return selected_worker or healthy_workers[0]

    def _select_weighted_performance(self, healthy_workers: List[str]) -> str:
        """Weighted performance selection algorithm."""
        if not healthy_workers:
            return None

        # Calculate performance scores
        worker_scores = {}

        for worker_id in healthy_workers:
            worker = self.workers[worker_id]
            base_weight = self.performance_weights.get(worker_id, 1.0)

            # Performance factors
            response_time_factor = 1.0 / (1.0 + worker.avg_response_time_ms / 100.0)  # Prefer faster workers
            load_factor = 1.0 / (1.0 + worker.active_requests)  # Prefer less loaded workers
            reliability_factor = (worker.total_requests - worker.failed_requests) / max(worker.total_requests, 1)

            # Health degradation penalty
            health_factor = 1.0 if worker.health_status == "healthy" else 0.5

            # Combined score
            score = base_weight * response_time_factor * load_factor * reliability_factor * health_factor
            worker_scores[worker_id] = score

        # Select worker with highest score
        best_worker = max(worker_scores.keys(), key=lambda w: worker_scores[w])
        return best_worker

    async def record_request_start(self, worker_id: str) -> bool:
        """
        Record the start of a request to a worker.

        Args:
            worker_id: Worker handling the request

        Returns:
            bool: True if recorded successfully
        """
        if worker_id not in self.workers:
            logger.error(f"Unknown worker {worker_id} for request start recording")
            return False

        worker = self.workers[worker_id]
        worker.active_requests += 1
        worker.total_requests += 1
        worker.last_request_time = time.time()

        self.metrics.total_requests += 1
        return True

    async def record_request_end(self, worker_id: str, success: bool, response_time_ms: float) -> bool:
        """
        Record the completion of a request.

        Args:
            worker_id: Worker that handled the request
            success: Whether the request was successful
            response_time_ms: Response time in milliseconds

        Returns:
            bool: True if recorded successfully
        """
        if worker_id not in self.workers:
            logger.error(f"Unknown worker {worker_id} for request end recording")
            return False

        worker = self.workers[worker_id]
        worker.active_requests = max(0, worker.active_requests - 1)

        if not success:
            worker.failed_requests += 1
            await self._handle_worker_failure(worker_id)

        # Update response time (exponential moving average)
        if worker.avg_response_time_ms == 0:
            worker.avg_response_time_ms = response_time_ms
        else:
            alpha = 0.1  # Smoothing factor
            worker.avg_response_time_ms = (
                alpha * response_time_ms + (1 - alpha) * worker.avg_response_time_ms
            )

        # Update global metrics
        self.request_times.append(response_time_ms)
        if len(self.request_times) > self.max_request_history:
            self.request_times = self.request_times[-self.max_request_history:]

        self._update_metrics()
        return True

    async def _handle_worker_failure(self, worker_id: str):
        """Handle worker failure and circuit breaker logic."""
        worker = self.workers[worker_id]

        # Calculate recent failure rate
        recent_requests = worker.total_requests
        recent_failures = worker.failed_requests

        if recent_requests > 0:
            failure_rate = recent_failures / recent_requests

            # Check if we should trigger circuit breaker
            if (recent_failures >= self.circuit_breaker_threshold and failure_rate > 0.5):
                self.failed_workers[worker_id] = time.time()
                worker.health_status = "failed"
                logger.warning(
                    f"Worker {worker_id} circuit breaker activated: "
                    f"{recent_failures} failures in {recent_requests} requests"
                )

    def _update_metrics(self):
        """Update overall load balancer metrics."""
        current_time = time.time()

        # Count healthy workers
        healthy_workers = self._get_healthy_workers()
        self.metrics.total_workers = len(self.workers)
        self.metrics.healthy_workers = len(healthy_workers)

        # Calculate requests per second
        time_window = 60.0  # 1 minute window
        recent_requests = [
            t for t in self.request_times
            if current_time - t < time_window
        ]
        self.metrics.requests_per_second = len(recent_requests) / time_window

        # Calculate average response time
        if self.request_times:
            self.metrics.avg_response_time_ms = statistics.mean(self.request_times[-100:])

        # Calculate load distribution variance
        if healthy_workers:
            loads = [self.workers[w].active_requests for w in healthy_workers]
            if len(loads) > 1:
                self.metrics.load_distribution_variance = statistics.variance(loads)

        self.metrics.last_updated = current_time

    async def get_worker_health(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed health information for a specific worker.

        Args:
            worker_id: Worker to check

        Returns:
            Dict with worker health information, or None if worker not found
        """
        if worker_id not in self.workers:
            return None

        worker = self.workers[worker_id]

        return {
            'worker_id': worker.worker_id,
            'health_status': worker.health_status,
            'active_requests': worker.active_requests,
            'total_requests': worker.total_requests,
            'failed_requests': worker.failed_requests,
            'success_rate': (worker.total_requests - worker.failed_requests) / max(worker.total_requests, 1),
            'avg_response_time_ms': worker.avg_response_time_ms,
            'last_request_time': worker.last_request_time,
            'performance_weight': self.performance_weights.get(worker_id, 1.0),
            'is_circuit_breaker_active': worker_id in self.failed_workers
        }

    def get_load_balancer_status(self) -> Dict[str, Any]:
        """Get comprehensive load balancer status."""
        return {
            'algorithm': self.algorithm,
            'metrics': {
                'total_workers': self.metrics.total_workers,
                'healthy_workers': self.metrics.healthy_workers,
                'total_requests': self.metrics.total_requests,
                'requests_per_second': self.metrics.requests_per_second,
                'avg_response_time_ms': self.metrics.avg_response_time_ms,
                'load_distribution_variance': self.metrics.load_distribution_variance
            },
            'workers': {
                worker_id: {
                    'health_status': worker.health_status,
                    'active_requests': worker.active_requests,
                    'performance_weight': self.performance_weights.get(worker_id, 1.0)
                }
                for worker_id, worker in self.workers.items()
            },
            'circuit_breakers': {
                worker_id: time.time() - failure_time
                for worker_id, failure_time in self.failed_workers.items()
            }
        }


# Global load balancer instance
performance_load_balancer = PerformanceLoadBalancer()