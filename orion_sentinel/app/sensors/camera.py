import numpy as np
from app.core import logger, config
import time

log = logger.get_logger()

class Camera:
    def __init__(self):
        try:
            from app.sensors.camera_singleton import picam2
            self.picam = picam2
            time.sleep(2)  # Camera warmup
        except Exception as e:
            log.error(f"Camera initialization error: {e}")
            self.picam = None

    def capture(self):
        try:
            if self.picam is None:
                raise RuntimeError("Camera not initialized")
            frame = self.picam.capture_array()
            return frame
        except Exception as e:
            log.error(f"Camera capture error: {e}")
            return None
