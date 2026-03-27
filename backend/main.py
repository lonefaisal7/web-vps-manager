import os
import sys

# Ensure root-only execution
if os.geteuid() != 0:
    print("[ERROR] Web VPS Manager must run as root.")
    sys.exit(1)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import secrets

from backend.routes import auth, files, terminal, system, processes, settings, network

app = FastAPI(title="Web VPS Manager", version="1.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", secrets.token_hex(32)),
    session_cookie="webvps_session",
    max_age=86400,
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(files.router, prefix="/api/files")
app.include_router(terminal.router, prefix="/ws")
app.include_router(system.router, prefix="/api/system")
app.include_router(processes.router, prefix="/api/processes")
app.include_router(settings.router, prefix="/api/settings")
app.include_router(network.router, prefix="/api/network")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    with open("frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("frontend/login.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/setup", response_class=HTMLResponse)
async def setup_page():
    with open("frontend/setup.html", "r") as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=5000, reload=False)
