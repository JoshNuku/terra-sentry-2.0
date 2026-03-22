import subprocess
import requests
import time
import threading
from app.core import config, logger

log = logger.get_logger()

BACKEND_URL = config.BACKEND_URL
DEVICE_ID = config.DEVICE_ID

_ngrok_lock = threading.Lock()
_cached_tunnel_url_by_proto = {}
_registered_stream_url = None  # The URL registered with backend during startup


def _kill_orphaned_ngrok():
    """Kill any orphaned ngrok processes from failed startups (ngrok free tier allows only 1 session)."""
    try:
        subprocess.run(["pkill", "-9", "-f", "ngrok"], capture_output=True, timeout=2)
        log.info("[NGROK_CLEANUP] Killed any orphaned ngrok processes")
        time.sleep(1)  # Give OS time to release port
    except Exception as e:
        log.warning(f"[NGROK_CLEANUP] Could not kill ngrok processes: {e}")


def _normalize_requested_proto(proto: str) -> str:
    p = (proto or "http").lower()
    if p not in {"http", "https", "tcp"}:
        return "http"
    return p


def _fetch_existing_tunnel(requested_proto: str):
    """Return a reusable ngrok public URL for the requested protocol if one exists."""
    try:
        resp = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        tunnels = resp.json().get("tunnels", [])

        # For HTTP requests, prefer https public URL first, then http.
        if requested_proto in {"http", "https"}:
            for t in tunnels:
                if t.get("proto") == "https":
                    return t.get("public_url")
            for t in tunnels:
                if t.get("proto") == "http":
                    return t.get("public_url")
            return None

        # For tcp, match exact proto.
        for t in tunnels:
            if t.get("proto") == requested_proto:
                return t.get("public_url")
    except Exception:
        return None
    return None


def start_ngrok(port, proto="http"):
    requested_proto = _normalize_requested_proto(proto)
    log.info(f"[NGROK] Requested tunnel proto={requested_proto} port={port}")

    # Fast path: cached URL if still valid in ngrok API.
    cached = _cached_tunnel_url_by_proto.get(requested_proto)
    if cached:
        existing = _fetch_existing_tunnel(requested_proto)
        if existing == cached:
            log.info(f"[NGROK_REUSE:CACHED] proto={requested_proto} url={cached}")
            return cached

    # Start ngrok and return public URL, but only if not already running
    import os
    authtoken = config.NGROK_AUTHTOKEN
    ngrok_cmd = ["ngrok", requested_proto, str(port), "--log=stdout"]
    config_path = os.path.expanduser("~/.config/ngrok/ngrok.yml")
    # Kill any orphaned ngrok processes before trying to start (ngrok free tier: 1 session limit)
    _kill_orphaned_ngrok()

    with _ngrok_lock:
        # Re-check existing/cached while locked to avoid races.
        cached = _cached_tunnel_url_by_proto.get(requested_proto)
        if cached:
            existing = _fetch_existing_tunnel(requested_proto)
            if existing == cached:
                log.info(f"[NGROK_REUSE:CACHED] proto={requested_proto} url={cached}")
                return cached

        existing = _fetch_existing_tunnel(requested_proto)
        if existing:
            _cached_tunnel_url_by_proto[requested_proto] = existing
            log.info(f"[NGROK_REUSE:EXISTING] proto={requested_proto} url={existing}")
            return existing

        # 0. Wait for FastAPI to be running on the target port before starting ngrok
        import socket
        max_wait = 10  # seconds
        waited = 0
        while waited < max_wait:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                s.close()
                log.info(f"FastAPI detected on port {port}.")
                break
            except Exception:
                s.close()
                time.sleep(1)
                waited += 1
        else:
            log.error(f"FastAPI not detected on port {port} after {max_wait} seconds. ngrok will not start.")
            return None

        # 1. Only add authtoken if not already present
        need_token = True
        if authtoken and os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    if authtoken in f.read():
                        need_token = False
            except Exception as e:
                log.error(f"Error reading ngrok config: {e}")
        if authtoken and need_token:
            result = subprocess.run(["ngrok", "config", "add-authtoken", authtoken], capture_output=True, text=True)
            if result.returncode != 0:
                log.error(f"ngrok authtoken error: {result.stderr}")
            else:
                log.info("ngrok authtoken added.")

        # 2. Start ngrok process only when no tunnel exists.
        try:
            log.info(f"[NGROK_START:NEW] {' '.join(ngrok_cmd)}")
            proc = subprocess.Popen(ngrok_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(5)
            if proc.poll() is not None:
                out, err = proc.communicate()
                log.error(f"ngrok failed to start. stdout: {out.decode(errors='ignore') if out else ''} stderr: {err.decode(errors='ignore') if err else ''}")

            url = _fetch_existing_tunnel(requested_proto)
            if url:
                _cached_tunnel_url_by_proto[requested_proto] = url
                log.info(f"[NGROK_READY] proto={requested_proto} url={url}")
                return url

            log.error("ngrok started but no usable tunnel found in API response.")
        except Exception as e:
            log.error(f"ngrok tunnel error: {e}")
        return None

def get_lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    if ip.startswith('127.'):
        # fallback: try hostname
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    return ip

def register_stream(stream_url, location, battery_level, ip_address=None, trigger_type="ai", status="active"):
    global _registered_stream_url
    url = f"{BACKEND_URL}/api/sentinels/register"
    # Enforce backend enums
    valid_status = {"active", "inactive", "alert"}
    valid_trigger = {"gpio", "microphone", "remote", "ai"}
    status = status.lower() if status and status.lower() in valid_status else "active"
    trigger_type = trigger_type.lower() if trigger_type and trigger_type.lower() in valid_trigger else "ai"
    if not ip_address or ip_address.startswith("127."):
        ip_address = get_lan_ip()
    payload = {
        "deviceId": DEVICE_ID,
        "location": location,
        "batteryLevel": battery_level,
        "ipAddress": ip_address,
        "status": status,
        "streamUrl": stream_url,
        "triggerType": trigger_type
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 201) and stream_url:
            _registered_stream_url = stream_url
            log.info(f"[REGISTERED_URL] Stored stream URL: {stream_url}")
        log.info(f"Stream registered: {payload} | Response: {resp.status_code}")
    except Exception as e:
        log.error(f"Stream registration failed: {e}")


def get_preferred_stream_url():
    """Return the globally preferred stream URL.

    - If NGROK_ENABLED is false: use LAN IP URL.
    - If NGROK_ENABLED is true: reuse registered URL, else reuse/start ngrok.
    """
    global _registered_stream_url

    if not bool(config.NGROK_ENABLED):
        lan_url = f"http://{get_lan_ip()}:{config.NGROK_HTTP_PORT}/stream"
        _registered_stream_url = lan_url
        log.info(f"[STREAM_URL:LAN] {lan_url}")
        return lan_url

    if _registered_stream_url:
        return _registered_stream_url

    tunnel = start_ngrok(config.NGROK_HTTP_PORT, proto="http")
    if tunnel:
        _registered_stream_url = f"{tunnel}/stream"
        return _registered_stream_url
    return None


def get_registered_stream_url():
    """Return the stream URL that was registered with backend during startup."""
    return _registered_stream_url
