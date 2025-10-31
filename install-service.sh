#!/bin/bash

# Stream Server Systemd Service Installer
echo "Installing Stream Server systemd service..."

# Check if running as root for service installation
if [[ $EUID -eq 0 ]]; then
    echo "Error: Don't run this script as root. Run as a regular user and it will use sudo when needed."
    exit 1
fi

# Copy service file to systemd directory
echo "Copying service file to /etc/systemd/system/"
sudo cp streamserver.service /etc/systemd/system/

# Set proper permissions
sudo chmod 644 /etc/systemd/system/streamserver.service

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling service to start on boot..."
sudo systemctl enable streamserver.service

# Check if user is in video group (required for camera access)
if groups $USER | grep -q "\bvideo\b"; then
    echo "✓ User is already in video group"
else
    echo "Adding user to video group for camera access..."
    sudo usermod -a -G video $USER
    echo "⚠️  You need to log out and log back in for group changes to take effect"
fi

echo ""
echo "Installation complete! You can now:"
echo "  Start the service: sudo systemctl start streamserver"
echo "  Stop the service:  sudo systemctl stop streamserver"
echo "  Check status:      sudo systemctl status streamserver"
echo "  View logs:         sudo journalctl -u streamserver -f"
echo ""
echo "The service is now enabled and will start automatically on boot."
echo "To start it now, run: sudo systemctl start streamserver"