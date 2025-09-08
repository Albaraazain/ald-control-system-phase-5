#!/usr/bin/env python3
"""
Standalone PLC Discovery Tool

This standalone script can discover PLCs on your network without needing 
the full ALD control system. Your friend can run this independently to:

1. Find PLCs by hostname (mDNS/DNS resolution)
2. Scan networks for Modbus-capable devices
3. Test connectivity to discovered PLCs
4. Generate connection reports

Usage:
    python3 plc_discovery_standalone.py
    python3 plc_discovery_standalone.py --hostname plc.local
    python3 plc_discovery_standalone.py --network 192.168.1.0/24
    python3 plc_discovery_standalone.py --scan-all
"""

import argparse
import asyncio
import socket
import ipaddress
import json
import sys
import time
from typing import Optional, List, Dict
import concurrent.futures

try:
    from pymodbus.client import ModbusTcpClient
    PYMODBUS_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: pymodbus not installed. Install with: pip install pymodbus")
    PYMODBUS_AVAILABLE = False


class StandalonePLCDiscovery:
    """Standalone PLC discovery tool."""
    
    def __init__(self, timeout: int = 3, max_workers: int = 20):
        """
        Initialize discovery tool.
        
        Args:
            timeout: Connection timeout in seconds
            max_workers: Maximum concurrent connections for scanning
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.discovered_devices = []
    
    async def resolve_hostname(self, hostname: str, port: int = 502) -> Optional[str]:
        """
        Resolve hostname to IP address and test Modbus connectivity.
        
        Args:
            hostname: Hostname to resolve (e.g., 'plc.local', 'my-plc')
            port: Port to test (default: 502)
            
        Returns:
            IP address if resolved and Modbus-capable, None otherwise
        """
        print(f"🔍 Resolving hostname: {hostname}")
        
        try:
            # Resolve hostname to IP
            ip_address = socket.gethostbyname(hostname)
            print(f"✅ Hostname {hostname} resolved to {ip_address}")
            
            # Test Modbus connectivity
            if await self._test_modbus_connection(ip_address, port):
                print(f"🎯 Modbus connectivity confirmed: {ip_address}:{port}")
                device_info = {
                    'ip': ip_address,
                    'hostname': hostname,
                    'port': port,
                    'method': 'hostname_resolution',
                    'timestamp': time.time()
                }
                self.discovered_devices.append(device_info)
                return ip_address
            else:
                print(f"❌ Host {ip_address} not responding to Modbus on port {port}")
                return None
                
        except socket.gaierror as e:
            print(f"❌ Could not resolve hostname {hostname}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error resolving hostname {hostname}: {e}")
            return None
    
    async def _test_modbus_connection(self, ip: str, port: int = 502) -> bool:
        """Test if an IP address responds to Modbus requests."""
        if not PYMODBUS_AVAILABLE:
            # Fallback to simple socket test
            return self._simple_socket_test(ip, port)
        
        try:
            def sync_test():
                client = ModbusTcpClient(ip, port=port, timeout=self.timeout)
                try:
                    if client.connect():
                        # Try a minimal read operation to confirm Modbus capability
                        result = client.read_holding_registers(0, 1, slave=1)
                        client.close()
                        # Even if read fails, connection success indicates Modbus capability
                        return True
                except:
                    pass
                finally:
                    try:
                        client.close()
                    except:
                        pass
                return False
            
            # Run the synchronous test in a thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, sync_test)
            return result
            
        except Exception:
            return False
    
    def _simple_socket_test(self, ip: str, port: int) -> bool:
        """Simple socket connectivity test when pymodbus is not available."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def scan_network(self, network: str = None, port: int = 502) -> List[str]:
        """
        Scan network for Modbus-capable devices.
        
        Args:
            network: Network to scan (e.g., '192.168.1.0/24'). If None, auto-detect
            port: Port to scan (default: 502)
            
        Returns:
            List of IP addresses with Modbus capability
        """
        if network is None:
            network = self._get_local_network()
        
        print(f"🌐 Scanning network {network} for Modbus devices on port {port}")
        print(f"⏱️  Using timeout: {self.timeout}s, Max workers: {self.max_workers}")
        
        try:
            network_obj = ipaddress.IPv4Network(network, strict=False)
            host_count = sum(1 for _ in network_obj.hosts())
            print(f"📊 Scanning {host_count} hosts...")
            
            discovered_ips = []
            
            # Create semaphore to limit concurrent connections
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def test_ip(ip):
                async with semaphore:
                    if await self._test_modbus_connection(str(ip), port):
                        device_info = {
                            'ip': str(ip),
                            'port': port,
                            'method': 'network_scan',
                            'timestamp': time.time()
                        }
                        self.discovered_devices.append(device_info)
                        return str(ip)
                    return None
            
            # Test all IPs in the network
            start_time = time.time()
            tasks = [test_ip(ip) for ip in network_obj.hosts()]
            
            # Show progress
            print("⏳ Scanning in progress...")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful connections
            for result in results:
                if result and not isinstance(result, Exception):
                    discovered_ips.append(result)
                    print(f"🎯 Discovered Modbus device at {result}")
            
            scan_time = time.time() - start_time
            print(f"✅ Network scan complete in {scan_time:.2f}s")
            print(f"📈 Found {len(discovered_ips)} Modbus devices out of {host_count} hosts")
            
            return discovered_ips
            
        except Exception as e:
            print(f"❌ Error scanning network {network}: {e}")
            return []
    
    def _get_local_network(self) -> str:
        """Auto-detect the local network range."""
        try:
            # Get the default route interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Assume /24 subnet (most common for local networks)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            network_str = str(network.network_address) + "/" + str(network.prefixlen)
            
            print(f"🔍 Auto-detected local network: {network_str}")
            return network_str
            
        except Exception as e:
            print(f"⚠️  Could not auto-detect network: {e}")
            return "192.168.1.0/24"  # Common default
    
    async def discover_all(self, hostname: str = None, network: str = None, port: int = 502):
        """Comprehensive discovery using all methods."""
        print("🚀 Starting comprehensive PLC discovery...")
        print("=" * 60)
        
        total_found = 0
        
        # Method 1: Hostname resolution
        if hostname:
            print(f"\n📍 STEP 1: Hostname Resolution")
            print("-" * 30)
            ip = await self.resolve_hostname(hostname, port)
            if ip:
                total_found += 1
        
        # Method 2: Network scanning
        print(f"\n📍 STEP 2: Network Scanning")
        print("-" * 30)
        discovered_ips = await self.scan_network(network, port)
        total_found += len(discovered_ips)
        
        # Summary
        print(f"\n📊 DISCOVERY SUMMARY")
        print("=" * 60)
        print(f"Total devices found: {total_found}")
        
        if self.discovered_devices:
            print("\n🎯 Discovered Devices:")
            for i, device in enumerate(self.discovered_devices, 1):
                hostname_str = f" ({device['hostname']})" if 'hostname' in device else ""
                print(f"  {i}. {device['ip']}:{device['port']}{hostname_str}")
                print(f"     Method: {device['method']}")
        else:
            print("❌ No Modbus devices found")
    
    def save_results(self, filename: str = "plc_discovery_results.json"):
        """Save discovery results to JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'discovery_timestamp': time.time(),
                    'discovery_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'total_devices': len(self.discovered_devices),
                    'devices': self.discovered_devices
                }, f, indent=2)
            print(f"💾 Results saved to {filename}")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    
    def generate_env_config(self):
        """Generate .env file suggestions based on discovered PLCs."""
        if not self.discovered_devices:
            print("❌ No devices found to generate config")
            return
        
        print(f"\n⚙️  CONFIGURATION SUGGESTIONS")
        print("=" * 60)
        
        # Use first discovered device as primary
        primary = self.discovered_devices[0]
        
        print(f"📝 Add these lines to your .env file:")
        print(f"PLC_IP={primary['ip']}")
        print(f"PLC_PORT={primary['port']}")
        
        # If hostname was used, suggest that too
        if 'hostname' in primary:
            print(f"PLC_HOSTNAME={primary['hostname']}")
            print(f"# You can use hostname instead of IP for DHCP environments")
        
        if len(self.discovered_devices) > 1:
            print(f"\n📋 Alternative devices found:")
            for device in self.discovered_devices[1:]:
                hostname_str = f" (hostname: {device['hostname']})" if 'hostname' in device else ""
                print(f"   - {device['ip']}:{device['port']}{hostname_str}")


def main():
    """Main entry point for standalone PLC discovery."""
    parser = argparse.ArgumentParser(
        description="Standalone PLC Discovery Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 plc_discovery_standalone.py                           # Auto-discover local network
  python3 plc_discovery_standalone.py --hostname plc.local      # Try hostname first
  python3 plc_discovery_standalone.py --network 10.5.5.0/24    # Scan specific network
  python3 plc_discovery_standalone.py --scan-all --port 1502   # Scan all with custom port
        """
    )
    
    parser.add_argument('--hostname', help='PLC hostname to resolve (e.g., plc.local)')
    parser.add_argument('--network', help='Network to scan (e.g., 192.168.1.0/24)')
    parser.add_argument('--port', type=int, default=502, help='Modbus port (default: 502)')
    parser.add_argument('--scan-all', action='store_true', help='Use comprehensive discovery')
    parser.add_argument('--timeout', type=int, default=3, help='Connection timeout (default: 3s)')
    parser.add_argument('--max-workers', type=int, default=20, help='Max concurrent connections (default: 20)')
    parser.add_argument('--save', help='Save results to JSON file')
    parser.add_argument('--generate-config', action='store_true', help='Generate .env configuration suggestions')
    
    args = parser.parse_args()
    
    # Header
    print("🤖 Standalone PLC Discovery Tool")
    print("=" * 60)
    
    if not PYMODBUS_AVAILABLE:
        print("⚠️  Note: pymodbus not available, using basic connectivity tests")
        print("   Install pymodbus for full Modbus protocol testing: pip install pymodbus")
        print()
    
    async def run_discovery():
        discovery = StandalonePLCDiscovery(
            timeout=args.timeout,
            max_workers=args.max_workers
        )
        
        if args.scan_all:
            # Comprehensive discovery
            await discovery.discover_all(
                hostname=args.hostname,
                network=args.network,
                port=args.port
            )
        elif args.hostname:
            # Hostname-only discovery
            await discovery.resolve_hostname(args.hostname, args.port)
        else:
            # Network scan only
            await discovery.scan_network(args.network, args.port)
        
        # Save results if requested
        if args.save:
            discovery.save_results(args.save)
        
        # Generate config if requested
        if args.generate_config:
            discovery.generate_env_config()
    
    try:
        asyncio.run(run_discovery())
    except KeyboardInterrupt:
        print("\n⏹️  Discovery interrupted by user")
    except Exception as e:
        print(f"❌ Error during discovery: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()