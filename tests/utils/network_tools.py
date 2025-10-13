"""
Network Tools for Failure Injection Testing

Platform-specific network manipulation utilities for testing under adverse conditions.

**Platform Support:**
- Linux: tc/netem (Traffic Control with Network Emulator) - full support
- macOS: Software fallback (pfctl too complex for automated testing)
- Windows: Software fallback only

Author: Phase 1 Agent 3 - Failure Injection Framework
Date: 2025-10-10
"""

import subprocess
import platform
import os
from typing import Optional, Dict, Any


def get_platform_info() -> Dict[str, Any]:
    """Get detailed platform information for network tools."""
    system = platform.system().lower()

    info = {
        'system': system,
        'normalized': 'linux' if system == 'linux' else ('macos' if system == 'darwin' else 'windows'),
        'release': platform.release(),
        'has_tc': False,
        'has_pfctl': False,
        'has_iptables': False,
        'is_root': False
    }

    # Check for root privileges
    try:
        info['is_root'] = os.geteuid() == 0
    except AttributeError:
        # Windows
        try:
            import ctypes
            info['is_root'] = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            info['is_root'] = False

    # Check for available tools
    if system == 'linux':
        info['has_tc'] = check_command_exists('tc')
        info['has_iptables'] = check_command_exists('iptables')
    elif system == 'darwin':
        info['has_pfctl'] = check_command_exists('pfctl')

    return info


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        result = subprocess.run(
            ['which', command],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except:
        return False


def apply_linux_tc_delay(
    interface: str,
    delay_ms: int,
    jitter_ms: int = 0,
    loss_percent: float = 0.0
) -> bool:
    """
    Apply traffic control delay on Linux using tc/netem.

    Args:
        interface: Network interface (e.g., 'lo', 'eth0')
        delay_ms: Base delay in milliseconds
        jitter_ms: Jitter/variance in milliseconds
        loss_percent: Packet loss percentage (0.0-100.0)

    Returns:
        True if successfully applied

    Requires:
        - Root privileges
        - tc command (iproute2 package)
    """
    if not check_command_exists('tc'):
        print("❌ 'tc' command not found - install iproute2")
        return False

    try:
        # Clear existing rules
        subprocess.run(
            ['tc', 'qdisc', 'del', 'dev', interface, 'root'],
            capture_output=True,
            stderr=subprocess.DEVNULL
        )

        # Build tc netem command
        cmd = ['tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem']

        if delay_ms > 0:
            cmd.extend(['delay', f'{delay_ms}ms'])
            if jitter_ms > 0:
                cmd.append(f'{jitter_ms}ms')

        if loss_percent > 0:
            cmd.extend(['loss', f'{loss_percent}%'])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Applied tc delay: {delay_ms}ms ±{jitter_ms}ms, {loss_percent}% loss on {interface}")
            return True
        else:
            print(f"❌ Failed to apply tc: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error applying tc: {e}")
        return False


def clear_linux_tc(interface: str) -> bool:
    """
    Clear traffic control rules on Linux.

    Args:
        interface: Network interface to clear

    Returns:
        True if successfully cleared
    """
    try:
        subprocess.run(
            ['tc', 'qdisc', 'del', 'dev', interface, 'root'],
            capture_output=True,
            stderr=subprocess.DEVNULL
        )
        print(f"✅ Cleared tc rules on {interface}")
        return True
    except Exception as e:
        print(f"⚠️  Error clearing tc: {e}")
        return False


def apply_linux_iptables_block(hostname: str) -> bool:
    """
    Block traffic to a hostname using iptables (Linux).

    Args:
        hostname: Hostname to block (e.g., 'xyz.supabase.co')

    Returns:
        True if successfully blocked

    Requires:
        - Root privileges
        - iptables command

    Note: This is a DESTRUCTIVE operation - use only in test environments!
    """
    if not check_command_exists('iptables'):
        print("❌ 'iptables' command not found")
        return False

    try:
        # Block OUTPUT chain (outgoing connections)
        cmd = ['iptables', '-A', 'OUTPUT', '-d', hostname, '-j', 'DROP']
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Blocked traffic to {hostname}")
            return True
        else:
            print(f"❌ Failed to block: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error blocking traffic: {e}")
        return False


def clear_linux_iptables_block(hostname: str) -> bool:
    """
    Unblock traffic to a hostname using iptables (Linux).

    Args:
        hostname: Hostname to unblock

    Returns:
        True if successfully unblocked
    """
    try:
        # Remove DROP rule
        cmd = ['iptables', '-D', 'OUTPUT', '-d', hostname, '-j', 'DROP']
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Unblocked traffic to {hostname}")
            return True
        else:
            # Rule might not exist - not an error
            return True

    except Exception as e:
        print(f"⚠️  Error unblocking traffic: {e}")
        return False


def get_recommended_interface() -> str:
    """
    Get recommended network interface for testing.

    Returns:
        'lo' for localhost testing (safest option)
    """
    # For testing, we primarily use localhost (lo/lo0)
    # This prevents accidentally affecting external network
    return 'lo'


def print_network_capabilities():
    """Print available network manipulation capabilities."""
    info = get_platform_info()

    print("🔧 Network Testing Capabilities:")
    print(f"   Platform: {info['system']} ({info['release']})")
    print(f"   Root privileges: {'✅ Yes' if info['is_root'] else '❌ No'}")

    if info['normalized'] == 'linux':
        print(f"   tc (Traffic Control): {'✅ Available' if info['has_tc'] else '❌ Not found'}")
        print(f"   iptables: {'✅ Available' if info['has_iptables'] else '❌ Not found'}")

        if info['has_tc'] and info['is_root']:
            print("   ✅ Full network latency injection supported")
        elif info['has_tc']:
            print("   ⚠️  tc available but requires root (sudo)")
        else:
            print("   ❌ Install iproute2 package for tc support")

    elif info['normalized'] == 'macos':
        print(f"   pfctl: {'✅ Available' if info['has_pfctl'] else '❌ Not found'}")
        print("   ⚠️  macOS network injection requires complex pfctl rules")
        print("   💡 Recommend: Use software delays or run tests on Linux")

    else:  # Windows
        print("   ❌ Windows network injection not supported")
        print("   💡 Use software delays or run tests on Linux")


# Example usage
if __name__ == '__main__':
    print_network_capabilities()

    info = get_platform_info()
    if info['normalized'] == 'linux' and info['is_root']:
        print("\n🧪 Testing network latency injection...")

        # Apply 100ms delay
        if apply_linux_tc_delay('lo', delay_ms=100, jitter_ms=10):
            print("✅ Applied 100ms ±10ms delay to localhost")
            input("Press Enter to clear...")
            clear_linux_tc('lo')
    else:
        print("\n⚠️  Root privileges on Linux required for testing")
