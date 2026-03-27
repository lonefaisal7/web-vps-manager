import psutil
import time
import threading
import subprocess
import shutil
import json
from collections import deque
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()

# ── In-memory history store ──
MAX_SAMPLES = 32 * 86400  # 32 days of per-second samples
_history = deque(maxlen=MAX_SAMPLES)
_lock = threading.Lock()
_last_counters = None
_last_time = None
_running = False

# ── Speed test state ──
_speedtest_lock = threading.Lock()
_speedtest_running = False
_speedtest_result = None   # last cached result


def _collect_loop():
    global _last_counters, _last_time
    _last_counters = psutil.net_io_counters()
    _last_time = time.time()
    while _running:
        time.sleep(1)
        now = time.time()
        cur = psutil.net_io_counters()
        dt = now - _last_time
        if dt > 0:
            dl_speed = (cur.bytes_recv - _last_counters.bytes_recv) / dt
            ul_speed = (cur.bytes_sent - _last_counters.bytes_sent) / dt
            with _lock:
                _history.append({
                    "ts": now,
                    "dl": max(0, dl_speed),
                    "ul": max(0, ul_speed),
                    "total_recv": cur.bytes_recv,
                    "total_sent": cur.bytes_sent,
                })
        _last_counters = cur
        _last_time = now


def start_collector():
    global _running
    if not _running:
        _running = True
        t = threading.Thread(target=_collect_loop, daemon=True)
        t.start()


start_collector()


def _fmt_speed(bps: float) -> str:
    if bps >= 1_048_576:
        return f"{bps/1_048_576:.2f} MB/s"
    return f"{bps/1024:.1f} KB/s"


def _fmt_bytes(b: float) -> str:
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.2f} GB"
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.1f} KB"


RANGE_SECONDS = {
    "24h":  86400,
    "2d":   2 * 86400,
    "3d":   3 * 86400,
    "7d":   7 * 86400,
    "1mo":  30 * 86400,
    "1yr":  365 * 86400,
}


@router.get("/live")
async def net_live(request: Request):
    require_auth(request)
    with _lock:
        if not _history:
            return JSONResponse({"dl": "0.0 KB/s", "ul": "0.0 KB/s", "dl_raw": 0, "ul_raw": 0})
        latest = _history[-1]
    return JSONResponse({
        "dl": _fmt_speed(latest["dl"]),
        "ul": _fmt_speed(latest["ul"]),
        "dl_raw": latest["dl"],
        "ul_raw": latest["ul"],
    })


