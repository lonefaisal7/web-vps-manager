import subprocess
import shutil
import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()


@router.post("/update")
async def update_panel(request: Request):
    require_auth(request)
    try:
        result = subprocess.run(
            ["bash", "/root/web-vps-manager/update.sh"],
            capture_output=True, text=True, timeout=120
        )
        return JSONResponse({"output": result.stdout + result.stderr, "code": result.returncode})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/uninstall")
async def uninstall_panel(request: Request, confirm: str = Form(...)):
    require_auth(request)
    if confirm != "DELETE":
        return JSONResponse({"error": "Confirmation failed"}, status_code=400)
    try:
        subprocess.Popen(["bash", "/root/web-vps-manager/uninstall.sh"])
        return JSONResponse({"success": True, "message": "Uninstalling..."})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
