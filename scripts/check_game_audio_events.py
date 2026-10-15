#!/usr/bin/env python3
"""Look for authored one-shot sounds in a recording of Unreal's actual mix.

Requires NumPy (available in the installed Blender Python). Normalized waveform
correlation distinguishes an ambient-only recording from audible action cues.
This supplements level checks; it does not judge sound quality or synchronization.
"""
import argparse
import json
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2 and wav.getcomptype() == 'NONE', 'Expected PCM16 WAV'
        assert wav.getframerate() == 48000, 'Expected native 48kHz recording'
        channels = wav.getnchannels()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float64)
    samples = samples.reshape(-1, channels)/32768.
    # The master device may export six channels with only front L/R active.
    active = np.any(samples != 0, axis=0)
    if not active.any():
        return np.zeros(len(samples)//3)
    return samples[:, active].mean(axis=1)[::3]


def correlate(mix, cue):
    if len(mix) < len(cue) or len(cue) == 0:
        return dict(correlation=0., time_seconds=None)
    cue = cue-cue.mean()
    cue_energy = np.dot(cue, cue)
    if cue_energy == 0:
        return dict(correlation=0., time_seconds=None)
    count = len(cue)
    fft_size = 1 << (len(mix)+count-1).bit_length()
    product = np.fft.rfft(mix, fft_size)*np.fft.rfft(cue[::-1], fft_size)
    covariance = np.fft.irfft(product, fft_size)[count-1:len(mix)]
    sums = np.r_[0., np.cumsum(mix)]
    squares = np.r_[0., np.cumsum(mix*mix)]
    variance = squares[count:]-squares[:-count]-(sums[count:]-sums[:-count])**2/count
    denominator = np.sqrt(np.maximum(variance, 0.)*cue_energy)
    values = np.divide(covariance, denominator, out=np.zeros_like(covariance), where=denominator > 1e-12)
    index = int(np.argmax(values))
    return dict(correlation=round(float(values[index]), 4), time_seconds=round(index/16000., 4), sample_offset=index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--threshold', type=float, default=.65)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--subtract-ambience', action='store_true',
                        help='Also inspect residuals after a strong waveform match to the authored wind loop')
    args = parser.parse_args()
    assert .5 <= args.threshold <= 1
    mix = read(args.recording)
    manifest = json.loads((ROOT/'art/audio/audio-manifest.json').read_text())
    ambient_fit, residual = None, None
    if args.subtract_ambience:
        wind = read(ROOT/manifest['assets']['SW_Ambience_WindIndustrial']['file'])
        repeated = np.tile(wind, int(np.ceil(len(mix)/len(wind)))+1)
        fit = correlate(repeated, mix)
        if fit['correlation'] >= .9:
            offset = fit['sample_offset']
            segment = repeated[offset:offset+len(mix)]
            gain = float(np.dot(segment, mix)/np.dot(segment, segment))
            if 0 < gain <= 2:
                residual = mix-gain*segment
                ambient_fit = dict(**fit, fitted_gain=round(gain, 6))
    rows = []
    for name, asset in manifest['assets'].items():
        if asset['loop']:
            continue
        cue = read(ROOT/asset['file'])
        raw = correlate(mix, cue)
        result, method = raw, 'raw_mix'
        if residual is not None:
            candidate = correlate(residual, cue)
            if candidate['correlation'] > raw['correlation']:
                result, method = candidate, 'fitted_ambience_residual'
        rows.append(dict(name=name, **result, method=method, raw_correlation=raw['correlation'],
                         detected=result['correlation'] >= args.threshold))
    rows.sort(key=lambda item: item['correlation'], reverse=True)
    detected = [row['name'] for row in rows if row['detected']]
    report = dict(ok=bool(detected), recording=str(args.recording.resolve()),
        duration_seconds=round(len(mix)/16000., 3), threshold=args.threshold,
        detected_one_shots=detected, candidates=rows, ambience_fit=ambient_fit,
        limitations=['A match is waveform evidence, not listening approval.',
                     'Undetected sounds may be absent, masked by other sounds, or altered by runtime processing.',
                     'Only cues actually present in this recording can be validated.',
                     'Ambience subtraction requires correlation >=0.9; residuals can also include compression and fit error.'])
    output = args.report or args.recording.with_suffix('.events.json')
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
