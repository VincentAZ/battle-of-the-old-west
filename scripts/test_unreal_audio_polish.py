#!/usr/bin/env python3
"""Record legal supply/water actions and replay them with master mute.

Verifies new cues in Unreal's actual mix, not only asset existence. Other sound
families and subjective listening quality remain separate review work.
Run with a Python environment containing NumPy (the installed Blender Python
can be used). Check this dependency before launching the game.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import wave

from analyze_game_audio import analyze
from native_launch import create_native_run_directory, stop_owned_process_groups
from test_unreal_interactions import EDITOR, ROOT, InteractionScenario, write_json


class AudioScenario(InteractionScenario):
    def volume(self, value):
        self.command('a', 'settings', operation='open')
        self.command('a', 'settings', operation='edit', volume=value)
        self.command('a', 'settings', operation='apply')
        self.wait('master volume applied', lambda: abs(self.hud().get('settings', {}).get('volume', -1) - value) < .001)
        self.command('a', 'settings', operation='close')
        time.sleep(.5)

    def play_resources(self):
        draws, ends = 0, 0
        actions = []
        for _ in range(10):
            actor = next(n for n in ('a', 'b') if self.snapshot(n).get('actions'))
            offered = self.snapshot(actor)['actions']
            assert all(a['command']['type'] != 'choose' for a in offered), 'Unexpected choice during resource-only play'
            action = next((a for a in offered if a['command']['type'] == 'draw'), None) if draws == 0 else None
            action = action or next(a for a in offered if a['command']['type'] == 'end_turn')
            self.submit(actor, action)
            actions.append({'peer': actor, 'action': action})
            draws += action['command']['type'] == 'draw'
            ends += action['command']['type'] == 'end_turn'
            # Allow snapshot delivery to start its presentation, then observe
            # its natural completion. No Skip is used in either recording.
            time.sleep(.35)
            self.wait('resource presentation completes naturally',
                      lambda: self.hud().get('controls_visible') is True and
                      not self.read().get('cinematic', {}).get('busy'), 45)
            if draws >= 1 and ends >= 2:
                return actions
        raise AssertionError('Could not reach a legal draw and two turn transitions')

    def record(self, name):
        self.command('a', 'start_audio_capture')
        actions = self.play_resources()
        time.sleep(1.1)
        self.command('a', 'stop_audio_capture', name=name, directory=str(self.folder))
        path = self.folder / f'{name}.wav'

        def exported():
            try:
                with wave.open(str(path), 'rb') as wav:
                    return wav.getnframes() > 48000 and len(wav.readframes(wav.getnframes())) == wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            except (OSError, EOFError, wave.Error):
                return False

        self.wait('complete native audio export', exported)
        return {'recording': str(path), 'actions': actions, 'mix': analyze(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--port', type=int, default=19660)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if importlib.util.find_spec('numpy') is None:
        parser.error('Audio cue analysis requires NumPy. Run this script with a Python environment containing NumPy, such as Blender Python.')
    args.seed, args.ruleset, args.settle, args.audio = 731846, 'boomtown', .25, True
    output = args.output or create_native_run_directory('oldwest-audio-polish-')
    output.mkdir(parents=True, exist_ok=True)
    scenario = AudioScenario(args, output, (1280, 720), 0)
    result = {'ok': False, 'folder': str(scenario.folder), 'package_directory': str(args.package_dir) if args.package_dir else None,
              'limitations': ['Automated same-workstation play, not human listening review.',
                              'Only supply delivery, water delivery and master mute are required by this test.']}
    if args.package_dir:
        result['package_manifest'] = json.loads((scenario.runtime.package_root / 'package-manifest.json').read_text())
    try:
        scenario.boot()
        scenario.volume(1.)
        result['audible'] = scenario.record('audible-resource-actions')
        assert result['audible']['mix']['ok'], result['audible']['mix']['errors']
        events_path = scenario.folder / 'audible-events.json'
        with (scenario.folder / 'correlation-console.log').open('w') as log:
            subprocess.run([sys.executable, str(ROOT / 'scripts/check_game_audio_events.py'),
                            result['audible']['recording'], '--subtract-ambience', '--report', str(events_path)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        result['audible_events'] = json.loads(events_path.read_text())
        expected = {'SW_Supply_Delivery', 'SW_Water_Delivery'}
        detected = set(result['audible_events']['detected_one_shots'])
        assert expected <= detected, f'New cues not detected in the real mix: {sorted(expected - detected)}'
        scenario.capture('resource-review')
        scenario.volume(0.)
        result['muted'] = scenario.record('muted-resource-actions')
        muted = result['muted']['mix']
        assert muted['peak_dbfs'] is None or muted['peak_dbfs'] < -70, 'Master mute leaves audible game output'
        assert muted['clipped_samples'] == 0
        result.update(ok=True, captures=scenario.captures,
                      checks=['New water and supply cues detected in actual rendered game output.',
                              'Audible resource sequence has no PCM clipping.',
                              'Master mute silences a second legal resource sequence.'])
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        try:
            stop_owned_process_groups(scenario.processes.values(), scenario.streams)
        except Exception as error:
            result.update(ok=False, cleanup_error=str(error))
            raise
        finally:
            result['elapsed_seconds'] = round(time.monotonic() - scenario.started, 2)
            write_json(scenario.folder / 'result.json', result)
            print(json.dumps({k: v for k, v in result.items() if k in ('ok', 'folder', 'error', 'checks', 'elapsed_seconds')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
