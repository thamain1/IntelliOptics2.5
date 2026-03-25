#!/bin/bash
# Camera Inspection Worker - Raspberry Pi Deployment Script
#
# Usage: sudo bash deploy-camera-inspection-rpi.sh

set -e

echo "=== IntelliOptics Camera Inspection Worker - Raspberry Pi Deployment ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo bash deploy-camera-inspection-rpi.sh)"
  exit 1
fi

# Detect architecture
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "armv7l" ]; then
  echo "Warning: This script is designed for ARM64/ARMv7 (Raspberry Pi)"
  read -p "Continue anyway? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Install system dependencies
echo ""
echo "=== Installing system dependencies ==="
apt-get update
apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libgl1-mesa-glx \
  git \
  curl

# Create installation directory
INSTALL_DIR="/opt/intellioptics/worker"
echo ""
echo "=== Creating installation directory: $INSTALL_DIR ==="
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Copy worker files
echo ""
echo "=== Copying worker files ==="
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -f "$SCRIPT_DIR/camera_inspection_worker.py" ]; then
  cp "$SCRIPT_DIR/camera_inspection_worker.py" "$INSTALL_DIR/"
  cp "$SCRIPT_DIR/requirements-camera-inspection.txt" "$INSTALL_DIR/"
  cp "$SCRIPT_DIR/.env.camera-inspection.template" "$INSTALL_DIR/.env.template"
  echo "Worker files copied successfully"
else
  echo "Error: Worker files not found in $SCRIPT_DIR"
  echo "Please run this script from the worker directory"
  exit 1
fi

# Create Python virtual environment
echo ""
echo "=== Creating Python virtual environment ==="
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo ""
echo "=== Installing Python dependencies (this may take 5-10 minutes on Raspberry Pi) ==="
pip install --upgrade pip
pip install -r requirements-camera-inspection.txt

# Create .env file if not exists
if [ ! -f "$INSTALL_DIR/.env" ]; then
  echo ""
  echo "=== Configuring environment variables ==="
  cp .env.template .env
  echo "Created .env file from template"
  echo ""
  echo "IMPORTANT: Please edit /opt/intellioptics/worker/.env with your settings:"
  echo "  - API_BASE_URL (backend API URL)"
  echo "  - SENDGRID_API_KEY (email notifications)"
  echo "  - AZURE_BLOB_CONNECTION_STRING (baseline image storage)"
  echo ""
  read -p "Press Enter to open .env file in nano editor..."
  nano .env
fi

# Create systemd service
echo ""
echo "=== Creating systemd service ==="
cat > /etc/systemd/system/camera-inspection.service <<EOF
[Unit]
Description=IntelliOptics Camera Inspection Worker
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/intellioptics/worker
ExecStart=/opt/intellioptics/worker/venv/bin/python /opt/intellioptics/worker/camera_inspection_worker.py
Restart=always
RestartSec=10
EnvironmentFile=/opt/intellioptics/worker/.env

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=camera-inspection

[Install]
WantedBy=multi-user.target
EOF

echo "Systemd service created: /etc/systemd/system/camera-inspection.service"

# Set permissions
echo ""
echo "=== Setting permissions ==="
chown -R pi:pi "$INSTALL_DIR"

# Enable and start service
echo ""
echo "=== Enabling and starting service ==="
systemctl daemon-reload
systemctl enable camera-inspection
systemctl start camera-inspection

# Show status
echo ""
echo "=== Service Status ==="
systemctl status camera-inspection --no-pager

# Show logs
echo ""
echo "=== Recent Logs ==="
journalctl -u camera-inspection -n 20 --no-pager

# Installation complete
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Camera Inspection Worker is now running as a systemd service."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status camera-inspection   # Check status"
echo "  sudo systemctl stop camera-inspection     # Stop worker"
echo "  sudo systemctl start camera-inspection    # Start worker"
echo "  sudo systemctl restart camera-inspection  # Restart worker"
echo "  sudo journalctl -u camera-inspection -f   # View logs (live)"
echo ""
echo "Configuration: /opt/intellioptics/worker/.env"
echo "Logs: sudo journalctl -u camera-inspection"
echo ""
echo "To update configuration:"
echo "  1. Edit /opt/intellioptics/worker/.env"
echo "  2. sudo systemctl restart camera-inspection"
echo ""
