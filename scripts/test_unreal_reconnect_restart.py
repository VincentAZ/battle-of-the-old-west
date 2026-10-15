#!/usr/bin/env python3
"""Test native seat authentication and private reconnect persistence across exits.

Runs real Unreal processes and ordinary RPCs. Test profiles are isolated under a
private per-run directory; credential values are never printed or copied into reports.
Includes unseated/malicious clients and verifies logs do not contain seat tokens.
"""
import argparse
import json
import stat
import subprocess
import time
from pathlib import Path
from native_launch import create_native_run_directory, game_net_driver_ports, resolve_native_launch

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path, help='Run an already cooked Development package instead of Unreal Editor')
    parser.add_argument('--port', type=int, default=19349)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='boomtown')
    args = parser.parse_args()
    folder = create_native_run_directory('oldwest-native-reconnect-')
    profiles = folder/'profiles'
    address = f'127.0.0.1:{args.port}'
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    base = runtime.argv
    active, all_processes, streams, sequences, generations, log_paths = {}, [], [], {}, {}, {}
    checks, private_tokens = [], set()
    last_reports = {}
    started = time.monotonic()

    def publish(result):
        directory = ROOT/'game/tests/reports'
        directory.mkdir(parents=True, exist_ok=True)
        names = ['latest-native-reconnect-restart.json']
        if args.package_dir:
            names += ['latest-packaged-reconnect-restart.json']
        for path in [folder/'result.json', *(directory/name for name in names)]:
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2)+'\n')
            temporary.replace(path)

    def launch(name, parameters):
        generations[name] = generations.get(name, 0)+1
        tag = f'{name}-{generations[name]}'
        stream = (folder/f'{tag}-console.log').open('w')
        streams.append(stream)
        log_paths[name] = folder/f'{tag}.log'
        process = subprocess.Popen(base + parameters +
            ['-nullrhi', '-nosound', '-unattended', '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput',
             '-OldWestLifecycleTest', '-OldWestVisualTest', f'-GameUserSettingsINI={folder}/{name}.settings.ini', f'-abslog={log_paths[name]}'],
            cwd=runtime.cwd, env=runtime.env, stdout=stream, stderr=subprocess.STDOUT)
        active[name] = process
        all_processes.append(process)

    def read(name):
        try:
            last_reports[name] = json.loads((folder/f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return last_reports.get(name, {})

    def snapshot(name):
        return read(name).get('snapshot', {})

    def wait(description, predicate, timeout=None):
        deadline = time.monotonic()+(timeout or args.timeout)
        progress = time.monotonic()
        while time.monotonic() < deadline:
            for name, process in active.items():
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited ({process.returncode}); inspect {folder}')
            result = predicate()
            if result:
                return result
            if time.monotonic()-progress > 25:
                print(f'Waiting: {description}', flush=True)
                progress = time.monotonic()
            time.sleep(.12)
        raise AssertionError(f'Timed out: {description}; inspect {folder}')

    def command(name, action, ack=True, **fields):
        sequences[name] = sequences.get(name, 0)+1
        path = folder/f'{name}.control.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequences[name], action=action, **fields)))
        temporary.replace(path)
        if ack:
            wait(f'{name} accepts {action}', lambda: read(name).get('sequence', -1) >= sequences[name])

    def menu(name):
        return snapshot(name).get('hosted') is False

    def connected(name, count=2):
        return snapshot(name).get('hosted') and snapshot(name).get('connected') == count

    def agree():
        a, b = snapshot('a'), snapshot('b')
        if not (connected('a') and connected('b') and a.get('match_id') == b.get('match_id')):
            return False
        if a['view']['revision'] != b['view']['revision']:
            return False
        for current in (a, b):
            enemy = current['view']['players'][1-current['seat']]
            assert 'hand' not in enemy and 'offers' not in enemy
            assert all('private_peek' not in card for column in enemy['columns'] for card in column)
        return True

    def checked(message):
        checks.append(message)
        print(f'PASS: {message}', flush=True)

    def start_server():
        map_url = f'/Game/Maps/WaterDepotV2?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={args.ruleset}'
        if args.package_dir:
            reset_client_control('b')
            launch('b', [map_url+'?listen', '-game', '-MULTIHOME=127.0.0.1', f'-port={args.port}',
                f'-OldWestLifecycleControl={folder}/b.control.json', f'-OldWestLifecycleReport={folder}/b.json',
                '-OldWestProfile=b', f'-OldWestProfileRoot={profiles}'])
        else:
            launch('server', [map_url, '-server', '-MULTIHOME=127.0.0.1', f'-port={args.port}'])
        name = 'b' if args.package_dir else 'server'
        wait('server listens', lambda: log_paths[name].exists() and
             args.port in game_net_driver_ports(log_paths[name].read_text(errors='replace')))
        if args.package_dir:
            wait('listen host authenticates', lambda: connected('b', 1))

    def reset_client_control(name):
        last_reports.pop(name, None)
        # A new process gets a new sequence namespace. Never replay its old Quit.
        for suffix in ('.json', '.control.json'):
            (folder/f'{name}{suffix}').unlink(missing_ok=True)
        sequences[name] = 0

    def start_client(name, profile=None, manual=False):
        reset_client_control(name)
        startup_map = [address] if manual else ([] if args.package_dir else ['/Game/Maps/WaterDepotV2'])
        parameters = startup_map + ['-game',
                      f'-OldWestLifecycleControl={folder}/{name}.control.json',
                      f'-OldWestLifecycleReport={folder}/{name}.json']
        if profile:
            parameters += [f'-OldWestProfile={profile}', f'-OldWestProfileRoot={profiles}']
        if manual:
            parameters.append('-OldWestManualSeatClaim')
        launch(name, parameters)
        if manual:
            wait('provisional client receives only public challenge', lambda: read(name).get('seat_challenge'))
            assert read(name)['seat'] == -1 and snapshot(name) == {}
        else:
            wait(f'{name} menu loads', lambda: menu(name))

    def stop_client(name, crash=False):
        process = active[name]
        if crash:
            del active[name]
            process.kill()
            process.wait(timeout=15)
        else:
            command(name, 'quit', ack=False)
            del active[name]
            code = process.wait(timeout=30)
            assert code == 0, f'Graceful Quit returned {code}; inspect {folder}'

    def stored(name):
        path = profiles/name/'reconnect.json'
        record = json.loads(path.read_text())
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert record['version'] == 1 and record['endpoint'] == address
        private_tokens.add(record['token'])
        return record

    def join(name):
        command(name, 'join', address=address)

    def submit(name, action):
        current = snapshot(name)
        revision = current['view']['revision']
        command(name, 'submit', command=action['command'], revision=revision, match_id=current['match_id'])
        wait('legal action synchronizes', lambda: agree() and snapshot(name)['view']['revision'] > revision)

    print(f'Native reconnect reports: {folder}', flush=True)
    try:
        start_server()
        start_client('a', 'a')
        assert read('a')['profile_enabled'] and not read('a')['profile_loaded']
        if not args.package_dir:
            join('a')
            wait('first seat authenticates', lambda: connected('a', 1))
            wait('first seat is saved', lambda: (profiles/'a/reconnect.json').exists())
            first_profile = stored('a')

        start_client('attacker', manual=True)
        witness = 'b' if args.package_dir else 'a'
        before = snapshot(witness)
        command('attacker', 'submit', command={'type': 'end_turn'}, revision=before['view']['revision'], match_id=before['match_id'])
        time.sleep(.2)
        assert snapshot('attacker') == {} and snapshot(witness) == before
        command('attacker', 'claim_seat', token='0'*32)
        wait('invalid claim is rejected', lambda: menu('attacker') and read('attacker').get('seat_rejections', 0) == 1)
        assert not read('attacker')['has_seat_token'] and not read('attacker')['profile_enabled']
        assert connected(witness, 1) and snapshot(witness) == before
        stop_client('attacker')
        checked('Provisional clients receive no private snapshot; invalid credentials cannot claim even an unused seat or submit moves')

        if args.package_dir:
            join('a')
        else:
            start_client('b', 'b')
            join('b')
        wait('two authenticated clients synchronize', agree)
        first_profile = stored('a')
        if args.package_dir:
            assert not read('b')['has_seat_token'] and not (profiles/'b/reconnect.json').exists()
            checked('Remote guest stores its credential in a private profile; listen hosting does not create a remote credential')
        else:
            second_profile = stored('b')
            assert first_profile['token'] != second_profile['token']
            assert first_profile['server_session'] == second_profile['server_session']
            checked('Two explicit test profiles store distinct credentials in private directories and files')

        start_client('third')
        assert not read('third')['profile_enabled'] and not read('third')['has_seat_token']
        join('third')
        wait('third client is rejected', lambda: menu('third') and read('third').get('seat_rejections', 0) > 0)
        assert not read('third')['has_seat_token'] and agree()
        stop_client('third')
        start_client('duplicate', 'a')
        assert read('duplicate')['profile_loaded']
        join('duplicate')
        wait('duplicate live seat is rejected', lambda: menu('duplicate') and 'already connected' in read('duplicate').get('notice', ''))
        assert agree()
        stop_client('duplicate')
        checked('Full-server and duplicate-seat claims are rejected without displacing either player; implicit test profiles stay disabled')

        for name in ('a', 'b'):
            submit(name, snapshot(name)['actions'][0])
        baseline = [snapshot(name) for name in ('a', 'b')]
        assert baseline[0]['view']['status'] == 'actions'
        saved_seat = snapshot('a')['seat']
        stop_client('a')
        wait('graceful exit reserves seat', lambda: connected('b', 1))
        start_client('a', 'a')
        assert read('a')['profile_loaded'] and read('a')['has_seat_token'] and read('a')['last_address'] == address
        join('a')
        wait('restarted application resumes exact match', agree)
        assert snapshot('a')['seat'] == saved_seat and read('a')['same_seat_token']
        assert [snapshot(name) for name in ('a', 'b')] == baseline
        checked('Graceful Quit exits successfully; a new process loads its saved credential and resumes the exact private/public match state')

        stop_client('a', crash=True)
        wait('server detects real process death', lambda: connected('b', 1), 40)
        start_client('a', 'a')
        join('a')
        wait('process restart after kill resumes seat', agree)
        assert [snapshot(name) for name in ('a', 'b')] == baseline
        checked('A killed client process can restart and reclaim its reserved seat without depending on a shutdown save')

        original_store = (profiles/'a/reconnect.json').read_bytes()
        command('a', 'leave')
        wait('leave reaches menu', lambda: menu('a') and connected('b', 1))
        rejected_before = read('a')['seat_rejections']
        command('a', 'join', address=f'localhost:{args.port}')
        wait('different endpoint fails without credentials', lambda: menu('a') and read('a')['seat_rejections'] > rejected_before)
        assert (profiles/'a/reconnect.json').read_bytes() == original_store
        assert read('a')['last_address'] == address
        join('a')
        wait('original endpoint still resumes', agree)
        assert [snapshot(name) for name in ('a', 'b')] == baseline
        checked('Failed join at a different endpoint preserves the original persisted credential and resumable match')

        server = active.pop('b' if args.package_dir else 'server')
        server.kill()
        server.wait(timeout=15)
        wait('real server loss returns surviving clients to menu',
             lambda: menu('a') and (bool(args.package_dir) or menu('b')), 45)
        old_session = first_profile['server_session']
        start_server()
        join('a')
        if not args.package_dir:
            wait('new server accepts first-time claim at same endpoint', lambda: connected('a', 1))
            join('b')
        wait('new server accepts the players as fresh seats', agree)
        for name in (('a',) if args.package_dir else ('a', 'b')):
            replacement = stored(name)
            assert replacement['server_session'] != old_session
            assert read(name)['last_server_session'] == replacement['server_session']
        assert snapshot('a')['view']['status'] == 'selection'
        assert snapshot('a')['match_id'] != baseline[0]['match_id']
        checked('A fresh server at the same endpoint changes public session ID, avoids stale-token claims, and creates a new playable match')

        start_client('silent', manual=True)
        wait('abandoned provisional claim expires', lambda: menu('silent') and read('silent').get('seat_rejections', 0) == 1, 25)
        assert not read('silent')['has_seat_token'] and agree()
        stop_client('silent')
        checked('Abandoned provisional authentication times out without revealing private state or consuming a seat')

        for name in ('a', 'b'):
            stop_client(name)
        # Private credential files are intentionally excluded. Ordinary logs,
        # controls and diagnostic reports must contain none of these real tokens.
        observed_files = list(folder.glob('*.log'))+list(folder.glob('*.json'))
        for path in observed_files:
            text = path.read_text(errors='replace')
            assert not any(token in text for token in private_tokens), f'Credential leaked into {path.name}'
            assert '?SeatToken=' not in text, f'Credential URL leaked into {path.name}'
        checked('Client/server logs and ordinary diagnostic reports contain no actual seat credentials or credential-bearing travel URLs')
        result = dict(ok=True, engine='Unreal 5.8.2', ruleset=args.ruleset, checks=checks, logs=str(folder),
                      topology='listen host and remote guest' if args.package_dir else 'dedicated Editor server and two remote clients',
                      executable_mode='packaged' if args.package_dir else 'editor_game',
                      package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                      elapsed_seconds=round(time.monotonic()-started, 2),
                      limitations=['Local loopback transport', 'Linux profile permission checks', 'Rendering disabled'])
        publish(result)
        print(json.dumps(result, indent=2), flush=True)
    except Exception as error:
        publish(dict(ok=False, engine='Unreal 5.8.2', ruleset=args.ruleset,
            executable_mode='packaged' if args.package_dir else 'editor_game',
            package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
            failure=str(error), completed_checks=checks, logs=str(folder),
            elapsed_seconds=round(time.monotonic()-started, 2)))
        raise
    finally:
        for process in all_processes:
            if process.poll() is None:
                process.terminate()
        for process in all_processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    main()
