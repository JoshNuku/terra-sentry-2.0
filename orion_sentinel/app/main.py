import threading
import time
from fastapi import FastAPI
from app.api import routes
from app.core import logger
from app.sensors import audio, gps
from app.services import detection_service, heartbeat_service

log = logger.get_logger()

from fastapi.middleware.cors import CORSMiddleware
from app.core import config

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)

# Shared state for location
global_location = {"lat": None, "lng": None}

def get_location():
    lat = global_location.get("lat")
    lng = global_location.get("lng")
    from app.core import config
    if lat is None or lng is None:
        return {"lat": config.DEFAULT_LAT, "lng": config.DEFAULT_LNG}
    return {"lat": lat, "lng": lng}

def gps_thread():
    def update_location():
        while True:
            event = gps.events.listen()
            if event.get("type") == "LOCATION_UPDATE":
                global_location["lat"] = event["lat"]
                global_location["lng"] = event["lng"]
    t = threading.Thread(target=update_location, daemon=True)
    t.start()


def start_background_threads():
    threads = []
    threads.append(threading.Thread(target=audio.audio_loop, daemon=True))
    threads.append(threading.Thread(target=gps.gps_loop, daemon=True))
    threads.append(threading.Thread(target=detection_service.detection_loop, args=(get_location,), daemon=True))
    threads.append(threading.Thread(target=heartbeat_service.heartbeat_loop, args=(get_location,), daemon=True))
    for t in threads:
        t.start()
    gps_thread()

    def watchdog():
        while True:
            for i, t in enumerate(threads):
                if not t.is_alive():
                    log.error(f"Background thread {i} died. Restarting...")
                    # Restart the thread
                    if i == 0:
                        threads[i] = threading.Thread(target=audio.audio_loop, daemon=True)
                    elif i == 1:
                        threads[i] = threading.Thread(target=gps.gps_loop, daemon=True)
                    elif i == 2:
                        threads[i] = threading.Thread(target=detection_service.detection_loop, args=(get_location,), daemon=True)
                    elif i == 3:
                        threads[i] = threading.Thread(target=heartbeat_service.heartbeat_loop, args=(get_location,), daemon=True)
                    threads[i].start()
            time.sleep(10)
    threading.Thread(target=watchdog, daemon=True).start()




def delayed_tunnel_and_registration():
    time.sleep(5)  # Wait 5 seconds to ensure FastAPI is listening
    log.info("Registering device with backend...")
    try:
        from app.services import stream_service, heartbeat_service
        location = get_location()
        battery_level = heartbeat_service.get_battery_level() if hasattr(heartbeat_service, "get_battery_level") else 100
        # Resolve preferred stream URL globally (LAN IP when TUNNEL_PROVIDER=none).
        stream_url = stream_service.get_preferred_stream_url()
        if not stream_url:
            log.error("Failed to resolve stream URL for registration.")
        # Register with actual stream URL (or None if still unavailable)
        stream_service.register_stream(
            stream_url=stream_url,
            location=location,
            battery_level=battery_level,
            ip_address=None,
            trigger_type="ai",
            status="active"
        )
    except Exception as e:
        log.error(f"Device registration failed: {e}")

@app.on_event("startup")
def on_startup():
    log.info("Starting background threads...")
    start_background_threads()
    threading.Thread(target=delayed_tunnel_and_registration, daemon=True).start()
