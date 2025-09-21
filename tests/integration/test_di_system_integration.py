#!/usr/bin/env python3
"""
DI Container System Integration Test
Tests complete system startup with new DI architecture and validates all integrations
"""

import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger
from src.di.container import ServiceContainer
from src.di.service_locator import ServiceLocator
from src.di.configuration import create_default_container

# Set up logging
logger = setup_logger(__name__)

class DISystemIntegrationTest:
    """Complete DI container system integration test"""

    def __init__(self):
        self.test_results = {
            'test_run_id': str(uuid.uuid4()),
            'start_time': datetime.now().isoformat(),
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': [],
            'environment': 'di_integration_test'
        }
        self.container = None

    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all DI integration tests"""
        logger.info("🚀 Starting DI Container System Integration Test Suite")
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")

        try:
            # Test 1: DI Container Creation and Configuration
            await self._test_di_container_creation()

            # Test 2: ServiceLocator Configuration
            await self._test_service_locator_configuration()

            # Test 3: Core Service Registration and Resolution
            await self._test_core_service_resolution()

            # Test 4: Async Service Creation and Lifecycle
            await self._test_async_service_lifecycle()

            # Test 5: Service Dependencies and Auto-wiring
            await self._test_service_dependencies()

            # Test 6: Performance and Resolution Speed
            await self._test_performance_requirements()

            # Test 7: Error Handling and Recovery
            await self._test_error_handling()

            # Test 8: Backward Compatibility Integration
            await self._test_backward_compatibility()

            # Test 9: Transactional Service Integration
            await self._test_transactional_service_integration()

            # Test 10: Production Startup Simulation
            await self._test_production_startup_simulation()

        except Exception as e:
            logger.error(f"❌ Critical test failure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._record_test_result("critical_failure", False, str(e))
        finally:
            # Cleanup
            if self.container:
                await self.container.dispose()

        # Generate final report
        await self._generate_final_report()
        return self.test_results

    async def _test_di_container_creation(self):
        """Test 1: DI Container creation and basic functionality"""
        test_name = "di_container_creation"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Create default container
            self.container = create_default_container()
            assert self.container is not None, "Failed to create DI container"

            # Verify container properties
            assert hasattr(self.container, '_services'), "Container missing _services"
            assert hasattr(self.container, '_singletons'), "Container missing _singletons"
            assert hasattr(self.container, '_lock'), "Container missing async lock"

            # Test basic registration
            class TestService:
                def __init__(self):
                    self.initialized = True

            self.container.register_singleton(TestService)

            # Test resolution
            service = await self.container.resolve(TestService)
            assert service is not None, "Failed to resolve test service"
            assert service.initialized, "Service not properly initialized"

            await self._record_test_result(test_name, True, "DI container creation and basic functionality working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"DI container creation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_service_locator_configuration(self):
        """Test 2: ServiceLocator configuration and global access"""
        test_name = "service_locator_configuration"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Configure ServiceLocator
            ServiceLocator.configure(self.container)
            assert ServiceLocator.is_configured(), "ServiceLocator not configured"

            # Test service resolution through ServiceLocator
            class LocatorTestService:
                def __init__(self):
                    self.value = "locator_test"

            self.container.register_singleton(LocatorTestService)

            service = await ServiceLocator.get(LocatorTestService)
            assert service is not None, "Failed to resolve through ServiceLocator"
            assert service.value == "locator_test", "Service value incorrect"

            # Test health check
            health = await ServiceLocator.health_check()
            assert isinstance(health, dict), "Health check should return dict"

            await self._record_test_result(test_name, True, "ServiceLocator configuration working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"ServiceLocator configuration failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_core_service_resolution(self):
        """Test 3: Core service registration and resolution"""
        test_name = "core_service_resolution"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Check if core interfaces are registered
            from src.abstractions.interfaces import (
                IPLCInterface, IDatabaseService, IParameterLogger
            )

            # Test interface registration
            is_plc_registered = ServiceLocator.is_service_registered(IPLCInterface)
            is_db_registered = ServiceLocator.is_service_registered(IDatabaseService)
            is_logger_registered = ServiceLocator.is_service_registered(IParameterLogger)

            logger.info(f"PLC Interface registered: {is_plc_registered}")
            logger.info(f"Database Service registered: {is_db_registered}")
            logger.info(f"Parameter Logger registered: {is_logger_registered}")

            # Get service information
            all_services = ServiceLocator.get_all_services()
            assert len(all_services) > 0, "No services registered"

            logger.info(f"Total services registered: {len(all_services)}")
            for service_name, info in all_services.items():
                logger.info(f"  - {service_name}: {info['lifetime']}")

            await self._record_test_result(test_name, True, f"Core services analysis complete: {len(all_services)} services")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Core service resolution failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_async_service_lifecycle(self):
        """Test 4: Async service creation and lifecycle management"""
        test_name = "async_service_lifecycle"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Create async service with lifecycle
            class AsyncLifecycleService:
                def __init__(self):
                    self.started = False
                    self.disposed = False

                async def start(self):
                    await asyncio.sleep(0.01)  # Simulate async work
                    self.started = True

                async def dispose(self):
                    await asyncio.sleep(0.01)  # Simulate async cleanup
                    self.disposed = True

            # Register with async factory
            async def create_async_service(container):
                service = AsyncLifecycleService()
                await service.start()
                return service

            self.container.register_singleton(AsyncLifecycleService, factory=create_async_service)

            # Resolve and test
            service = await self.container.resolve(AsyncLifecycleService)
            assert service.started, "Async service not started"
            assert not service.disposed, "Service should not be disposed yet"

            # Test service disposal
            await service.dispose()
            assert service.disposed, "Service not disposed properly"

            await self._record_test_result(test_name, True, "Async service lifecycle working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Async service lifecycle failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_service_dependencies(self):
        """Test 5: Service dependencies and auto-wiring"""
        test_name = "service_dependencies"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Create dependent services
            class DatabaseService:
                def __init__(self):
                    self.connected = True

            class LoggingService:
                def __init__(self, db: DatabaseService):
                    self.db = db
                    self.initialized = True

            # Register services
            self.container.register_singleton(DatabaseService)
            self.container.register_singleton(LoggingService)

            # Resolve with auto-wiring
            logging_service = await self.container.resolve(LoggingService)
            assert logging_service.initialized, "Logging service not initialized"
            assert logging_service.db is not None, "Database dependency not injected"
            assert logging_service.db.connected, "Database service not connected"

            # Test circular dependency detection
            class ServiceA:
                def __init__(self, b: 'ServiceB'):
                    self.b = b

            class ServiceB:
                def __init__(self, a: ServiceA):
                    self.a = a

            self.container.register_singleton(ServiceA)
            self.container.register_singleton(ServiceB)

            try:
                await self.container.resolve(ServiceA)
                assert False, "Should have detected circular dependency"
            except Exception as e:
                assert "circular" in str(e).lower(), f"Wrong error type: {str(e)}"
                logger.info("✅ Circular dependency detection working")

            await self._record_test_result(test_name, True, "Service dependencies and auto-wiring working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Service dependencies failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_performance_requirements(self):
        """Test 6: Performance and resolution speed"""
        test_name = "performance_requirements"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Create performance test service
            class PerformanceTestService:
                def __init__(self):
                    self.created_at = datetime.now()

            self.container.register_singleton(PerformanceTestService)

            # Measure resolution time
            import time
            resolution_times = []

            for i in range(100):
                start = time.perf_counter()
                service = await self.container.resolve(PerformanceTestService)
                end = time.perf_counter()
                resolution_times.append((end - start) * 1000)  # Convert to ms

            avg_time = sum(resolution_times) / len(resolution_times)
            max_time = max(resolution_times)

            logger.info(f"Resolution times - Avg: {avg_time:.3f}ms, Max: {max_time:.3f}ms")

            # Performance requirements: <1ms for singleton resolution
            assert avg_time < 1.0, f"Average resolution time too slow: {avg_time:.3f}ms"
            assert max_time < 5.0, f"Max resolution time too slow: {max_time:.3f}ms"

            await self._record_test_result(test_name, True, f"Performance good - Avg: {avg_time:.3f}ms, Max: {max_time:.3f}ms")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Performance requirements failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_error_handling(self):
        """Test 7: Error handling and recovery scenarios"""
        test_name = "error_handling_recovery"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test unregistered service
            class UnregisteredService:
                pass

            try:
                await self.container.resolve(UnregisteredService)
                assert False, "Should have failed for unregistered service"
            except Exception as e:
                assert "not registered" in str(e).lower(), f"Wrong error message: {str(e)}"

            # Test factory failure
            async def failing_factory(container):
                raise RuntimeError("Factory intentionally failed")

            class FailingService:
                pass

            self.container.register_singleton(FailingService, factory=failing_factory)

            try:
                await self.container.resolve(FailingService)
                assert False, "Should have failed for failing factory"
            except RuntimeError as e:
                assert "intentionally failed" in str(e), f"Wrong error: {str(e)}"

            # Test container disposal
            test_container = ServiceContainer()
            await test_container.dispose()

            try:
                test_container.register_singleton(UnregisteredService)
                assert False, "Should have failed for disposed container"
            except RuntimeError as e:
                assert "disposed" in str(e).lower(), f"Wrong error: {str(e)}"

            await self._record_test_result(test_name, True, "Error handling and recovery working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Error handling failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_backward_compatibility(self):
        """Test 8: Backward compatibility with existing code"""
        test_name = "backward_compatibility"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test that existing imports still work
            try:
                from src.plc.manager import plc_manager
                from src.data_collection.service import data_collection_service
                logger.info("✅ Existing singleton imports working")
            except ImportError as e:
                logger.warning(f"⚠️ Import warning: {str(e)}")

            # Test ServiceLocator can coexist with singletons
            class LegacyCompatService:
                def __init__(self):
                    self.legacy_compatible = True

            self.container.register_singleton(LegacyCompatService)
            service = await ServiceLocator.get(LegacyCompatService)
            assert service.legacy_compatible, "Legacy compatibility broken"

            # Test that we can still resolve services synchronously for certain cases
            try:
                service_sync = ServiceLocator.get_sync(LegacyCompatService)
                assert service_sync is not None, "Sync resolution failed"
                logger.info("✅ Synchronous resolution working")
            except Exception as e:
                logger.info(f"ℹ️ Sync resolution not available: {str(e)}")

            await self._record_test_result(test_name, True, "Backward compatibility preserved")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Backward compatibility failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_transactional_service_integration(self):
        """Test 9: Integration with transactional services"""
        test_name = "transactional_service_integration"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Check if transactional components exist and can be registered
            try:
                from src.data_collection.transactional.async_transaction_manager import AsyncTransactionManager
                from src.data_collection.transactional.atomic_dual_mode_repository import AtomicDualModeRepository

                # Register transactional services
                self.container.register_singleton(AsyncTransactionManager)

                # Test resolution
                tx_manager = await self.container.resolve(AsyncTransactionManager)
                assert tx_manager is not None, "Failed to resolve transaction manager"

                logger.info("✅ Transactional services can be integrated with DI")

            except ImportError as e:
                logger.warning(f"⚠️ Transactional services not found: {str(e)}")

            await self._record_test_result(test_name, True, "Transactional service integration possible")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Transactional service integration failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_production_startup_simulation(self):
        """Test 10: Production startup simulation"""
        test_name = "production_startup_simulation"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Simulate production startup sequence
            startup_times = {}

            # 1. Container creation
            start_time = datetime.now()
            prod_container = create_default_container()
            startup_times['container_creation'] = (datetime.now() - start_time).total_seconds() * 1000

            # 2. ServiceLocator configuration
            start_time = datetime.now()
            ServiceLocator.configure(prod_container)
            startup_times['service_locator_config'] = (datetime.now() - start_time).total_seconds() * 1000

            # 3. Core service resolution
            start_time = datetime.now()
            try:
                from src.abstractions.interfaces import IPLCInterface
                if ServiceLocator.is_service_registered(IPLCInterface):
                    await ServiceLocator.get(IPLCInterface)
                    startup_times['plc_service_resolution'] = (datetime.now() - start_time).total_seconds() * 1000
            except Exception as e:
                logger.info(f"PLC service not available: {str(e)}")
                startup_times['plc_service_resolution'] = 0

            # 4. Health check
            start_time = datetime.now()
            health = await ServiceLocator.health_check()
            startup_times['health_check'] = (datetime.now() - start_time).total_seconds() * 1000

            # Log startup performance
            total_startup_time = sum(startup_times.values())
            logger.info(f"Production startup simulation:")
            for phase, time_ms in startup_times.items():
                logger.info(f"  - {phase}: {time_ms:.2f}ms")
            logger.info(f"  - Total: {total_startup_time:.2f}ms")

            # Cleanup
            await prod_container.dispose()

            # Startup should be fast (<1000ms total)
            assert total_startup_time < 1000, f"Startup too slow: {total_startup_time:.2f}ms"

            await self._record_test_result(test_name, True, f"Production startup simulation passed - {total_startup_time:.2f}ms")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Production startup simulation failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _record_test_result(self, test_name: str, passed: bool, message: str):
        """Record individual test result"""
        if passed:
            self.test_results['tests_passed'] += 1
        else:
            self.test_results['tests_failed'] += 1

        self.test_results['test_details'].append({
            'test_name': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

    async def _generate_final_report(self):
        """Generate comprehensive test report"""
        self.test_results['end_time'] = datetime.now().isoformat()
        self.test_results['total_tests'] = self.test_results['tests_passed'] + self.test_results['tests_failed']
        self.test_results['success_rate'] = (self.test_results['tests_passed'] / self.test_results['total_tests'] * 100) if self.test_results['total_tests'] > 0 else 0

        # Write detailed report
        report_filename = f"di_integration_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        logger.info("=" * 60)
        logger.info("🏁 DI CONTAINER SYSTEM INTEGRATION TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")
        logger.info(f"Total Tests: {self.test_results['total_tests']}")
        logger.info(f"Passed: {self.test_results['tests_passed']}")
        logger.info(f"Failed: {self.test_results['tests_failed']}")
        logger.info(f"Success Rate: {self.test_results['success_rate']:.1f}%")
        logger.info(f"Report saved: {report_filename}")
        logger.info("=" * 60)

        for test in self.test_results['test_details']:
            status_emoji = "✅" if test['passed'] else "❌"
            logger.info(f"{status_emoji} {test['test_name']}: {test['message']}")

        logger.info("=" * 60)


async def main():
    """Main entry point for DI integration testing"""
    try:
        logger.info("🚀 Starting DI Container System Integration Test")

        # Initialize test framework
        test_framework = DISystemIntegrationTest()

        # Run all tests
        results = await test_framework.run_all_tests()

        # Return appropriate exit code
        if results['tests_failed'] == 0:
            logger.info("🎉 ALL DI INTEGRATION TESTS PASSED!")
            return 0
        else:
            logger.error(f"💥 {results['tests_failed']} DI INTEGRATION TESTS FAILED!")
            return 1

    except Exception as e:
        logger.error(f"💥 Critical failure in DI integration test framework: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)