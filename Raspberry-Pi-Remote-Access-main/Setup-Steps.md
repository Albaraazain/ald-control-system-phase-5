# Detailed Setup Steps

## Phase 1: Initial SSH Setup

### 1. Generate SSH Key Pair
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "atomicoat@$(hostname)"
```

### 2. Copy Public Key to Pi
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub atomicoat@pi.local
```

### 3. Test SSH Connection
```bash
ssh -i ~/.ssh/id_ed25519 atomicoat@pi.local 'echo "SSH connection successful!"'
```

## Phase 2: Tailscale VPN Setup

### 1. Install Tailscale on Mac
```bash
brew install tailscale
sudo brew services start tailscale
sudo tailscale up
```

### 2. Install Tailscale on Pi
```bash
# Already installed via: curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### 3. Verify Tailscale Connection
```bash
tailscale status
tailscale ping pi
```

## Phase 3: Headless Configuration

### 1. Configure Auto-Login
```bash
# On Pi
sudo raspi-config nonint do_boot_behaviour B2
sudo systemctl set-default multi-user.target
sudo systemctl disable getty@tty1
```

### 2. Create Auto-Login Service
```bash
# On Pi
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
echo "[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin atomicoat --noclear %I \$TERM" | sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf
sudo systemctl daemon-reload
sudo systemctl enable getty@tty1
```

### 3. Configure Passwordless Sudo
```bash
# On Pi
echo "atomicoat ALL=(ALL) NOPASSWD: /usr/bin/tailscale, /bin/systemctl, /sbin/reboot, /sbin/shutdown, /usr/bin/apt, /usr/bin/apt-get" | sudo tee /etc/sudoers.d/atomicoat-nopasswd
sudo chmod 0440 /etc/sudoers.d/atomicoat-nopasswd
```

### 4. Enable Services
```bash
# On Pi
sudo systemctl enable ssh
sudo systemctl enable tailscaled
sudo systemctl enable systemd-timesyncd
```

## Phase 4: SSH Configuration

### 1. Create SSH Config
```bash
# On Mac
cat >> ~/.ssh/config << 'EOF'
# Raspberry Pi Remote Access Configuration
Host pi
    HostName pi.local
    User atomicoat
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

# Raspberry Pi via Tailscale (works from anywhere)
Host pi-remote
    HostName 100.100.138.5
    User atomicoat
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
EOF
```

## Phase 5: Testing

### 1. Test Basic Connection
```bash
ssh pi-remote 'echo "Connection successful!" && whoami && hostname'
```

### 2. Test Passwordless Sudo
```bash
ssh pi-remote 'sudo systemctl status ssh --no-pager | head -3'
```

### 3. Test Tailscale Connectivity
```bash
tailscale ping pi
```

### 4. Test Reboot and Reconnection
```bash
ssh pi-remote 'sudo reboot'
# Wait 60 seconds
ssh pi-remote 'echo "Reconnected successfully!" && uptime'
```

## Phase 6: Backup Setup

### 1. Install ngrok (Backup Tunnel)
```bash
# On Pi
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok
```

## Verification Commands

### Check All Services
```bash
ssh pi-remote 'sudo systemctl is-enabled ssh tailscaled systemd-timesyncd'
```

### Check Network Status
```bash
ssh pi-remote 'ip addr show | grep -E "inet " | grep -v "127.0.0.1"'
```

### Check Tailscale Status
```bash
tailscale status
```

### Test File Operations
```bash
ssh pi-remote 'echo "Test file - $(date)" > /tmp/test.txt && cat /tmp/test.txt'
```

---
*This setup provides bulletproof remote access to your Raspberry Pi from anywhere in the world.*
