import serial
import time
from app.core import events, logger, config

log = logger.get_logger()

def parse_nmea_latlng(nmea_lat, nmea_dir):
    if not nmea_lat or not nmea_dir:
        return None
    try:
        deg = int(nmea_lat[:2])
        min_ = float(nmea_lat[2:])
        lat = deg + min_ / 60
        if nmea_dir in ["S", "W"]:
            lat = -lat
        return lat
    except Exception:
        return None

def gps_loop():
    try:
        ser = serial.Serial(config.GPS_UART_PORT, 9600, timeout=1)
    except Exception as e:
        log.warning(f"GPS unavailable: {e}, using default location")
        while True:
            try:
                event = {
                    "type": "LOCATION_UPDATE",
                    "lat": config.DEFAULT_LAT,
                    "lng": config.DEFAULT_LNG,
                    "sensor": "gps",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                }
                log.info(f"GPS fallback: {event}")
                events.emit(event)
                time.sleep(30)
            except Exception as e2:
                log.error(f"GPS fallback error: {e2}")
                time.sleep(5)
        return
    while True:
        try:
            line = ser.readline().decode(errors='ignore')
            if line.startswith("$GPGGA"):
                parts = line.split(",")
                lat = parse_nmea_latlng(parts[2], parts[3])
                lng = parse_nmea_latlng(parts[4], parts[5])
                if lat and lng:
                    event = {
                        "type": "LOCATION_UPDATE",
                        "lat": lat,
                        "lng": lng,
                        "sensor": "gps",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                    }
                    log.info(f"GPS update: {event}")
                    events.emit(event)
        except Exception as e:
            log.warning(f"GPS read error: {e}")
            time.sleep(5)
