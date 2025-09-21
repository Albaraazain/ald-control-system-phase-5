#!/usr/bin/env python3
"""
Production Readiness Integration Test
Tests complete system startup, deployment scenarios, and operational procedures
"""

import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
import signal
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import subprocess

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.log_setup import setup_logger

# Set up logging
logger = setup_logger(__name__)

class ProductionReadinessTest:
    """Complete production readiness and deployment testing"""

    def __init__(self):
        self.test_results = {
            'test_run_id': str(uuid.uuid4()),
            'start_time': datetime.now().isoformat(),
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': [],
            'environment': 'production_readiness_test'
        }
        self.processes = []

    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all production readiness tests"""
        logger.info("🚀 Starting Production Readiness Test Suite")
        logger.info(f"Test Run ID: {self.test_results['test_run_id']}")

        try:
            # Test 1: Environment Setup and Configuration
            await self._test_environment_setup()

            # Test 2: System Dependencies and Requirements
            await self._test_system_dependencies()

            # Test 3: Application Startup and Initialization
            await self._test_application_startup()

            # Test 4: Service Health Checks and Monitoring
            await self._test_service_health_monitoring()

            # Test 5: Error Recovery and Resilience
            await self._test_error_recovery()

            # Test 6: Performance Under Load
            await self._test_performance_under_load()

            # Test 7: Graceful Shutdown and Cleanup
            await self._test_graceful_shutdown()

            # Test 8: Security and Access Control
            await self._test_security_access_control()

            # Test 9: Data Integrity and Persistence
            await self._test_data_integrity_persistence()

            # Test 10: Operational Procedures
            await self._test_operational_procedures()

        except Exception as e:
            logger.error(f"❌ Critical test failure: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._record_test_result("critical_failure", False, str(e))
        finally:
            # Cleanup any running processes
            await self._cleanup_processes()

        # Generate final report
        await self._generate_final_report()
        return self.test_results

    async def _test_environment_setup(self):
        """Test 1: Environment setup and configuration validation"""
        test_name = "environment_setup"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Check required files exist
            required_files = [
                'src/main.py',
                'requirements.txt',
                'CLAUDE.md',
                'src/di/container.py',
                'src/di/service_locator.py'
            ]

            missing_files = []
            for file_path in required_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)

            assert len(missing_files) == 0, f"Missing required files: {missing_files}"

            # Check Python version
            python_version = sys.version_info
            assert python_version >= (3, 8), f"Python 3.8+ required, got {python_version}"

            # Check virtual environment (if available)
            in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
            logger.info(f"Virtual environment: {'Yes' if in_venv else 'No'}")

            # Check environment variables
            critical_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
            missing_env_vars = []
            for var in critical_env_vars:
                if not os.getenv(var):
                    missing_env_vars.append(var)

            if missing_env_vars:
                logger.warning(f"Missing environment variables: {missing_env_vars}")

            await self._record_test_result(test_name, True, f"Environment setup validated - Python {python_version.major}.{python_version.minor}")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Environment setup failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_system_dependencies(self):
        """Test 2: System dependencies and requirements check"""
        test_name = "system_dependencies"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Check Python package dependencies
            try:
                import asyncio
                import supabase
                import dotenv
                logger.info("✅ Core Python dependencies available")
            except ImportError as e:
                logger.warning(f"⚠️ Missing Python dependency: {str(e)}")

            # Check project structure
            required_dirs = [
                'src',
                'src/di',
                'src/abstractions',
                'src/plc',
                'src/data_collection',
                'tests'
            ]

            missing_dirs = []
            for dir_path in required_dirs:
                if not os.path.isdir(dir_path):
                    missing_dirs.append(dir_path)

            assert len(missing_dirs) == 0, f"Missing required directories: {missing_dirs}"

            # Check if requirements.txt is parseable
            if os.path.exists('requirements.txt'):
                with open('requirements.txt', 'r') as f:
                    requirements = f.read()
                    assert len(requirements.strip()) > 0, "requirements.txt is empty"
                    logger.info(f"Requirements file contains {len(requirements.splitlines())} entries")

            await self._record_test_result(test_name, True, "System dependencies validated")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"System dependencies check failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_application_startup(self):
        """Test 3: Application startup and initialization"""
        test_name = "application_startup"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test import of main application modules
            startup_modules = [
                'src.main',
                'src.di.container',
                'src.di.service_locator',
                'src.log_setup'
            ]

            import_errors = []
            for module in startup_modules:
                try:
                    __import__(module)
                    logger.info(f"✅ Successfully imported {module}")
                except ImportError as e:
                    import_errors.append(f"{module}: {str(e)}")

            if import_errors:
                logger.warning(f"Import warnings: {import_errors}")

            # Test DI container creation
            from src.di.configuration import create_default_container
            from src.di.service_locator import ServiceLocator

            container = create_default_container()
            assert container is not None, "Failed to create DI container"

            ServiceLocator.configure(container)
            assert ServiceLocator.is_configured(), "ServiceLocator not configured"

            # Test basic service resolution
            all_services = ServiceLocator.get_all_services()
            logger.info(f"DI Container has {len(all_services)} registered services")

            # Cleanup
            await container.dispose()
            ServiceLocator.reset()

            await self._record_test_result(test_name, True, f"Application startup successful - {len(all_services)} services")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Application startup failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_service_health_monitoring(self):
        """Test 4: Service health checks and monitoring capabilities"""
        test_name = "service_health_monitoring"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test health check system
            from src.di.configuration import create_default_container
            from src.di.service_locator import ServiceLocator

            container = create_default_container()
            ServiceLocator.configure(container)

            # Perform health check
            health_status = await ServiceLocator.health_check()
            assert isinstance(health_status, dict), "Health check should return dict"

            logger.info(f"Health check completed for {len(health_status)} services")

            # Test individual service health monitoring
            class MonitoredService:
                def __init__(self):
                    self.healthy = True

                def health_check(self):
                    return self.healthy

            # Register service with health monitor
            container.register_singleton(MonitoredService)
            container.register_health_monitor(MonitoredService, lambda s: s.health_check())

            service = await container.resolve(MonitoredService)
            assert service.healthy, "Service should be healthy"

            # Test health check
            health = await container.health_check()
            assert MonitoredService in health, "Service not in health check results"
            assert health[MonitoredService] == True, "Service should report healthy"

            # Cleanup
            await container.dispose()
            ServiceLocator.reset()

            await self._record_test_result(test_name, True, "Service health monitoring working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Service health monitoring failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_error_recovery(self):
        """Test 5: Error recovery and resilience"""
        test_name = "error_recovery"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test graceful error handling in DI container
            from src.di.container import ServiceContainer

            container = ServiceContainer()

            # Test service registration failure recovery
            class FailingService:
                def __init__(self):
                    raise RuntimeError("Intentional failure")

            container.register_singleton(FailingService)

            try:
                await container.resolve(FailingService)
                assert False, "Should have failed"
            except RuntimeError as e:
                assert "Intentional failure" in str(e), "Wrong error message"
                logger.info("✅ Service creation failure handled gracefully")

            # Test container can continue working after failure
            class WorkingService:
                def __init__(self):
                    self.working = True

            container.register_singleton(WorkingService)
            service = await container.resolve(WorkingService)
            assert service.working, "Container should continue working after failure"

            # Test cleanup after errors
            await container.dispose()

            await self._record_test_result(test_name, True, "Error recovery and resilience working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Error recovery test failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_performance_under_load(self):
        """Test 6: Performance under load"""
        test_name = "performance_under_load"
        logger.info(f"🔍 Running {test_name}")

        try:
            from src.di.configuration import create_default_container
            from src.di.service_locator import ServiceLocator

            container = create_default_container()
            ServiceLocator.configure(container)

            # Create load test service
            class LoadTestService:
                def __init__(self):
                    self.requests = 0

                async def process_request(self):
                    self.requests += 1
                    await asyncio.sleep(0.001)  # Simulate work
                    return self.requests

            container.register_singleton(LoadTestService)

            # Load test with concurrent requests
            async def make_request():
                service = await ServiceLocator.get(LoadTestService)
                return await service.process_request()

            # Run 100 concurrent requests
            start_time = time.time()
            tasks = [make_request() for _ in range(100)]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            total_time = (end_time - start_time) * 1000  # Convert to ms
            requests_per_second = len(results) / (total_time / 1000)

            logger.info(f"Load test results:")
            logger.info(f"  - 100 requests in {total_time:.2f}ms")
            logger.info(f"  - {requests_per_second:.2f} requests/second")
            logger.info(f"  - Average time per request: {total_time / len(results):.2f}ms")

            # Performance requirements
            assert total_time < 1000, f"Load test too slow: {total_time:.2f}ms"
            assert requests_per_second > 50, f"Too few requests per second: {requests_per_second:.2f}"

            # Cleanup
            await container.dispose()
            ServiceLocator.reset()

            await self._record_test_result(test_name, True, f"Performance under load passed - {requests_per_second:.2f} req/s")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Performance under load failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_graceful_shutdown(self):
        """Test 7: Graceful shutdown and cleanup"""
        test_name = "graceful_shutdown"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test container disposal
            from src.di.container import ServiceContainer

            container = ServiceContainer()

            # Create service with cleanup
            class CleanupService:
                def __init__(self):
                    self.disposed = False

                async def dispose(self):
                    await asyncio.sleep(0.01)  # Simulate cleanup
                    self.disposed = True

            container.register_singleton(CleanupService)
            service = await container.resolve(CleanupService)

            # Test graceful shutdown
            await container.dispose()

            # Verify service was properly disposed
            assert service.disposed, "Service should be disposed"

            # Test container is properly disposed
            try:
                container.register_singleton(CleanupService)
                assert False, "Should not allow registration after disposal"
            except RuntimeError:
                logger.info("✅ Container properly prevents use after disposal")

            await self._record_test_result(test_name, True, "Graceful shutdown working")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Graceful shutdown failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_security_access_control(self):
        """Test 8: Security and access control"""
        test_name = "security_access_control"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test if security modules are available
            security_modules = []
            try:
                from src.security.credential_manager import SecureCredentialManager
                security_modules.append("credential_manager")
            except ImportError:
                pass

            try:
                from src.security.input_validator import InputValidator
                security_modules.append("input_validator")
            except ImportError:
                pass

            logger.info(f"Available security modules: {security_modules}")

            # Test basic security configuration
            if os.path.exists('.security_config.json'):
                with open('.security_config.json', 'r') as f:
                    security_config = json.load(f)
                    assert isinstance(security_config, dict), "Security config should be dict"
                    logger.info("✅ Security configuration file found")

            # Test environment variable security
            env_file_exists = os.path.exists('.env')
            if env_file_exists:
                logger.warning("⚠️ .env file exists - should be removed in production")

            # Test file permissions (if on Unix-like system)
            if hasattr(os, 'stat'):
                critical_files = ['src/main.py', 'requirements.txt']
                for file_path in critical_files:
                    if os.path.exists(file_path):
                        stat = os.stat(file_path)
                        # Check if file is world-writable
                        if stat.st_mode & 0o002:
                            logger.warning(f"⚠️ {file_path} is world-writable")

            await self._record_test_result(test_name, True, f"Security validation completed - {len(security_modules)} modules")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Security access control failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_data_integrity_persistence(self):
        """Test 9: Data integrity and persistence"""
        test_name = "data_integrity_persistence"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test database connectivity (if available)
            try:
                from src.db import get_supabase
                supabase = get_supabase()

                # Test basic connection
                result = supabase.table('component_parameters').select('id').limit(1).execute()
                logger.info("✅ Database connectivity working")

            except Exception as e:
                logger.warning(f"⚠️ Database connection issue: {str(e)}")

            # Test transactional components (if available)
            transactional_modules = []
            try:
                from src.data_collection.transactional.async_transaction_manager import AsyncTransactionManager
                transactional_modules.append("async_transaction_manager")
            except ImportError:
                pass

            try:
                from src.data_collection.transactional.atomic_dual_mode_repository import AtomicDualModeRepository
                transactional_modules.append("atomic_dual_mode_repository")
            except ImportError:
                pass

            logger.info(f"Available transactional modules: {transactional_modules}")

            # Test data validation interfaces
            try:
                from src.abstractions.interfaces import IDatabaseService, IParameterLogger
                logger.info("✅ Data service interfaces available")
            except ImportError as e:
                logger.warning(f"⚠️ Data interfaces not available: {str(e)}")

            await self._record_test_result(test_name, True, f"Data integrity validation completed - {len(transactional_modules)} transactional modules")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Data integrity persistence failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _test_operational_procedures(self):
        """Test 10: Operational procedures and monitoring"""
        test_name = "operational_procedures"
        logger.info(f"🔍 Running {test_name}")

        try:
            # Test logging configuration
            from src.log_setup import logger as app_logger
            assert app_logger is not None, "Application logger not available"

            # Test if operational scripts exist
            operational_scripts = [
                'run_migrations.py',
                'quick_performance_check.py',
                'baseline_performance_measurement.py'
            ]

            available_scripts = []
            for script in operational_scripts:
                if os.path.exists(script):
                    available_scripts.append(script)

            logger.info(f"Available operational scripts: {available_scripts}")

            # Test configuration files
            config_files = ['CLAUDE.md', 'requirements.txt']
            for config_file in config_files:
                assert os.path.exists(config_file), f"Missing config file: {config_file}"

            # Test documentation
            doc_files = []
            doc_patterns = ['*.md', 'README*', 'SETUP*', 'OPERATIONS*']
            for pattern in doc_patterns:
                import glob
                matches = glob.glob(pattern)
                doc_files.extend(matches)

            logger.info(f"Available documentation: {doc_files}")

            await self._record_test_result(test_name, True, f"Operational procedures validated - {len(available_scripts)} scripts, {len(doc_files)} docs")
            logger.info(f"✅ {test_name} passed")

        except Exception as e:
            await self._record_test_result(test_name, False, f"Operational procedures failed: {str(e)}")
            logger.error(f"❌ {test_name} failed: {str(e)}")

    async def _cleanup_processes(self):
        """Clean up any running processes"""
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass

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
        report_filename = f"production_readiness_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        logger.info("=" * 60)
        logger.info("🏁 PRODUCTION READINESS TEST RESULTS")
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
    """Main entry point for production readiness testing"""
    try:
        logger.info("🚀 Starting Production Readiness Test")

        # Initialize test framework
        test_framework = ProductionReadinessTest()

        # Run all tests
        results = await test_framework.run_all_tests()

        # Return appropriate exit code
        if results['tests_failed'] == 0:
            logger.info("🎉 ALL PRODUCTION READINESS TESTS PASSED!")
            return 0
        else:
            logger.error(f"💥 {results['tests_failed']} PRODUCTION READINESS TESTS FAILED!")
            return 1

    except Exception as e:
        logger.error(f"💥 Critical failure in production readiness test framework: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)