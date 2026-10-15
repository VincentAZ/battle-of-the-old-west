#!/usr/bin/env python3
"""Exercise the player's actual Host a Match flow with a second game process.

No dedicated server or injected rule state. The same harness can run a cooked
package through the player launcher. Only its own child processes are stopped.
"""
import argparse
import ipaddress
import json
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

from native_runtime_checks import assert_runtime_assets, assert_packaged_file_access
from native_launch import create_native_run_directory, resolve_native_launch, game_net_driver_ports, stop_owned_process_groups
from test_unreal_session_lifecycle import public_state

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='base_2024')
    parser.add_argument('--port', type=int, default=19289)
    parser.add_argument('--connect-host', type=ipaddress.IPv4Address, default=ipaddress.IPv4Address('127.0.0.1'),
                        help='Address of this test computer used by the guest; can exercise its local LAN address')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--render-host', action='store_true')
    parser.add_argument('--resolution', choices=['1280x720', '1920x1080'], default='1920x1080')
    parser.add_argument('--check-invite-layout', action='store_true',
                        help='Require all actual join-address buttons to fit inside the rendered HUD')
    parser.add_argument('--seed', type=int, help='Use a reproducible legal deal through the gated native test hook')
    parser.add_argument('--require-offer-card', action='append', default=[],
                        help='Require this camp in the host\'s initial offers')
    parser.add_argument('--check-camp-layout', action='store_true',
                        help='Check full camp descriptions while the host is waiting for a guest')
    parser.add_argument('--audio', action='store_true', help='Record the rendered host\'s actual full-match audio mix')
    parser.add_argument('--trace-packaged-files', action='store_true',
                        help='Trace the copied package\'s successful opens and reject source/engine dependencies')
    parser.add_argument('--require-shader-platform', choices=['VULKAN_SM5', 'VULKAN_SM6'])
    parser.add_argument('--require-nanite', action='store_true', help='Require a live Nanite terrain scene proxy')
    args = parser.parse_args()
    if args.audio and not args.render_host:
        parser.error('--audio requires --render-host')
    if args.trace_packaged_files and (not args.package_dir or not shutil.which('strace')):
        parser.error('--trace-packaged-files requires --package-dir and strace')
    if (args.require_shader_platform or args.require_nanite) and not args.render_host:
        parser.error('Renderer checks require --render-host')
    if args.check_invite_layout and not args.render_host:
        parser.error('--check-invite-layout requires --render-host')
    if args.check_camp_layout and not args.render_host:
        parser.error('--check-camp-layout requires --render-host')
    if args.seed is not None and not 0 <= args.seed < 2**64:
        parser.error('--seed must be an unsigned 64-bit integer')
    width, height = map(int, args.resolution.split('x'))
    folder = create_native_run_directory('oldwest-listen-host-', outside_project=args.trace_packaged_files)
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    processes, streams, sequences, expected_exits, last_reports = {}, [], {}, set(), {}
    checks, screenshots = [], []
    started = time.monotonic()

    def publish(result):
        names = ['latest-listen-host.json', f'latest-listen-host-{args.ruleset}.json']
        if args.package_dir:
            names += ['latest-packaged-listen-host.json', f'latest-packaged-listen-host-{args.ruleset}.json']
        report_dir = ROOT/'game/tests/reports'
        report_dir.mkdir(parents=True, exist_ok=True)
        for path in [folder/'result.json', *(report_dir/name for name in names)]:
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2)+'\n')
            temporary.replace(path)

    def launch(name, render=False):
        stream = (folder/f'{name}-console.log').open('w')
        streams.append(stream)
        graphics = ['-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}'] if render else ['-nullrhi']
        trace = ['strace', '-f', '-yy', '-s', '4096', '-e', 'trace=openat,openat2',
                 '-o', str(folder/f'{name}.files.trace')] if args.trace_packaged_files else []
        startup_map = [] if args.package_dir else ['/Game/Maps/WaterDepotV2']
        processes[name] = subprocess.Popen(trace + runtime.argv + startup_map + ['-game',
            '-OldWestTestBot', '-OldWestLifecycleTest', '-OldWestVisualTest', '-OldWestTestDelay=0.2',
            *([f'-OldWestTestSeed={args.seed}'] if args.seed is not None else []),
            f'-OldWestLifecycleControl={folder}/{name}.control.json',
            f'-OldWestLifecycleReport={folder}/{name}.json', f'-port={args.port}',
            f'-GameUserSettingsINI={folder}/{name}.GameUserSettings.ini',
            *([] if render and args.audio else ['-nosound']), '-unattended', '-nosplash', '-NoLiveCoding',
            '-stdout', '-FullStdOutLogOutput', f'-abslog={folder}/{name}.log', *graphics],
            cwd=runtime.cwd, env=runtime.env, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True)

    def read(name):
        try:
            last_reports[name] = json.loads((folder/f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            # UE's diagnostic Move briefly removes the destination. Retain the
            # last complete observation while waiting for a newer sequence.
            pass
        return last_reports.get(name, {})

    def snapshot(name):
        return read(name).get('snapshot', {})

    def wait(description, predicate, timeout=45):
        end = min(started + args.timeout, time.monotonic() + timeout)
        progress = time.monotonic()
        while time.monotonic() < end:
            for name, process in processes.items():
                if name not in expected_exits and process.poll() is not None:
                    raise RuntimeError(f'{name} exited ({process.returncode}); inspect {folder}')
            result = predicate()
            if result:
                return result
            if time.monotonic()-progress > 25:
                print(f'Waiting for {description}', flush=True)
                progress = time.monotonic()
            time.sleep(.1)
        raise AssertionError(f'Timed out: {description}; inspect {folder}')

    def command(client_name, action, acknowledge=True, **fields):
        sequences[client_name] = sequences.get(client_name, 0) + 1
        path = folder/f'{client_name}.control.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequences[client_name], action=action, **fields)))
        temporary.replace(path)
        if acknowledge:
            wait(f'{client_name} accepts {action}', lambda: read(client_name).get('sequence', -1) >= sequences[client_name], 15)

    def menu(name):
        return snapshot(name).get('hosted') is False

    def connected(name, count=2):
        return snapshot(name).get('hosted') and snapshot(name).get('connected') == count

    def agreement():
        host, guest = snapshot('host'), snapshot('guest')
        if not (connected('host') and connected('guest') and host.get('match_id') == guest.get('match_id')):
            return False
        for state in (host, guest):
            opponent = state['view']['players'][1-state['seat']]
            assert 'hand' not in opponent and 'offers' not in opponent, 'Opponent private cards leaked'
            for column in opponent['columns']:
                assert all('private_peek' not in card for card in column), 'Opponent private punk identity leaked'
        return public_state(host) == public_state(guest)

    def capture(label):
        if not args.render_host:
            return
        path = folder/f'{label}.png'
        command('host', 'screenshot', filename=str(path))
        def complete():
            if not path.exists(): return False
            data = path.read_bytes()
            return data if data.endswith(b'IEND\xaeB`\x82') else False
        data = wait('complete native screenshot', complete)
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert int.from_bytes(data[16:20], 'big') == width and int.from_bytes(data[20:24], 'big') == height
        screenshots.append(str(path))

    print(f'Actual listen-host test: {folder}', flush=True)
    try:
        launch('host', args.render_host)
        wait('host opens its menu', lambda: menu('host'), 90)
        command('host', 'host', ruleset=args.ruleset)
        wait('local host authenticates its own seat', lambda: connected('host', 1))
        capture('00-waiting-for-guest')
        if args.require_offer_card:
            current = snapshot('host')
            offered = {card['id'] for card in current['view']['players'][current['seat']]['offers']}
            assert set(args.require_offer_card) <= offered, f'Required long-description camps absent: {offered}'
        camp_layout = None
        if args.check_camp_layout:
            camp_layout = read('host').get('hud', {}).get('camp_options', [])
            (folder/'waiting-camp-option-layout.json').write_text(json.dumps(camp_layout, indent=2)+'\n')
            assert len(camp_layout) == 6, 'Expected six actual camp-option widgets in the waiting lobby'
            for option in camp_layout:
                actual, desired = option['allocated_size'], option['desired_size']
                assert all(a+.5 >= d for a, d in zip(actual, desired)), f'Waiting camp description is clipped: {option}'
            checks.append('All six waiting-lobby camp options allocate their complete wrapped text size')
        # Live telemetry can be published before the buffered UE log reaches
        # disk. Wait for the same named-driver evidence instead of failing a
        # correctly connected host on the first read (especially with null RHI).
        ports = wait('the host game-driver listener appears in the log',
            lambda: game_net_driver_ports((folder/'host.log').read_text(errors='replace')), 15)
        host_log = (folder/'host.log').read_text(errors='replace')
        platforms = re.findall(r'Metadata set\s*:\s*shaderplatform="([^"]+)"', host_log)
        rendering = {'shader_platform': platforms[-1] if platforms else None,
                     'terrain': read('host').get('cinematic', {}).get('terrain_renderer')}
        if args.require_shader_platform:
            assert rendering['shader_platform'] == args.require_shader_platform, \
                f'Unexpected actual shader platform: {rendering["shader_platform"]}'
        if args.require_nanite:
            assert rendering['terrain'] and rendering['terrain'].get('nanite_mesh_proxy') is True, \
                'The live terrain renderer is not a Nanite mesh proxy'
        address = f'{args.connect_host}:{ports[-1]}'
        invite_layout = None
        if args.check_invite_layout:
            hud = read('host').get('hud', {})
            buttons = hud.get('invite_buttons', [])
            hud_width, hud_height = hud.get('hud_size', [0, 0])
            assert buttons and hud_width > 0 and hud_height > 0, 'Join-address geometry was not recorded'
            endpoints = [button['endpoint'] for button in buttons]
            assert len(endpoints) == len(set(endpoints)), 'Duplicate join-address buttons'
            if not args.connect_host.is_loopback:
                assert address in endpoints, 'The address used by the guest is missing from the lobby'
            for button in buttons:
                x0, y0 = button['min']
                x1, y1 = button['max']
                assert button['visible'] and button['enabled'], f'Join button unavailable: {button["endpoint"]}'
                assert -1 <= x0 < x1 <= hud_width+1 and -1 <= y0 < y1 <= hud_height+1, \
                    f'Join button outside the HUD: {button}'
            for index, button in enumerate(buttons):
                for other in buttons[index+1:]:
                    assert (button['max'][0] <= other['min'][0]+1 or other['max'][0] <= button['min'][0]+1
                            or button['max'][1] <= other['min'][1]+1 or other['max'][1] <= button['min'][1]+1), \
                        'Join-address buttons overlap'
            invite_layout = {'hud_size': [hud_width, hud_height], 'buttons': buttons}
            checks.append('Every join-address button is visible, enabled, non-overlapping and inside the HUD')
        launch('guest')
        wait('guest opens its menu', lambda: menu('guest'), 90)
        command('guest', 'join', address=address)
        wait('listen host and guest agree', agreement)
        assert {snapshot(n)['seat'] for n in ('host', 'guest')} == {0, 1}
        checks.append('Host a Match creates a listen server and authenticates the local host plus one remote client')
        capture('01-hosted-selection')
        if args.audio:
            command('host', 'start_audio_capture')
        command('host', 'resume')
        command('guest', 'resume')
        wait('a complete legal two-player match', lambda: agreement() and snapshot('host')['view']['status'] in ('won', 'draw'), 180)
        command('host', 'pause')
        command('guest', 'pause')
        finished = snapshot('host')
        checks.append('Listen-host and remote client finish a legal match with matching public results and private hands')
        capture('02-finished-match')
        audio_report = None
        if args.audio:
            command('host', 'stop_audio_capture', name='full-match-mix', directory=str(folder))
            recording = folder/'full-match-mix.wav'
            def complete_audio():
                try:
                    with wave.open(str(recording), 'rb') as source:
                        frames = source.getnframes()
                        return frames > 0 and len(source.readframes(frames)) == frames*source.getnchannels()*source.getsampwidth()
                except (FileNotFoundError, EOFError, wave.Error):
                    return False
            wait('complete game-only audio recording', complete_audio, 20)
            from analyze_game_audio import analyze
            audio_report = analyze(recording)
            recording.with_suffix('.levels.json').write_text(json.dumps(audio_report, indent=2)+'\n')
            assert audio_report['ok'], 'Actual game audio failed its signal checks'
            audio_report = {key: value for key, value in audio_report.items() if key != 'window_levels'}
            checks.append('Live full-match audio is non-silent and has no clipped PCM samples')
        command('host', 'rematch')
        command('guest', 'rematch')
        wait('both players enter rematch selection', lambda: agreement() and snapshot('host')['view']['status'] == 'selection'
             and snapshot('host')['match_id'] != finished['match_id'])
        match_id = snapshot('host')['match_id']
        seat = snapshot('guest')['seat']
        checks.append('Two rematch votes create a fresh match within the same listen server')
        command('guest', 'leave')
        wait('guest leaves while the host keeps the match', lambda: menu('guest') and connected('host', 1))
        command('guest', 'join', address=address)
        wait('guest reclaims its reserved seat', agreement)
        assert snapshot('guest')['seat'] == seat and snapshot('guest')['match_id'] == match_id
        checks.append('Guest leaves and reclaims the same reserved seat and match')
        command('host', 'leave')
        wait('host closes the server and guest returns to menu', lambda: menu('host') and menu('guest'))
        checks.append('Host Leave shuts down hosting; the guest returns to a usable menu')
        for name in ('guest', 'host'):
            expected_exits.add(name)
            command(name, 'quit', acknowledge=False)
            wait(f'{name} quits gracefully', lambda: processes[name].poll() is not None, 30)
            assert processes[name].returncode == 0, f'{name} Quit exit code {processes[name].returncode}'
        checks.append('Both normal Quit actions exit with code zero')
        assets = assert_runtime_assets([folder/'host.log', folder/'guest.log'])
        file_access = None
        if args.trace_packaged_files:
            file_access = assert_packaged_file_access(
                [folder/'host.files.trace', folder/'guest.files.trace'], runtime.package_root,
                [ROOT, args.editor.resolve().parents[3]])
            checks.append('Copied package opens its cooked containers without opening source-project or installed-engine files')
        result = dict(ok=True, runtime='packaged Linux game' if args.package_dir else 'Unreal Editor game runtime',
            package_directory=str(args.package_dir.resolve()) if args.package_dir else None,
            ruleset=args.ruleset, transport='two local processes over loopback' if args.connect_host.is_loopback
                else 'two local processes using this computer\'s LAN address', endpoint=address,
            checks=checks, finished_status=finished['view']['status'], winner=finished['view']['winner'],
            rendered=args.render_host, resolution=[width, height], rendering=rendering,
            invite_layout=invite_layout, camp_layout=camp_layout, test_seed=args.seed,
            required_offer_cards=args.require_offer_card, screenshots=screenshots, runtime_assets=assets,
            audio=audio_report, file_access=file_access,
            elapsed_seconds=round(time.monotonic()-started, 2), logs=str(folder),
            limitations=['Same computer; two-machine and internet connectivity remain untested',
                         'Visual quality requires inspecting rendered captures'])
        publish(result)
        print(json.dumps(result, indent=2), flush=True)
    except Exception as error:
        publish(dict(ok=False, runtime='packaged Linux game' if args.package_dir else 'Unreal Editor game runtime',
            package_directory=str(args.package_dir.resolve()) if args.package_dir else None,
            ruleset=args.ruleset, failure=str(error), completed_checks=checks,
            rendered=args.render_host, screenshots=screenshots, logs=str(folder),
            elapsed_seconds=round(time.monotonic()-started, 2)))
        raise
    finally:
        stop_owned_process_groups(processes.values(), streams)


if __name__ == '__main__':
    main()
