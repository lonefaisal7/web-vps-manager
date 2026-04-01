import psutil
import time
import threading
import subprocess
import shutil
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.utils.auth_guard import require_auth

router = APIRouter()

# ── Live speed tracking (psutil, 1-sec delta) ──
_live_lock = threading.Lock()
_last_counters = None
_last_time = None
_latest_speed = {"dl": 0.0, "ul": 0.0}
_live_running = False


def _live_loop():
    global _last_counters, _last_time, _latest_speed
    _last_counters = psutil.net_io_counters()
    _last_time = time.time()
    while _live_running:
        time.sleep(1)
        now = time.time()
        cur = psutil.net_io_counters()
        dt = now - _last_time
        if dt > 0:
            with _live_lock:
                _latest_speed = {
                    "dl": max(0.0, (cur.bytes_recv - _last_counters.bytes_recv) / dt),
                    "ul": max(0.0, (cur.bytes_sent - _last_counters.bytes_sent) / dt),
                }
        _last_counters = cur
        _last_time = now


def start_live_collector():
    global _live_running
    if not _live_running:
        _live_running = True
        t = threading.Thread(target=_live_loop, daemon=True)
        t.start()


start_live_collector()


# ── vnStat cache ──
_vnstat_cache = None
_vnstat_cache_time = 0.0
_vnstat_lock = threading.Lock()
VNSTAT_CACHE_TTL = 3600  # 1 hour


# ── Interface detection ──

def _detect_iface(data: dict) -> dict | None:
    """
    Pick the best interface from vnStat JSON output.
    Priority:
      1. Any interface matching common VPS names: ens5, ens3, eth0, enp*, ens*
      2. The interface with the most total traffic (rx+tx)
      3. First interface in list
    Skips loopback (lo) and virtual/docker interfaces.
    """
    ifaces = data.get("interfaces", [])
    if not ifaces:
        return None

    SKIP = {"lo", "docker0", "virbr0", "lxcbr0", "br-"}
    PREFERRED = ["ens5", "ens3", "eth0", "ens4", "enp0s3", "enp3s0"]

    candidates = [
        i for i in ifaces
        if not any(i["name"].startswith(s) for s in SKIP)
    ]
    if not candidates:
        return ifaces[0]

    # Try preferred names first
    for pref in PREFERRED:
        for iface in candidates:
            if iface["name"] == pref:
                return iface

    # Pick the one with most traffic (most data = primary interface)
    def _total_traffic(iface):
        traffic = iface.get("traffic", {})
        total = 0
        for bucket in ("day", "month", "hour"):
            for entry in traffic.get(bucket, []):
                total += _parse_rx(entry) + _parse_tx(entry)
        return total

    return max(candidates, key=_total_traffic)


# ── vnStat rx/tx byte extraction ──
# vnStat v2.x JSON: rx/tx are integers in BYTES directly
# vnStat v1.x JSON: rx/tx stored under "traffic" with "bytes" sub-key (KiB)
# We handle both schemas safely.

def _parse_rx(entry: dict) -> int:
    """Extract download bytes from a vnStat traffic entry (handles v1 and v2 schema)."""
    rx = entry.get("rx", 0)
    if isinstance(rx, dict):
        # v1 schema: {"bytes": N, "kib": N}  — value is in bytes
        return int(rx.get("bytes", 0))
    return int(rx)  # v2 schema: plain integer bytes


def _parse_tx(entry: dict) -> int:
    """Extract upload bytes from a vnStat traffic entry (handles v1 and v2 schema)."""
    tx = entry.get("tx", 0)
    if isinstance(tx, dict):
        return int(tx.get("bytes", 0))
    return int(tx)


