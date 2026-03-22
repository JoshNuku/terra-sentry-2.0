import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
import time

from app.sensors import gps
import threading
threading.Thread(target=gps.gps_loop, daemon=True).start()



def print_gps():
    print("Listening for GPS events...")
    for event in gps.events.listen():
        if event.get("type") == "LOCATION_UPDATE":
            print(f"Lat: {event['lat']}, Lng: {event['lng']}")
        else:
            print(f"Other event: {event}")
        time.sleep(1)

if __name__ == "__main__":
    print_gps()
