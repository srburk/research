"""CLI entry point for VAD testing."""

import argparse

from .streaming_vad import AudioConfig, StreamingVADTester


def main():
    """Main CLI entry point."""
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
