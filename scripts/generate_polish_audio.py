#!/usr/bin/env python3
"""Author distinct action cues and extend the existing local audio manifest.

Requires NumPy. Existing WAVs are preserved; rerunning this script replaces
only its own deterministic assets. Reimport with import_polish_audio.py.
"""
import hashlib
import json
import math
from pathlib import Path
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/audio'
SR = 48000
GENERATOR = 'scripts/generate_polish_audio.py'


def noise(t, seed, low, high):
    rng = np.random.default_rng(seed)
    frequencies = np.fft.rfftfreq(len(t), 1 / SR)
    spectrum = np.fft.rfft(rng.normal(size=len(t)))
    spectrum *= (1 / np.sqrt(1 + (frequencies / high) ** 8)
                 / np.sqrt(1 + (low / np.maximum(frequencies, .001)) ** 8))
    spectrum[0] = 0
    result = np.fft.irfft(spectrum, n=len(t))
    return result / max(np.std(result), 1e-12)


def envelope(t, start, attack, decay):
    age = np.maximum(0, t - start)
    return (1 - np.exp(-age / attack)) * np.exp(-age / decay) * (t >= start)


def render(name):
    durations = {
        'SW_Water_Delivery': 1.05, 'SW_Supply_Delivery': .65,
        'SW_Deck_Shuffle': .85, 'SW_Ability_Mechanism': .72,
        'SW_Impact_Body_01': .38, 'SW_Impact_Body_02': .38,
        'SW_Melee_Swing': .32, 'SW_Event_Advance': .60, 'SW_Match_End': 1.8,
    }
    t = np.arange(round(durations[name] * SR)) / SR
    if name == 'SW_Water_Delivery':
        # Low slosh under a few rounded air bubbles and a damp container tap.
        x = noise(t, 6101, 100, 1200) * envelope(t, .025, .025, .17) * .22
        for i, start in enumerate((.045, .12, .23, .36, .49)):
            age = np.maximum(0, t - start)
            phase = 2 * math.pi * ((390 + i * 64) * age - 100 * age * age)
            x += np.sin(phase) * envelope(t, start, .004, .024) * .20
        x += np.sin(2 * math.pi * 165 * t) * envelope(t, .01, .002, .045) * .12
        return x, -19, 'Water slosh, rounded bubbles and a damp container tap.'
    if name == 'SW_Supply_Delivery':
        x = noise(t, 6201, 210, 1800) * envelope(t, .01, .012, .085) * .18
        x += noise(t, 6202, 60, 440) * envelope(t, .17, .003, .055) * .34
        return x, -21, 'Canvas scrape and a soft crate landing for incoming supplies.'
    if name == 'SW_Deck_Shuffle':
        x = np.zeros_like(t)
        for i, start in enumerate((.01, .07, .14, .24, .35, .46)):
            x += noise(t, 6300 + i, 500, 2600) * envelope(t, start, .003, .024) * (.22 - i * .014)
        return x, -23, 'Short staggered paper brushes for recycling the deck.'
    if name == 'SW_Ability_Mechanism':
        x = noise(t, 6401, 120, 1600) * envelope(t, .005, .002, .019) * .30
        x += noise(t, 6402, 280, 1100) * envelope(t, .035, .018, .095) * .09
        for hz, gain in ((183, .17), (367, .09), (711, .04)):
            x += np.sin(2 * math.pi * hz * t) * envelope(t, .11, .002, .062) * gain
        return x, -22, 'Lever latch, soft pneumatic travel and a damp mechanical detent.'
    if name.startswith('SW_Impact_Body_'):
        variant = int(name[-2:])
        x = noise(t, 6500 + variant, 45, 330) * envelope(t, .001, .0015, .032) * .55
        x += noise(t, 6510 + variant, 230, 1450) * envelope(t, .002, .001, .018) * .11
        return x, -18, 'Dull clothed-body impact without a wooden or metallic ring.'
    if name == 'SW_Melee_Swing':
        x = noise(t, 6601, 180, 1700) * np.exp(-.5 * ((t - .085) / .031) ** 2)
        return x, -24, 'Brief cloth and air movement for an unarmed attack.'
    if name == 'SW_Event_Advance':
        x = noise(t, 6701, 110, 1500) * envelope(t, .005, .002, .03) * .25
        x += noise(t, 6702, 80, 650) * envelope(t, .085, .003, .047) * .25
        return x, -22, 'Two restrained ratchet steps for a moving event queue.'
    x = np.zeros_like(t)
    # Neutral closure for either outcome; does not imply the local player won.
    for i, hz in enumerate((146.832, 220., 293.665)):
        age = np.maximum(0, t - i * .13)
        x += np.sin(2 * math.pi * hz * age) * envelope(t, i * .13, .02, .28) * .20
    x += noise(t, 6801, 70, 700) * envelope(t, .015, .02, .12) * .025
    return x, -21, 'Low open-fifth resolution marking the end of a match for both players.'


NAMES = ('SW_Water_Delivery', 'SW_Supply_Delivery', 'SW_Deck_Shuffle',
         'SW_Ability_Mechanism', 'SW_Impact_Body_01', 'SW_Impact_Body_02',
         'SW_Melee_Swing', 'SW_Event_Advance', 'SW_Match_End')


def main():
    manifest_path = OUT / 'audio-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['sample_rate'] == SR and manifest['pcm_bits'] == 16
    for name in NAMES:
        x, peak_db, description = render(name)
        x -= x.mean()
        for n, start in ((48, True), (1680, False)):
            fade = np.sin(np.linspace(0, math.pi / 2, min(n, len(x) // 2))) ** 2
            if start:
                x[:len(fade)] *= fade
            else:
                x[-len(fade):] *= fade[::-1]
        x *= 10 ** (peak_db / 20) / max(float(np.abs(x).max()), 1e-12)
        pcm = np.rint(x * 32767).astype('<i2')
        decoded = pcm.astype(np.float64) / 32768
        peak = float(np.abs(decoded).max())
        rms = float(np.sqrt(np.mean(decoded ** 2)))
        spectrum = np.abs(np.fft.rfft(decoded)) ** 2
        high = float(spectrum[np.fft.rfftfreq(len(decoded), 1 / SR) > 5000].sum() / spectrum.sum())
        dc = abs(float(decoded.mean()))
        assert np.isfinite(decoded).all() and 0 < peak < .36
        assert decoded[0] == decoded[-1] == 0 and dc < .0001 and high < .025
        path = OUT / f'{name}.wav'
        with wave.open(str(path), 'wb') as output:
            output.setparams((1, 2, SR, len(pcm), 'NONE', 'not compressed'))
            output.writeframes(pcm.tobytes())
        manifest['assets'][name] = dict(
            file=str(path.relative_to(ROOT)), unreal_path=f'/Game/Audio/{name}',
            generator=GENERATOR, duration_seconds=len(pcm) / SR, channels=1,
            loop=False, group='Effects', description=description,
            peak_dbfs=20 * math.log10(peak), rms_dbfs=20 * math.log10(rms),
            dc_absolute=dc, boundary_jump=0., clipped_samples=0,
            energy_above_5khz_fraction=high,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        print(f'{name}: {len(pcm)/SR:.2f}s, peak {20*math.log10(peak):.1f} dBFS')
    manifest['listening_qa'] = False
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
