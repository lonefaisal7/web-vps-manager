import psutil
import subprocess
import time
import platform
import socket
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()


@router.get("/stats")
async def get_stats(request: Request):
    require_auth(request)
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = str(int(uptime_seconds // 3600)) + "h " + str(int((uptime_seconds % 3600) // 60)) + "m"
    return JSONResponse({
        "cpu": cpu,
        "ram": {
            "total": ram.total,
            "used": ram.used,
            "percent": ram.percent
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "percent": disk.percent
        },
        "uptime": uptime_str
    })


@router.get("/info")
async def get_system_info(request: Request):
    require_auth(request)
    uptime_seconds = int(time.time() - psutil.boot_time())
    return JSONResponse({
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "cpu_model": platform.processor() or "Unknown",
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "ram_total": psutil.virtual_memory().total,
        "disk_total": psutil.disk_usage("/").total,
        "uptime_seconds": uptime_seconds,
    })


@router.post("/restart")
async def restart_system(request: Request):
    require_auth(request)
    try:
        subprocess.Popen(["shutdown", "-r", "now"])
        return JSONResponse({"success": True, "message": "System restart scheduled."})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
