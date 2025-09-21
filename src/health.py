# File: src/health.py
"""
Health check endpoints and monitoring for ALD Control System.
Provides comprehensive health status for deployment monitoring.
"""
import asyncio
import time
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from src.log_setup import logger
from src.connection_monitor import connection_monitor
from src.plc.manager import plc_manager


@dataclass
class HealthStatus:
    """Health status data structure"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    uptime: float
    services: Dict[str, Any]
    metrics: Dict[str, Any]
    errors: list[str]


class HealthChecker:
    """Comprehensive health checker for the ALD control system"""

    def __init__(self):
        self.start_time = time.time()
        self.last_check = None
        self.health_cache = None
        self.cache_duration = 5.0  # Cache health status for 5 seconds

    async def get_health_status(self, force_refresh: bool = False) -> HealthStatus:
        """Get comprehensive health status"""
        current_time = time.time()

        # Use cached result if available and not expired
        if (not force_refresh and
            self.health_cache and
            self.last_check and
            current_time - self.last_check < self.cache_duration):
            return self.health_cache

        try:
            # Check all system components
            services = await self._check_services()
            metrics = await self._collect_metrics()
            errors = self._collect_errors(services)

            # Determine overall health status
            overall_status = self._determine_overall_status(services, errors)

            health_status = HealthStatus(
                status=overall_status,
                timestamp=current_time,
                uptime=current_time - self.start_time,
                services=services,
                metrics=metrics,
                errors=errors
            )

            # Cache the result
            self.health_cache = health_status
            self.last_check = current_time

            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return HealthStatus(
                status="unhealthy",
                timestamp=current_time,
                uptime=current_time - self.start_time,
                services={},
                metrics={},
                errors=[f"Health check failed: {str(e)}"]
            )

    async def _check_services(self) -> Dict[str, Any]:
        """Check status of all services"""
        services = {}

        # PLC Connection Status
        try:
            plc_status = connection_monitor.plc_status
            services["plc"] = {
                "status": "healthy" if plc_status.get("connected", False) else "unhealthy",
                "connected": plc_status.get("connected", False),
                "last_success": plc_status.get("last_success"),
                "last_error": plc_status.get("last_error"),
                "error_count": plc_status.get("error_count", 0)
            }
        except Exception as e:
            services["plc"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Database/Supabase Connection Status
        try:
            realtime_status = connection_monitor.realtime_status
            services["database"] = {
                "status": "healthy" if realtime_status.get("connected", False) else "degraded",
                "connected": realtime_status.get("connected", False),
                "using_polling": not realtime_status.get("connected", False),
                "last_success": realtime_status.get("last_success"),
                "last_error": realtime_status.get("last_error")
            }
        except Exception as e:
            services["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Data Collection Service Status
        try:
            from src.data_collection.service import data_collection_service
            dc_status = data_collection_service.get_status()
            services["data_collection"] = {
                "status": "healthy" if dc_status.get("service_running", False) else "unhealthy",
                "running": dc_status.get("service_running", False),
                "mode": dc_status.get("current_mode", "unknown"),
                "last_log_time": dc_status.get("last_log_time"),
                "error_count": dc_status.get("error_count", 0)
            }
        except Exception as e:
            services["data_collection"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Memory and Resource Status
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            services["resources"] = {
                "status": "healthy" if memory_info.rss < 500 * 1024 * 1024 else "degraded",  # 500MB limit
                "memory_mb": memory_info.rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "open_files": len(process.open_files())
            }
        except Exception as e:
            services["resources"] = {
                "status": "unknown",
                "error": str(e)
            }

        return services

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics"""
        metrics = {}

        try:
            # System uptime
            metrics["uptime_seconds"] = time.time() - self.start_time

            # Connection status counts
            plc_connected = connection_monitor.plc_status.get("connected", False)
            db_connected = connection_monitor.realtime_status.get("connected", False)

            metrics["connections"] = {
                "plc_connected": plc_connected,
                "database_connected": db_connected,
                "total_connections": sum([plc_connected, db_connected])
            }

            # Performance metrics (if available)
            try:
                from src.data_collection.service import data_collection_service
                dc_status = data_collection_service.get_status()
                metrics["data_collection"] = {
                    "last_log_time": dc_status.get("last_log_time"),
                    "error_count": dc_status.get("error_count", 0),
                    "mode": dc_status.get("current_mode", "unknown")
                }
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            metrics["error"] = str(e)

        return metrics

    def _collect_errors(self, services: Dict[str, Any]) -> list[str]:
        """Collect error messages from service checks"""
        errors = []

        for service_name, service_data in services.items():
            if service_data.get("status") == "unhealthy":
                if "error" in service_data:
                    errors.append(f"{service_name}: {service_data['error']}")
                else:
                    errors.append(f"{service_name}: Service unhealthy")
            elif service_data.get("status") == "degraded":
                errors.append(f"{service_name}: Service degraded")

        return errors

    def _determine_overall_status(self, services: Dict[str, Any], errors: list[str]) -> str:
        """Determine overall health status based on service states"""
        unhealthy_count = 0
        degraded_count = 0
        total_services = len(services)

        for service_data in services.values():
            status = service_data.get("status", "unknown")
            if status == "unhealthy":
                unhealthy_count += 1
            elif status == "degraded":
                degraded_count += 1

        # Determine overall status
        if unhealthy_count > 0:
            # Any unhealthy service makes the system unhealthy
            if unhealthy_count >= total_services * 0.5:  # More than 50% unhealthy
                return "unhealthy"
            else:
                return "degraded"
        elif degraded_count > 0:
            return "degraded"
        else:
            return "healthy"

    async def basic_health(self) -> Dict[str, Any]:
        """Quick basic health check for load balancer"""
        try:
            current_time = time.time()
            uptime = current_time - self.start_time

            # Quick checks
            plc_connected = connection_monitor.plc_status.get("connected", False)

            # Basic health criteria
            is_healthy = uptime > 5  # At least 5 seconds uptime

            return {
                "status": "ok" if is_healthy else "starting",
                "timestamp": current_time,
                "uptime": uptime,
                "plc_connected": plc_connected
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }


# Global health checker instance
health_checker = HealthChecker()


# Convenience functions for different health check types
async def get_health() -> Dict[str, Any]:
    """Get full health status as dictionary"""
    health_status = await health_checker.get_health_status()
    return asdict(health_status)


async def get_basic_health() -> Dict[str, Any]:
    """Get basic health status for load balancer"""
    return await health_checker.basic_health()


async def is_healthy() -> bool:
    """Simple boolean health check"""
    health_status = await health_checker.get_health_status()
    return health_status.status == "healthy"


# Health check server (optional - for standalone health endpoint)
async def start_health_server(port: int = 8000):
    """Start a simple health check server"""
    try:
        from aiohttp import web

        async def health_endpoint(request):
            health_data = await get_health()
            status_code = 200 if health_data["status"] == "healthy" else 503
            return web.json_response(health_data, status=status_code)

        async def basic_health_endpoint(request):
            health_data = await get_basic_health()
            status_code = 200 if health_data["status"] == "ok" else 503
            return web.json_response(health_data, status=status_code)

        app = web.Application()
        app.router.add_get("/health", health_endpoint)
        app.router.add_get("/health/basic", basic_health_endpoint)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        logger.info(f"Health check server started on port {port}")
        return runner

    except ImportError:
        logger.warning("aiohttp not available, health server not started")
        return None
    except Exception as e:
        logger.error(f"Failed to start health server: {str(e)}")
        return None