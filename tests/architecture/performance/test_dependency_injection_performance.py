#!/usr/bin/env python3
"""
Dependency Injection Performance Impact Testing Framework

Tests for dependency injection overhead, service startup/shutdown performance,
memory usage, and concurrent service operation testing.
"""

import pytest
import asyncio
import time
import gc
import sys
import psutil
import threading
from typing import Dict, List, Any, Optional, Protocol
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from memory_profiler import profile as memory_profile


@dataclass
class PerformanceMetrics:
    """Performance measurement results"""
    operation: str
    execution_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    iterations: int
    operations_per_second: float


class PerformanceProfiler:
    """Performance profiling utility"""

    def __init__(self):
        self.process = psutil.Process()
        self.baseline_memory = None
        self.baseline_cpu = None

    def start_profiling(self):
        """Start performance profiling"""
        self.baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.baseline_cpu = self.process.cpu_percent()

    def stop_profiling(self) -> Dict[str, float]:
        """Stop profiling and return metrics"""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        current_cpu = self.process.cpu_percent()

        return {
            "memory_mb": current_memory,
            "memory_delta_mb": current_memory - (self.baseline_memory or 0),
            "cpu_percent": current_cpu,
            "cpu_delta_percent": current_cpu - (self.baseline_cpu or 0)
        }


# Service Interfaces for Performance Testing
class IHighPerformanceService(Protocol):
    """High-performance service interface"""

    async def initialize(self) -> bool:
        ...

    async def process_batch(self, data: List[Any]) -> bool:
        ...

    async def shutdown(self) -> bool:
        ...


class ILightweightService(Protocol):
    """Lightweight service interface"""

    def quick_operation(self) -> Any:
        ...

    async def async_operation(self) -> Any:
        ...


# Test Service Implementations
class HighPerformanceService:
    """High-performance service implementation for testing"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.initialized = False
        self.batch_count = 0

    async def initialize(self) -> bool:
        """Initialize service with simulated startup cost"""
        await asyncio.sleep(0.01)  # Simulate initialization time
        self.initialized = True
        return True

    async def process_batch(self, data: List[Any]) -> bool:
        """Process a batch of data"""
        if not self.initialized:
            raise RuntimeError("Service not initialized")

        # Simulate CPU-intensive processing
        await asyncio.sleep(0.001 * len(data))
        self.batch_count += 1
        return True

    async def shutdown(self) -> bool:
        """Shutdown service"""
        await asyncio.sleep(0.005)  # Simulate cleanup time
        self.initialized = False
        return True


class LightweightService:
    """Lightweight service for overhead testing"""

    def __init__(self, dependency: Optional[Any] = None):
        self.dependency = dependency
        self.operation_count = 0

    def quick_operation(self) -> Any:
        """Quick synchronous operation"""
        self.operation_count += 1
        return self.operation_count

    async def async_operation(self) -> Any:
        """Quick asynchronous operation"""
        await asyncio.sleep(0.001)
        self.operation_count += 1
        return self.operation_count


# DI Container for Performance Testing
class PerformanceDIContainer:
    """Performance-optimized DI container"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}
        self._creation_times: Dict[str, float] = {}

    def register_singleton(self, interface: type, implementation: type, config: Dict = None):
        """Register singleton service"""
        self._services[interface.__name__] = (implementation, config or {})

    def register_factory(self, interface: type, factory: callable):
        """Register factory function"""
        self._factories[interface.__name__] = factory

    def resolve(self, interface: type) -> Any:
        """Resolve service with performance tracking"""
        service_name = interface.__name__
        start_time = time.time()

        try:
            # Check singleton cache first
            if service_name in self._singletons:
                return self._singletons[service_name]

            # Create from factory
            if service_name in self._factories:
                instance = self._factories[service_name]()
                self._singletons[service_name] = instance
                return instance

            # Create from registered service
            if service_name in self._services:
                implementation, config = self._services[service_name]
                instance = implementation(config)
                self._singletons[service_name] = instance
                return instance

            raise ValueError(f"Service {service_name} not registered")

        finally:
            self._creation_times[service_name] = time.time() - start_time

    def get_creation_time(self, interface: type) -> float:
        """Get service creation time"""
        return self._creation_times.get(interface.__name__, 0.0)

    def clear(self):
        """Clear container state"""
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()
        self._creation_times.clear()


