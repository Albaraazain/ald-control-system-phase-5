#!/bin/bash
# Install ALD systemd user services on Raspberry Pi
# Run this on the Pi after pulling the latest code

set -e

echo "Installing ALD systemd user services..."

# Create user systemd directory if it doesn't exist
mkdir -p ~/.config/systemd/user

# Copy service files
cp systemd/ald-terminal1.service ~/.config/systemd/user/
cp systemd/ald-terminal2.service ~/.config/systemd/user/
cp systemd/ald-terminal3.service ~/.config/systemd/user/

echo "Service files copied to ~/.config/systemd/user/"

# Reload systemd user daemon
systemctl --user daemon-reload

echo "Systemd daemon reloaded"

# Enable user lingering (allows services to run without SSH login)
loginctl enable-linger $USER

echo "User lingering enabled for $USER"

# Enable services to start at boot
systemctl --user enable ald-terminal1.service
systemctl --user enable ald-terminal2.service
systemctl --user enable ald-terminal3.service

echo "Services enabled for auto-start at boot"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Start services now:  systemctl --user start ald-terminal{1,2,3}"
echo "  2. Check status:        systemctl --user status ald-terminal1"
echo "  3. View logs:           journalctl --user -u ald-terminal1 -f"
echo "  4. Restart a service:   systemctl --user restart ald-terminal1"
echo "  5. Stop a service:      systemctl --user stop ald-terminal1"
echo ""
echo "Services will now auto-start on boot and auto-restart on crashes!"
