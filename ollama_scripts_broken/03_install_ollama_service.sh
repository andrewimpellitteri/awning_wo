#!/bin/bash
# Install Ollama as a systemd service for persistent operation

set -e

echo "Installing Ollama systemd service..."

# Copy service file to systemd directory
if [ -f "/var/app/current/.platform/files/ollama.service" ]; then
    sudo cp /var/app/current/.platform/files/ollama.service /etc/systemd/system/ollama.service
    sudo chmod 644 /etc/systemd/system/ollama.service

    # Reload systemd
    sudo systemctl daemon-reload

    # Enable service to start on boot
    sudo systemctl enable ollama.service

    # Start or restart the service
    sudo systemctl restart ollama.service

    echo "Ollama systemd service installed and started"

    # Check status
    sudo systemctl status ollama.service --no-pager || true
else
    echo "WARNING: ollama.service file not found"
fi
