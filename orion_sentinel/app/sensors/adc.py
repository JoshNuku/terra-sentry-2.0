from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.ads1x15 import Pin
from adafruit_ads1x15.analog_in import AnalogIn
import board
import busio
from app.core import config

class ADC:
    def __init__(self, address):
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS1115(i2c, address=address)
            # Max out data rate for better audio responsiveness over I2C.
            if hasattr(self.ads, "data_rate"):
                self.ads.data_rate = int(config.ADS1115_DATA_RATE)
        except Exception as e:
            print(f"ADC initialization error: {e}")
            self.ads = None

    def read_channel(self, channel):
        try:
            if self.ads is None:
                raise RuntimeError("ADC not initialized")
            chan = AnalogIn(self.ads, getattr(Pin, f'A{channel}'))
            return chan.value
        except Exception as e:
            print(f"ADC read error: {e}")
            return None
