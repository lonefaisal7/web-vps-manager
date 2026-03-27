import os
import pty
import asyncio
import struct
import fcntl
import termios
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

router = APIRouter()


@router.websocket("/terminal")
async def terminal_ws(websocket: WebSocket, cwd: str = "/root"):
    await websocket.accept()
    loop = asyncio.get_event_loop()

    master_fd, slave_fd = pty.openpty()
    pid = os.fork()

    if pid == 0:
        # Child process
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(master_fd)
        os.close(slave_fd)
        try:
            os.chdir(cwd)
        except:
            os.chdir("/root")
        os.execve("/bin/bash", ["/bin/bash", "--login"], {
            "TERM": "xterm-256color",
            "HOME": "/root",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "SHELL": "/bin/bash",
            "USER": "root",
            "LOGNAME": "root",
        })
    else:
        # Parent process
        os.close(slave_fd)

        async def read_from_pty():
            while True:
                try:
                    data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_bytes(data)
                    else:
                        break
                except OSError:
                    break

        async def write_to_pty():
            while True:
                try:
                    data = await websocket.receive_bytes()
                    os.write(master_fd, data)
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

        try:
            await asyncio.gather(read_from_pty(), write_to_pty())
        finally:
            try:
                os.close(master_fd)
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except:
                pass
