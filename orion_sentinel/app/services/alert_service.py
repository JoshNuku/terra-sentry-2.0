import requests
import base64
import datetime
from app.core import config, logger

log = logger.get_logger()

BACKEND_URL = config.BACKEND_URL

# Exported allowed values so other modules (routes, tests) can validate consistently
VALID_TRIGGER_TYPES = {"microphone", "remote", "ai"}
VALID_THREAT_TYPES = {"person", "car", "truck", "motorcycle", "bus", "excavator", "suspicious_noise"}


def send_alert(sentinel_id, threat_type, confidence, location, image_data, trigger_type, triggered_sensors):
    url = f"{BACKEND_URL}/api/alerts"
    # Enforce backend enums
    trigger_type = trigger_type.lower() if trigger_type and trigger_type.lower() in VALID_TRIGGER_TYPES else None
    threat_type = threat_type.lower() if threat_type and threat_type.lower() in VALID_THREAT_TYPES else None
    if trigger_type is None:
        raise ValueError(f"Invalid triggerType: {trigger_type}. Must be one of {VALID_TRIGGER_TYPES}")
    if threat_type is None:
        raise ValueError(f"Invalid threatType: {threat_type}. Must be one of {VALID_THREAT_TYPES}")
    sentinel_id = sentinel_id.upper() if sentinel_id else None
    # Normalize triggered_sensors to a list of lowercase strings
    if triggered_sensors is None:
        triggered_sensors = []
    elif isinstance(triggered_sensors, str):
        triggered_sensors = [triggered_sensors]
    triggered_sensors = [str(s).lower() for s in triggered_sensors]

    payload = {
        "sentinelId": sentinel_id,
        "threatType": threat_type,
        "confidence": confidence,
        "location": location,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "imageData": image_data,
        "triggerType": trigger_type,
        "triggeredSensors": triggered_sensors
    }
    try:
        headers = {"X-API-KEY": config.EDGE_API_KEY}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        log.info(f"Alert sent: {payload} | Response: {resp.status_code}")
    except Exception as e:
        log.error(f"Failed to send alert: {e}")
