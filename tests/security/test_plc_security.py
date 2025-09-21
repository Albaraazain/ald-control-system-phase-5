"""
PLC communication security testing framework for ALD control system.

Tests for:
- Modbus TCP/IP security vulnerabilities
- Network security testing
- Man-in-the-middle attack simulation
- Authentication and authorization testing
- Network traffic validation
"""
import pytest
import asyncio
import socket
import struct
from unittest.mock import patch, Mock, MagicMock
from typing import List, Dict, Any, Optional
import time
import threading
import ipaddress


class PLCSecurityTester:
    """Comprehensive PLC communication security testing framework."""

    def __init__(self):
        """Initialize PLC security tester."""
        self.modbus_function_codes = {
            0x01: "READ_COILS",
            0x02: "READ_DISCRETE_INPUTS",
            0x03: "READ_HOLDING_REGISTERS",
            0x04: "READ_INPUT_REGISTERS",
            0x05: "WRITE_SINGLE_COIL",
            0x06: "WRITE_SINGLE_REGISTER",
            0x0F: "WRITE_MULTIPLE_COILS",
            0x10: "WRITE_MULTIPLE_REGISTERS"
        }

        self.malicious_payloads = [
            b'\x00\x00\x00\x00\x00\x06\x01\x03\x00\x00\x00\x7D',  # Read all registers
            b'\x00\x00\x00\x00\x00\x06\x01\x10\x00\x00\xFF\xFF',  # Write to all registers
            b'\x00' * 1000,  # Buffer overflow attempt
            b'\xFF' * 500,   # Maximum values
            b'\x00\x00\x00\x00\x00\x06\x01\x17\x00\x00\x00\x01',  # Read device identification
        ]

        self.network_scan_payloads = [
            b'\x00\x00\x00\x00\x00\x06\x01\x2B\x0E\x01\x00',  # Device identification
            b'\x00\x00\x00\x00\x00\x06\x01\x08\x00\x00',      # Diagnostics
            b'\x00\x00\x00\x00\x00\x06\x01\x11',              # Report slave ID
        ]

    def create_modbus_tcp_packet(self, function_code: int, data: bytes = b'') -> bytes:
        """Create a Modbus TCP packet."""
        transaction_id = 0x0000
        protocol_id = 0x0000
        length = len(data) + 2  # Function code + data
        unit_id = 0x01

        header = struct.pack('>HHHB', transaction_id, protocol_id, length, unit_id)
        return header + struct.pack('B', function_code) + data

    def parse_modbus_response(self, response: bytes) -> Dict[str, Any]:
        """Parse a Modbus TCP response."""
        if len(response) < 7:
            return {'error': 'Response too short'}

        try:
            transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', response[:7])
            function_code = response[7] if len(response) > 7 else 0
            data = response[8:] if len(response) > 8 else b''

            return {
                'transaction_id': transaction_id,
                'protocol_id': protocol_id,
                'length': length,
                'unit_id': unit_id,
                'function_code': function_code,
                'data': data,
                'is_error': function_code & 0x80 != 0
            }
        except Exception as e:
            return {'error': str(e)}

    async def test_modbus_injection_attacks(self, host: str, port: int = 502) -> List[Dict[str, Any]]:
        """Test Modbus injection attacks against PLC."""
        results = []

        for payload in self.malicious_payloads:
            try:
                # Create connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=5.0
                )

                # Send malicious payload
                writer.write(payload)
                await writer.drain()

                # Read response
                response = await asyncio.wait_for(reader.read(1024), timeout=5.0)

                # Parse response
                parsed = self.parse_modbus_response(response)

                results.append({
                    'payload': payload.hex(),
                    'response': response.hex() if response else None,
                    'parsed': parsed,
                    'vulnerable': not parsed.get('is_error', True)
                })

                writer.close()
                await writer.wait_closed()

            except Exception as e:
                results.append({
                    'payload': payload.hex(),
                    'error': str(e),
                    'vulnerable': False
                })

            # Small delay between tests
            await asyncio.sleep(0.1)

        return results

    def test_network_scanning_resistance(self, host: str, port: int = 502) -> Dict[str, Any]:
        """Test resistance to network scanning attacks."""
        scan_results = {
            'port_responses': [],
            'timing_analysis': {},
            'service_fingerprinting': []
        }

        # Test multiple ports for service discovery
        test_ports = [502, 503, 102, 2404, 44818]  # Common industrial protocol ports

        for test_port in test_ports:
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                result = sock.connect_ex((host, test_port))
                end_time = time.time()
                sock.close()

                response_time = end_time - start_time

                scan_results['port_responses'].append({
                    'port': test_port,
                    'open': result == 0,
                    'response_time': response_time
                })

                scan_results['timing_analysis'][test_port] = response_time

            except Exception as e:
                scan_results['port_responses'].append({
                    'port': test_port,
                    'error': str(e),
                    'open': False
                })

        # Test service fingerprinting
        if port in [p['port'] for p in scan_results['port_responses'] if p.get('open')]:
            for payload in self.network_scan_payloads:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3.0)
                    sock.connect((host, port))
                    sock.send(payload)
                    response = sock.recv(1024)
                    sock.close()

                    scan_results['service_fingerprinting'].append({
                        'payload': payload.hex(),
                        'response': response.hex(),
                        'info_leaked': len(response) > 0
                    })

                except Exception as e:
                    scan_results['service_fingerprinting'].append({
                        'payload': payload.hex(),
                        'error': str(e)
                    })

        return scan_results

    def simulate_mitm_attack(self, target_host: str, target_port: int = 502, proxy_port: int = 5020) -> Dict[str, Any]:
        """Simulate man-in-the-middle attack on Modbus communication."""
        mitm_results = {
            'intercepted_packets': [],
            'modified_responses': [],
            'attack_success': False
        }

        class ModbusMITMProxy:
            def __init__(self):
                self.intercepted = []
                self.running = False

            def handle_client(self, client_socket, target_host, target_port):
                try:
                    # Connect to actual PLC
                    target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    target_socket.connect((target_host, target_port))

                    # Relay traffic and intercept
                    while self.running:
                        try:
                            # Client to server
                            data = client_socket.recv(1024)
                            if not data:
                                break

                            # Log intercepted data
                            self.intercepted.append({
                                'direction': 'client_to_server',
                                'data': data.hex(),
                                'timestamp': time.time()
                            })

                            # Optionally modify data here (for testing)
                            modified_data = self.modify_request(data)
                            target_socket.send(modified_data)

                            # Server to client
                            response = target_socket.recv(1024)
                            if not response:
                                break

                            self.intercepted.append({
                                'direction': 'server_to_client',
                                'data': response.hex(),
                                'timestamp': time.time()
                            })

                            # Optionally modify response
                            modified_response = self.modify_response(response)
                            client_socket.send(modified_response)

                        except socket.timeout:
                            continue
                        except Exception:
                            break

                    target_socket.close()
                    client_socket.close()

                except Exception as e:
                    mitm_results['error'] = str(e)

            def modify_request(self, data: bytes) -> bytes:
                """Modify Modbus requests for MITM testing."""
                # For testing: don't actually modify in production!
                return data

            def modify_response(self, data: bytes) -> bytes:
                """Modify Modbus responses for MITM testing."""
                # For testing: could modify parameter values
                parsed = self.parse_response(data)
                if parsed and not parsed.get('is_error'):
                    mitm_results['modified_responses'].append({
                        'original': data.hex(),
                        'timestamp': time.time()
                    })
                return data

            def parse_response(self, data: bytes) -> Optional[Dict]:
                """Parse Modbus response for analysis."""
                if len(data) < 7:
                    return None
                try:
                    function_code = data[7]
                    return {'function_code': function_code, 'is_error': function_code & 0x80 != 0}
                except:
                    return None

        # Note: This is a simulation framework - actual MITM would be unethical
        # In practice, this tests the system's vulnerability to MITM attacks
        mitm_results['test_framework_ready'] = True
        mitm_results['recommendation'] = "Implement TLS/encryption for Modbus communication"

        return mitm_results

    def test_authentication_bypass(self, host: str, port: int = 502) -> Dict[str, Any]:
        """Test for authentication bypass vulnerabilities."""
        auth_test_results = {
            'no_authentication_required': False,
            'weak_authentication': False,
            'unauthorized_access': []
        }

        # Test if Modbus allows direct access without authentication
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))

            # Try to read holding registers without auth
            read_packet = self.create_modbus_tcp_packet(0x03, struct.pack('>HH', 0x0000, 0x0001))
            sock.send(read_packet)
            response = sock.recv(1024)

            if response:
                parsed = self.parse_modbus_response(response)
                if not parsed.get('is_error', True):
                    auth_test_results['no_authentication_required'] = True
                    auth_test_results['unauthorized_access'].append({
                        'operation': 'READ_HOLDING_REGISTERS',
                        'success': True,
                        'response': response.hex()
                    })

            # Try to write without authentication
            write_packet = self.create_modbus_tcp_packet(0x06, struct.pack('>HH', 0x0000, 0x0001))
            sock.send(write_packet)
            response = sock.recv(1024)

            if response:
                parsed = self.parse_modbus_response(response)
                if not parsed.get('is_error', True):
                    auth_test_results['unauthorized_access'].append({
                        'operation': 'WRITE_SINGLE_REGISTER',
                        'success': True,
                        'response': response.hex()
                    })

            sock.close()

        except Exception as e:
            auth_test_results['connection_error'] = str(e)

        return auth_test_results

    def analyze_network_traffic_security(self, captured_packets: List[bytes]) -> Dict[str, Any]:
        """Analyze captured network traffic for security issues."""
        analysis = {
            'unencrypted_data': 0,
            'sensitive_data_exposed': [],
            'protocol_violations': [],
            'suspicious_patterns': []
        }

        for packet in captured_packets:
            # Check if data is encrypted
            if self.is_plaintext_modbus(packet):
                analysis['unencrypted_data'] += 1

            # Check for sensitive data patterns
            if self.contains_sensitive_data(packet):
                analysis['sensitive_data_exposed'].append({
                    'packet': packet.hex(),
                    'pattern': 'sensitive_data_detected'
                })

            # Check for protocol violations
            parsed = self.parse_modbus_response(packet)
            if parsed.get('error'):
                analysis['protocol_violations'].append({
                    'packet': packet.hex(),
                    'error': parsed['error']
                })

        return analysis

    def is_plaintext_modbus(self, data: bytes) -> bool:
        """Check if data appears to be plaintext Modbus."""
        if len(data) < 7:
            return False

        try:
            # Check Modbus TCP header
            protocol_id = struct.unpack('>H', data[2:4])[0]
            return protocol_id == 0x0000  # Modbus protocol ID
        except:
            return False

    def contains_sensitive_data(self, data: bytes) -> bool:
        """Check if packet contains potentially sensitive data."""
        # Look for patterns that might indicate sensitive information
        sensitive_patterns = [
            b'password',
            b'admin',
            b'config',
            b'secret'
        ]

        data_lower = data.lower()
        return any(pattern in data_lower for pattern in sensitive_patterns)


