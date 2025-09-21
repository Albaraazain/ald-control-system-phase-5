# File: data_collection/service.py
"""
Data collection service integration for the main application with transactional data integrity.
"""
import asyncio
from src.log_setup import logger
from src.data_collection.transactional_adapter import transactional_parameter_logger_adapter


class DataCollectionService:
    """Service to manage all data collection components."""

    def __init__(self):
        """Initialize the data collection service."""
        self.is_running = False

    async def start(self):
        """Start all data collection services."""
        if self.is_running:
            logger.warning("Data collection service is already running")
            return

        try:
            # Start transactional parameter logger with atomic guarantees
            await transactional_parameter_logger_adapter.start()
            self.is_running = True
            logger.info("Data collection service started successfully with transactional integrity")

        except Exception as e:
            logger.error(f"Error starting data collection service: {str(e)}", exc_info=True)
            await self.stop()  # Cleanup on failure
            raise

    async def stop(self):
        """Stop all data collection services."""
        if not self.is_running:
            return

        try:
            # Stop transactional parameter logger
            await transactional_parameter_logger_adapter.stop()
            self.is_running = False
            logger.info("Data collection service stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping data collection service: {str(e)}", exc_info=True)

    def get_status(self):
        """Get status of all data collection services."""
        return {
            'service_running': self.is_running,
            'transactional_parameter_logger': transactional_parameter_logger_adapter.get_status()
        }

    async def get_health_status(self):
        """Get comprehensive health status including transactional layer."""
        try:
            if self.is_running:
                health = await transactional_parameter_logger_adapter.get_health_status()
                health['service_running'] = True
                return health
            else:
                return {
                    'service_running': False,
                    'overall_status': 'stopped'
                }
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                'service_running': self.is_running,
                'overall_status': 'unhealthy',
                'error': str(e)
            }

    async def test_atomic_operation(self):
        """Test atomic operation capability."""
        if self.is_running:
            return await transactional_parameter_logger_adapter.test_atomic_operation()
        else:
            return {
                'test_successful': False,
                'error': 'Service not running'
            }


# Global instance
data_collection_service = DataCollectionService()