# Silero VAD for Multi-Turn Voice Agent: Architecture Analysis

## Executive Summary

Silero VAD is well-suited for your use case with some important configuration considerations. The model natively supports 8kHz phone audio, has sub-millisecond latency, and provides tunable parameters for handling slow speech patterns. However, form entry scenarios (addresses, emails) require careful parameter tuning to avoid premature speech-end detection during natural pauses.

---

## Key Technical Findings

### Audio Compatibility

| Feature | Support Level | Notes |
|---------|---------------|-------|
| Phone Audio (8kHz) | ✅ Native | Uses 256-sample chunks (32ms windows) |
| Standard (16kHz) | ✅ Native | Uses 512-sample chunks (32ms windows) |
| Background Noise | ✅ Good | Trained on diverse audio conditions |
| Language Support | ✅ Excellent | 6000+ languages |

### Performance Characteristics

- **Model Size**: ~2.3MB (JIT/ONNX)
- **Latency**: <1ms per 32ms chunk on single CPU thread
- **Memory**: Minimal footprint, stateful LSTM architecture
- **Deployment**: CPU-only (no GPU required)

---

## Architecture for Multi-Turn Voice Agent

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VOICE AGENT PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌───────────────┐    ┌────────────────┐               │
│  │  Phone   │    │   Audio       │    │   Silero VAD   │               │
│  │  Input   │───▶│   Buffer      │───▶│   (Streaming)  │               │
│  │  8kHz    │    │   256 samples │    │   VADIterator  │               │
│  └──────────┘    └───────────────┘    └───────┬────────┘               │
│                                               │                         │
│                    ┌──────────────────────────┼──────────────────────┐  │
│                    │                          ▼                      │  │
│                    │    ┌─────────────────────────────────────────┐  │  │
│                    │    │         VAD Event Handler               │  │  │
│                    │    │  ┌─────────────────────────────────┐    │  │  │
│                    │    │  │ speech_start → Start buffering  │    │  │  │
│                    │    │  │ speech_end   → Process utterance│    │  │  │
│                    │    │  │ (ongoing)    → Continue buffer  │    │  │  │
│                    │    │  └─────────────────────────────────┘    │  │  │
│                    │    └─────────────────────────────────────────┘  │  │
│                    │                          │                      │  │
│                    │                          ▼                      │  │
│                    │    ┌─────────────────────────────────────────┐  │  │
│                    │    │      Utterance Accumulator              │  │  │
│                    │    │  (Collects speech until silence gap)    │  │  │
│                    │    │  min_silence: 800-1500ms for form entry │  │  │
│                    │    └─────────────────────────────────────────┘  │  │
│                    │                          │                      │  │
│                    └──────────────────────────┼──────────────────────┘  │
│                                               │                         │
│                                               ▼                         │
│                    ┌─────────────────────────────────────────────┐      │
│                    │              ASR Engine                      │      │
│                    │      (Whisper, Deepgram, etc.)               │      │
│                    └─────────────────────────────────────────────┘      │
│                                               │                         │
│                                               ▼                         │
│                    ┌─────────────────────────────────────────────┐      │
│                    │         Turn Management / Agent Logic        │      │
│                    │   (Form validation, next prompt decision)    │      │
│                    └─────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Streaming Implementation Pattern

```python
from silero_vad import load_silero_vad, VADIterator
import torch

class VoiceAgentVAD:
    """VAD handler optimized for form entry with slow/deliberate speech."""

    def __init__(self, sample_rate=8000):
        self.sample_rate = sample_rate
        self.model = load_silero_vad(onnx=True)  # ONNX for speed

        # Tuned for phone audio + form entry
        self.vad_iterator = VADIterator(
            self.model,
            threshold=0.45,               # Slightly lower for phone quality
            sampling_rate=sample_rate,
            min_silence_duration_ms=800,  # KEY: Long silence tolerance
            speech_pad_ms=100             # Extra padding for natural boundaries
        )

        self.speech_buffer = []
        self.is_speaking = False
        self.silence_frames = 0

    def process_chunk(self, audio_chunk):
        """
        Process 256 samples (32ms) at 8kHz.
        Returns: None (no event), 'speech_start', or 'speech_end' with audio
        """
        chunk_tensor = torch.FloatTensor(audio_chunk)
        result = self.vad_iterator(chunk_tensor, return_seconds=True)

        if result is not None:
            if 'start' in result:
                self.is_speaking = True
                self.speech_buffer = [audio_chunk]
                return {'event': 'speech_start', 'time': result['start']}

            elif 'end' in result:
                self.is_speaking = False
                complete_audio = self._collect_buffer()
                self.speech_buffer = []
                return {
                    'event': 'speech_end',
                    'time': result['end'],
                    'audio': complete_audio
                }

        # Accumulate during speech
        if self.is_speaking:
            self.speech_buffer.append(audio_chunk)

        return None

    def _collect_buffer(self):
        return torch.cat([torch.FloatTensor(c) for c in self.speech_buffer])

    def reset(self):
        """Reset for new turn."""
        self.vad_iterator.reset_states()
        self.speech_buffer = []
        self.is_speaking = False
```

