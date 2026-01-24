"""Simulate phone-quality audio degradation."""

import numpy as np


class PhoneAudioSimulator:
    """Simulates phone-quality audio degradation (8kHz narrowband)."""

    def __init__(self, input_rate: int = 16000, output_rate: int = 8000):
        self.input_rate = input_rate
        self.output_rate = output_rate

        # Phone bandpass filter (300-3400 Hz)
        try:
            from scipy.signal import butter
            self.sos = butter(4, [300, 3400], btype='band',
                             fs=input_rate, output='sos')
            self.use_filter = True
        except ImportError:
            print("Note: scipy not installed, skipping bandpass filter")
            self.use_filter = False

    def degrade(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply phone-quality degradation to audio.

        Applies:
        1. Bandpass filter (300-3400 Hz phone frequency range)
        2. Downsampling to 8kHz
        3. Subtle line noise
        4. Light compression (codec simulation)
        """
        # 1. Bandpass filter (phone frequency range)
        if self.use_filter:
            from scipy.signal import sosfilt
            audio = sosfilt(self.sos, audio).astype(np.float32)

        # 2. Downsample to 8kHz
        if self.input_rate != self.output_rate:
            ratio = self.input_rate // self.output_rate
            audio = audio[::ratio]

        # 3. Add subtle noise (simulates line noise)
        noise = np.random.normal(0, 0.002, len(audio)).astype(np.float32)
        audio = audio + noise

        # 4. Light compression (phone codecs compress dynamic range)
        audio = np.tanh(audio * 1.5) / 1.5

        return audio
