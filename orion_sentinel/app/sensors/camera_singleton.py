from picamera2 import Picamera2
from app.core import config

# Singleton Picamera2 instance for the entire app
picam2 = Picamera2()
picam2.configure(
	picam2.create_video_configuration(
		main={"size": config.CAMERA_RESOLUTION},
		controls={"FrameDurationLimits": (int(1_000_000 / max(1, config.CAMERA_FRAMERATE)), int(1_000_000 / max(1, config.CAMERA_FRAMERATE)))}
	)
)
picam2.start()