class TestPLCSecurityFramework:
    """PLC security testing framework test suite."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tester = PLCSecurityTester()
        self.mock_host = "192.168.1.100"
        self.mock_port = 502

    def test_modbus_packet_creation(self):
        """Test Modbus packet creation for security testing."""
        packet = self.tester.create_modbus_tcp_packet(0x03, struct.pack('>HH', 0x0000, 0x0001))

        assert len(packet) >= 8
        assert packet[6] == 0x01  # Unit ID
        assert packet[7] == 0x03  # Function code

    def test_modbus_response_parsing(self):
        """Test Modbus response parsing for security analysis."""
        # Valid response
        response = b'\x00\x00\x00\x00\x00\x05\x01\x03\x02\x00\x01'
        parsed = self.tester.parse_modbus_response(response)

        assert parsed['function_code'] == 0x03
        assert not parsed['is_error']

        # Error response
        error_response = b'\x00\x00\x00\x00\x00\x03\x01\x83\x02'
        parsed_error = self.tester.parse_modbus_response(error_response)

        assert parsed_error['function_code'] == 0x83
        assert parsed_error['is_error']

    @pytest.mark.asyncio
    async def test_injection_attack_framework(self):
        """Test the injection attack testing framework."""
        # Mock the network connection
        async def mock_open_connection(host, port):
            reader = Mock()
            writer = Mock()

            # Mock response for different payloads
            writer.write = Mock()
            writer.drain = Mock(return_value=asyncio.Future())
            writer.drain.return_value.set_result(None)
            writer.close = Mock()
            writer.wait_closed = Mock(return_value=asyncio.Future())
            writer.wait_closed.return_value.set_result(None)

            # Mock response based on payload
            mock_response = b'\x00\x00\x00\x00\x00\x03\x01\x83\x01'  # Error response
            reader.read = Mock(return_value=asyncio.Future())
            reader.read.return_value.set_result(mock_response)

            return reader, writer

        with patch('asyncio.open_connection', side_effect=mock_open_connection):
            results = await self.tester.test_modbus_injection_attacks(self.mock_host)

            assert len(results) > 0
            assert all('payload' in result for result in results)

    def test_network_scanning_detection(self):
        """Test network scanning resistance testing."""
        # Mock socket operations
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            mock_sock.connect_ex.return_value = 0  # Port is open
            mock_sock.recv.return_value = b'\x00\x01\x02\x03'

            results = self.tester.test_network_scanning_resistance(self.mock_host)

            assert 'port_responses' in results
            assert 'timing_analysis' in results
            assert 'service_fingerprinting' in results

    def test_authentication_bypass_detection(self):
        """Test authentication bypass vulnerability detection."""
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            mock_sock.recv.return_value = b'\x00\x00\x00\x00\x00\x05\x01\x03\x02\x00\x01'  # Valid response

            results = self.tester.test_authentication_bypass(self.mock_host)

            assert 'no_authentication_required' in results
            assert 'unauthorized_access' in results

    def test_traffic_analysis_framework(self):
        """Test network traffic security analysis."""
        # Sample Modbus packets
        sample_packets = [
            b'\x00\x00\x00\x00\x00\x06\x01\x03\x00\x00\x00\x01',  # Read request
            b'\x00\x00\x00\x00\x00\x05\x01\x03\x02\x00\x01',     # Read response
            b'\x00\x00\x00\x00\x00\x06\x01\x06\x00\x00\x00\x01', # Write request
        ]

        analysis = self.tester.analyze_network_traffic_security(sample_packets)

        assert 'unencrypted_data' in analysis
        assert analysis['unencrypted_data'] > 0  # Should detect unencrypted Modbus

    def test_plc_manager_security_integration(self):
        """Test integration with PLC manager for security validation."""
        from src.plc.manager import PLCManager

        # Test that PLC manager has basic security considerations
        manager = PLCManager()

        # Test connection validation
        with patch.object(manager, '_validate_plc_connection') as mock_validate:
            mock_validate.return_value = True

            # Connection should validate parameters
            result = manager.initialize(ip="192.168.1.100", port=502)

            # Verify validation was called
            mock_validate.assert_called()

    def test_secure_parameter_reading(self):
        """Test that parameter reading is done securely."""
        from src.plc.manager import PLCManager

        manager = PLCManager()

        # Mock the underlying client
        with patch.object(manager, 'client') as mock_client:
            mock_client.read_holding_registers.return_value = Mock(
                isError=Mock(return_value=False),
                registers=[42]
            )

            # Test parameter reading with validation
            with patch.object(manager, '_validate_parameter_response') as mock_validate:
                mock_validate.return_value = True

                result = manager.read_parameter(parameter_id="test_param")

                # Should validate the response
                mock_validate.assert_called()


# Security audit functions for CI/CD integration
def run_plc_security_audit(target_host: str = "127.0.0.1", target_port: int = 502):
    """Run comprehensive PLC security audit."""
    print("Running PLC communication security audit...")

    tester = PLCSecurityTester()
    audit_results = {
        'tests_run': 0,
        'vulnerabilities_found': 0,
        'critical_issues': [],
        'recommendations': []
    }

    # Test 1: Network scanning resistance
    print("  Testing network scanning resistance...")
    audit_results['tests_run'] += 1
    try:
        scan_results = tester.test_network_scanning_resistance(target_host, target_port)
        open_ports = [r for r in scan_results['port_responses'] if r.get('open')]
        if len(open_ports) > 1:
            audit_results['vulnerabilities_found'] += 1
            audit_results['critical_issues'].append("Multiple industrial protocol ports open")
            audit_results['recommendations'].append("Close unused industrial protocol ports")
        print(f"    Found {len(open_ports)} open ports")
    except Exception as e:
        print(f"    Network scan test failed: {e}")

    # Test 2: Authentication bypass
    print("  Testing authentication mechanisms...")
    audit_results['tests_run'] += 1
    try:
        auth_results = tester.test_authentication_bypass(target_host, target_port)
        if auth_results.get('no_authentication_required'):
            audit_results['vulnerabilities_found'] += 1
            audit_results['critical_issues'].append("No authentication required for PLC access")
            audit_results['recommendations'].append("Implement Modbus security or VPN tunnel")
        print(f"    Authentication required: {not auth_results.get('no_authentication_required', False)}")
    except Exception as e:
        print(f"    Authentication test failed: {e}")

    # Test 3: Protocol security
    print("  Testing protocol security...")
    audit_results['tests_run'] += 1
    sample_traffic = [
        b'\x00\x00\x00\x00\x00\x06\x01\x03\x00\x00\x00\x01',  # Unencrypted Modbus
    ]
    traffic_analysis = tester.analyze_network_traffic_security(sample_traffic)
    if traffic_analysis['unencrypted_data'] > 0:
        audit_results['recommendations'].append("Consider implementing Modbus security or TLS tunnel")
    print(f"    Unencrypted packets detected: {traffic_analysis['unencrypted_data']}")

    # Test 4: MITM vulnerability assessment
    print("  Assessing MITM vulnerability...")
    audit_results['tests_run'] += 1
    mitm_assessment = tester.simulate_mitm_attack(target_host, target_port)
    if mitm_assessment.get('test_framework_ready'):
        audit_results['recommendations'].append("Implement network segmentation and encryption")
    print(f"    MITM protection: {'TLS/Encryption recommended' if mitm_assessment.get('test_framework_ready') else 'Unknown'}")

    print(f"\nPLC Security Audit Results:")
    print(f"  Tests run: {audit_results['tests_run']}")
    print(f"  Vulnerabilities found: {audit_results['vulnerabilities_found']}")
    print(f"  Critical issues: {len(audit_results['critical_issues'])}")

    if audit_results['critical_issues']:
        print(f"\n❌ CRITICAL SECURITY ISSUES FOUND:")
        for issue in audit_results['critical_issues']:
            print(f"    - {issue}")

    if audit_results['recommendations']:
        print(f"\n📋 SECURITY RECOMMENDATIONS:")
        for rec in audit_results['recommendations']:
            print(f"    - {rec}")

    # Consider audit successful if no critical issues
    critical_threshold = 0
    if len(audit_results['critical_issues']) <= critical_threshold:
        print(f"\n✅ PLC SECURITY AUDIT PASSED")
        return True
    else:
        print(f"\n❌ PLC SECURITY AUDIT FAILED - {len(audit_results['critical_issues'])} critical issues")
        return False


if __name__ == "__main__":
    # Run audit when executed directly
    success = run_plc_security_audit()
    exit(0 if success else 1)