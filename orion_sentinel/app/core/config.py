import os

# Paths configuration with auto-discovery of best.onnx and coco.names
_models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models"))
_best_onnx = os.path.join(_models_dir, "best.onnx")
_default_tflite = os.path.join(_models_dir, "yolov5n.tflite")
_coco_names = os.path.join(_models_dir, "coco.names")
_coco_classes = os.path.join(_models_dir, "coco_classes.txt")

# Path to COCO classes file (prefer coco.names if present)
COCO_CLASSES_PATH = os.getenv(
    "COCO_CLASSES_PATH",
    _coco_names if os.path.exists(_coco_names) else _coco_classes
)

# Allowed classes for backend alerts
ALLOWED_CLASSES = ["excavator", "bus", "car", "motorcycle", "truck", "person"]

# --- Hardware/Model Parameters ---
# Audio
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
BUFFER_SECONDS = float(os.getenv("AUDIO_BUFFER_SECONDS", "1.0"))
MAX9814_ADC_CHANNEL = int(os.getenv("MAX9814_ADC_CHANNEL", "0"))  # A1

# Vision
YOLO_INPUT_SIZE = int(os.getenv("YOLO_INPUT_SIZE", "640"))
YOLO_CLASSES = ["excavator", "bus", "car", "motorcycle", "truck", "person"]

# Dynamic Model Path selection (prefer best.onnx if present)
YOLO_TFLITE_PATH = os.getenv(
    "YOLO_TFLITE_PATH",
    _best_onnx if os.path.exists(_best_onnx) else _default_tflite
)


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
EDGE_API_KEY = _get_env("EDGE_API_KEY", "orion-edge-key-dev")
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
TUNNEL_HTTP_PORT = _get_env("TUNNEL_HTTP_PORT", "8080", cast=int)
TUNNEL_PROVIDER = _get_env("TUNNEL_PROVIDER", "cloudflare")

