
import numpy as np
from app.core import config

def _band_energy(fft_mags, freq_bins, freq_range):
    idx = np.where((freq_bins >= freq_range[0]) & (freq_bins <= freq_range[1]))[0]
    if len(idx) == 0:
        return 0.0
    return np.mean(fft_mags[idx])

def classify(audio_chunk, sample_rate=None):
    # FFT-based signature detection for speech, excavator, chainsaw
    audio_chunk = np.asarray(audio_chunk, dtype=np.float32)
    window_size = config.FFT_WINDOW_SIZE
    hop_size = config.FFT_HOP_SIZE
    sample_rate = float(sample_rate or config.SAMPLE_RATE)
    n_windows = (len(audio_chunk) - window_size) // hop_size + 1
    if n_windows < 1:
        return None, 0.0
    speech_energy = 0.0
    chainsaw_energy = 0.0
    excavator_energy = 0.0
    for i in range(n_windows):
        start = i * hop_size
        end = start + window_size
        window = audio_chunk[start:end] * np.hanning(window_size)
        fft = np.fft.rfft(window)
        mags = np.abs(fft)
        freqs = np.fft.rfftfreq(window_size, 1.0 / sample_rate)
        speech_energy += _band_energy(mags, freqs, config.SPEECH_FREQ_RANGE)
        chainsaw_energy += _band_energy(mags, freqs, config.CHAINSAW_FREQ_RANGE)
        excavator_energy += _band_energy(mags, freqs, config.EXCAVATOR_FREQ_RANGE)
    speech_energy /= n_windows
    chainsaw_energy /= n_windows
    excavator_energy /= n_windows
    # Decision logic
    if speech_energy > config.SPEECH_ENERGY_THRESHOLD:
        return "speech", float(speech_energy)
    elif chainsaw_energy > config.CHAINSAW_ENERGY_THRESHOLD:
        return "chainsaw", float(chainsaw_energy)
    elif excavator_energy > config.EXCAVATOR_ENERGY_THRESHOLD:
        return "excavator", float(excavator_energy)
    else:
        return None, 0.0
