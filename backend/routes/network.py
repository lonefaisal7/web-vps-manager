import psutil
import time
import threading
from collections import deque
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()

# ── In-memory history store ──
# Each sample: (timestamp, bytes_sent, bytes_recv)
# Keep 1 year max = 365*24*3600 seconds, but we sample every second
# We use deque with maxlen = 366 days * 86400 sec is too large;
# instead store 1-second samples in a rolling deque for 1 year in daily buckets.
# Practical approach: keep last 32 days of per-second data (2,764,800 samples)
# That's ~66 MB RAM max. We'll keep 32*86400 = 2,764,800 entries max.

MAX_SAMPLES = 32 * 86400  # 32 days of per-second samples
_history = deque(maxlen=MAX_SAMPLES)
_lock = threading.Lock()
_last_counters = None
_last_time = None
_running = False


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


# Start immediately on import
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
    """Returns current download & upload speed (latest 1-second sample)."""
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
    """
    Returns total downloaded + uploaded for the chosen range,
    plus a sparkline (up to 60 aggregated buckets) for the chart.
    """
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

    # Total bytes transferred in range
    total_recv_bytes = sum(s["dl"] for s in samples)  # bytes/s * 1s each
    total_sent_bytes = sum(s["ul"] for s in samples)

    # Build sparkline: aggregate into 60 buckets
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
