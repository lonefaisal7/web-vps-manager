import os
import shutil
import stat
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from backend.utils.auth_guard import require_auth
import aiofiles

router = APIRouter()


def get_permissions(path: str) -> str:
    try:
        mode = os.stat(path).st_mode
        return stat.filemode(mode)
    except:
        return "----------"


def get_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except:
        return 0


@router.get("/list")
async def list_dir(request: Request, path: str = "/"):
    require_auth(request)
    try:
        entries = []
        for item in sorted(os.listdir(path)):
            full = os.path.join(path, item)
            is_dir = os.path.isdir(full)
            entries.append({
                "name": item,
                "path": full,
                "is_dir": is_dir,
                "size": get_size(full) if not is_dir else 0,
                "permissions": get_permissions(full)
            })
        return JSONResponse({"path": path, "entries": entries})
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/read")
async def read_file(request: Request, path: str):
    require_auth(request)
    try:
        async with aiofiles.open(path, "r", errors="replace") as f:
            content = await f.read()
        return JSONResponse({"content": content})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/write")
async def write_file(request: Request, path: str = Form(...), content: str = Form(...)):
    require_auth(request)
    try:
        async with aiofiles.open(path, "w") as f:
            await f.write(content)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/create")
async def create_item(request: Request, path: str = Form(...), is_dir: bool = Form(False)):
    require_auth(request)
    try:
        if is_dir:
            os.makedirs(path, exist_ok=True)
        else:
            Path(path).touch()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/rename")
async def rename_item(request: Request, src: str = Form(...), dst: str = Form(...)):
    require_auth(request)
    try:
        os.rename(src, dst)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/delete")
async def delete_item(request: Request, path: str = Form(...)):
    require_auth(request)
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/upload")
async def upload_file(request: Request, path: str = Form(...), file: UploadFile = File(...)):
    require_auth(request)
    try:
        dest = os.path.join(path, file.filename)
        async with aiofiles.open(dest, "wb") as f:
            content = await file.read()
            await f.write(content)
        return JSONResponse({"success": True, "filename": file.filename})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/download")
async def download_file(request: Request, path: str):
    require_auth(request)
    return FileResponse(path, filename=os.path.basename(path))
