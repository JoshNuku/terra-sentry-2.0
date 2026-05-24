
import numpy as np

def classify(audio_chunk, sample_rate=None):
    # Calculate Root Mean Square (RMS) of normalized audio chunk (lightweight spike detection)
    audio_chunk = np.asarray(audio_chunk, dtype=np.float32)
    if len(audio_chunk) == 0:
        return None, 0.0
    
    rms = np.sqrt(np.mean(audio_chunk**2))
    # Threshold 0.02 is standard for capturing audio volume spike events
    if rms > 0.02:
        return "suspicious_noise", float(rms)
    return None, 0.0
