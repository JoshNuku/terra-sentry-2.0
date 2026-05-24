import requests
import random
import time
import datetime
from app.core import config, logger

log = logger.get_logger()

BACKEND_URL = config.BACKEND_URL
DEVICE_ID = config.DEVICE_ID


def get_battery_level():
    # Simulate battery level 90-100% with slow decay
    return random.randint(90, 100)

def heartbeat_loop(get_location, trigger_type="mic"):
    valid_status = {"active", "inactive", "alert"}
    valid_trigger = {"microphone", "remote", "ai"}
    while True:
        location = get_location()
        # Ensure enums are backend-compliant
        status = "active"
        trig = trigger_type.lower()
        if trig not in valid_trigger:
            trig = "microphone"
        payload = {
            "status": status,
            "location": location,
            "batteryLevel": get_battery_level(),
            "triggerType": trig
        }
        url = f"{BACKEND_URL}/api/sentinels/{DEVICE_ID}/status"
        try:
            headers = {"X-API-KEY": config.EDGE_API_KEY}
            resp = requests.put(url, json=payload, headers=headers, timeout=10)
            log.info(f"Heartbeat sent: {payload} | Response: {resp.status_code}")
        except Exception as e:
            log.error(f"Heartbeat failed: {e}")
        time.sleep(60)
