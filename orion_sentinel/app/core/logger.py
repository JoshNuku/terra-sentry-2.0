import logging
import sys

logger = logging.getLogger("orion_sentinel")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s', "%Y-%m-%dT%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_logger():
    return logger
