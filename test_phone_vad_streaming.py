#!/usr/bin/env python3
"""
Real-time Silero VAD test with simulated phone audio quality.

This script captures microphone audio on Mac, degrades it to phone quality
(8kHz narrowband), and runs streaming VAD detection.

Requirements:
    pip install silero-vad pyaudio numpy scipy

Usage:
    python test_phone_vad_streaming.py
    python test_phone_vad_streaming.py --silence-ms 1200  # More tolerance for slow speech
    python test_phone_vad_streaming.py --no-degrade       # Skip phone quality simulation
"""

import argparse
import collections
import queue
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
import torch

try:
    import pyaudio
except ImportError:
    print("ERROR: pyaudio not installed.")
    print("  Mac: brew install portaudio && pip install pyaudio")
    print("  Or:  pip install pyaudio")
    sys.exit(1)

from silero_vad import load_silero_vad, VADIterator


@dataclass
class AudioConfig:
    """Audio configuration for phone simulation."""
    input_rate: int = 16000      # Mac mic typically 16kHz or higher
    output_rate: int = 8000      # Phone quality
    channels: int = 1
    chunk_ms: int = 32           # VAD window size
    format: int = pyaudio.paInt16

    @property
    def input_chunk_size(self) -> int:
        return int(self.input_rate * self.chunk_ms / 1000)

    @property
    def output_chunk_size(self) -> int:
        return int(self.output_rate * self.chunk_ms / 1000)  # 256 at 8kHz


class PhoneAudioSimulator:
    """Simulates phone-quality audio degradation."""

    def __init__(self, input_rate: int = 16000, output_rate: int = 8000):
        self.input_rate = input_rate
        self.output_rate = output_rate

        # Phone bandpass filter (300-3400 Hz)
        try:
            from scipy.signal import butter, sosfilt
            self.sos = butter(4, [300, 3400], btype='band',
                             fs=input_rate, output='sos')
            self.use_filter = True
        except ImportError:
            print("Note: scipy not installed, skipping bandpass filter")
            self.use_filter = False

    def degrade(self, audio: np.ndarray) -> np.ndarray:
        """Apply phone-quality degradation to audio."""
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


