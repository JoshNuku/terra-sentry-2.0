import subprocess
import requests
import time
import threading
from app.core import config, logger

log = logger.get_logger()

BACKEND_URL = config.BACKEND_URL
DEVICE_ID = config.DEVICE_ID

_registered_stream_url = None  # The URL registered with backend during startup


def start_cloudflare_tunnel(port):
    import sys
    import re
    
    # Active cleanup of any orphaned cloudflared processes to prevent port conflicts or duplicate tunnels
    try:
        log.info("[CLOUDFLARE] Cleaning up any existing cloudflared instances...")
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "cloudflared"], capture_output=True)
    except Exception as e:
        log.warning(f"[CLOUDFLARE] Cleanup of existing cloudflared instances failed: {e}")

    cmd = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"]
    if sys.platform.startswith("win"):
        cmd[0] = "cloudflared.exe"

    log.info(f"[CLOUDFLARE] Starting Cloudflare Quick Tunnel: {' '.join(cmd)}")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        tunnel_url = None
        start_time = time.time()
        timeout = 15.0
        
        def read_stream():
            nonlocal tunnel_url
            for line in iter(proc.stderr.readline, ''):
                if not line:
                    break
                match = re.search(r'https://[a-zA-Z0-9.-]+\.trycloudflare\.com', line)
                if match:
                    tunnel_url = match.group(0)
                    log.info(f"[CLOUDFLARE] Created Quick Tunnel URL: {tunnel_url}")
                    break
                    
        t = threading.Thread(target=read_stream, daemon=True)
        t.start()
        
        while time.time() - start_time < timeout:
            if tunnel_url:
                return tunnel_url
            if proc.poll() is not None:
                log.error("[CLOUDFLARE] cloudflared process terminated prematurely")
                break
            time.sleep(0.5)
            
        log.error("[CLOUDFLARE] Timed out waiting for Cloudflare Tunnel URL")
        return None
    except Exception as e:
        log.error(f"[CLOUDFLARE] Failed to start cloudflared: {e}")
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
    valid_trigger = {"microphone", "remote", "ai"}
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
        headers = {"X-API-KEY": config.EDGE_API_KEY}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201) and stream_url:
            _registered_stream_url = stream_url
            log.info(f"[REGISTERED_URL] Stored stream URL: {stream_url}")
        log.info(f"Stream registered: {payload} | Response: {resp.status_code}")
    except Exception as e:
        log.error(f"Stream registration failed: {e}")


def get_preferred_stream_url():
    """Return the globally preferred stream URL.

    Attempts to start/reuse a Cloudflare tunnel by default. If that fails or
    TUNNEL_PROVIDER is explicitly set to 'none', falls back to direct local LAN IP stream.
    """
    global _registered_stream_url

    if _registered_stream_url:
        return _registered_stream_url

    provider = getattr(config, "TUNNEL_PROVIDER", "cloudflare").lower()

    if provider == "cloudflare":
        tunnel = start_cloudflare_tunnel(config.TUNNEL_HTTP_PORT)
        if tunnel:
            _registered_stream_url = f"{tunnel}/stream"
            log.info(f"[STREAM_URL:CLOUDFLARE] {_registered_stream_url}")
            return _registered_stream_url
        log.warning("[STREAM_URL] Cloudflare Quick Tunnel failed to start. Falling back to local LAN IP stream.")

    # Local LAN Fallback
    lan_url = f"http://{get_lan_ip()}:{config.TUNNEL_HTTP_PORT}/stream"
    _registered_stream_url = lan_url
    log.info(f"[STREAM_URL:LOCAL_FALLBACK] {lan_url}")
    return lan_url


def get_registered_stream_url():
    """Return the stream URL that was registered with backend during startup."""
    return _registered_stream_url
