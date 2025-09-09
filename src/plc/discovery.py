"""
PLC Discovery Module for DHCP-based connections.

This module provides automatic PLC discovery capabilities using:
1. Hostname resolution (mDNS/DNS)
2. Network scanning for Modbus devices
3. Cached IP resolution to avoid repeated scans
"""
import asyncio
import socket
import ipaddress
import concurrent.futures
from typing import Optional, List, Dict, Tuple
from pymodbus.client import ModbusTcpClient
from src.log_setup import logger
import json
import os
import time

class PLCDiscovery:
    """PLC Discovery service for finding PLCs on the network."""
    
    def __init__(self, cache_file: str = ".plc_cache.json", cache_ttl: int = 300):
        """
        Initialize PLC discovery service.
        
        Args:
            cache_file: Path to cache file for storing discovered PLCs
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.cache_file = cache_file
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached PLC discoveries."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self._cache = json.load(f)
                logger.debug(f"Loaded PLC discovery cache from {self.cache_file}")
        except Exception as e:
            logger.warning(f"Could not load PLC cache: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """Save PLC discoveries to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
            logger.debug(f"Saved PLC discovery cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Could not save PLC cache: {e}")
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid."""
        if 'timestamp' not in cache_entry:
            return False
        return (time.time() - cache_entry['timestamp']) < self.cache_ttl
    
    async def resolve_hostname(self, hostname: str, port: int = 502) -> Optional[str]:
        """
        Resolve hostname to IP address and test Modbus connectivity.
        
        Args:
            hostname: Hostname to resolve (e.g., 'plc.local', 'my-plc')
            port: Port to test (default: 502)
            
        Returns:
            IP address if resolved and Modbus-capable, None otherwise
        """
        cache_key = f"hostname:{hostname}:{port}"
        
        # Check cache first
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached_ip = self._cache[cache_key].get('ip')
            logger.info(f"Using cached IP for {hostname}: {cached_ip}")
            return cached_ip
        
        try:
            logger.info(f"Resolving hostname: {hostname}")
            
            # Resolve hostname to IP
            ip_address = socket.gethostbyname(hostname)
            logger.info(f"Hostname {hostname} resolved to {ip_address}")
            
            # Test Modbus connectivity
            if await self._test_modbus_connection(ip_address, port):
                # Cache the successful resolution
                self._cache[cache_key] = {
                    'ip': ip_address,
                    'timestamp': time.time(),
                    'method': 'hostname'
                }
                self._save_cache()
                return ip_address
            else:
                logger.warning(f"Host {ip_address} not responding to Modbus")
                return None
                
        except socket.gaierror as e:
            logger.warning(f"Could not resolve hostname {hostname}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error resolving hostname {hostname}: {e}")
            return None
    
    async def _test_modbus_connection(self, ip: str, port: int = 502, timeout: int = 3) -> bool:
        """
        Test if an IP address responds to Modbus requests.
        
        Args:
            ip: IP address to test
            port: Port to test
            timeout: Connection timeout in seconds
            
        Returns:
            True if Modbus-capable, False otherwise
        """
        try:
            def sync_test():
                client = ModbusTcpClient(ip, port=port, timeout=timeout)
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
            
            # Run the synchronous test in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, sync_test)
            return result
            
        except Exception as e:
            logger.debug(f"Modbus test failed for {ip}: {e}")
            return False
    
    async def scan_network(self, network: str = None, port: int = 502, max_workers: int = 20) -> List[str]:
        """
        Scan network for Modbus-capable devices.
        
        Args:
            network: Network to scan (e.g., '192.168.1.0/24'). If None, auto-detect
            port: Port to scan (default: 502)
            max_workers: Maximum concurrent connections
            
        Returns:
            List of IP addresses with Modbus capability
        """
        if network is None:
            network = self._get_local_network()
        
        cache_key = f"network:{network}:{port}"
        
        # Check cache first
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached_ips = self._cache[cache_key].get('devices', [])
            logger.info(f"Using cached network scan for {network}: {len(cached_ips)} devices")
            return cached_ips
        
        logger.info(f"Scanning network {network} for Modbus devices on port {port}")
        
        try:
            network_obj = ipaddress.IPv4Network(network, strict=False)
            discovered_ips = []
            
            # Create tasks for parallel scanning
            semaphore = asyncio.Semaphore(max_workers)
            
            async def test_ip(ip):
                async with semaphore:
                    if await self._test_modbus_connection(str(ip), port):
                        return str(ip)
                    return None
            
            # Test all IPs in the network
            tasks = [test_ip(ip) for ip in network_obj.hosts()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful connections
            for result in results:
                if result and not isinstance(result, Exception):
                    discovered_ips.append(result)
                    logger.info(f"Discovered Modbus device at {result}")
            
            # Cache the results
            self._cache[cache_key] = {
                'devices': discovered_ips,
                'timestamp': time.time(),
                'method': 'network_scan'
            }
            self._save_cache()
            
            logger.info(f"Network scan complete. Found {len(discovered_ips)} Modbus devices")
            return discovered_ips
            
        except Exception as e:
            logger.error(f"Error scanning network {network}: {e}")
            return []
    
    def _get_local_network(self) -> str:
        """
        Auto-detect the local network range.
        
        Returns:
            Network range in CIDR notation (e.g., '192.168.1.0/24')
        """
        try:
            # Get the default route interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Connect to external IP to find default interface
            local_ip = s.getsockname()[0]
            s.close()
            
            # Assume /24 subnet (most common for local networks)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            network_str = str(network.network_address) + "/" + str(network.prefixlen)
            
            logger.info(f"Auto-detected local network: {network_str}")
            return network_str
            
        except Exception as e:
            logger.warning(f"Could not auto-detect network, using default: {e}")
            return "192.168.1.0/24"  # Common default
    
    async def discover_plc(self, 
                          hostname: Optional[str] = None,
                          network: Optional[str] = None,
                          port: int = 502) -> Optional[str]:
        """
        Comprehensive PLC discovery using multiple methods.
        
        Args:
            hostname: Preferred hostname to try first
            network: Network to scan if hostname fails
            port: Port to use for connections
            
        Returns:
            IP address of discovered PLC, None if not found
        """
        logger.info("Starting PLC discovery process")
        
        # Method 1: Try hostname resolution first (fastest if it works)
        if hostname:
            logger.info(f"Attempting hostname resolution: {hostname}")
            ip = await self.resolve_hostname(hostname, port)
            if ip:
                logger.info(f"PLC discovered via hostname: {hostname} -> {ip}")
                return ip
        
        # Method 2: Network scanning (slower but comprehensive)
        logger.info("Hostname resolution failed or not provided, starting network scan")
        discovered_ips = await self.scan_network(network, port)
        
        if discovered_ips:
            # Return the first discovered IP
            selected_ip = discovered_ips[0]
            logger.info(f"PLC discovered via network scan: {selected_ip}")
            
            if len(discovered_ips) > 1:
                logger.info(f"Multiple PLCs found: {discovered_ips}. Using first one: {selected_ip}")
            
            return selected_ip
        
        logger.warning("No PLC devices discovered")
        return None
    
    def clear_cache(self):
        """Clear the discovery cache."""
        self._cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        logger.info("PLC discovery cache cleared")
    
    def get_cache_info(self) -> Dict:
        """Get information about cached discoveries."""
        info = {
            'entries': len(self._cache),
            'cache_file': self.cache_file,
            'cache_ttl': self.cache_ttl,
            'devices': []
        }
        
        for key, entry in self._cache.items():
            valid = self._is_cache_valid(entry)
            age = time.time() - entry.get('timestamp', 0)
            
            info['devices'].append({
                'key': key,
                'ip': entry.get('ip'),
                'method': entry.get('method'),
                'age_seconds': int(age),
                'valid': valid
            })
        
        return info


# Convenience functions for easy integration

async def find_plc_by_hostname(hostname: str, port: int = 502) -> Optional[str]:
    """
    Simple function to find PLC by hostname.
    
    Args:
        hostname: Hostname of the PLC
        port: Modbus port (default: 502)
        
    Returns:
        IP address if found, None otherwise
    """
    discovery = PLCDiscovery()
    return await discovery.resolve_hostname(hostname, port)

async def find_plc_on_network(network: str = None, port: int = 502) -> Optional[str]:
    """
    Simple function to find first PLC on network.
    
    Args:
        network: Network to scan (auto-detect if None)
        port: Modbus port (default: 502)
        
    Returns:
        First discovered IP address, None if not found
    """
    discovery = PLCDiscovery()
    discovered = await discovery.scan_network(network, port)
    return discovered[0] if discovered else None

async def auto_discover_plc(hostname: str = None, network: str = None, port: int = 502) -> Optional[str]:
    """
    Auto-discover PLC using hostname first, then network scan.
    
    Args:
        hostname: Optional hostname to try first
        network: Optional network to scan
        port: Modbus port (default: 502)
        
    Returns:
        Discovered IP address, None if not found
    """
    discovery = PLCDiscovery()
    return await discovery.discover_plc(hostname, network, port)