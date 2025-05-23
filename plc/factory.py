# File: plc/factory.py
"""
Factory for creating PLC interface instances.
"""
from typing import Dict, Any, Optional
from log_setup import logger
from plc.interface import PLCInterface
from plc.simulation import SimulationPLC
from plc.real_plc import RealPLC

class PLCFactory:
    """Factory for creating PLC interface instances."""
    
    @staticmethod
    async def create_plc(plc_type: str, config: Optional[Dict[str, Any]] = None) -> PLCInterface:
        """
        Create a PLC interface instance based on the specified type.
        
        Args:
            plc_type: Type of PLC ('simulation' or 'real')
            config: Configuration options for the PLC
            
        Returns:
            PLCInterface: An initialized PLC interface
            
        Raises:
            ValueError: If the PLC type is invalid
        """
        config = config or {}
        
        if plc_type.lower() == 'simulation':
            logger.info("Creating simulation PLC")
            plc = SimulationPLC()
            
        elif plc_type.lower() == 'real':
            logger.info("Creating real PLC connection")
            # Extract connection parameters from config
            ip_address = config.get('ip_address', '127.0.0.1')
            port = config.get('port', 502)  # Default Modbus port
            
            plc = RealPLC(ip_address, port)
            
        else:
            raise ValueError(f"Invalid PLC type: {plc_type}. Must be 'simulation' or 'real'")
        
        # Initialize the PLC connection
        success = await plc.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize {plc_type} PLC")
            
        return plc