#!/usr/bin/env python3
"""
Test script for DHCP-based PLC connections.

This script demonstrates how to use the new DHCP discovery features
in your ALD control system.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import your PLC modules
from plc.factory import PLCFactory
from plc.discovery import auto_discover_plc, find_plc_by_hostname
from log_setup import logger

async def test_hostname_connection():
    """Test connecting to PLC via hostname."""
    print("🔍 Testing hostname-based connection...")
    
    # Try common PLC hostnames
    hostnames_to_try = [
        'plc.local',
        'plc-controller.local', 
        'modbus-plc.local',
        'ald-plc.local'
    ]
    
    for hostname in hostnames_to_try:
        print(f"   Trying hostname: {hostname}")
        ip = await find_plc_by_hostname(hostname)
        if ip:
            print(f"   ✅ Found PLC at {hostname} -> {ip}")
            return hostname, ip
        else:
            print(f"   ❌ No response from {hostname}")
    
    print("   ⚠️  No PLCs found via hostname")
    return None, None

async def test_auto_discovery():
    """Test automatic PLC discovery."""
    print("🌐 Testing automatic PLC discovery...")
    
    discovered_ip = await auto_discover_plc()
    if discovered_ip:
        print(f"   ✅ Auto-discovered PLC at {discovered_ip}")
        return discovered_ip
    else:
        print("   ❌ No PLCs found via auto-discovery")
        return None

async def test_plc_factory_with_dhcp():
    """Test PLC factory with DHCP configuration."""
    print("🏭 Testing PLC factory with DHCP config...")
    
    # Configuration with DHCP support
    dhcp_config = {
        'ip_address': os.getenv('PLC_IP', '10.5.5.80'),  # Fallback IP
        'port': int(os.getenv('PLC_PORT', '502')),
        'hostname': 'plc.local',  # Try hostname first
        'auto_discover': True     # Enable auto-discovery
    }
    
    try:
        plc = await PLCFactory.create_plc('real', dhcp_config)
        print("   ✅ PLC factory successfully created connection with DHCP support")
        
        # Test basic functionality
        print("   🔧 Testing basic PLC operations...")
        
        # Try reading all parameters
        params = await plc.read_all_parameters()
        print(f"   📊 Read {len(params)} parameters from PLC")
        
        await plc.disconnect()
        print("   ✅ PLC disconnected successfully")
        
        return True
        
    except Exception as e:
        print(f"   ❌ PLC factory test failed: {e}")
        return False

async def demonstrate_dhcp_config_options():
    """Demonstrate different DHCP configuration options."""
    print("⚙️  DHCP Configuration Examples:")
    print("=" * 50)
    
    configs = [
        {
            'name': 'Hostname Only',
            'config': {
                'hostname': 'plc.local',
                'port': 502
            },
            'description': 'Connects via hostname resolution (fastest if PLC has mDNS)'
        },
        {
            'name': 'Auto-Discovery Only', 
            'config': {
                'auto_discover': True,
                'port': 502
            },
            'description': 'Scans network for Modbus devices (works with any IP)'
        },
        {
            'name': 'Hybrid (Recommended)',
            'config': {
                'ip_address': '10.5.5.80',    # Static fallback
                'hostname': 'plc.local',      # Try hostname first
                'auto_discover': True,        # Auto-discover if hostname fails
                'port': 502
            },
            'description': 'Best of all worlds: hostname -> discovery -> static IP'
        }
    ]
    
    for i, option in enumerate(configs, 1):
        print(f"\n{i}. {option['name']}:")
        print(f"   Description: {option['description']}")
        print(f"   Config: {option['config']}")
    
    print(f"\n💡 To use any of these, update your .env file:")
    print(f"   PLC_HOSTNAME=plc.local")
    print(f"   PLC_AUTO_DISCOVER=true")

async def main():
    """Main test function."""
    print("🤖 ALD Control System - DHCP PLC Connection Test")
    print("=" * 60)
    
    # Test 1: Hostname resolution
    hostname, hostname_ip = await test_hostname_connection()
    
    # Test 2: Auto-discovery
    discovered_ip = await test_auto_discovery()
    
    # Test 3: PLC Factory integration
    factory_success = await test_plc_factory_with_dhcp()
    
    # Test 4: Configuration examples
    await demonstrate_dhcp_config_options()
    
    # Summary
    print(f"\n📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Hostname resolution: {'✅ Success' if hostname else '❌ Failed'}")
    print(f"Auto-discovery:      {'✅ Success' if discovered_ip else '❌ Failed'}")
    print(f"PLC Factory test:    {'✅ Success' if factory_success else '❌ Failed'}")
    
    if hostname_ip or discovered_ip:
        print(f"\n🎯 RECOMMENDED CONFIGURATION:")
        print(f"Add to your .env file:")
        if hostname:
            print(f"PLC_HOSTNAME={hostname}")
        if discovered_ip:
            print(f"# Discovered IP: {discovered_ip}")
            print(f"PLC_IP={discovered_ip}")
        print(f"PLC_AUTO_DISCOVER=true")
        
        print(f"\n💡 Your PLC should now work with DHCP!")
    else:
        print(f"\n⚠️  No PLCs found. Check:")
        print(f"   - PLC is powered on and connected to network")
        print(f"   - Raspberry Pi is on same network as PLC") 
        print(f"   - Firewall allows Modbus TCP (port 502)")
        print(f"   - PLC has Modbus TCP enabled")

if __name__ == "__main__":
    asyncio.run(main())