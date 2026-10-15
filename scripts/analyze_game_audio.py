#!/usr/bin/env python3
"""Check a recording of Unreal's actual output mix, without claiming listening QA.

Accepts PCM16 WAV output from AudioMixer's recording API. Source effect files do
not demonstrate that in-game audio works; point this at a live match recording.
"""
import argparse
import array
import json
import math
import sys
import wave
from pathlib import Path


def dbfs(value):
    return round(20 * math.log10(value), 3) if value > 0 else None


def analyze(path):
    with wave.open(str(path), 'rb') as source:
        channels, rate, width = source.getnchannels(), source.getframerate(), source.getsampwidth()
        if width != 2 or source.getcomptype() != 'NONE':
            raise ValueError('Expected an uncompressed PCM16 output recording from Unreal AudioMixer.')
        samples = array.array('h', source.readframes(source.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples or channels < 1 or rate < 8000:
        raise ValueError('Recording has no usable PCM audio.')
    frame_count = len(samples) // channels
    peak = max(abs(value) for value in samples) / 32768.
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768.
    clipped = sum(value >= 32767 or value <= -32768 for value in samples)
    per_channel = []
    for channel in range(channels):
        values = samples[channel::channels]
        per_channel.append(dict(channel=channel,
            peak_dbfs=dbfs(max(abs(value) for value in values) / 32768.),
            rms_dbfs=dbfs(math.sqrt(sum(value * value for value in values) / len(values)) / 32768.),
            dc_offset=sum(values) / (len(values) * 32768.)))
    window_samples = max(1, rate // 10) * channels
    windows, quiet_duration, longest_quiet = [], 0., 0.
    for offset in range(0, len(samples), window_samples):
        values = samples[offset:offset + window_samples]
        window_rms = math.sqrt(sum(value * value for value in values) / len(values)) / 32768.
        duration = len(values) / (rate * channels)
        quiet_duration = quiet_duration + duration if window_rms < 10 ** (-75 / 20) else 0.
        longest_quiet = max(longest_quiet, quiet_duration)
        windows.append(dict(time_seconds=round(offset / (rate * channels), 3), rms_dbfs=dbfs(window_rms)))
    errors = []
    if frame_count / rate < 3:
        errors.append('Recording is shorter than three seconds; capture an actual gameplay sequence.')
    if rms < 10 ** (-65 / 20):
        errors.append('Output mix is silent or nearly silent overall.')
    if clipped:
        errors.append(f'Output mix contains {clipped} samples at the PCM limits; inspect for clipping.')
    return dict(ok=not errors, errors=errors, recording=str(path.resolve()),
        duration_seconds=round(frame_count / rate, 3), channels=channels, sample_rate=rate,
        peak_dbfs=dbfs(peak), rms_dbfs=dbfs(rms), clipped_samples=clipped,
        longest_near_silent_seconds=round(longest_quiet, 3), per_channel=per_channel,
        window_levels=windows,
        limitations=['Signal checks do not establish sound quality, event synchronization, or speaker playback.',
                     'This report only proves runtime mixing if its input was recorded from the live game.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = analyze(args.recording)
    output = args.report or args.recording.with_suffix('.levels.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'window_levels'}, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
