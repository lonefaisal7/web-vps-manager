from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from backend.auth.manager import is_setup_done, create_user, verify_user

router = APIRouter()


@router.post("/api/setup")
async def setup(request: Request, username: str = Form(...), password: str = Form(...)):
    if is_setup_done():
        return JSONResponse({"error": "Already configured"}, status_code=400)
    create_user(username, password)
    request.session["authenticated"] = True
    request.session["username"] = username
    return JSONResponse({"success": True})


@router.post("/api/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not is_setup_done():
        return JSONResponse({"error": "Not configured"}, status_code=400)
    if verify_user(username, password):
        request.session["authenticated"] = True
        request.session["username"] = username
        return JSONResponse({"success": True})
    return JSONResponse({"error": "Invalid credentials"}, status_code=401)


@router.post("/api/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse({"success": True})


@router.get("/api/auth/status")
async def auth_status(request: Request):
    return JSONResponse({
        "authenticated": bool(request.session.get("authenticated")),
        "setup_done": is_setup_done(),
        "username": request.session.get("username", "")
    })
