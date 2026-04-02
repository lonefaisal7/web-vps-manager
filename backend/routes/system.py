import psutil
import subprocess
import time
import platform
import socket
import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()


def _build_disk_tree(path: str, depth: int):
    cmd = ["du", "-x", "-B1", f"--max-depth={depth}", path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)

    nodes = {}
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        size_raw, dir_path = line.split("\t", 1)
        try:
            size = int(size_raw.strip())
        except ValueError:
            continue
        normalized = os.path.normpath(dir_path.strip() or path)
        nodes[normalized] = {
            "name": os.path.basename(normalized) or normalized,
            "path": normalized,
            "size": size,
            "children": []
        }

    normalized_root = os.path.normpath(path)
    if normalized_root not in nodes:
        return None, ["Could not analyze disk usage for the selected path."]

    for node_path in list(nodes.keys()):
        if node_path == normalized_root:
            continue
        parent = os.path.dirname(node_path)
        if parent in nodes:
            nodes[parent]["children"].append(nodes[node_path])

    for node in nodes.values():
        node["children"].sort(key=lambda c: c["size"], reverse=True)

    warnings = []
    if proc.stderr:
        warnings = [ln.strip() for ln in proc.stderr.splitlines() if ln.strip()][:10]
    return nodes[normalized_root], warnings


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


@router.get("/disk-usage")
async def get_disk_usage(request: Request, path: str = "/", depth: int = 3):
    require_auth(request)
    depth = max(1, min(depth, 5))
    path = os.path.normpath(path or "/")
    if not os.path.isdir(path):
        return JSONResponse({"error": f"Path is not a directory: {path}"}, status_code=400)
    try:
        tree, warnings = _build_disk_tree(path, depth)
        if tree is None:
            return JSONResponse({"error": "Failed to read disk usage tree."}, status_code=500)
        return JSONResponse({
            "path": path,
            "depth": depth,
            "tree": tree,
            "warnings": warnings
        })
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Disk usage scan timed out. Try a smaller depth."}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
