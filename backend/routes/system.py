import psutil
import subprocess
import time
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
