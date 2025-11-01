# Network Information & Configuration

## Current Network Setup

### Device Information
- **Pi Hostname:** pi
- **Pi User:** atomicoat
- **Mac Hostname:** albaraas-macbook-air
- **Mac User:** albaraamac
- **PLC IP:** 192.168.1.50 (static)
- **PLC Network:** 192.168.1.x

### IP Addresses

#### Tailscale Network (Private VPN)
- **Pi Tailscale IP:** 100.100.138.5
- **Mac Tailscale IP:** 100.106.50.78
- **Network Range:** 100.64.0.0/10 (Tailscale private network)

#### Local Network
- **Pi Local IP:** 10.5.5.100 (primary), 10.5.5.83 (secondary)
- **Mac Local IP:** 10.5.5.93
- **Network Range:** 10.5.5.0/24
- **Gateway:** 10.5.5.1

#### PLC Network
- **Pi PLC IP:** 192.168.1.7 (DHCP)
- **PLC IP:** 192.168.1.50 (static)
- **Network Range:** 192.168.1.0/24
- **Gateway:** 192.168.1.1

#### Public Internet
- **Public IP:** 78.188.81.153
- **ISP:** (Your internet service provider)

## Connection Methods

### Primary Access (Recommended)
```bash
# SSH via Tailscale (works from anywhere)
ssh pi-remote
# or
ssh atomicoat@100.100.138.5
```

### Local Network Access
```bash
# SSH via local network (when on same WiFi)
ssh pi
# or
ssh atomicoat@pi.local
# or
ssh atomicoat@10.5.5.100
```

### Direct IP Access
```bash
# SSH via direct IP (when on same network)
ssh atomicoat@10.5.5.100
```

## Network Topology

```
Internet (WiFi)
    │
    ├── Router (10.5.5.1) - Home Network
    │   ├── Mac (10.5.5.93)
    │   └── Pi (10.5.5.100)
    │
    ├── Tailscale VPN
    │   ├── Mac (100.106.50.78)
    │   └── Pi (100.100.138.5)
    │
    └── PLC Network (Ethernet Hub)
        ├── Router (192.168.1.1) - Turkcell Superbox
        ├── Pi (192.168.1.7)
        └── PLC (192.168.1.50) - Static IP
```

## Ports and Services

### SSH Service
- **Port:** 22
- **Protocol:** TCP
- **Authentication:** SSH key only (no passwords)
- **Status:** Enabled and running

### Tailscale Service
- **Port:** 41641 (UDP, outbound)
- **Protocol:** UDP + TCP/443 (DERP relays)
- **Authentication:** OAuth (Google account)
- **Status:** Enabled and running

### Backup Services
- **ngrok:** Available for emergency access
- **Local SSH:** Available when on same network

## Security Configuration

### SSH Security
- **Password authentication:** Disabled
- **Root login:** Disabled
- **Key authentication:** Required
- **Key type:** ED25519

### Tailscale Security
- **Encryption:** End-to-end encrypted
- **Authentication:** OAuth (Google)
- **Network:** Private (only your devices)
- **Traffic:** Direct peer-to-peer when possible

### Firewall Rules
- **SSH:** Port 22 (internal only)
- **Tailscale:** Port 41641 (outbound)
- **Internet:** All outbound allowed

## Network Diagnostics

### Check Tailscale Status
```bash
tailscale status
tailscale ping pi
tailscale ip -4
```

### Check Local Network
```bash
# On Mac
ifconfig | grep "inet "
# On Pi
ip addr show | grep "inet "
```

### Check Internet Connectivity
```bash
# On Pi
ping -c 3 8.8.8.8
curl -s ifconfig.me
```

### Check SSH Service
```bash
# On Pi
sudo systemctl status ssh
sudo netstat -tlnp | grep :22
```

## Connection Quality

### Direct Connection (Best)
- **Latency:** ~8-10ms
- **Speed:** Full bandwidth
- **Reliability:** High
- **Status:** When on same network

### DERP Relay (Fallback)
- **Latency:** ~120-140ms
- **Speed:** Limited by relay
- **Reliability:** High
- **Status:** When behind firewalls

## Mobile Access

### Tailscale Mobile App
1. Install Tailscale app on phone/tablet
2. Sign in with same Google account
3. Connect: `ssh atomicoat@100.100.138.5`

### SSH Apps for Mobile
- **iOS:** Termius, Prompt, Blink Shell
- **Android:** Termux, JuiceSSH, ConnectBot

## Backup Access Methods

### 1. ngrok Tunnel
```bash
# On Pi
ngrok tcp 22
# Use provided hostname:port
```

### 2. Local Network
```bash
# When on same WiFi
ssh pi
```

### 3. Physical Access
- Connect monitor/keyboard to Pi
- Use local console access

## Network Monitoring

### Check Connection Status
```bash
# Quick status check
ssh pi-remote 'echo "Pi Status: $(whoami)@$(hostname) - $(uptime)"'
```

### Monitor Tailscale
```bash
tailscale status
tailscale ping pi
```

### Check Services
```bash
ssh pi-remote 'sudo systemctl is-enabled ssh tailscaled'
```

---
*This network setup provides reliable, secure, and global access to your Raspberry Pi.*
