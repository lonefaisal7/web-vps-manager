#!/bin/bash
set -e
INSTALL_DIR="/root/web-vps-manager"
VENV_DIR="$INSTALL_DIR/venv"

echo "[WebVPS] Pulling latest from GitHub..."
cd "$INSTALL_DIR"
git pull origin main

echo "[WebVPS] Installing updated dependencies into venv..."
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt

echo "[WebVPS] Restarting service..."
systemctl restart webvps

echo "[WebVPS] ✅ Update complete."
