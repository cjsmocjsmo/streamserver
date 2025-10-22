#!/bin/bash

# Stream Server Systemd Service Uninstaller
echo "Uninstalling Stream Server systemd service..."

# Stop the service if it's running
echo "Stopping service..."
sudo systemctl stop streamserver.service

# Disable the service
echo "Disabling service..."
sudo systemctl disable streamserver.service

# Remove service file
echo "Removing service file..."
sudo rm -f /etc/systemd/system/streamserver.service

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Reset any failed states
sudo systemctl reset-failed

echo ""
echo "Uninstall complete!"
echo "The stream server service has been removed and will no longer start on boot."