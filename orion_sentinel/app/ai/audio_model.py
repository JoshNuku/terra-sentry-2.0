import numpy as np

class NoiseDetector:
    def __init__(self, alpha=0.05, sensitivity_factor=3.0):
        """
        alpha: Smoothing factor for the baseline noise floor tracker (0.01 to 0.1).
        sensitivity_factor: How many times greater the instant RMS must be 
                             compared to the baseline to trigger.
        """
        self.alpha = alpha
        self.sensitivity_factor = sensitivity_factor
        self.baseline_rms = None

    def classify(self, audio_chunk, sample_rate=None):
        audio_chunk = np.asarray(audio_chunk, dtype=np.float32)
        if len(audio_chunk) == 0:
            return None, 1.0
        
        # 1. Calculate current instantaneous RMS
        current_rms = np.sqrt(np.mean(audio_chunk**2))
        
        # Absolute silence guard (if the mic is completely quiet or disconnected)
        if current_rms < 0.001:
            return None, 1.0

        # 2. Initialize or update the slow-moving baseline noise floor
        if self.baseline_rms is None:
            self.baseline_rms = current_rms
            return None, 1.0
        
        # Exponential moving average to track ambient levels and AGC behavior
        self.baseline_rms = (self.alpha * current_rms) + ((1.0 - self.alpha) * self.baseline_rms)
        
        # 3. Calculate relative spike ratio (Signal-to-Noise Floor Ratio)
        ratio = float(current_rms / self.baseline_rms) if self.baseline_rms > 0 else 1.0
        
        # Check for a spike relative to the current baseline
        # Because the mic is at 60dB gain, we look for sudden multi-fold multipliers
        if current_rms > (self.baseline_rms * self.sensitivity_factor):
            return "suspicious_noise", ratio
            
        return None, ratio

# Global tracker instance to preserve the stateless function interface for the rest of the application
_detector = NoiseDetector()

def classify(audio_chunk, sample_rate=None):
    return _detector.classify(audio_chunk, sample_rate)
