
import os
# Path to COCO classes file
COCO_CLASSES_PATH = os.getenv("COCO_CLASSES_PATH", os.path.join(os.path.dirname(__file__), "../../models/coco_classes.txt"))

# Allowed classes for backend alerts
ALLOWED_CLASSES = ["person", "truck", "car", "motorcycle", "bus"]
# --- Hardware/Model Parameters ---
# Audio
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
BUFFER_SECONDS = float(os.getenv("AUDIO_BUFFER_SECONDS", "1.0"))
MAX9814_ADC_CHANNEL = int(os.getenv("MAX9814_ADC_CHANNEL", "1"))  # A1

# Vision
YOLO_INPUT_SIZE = int(os.getenv("YOLO_INPUT_SIZE", "320"))
YOLO_CLASSES = ["person", "truck", "car", "motorcycle", "bus"]
YOLO_TFLITE_PATH = os.getenv("YOLO_TFLITE_PATH", os.path.join(os.path.dirname(__file__), "../../models/yolov5n.tflite"))



# FFT-based audio classification parameters
FFT_WINDOW_SIZE = int(os.getenv("FFT_WINDOW_SIZE", "1024"))
FFT_HOP_SIZE = int(os.getenv("FFT_HOP_SIZE", "512"))
SPEECH_FREQ_RANGE = (int(os.getenv("SPEECH_FREQ_MIN", "300")), int(os.getenv("SPEECH_FREQ_MAX", "3400")))
CHAINSAW_FREQ_RANGE = (int(os.getenv("CHAINSAW_FREQ_MIN", "80")), int(os.getenv("CHAINSAW_FREQ_MAX", "500")))
EXCAVATOR_FREQ_RANGE = (int(os.getenv("EXCAVATOR_FREQ_MIN", "20")), int(os.getenv("EXCAVATOR_FREQ_MAX", "200")))
SPEECH_ENERGY_THRESHOLD = float(os.getenv("SPEECH_ENERGY_THRESHOLD", "0.02"))
CHAINSAW_ENERGY_THRESHOLD = float(os.getenv("CHAINSAW_ENERGY_THRESHOLD", "0.05"))
EXCAVATOR_ENERGY_THRESHOLD = float(os.getenv("EXCAVATOR_ENERGY_THRESHOLD", "0.03"))

# AI verification window settings (multi-frame vote)
AI_VERIFY_FRAMES = int(os.getenv("AI_VERIFY_FRAMES", "8"))
AI_VERIFY_MIN_POSITIVE = int(os.getenv("AI_VERIFY_MIN_POSITIVE", "3"))

import os
import sys
from dotenv import load_dotenv, find_dotenv
from app.core.logger import get_logger

log = get_logger()

# Load .env.production if present, else .env
env_file = find_dotenv('.env.production') or find_dotenv('.env')
if env_file:
	load_dotenv(env_file)
else:
	log.warning("No .env or .env.production found. Using default config values.")

def _get_env(key, default=None, required=False, cast=str):
	val = os.getenv(key, default)
	if required and (val is None or val == ""):
		log.error(f"Missing required config: {key}")
		sys.exit(1)
	try:
		return cast(val)
	except Exception as e:
		log.error(f"Invalid value for {key}: {val} ({e})")
		sys.exit(1)


def _to_bool(val):
	return str(val).strip().lower() in {"1", "true", "yes", "on"}

BACKEND_URL = _get_env("BACKEND_URL", required=True)
DEVICE_ID = _get_env("DEVICE_ID", required=True)
DEFAULT_LAT = _get_env("DEFAULT_LAT", "5.6500", cast=float)
DEFAULT_LNG = _get_env("DEFAULT_LNG", "-0.1870", cast=float)
MAX9814_ADC_CHANNEL = _get_env("MAX9814_ADC_CHANNEL", "0", cast=int)
ADS1115_I2C_ADDRESS = _get_env("ADS1115_I2C_ADDRESS", "0x48", cast=lambda v: int(v, 16))
ADS1115_DATA_RATE = _get_env("ADS1115_DATA_RATE", "860", cast=int)
GPS_UART_PORT = _get_env("GPS_UART_PORT", "/dev/serial0")
CAMERA_RESOLUTION = _get_env("CAMERA_RESOLUTION", "1280,720", cast=lambda v: tuple(map(int, v.split(","))))
CAMERA_FRAMERATE = _get_env("CAMERA_FRAMERATE", "15", cast=int)
STREAM_TARGET_FPS = _get_env("STREAM_TARGET_FPS", "12", cast=int)
STREAM_JPEG_QUALITY = _get_env("STREAM_JPEG_QUALITY", "80", cast=int)
NGROK_AUTHTOKEN = _get_env("NGROK_AUTHTOKEN", "")
NGROK_ENABLED = _get_env("NGROK_ENABLED", "true", cast=_to_bool)
NGROK_HTTP_PORT = _get_env("NGROK_HTTP_PORT", "8080", cast=int)
NGROK_TCP_PORT = _get_env("NGROK_TCP_PORT", "8554", cast=int)
