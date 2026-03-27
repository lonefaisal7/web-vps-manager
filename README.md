# 🚀 Web VPS Manager

A self-hosted, lightweight VPS control panel built with **Python (FastAPI)**.

> ⚠️ **WARNING**: This panel grants **full root access** to your server. Use responsibly.

## ⚡ One-Line Install

```bash
bash <(curl -s https://raw.githubusercontent.com/lonefaisal7/web-vps-manager/main/install.sh)
```

Access at: `http://<your-ip>:5000`

## ✨ Features

- 📊 **Dashboard** – Real-time CPU, RAM, Disk, Uptime
- 📁 **File Manager** – Browse, edit, upload, download, delete
- 🖥️ **Live Terminal** – Full bash via WebSockets + pty
- ⚡ **Process Manager** – View/kill processes, manage systemd services
- 🔄 **Auto-Update** – git pull + restart from UI
- 🗑️ **Uninstall** – Clean removal from UI

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + Uvicorn |
| Terminal | pty + WebSockets |
| Auth | bcrypt + sessions |
| Frontend | HTML + TailwindCSS + xterm.js |
| Monitoring | psutil |

## 📂 Structure

```
web-vps-manager/
├── backend/           # FastAPI app
│   ├── main.py
│   ├── auth/
│   ├── routes/
│   └── utils/
├── frontend/          # HTML + JS + CSS
├── service/           # systemd unit
├── install.sh
├── update.sh
├── uninstall.sh
└── requirements.txt
```

## 🔐 Security Notes

- Runs on port `5000` as root
- Recommend: Nginx reverse proxy + HTTPS
- Restrict access by IP using firewall

## 🔄 Update

```bash
bash /root/web-vps-manager/update.sh
```

## 🗑️ Uninstall

```bash
bash /root/web-vps-manager/uninstall.sh
```