# Test Fixtures
@pytest.fixture
def performance_container():
    """Performance DI container fixture"""
    return PerformanceDIContainer()


@pytest.fixture
def profiler():
    """Performance profiler fixture"""
    return PerformanceProfiler()


@pytest.fixture
def configured_performance_container(performance_container):
    """Pre-configured performance container"""
    performance_container.register_singleton(
        IHighPerformanceService,
        HighPerformanceService,
        {"batch_size": 100}
    )
    performance_container.register_factory(
        ILightweightService,
        lambda: LightweightService()
    )
    return performance_container


# DI Overhead Tests
class TestDependencyInjectionOverhead:
    """Test dependency injection performance overhead"""

    def test_service_resolution_overhead(self, configured_performance_container, profiler):
        """Test overhead of service resolution"""
        profiler.start_profiling()

        # Measure service resolution time
        iterations = 1000
        start_time = time.time()

        for _ in range(iterations):
            service = configured_performance_container.resolve(ILightweightService)
            assert service is not None

        end_time = time.time()
        metrics = profiler.stop_profiling()

        total_time = end_time - start_time
        ops_per_second = iterations / total_time

        print(f"Service resolution: {ops_per_second:.0f} ops/sec")
        print(f"Average resolution time: {(total_time / iterations) * 1000:.3f}ms")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        # Should resolve services quickly
        assert ops_per_second > 5000  # At least 5000 resolutions per second
        assert total_time < 1.0  # Should complete in under 1 second

    def test_singleton_caching_performance(self, configured_performance_container):
        """Test singleton caching performance"""
        # First resolution (creates instance)
        start_time = time.time()
        service1 = configured_performance_container.resolve(IHighPerformanceService)
        first_resolution_time = time.time() - start_time

        # Subsequent resolutions (from cache)
        resolution_times = []
        for _ in range(100):
            start_time = time.time()
            service2 = configured_performance_container.resolve(IHighPerformanceService)
            resolution_times.append(time.time() - start_time)

        avg_cached_time = sum(resolution_times) / len(resolution_times)

        print(f"First resolution: {first_resolution_time * 1000:.3f}ms")
        print(f"Average cached resolution: {avg_cached_time * 1000:.3f}ms")

        # Cached resolutions should be much faster
        assert avg_cached_time < first_resolution_time / 10
        assert service1 is service2  # Should be same instance

    def test_factory_vs_singleton_performance(self, performance_container):
        """Compare factory vs singleton performance"""
        # Register same service as both factory and singleton
        performance_container.register_factory(
            ILightweightService,
            lambda: LightweightService()
        )

        class ISingletonService(Protocol):
            def quick_operation(self) -> Any: ...

        performance_container.register_singleton(
            ISingletonService,
            LightweightService
        )

        # Test factory performance
        factory_times = []
        for _ in range(100):
            start_time = time.time()
            service = performance_container.resolve(ILightweightService)
            factory_times.append(time.time() - start_time)

        # Test singleton performance
        singleton_times = []
        for _ in range(100):
            start_time = time.time()
            service = performance_container.resolve(ISingletonService)
            singleton_times.append(time.time() - start_time)

        avg_factory_time = sum(factory_times) / len(factory_times)
        avg_singleton_time = sum(singleton_times) / len(singleton_times)

        print(f"Average factory time: {avg_factory_time * 1000:.3f}ms")
        print(f"Average singleton time: {avg_singleton_time * 1000:.3f}ms")

        # Singletons should be faster after first creation
        # (Note: first singleton creation will be slower, but subsequent ones fast)

    @pytest.mark.asyncio
    async def test_async_service_overhead(self, configured_performance_container, profiler):
        """Test overhead of async service operations"""
        service = configured_performance_container.resolve(ILightweightService)

        profiler.start_profiling()

        # Test async operation overhead
        iterations = 500
        start_time = time.time()

        tasks = []
        for _ in range(iterations):
            tasks.append(service.async_operation())

        results = await asyncio.gather(*tasks)

        end_time = time.time()
        metrics = profiler.stop_profiling()

        total_time = end_time - start_time
        ops_per_second = iterations / total_time

        print(f"Async operations: {ops_per_second:.0f} ops/sec")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert len(results) == iterations
        assert ops_per_second > 100  # Should handle at least 100 async ops/sec