@router.get("/history")
async def net_history(request: Request, range: str = "24h"):
    require_auth(request)
    seconds = RANGE_SECONDS.get(range, 86400)
    cutoff = time.time() - seconds
    with _lock:
        samples = [s for s in _history if s["ts"] >= cutoff]
    if not samples:
        return JSONResponse({
            "range": range,
            "total_dl": "0.0 KB",
            "total_ul": "0.0 KB",
            "sparkline_dl": [],
            "sparkline_ul": [],
        })
    total_recv_bytes = sum(s["dl"] for s in samples)
    total_sent_bytes = sum(s["ul"] for s in samples)
    bucket_count = 60
    bucket_size = max(1, len(samples) // bucket_count)
    sparkline_dl = []
    sparkline_ul = []
    for i in range(0, len(samples), bucket_size):
        chunk = samples[i:i + bucket_size]
        sparkline_dl.append(round(sum(c["dl"] for c in chunk) / len(chunk), 1))
        sparkline_ul.append(round(sum(c["ul"] for c in chunk) / len(chunk), 1))
    return JSONResponse({
        "range": range,
        "total_dl": _fmt_bytes(total_recv_bytes),
        "total_ul": _fmt_bytes(total_sent_bytes),
        "sparkline_dl": sparkline_dl[-60:],
        "sparkline_ul": sparkline_ul[-60:],
    })


# ──────────────────────────────────────────
# AUTO-INSTALL HELPER
# ──────────────────────────────────────────

def _ensure_speedtest_cli() -> tuple[bool, str]:
    """
    Checks if speedtest-cli is available on PATH.
    If not, tries to install it automatically:
      1. apt-get install -y speedtest-cli  (Debian / Ubuntu)
      2. pip install speedtest-cli          (fallback, any OS)
    Returns (success: bool, message: str).
    """
    # Already installed — nothing to do
    if shutil.which("speedtest-cli"):
        return True, "ok"

    # ── Try apt first (most VPS distros are Debian/Ubuntu) ──
    apt = shutil.which("apt-get") or shutil.which("apt")
    if apt:
        try:
            # Update package lists (best-effort, ignore errors)
            subprocess.run(
                [apt, "update", "-qq"],
                capture_output=True, timeout=60
            )
            res = subprocess.run(
                [apt, "install", "-y", "speedtest-cli"],
                capture_output=True, text=True, timeout=120
            )
            if res.returncode == 0 and shutil.which("speedtest-cli"):
                return True, "installed via apt"
        except Exception:
            pass  # fall through to pip

    # ── Fallback: pip install ──
    try:
        pip = shutil.which("pip3") or shutil.which("pip")
        if pip:
            res = subprocess.run(
                [pip, "install", "--quiet", "speedtest-cli"],
                capture_output=True, text=True, timeout=120
            )
            if res.returncode == 0 and shutil.which("speedtest-cli"):
                return True, "installed via pip"
    except Exception:
        pass

    return False, (
        "speedtest-cli could not be installed automatically. "
        "Run manually: apt install speedtest-cli"
    )


# ──────────────────────────────────────────
# SPEED TEST
# ──────────────────────────────────────────

def _run_speedtest_thread():
    """Auto-installs speedtest-cli if missing, then runs the test."""
    global _speedtest_running, _speedtest_result
    try:
        # ── Step 1: ensure binary exists ──
        ok, msg = _ensure_speedtest_cli()
        if not ok:
            _speedtest_result = {"status": "error", "message": msg}
            return

        # ── Step 2: run the test ──
        proc = subprocess.run(
            ["speedtest-cli", "--json", "--secure"],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            _speedtest_result = {
                "status": "ok",
                "download_mbps": round(data["download"] / 1_000_000, 2),
                "upload_mbps":   round(data["upload"]   / 1_000_000, 2),
                "ping_ms":       round(data["ping"], 1),
                "server":        data["server"]["name"],
                "server_country": data["server"]["country"],
                "sponsor":       data["server"]["sponsor"],
                "timestamp":     data["timestamp"],
                "ip":            data.get("client", {}).get("ip", "--"),
                "isp":           data.get("client", {}).get("isp", "--"),
            }
        else:
            _speedtest_result = {
                "status": "error",
                "message": proc.stderr.strip() or "speedtest-cli exited with code " + str(proc.returncode)
            }
    except subprocess.TimeoutExpired:
        _speedtest_result = {"status": "error", "message": "Speed test timed out (120s)"}
    except Exception as e:
        _speedtest_result = {"status": "error", "message": str(e)}
    finally:
        _speedtest_running = False


@router.post("/speedtest")
async def run_speedtest(request: Request):
    """Starts a speed test in background. Returns running=True while in progress."""
    require_auth(request)
    global _speedtest_running
    with _speedtest_lock:
        if _speedtest_running:
            return JSONResponse({"status": "running"})
        _speedtest_running = True
    t = threading.Thread(target=_run_speedtest_thread, daemon=True)
    t.start()
    return JSONResponse({"status": "started"})


@router.get("/speedtest")
async def get_speedtest(request: Request):
    """Poll for speed test status / last result."""
    require_auth(request)
    if _speedtest_running:
        return JSONResponse({"status": "running"})
    if _speedtest_result is None:
        return JSONResponse({"status": "idle"})
    return JSONResponse(_speedtest_result)
