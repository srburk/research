"""Real-time streaming VAD with phone audio simulation."""

import collections
import queue
import sys
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pyaudio
import torch
from silero_vad import load_silero_vad

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


@dataclass
class VADConfig:
    """VAD configuration with all tunable parameters."""
    threshold: float = 0.5           # Speech probability threshold
    neg_threshold: float | None = None  # Below this = silence (default: threshold - 0.15)
    min_silence_duration_ms: int = 100  # Silence needed to end speech
    min_speech_duration_ms: int = 250   # Minimum speech duration to report
    speech_pad_ms: int = 30             # Padding on speech boundaries

    def __post_init__(self):
        if self.neg_threshold is None:
            self.neg_threshold = max(self.threshold - 0.15, 0.01)


class StreamingVADIterator:
    """
    Custom VAD iterator with configurable neg_threshold.

    Unlike silero's VADIterator, this allows tuning the negative threshold
    independently from the speech threshold - critical for noisy phone audio.
    """

    def __init__(self, model, sampling_rate: int, config: VADConfig):
        self.model = model
        self.sampling_rate = sampling_rate
        self.config = config

        # Convert ms to samples
        self.min_silence_samples = int(sampling_rate * config.min_silence_duration_ms / 1000)
        self.min_speech_samples = int(sampling_rate * config.min_speech_duration_ms / 1000)
        self.speech_pad_samples = int(sampling_rate * config.speech_pad_ms / 1000)

        # Chunk size
        self.window_size = 512 if sampling_rate == 16000 else 256

        self.reset_states()

    def reset_states(self):
        """Reset all state for new audio stream."""
        self.model.reset_states()
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
        self.speech_start_sample = 0

    def __call__(self, audio_chunk: torch.Tensor, return_seconds: bool = False) -> dict | None:
        """
        Process one audio chunk and return speech events.

        Returns:
            None: No event
            {'start': time}: Speech started
            {'end': time}: Speech ended
        """
        if not torch.is_tensor(audio_chunk):
            audio_chunk = torch.FloatTensor(audio_chunk)

        # Handle batched input
        if audio_chunk.dim() == 2:
            audio_chunk = audio_chunk.squeeze(0)

        window_size = len(audio_chunk)
        self.current_sample += window_size

        # Get speech probability from model
        prob = self.model(audio_chunk.unsqueeze(0), self.sampling_rate).item()

        # Speech detected - reset silence tracking
        if prob >= self.config.threshold and self.temp_end:
            self.temp_end = 0

        # Speech START
        if prob >= self.config.threshold and not self.triggered:
            self.triggered = True
            self.speech_start_sample = self.current_sample
            speech_start = max(0, self.current_sample - self.speech_pad_samples - window_size)

            if return_seconds:
                return {'start': round(speech_start / self.sampling_rate, 2)}
            return {'start': int(speech_start)}

        # Potential speech END - probability dropped below neg_threshold
        if prob < self.config.neg_threshold and self.triggered:
            if not self.temp_end:
                self.temp_end = self.current_sample

            silence_duration = self.current_sample - self.temp_end

            # Not enough silence yet - keep waiting
            if silence_duration < self.min_silence_samples:
                return None

            # Check minimum speech duration
            speech_duration = self.temp_end - self.speech_start_sample
            if speech_duration < self.min_speech_samples:
                # Too short - reset without reporting
                self.triggered = False
                self.temp_end = 0
                return None

            # Valid speech end
            speech_end = self.temp_end + self.speech_pad_samples - window_size
            self.triggered = False
            self.temp_end = 0

            if return_seconds:
                return {'end': round(speech_end / self.sampling_rate, 2)}
            return {'end': int(speech_end)}

        return None

    @property
    def probability(self) -> float:
        """Get last computed probability (for visualization)."""
        return getattr(self, '_last_prob', 0.0)


class StreamingVADTester:
    """Real-time VAD testing with microphone input."""

    def __init__(self, config: AudioConfig, vad_config: VADConfig,
                 degrade_audio: bool = True):
        self.config = config
        self.vad_config = vad_config
        self.audio_queue: queue.Queue = queue.Queue()
        self.running = False

        # Phone audio simulator
        self.degrade_audio = degrade_audio
        if degrade_audio:
            self.phone_sim = PhoneAudioSimulator(
                config.input_rate, config.output_rate
            )

        # Load Silero VAD model
        print("Loading Silero VAD model...")
        self.model = load_silero_vad(onnx=True)

        # Use our custom VAD iterator with configurable neg_threshold
        self.vad = StreamingVADIterator(
            self.model,
            sampling_rate=config.output_rate,
            config=vad_config
        )

        print(f"VAD config:")
        print(f"  threshold:         {vad_config.threshold}")
        print(f"  neg_threshold:     {vad_config.neg_threshold}")
        print(f"  min_silence_ms:    {vad_config.min_silence_duration_ms}")
        print(f"  min_speech_ms:     {vad_config.min_speech_duration_ms}")
        print(f"  speech_pad_ms:     {vad_config.speech_pad_ms}")

        # State tracking
        self.is_speaking = False
        self.speech_start_time: float | None = None
        self.speech_buffer: list = []
        self.total_speech_chunks = 0
        self.silence_chunk_count = 0

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

        # Show threshold markers on the bar
        thresh_pos = int(self.vad_config.threshold * 30)
        neg_thresh_pos = int(self.vad_config.neg_threshold * 30)

        state = "🎤 SPEECH" if self.is_speaking else "   silent"

        # Track silence duration during speech for debugging
        if self.is_speaking and prob < self.vad_config.neg_threshold:
            self.silence_chunk_count += 1
        else:
            self.silence_chunk_count = 0

        # Update state based on VAD result
        if result is not None:
            if 'start' in result:
                self.is_speaking = True
                self.speech_start_time = time.time()
                self.speech_buffer = [audio]
                self.total_speech_chunks = 1
                self.silence_chunk_count = 0
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

        # Real-time display with silence counter when in speech
        silence_info = ""
        if self.is_speaking and self.silence_chunk_count > 0:
            silence_ms = self.silence_chunk_count * self.config.chunk_ms
            target_ms = self.vad_config.min_silence_duration_ms
            silence_info = f" [silence: {silence_ms}/{target_ms}ms]"

        sys.stdout.write(f"\r{state} |{bar}| {prob:.2f}{silence_info}    ")
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
