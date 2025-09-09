"""
Connection monitoring and health check module for ALD Control System.
Monitors PLC connection, Supabase realtime channels, and system health.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from src.log_setup import logger
from src.plc.manager import plc_manager
from src.db import get_supabase
from src.config import MACHINE_ID


class ConnectionMonitor:
    """Monitor and manage system connections."""
    
    def __init__(self):
        self.plc_status = {
            "connected": False,
            "last_check": None,
            "last_connected": None,
            "reconnect_attempts": 0,
            "error": None
        }
        self.realtime_status = {
            "connected": False,
            "last_check": None,
            "last_message": None,
            "error": None
        }
        self.health_check_interval = 30  # seconds
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10  # seconds
        
    async def start_monitoring(self):
        """Start the connection monitoring tasks."""
        logger.info("Starting connection monitor...")
        
        # Start monitoring tasks
        asyncio.create_task(self.monitor_plc_connection())
        asyncio.create_task(self.update_machine_health_status())
        
        logger.info("Connection monitor started")
    
    async def monitor_plc_connection(self):
        """Continuously monitor PLC connection and attempt reconnection if needed."""
        while True:
            try:
                # Check PLC connection status
                is_connected = plc_manager.is_connected()
                self.plc_status["last_check"] = datetime.utcnow()
                
                if is_connected:
                    if not self.plc_status["connected"]:
                        logger.info("✅ PLC connection established")
                        self.plc_status["connected"] = True
                        self.plc_status["last_connected"] = datetime.utcnow()
                        self.plc_status["reconnect_attempts"] = 0
                        self.plc_status["error"] = None
                else:
                    if self.plc_status["connected"]:
                        logger.warning("⚠️ PLC connection lost")
                        self.plc_status["connected"] = False
                    
                    # Attempt reconnection if not at max attempts
                    if self.plc_status["reconnect_attempts"] < self.max_reconnect_attempts:
                        logger.info(f"Attempting PLC reconnection (attempt {self.plc_status['reconnect_attempts'] + 1}/{self.max_reconnect_attempts})...")
                        
                        try:
                            success = await plc_manager.initialize()
                            if success:
                                logger.info("✅ PLC reconnection successful")
                                self.plc_status["connected"] = True
                                self.plc_status["last_connected"] = datetime.utcnow()
                                self.plc_status["reconnect_attempts"] = 0
                                self.plc_status["error"] = None
                            else:
                                self.plc_status["reconnect_attempts"] += 1
                                self.plc_status["error"] = "Reconnection failed"
                                await asyncio.sleep(self.reconnect_delay)
                        except Exception as e:
                            self.plc_status["reconnect_attempts"] += 1
                            self.plc_status["error"] = str(e)
                            logger.error(f"PLC reconnection error: {str(e)}")
                            await asyncio.sleep(self.reconnect_delay)
                    else:
                        # Max attempts reached, wait longer before resetting
                        if self.plc_status["reconnect_attempts"] >= self.max_reconnect_attempts:
                            logger.error(f"❌ Max PLC reconnection attempts reached ({self.max_reconnect_attempts})")
                            await asyncio.sleep(60)  # Wait 1 minute before resetting attempts
                            self.plc_status["reconnect_attempts"] = 0
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in PLC connection monitor: {str(e)}", exc_info=True)
                await asyncio.sleep(self.health_check_interval)
    
    async def update_machine_health_status(self):
        """Update machine health status in database."""
        while True:
            try:
                # Prepare health status data
                health_data = {
                    "machine_id": MACHINE_ID,
                    "plc_connected": self.plc_status["connected"],
                    "plc_last_check": self.plc_status["last_check"].isoformat() if self.plc_status["last_check"] else None,
                    "plc_last_connected": self.plc_status["last_connected"].isoformat() if self.plc_status["last_connected"] else None,
                    "plc_reconnect_attempts": self.plc_status["reconnect_attempts"],
                    "plc_error": self.plc_status["error"],
                    "realtime_connected": self.realtime_status["connected"],
                    "realtime_last_check": self.realtime_status["last_check"].isoformat() if self.realtime_status["last_check"] else None,
                    "realtime_last_message": self.realtime_status["last_message"].isoformat() if self.realtime_status["last_message"] else None,
                    "realtime_error": self.realtime_status["error"],
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Update machine health in database
                supabase = get_supabase()
                
                # First check if health record exists
                existing = supabase.table("machine_health").select("*").eq("machine_id", MACHINE_ID).execute()
                
                if existing.data and len(existing.data) > 0:
                    # Update existing record
                    result = (
                        supabase.table("machine_health")
                        .update(health_data)
                        .eq("machine_id", MACHINE_ID)
                        .execute()
                    )
                else:
                    # Insert new record
                    result = (
                        supabase.table("machine_health")
                        .insert(health_data)
                        .execute()
                    )
                
                if result.data:
                    logger.debug("Machine health status updated in database")
                
                # Wait before next update
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Error updating machine health status: {str(e)}", exc_info=True)
                await asyncio.sleep(60)
    
    def update_realtime_status(self, connected: bool, error: Optional[str] = None):
        """Update realtime connection status."""
        self.realtime_status["connected"] = connected
        self.realtime_status["last_check"] = datetime.utcnow()
        if connected:
            self.realtime_status["last_message"] = datetime.utcnow()
            self.realtime_status["error"] = None
        else:
            self.realtime_status["error"] = error
    
    def get_status(self) -> Dict[str, Any]:
        """Get current connection status."""
        return {
            "plc": self.plc_status.copy(),
            "realtime": self.realtime_status.copy(),
            "machine_id": MACHINE_ID,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def is_healthy(self) -> bool:
        """Check if all connections are healthy."""
        # PLC must be connected
        if not self.plc_status["connected"]:
            return False
        
        # PLC should have been checked recently (within 2 minutes)
        if self.plc_status["last_check"]:
            time_since_check = datetime.utcnow() - self.plc_status["last_check"]
            if time_since_check > timedelta(minutes=2):
                return False
        
        return True


# Global instance
connection_monitor = ConnectionMonitor()