#!/usr/bin/env python3
"""
Modbus TCP Network Scanner for ALD Control System
Scans network to discover Modbus devices and slave IDs
"""

import asyncio
import socket
import time
from typing import List, Tuple, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException
import ipaddress
import argparse

class ModbusNetworkScanner:
    def __init__(self, timeout: float = 1.0, max_concurrent: int = 10):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.discovered_devices = []

    def get_local_network_range(self) -> str:
        """Get the local network range automatically"""
        try:
            # Get local IP by connecting to a remote address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            # Assume /24 network (common for local networks)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            return str(network.network_address)[:-1]  # Remove last digit
        except Exception:
            return "192.168.1."  # Default fallback

    async def test_tcp_connection(self, ip: str, port: int = 502) -> bool:
        """Test if TCP connection is possible to given IP:port"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    def test_modbus_slave(self, ip: str, slave_id: int, port: int = 502) -> bool:
        """Test if a specific slave ID responds on given IP"""
        try:
            client = ModbusTcpClient(ip, port=port, timeout=self.timeout)
            if not client.connect():
                return False

            # Try to read holding registers (common starting address)
            for addr in [0, 1, 40001, 30001]:  # Common Modbus addresses
                try:
                    result = client.read_holding_registers(addr, 1, slave=slave_id)
                    if not result.isError():
                        client.close()
                        return True
                except Exception:
                    continue

            # Try reading input registers
            try:
                result = client.read_input_registers(0, 1, slave=slave_id)
                if not result.isError():
                    client.close()
                    return True
            except Exception:
                pass

            # Try reading coils
            try:
                result = client.read_coils(0, 1, slave=slave_id)
                if not result.isError():
                    client.close()
                    return True
            except Exception:
                pass

            client.close()
            return False

        except Exception as e:
            return False

    def get_device_info(self, ip: str, slave_id: int, port: int = 502) -> dict:
        """Try to get device identification info"""
        info = {"ip": ip, "slave_id": slave_id, "port": port}

        try:
            client = ModbusTcpClient(ip, port=port, timeout=self.timeout)
            if not client.connect():
                return info

            # Try to read device identification (if supported)
            try:
                from pymodbus.mei_message import ReadDeviceInformationRequest
                request = ReadDeviceInformationRequest(slave=slave_id)
                result = client.execute(request)
                if hasattr(result, 'information') and result.information:
                    info['device_info'] = result.information
            except Exception:
                pass

            # Test different register types to understand capabilities
            capabilities = []

            # Test holding registers
            try:
                result = client.read_holding_registers(0, 1, slave=slave_id)
                if not result.isError():
                    capabilities.append("holding_registers")
            except Exception:
                pass

            # Test input registers
            try:
                result = client.read_input_registers(0, 1, slave=slave_id)
                if not result.isError():
                    capabilities.append("input_registers")
            except Exception:
                pass

            # Test coils
            try:
                result = client.read_coils(0, 1, slave=slave_id)
                if not result.isError():
                    capabilities.append("coils")
            except Exception:
                pass

            # Test discrete inputs
            try:
                result = client.read_discrete_inputs(0, 1, slave=slave_id)
                if not result.isError():
                    capabilities.append("discrete_inputs")
            except Exception:
                pass

            info['capabilities'] = capabilities
            client.close()

        except Exception as e:
            info['error'] = str(e)

        return info

    async def scan_ip_range(self, network_base: str, start_ip: int = 1, end_ip: int = 254) -> List[str]:
        """Scan IP range for devices responding on port 502"""
        print(f"Scanning IP range {network_base}{start_ip}-{end_ip} for Modbus TCP devices...")

        responsive_ips = []

        # Create semaphore to limit concurrent connections
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def test_ip(ip_suffix):
            async with semaphore:
                ip = f"{network_base}{ip_suffix}"
                if await self.test_tcp_connection(ip):
                    responsive_ips.append(ip)
                    print(f"  Found TCP response: {ip}")

        # Test all IPs concurrently
        tasks = [test_ip(i) for i in range(start_ip, end_ip + 1)]
        await asyncio.gather(*tasks)

        return responsive_ips

    def scan_slave_ids(self, ip: str, slave_range: range = range(1, 248)) -> List[int]:
        """Scan slave IDs on a specific IP"""
        print(f"Scanning slave IDs on {ip}...")

        responsive_slaves = []

        # Common slave IDs to check first (optimization)
        priority_slaves = [1, 2, 3, 8, 16, 17, 32, 64, 100, 127, 200, 240, 247]

        # Check priority slaves first
        for slave_id in priority_slaves:
            if slave_id in slave_range:
                if self.test_modbus_slave(ip, slave_id):
                    responsive_slaves.append(slave_id)
                    print(f"    Found slave: {ip}:{slave_id}")

        # Check remaining slaves
        remaining_slaves = [s for s in slave_range if s not in priority_slaves]
        for slave_id in remaining_slaves:
            if self.test_modbus_slave(ip, slave_id):
                responsive_slaves.append(slave_id)
                print(f"    Found slave: {ip}:{slave_id}")

        return responsive_slaves

    async def full_network_scan(self, network_base: Optional[str] = None,
                              ip_range: Tuple[int, int] = (1, 254),
                              slave_range: range = range(1, 248)) -> List[dict]:
        """Perform full network scan for Modbus devices"""

        if network_base is None:
            network_base = self.get_local_network_range()

        print(f"Starting Modbus network scan on {network_base}x")
        print(f"IP range: {ip_range[0]}-{ip_range[1]}")
        print(f"Slave range: {slave_range.start}-{slave_range.stop-1}")
        print("-" * 50)

        start_time = time.time()

        # Step 1: Find IPs responding on port 502
        responsive_ips = await self.scan_ip_range(network_base, ip_range[0], ip_range[1])

        if not responsive_ips:
            print("No devices found responding on port 502")
            return []

        print(f"\nFound {len(responsive_ips)} IP(s) responding on port 502")
        print("-" * 50)

        # Step 2: Scan slave IDs on each responsive IP
        all_devices = []

        for ip in responsive_ips:
            slaves = self.scan_slave_ids(ip, slave_range)

            for slave_id in slaves:
                device_info = self.get_device_info(ip, slave_id)
                all_devices.append(device_info)

        elapsed_time = time.time() - start_time

        print(f"\nScan completed in {elapsed_time:.2f} seconds")
        print(f"Found {len(all_devices)} Modbus device(s)")
        print("=" * 50)

        # Display results
        for i, device in enumerate(all_devices, 1):
            print(f"\nDevice {i}:")
            print(f"  IP: {device['ip']}")
            print(f"  Slave ID: {device['slave_id']}")
            print(f"  Port: {device['port']}")

            if 'capabilities' in device:
                print(f"  Capabilities: {', '.join(device['capabilities'])}")

            if 'device_info' in device:
                print(f"  Device Info: {device['device_info']}")

            if 'error' in device:
                print(f"  Error: {device['error']}")

        return all_devices

async def main():
    parser = argparse.ArgumentParser(description='Scan network for Modbus TCP devices')
    parser.add_argument('--network', help='Network base (e.g., 192.168.1.)', default=None)
    parser.add_argument('--ip-start', type=int, default=1, help='Start IP suffix')
    parser.add_argument('--ip-end', type=int, default=254, help='End IP suffix')
    parser.add_argument('--slave-start', type=int, default=1, help='Start slave ID')
    parser.add_argument('--slave-end', type=int, default=247, help='End slave ID')
    parser.add_argument('--timeout', type=float, default=1.0, help='Connection timeout')
    parser.add_argument('--concurrent', type=int, default=10, help='Max concurrent connections')

    args = parser.parse_args()

    scanner = ModbusNetworkScanner(timeout=args.timeout, max_concurrent=args.concurrent)

    devices = await scanner.full_network_scan(
        network_base=args.network,
        ip_range=(args.ip_start, args.ip_end),
        slave_range=range(args.slave_start, args.slave_end + 1)
    )

    if devices:
        print(f"\nDiscovered devices:")
        for device in devices:
            print(f"  {device['ip']}:{device['slave_id']}")
    else:
        print("\nNo Modbus devices found on the network.")

if __name__ == "__main__":
    asyncio.run(main())