class StreamingVADTester:
    """Real-time VAD testing with microphone input."""

    def __init__(self, config: AudioConfig, vad_params: dict,
                 degrade_audio: bool = True):
        self.config = config
        self.audio_queue = queue.Queue()
        self.running = False

        # Phone audio simulator
        self.degrade_audio = degrade_audio
        if degrade_audio:
            self.phone_sim = PhoneAudioSimulator(
                config.input_rate, config.output_rate
            )

        # Load Silero VAD
        print("Loading Silero VAD model...")
        self.model = load_silero_vad(onnx=True)
        self.vad = VADIterator(
            self.model,
            sampling_rate=config.output_rate,
            **vad_params
        )
        print(f"VAD initialized with: {vad_params}")

        # State tracking
        self.is_speaking = False
        self.speech_start_time = None
        self.speech_buffer = []
        self.total_speech_chunks = 0

        # PyAudio setup
        self.pa = pyaudio.PyAudio()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - runs in separate thread."""
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def _process_audio(self):
        """Main processing loop."""
        chunk_times = collections.deque(maxlen=100)

        while self.running:
            try:
                raw_audio = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            start_time = time.perf_counter()

            # Convert to float32
            audio = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
            audio = audio / 32768.0  # Normalize to [-1, 1]

            # Apply phone degradation
            if self.degrade_audio:
                audio = self.phone_sim.degrade(audio)

            # Ensure correct chunk size for VAD (256 samples at 8kHz)
            expected_size = self.config.output_chunk_size
            if len(audio) != expected_size:
                # Resample/pad if needed
                if len(audio) > expected_size:
                    audio = audio[:expected_size]
                else:
                    audio = np.pad(audio, (0, expected_size - len(audio)))

            # Run VAD
            chunk_tensor = torch.FloatTensor(audio)
            result = self.vad(chunk_tensor, return_seconds=True)

            # Get raw probability for visualization
            prob = self.model(chunk_tensor.unsqueeze(0), self.config.output_rate).item()

            # Process result
            self._handle_vad_result(result, prob, audio)

            # Track processing time
            elapsed = (time.perf_counter() - start_time) * 1000
            chunk_times.append(elapsed)

            # Periodic stats
            if len(chunk_times) == 100:
                avg_ms = sum(chunk_times) / len(chunk_times)
                if avg_ms > 5:  # Only warn if slow
                    print(f"  [perf] Avg processing: {avg_ms:.1f}ms per chunk")

    def _handle_vad_result(self, result: dict, prob: float, audio: np.ndarray):
        """Handle VAD events and update display."""
        # Visual probability meter
        bar_len = int(prob * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        state = "🎤 SPEECH" if self.is_speaking else "   silent"

        # Update state based on VAD result
        if result is not None:
            if 'start' in result:
                self.is_speaking = True
                self.speech_start_time = time.time()
                self.speech_buffer = [audio]
                self.total_speech_chunks = 1
                print(f"\n{'='*60}")
                print(f"🎙️  SPEECH STARTED at {result['start']:.2f}s")
                print(f"{'='*60}")

            elif 'end' in result:
                duration = time.time() - self.speech_start_time if self.speech_start_time else 0
                self.is_speaking = False
                print(f"\n{'='*60}")
                print(f"🔇 SPEECH ENDED at {result['end']:.2f}s")
                print(f"   Duration: {duration:.2f}s ({self.total_speech_chunks} chunks)")
                print(f"{'='*60}\n")
                self.speech_buffer = []
                self.speech_start_time = None

        elif self.is_speaking:
            self.speech_buffer.append(audio)
            self.total_speech_chunks += 1

        # Real-time display (overwrite line)
        sys.stdout.write(f"\r{state} |{bar}| {prob:.2f}  ")
        sys.stdout.flush()

    def list_devices(self):
        """List available audio input devices."""
        print("\nAvailable audio input devices:")
        print("-" * 50)
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  [{i}] {info['name']}")
                print(f"      Sample rate: {int(info['defaultSampleRate'])}Hz")
        print("-" * 50)

    def run(self, device_index: int = None):
        """Start streaming VAD test."""
        self.list_devices()

        # Find default input device if not specified
        if device_index is None:
            device_index = self.pa.get_default_input_device_info()['index']

        device_info = self.pa.get_device_info_by_index(device_index)
        actual_rate = int(device_info['defaultSampleRate'])

        # Adjust config if device has different sample rate
        if actual_rate != self.config.input_rate:
            print(f"Note: Device sample rate is {actual_rate}Hz, adjusting...")
            self.config.input_rate = actual_rate
            if self.degrade_audio:
                self.phone_sim = PhoneAudioSimulator(actual_rate, self.config.output_rate)

        print(f"\nUsing device [{device_index}]: {device_info['name']}")
        print(f"Input: {self.config.input_rate}Hz → Output: {self.config.output_rate}Hz (phone quality)")
        print(f"Phone simulation: {'ON' if self.degrade_audio else 'OFF'}")
        print("\n" + "="*60)
        print("  Speak into your microphone. Try slow dictation like:")
        print("  'My email is... john... dot... smith... at... gmail'")
        print("  Press Ctrl+C to stop.")
        print("="*60 + "\n")

        # Open audio stream
        stream = self.pa.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.input_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.config.input_chunk_size,
            stream_callback=self._audio_callback
        )

        self.running = True
        stream.start_stream()

        # Start processing thread
        process_thread = threading.Thread(target=self._process_audio)
        process_thread.start()

        try:
            while stream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.running = False
            stream.stop_stream()
            stream.close()
            process_thread.join()
            self.pa.terminate()

        print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description="Test Silero VAD with simulated phone audio quality"
    )
    parser.add_argument(
        '--threshold', type=float, default=0.45,
        help='Speech detection threshold (default: 0.45)'
    )
    parser.add_argument(
        '--silence-ms', type=int, default=1000,
        help='Min silence duration in ms to end speech (default: 1000)'
    )
    parser.add_argument(
        '--pad-ms', type=int, default=100,
        help='Speech padding in ms (default: 100)'
    )
    parser.add_argument(
        '--device', type=int, default=None,
        help='Audio input device index (default: system default)'
    )
    parser.add_argument(
        '--no-degrade', action='store_true',
        help='Skip phone quality simulation (use raw mic audio)'
    )
    parser.add_argument(
        '--sample-rate', type=int, default=8000,
        choices=[8000, 16000],
        help='Target sample rate (default: 8000 for phone quality)'
    )

    args = parser.parse_args()

    config = AudioConfig(output_rate=args.sample_rate)

    vad_params = {
        'threshold': args.threshold,
        'min_silence_duration_ms': args.silence_ms,
        'speech_pad_ms': args.pad_ms,
    }

    tester = StreamingVADTester(
        config=config,
        vad_params=vad_params,
        degrade_audio=not args.no_degrade
    )

    tester.run(device_index=args.device)


if __name__ == '__main__':
    main()
