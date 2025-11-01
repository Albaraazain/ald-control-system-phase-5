# PLC Static IP Configuration Guide

## Overview
This guide shows how to configure your Raspberry Pi with a static IP for PLC communication while maintaining internet access and remote connectivity.

## Network Architecture

### Current Setup
- **Internet Access:** Via WiFi/Ethernet (DHCP)
- **Remote Access:** Via Tailscale VPN
- **PLC Communication:** Needs static IP

### Target Configuration
- **Internet Access:** Maintained via WiFi/Ethernet
- **PLC Communication:** Static IP on dedicated interface
- **Remote Access:** Still available via Tailscale

## Configuration Options

### Option 1: Dual Network Interface (Recommended)
- **Primary Interface:** WiFi/Ethernet for internet
- **Secondary Interface:** Ethernet for PLC (static IP)

### Option 2: Single Interface with Static IP
- **Single Interface:** Ethernet with static IP
- **Internet Access:** Via PLC network or router

### Option 3: USB Ethernet Adapter
- **Built-in WiFi:** For internet access
- **USB Ethernet:** For PLC communication (static IP)

## Implementation Steps

### Step 1: Check Current Network Configuration
```bash
# Check network interfaces
ip addr show

# Check routing table
ip route show

# Check current IP configuration
cat /etc/dhcpcd.conf
```

### Step 2: Configure Static IP for PLC

#### Method A: Using dhcpcd.conf (Recommended)
```bash
# Edit dhcpcd configuration
sudo nano /etc/dhcpcd.conf

# Add static IP configuration
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

#### Method B: Using netplan (Ubuntu/Debian)
```bash
# Create netplan configuration
sudo nano /etc/netplan/01-netcfg.yaml

# Configuration example:
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

### Step 3: Configure Dual Network Setup

#### For WiFi + Ethernet Setup
```bash
# WiFi for internet (DHCP)
interface wlan0
# No static configuration - uses DHCP

# Ethernet for PLC (Static IP)
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

#### For USB Ethernet Adapter
```bash
# Built-in WiFi for internet
interface wlan0
# No static configuration - uses DHCP

# USB Ethernet for PLC
interface eth1
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

### Step 4: Apply Configuration
```bash
# Restart networking
sudo systemctl restart dhcpcd
# or
sudo netplan apply

# Check configuration
ip addr show
ip route show
```

### Step 5: Test Connectivity

#### Test Internet Access
```bash
# Test internet connectivity
ping -c 3 8.8.8.8
curl -s ifconfig.me
```

#### Test PLC Communication
```bash
# Test PLC connectivity
ping -c 3 192.168.1.1
ping -c 3 [PLC_IP_ADDRESS]
```

#### Test Remote Access
```bash
# Test Tailscale connectivity
tailscale status
tailscale ping pi
```

## Common PLC Network Configurations

### Siemens PLC Networks
- **IP Range:** 192.168.0.x or 192.168.1.x
- **Subnet:** 255.255.255.0
- **Gateway:** 192.168.1.1 or 192.168.0.1

### Allen-Bradley PLC Networks
- **IP Range:** 192.168.1.x
- **Subnet:** 255.255.255.0
- **Gateway:** 192.168.1.1

### Modbus TCP Networks
- **IP Range:** 192.168.1.x
- **Port:** 502 (Modbus TCP)
- **Subnet:** 255.255.255.0

## Example Configurations

### Example 1: Siemens S7-1200 Network
```bash
# /etc/dhcpcd.conf
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# Keep WiFi for internet
interface wlan0
# No static configuration - uses DHCP
```

### Example 2: Allen-Bradley CompactLogix Network
```bash
# /etc/dhcpcd.conf
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# Keep WiFi for internet
interface wlan0
# No static configuration - uses DHCP
```

### Example 3: USB Ethernet for PLC
```bash
# /etc/dhcpcd.conf
# Built-in WiFi for internet
interface wlan0
# No static configuration - uses DHCP

# USB Ethernet for PLC
interface eth1
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

## Troubleshooting

### Check Network Interfaces
```bash
# List all interfaces
ip addr show

# Check interface status
ip link show

# Check routing table
ip route show
```

### Test Connectivity
```bash
# Test internet
ping -c 3 8.8.8.8

# Test PLC network
ping -c 3 192.168.1.1

# Test specific PLC
ping -c 3 [PLC_IP]
```

### Check Configuration
```bash
# Check dhcpcd status
sudo systemctl status dhcpcd

# Check configuration
cat /etc/dhcpcd.conf

# Restart networking
sudo systemctl restart dhcpcd
```

## Security Considerations

### Network Isolation
- **PLC Network:** Isolated from internet
- **Internet Network:** Separate from PLC
- **Remote Access:** Via Tailscale VPN only

### Firewall Rules
```bash
# Allow PLC communication
sudo ufw allow from 192.168.1.0/24

# Allow Tailscale
sudo ufw allow from 100.64.0.0/10

# Block other access
sudo ufw default deny incoming
```

## Best Practices

### 1. Use Dedicated Interface for PLC
- **WiFi:** For internet access
- **Ethernet:** For PLC communication

### 2. Use USB Ethernet Adapter
- **Built-in WiFi:** For internet
- **USB Ethernet:** For PLC (static IP)

### 3. Network Segmentation
- **PLC Network:** 192.168.1.x
- **Internet Network:** 10.5.5.x (your current)
- **Remote Access:** 100.100.138.x (Tailscale)

### 4. Redundancy
- **Primary:** WiFi for internet
- **Backup:** Ethernet for internet (if WiFi fails)
- **PLC:** Dedicated Ethernet interface

## Testing Commands

### Network Status
```bash
# Check all interfaces
ip addr show

# Check routing
ip route show

# Check connectivity
ping -c 3 8.8.8.8
ping -c 3 192.168.1.1
```

### Service Status
```bash
# Check networking services
sudo systemctl status dhcpcd
sudo systemctl status networking

# Check Tailscale
sudo systemctl status tailscaled
tailscale status
```

---
*This configuration allows your Pi to communicate with PLCs while maintaining internet access and remote connectivity.*
