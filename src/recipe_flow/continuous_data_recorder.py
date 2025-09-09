# File: recipe_flow/continuous_data_recorder.py
"""
Provides continuous data recording functionality for recipe execution.
"""
import asyncio
import time
from typing import Optional
from src.log_setup import logger
from src.recipe_flow.data_recorder import record_process_data

class ContinuousDataRecorder:
    """Records process data at regular intervals during recipe execution."""
    
    def __init__(self, interval_seconds: float = 1.0):
        """
        Initialize the continuous recorder.
        
        Args:
            interval_seconds: Time between recordings in seconds
        """
        self.interval = interval_seconds
        self.is_running = False
        self.current_process_id = None
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, process_id: str):
        """
        Start continuous recording for a process.
        
        Args:
            process_id: The ID of the process execution
        """
        if self.is_running:
            await self.stop()
            
        self.current_process_id = process_id
        self.is_running = True
        self._task = asyncio.create_task(self._record_loop())
        logger.info(f"Started continuous data recording for process {process_id}")
    
    async def stop(self):
        """Stop the continuous recording."""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info(f"Stopped continuous data recording for process {self.current_process_id}")
        self.current_process_id = None
    
    async def _record_loop(self):
        """Internal loop that records data at the specified interval."""
        try:
            while self.is_running and self.current_process_id:
                start_time = time.time()
                
                # Record data points
                await record_process_data(self.current_process_id)
                
                # Calculate sleep time to maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            logger.info("Data recording loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in continuous data recording: {str(e)}", exc_info=True)
            self.is_running = False

# Global instance
continuous_recorder = ContinuousDataRecorder()