---

## Critical Configuration for Form Entry

### The Core Problem

When users speak addresses or emails slowly:
```
"My email is... [500ms pause] john... [300ms pause] dot... [400ms pause] smith..."
```

Default VAD settings (100ms silence threshold) will trigger multiple `speech_end` events, fragmenting the input.

### Recommended Parameter Tuning

| Parameter | Default | Form Entry Value | Rationale |
|-----------|---------|------------------|-----------|
| `threshold` | 0.5 | **0.4-0.5** | Phone audio has lower SNR; avoid false negatives |
| `min_silence_duration_ms` | 100 | **800-1500** | Tolerate thinking pauses during dictation |
| `speech_pad_ms` | 30 | **100-150** | Capture leading/trailing phonemes on low-quality audio |
| `neg_threshold` | auto | **0.25-0.35** | Less aggressive exit from speech state |

### Multi-Stage Silence Detection Strategy

For form entry, implement a **two-tier silence detector**:

```python
class FormEntryVAD:
    """
    Two-tier silence handling:
    - Tier 1: Short pauses (< 1s) - continue buffering
    - Tier 2: Long silence (> 1.5s) - finalize utterance
    """

    def __init__(self):
        self.model = load_silero_vad(onnx=True)

        # Primary VAD with LONG silence tolerance
        self.vad = VADIterator(
            self.model,
            threshold=0.45,
            sampling_rate=8000,
            min_silence_duration_ms=1500,  # Very tolerant
            speech_pad_ms=100
        )

        # Secondary tracking for activity
        self.last_speech_prob = 0.0
        self.frames_below_threshold = 0
        self.FINAL_SILENCE_FRAMES = 50  # ~1.6s at 32ms chunks

    def process_with_context(self, chunk, field_type='address'):
        """
        Context-aware processing based on form field type.
        """
        # Get raw speech probability for fine-grained control
        prob = self.model(torch.FloatTensor(chunk), 8000).item()

        # Adjust patience based on field type
        patience_map = {
            'address': 60,    # ~2s - addresses have many pauses
            'email': 50,      # ~1.6s - spelling is deliberate
            'phone': 40,      # ~1.3s - numbers are faster
            'name': 35,       # ~1.1s - names are quicker
        }

        patience = patience_map.get(field_type, 50)

        if prob < 0.35:
            self.frames_below_threshold += 1
        else:
            self.frames_below_threshold = 0

        # Final decision
        if self.frames_below_threshold > patience:
            return {'event': 'utterance_complete'}

        return None
```

---

## Phone Audio Specific Considerations

### Narrowband Audio Characteristics

Phone audio (8kHz) has:
- **Limited frequency range**: 300-3400 Hz (loses consonant clarity)
- **Compression artifacts**: G.711/G.729 codecs add noise
- **Variable latency**: Jitter affects chunk timing

### Recommendations

1. **Use 8kHz Mode Directly**
   ```python
   # Don't upsample - work in native sample rate
   model = load_silero_vad()
   vad = VADIterator(model, sampling_rate=8000)  # Native 8kHz
   ```

2. **Pre-filter Audio** (Optional)
   ```python
   # High-pass filter to remove phone line hum
   import torchaudio.transforms as T
   highpass = T.HighPassBiquad(8000, cutoff_freq=200)
   audio = highpass(audio)
   ```

3. **Buffer Jitter**
   - Implement a small ring buffer (100-200ms) before VAD
   - Smooths out network-induced chunk timing variations

---

## Architecture Patterns for Multi-Turn Agents

### Pattern 1: VAD-Gated ASR (Recommended)

```
Audio Stream → VAD → [speech segments only] → ASR → Agent
```

**Pros**: Efficient, only processes speech
**Cons**: Latency at speech start (must wait for VAD to trigger)

### Pattern 2: Continuous ASR with VAD Annotations

```
Audio Stream → ASR (always running)
            → VAD → [speech events] → Agent (for turn-taking)
```

**Pros**: Lower latency, streaming transcription
**Cons**: Higher compute, processes silence

### Pattern 3: Hybrid (Best for Form Entry)

