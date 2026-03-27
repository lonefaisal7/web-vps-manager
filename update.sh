#!/bin/bash
set -e
INSTALL_DIR="/root/web-vps-manager"
echo "[WebVPS] Pulling latest from GitHub..."
cd "$INSTALL_DIR"
git pull origin main
echo "[WebVPS] Installing updated dependencies..."
pip3 install -q -r requirements.txt
echo "[WebVPS] Restarting service..."
systemctl restart webvps
echo "[WebVPS] ✅ Update complete."
