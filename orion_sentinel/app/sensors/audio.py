
import time
import numpy as np
from app.core import events, logger, config
from app.sensors.adc import ADC
from app.ai import audio_model

log = logger.get_logger()


SAMPLE_RATE = config.SAMPLE_RATE
BUFFER_SECONDS = config.BUFFER_SECONDS
CHANNEL = config.MAX9814_ADC_CHANNEL

def audio_loop():
    adc = ADC(config.ADS1115_I2C_ADDRESS)
    if adc.ads is None:
        log.error("ADC hardware not initialized. Audio loop will not start.")
        return
    # ADS1115 over I2C cannot sustain 16kHz; cap requested rate to realistic hardware rate.
    target_rate = max(50, min(int(SAMPLE_RATE), int(config.ADS1115_DATA_RATE)))
    sleep_interval = 1.0 / float(target_rate)
    buffer_size = max(256, int(target_rate * BUFFER_SECONDS))
    last_trigger = 0
    min_trigger_interval = 15  # seconds
    status_log_interval = 60  # seconds
    last_status_log = 0
    windows_processed = 0
    triggers_since_last_status = 0
    recent_effective_hz = 0.0

    log.info(
        "Audio loop started: requested_rate=%sHz target_rate=%sHz buffer_size=%s samples",
        SAMPLE_RATE,
        target_rate,
        buffer_size,
    )
    while True:
        try:
            audio_buffer = []
            capture_start = time.time()
            for _ in range(buffer_size):
                val = adc.read_channel(CHANNEL)
                if val is None:
                    val = 32768
                audio_buffer.append(val)
                time.sleep(sleep_interval)
            capture_elapsed = max(1e-6, time.time() - capture_start)
            recent_effective_hz = float(len(audio_buffer)) / capture_elapsed
            audio_np = np.array(audio_buffer, dtype=np.float32)
            # Normalize to [-1, 1] for FFT
            audio_np = (audio_np - 32768) / 32768.0
            # FFT-based signature detection
            label, confidence = audio_model.classify(audio_np, sample_rate=recent_effective_hz)
            now = time.time()
            windows_processed += 1
            if label and confidence >= 3.0 and (now - last_trigger) > min_trigger_interval:
                event = {
                    "type": "AUDIO_TRIGGER",
                    "label": label,
                    "confidence": float(confidence),
                    "sensor": "mic",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
                }
                log.info(f"Audio trigger: {event}")
                events.emit(event)
                last_trigger = now
                triggers_since_last_status += 1

            # Non-intrusive health/status log once per minute.
            if now - last_status_log >= status_log_interval:
                log.info(
                    "Audio status: windows=%s effective_hz=%.1f last_label=%s last_confidence=%.3f triggers_last_min=%s",
                    windows_processed,
                    recent_effective_hz,
                    label or "none",
                    float(confidence or 0.0),
                    triggers_since_last_status,
                )
                last_status_log = now
                windows_processed = 0
                triggers_since_last_status = 0
        except Exception as e:
            log.error(f"Audio hardware/model error: {e}")
            time.sleep(2)
