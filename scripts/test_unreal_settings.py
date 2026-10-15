#!/usr/bin/env python3
"""Exercise native Settings through its normal local UI handlers and restart.

Uses a private GameUserSettings INI. Display changes are real engine requests;
the normal 15-second timer, Keep, Revert, and graceful Quit remain in charge.
The opt-in visual bridge is absent from shipping builds. No game state changes.
"""
import argparse
import array
import configparser
import json
import math
import struct
import subprocess
import time
import wave
from pathlib import Path
from native_launch import create_native_run_directory, resolve_native_launch

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--offscreen', action='store_true', help='Use an offscreen viewport instead of a desktop game window')
    parser.add_argument('--audio-only', action='store_true', help='Measure the real native mix at full volume and mute; skip the display suite')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    folder = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-settings-')
    folder.mkdir(parents=True, exist_ok=True)
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    base = runtime.argv
    ini = folder/'GameUserSettings.ini'
    report_path, control = folder/'client.json', folder/'client.control.json'
    process, streams, sequence, generation, last_report = None, [], 0, 0, {}
    started = time.monotonic()
    checks, captures, exits = [], {}, []

    def publish(result):
        result.update(executable_mode='packaged' if args.package_dir else 'editor-game',
                      package_dir=str(runtime.package_root) if runtime.package_root else None,
                      directory=str(folder), elapsed_seconds=round(time.monotonic()-started, 2),
                      exit_codes=exits)
        suite = 'master-audio' if args.audio_only else 'settings'
        targets = [folder/'result.json', ROOT/f'game/tests/reports/latest-native-{suite}.json']
        if runtime.package_root:
            targets.append(ROOT/f'game/tests/reports/latest-packaged-{suite}.json')
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2)+'\n')
            temporary.replace(target)

    def launch(first=False):
        nonlocal process, generation, last_report, sequence
        generation += 1
        last_report, sequence = {}, 0
        report_path.unlink(missing_ok=True)
        control.unlink(missing_ok=True)
        stream = (folder/f'client-{generation}-console.log').open('w')
        streams.append(stream)
        display = ['-windowed', '-ForceRes', '-ResX=1280', '-ResY=720'] if first else []
        if args.offscreen:
            display.append('-RenderOffscreen')
            # NullApplication advertises a small virtual desktop. Keep its
            # startup clamp from replacing the saved resolution on restart.
            # No ResX/ResY is supplied on restart: dimensions still come from
            # the real saved preferences. Desktop runs use normal OS bounds.
            if '-ForceRes' not in display:
                display.append('-ForceRes')
        sound = ['-AudioMixer'] if args.audio_only else ['-nosound']
        startup_map = [] if args.package_dir else ['/Game/Maps/WaterDepotV2']
        process = subprocess.Popen(base + startup_map + ['-game', *sound, '-unattended',
            '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput', '-OldWestLifecycleTest', '-OldWestVisualTest',
            f'-GameUserSettingsINI={ini}', f'-OldWestLifecycleReport={report_path}',
            f'-OldWestLifecycleControl={control}', f'-abslog={folder}/client-{generation}.log', *display],
            cwd=runtime.cwd, env=runtime.env, stdout=stream, stderr=subprocess.STDOUT)

    def read():
        nonlocal last_report
        try:
            last_report = json.loads(report_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return last_report

    def state():
        return read().get('hud', {}).get('settings', {})

    def wait(label, predicate, timeout=None):
        deadline = time.monotonic() + (timeout or args.timeout)
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Native process exited {process.returncode}; inspect {folder}')
            result = predicate()
            if result:
                return result
            time.sleep(.12)
        raise AssertionError(f'Timed out: {label}; inspect {folder}')

    def command(action, ack=True, **fields):
        nonlocal sequence
        sequence += 1
        temporary = control.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequence, action=action, **fields)))
        temporary.replace(control)
        if ack:
            wait(action, lambda: read().get('sequence', -1) >= sequence)

    def settings(operation, **fields):
        command('settings', operation=operation, **fields)

    def capture(name, expected):
        time.sleep(1)
        path = folder/f'{name}.png'
        path.unlink(missing_ok=True)
        command('screenshot', filename=str(path))

        def complete():
            try:
                data = path.read_bytes()
                return data if len(data) > 1000 and b'IEND' in data[-16:] else None
            except FileNotFoundError:
                return None

        data = wait(name, complete)
        dimensions = struct.unpack('>II', data[16:24])
        assert dimensions == expected, f'{name} viewport {dimensions}, expected {expected}'
        captures[name] = str(path)
        print(f'Captured {name} at {dimensions[0]}×{dimensions[1]}', flush=True)

    def saved():
        config = configparser.ConfigParser(strict=False)
        config.read(ini)
        return config

    def matches(width, height, quality=None, limit=None, volume=None, mode=2):
        value = state()
        return (value.get('width') == width and value.get('height') == height and value.get('window_mode') == mode
                and (quality is None or value.get('quality') == quality)
                and (limit is None or value.get('frame_limit') == limit)
                and (volume is None or abs(value.get('volume', -1)-volume) < .005))

    def stop():
        command('quit', ack=False)
        code = process.wait(timeout=35)
        exits.append(code)
        assert code == 0, f'Graceful Quit exit {code}; inspect {folder}'

    def passed(message):
        checks.append(message)
        print(f'PASS: {message}', flush=True)

    try:
        launch(first=True)
        wait('menu with settings support', lambda: state() and read().get('snapshot', {}).get('hosted') is False)
        assert state()['persistence_enabled']
        untouched_snapshot = read()['snapshot']
        settings('open')
        wait('720p settings panel', lambda: state()['open'] and matches(1280, 720))
        if args.audio_only:
            measurements = {}
            for label, volume in [('audible', 1.), ('muted', 0.)]:
                settings('edit', quality=1, frame_limit=60, volume=volume)
                settings('apply')
                wait(f'{label} volume', lambda: matches(1280, 720, 1, 60, volume))
                time.sleep(1)
                path = folder/f'{label}.wav'
                path.unlink(missing_ok=True)
                command('start_audio_capture')
                time.sleep(3)
                command('stop_audio_capture', name=label, directory=str(folder))

                def complete_wave():
                    try:
                        with wave.open(str(path), 'rb') as source:
                            if source.getsampwidth() != 2 or source.getnframes() < 24000:
                                return None
                            payload = source.readframes(source.getnframes())
                            if len(payload) != source.getnframes()*source.getnchannels()*2:
                                return None
                            return source.getnchannels(), source.getframerate(), payload
                    except (FileNotFoundError, wave.Error, EOFError):
                        return None

                channels, rate, payload = wait(f'{label} native WAV export', complete_wave)
                samples = array.array('h', payload)
                peak = max(abs(sample) for sample in samples)/32768
                rms = math.sqrt(sum(sample*sample for sample in samples)/len(samples))/32768
                measurements[label] = dict(path=str(path), channels=channels, sample_rate=rate,
                    frames=len(samples)//channels, peak=peak, rms=rms)
            assert measurements['audible']['rms'] > .00001, 'Full-volume native menu mix is silent'
            assert measurements['muted']['rms'] < max(.00001, measurements['audible']['rms']*.01), 'Master mute failed to silence the real mix'
            assert read()['snapshot'] == untouched_snapshot
            stop()
            result = dict(ok=True, checks=['Master volume controls the actual native output mix; mute reduces RMS by at least 40 dB.'],
                          measurements=measurements, directory=str(folder), elapsed_seconds=round(time.monotonic()-started, 2),
                          exit_codes=exits, executable_mode='packaged' if args.package_dir else 'editor-game')
            publish(result)
            print(json.dumps(result, indent=2), flush=True)
            return
        capture('01-settings-720p', (1280, 720))

        for quality in range(4):
            settings('edit', quality=quality, frame_limit=60, volume=.37)
            settings('apply')
            wait(f'quality preset {quality}', lambda: matches(1280, 720, quality, 60, .37) and not state()['pending'])
        config = saved()
        assert abs(config.getfloat('OldWest.Audio', 'MasterVolume')-.37) < .005
        assert config.getfloat('/Script/Engine.GameUserSettings', 'FrameRateLimit') == 60
        passed('All four quality presets apply; frame cap and master volume persist in the isolated INI.')

        settings('edit', width=1600, height=900, quality=0, frame_limit=30, volume=.8)
        settings('apply')
        wait('display trial', lambda: state()['pending'])
        capture('02-display-confirmation', (1600, 900))
        config = saved()
        assert config.getint('/Script/Engine.GameUserSettings', 'ResolutionSizeX') == 1280
        assert abs(config.getfloat('OldWest.Audio', 'MasterVolume')-.37) < .005
        wait('real display timeout', lambda: not state()['pending'] and matches(1280, 720, 3, 60, .37), 22)
        capture('03-timeout-restored', (1280, 720))
        passed('The real 15-second timeout restores resolution, quality, frame cap, and audio without saving the trial.')

        for mode in (1, 0):
            settings('edit', window_mode=mode)
            settings('apply')
            wait(f'display mode {mode} trial', lambda: state()['pending'] and state()['window_mode'] == mode)
            settings('revert')
            wait('window mode reverted', lambda: not state()['pending'] and matches(1280, 720, 3, 60, .37))
        passed('Borderless and fullscreen mode trials both return to the prior window through Revert.')

        settings('edit', width=1920, height=1080, window_mode=2, quality=1, frame_limit=120, volume=.23)
        settings('apply')
        wait('1080p trial', lambda: state()['pending'])
        settings('keep')
        wait('1080p kept', lambda: not state()['pending'] and matches(1920, 1080, 1, 120, .23))
        capture('04-settings-1080p', (1920, 1080))
        assert read()['snapshot'] == untouched_snapshot
        passed('Keep confirms a 1080p window; all Settings operations leave the authoritative game snapshot unchanged.')

        # Closing settings and exiting during a new trial both cancel it.
        settings('edit', width=1280, height=720)
        settings('apply')
        wait('trial before closing panel', lambda: state()['pending'])
        settings('close')
        wait('close cancelled trial', lambda: not state()['pending'] and not state()['open'] and matches(1920, 1080))
        settings('open')
        settings('edit', width=1280, height=720)
        settings('apply')
        wait('trial before graceful exit', lambda: state()['pending'])
        stop()
        config = saved()
        assert config.getint('/Script/Engine.GameUserSettings', 'ResolutionSizeX') == 1920
        passed('Closing the panel and quitting during an unconfirmed trial both preserve the confirmed display preference.')

        launch()
        wait('saved preferences after process restart', lambda: matches(1920, 1080, 1, 120, .23))
        settings('open')
        capture('05-restarted-preferences', (1920, 1080))
        passed('A new native process restores confirmed display, quality, frame cap, and master volume.')

        # SIGTERM follows Unreal's graceful external exit path, bypassing our
        # menu Quit handler. Its documented Unix exit status is 128 + SIGTERM.
        settings('edit', width=1280, height=720)
        settings('apply')
        wait('trial before external graceful exit', lambda: state()['pending'])
        process.terminate()
        code = process.wait(timeout=35)
        exits.append(code)
        assert code == 143, f'Expected Unreal graceful SIGTERM status 143, got {code}'
        assert saved().getint('/Script/Engine.GameUserSettings', 'ResolutionSizeX') == 1920
        launch()
        wait('confirmed preferences after external exit', lambda: matches(1920, 1080, 1, 120, .23))
        stop()
        passed('An external graceful exit during a trial also preserves confirmed preferences; both normal Quit exits return zero.')

        result = dict(ok=True, checks=checks, screenshots=captures, exit_codes=exits, directory=str(folder),
                      elapsed_seconds=round(time.monotonic()-started, 2), offscreen=args.offscreen,
                      executable_mode='packaged' if args.package_dir else 'editor-game',
                      package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                      limitation='Master volume persistence is tested; this suite disables sound and does not measure the output mix.')
        publish(result)
        print(json.dumps(result, indent=2), flush=True)
    except BaseException as error:
        publish(dict(ok=False, failure_type=type(error).__name__, failure=str(error),
                     checks=checks, screenshots=captures,
                     measurements=locals().get('measurements', {}), offscreen=args.offscreen))
        raise
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    main()
