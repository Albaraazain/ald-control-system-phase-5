"""
Ultra-simple script to turn on a valve - everything hardcoded.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plc.manager import plc_manager

async def turn_on_valve():
    # HARDCODED VALUES - CHANGE THESE
    VALVE_NUMBER = 1
    MODBUS_ADDRESS = 10  # Change this to your valve's address
    
    # Connect to PLC
    await plc_manager.initialize()
    plc = plc_manager.plc
    
    # Turn valve ON
    plc.communicator.write_coil(MODBUS_ADDRESS, True)
    print(f"Valve {VALVE_NUMBER} at address {MODBUS_ADDRESS} turned ON")
    
    # Disconnect
    await plc_manager.disconnect()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(turn_on_valve())