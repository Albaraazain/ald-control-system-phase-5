# Raspberry Pi Remote Access Setup Guide

## Overview
This guide documents the complete setup for accessing your Raspberry Pi from anywhere in the world using Tailscale VPN and SSH key authentication.

## Quick Access Commands
```bash
# Connect to Pi from anywhere
ssh pi-remote

# Or use direct Tailscale IP
ssh atomicoat@100.100.138.5

# Check Tailscale status
tailscale status
```

## What We Configured

### 1. SSH Key Authentication
- Generated ED25519 SSH key pair
- Copied public key to Pi for passwordless access
- Configured SSH config for easy connection

### 2. Tailscale VPN
- Installed Tailscale on both Mac and Pi
- Connected both devices to same private network
- Enabled auto-start on boot

### 3. Headless Operation
- Configured automatic login without password
- Set up passwordless sudo for essential commands
- Enabled all services to start automatically

### 4. Global Access
- Pi accessible from anywhere with internet
- Works through firewalls and NAT
- Auto-reconnects after reboot

### 5. PLC Communication
- Static IP communication with PLC
- Dual network setup (WiFi + Ethernet)
- Remote PLC programming and monitoring

## Network Information
- **Pi Tailscale IP:** 100.100.138.5
- **Mac Tailscale IP:** 100.106.50.78
- **Local Network:** 10.5.5.x
- **PLC Network:** 192.168.1.x
- **PLC IP:** 192.168.1.50
- **Pi PLC Network IP:** 192.168.1.7
- **Public IP:** 78.188.81.153

## Files Created/Modified
- `~/.ssh/id_ed25519` - Private SSH key
- `~/.ssh/id_ed25519.pub` - Public SSH key
- `~/.ssh/config` - SSH configuration
- `/etc/sudoers.d/atomicoat-nopasswd` - Passwordless sudo config
- `/etc/systemd/system/getty@tty1.service.d/autologin.conf` - Auto-login config

## Services Enabled
- `ssh.service` - SSH server
- `tailscaled.service` - Tailscale daemon
- `systemd-timesyncd.service` - Time synchronization

## Security Features
- SSH key authentication only (no passwords)
- Encrypted Tailscale connection
- Limited sudo access for essential commands
- Private network (only your devices can connect)

## Troubleshooting
If connection fails:
1. Check Tailscale status: `tailscale status`
2. Ping Pi: `tailscale ping pi`
3. Restart Tailscale: `sudo systemctl restart tailscaled`
4. Check SSH: `sudo systemctl status ssh`

## Access from Mobile
1. Install Tailscale app on phone/tablet
2. Sign in with same Google account
3. Use any SSH app to connect: `ssh atomicoat@100.100.138.5`

## Backup Access Methods
- **ngrok:** Installed as backup tunnel service
- **Local network:** `ssh pi` (when on same network)
- **Direct IP:** `ssh atomicoat@pi.local` (when on same network)

---
*Created: $(date)*
*Pi Hostname: pi*
*User: atomicoat*