# Service Startup Performance Tests
class TestServiceStartupPerformance:
    """Test service startup and shutdown performance"""

    @pytest.mark.asyncio
    async def test_single_service_startup(self, configured_performance_container, profiler):
        """Test startup time for single service"""
        profiler.start_profiling()

        service = configured_performance_container.resolve(IHighPerformanceService)

        start_time = time.time()
        result = await service.initialize()
        initialization_time = time.time() - start_time

        metrics = profiler.stop_profiling()

        print(f"Service initialization: {initialization_time * 1000:.3f}ms")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert result is True
        assert initialization_time < 0.1  # Should initialize in under 100ms

    @pytest.mark.asyncio
    async def test_multiple_service_startup(self, performance_container, profiler):
        """Test startup time for multiple services"""
        # Register multiple services
        for i in range(10):
            class ITestService(Protocol):
                async def initialize(self) -> bool: ...

            # Create unique interface for each service
            interface_name = f"ITestService{i}"
            interface = type(interface_name, (Protocol,), {
                "initialize": lambda self: None
            })

            performance_container.register_singleton(
                interface,
                HighPerformanceService
            )

        profiler.start_profiling()

        # Initialize all services
        start_time = time.time()

        services = []
        for i in range(10):
            interface_name = f"ITestService{i}"
            # Would need proper interface resolution in real implementation
            service = HighPerformanceService()
            await service.initialize()
            services.append(service)

        total_startup_time = time.time() - start_time
        metrics = profiler.stop_profiling()

        print(f"Total startup time for 10 services: {total_startup_time * 1000:.3f}ms")
        print(f"Average per service: {(total_startup_time / 10) * 1000:.3f}ms")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert total_startup_time < 1.0  # Should start all services in under 1 second
        assert len(services) == 10

    @pytest.mark.asyncio
    async def test_concurrent_service_startup(self, profiler):
        """Test concurrent service startup performance"""
        profiler.start_profiling()

        # Create multiple services concurrently
        services = []
        start_time = time.time()

        tasks = []
        for i in range(20):
            service = HighPerformanceService()
            services.append(service)
            tasks.append(service.initialize())

        results = await asyncio.gather(*tasks)

        concurrent_startup_time = time.time() - start_time
        metrics = profiler.stop_profiling()

        print(f"Concurrent startup time for 20 services: {concurrent_startup_time * 1000:.3f}ms")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert all(results)  # All should initialize successfully
        assert concurrent_startup_time < 0.5  # Should be faster than sequential


# Memory Usage Tests
class TestMemoryUsageImpact:
    """Test memory usage impact of DI container"""

    def test_container_memory_overhead(self, profiler):
        """Test memory overhead of DI container itself"""
        profiler.start_profiling()

        # Create container and register services
        container = PerformanceDIContainer()

        for i in range(100):
            interface = type(f"IService{i}", (Protocol,), {})
            container.register_singleton(interface, LightweightService)

        metrics = profiler.stop_profiling()

        print(f"Container with 100 registrations: {metrics['memory_delta_mb']:.2f}MB")

        # Container overhead should be minimal
        assert metrics['memory_delta_mb'] < 10  # Less than 10MB overhead

    def test_service_instance_memory(self, configured_performance_container, profiler):
        """Test memory usage of service instances"""
        profiler.start_profiling()

        # Create many service instances
        services = []
        for _ in range(50):
            service = configured_performance_container.resolve(ILightweightService)
            services.append(service)

        metrics = profiler.stop_profiling()

        print(f"50 service instances: {metrics['memory_delta_mb']:.2f}MB")
        print(f"Average per instance: {metrics['memory_delta_mb'] / 50:.3f}MB")

        # Memory usage should be reasonable
        assert metrics['memory_delta_mb'] < 50  # Less than 50MB for 50 services

    def test_memory_cleanup_on_container_clear(self, configured_performance_container, profiler):
        """Test memory cleanup when container is cleared"""
        # Create services
        services = []
        for _ in range(20):
            service = configured_performance_container.resolve(IHighPerformanceService)
            services.append(service)

        profiler.start_profiling()

        # Clear container and references
        configured_performance_container.clear()
        services.clear()

        # Force garbage collection
        gc.collect()

        metrics = profiler.stop_profiling()

        print(f"Memory delta after cleanup: {metrics['memory_delta_mb']:.2f}MB")

        # Memory should be reclaimed (or at least not increase significantly)
        assert metrics['memory_delta_mb'] < 5  # Should not increase by more than 5MB


