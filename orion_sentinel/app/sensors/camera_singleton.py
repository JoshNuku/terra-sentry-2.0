from app.core import config, logger

log = logger.get_logger()

try:
	from picamera2 import Picamera2
except Exception as e:
	Picamera2 = None
	log.error(f"Picamera2 import failed: {e}")

# Singleton Picamera2 instance for the entire app
picam2 = None

if Picamera2 is not None:
	try:
		picam2 = Picamera2()
		picam2.configure(
			picam2.create_video_configuration(
				main={"size": config.CAMERA_RESOLUTION},
				controls={"FrameDurationLimits": (int(1_000_000 / max(1, config.CAMERA_FRAMERATE)), int(1_000_000 / max(1, config.CAMERA_FRAMERATE)))}
			)
		)
		picam2.start()
	except Exception as e:
		log.error(f"Picamera2 initialization failed: {e}")
		picam2 = None
