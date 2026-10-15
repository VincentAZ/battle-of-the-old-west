#!/usr/bin/env python3
"""Run an actual Unreal server and two RPC clients to match completion.

This check validates native networking and gameplay in the editor runtime or an
actual packaged executable. Rendered captures still need visual review; this
does not certify cinematic quality or internet NAT.
Only processes created by this script are stopped.
"""
import argparse
import json
import subprocess
import struct
import time
from pathlib import Path
from native_runtime_checks import assert_runtime_assets
from native_launch import create_native_run_directory, resolve_native_launch, game_net_driver_ports

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'

def public_state(report):
    state = json.loads(json.dumps(report['view']))
    state.pop('viewer', None)
    for player in state['players']:
        player.pop('hand', None)
        player.pop('offers', None)
        for column in player['columns']:
            for card in column:
                card.pop('private_peek', None)
                # Rules expose this owner-only legal-action explanation to
                # its viewer; it is not part of the shared public board.
                card.pop('ability_availability', None)
    state.pop('choice', None)
    return state

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--editor', type=Path, default=DEFAULT_EDITOR)
    parser.add_argument('--package-dir', type=Path, help='Test a cooked Linux package through the normal player launcher')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--port', type=int, default=19277)
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='base_2024')
    parser.add_argument('--render-client', action='store_true', help='Render client 0 offscreen and capture its actual UI')
    args = parser.parse_args()
    folder = create_native_run_directory('oldwest-native-match-')
    processes, streams = [], []
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    flags = ['-nosound', '-unattended', '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput']
    started = time.monotonic()

    def publish(result):
        names = ['latest-native-match.json', f'latest-native-match-{args.ruleset}.json']
        if args.package_dir:
            names += ['latest-packaged-match.json', f'latest-packaged-match-{args.ruleset}.json']
        report_dir = ROOT/'game/tests/reports'
        report_dir.mkdir(parents=True, exist_ok=True)
        for path in [folder/'result.json', *(report_dir/name for name in names)]:
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2)+'\n')
            temporary.replace(path)

    def launch(name, parameters, render=False):
        output = (folder/f'{name}-console.log').open('w')
        streams.append(output)
        graphics = ['-RenderOffscreen', '-windowed', '-ForceRes', '-ResX=1920', '-ResY=1080'] if render else ['-nullrhi']
        process = subprocess.Popen(runtime.argv + parameters + flags + graphics +
                                   [f'-abslog={folder/name}.log', f'-GameUserSettingsINI={folder}/{name}.GameUserSettings.ini'],
                                   cwd=runtime.cwd, env=runtime.env, stdout=output, stderr=subprocess.STDOUT)
        processes.append(process)
        return process

    print(f'Native match reports: {folder}', flush=True)
    try:
        map_url = f'/Game/Maps/WaterDepotV2?Match=1?Ruleset={args.ruleset}?game=/Script/OldWestGame.OldWestGameMode'
        clients = []
        def player_parameters(index, destination):
            parameters = [destination, '-game', '-OldWestTestBot', f'-OldWestReport={folder}/client-{index}.json']
            if args.render_client and index == 0:
                parameters += [f'-OldWestCapturePrefix={folder}/render', '-OldWestTestDelay=0.7']
            return parameters
        if args.package_dir:
            server = launch('client-0', player_parameters(0, map_url+'?listen') + [f'-port={args.port}'], render=args.render_client)
            clients.append(server)
        else:
            server = launch('server', [map_url, '-server', f'-port={args.port}'])
        start = time.monotonic()
        while time.monotonic()-start < 90:
            if server.poll() is not None:
                raise RuntimeError(f'Server exited ({server.returncode}); see {folder}/server-console.log')
            log = folder/('client-0.log' if args.package_dir else 'server.log')
            if log.exists() and args.port in game_net_driver_ports(log.read_text(errors='replace')):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Server did not start listening within 90 seconds')
        print('Host is listening. Connecting the remaining players.', flush=True)
        for i in range(len(clients), 2):
            parameters = player_parameters(i, f'127.0.0.1:{args.port}')
            clients.append(launch(f'client-{i}', parameters, render=args.render_client and i == 0))
        deadline = time.monotonic()+args.timeout
        last_progress = 0
        while time.monotonic() < deadline:
            if all((folder/f'client-{i}.json').exists() for i in range(2)):
                break
            for i, process in enumerate(clients):
                if process.poll() is not None:
                    raise RuntimeError(f'Client {i} exited ({process.returncode}); inspect its log')
            elapsed = int(time.monotonic()-start)
            if elapsed-last_progress >= 30:
                print(f'Two-client match still running ({elapsed}s).', flush=True)
                last_progress = elapsed
            time.sleep(0.5)
        else:
            raise RuntimeError('Two-client match did not finish before timeout')
        # Unreal may write a BOM-prefixed UTF-16 report when it contains
        # non-ASCII presentation text. json.loads detects that from bytes.
        reports = [json.loads((folder/f'client-{i}.json').read_bytes()) for i in range(2)]
        assert {r['seat'] for r in reports} == {0,1}, 'Two clients did not receive distinct seats'
        assert all(r['view']['status'] in ('won','draw') for r in reports), 'Match is not finished'
        assert public_state(reports[0]) == public_state(reports[1]), 'Clients disagree about final public state'
        assert all('hand' not in r['view']['players'][1-r['seat']] for r in reports), 'Private hand leaked'
        for r in reports:
            for p, player in enumerate(r['view']['players']):
                for column in player['columns']:
                    assert all('card_id' not in c for c in column if c.get('punk')), 'Punk identity leaked'
                    if p != r['seat']:
                        assert all('private_peek' not in c for c in column), 'Opponent punk inspection leaked'
        screenshots = sorted(folder.glob('render-*.png'))
        dimensions = []
        for path in screenshots:
            with path.open('rb') as stream:
                header = stream.read(24)
            assert header[:8] == b'\x89PNG\r\n\x1a\n', 'Invalid native screenshot'
            dimensions.append(struct.unpack('>II', header[16:24]))
        if args.render_client:
            assert len(screenshots) >= 2, 'Selection and gameplay screenshots were not captured'
            assert all(d == (1920, 1080) for d in dimensions), f'Native resolution mismatch: {dimensions}'
        log_names = ['client-0.log', 'client-1.log'] if args.package_dir else ['server.log', 'client-0.log', 'client-1.log']
        runtime_assets = assert_runtime_assets([folder/name for name in log_names])
        result = dict(ok=True, engine='Unreal 5.8.2', transport='native UDP over loopback',
                      runtime='packaged Linux game' if args.package_dir else 'Unreal Editor game runtime',
                      package_directory=str(args.package_dir.resolve()) if args.package_dir else None,
                      topology='listen host and remote guest' if args.package_dir else 'dedicated Editor server and two remote clients',
                      ruleset=args.ruleset,
                      clients=2, status=reports[0]['view']['status'], winner=reports[0]['view']['winner'],
                      revision=reports[0]['view']['revision'], turn=reports[0]['view']['turn'],
                      elapsed_seconds=round(time.monotonic()-start,2), logs=str(folder),
                      rendering_enabled=args.render_client,
                      screenshots=[str(p) for p in screenshots], screenshot_dimensions=dimensions,
                      runtime_assets=runtime_assets,
                      limitations=['Same-machine test', 'Internet connectivity not tested'] + ([] if args.render_client else ['Rendering disabled']))
        publish(result)
        print(json.dumps(result,indent=2),flush=True)
    except Exception as error:
        publish(dict(ok=False, runtime='packaged Linux game' if args.package_dir else 'Unreal Editor game runtime',
            package_directory=str(args.package_dir.resolve()) if args.package_dir else None,
            ruleset=args.ruleset, failure=str(error), logs=str(folder),
            elapsed_seconds=round(time.monotonic()-started, 2)))
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None: process.terminate()
        for process in reversed(processes):
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in streams: stream.close()

if __name__ == '__main__':
    run()
