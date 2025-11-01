# Quick Reference Guide

## 🚀 Quick Access Commands

### Connect to Pi
```bash
# From anywhere in the world
ssh pi-remote

# Direct Tailscale IP
ssh atomicoat@100.100.138.5

# Local network (when on same WiFi)
ssh pi
```

### Check Status
```bash
# Tailscale status
tailscale status

# Ping Pi
tailscale ping pi

# Pi system info
ssh pi-remote 'whoami && hostname && uptime'
```

## 🔧 Essential Commands

### System Management
```bash
# Check services
ssh pi-remote 'sudo systemctl status ssh tailscaled'

# Restart services
ssh pi-remote 'sudo systemctl restart ssh'
ssh pi-remote 'sudo systemctl restart tailscaled'

# Reboot Pi
ssh pi-remote 'sudo reboot'

# Check disk space
ssh pi-remote 'df -h'
```

### PLC Communication
```bash
# Test PLC connectivity
ssh pi-remote 'ping -c 3 192.168.1.50'

# Test PLC ports
ssh pi-remote 'telnet 192.168.1.50 502'  # Modbus TCP
ssh pi-remote 'telnet 192.168.1.50 102'  # Siemens S7

# Check network interfaces
ssh pi-remote 'ip addr show'
```

### Network Diagnostics
```bash
# Check Pi's network
ssh pi-remote 'ip addr show | grep "inet "'

# Test internet
ssh pi-remote 'ping -c 3 8.8.8.8'

# Check Tailscale IP
ssh pi-remote 'tailscale ip -4'
```

### File Operations
```bash
# Create file
ssh pi-remote 'echo "Hello World" > /tmp/test.txt'

# Read file
ssh pi-remote 'cat /tmp/test.txt'

# List files
ssh pi-remote 'ls -la /tmp/'
```

## 📱 Mobile Access

### Setup Mobile Access
1. Install Tailscale app on phone/tablet
2. Sign in with same Google account
3. Install SSH app (Termius, Prompt, etc.)
4. Connect: `ssh atomicoat@100.100.138.5`

### Mobile SSH Apps
- **iOS:** Termius, Prompt, Blink Shell
- **Android:** Termux, JuiceSSH, ConnectBot

## 🛠️ Troubleshooting

### Connection Issues
```bash
# Check Tailscale
tailscale status
tailscale ping pi

# Restart Tailscale
ssh pi-remote 'sudo systemctl restart tailscaled'

# Check SSH
ssh pi-remote 'sudo systemctl status ssh'
```

### If Pi Not Responding
1. Wait 30-60 seconds (Pi might be booting)
2. Check Tailscale status: `tailscale status`
3. Try ping: `tailscale ping pi`
4. If still not working, Pi might need physical access

### Emergency Access
```bash
# Use local network (if on same WiFi)
ssh pi

# Use ngrok (if installed)
# On Pi: ngrok tcp 22
# Then use provided hostname:port
```

## 📊 System Information

### Pi Details
- **Hostname:** pi
- **User:** atomicoat
- **OS:** Raspberry Pi OS (Debian-based)
- **Architecture:** aarch64
- **Memory:** 8GB
- **Storage:** 32GB (13GB used, 15GB free)

### PLC Details
- **PLC IP:** 192.168.1.50 (static)
- **PLC Network:** 192.168.1.x
- **Pi PLC IP:** 192.168.1.7 (DHCP)
- **Communication:** Ethernet via hub

### Network Details
- **Pi Tailscale IP:** 100.100.138.5
- **Mac Tailscale IP:** 100.106.50.78
- **Local Network:** 10.5.5.x
- **PLC Network:** 192.168.1.x
- **PLC IP:** 192.168.1.50
- **Public IP:** 78.188.81.153

## 🔐 Security Features

### Authentication
- **SSH:** Key-based only (no passwords)
- **Tailscale:** OAuth (Google account)
- **Sudo:** Passwordless for essential commands

### Encryption
- **SSH:** Encrypted connection
- **Tailscale:** End-to-end encrypted
- **Traffic:** All data encrypted in transit

## 📁 Important Files

### SSH Configuration
- **Private Key:** `~/.ssh/id_ed25519`
- **Public Key:** `~/.ssh/id_ed25519.pub`
- **Config:** `~/.ssh/config`

### Pi Configuration
- **Sudoers:** `/etc/sudoers.d/atomicoat-nopasswd`
- **Auto-login:** `/etc/systemd/system/getty@tty1.service.d/autologin.conf`

## 🌍 Global Access

### How It Works
1. Pi connects to internet
2. Tailscale auto-connects
3. You can SSH from anywhere
4. Works through firewalls/NAT

### Network Scenarios That Work
- ✅ Home WiFi
- ✅ Mobile hotspot
- ✅ Hotel WiFi
- ✅ Coffee shop WiFi
- ✅ Different country
- ✅ Corporate networks (usually)

## 🚨 Emergency Procedures

### If Pi Won't Connect
1. **Wait:** Pi might be booting (up to 2 minutes)
2. **Check:** `tailscale status`
3. **Ping:** `tailscale ping pi`
4. **Restart:** `ssh pi-remote 'sudo systemctl restart tailscaled'`

### If SSH Fails
1. **Check service:** `ssh pi-remote 'sudo systemctl status ssh'`
2. **Restart SSH:** `ssh pi-remote 'sudo systemctl restart ssh'`
3. **Check keys:** `ssh pi-remote 'ls -la ~/.ssh/authorized_keys'`

### Complete Reset (Last Resort)
1. **Reset Tailscale:** `ssh pi-remote 'sudo tailscale logout && sudo tailscale up'`
2. **Reset SSH keys:** Regenerate and copy keys
3. **Factory reset:** Reinstall everything

---
*Keep this guide handy for quick reference and troubleshooting.*