# Concurrent Operations Tests
class TestConcurrentServiceOperations:
    """Test concurrent service operation performance"""

    @pytest.mark.asyncio
    async def test_concurrent_service_resolution(self, configured_performance_container, profiler):
        """Test concurrent service resolution performance"""
        profiler.start_profiling()

        async def resolve_service():
            service = configured_performance_container.resolve(ILightweightService)
            return service.quick_operation()

        # Create many concurrent resolution tasks
        start_time = time.time()
        tasks = [resolve_service() for _ in range(200)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        metrics = profiler.stop_profiling()

        ops_per_second = len(results) / total_time

        print(f"Concurrent resolutions: {ops_per_second:.0f} ops/sec")
        print(f"Total time: {total_time * 1000:.3f}ms")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert len(results) == 200
        assert ops_per_second > 1000  # Should handle high concurrency

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self, configured_performance_container, profiler):
        """Test concurrent operations on same service"""
        service = configured_performance_container.resolve(IHighPerformanceService)
        await service.initialize()

        profiler.start_profiling()

        # Create concurrent batch processing tasks
        batch_data = list(range(10))  # Small batches for testing

        start_time = time.time()
        tasks = [service.process_batch(batch_data) for _ in range(50)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        metrics = profiler.stop_profiling()

        batches_per_second = len(results) / total_time

        print(f"Concurrent batch processing: {batches_per_second:.0f} batches/sec")
        print(f"Memory delta: {metrics['memory_delta_mb']:.2f}MB")

        assert all(results)  # All batches should process successfully
        assert batches_per_second > 10  # Should handle reasonable throughput

    def test_thread_safety_of_container(self, configured_performance_container):
        """Test thread safety of DI container"""
        results = []
        errors = []

        def worker_thread():
            try:
                for _ in range(100):
                    service = configured_performance_container.resolve(ILightweightService)
                    result = service.quick_operation()
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads accessing container
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker_thread)
            threads.append(thread)

        start_time = time.time()

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        print(f"Thread safety test: {len(results)} operations in {total_time:.3f}s")
        print(f"Errors: {len(errors)}")

        # Should handle concurrent access without errors
        assert len(errors) == 0
        assert len(results) == 500  # 5 threads * 100 operations


# Performance Regression Tests
class TestPerformanceRegression:
    """Test for performance regressions"""

    def test_performance_baseline(self, configured_performance_container):
        """Establish performance baseline for regression testing"""
        # This test establishes baseline metrics that can be compared
        # in future test runs to detect performance regressions

        metrics = {}

        # Service resolution baseline
        start_time = time.time()
        for _ in range(1000):
            service = configured_performance_container.resolve(ILightweightService)
        metrics["resolution_time"] = time.time() - start_time

        # Service creation baseline
        creation_time = configured_performance_container.get_creation_time(ILightweightService)
        metrics["creation_time"] = creation_time

        print("Performance Baseline Metrics:")
        print(f"  Resolution time (1000 ops): {metrics['resolution_time']:.3f}s")
        print(f"  Service creation time: {metrics['creation_time'] * 1000:.3f}ms")

        # Store baseline for comparison (in real implementation)
        # This could be saved to a file or database for comparison
        baseline = {
            "resolution_ops_per_second": 1000 / metrics["resolution_time"],
            "creation_time_ms": metrics["creation_time"] * 1000
        }

        # Basic performance requirements
        assert baseline["resolution_ops_per_second"] > 5000
        assert baseline["creation_time_ms"] < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])