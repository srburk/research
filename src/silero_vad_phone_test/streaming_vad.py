"""Real-time streaming VAD with phone audio simulation."""

import collections
import queue
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
import pyaudio
import torch
from silero_vad import load_silero_vad, VADIterator

from .phone_simulator import PhoneAudioSimulator


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


class StreamingVADTester:
    """Real-time VAD testing with microphone input."""

    def __init__(self, config: AudioConfig, vad_params: dict,
                 degrade_audio: bool = True):
        self.config = config
        self.audio_queue: queue.Queue = queue.Queue()
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
        self.speech_start_time: float | None = None
        self.speech_buffer: list = []
        self.total_speech_chunks = 0

        # PyAudio setup
        self.pa = pyaudio.PyAudio()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - runs in separate thread."""
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def _process_audio(self):
        """Main processing loop."""
        chunk_times: collections.deque = collections.deque(maxlen=100)

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

    def _handle_vad_result(self, result: dict | None, prob: float, audio: np.ndarray):
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

    def run(self, device_index: int | None = None):
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
