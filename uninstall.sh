#!/bin/bash
INSTALL_DIR="/root/web-vps-manager"
echo "[WebVPS] Stopping service..."
systemctl stop webvps 2>/dev/null || true
systemctl disable webvps 2>/dev/null || true
echo "[WebVPS] Removing systemd service..."
rm -f /etc/systemd/system/webvps.service
systemctl daemon-reload
echo "[WebVPS] Deleting installation directory..."
rm -rf "$INSTALL_DIR"
echo "[WebVPS] ✅ Uninstall complete."
