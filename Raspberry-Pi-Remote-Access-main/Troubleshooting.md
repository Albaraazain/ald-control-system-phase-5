# Troubleshooting Guide

## Common Issues and Solutions

### 1. Cannot Connect to Pi

#### Check Tailscale Status
```bash
tailscale status
```
**Expected Output:**
```
100.106.50.78   albaraas-macbook-air albaraazain11@ macOS   -
100.100.138.5   pi                   albaraazain11@ linux   -
```

#### If Pi Not Showing:
```bash
# On Pi
sudo systemctl status tailscaled
sudo systemctl restart tailscaled
sudo tailscale up
```

#### Test Tailscale Connectivity
```bash
tailscale ping pi
```
**Expected:** `pong from pi (100.100.138.5) via [connection] in [time]ms`

### 2. SSH Connection Refused

#### Check SSH Service
```bash
ssh pi-remote 'sudo systemctl status ssh'
```

#### Restart SSH if Needed
```bash
ssh pi-remote 'sudo systemctl restart ssh'
```

#### Check SSH Config
```bash
cat ~/.ssh/config
```

### 3. Password Prompts for Sudo

#### Check Sudoers File
```bash
ssh pi-remote 'sudo visudo -c'
```

#### Verify Passwordless Config
```bash
ssh pi-remote 'cat /etc/sudoers.d/atomicoat-nopasswd'
```

### 4. Pi Not Auto-Connecting After Reboot

#### Check Service Status
```bash
ssh pi-remote 'sudo systemctl is-enabled ssh tailscaled'
```

#### Check Auto-Login Config
```bash
ssh pi-remote 'cat /etc/systemd/system/getty@tty1.service.d/autologin.conf'
```

#### Restart Services
```bash
ssh pi-remote 'sudo systemctl daemon-reload'
ssh pi-remote 'sudo systemctl restart getty@tty1'
```

### 5. Network Connectivity Issues

#### Check Pi's Network
```bash
ssh pi-remote 'ping -c 3 8.8.8.8'
```

#### Check Tailscale IP
```bash
ssh pi-remote 'tailscale ip -4'
```

#### Check Local Network
```bash
ssh pi-remote 'ip addr show | grep -E "inet " | grep -v "127.0.0.1"'
```

### 6. Mobile Access Issues

#### Install Tailscale App
1. Download Tailscale from App Store/Play Store
2. Sign in with same Google account
3. Connect to Pi: `ssh atomicoat@100.100.138.5`

#### Check Mobile Tailscale Status
- Open Tailscale app
- Verify Pi appears in device list
- Check connection status

### 7. Backup Access Methods

#### Use ngrok (if Tailscale fails)
```bash
# On Pi
ngrok authtoken YOUR_TOKEN
ngrok tcp 22
# Use the provided hostname:port
```

#### Use Local Network (if on same WiFi)
```bash
ssh pi
# or
ssh atomicoat@pi.local
```

### 8. Performance Issues

#### Check Connection Type
```bash
tailscale status
```
- `direct` = Best performance
- `DERP(server)` = Slower but works through firewalls

#### Optimize Connection
```bash
# On Pi
sudo tailscale set --accept-routes
```

### 9. Security Issues

#### Check SSH Key Authentication
```bash
ssh pi-remote 'sudo grep "PasswordAuthentication" /etc/ssh/sshd_config'
```
**Should show:** `PasswordAuthentication no`

#### Verify SSH Keys
```bash
ssh pi-remote 'ls -la ~/.ssh/authorized_keys'
```

#### Check Tailscale Access
```bash
tailscale status
# Only your devices should appear
```

### 10. Complete Reset (Last Resort)

#### Reset Tailscale
```bash
# On Pi
sudo tailscale logout
sudo tailscale up
```

#### Reset SSH Keys
```bash
# On Mac
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "atomicoat@$(hostname)"
ssh-copy-id -i ~/.ssh/id_ed25519.pub atomicoat@pi.local
```

## Diagnostic Commands

### System Status
```bash
ssh pi-remote 'echo "=== System Status ===" && whoami && hostname && uptime && echo "=== Services ===" && sudo systemctl is-enabled ssh tailscaled && echo "=== Network ===" && tailscale ip -4'
```

### Connection Test
```bash
echo "=== Connection Test ===" && ssh pi-remote 'echo "✅ SSH Working" && sudo systemctl status ssh --no-pager | head -3'
```

### Tailscale Test
```bash
echo "=== Tailscale Test ===" && tailscale ping pi && tailscale status
```

## Emergency Access

If all else fails:
1. **Physical access:** Connect monitor/keyboard to Pi
2. **Local network:** Use `ssh pi` when on same WiFi
3. **ngrok tunnel:** Use backup tunnel service
4. **Factory reset:** Reinstall everything from scratch

---
*Keep this guide handy for troubleshooting remote access issues.*