```
Audio → Pre-filter VAD (WebRTC, low-latency)
                ↓
        [candidate speech]
                ↓
     Silero VAD (high-accuracy validation)
                ↓
        [confirmed speech] → ASR → Agent
```

The example in the repo (`microphone_and_webRTC_integration.py`) demonstrates this pattern.

---

## Potential Issues & Mitigations

### Issue 1: Premature End Detection

**Symptom**: "123... Main... Street" detected as 3 separate utterances
**Mitigation**:
- Increase `min_silence_duration_ms` to 1000-1500ms
- Implement timeout-based finalization instead of pure silence detection

### Issue 2: Slow Response After User Finishes

**Symptom**: Agent takes too long to respond after user stops speaking
**Mitigation**:
```python
# Adaptive silence detection
class AdaptiveVAD:
    def __init__(self):
        self.speech_duration = 0

    def get_silence_threshold(self):
        # Shorter threshold for longer utterances
        if self.speech_duration > 3.0:  # seconds
            return 600   # User likely done with long input
        else:
            return 1200  # Still dictating
```

### Issue 3: Phone Line Noise False Positives

**Symptom**: Background noise triggers speech detection
**Mitigation**:
- Increase `threshold` to 0.55-0.6
- Use WebRTC VAD as pre-filter (aggressiveness=3)
- Implement minimum speech duration requirement

### Issue 4: Crosstalk/Echo

**Symptom**: Agent's own output (via earpiece) triggers VAD
**Mitigation**:
- Implement echo cancellation or detection
- Suppress VAD during agent playback window + 200ms

---

## Quick Test Deployment Checklist

### Minimal Viable Test

```bash
# 1. Install dependencies
pip install silero-vad pyaudio numpy

# 2. Test script
python test_phone_vad.py --sample-rate 8000
```

### Test Script Template

```python
#!/usr/bin/env python3
"""Quick VAD test for phone-quality audio simulation."""

from silero_vad import load_silero_vad, VADIterator
import torch
import numpy as np

def simulate_phone_audio(wav_path):
    """Load audio and downsample to 8kHz phone quality."""
    import torchaudio
    wav, sr = torchaudio.load(wav_path)

    # Resample to 8kHz
    if sr != 8000:
        resampler = torchaudio.transforms.Resample(sr, 8000)
        wav = resampler(wav)

    # Mono
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)

    return wav.squeeze()

def test_vad_on_file(audio_path, min_silence_ms=1000):
    """Test VAD with form-entry optimized settings."""

    model = load_silero_vad(onnx=True)
    vad = VADIterator(
        model,
        threshold=0.45,
        sampling_rate=8000,
        min_silence_duration_ms=min_silence_ms,
        speech_pad_ms=100
    )

    audio = simulate_phone_audio(audio_path)
    chunk_size = 256  # 32ms at 8kHz

    events = []
    for i in range(0, len(audio) - chunk_size, chunk_size):
        chunk = audio[i:i+chunk_size]
        result = vad(chunk, return_seconds=True)

        if result:
            events.append({
                'time': i / 8000,
                'event': 'start' if 'start' in result else 'end',
                'value': result.get('start', result.get('end'))
            })
            print(f"[{i/8000:.2f}s] {events[-1]}")

    return events

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        test_vad_on_file(sys.argv[1])
    else:
        print("Usage: python test_phone_vad.py <audio_file.wav>")
```

### Evaluation Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Speech Detection Rate | >98% | Ground truth annotation comparison |
| False Trigger Rate | <2% | Silence/noise-only segments |
| End-of-Utterance Latency | <2s | Time from last speech to event |
| Fragmentation Rate | <5% | Utterances incorrectly split |

---

## Conclusion

**Will it work for your use case?** Yes, with proper tuning.

**Key Success Factors**:
1. Use **8kHz native mode** for phone audio
2. Set **min_silence_duration_ms to 800-1500ms** for form entry
3. Implement **context-aware silence thresholds** (address vs phone number)
4. Consider **two-stage VAD** (WebRTC pre-filter + Silero validation)
5. Add **adaptive finalization** based on speech duration

**Biggest Risk**: Premature end-of-speech detection during slow dictation. Mitigate with aggressive silence tolerance and user feedback mechanisms (e.g., "I heard 123 Main, is that correct?").

---

## Repository Reference

- **Cloned to**: `/tmp/silero-vad`
- **Core implementation**: `/tmp/silero-vad/src/silero_vad/utils_vad.py`
- **Streaming example**: `/tmp/silero-vad/examples/microphone_and_webRTC_integration/`
- **Documentation**: `/tmp/silero-vad/README.md`
