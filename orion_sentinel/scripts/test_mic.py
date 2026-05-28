import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
import time
import wave
import argparse
from datetime import datetime
import numpy as np
from app.sensors import adc
from app.core import config


SAMPLE_RATE = config.SAMPLE_RATE
CHANNEL = config.MAX9814_ADC_CHANNEL

adc_inst = adc.ADC(config.ADS1115_I2C_ADDRESS)
if adc_inst.ads is None:
    print("ADC hardware not initialized. Check wiring and I2C address.")
    exit(1)

def _resample_linear(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if len(x) == 0 or src_rate <= 0 or dst_rate <= 0 or src_rate == dst_rate:
        return x
    src_t = np.arange(len(x), dtype=np.float64) / float(src_rate)
    dst_len = max(1, int(round(len(x) * float(dst_rate) / float(src_rate))))
    dst_t = np.arange(dst_len, dtype=np.float64) / float(dst_rate)
    return np.interp(dst_t, src_t, x).astype(np.float32)


def monitor_levels(seconds: float):
    print(f"Monitoring ADC level for {seconds:.1f}s (tap/speak near mic)...")
    print("(normalized RMS matches the audio detector threshold)\n")
    start = time.time()
    end = start + seconds
    window = []
    last_print = start

    while time.time() < end:
        val = adc_inst.read_channel(CHANNEL)
        if val is None:
            val = 32768
        window.append(int(val))

        now = time.time()
        if now - last_print >= 1.0 and window:
            arr = np.array(window, dtype=np.float32)
            # Normalize to [-1, 1] just like audio_loop does
            normalized = (arr - 32768.0) / 32768.0
            # Compute RMS on normalized audio (what the detector uses)
            rms_normalized = float(np.sqrt(np.mean(normalized ** 2)))
            # Also show raw RMS for reference
            centered = arr - np.mean(arr)
            rms_raw = float(np.sqrt(np.mean(centered ** 2)))
            peak = float(np.max(np.abs(centered)))
            # Bar is now scaled to match thresholds (0.30 is current trigger)
            bar = "#" * min(50, int(rms_normalized * 100))
            print(f"norm_rms={rms_normalized:.4f} raw_rms={rms_raw:8.2f} peak={peak:8.2f} |{bar}")
            print(f"  (trigger threshold is 0.30, current value is {rms_normalized:.4f})")
            window = []
            last_print = now

        if SAMPLE_RATE > 0:
            time.sleep(1.0 / SAMPLE_RATE)


def record_to_wav(seconds: float, output_path: str, playback_rate: int):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Recording from ADC channel {CHANNEL} for {seconds:.1f}s...")
    start = time.time()
    end = start + seconds
    raw_samples = []

    # Capture until wall-clock duration is reached. This avoids assumptions about ADC throughput.
    while time.time() < end:
        val = adc_inst.read_channel(CHANNEL)
        if val is None:
            val = 32768
        raw_samples.append(int(val))
        if SAMPLE_RATE > 0:
            time.sleep(1.0 / SAMPLE_RATE)

    elapsed = max(1e-6, time.time() - start)
    effective_rate = max(1, int(round(len(raw_samples) / elapsed)))

    # ADS1115 values are 0..65535-ish; remove DC offset then normalize for audibility.
    pcm = np.array(raw_samples, dtype=np.float32) - 32768.0
    pcm = pcm - float(np.mean(pcm))
    peak = float(np.max(np.abs(pcm))) if len(pcm) else 0.0
    if peak > 0.0:
        pcm = (pcm / peak) * (0.9 * 32767.0)

    # Resample to a human-audible playback rate for easier listening.
    out_rate = max(1000, int(playback_rate))
    pcm = _resample_linear(pcm, effective_rate, out_rate)
    pcm = np.clip(pcm, -32768, 32767).astype(np.int16)

    with wave.open(output_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(out_rate)
        wav.writeframes(pcm.tobytes())

    print(f"Saved: {output_path}")
    print(f"Samples: {len(raw_samples)} | Effective sample rate: {effective_rate} Hz | Playback rate: {out_rate} Hz")
    if effective_rate < 2000:
        print("WARNING: Effective sample rate is very low for voice recording.")
        print("ADS1115 over I2C is usually too slow for intelligible audio; this output is amplified/resampled for diagnostics only.")


def main():
    parser = argparse.ArgumentParser(description="Record microphone ADC input to a WAV file")
    parser.add_argument("--seconds", type=float, default=5.0, help="Recording length in seconds")
    parser.add_argument("--out", type=str, default=None, help="Output WAV path")
    parser.add_argument("--playback-rate", type=int, default=8000, help="WAV playback sample rate")
    parser.add_argument("--monitor", action="store_true", help="Only monitor live level (no WAV output)")
    args = parser.parse_args()

    if args.monitor:
        monitor_levels(max(1.0, args.seconds))
        return

    if args.out:
        out_path = args.out
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(project_root, "recordings", f"mic_{ts}.wav")

    record_to_wav(max(0.1, args.seconds), out_path, max(1000, args.playback_rate))


if __name__ == "__main__":
    main()