def _fetch_vnstat() -> dict | None:
    """Run vnstat --json and return parsed dict, or None on failure."""
    try:
        result = subprocess.run(
            ["vnstat", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _get_vnstat_cached(force: bool = False) -> dict | None:
    global _vnstat_cache, _vnstat_cache_time
    with _vnstat_lock:
        now = time.time()
        if force or _vnstat_cache is None or (now - _vnstat_cache_time) > VNSTAT_CACHE_TTL:
            data = _fetch_vnstat()
            if data is not None:
                _vnstat_cache = data
                _vnstat_cache_time = now
        return _vnstat_cache


# ── Formatters ──

def _fmt_speed(bps: float) -> str:
    if bps >= 1_048_576:
        return f"{bps/1_048_576:.2f} MB/s"
    if bps >= 1024:
        return f"{bps/1024:.1f} KB/s"
    return f"{bps:.0f} B/s"


def _fmt_bytes(b: float) -> str:
    """Auto-scale bytes to human readable string."""
    if b >= 1_099_511_627_776:
        return f"{b/1_099_511_627_776:.2f} TB"
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.2f} GB"
    if b >= 1_048_576:
        return f"{b/1_048_576:.2f} MB"
    if b >= 1024:
        return f"{b/1024:.1f} KB"
    return f"{b:.0f} B"


# ── Range → vnStat bucket mapping ──
# (bucket_type, entry_count)
RANGE_MAP = {
    "1h":  ("hour",  1),
    "6h":  ("hour",  6),
    "12h": ("hour", 12),
    "24h": ("day",   1),
    "2d":  ("day",   2),
    "3d":  ("day",   3),
    "7d":  ("day",   7),
    "15d": ("day",  15),
    "1mo": ("month",  1),
    "3mo": ("month",  3),
    "6mo": ("month",  6),
    "1yr": ("month", 12),
}


def _extract_entries(iface_data: dict, bucket: str, count: int) -> list[dict]:
    """Return last `count` entries of the given bucket type (oldest→newest order)."""
    traffic = iface_data.get("traffic", {})
    key = {"hour": "hour", "day": "day", "month": "month"}.get(bucket, "day")
    entries = traffic.get(key, [])
    # vnStat returns oldest-first; slice last N
    return entries[-count:] if entries else []


def _entry_label(entry: dict, bucket: str) -> str:
    """Build a human-readable label for a traffic entry."""
    d = entry.get("date", {})
    t = entry.get("time", {})
    day = d.get("day", "?")
    month = d.get("month", "?")
    year = str(d.get("year", "??"))[-2:]
    if bucket == "hour":
        hour = t.get("hour", "?")
        hour_str = f"{hour:02d}:00" if isinstance(hour, int) else "--:--"
        return f"{day}/{month} {hour_str}"
    elif bucket == "day":
        return f"{day}/{month}/{year}"
    else:
        return f"{month}/{year}"


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@router.get("/live")
async def net_live(request: Request):
    """Real-time 1-second network speed via psutil delta."""
    require_auth(request)
    with _live_lock:
        speed = dict(_latest_speed)
    return JSONResponse({
        "dl": _fmt_speed(speed["dl"]),
        "ul": _fmt_speed(speed["ul"]),
        "dl_raw": round(speed["dl"], 2),
        "ul_raw": round(speed["ul"], 2),
    })


@router.get("/history")
async def net_history(request: Request, range: str = "24h"):
    """
    Historical network usage from vnStat.
    - Interface: auto-detected (prefers ens5 > ens3 > eth0 > highest-traffic)
    - rx/tx: summed (NOT averaged) across requested time range
    - Units: auto-scaled bytes (B / KB / MB / GB / TB)
    """
    require_auth(request)

    bucket, count = RANGE_MAP.get(range, ("day", 1))
    data = _get_vnstat_cached()

    if data is None:
        return JSONResponse({
            "range": range,
            "total_dl": "N/A",
            "total_ul": "N/A",
            "sparkline_dl": [],
            "sparkline_ul": [],
            "labels": [],
            "vnstat": False,
            "error": "vnstat not available. Install: apt install vnstat -y",
        })

    iface = _detect_iface(data)
    if iface is None:
        return JSONResponse({
            "range": range,
            "total_dl": "0 B",
            "total_ul": "0 B",
            "sparkline_dl": [],
            "sparkline_ul": [],
            "labels": [],
            "vnstat": True,
            "interface": "none",
        })

    entries = _extract_entries(iface, bucket, count)

    # SUM totals — never average
    total_rx = 0
    total_tx = 0
    sparkline_dl = []
    sparkline_ul = []
    labels = []

    for e in entries:
        rx = _parse_rx(e)
        tx = _parse_tx(e)
        total_rx += rx
        total_tx += tx
        sparkline_dl.append(rx)
        sparkline_ul.append(tx)
        labels.append(_entry_label(e, bucket))

    return JSONResponse({
        "range": range,
        "total_dl": _fmt_bytes(total_rx),
        "total_ul": _fmt_bytes(total_tx),
        "total_dl_raw": total_rx,
        "total_ul_raw": total_tx,
        "sparkline_dl": sparkline_dl,
        "sparkline_ul": sparkline_ul,
        "labels": labels,
        "interface": iface.get("name", "unknown"),
        "vnstat": True,
        "cached_at": int(_vnstat_cache_time),
    })


@router.post("/refresh")
async def net_refresh(request: Request):
    """Force-refresh vnStat cache immediately (bypasses 1h TTL)."""
    require_auth(request)
    data = _get_vnstat_cached(force=True)
    if data is None:
        return JSONResponse({"status": "error", "message": "vnstat not available"}, status_code=503)
    iface = _detect_iface(data)
    return JSONResponse({
        "status": "ok",
        "interface": iface.get("name", "unknown") if iface else "none",
        "interfaces": [i.get("name") for i in data.get("interfaces", [])],
        "cached_at": int(_vnstat_cache_time),
    })


# ──────────────────────────────────────────
# AUTO-INSTALL HELPER
# ──────────────────────────────────────────

def _ensure_speedtest_cli() -> tuple[bool, str]:
    if shutil.which("speedtest-cli"):
        return True, "ok"
    apt = shutil.which("apt-get") or shutil.which("apt")
    if apt:
        try:
            subprocess.run([apt, "update", "-qq"], capture_output=True, timeout=60)
            res = subprocess.run(
                [apt, "install", "-y", "speedtest-cli"],
                capture_output=True, text=True, timeout=120
            )
            if res.returncode == 0 and shutil.which("speedtest-cli"):
                return True, "installed via apt"
        except Exception:
            pass
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

_speedtest_lock = threading.Lock()
_speedtest_running = False
_speedtest_result = None


def _run_speedtest_thread():
    global _speedtest_running, _speedtest_result
    try:
        ok, msg = _ensure_speedtest_cli()
        if not ok:
            _speedtest_result = {"status": "error", "message": msg}
            return
        proc = subprocess.run(
            ["speedtest-cli", "--json", "--secure"],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode == 0:
            d = json.loads(proc.stdout)
            _speedtest_result = {
                "status": "ok",
                "download_mbps": round(d["download"] / 1_000_000, 2),
                "upload_mbps":   round(d["upload"]   / 1_000_000, 2),
                "ping_ms":       round(d["ping"], 1),
                "server":        d["server"]["name"],
                "server_country": d["server"]["country"],
                "sponsor":       d["server"]["sponsor"],
                "timestamp":     d["timestamp"],
                "ip":            d.get("client", {}).get("ip", "--"),
                "isp":           d.get("client", {}).get("isp", "--"),
            }
        else:
            _speedtest_result = {
                "status": "error",
                "message": proc.stderr.strip() or f"speedtest-cli exited with code {proc.returncode}",
            }
    except subprocess.TimeoutExpired:
        _speedtest_result = {"status": "error", "message": "Speed test timed out (120s)"}
    except Exception as e:
        _speedtest_result = {"status": "error", "message": str(e)}
    finally:
        _speedtest_running = False


@router.post("/speedtest")
async def run_speedtest(request: Request):
    """Starts a speed test in background."""
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
