#!/bin/bash
set -e

# ── Colors ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}"
echo "  ██╗    ██╗███████╗██████╗     ██╗   ██╗██████╗ ███████╗"
echo "  ██║    ██║██╔════╝██╔══██╗    ██║   ██║██╔══██╗██╔════╝"
echo "  ██║ █╗ ██║█████╗  ██████╔╝    ██║   ██║██████╔╝███████╗"
echo "  ██║███╗██║██╔══╝  ██╔══██╗    ╚██╗ ██╔╝██╔═══╝ ╚════██║"
echo "  ╚███╔███╔╝███████╗██████╔╝     ╚████╔╝ ██║     ███████║"
echo "   ╚══╝╚══╝ ╚══════╝╚═════╝       ╚═══╝  ╚═╝     ╚══════╝"
echo -e "${NC}"
echo -e "${GREEN}  Web VPS Manager – Installer${NC}"
echo ""

# ── Root check ──
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}[ERROR] Must run as root.${NC}"; exit 1
fi

INSTALL_DIR="/root/web-vps-manager"
REPO="https://github.com/lonefaisal7/web-vps-manager.git"

echo -e "${YELLOW}[1/6] Checking dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip git curl

echo -e "${YELLOW}[2/6] Cloning repository...${NC}"
if [ -d "$INSTALL_DIR" ]; then
  echo "Directory exists, pulling latest..."
  cd "$INSTALL_DIR" && git pull origin main
else
  git clone "$REPO" "$INSTALL_DIR"
fi

echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"
pip3 install -q -r "$INSTALL_DIR/requirements.txt"

echo -e "${YELLOW}[4/6] Downloading xterm.js assets...${NC}"
XTERM_VER="5.3.0"
mkdir -p "$INSTALL_DIR/frontend/js" "$INSTALL_DIR/frontend/css"
curl -sL "https://cdn.jsdelivr.net/npm/xterm@${XTERM_VER}/lib/xterm.min.js" -o "$INSTALL_DIR/frontend/js/xterm.min.js"
curl -sL "https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js" -o "$INSTALL_DIR/frontend/js/xterm-addon-fit.min.js"
curl -sL "https://cdn.jsdelivr.net/npm/xterm@${XTERM_VER}/css/xterm.min.css" -o "$INSTALL_DIR/frontend/css/xterm.min.css"

echo -e "${YELLOW}[5/6] Setting up systemd service...${NC}"
cp "$INSTALL_DIR/service/webvps.service" /etc/systemd/system/webvps.service
systemctl daemon-reload
systemctl enable webvps
systemctl start webvps

echo -e "${YELLOW}[6/6] Making scripts executable...${NC}"
chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/uninstall.sh"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Installation Complete!               ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}║  🌐 Access: http://${IP}:5000        ║${NC}"
echo -e "${GREEN}║  📌 First visit: Setup admin account    ║${NC}"
echo -e "${GREEN}║  ⚠️  Root access – keep secure!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
