import psutil
import subprocess
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()


@router.get("/list")
async def list_processes(request: Request):
    require_auth(request)
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
    return JSONResponse({"processes": procs[:100]})


@router.post("/kill")
async def kill_process(request: Request, pid: int = Form(...)):
    require_auth(request)
    try:
        p = psutil.Process(pid)
        p.kill()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/service")
async def manage_service(request: Request, name: str = Form(...), action: str = Form(...)):
    require_auth(request)
    allowed = ["start", "stop", "restart", "status"]
    if action not in allowed:
        return JSONResponse({"error": "Invalid action"}, status_code=400)
    try:
        result = subprocess.run(
            ["systemctl", action, name],
            capture_output=True, text=True, timeout=10
        )
        return JSONResponse({"output": result.stdout + result.stderr, "code": result.returncode})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
