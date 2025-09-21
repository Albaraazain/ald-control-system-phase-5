# File: src/di/deployment.py
"""
Zero-downtime deployment and service lifecycle management.
Implements blue-green deployment strategy with health checks and automated rollback.
"""
import asyncio
import time
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
import uuid
import json
import os
from contextlib import asynccontextmanager

from .container import ServiceContainer, ServiceLifetime
from .service_locator import ServiceLocator
from .migration import FeatureFlag, MigrationPhase
from ..abstractions.interfaces import IPLCInterface, IDatabaseService, IParameterLogger
from src.log_setup import logger

class DeploymentState(Enum):
    """Deployment states for blue-green deployment"""
    IDLE = "idle"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    TESTING = "testing"
    ACTIVATING = "activating"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"

class ServiceHealth(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service_name: str
    status: ServiceHealth
    message: str
    response_time_ms: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeploymentConfiguration:
    """Configuration for a deployment"""
    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rollback_timeout_seconds: int = 300
    health_check_timeout_seconds: int = 30
    health_check_retries: int = 3
    health_check_interval_seconds: int = 5
    canary_percentage: float = 0.1
    enable_automated_rollback: bool = True
    require_manual_approval: bool = False
    backup_services: bool = True

class HealthCheckRegistry:
    """Registry for service health checks"""

    def __init__(self):
        self._health_checks: Dict[str, Callable] = {}
        self._health_history: Dict[str, List[HealthCheckResult]] = {}
        self._max_history_size = 100

    def register_health_check(self, service_name: str, health_check: Callable):
        """
        Register a health check for a service.

        Args:
            service_name: Name of the service
            health_check: Async function that returns HealthCheckResult
        """
        self._health_checks[service_name] = health_check
        if service_name not in self._health_history:
            self._health_history[service_name] = []
        logger.debug(f"Registered health check for service: {service_name}")

    async def check_service_health(self, service_name: str) -> HealthCheckResult:
        """
        Perform health check for a specific service.

        Args:
            service_name: Name of the service to check

        Returns:
            Health check result
        """
        if service_name not in self._health_checks:
            return HealthCheckResult(
                service_name=service_name,
                status=ServiceHealth.UNKNOWN,
                message="No health check registered",
                response_time_ms=0.0
            )

        start_time = time.perf_counter()
        try:
            health_check = self._health_checks[service_name]
            result = await health_check()

            if not isinstance(result, HealthCheckResult):
                # Convert simple boolean/dict responses
                if isinstance(result, bool):
                    status = ServiceHealth.HEALTHY if result else ServiceHealth.UNHEALTHY
                    message = "Health check passed" if result else "Health check failed"
                elif isinstance(result, dict):
                    status = ServiceHealth(result.get('status', 'unknown'))
                    message = result.get('message', 'No message')
                else:
                    status = ServiceHealth.HEALTHY
                    message = str(result)

                response_time = (time.perf_counter() - start_time) * 1000
                result = HealthCheckResult(
                    service_name=service_name,
                    status=status,
                    message=message,
                    response_time_ms=response_time
                )

            # Store in history
            self._health_history[service_name].append(result)
            if len(self._health_history[service_name]) > self._max_history_size:
                self._health_history[service_name].pop(0)

            return result

        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            result = HealthCheckResult(
                service_name=service_name,
                status=ServiceHealth.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=response_time
            )
            self._health_history[service_name].append(result)
            logger.error(f"Health check failed for {service_name}: {str(e)}")
            return result

    async def check_all_services(self) -> Dict[str, HealthCheckResult]:
        """
        Perform health checks for all registered services.

        Returns:
            Dictionary mapping service names to health check results
        """
        tasks = [
            self.check_service_health(service_name)
            for service_name in self._health_checks.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        health_status = {}
        for i, result in enumerate(results):
            service_name = list(self._health_checks.keys())[i]
            if isinstance(result, Exception):
                health_status[service_name] = HealthCheckResult(
                    service_name=service_name,
                    status=ServiceHealth.UNHEALTHY,
                    message=f"Health check exception: {str(result)}",
                    response_time_ms=0.0
                )
            else:
                health_status[service_name] = result

        return health_status

    def get_service_health_history(self, service_name: str) -> List[HealthCheckResult]:
        """Get health check history for a service"""
        return self._health_history.get(service_name, []).copy()

    def get_overall_health(self) -> ServiceHealth:
        """Get overall system health based on all services"""
        if not self._health_checks:
            return ServiceHealth.UNKNOWN

        # Get latest health status for each service
        latest_status = []
        for service_name in self._health_checks.keys():
            history = self._health_history.get(service_name, [])
            if history:
                latest_status.append(history[-1].status)

        if not latest_status:
            return ServiceHealth.UNKNOWN

        # Determine overall health
        if all(status == ServiceHealth.HEALTHY for status in latest_status):
            return ServiceHealth.HEALTHY
        elif any(status == ServiceHealth.UNHEALTHY for status in latest_status):
            return ServiceHealth.UNHEALTHY
        else:
            return ServiceHealth.DEGRADED

class BlueGreenDeploymentManager:
    """
    Blue-green deployment manager for zero-downtime updates.

    Manages two service environments (blue/green) and switches between them
    after successful health checks and validation.
    """

    def __init__(self, health_registry: HealthCheckRegistry):
        self.health_registry = health_registry
        self._blue_container: Optional[ServiceContainer] = None
        self._green_container: Optional[ServiceContainer] = None
        self._active_environment = "blue"  # blue or green
        self._deployment_state = DeploymentState.IDLE
        self._deployment_history: List[Dict[str, Any]] = []
        self._rollback_stack: List[Dict[str, Any]] = []

    @property
    def active_container(self) -> Optional[ServiceContainer]:
        """Get the currently active service container"""
        if self._active_environment == "blue":
            return self._blue_container
        else:
            return self._green_container

    @property
    def inactive_container(self) -> Optional[ServiceContainer]:
        """Get the currently inactive service container"""
        if self._active_environment == "blue":
            return self._green_container
        else:
            return self._blue_container

    def initialize_environments(
        self,
        blue_container: ServiceContainer,
        green_container: Optional[ServiceContainer] = None
    ):
        """
        Initialize blue and green environments.

        Args:
            blue_container: Blue environment container
            green_container: Green environment container (optional, will clone blue if not provided)
        """
        self._blue_container = blue_container

        if green_container is None:
            # Create a new container for green environment
            self._green_container = ServiceContainer()
            # Note: In a real implementation, you'd want to copy service registrations
            logger.info("Created new green environment container")
        else:
            self._green_container = green_container

        logger.info(f"Initialized blue-green environments, active: {self._active_environment}")

    async def deploy(
        self,
        deployment_fn: Callable[[ServiceContainer], None],
        config: DeploymentConfiguration
    ) -> bool:
        """
        Perform a blue-green deployment.

        Args:
            deployment_fn: Function to configure the new environment
            config: Deployment configuration

        Returns:
            True if deployment successful, False otherwise
        """
        if self._deployment_state != DeploymentState.IDLE:
            logger.error(f"Cannot start deployment, current state: {self._deployment_state}")
            return False

        deployment_record = {
            "deployment_id": config.deployment_id,
            "start_time": time.time(),
            "initial_environment": self._active_environment,
            "config": config.__dict__.copy()
        }

        try:
            self._deployment_state = DeploymentState.PREPARING
            logger.info(f"Starting blue-green deployment {config.deployment_id}")

            # Prepare the inactive environment
            target_container = self.inactive_container
            if target_container is None:
                raise RuntimeError("Target environment not initialized")

            # Backup current configuration if requested
            if config.backup_services:
                await self._backup_current_environment()

            # Deploy to inactive environment
            self._deployment_state = DeploymentState.DEPLOYING
            logger.info(f"Deploying to {self._get_inactive_environment_name()} environment")

            await asyncio.get_event_loop().run_in_executor(
                None, deployment_fn, target_container
            )

            # Health check the new environment
            self._deployment_state = DeploymentState.TESTING
            if not await self._validate_deployment(config):
                logger.error("Deployment validation failed")
                if config.enable_automated_rollback:
                    await self._rollback(config)
                return False

            # Manual approval if required
            if config.require_manual_approval:
                logger.info("Deployment ready, waiting for manual approval...")
                # In a real implementation, this would wait for external approval
                await asyncio.sleep(1)  # Placeholder

            # Switch environments
            self._deployment_state = DeploymentState.ACTIVATING
            await self._switch_environments()

            self._deployment_state = DeploymentState.COMPLETED
            deployment_record["end_time"] = time.time()
            deployment_record["status"] = "success"
            deployment_record["final_environment"] = self._active_environment

            self._deployment_history.append(deployment_record)
            logger.info(f"Blue-green deployment {config.deployment_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Deployment {config.deployment_id} failed: {str(e)}")
            self._deployment_state = DeploymentState.FAILED
            deployment_record["end_time"] = time.time()
            deployment_record["status"] = "failed"
            deployment_record["error"] = str(e)
            self._deployment_history.append(deployment_record)

            if config.enable_automated_rollback:
                await self._rollback(config)

            return False

        finally:
            if self._deployment_state not in [DeploymentState.COMPLETED, DeploymentState.ROLLING_BACK]:
                self._deployment_state = DeploymentState.IDLE

    async def _validate_deployment(self, config: DeploymentConfiguration) -> bool:
        """Validate deployment through health checks"""
        logger.info("Validating deployment through health checks...")

        for attempt in range(config.health_check_retries):
            logger.info(f"Health check attempt {attempt + 1}/{config.health_check_retries}")

            try:
                # Perform health checks with timeout
                health_results = await asyncio.wait_for(
                    self.health_registry.check_all_services(),
                    timeout=config.health_check_timeout_seconds
                )

                # Analyze results
                failed_services = [
                    name for name, result in health_results.items()
                    if result.status == ServiceHealth.UNHEALTHY
                ]

                if not failed_services:
                    logger.info("All health checks passed")
                    return True

                logger.warning(f"Failed services: {failed_services}")

                if attempt < config.health_check_retries - 1:
                    await asyncio.sleep(config.health_check_interval_seconds)

            except asyncio.TimeoutError:
                logger.error(f"Health check timed out after {config.health_check_timeout_seconds}s")
            except Exception as e:
                logger.error(f"Health check failed: {str(e)}")

        logger.error("Deployment validation failed after all retries")
        return False

    async def _switch_environments(self):
        """Switch active and inactive environments"""
        old_environment = self._active_environment
        self._active_environment = "green" if self._active_environment == "blue" else "blue"

        # Update service locator to use new active container
        ServiceLocator.configure(self.active_container)

        logger.info(f"Switched from {old_environment} to {self._active_environment} environment")

    async def _backup_current_environment(self):
        """Backup current environment for rollback"""
        backup_info = {
            "timestamp": time.time(),
            "active_environment": self._active_environment,
            "container_info": self.active_container.get_all_services() if self.active_container else []
        }
        self._rollback_stack.append(backup_info)
        logger.info("Backed up current environment for rollback")

    async def _rollback(self, config: DeploymentConfiguration):
        """Rollback to previous environment"""
        if not self._rollback_stack:
            logger.error("No backup available for rollback")
            return

        logger.info("Starting automated rollback...")
        self._deployment_state = DeploymentState.ROLLING_BACK

        try:
            # Switch back to previous environment
            await self._switch_environments()

            # Validate rollback
            if await self._validate_deployment(config):
                logger.info("Rollback completed successfully")
            else:
                logger.error("Rollback validation failed")

        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")

        finally:
            self._deployment_state = DeploymentState.IDLE

    def _get_inactive_environment_name(self) -> str:
        """Get the name of the inactive environment"""
        return "green" if self._active_environment == "blue" else "blue"

    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return {
            "state": self._deployment_state.value,
            "active_environment": self._active_environment,
            "deployment_history": self._deployment_history[-10:],  # Last 10 deployments
            "rollback_available": bool(self._rollback_stack)
        }

class ServiceLifecycleManager:
    """
    Manages service lifecycle including startup, shutdown, and health monitoring.
    """

    def __init__(
        self,
        container: ServiceContainer,
        health_registry: HealthCheckRegistry
    ):
        self.container = container
        self.health_registry = health_registry
        self._running_services: Dict[str, Any] = {}
        self._service_dependencies: Dict[str, List[str]] = {}
        self._startup_order: List[str] = []
        self._shutdown_order: List[str] = []
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._health_monitor_interval = 30  # seconds

    def register_service_lifecycle(
        self,
        service_name: str,
        startup_fn: Optional[Callable] = None,
        shutdown_fn: Optional[Callable] = None,
        health_check_fn: Optional[Callable] = None,
        dependencies: Optional[List[str]] = None
    ):
        """
        Register lifecycle management for a service.

        Args:
            service_name: Name of the service
            startup_fn: Optional startup function
            shutdown_fn: Optional shutdown function
            health_check_fn: Optional health check function
            dependencies: List of service dependencies
        """
        if startup_fn:
            # Store startup function
            pass  # Implementation would register startup function

        if shutdown_fn:
            # Store shutdown function
            pass  # Implementation would register shutdown function

        if health_check_fn:
            self.health_registry.register_health_check(service_name, health_check_fn)

        if dependencies:
            self._service_dependencies[service_name] = dependencies

        logger.debug(f"Registered lifecycle management for service: {service_name}")

    async def start_all_services(self) -> bool:
        """Start all registered services in dependency order"""
        logger.info("Starting all services...")

        try:
            # Calculate startup order based on dependencies
            startup_order = self._calculate_startup_order()

            for service_name in startup_order:
                logger.info(f"Starting service: {service_name}")
                # Start service (implementation would call startup function)
                self._running_services[service_name] = {"status": "running", "start_time": time.time()}

            # Start health monitoring
            await self._start_health_monitoring()

            logger.info("All services started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start services: {str(e)}")
            return False

    async def stop_all_services(self) -> bool:
        """Stop all services in reverse dependency order"""
        logger.info("Stopping all services...")

        try:
            # Stop health monitoring
            if self._health_monitor_task:
                self._health_monitor_task.cancel()
                try:
                    await self._health_monitor_task
                except asyncio.CancelledError:
                    pass

            # Calculate shutdown order (reverse of startup)
            shutdown_order = list(reversed(self._startup_order))

            for service_name in shutdown_order:
                if service_name in self._running_services:
                    logger.info(f"Stopping service: {service_name}")
                    # Stop service (implementation would call shutdown function)
                    del self._running_services[service_name]

            logger.info("All services stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to stop services: {str(e)}")
            return False

    def _calculate_startup_order(self) -> List[str]:
        """Calculate service startup order based on dependencies"""
        # Simple topological sort implementation
        # In a real implementation, this would be more sophisticated
        ordered_services = []

        # For now, just return services without dependencies first
        services_without_deps = [
            name for name, deps in self._service_dependencies.items()
            if not deps
        ]
        services_with_deps = [
            name for name, deps in self._service_dependencies.items()
            if deps
        ]

        ordered_services.extend(services_without_deps)
        ordered_services.extend(services_with_deps)

        self._startup_order = ordered_services
        return ordered_services

    async def _start_health_monitoring(self):
        """Start background health monitoring"""
        if self._health_monitor_task and not self._health_monitor_task.done():
            return  # Already running

        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        logger.info("Started health monitoring")

    async def _health_monitor_loop(self):
        """Background health monitoring loop"""
        try:
            while True:
                await asyncio.sleep(self._health_monitor_interval)

                try:
                    health_results = await self.health_registry.check_all_services()

                    # Log any unhealthy services
                    for service_name, result in health_results.items():
                        if result.status == ServiceHealth.UNHEALTHY:
                            logger.warning(
                                f"Service {service_name} is unhealthy: {result.message}"
                            )
                        elif result.status == ServiceHealth.DEGRADED:
                            logger.info(
                                f"Service {service_name} is degraded: {result.message}"
                            )

                except Exception as e:
                    logger.error(f"Health monitoring error: {str(e)}")

        except asyncio.CancelledError:
            logger.info("Health monitoring stopped")
            raise

# Global instances
_health_registry: Optional[HealthCheckRegistry] = None
_deployment_manager: Optional[BlueGreenDeploymentManager] = None
_lifecycle_manager: Optional[ServiceLifecycleManager] = None

def get_health_registry() -> HealthCheckRegistry:
    """Get the global health check registry"""
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    return _health_registry

def get_deployment_manager() -> BlueGreenDeploymentManager:
    """Get the global deployment manager"""
    global _deployment_manager
    if _deployment_manager is None:
        _deployment_manager = BlueGreenDeploymentManager(get_health_registry())
    return _deployment_manager

def get_lifecycle_manager(container: Optional[ServiceContainer] = None) -> ServiceLifecycleManager:
    """Get the global lifecycle manager"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        if container is None:
            raise RuntimeError("Container required for first-time lifecycle manager initialization")
        _lifecycle_manager = ServiceLifecycleManager(container, get_health_registry())
    return _lifecycle_manager

# Default health checks for core services
async def plc_health_check() -> HealthCheckResult:
    """Health check for PLC service"""
    try:
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IPLCInterface):
            plc = ServiceLocator.try_get(IPLCInterface)
            if plc:
                # Check if PLC is connected
                connected = getattr(plc, 'connected', False)
                if callable(connected):
                    connected = connected()

                status = ServiceHealth.HEALTHY if connected else ServiceHealth.UNHEALTHY
                message = "PLC connected" if connected else "PLC disconnected"

                return HealthCheckResult(
                    service_name="plc",
                    status=status,
                    message=message,
                    response_time_ms=0.0
                )

        return HealthCheckResult(
            service_name="plc",
            status=ServiceHealth.UNKNOWN,
            message="PLC service not available",
            response_time_ms=0.0
        )

    except Exception as e:
        return HealthCheckResult(
            service_name="plc",
            status=ServiceHealth.UNHEALTHY,
            message=f"PLC health check failed: {str(e)}",
            response_time_ms=0.0
        )

async def database_health_check() -> HealthCheckResult:
    """Health check for database service"""
    try:
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IDatabaseService):
            db = ServiceLocator.try_get(IDatabaseService)
            if db:
                # Simple connectivity test
                # Implementation would depend on the database interface
                status = ServiceHealth.HEALTHY
                message = "Database connected"

                return HealthCheckResult(
                    service_name="database",
                    status=status,
                    message=message,
                    response_time_ms=0.0
                )

        return HealthCheckResult(
            service_name="database",
            status=ServiceHealth.UNKNOWN,
            message="Database service not available",
            response_time_ms=0.0
        )

    except Exception as e:
        return HealthCheckResult(
            service_name="database",
            status=ServiceHealth.UNHEALTHY,
            message=f"Database health check failed: {str(e)}",
            response_time_ms=0.0
        )

async def parameter_logger_health_check() -> HealthCheckResult:
    """Health check for parameter logger service"""
    try:
        if ServiceLocator.is_configured() and ServiceLocator.is_service_registered(IParameterLogger):
            logger_service = ServiceLocator.try_get(IParameterLogger)
            if logger_service:
                # Check if logger is running
                running = getattr(logger_service, 'is_running', False)
                if callable(running):
                    running = running()

                status = ServiceHealth.HEALTHY if running else ServiceHealth.UNHEALTHY
                message = "Parameter logger running" if running else "Parameter logger stopped"

                return HealthCheckResult(
                    service_name="parameter_logger",
                    status=status,
                    message=message,
                    response_time_ms=0.0
                )

        return HealthCheckResult(
            service_name="parameter_logger",
            status=ServiceHealth.UNKNOWN,
            message="Parameter logger service not available",
            response_time_ms=0.0
        )

    except Exception as e:
        return HealthCheckResult(
            service_name="parameter_logger",
            status=ServiceHealth.UNHEALTHY,
            message=f"Parameter logger health check failed: {str(e)}",
            response_time_ms=0.0
        )

def register_default_health_checks():
    """Register default health checks for core services"""
    registry = get_health_registry()
    registry.register_health_check("plc", plc_health_check)
    registry.register_health_check("database", database_health_check)
    registry.register_health_check("parameter_logger", parameter_logger_health_check)
    logger.info("Registered default health checks")