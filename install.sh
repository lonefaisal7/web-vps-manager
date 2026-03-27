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
VENV_DIR="$INSTALL_DIR/venv"
REPO="https://github.com/lonefaisal7/web-vps-manager.git"

echo -e "${YELLOW}[1/7] Checking dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv python3-full git curl

echo -e "${YELLOW}[2/7] Cloning repository...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Directory exists, pulling latest..."
  cd "$INSTALL_DIR" && git pull origin main
else
  # Remove broken dir if exists without .git
  rm -rf "$INSTALL_DIR"
  git clone "$REPO" "$INSTALL_DIR"
fi

echo -e "${YELLOW}[3/7] Creating Python virtual environment...${NC}"
python3 -m venv "$VENV_DIR"
echo "Virtual environment created at $VENV_DIR"

echo -e "${YELLOW}[4/7] Installing Python dependencies into venv...${NC}"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "Dependencies installed."

echo -e "${YELLOW}[5/7] Downloading xterm.js assets...${NC}"
XTERM_VER="5.3.0"
mkdir -p "$INSTALL_DIR/frontend/js" "$INSTALL_DIR/frontend/css"
curl -sL "https://cdn.jsdelivr.net/npm/xterm@${XTERM_VER}/lib/xterm.min.js" -o "$INSTALL_DIR/frontend/js/xterm.min.js"
curl -sL "https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js" -o "$INSTALL_DIR/frontend/js/xterm-addon-fit.min.js"
curl -sL "https://cdn.jsdelivr.net/npm/xterm@${XTERM_VER}/css/xterm.min.css" -o "$INSTALL_DIR/frontend/css/xterm.min.css"
echo "xterm.js assets downloaded."

echo -e "${YELLOW}[6/7] Setting up systemd service...${NC}"
cp "$INSTALL_DIR/service/webvps.service" /etc/systemd/system/webvps.service
systemctl daemon-reload
systemctl enable webvps
systemctl restart webvps

echo -e "${YELLOW}[7/7] Making scripts executable...${NC}"
chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/uninstall.sh"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Installation Complete!               ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
IP=$(hostname -I | awk '{print $1}')
printf "${GREEN}║  🌐 Access: http://%-22s║${NC}\n" "${IP}:5000"
echo -e "${GREEN}║  📌 First visit: Setup admin account    ║${NC}"
echo -e "${GREEN}║  ⚠️  Root access – keep secure!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
