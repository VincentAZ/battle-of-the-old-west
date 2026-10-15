#!/usr/bin/env python3
"""Exercise native Unreal reconnect, seat rejection, and rematch RPC lifecycles.

Uses opt-in, non-shipping controls in the real player controllers. Packet loss
drops actual UE network packets; no failure callback or game state is mocked.
Only this script's processes are terminated. Reports never contain seat tokens.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from native_launch import create_native_run_directory, game_net_driver_ports, resolve_native_launch

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def public_state(snapshot):
    state = json.loads(json.dumps(snapshot['view']))
    state.pop('viewer', None)
    state.pop('choice', None)
    for player in state['players']:
        player.pop('hand', None)
        player.pop('offers', None)
        # Camp choices remain private until both players finish selecting.
        if state['status'] == 'selection':
            player.pop('columns', None)
        else:
            for column in player['columns']:
                for card in column:
                    card.pop('private_peek', None)
    return state


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path, help='Run an already cooked Development package instead of Unreal Editor')
    parser.add_argument('--port', type=int, default=19279)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='base_2024')
    parser.add_argument('--production-timeouts', action='store_true',
                        help='Keep the normal 60-second connection timeouts while exercising lifecycle controls')
    parser.add_argument('--listen-host', action='store_true',
                        help='Use a local host player and one remote guest (automatic for a packaged Game target)')
    parser.add_argument('--packet-loss-model', choices=['auto', 'client_emulation', 'both_endpoints'], default='auto',
                        help='Listen-host default blocks both endpoints, including Unreal shutdown packets that bypass outgoing emulation')
    args = parser.parse_args()
    listen_host = bool(args.package_dir or args.listen_host)
    loss_model = ('both_endpoints' if listen_host else 'client_emulation') if args.packet_loss_model == 'auto' else args.packet_loss_model
    if loss_model == 'both_endpoints' and not listen_host:
        parser.error('Both-endpoint packet loss requires the controllable local listen host')
    folder = create_native_run_directory('oldwest-native-lifecycle-')
    processes, streams, sequences, clients = [], [], {}, {}
    checks = []
    last_reports = {}
    network_observations = []
    loss_started = None
    started = time.monotonic()
    address = f'127.0.0.1:{args.port}'
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    base = runtime.argv

    def publish(result):
        reports = ROOT/'game/tests/reports'
        reports.mkdir(parents=True, exist_ok=True)
        names = ['latest-native-lifecycle.json', f'latest-native-lifecycle-{args.ruleset}.json']
        if args.production_timeouts:
            names += ['latest-native-lifecycle-production-timeouts.json']
        if args.package_dir:
            names += ['latest-packaged-lifecycle.json', f'latest-packaged-lifecycle-{args.ruleset}.json']
            if args.production_timeouts:
                names += ['latest-packaged-lifecycle-production-timeouts.json']
        for path in [folder/'result.json', *(reports/name for name in names)]:
            # Concurrent ruleset runs share the latest-report aliases.
            temporary = path.with_suffix(f'.{os.getpid()}.tmp')
            temporary.write_text(json.dumps(result, indent=2)+'\n')
            temporary.replace(path)

    def launch(name, parameters):
        output = (folder/f'{name}-console.log').open('w')
        streams.append(output)
        process = subprocess.Popen(
            base + parameters +
            ['-nullrhi', '-nosound', '-unattended', '-nosplash', '-NoLiveCoding',
             '-stdout', '-FullStdOutLogOutput', '-OldWestLifecycleTest',
             *(['-OldWestProductionTimeouts'] if args.production_timeouts else []),
             f'-GameUserSettingsINI={folder}/{name}.settings.ini', f'-abslog={folder/name}.log'],
            cwd=runtime.cwd, env=runtime.env, stdout=output, stderr=subprocess.STDOUT)
        processes.append(process)
        return process

    def read(name):
        try:
            last_reports[name] = json.loads((folder/f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        # UE's report replacement may briefly remove its destination. Retain
        # the last complete record until the next sequence/revision arrives.
        return last_reports.get(name, {})

    def wait(description, predicate, timeout=45):
        deadline = time.monotonic() + timeout
        progress = time.monotonic()
        while time.monotonic() < deadline:
            for name, process in clients.items():
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited ({process.returncode}); see {folder}')
            if server.poll() is not None:
                raise RuntimeError(f'Server exited ({server.returncode}); see {folder}')
            if loss_started is not None:
                elapsed = time.monotonic()-loss_started
                if not network_observations or elapsed-network_observations[-1]['elapsed_seconds'] >= 1:
                    network_observations.append({'elapsed_seconds': elapsed,
                        'players': {name: {'network': read(name).get('network'),
                            'hosted': snapshot(name).get('hosted'), 'connected': snapshot(name).get('connected'),
                            'network_failures': read(name).get('network_failures')}
                            for name in ('a', 'b')}})
            value = predicate()
            if value:
                return value
            if time.monotonic() - progress > 25:
                print(f'Waiting: {description}', flush=True)
                progress = time.monotonic()
            time.sleep(0.15)
        raise AssertionError(f'Timed out: {description}; inspect {folder}')

    def command(name, action, **fields):
        sequences[name] = sequences.get(name, 0) + 1
        path = folder/f'{name}.control.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequences[name], action=action, **fields)))
        temporary.replace(path)
        wait(f'{name} accepts {action}', lambda: read(name).get('sequence', -1) >= sequences[name])

    def snapshot(name):
        return read(name).get('snapshot', {})

    def connected(name, count=2):
        state = snapshot(name)
        return state.get('hosted') and state.get('connected') == count

    def menu(name):
        state = snapshot(name)
        return state and state.get('hosted') is False

    def rejected_or_failed(name):
        state = read(name)
        return state.get('network_failures', 0)+state.get('seat_rejections', 0)

    def agree():
        a, b = snapshot('a'), snapshot('b')
        for current in (a, b):
            if 'view' in current:
                for column in current['view']['players'][1-current['seat']]['columns']:
                    assert all('private_peek' not in card for card in column), 'Opponent punk identity leaked'
        return (connected('a') and connected('b') and a.get('match_id') == b.get('match_id')
                and public_state(a) == public_state(b))

    def start_client(name):
        clients[name] = launch(name, [address, '-game', '-OldWestTestBot',
            f'-OldWestLifecycleControl={folder}/{name}.control.json',
            f'-OldWestLifecycleReport={folder}/{name}.json'])

    def checked(message):
        checks.append(message)
        print(f'PASS: {message}', flush=True)

    def rejoin_a(expected_match, expected_public, expected_seat):
        command('a', 'join', address=address)
        wait('original seat reconnects with both clients synchronized', agree)
        a = read('a')
        assert a['seat'] == expected_seat and a['same_seat_token']
        assert a['snapshot']['match_id'] == expected_match
        assert public_state(a['snapshot']) == expected_public

    print(f'Native lifecycle reports: {folder}', flush=True)
    try:
        map_url = f'/Game/Maps/WaterDepotV2?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={args.ruleset}'
        if listen_host:
            server = launch('b', [map_url+'?listen', '-game', '-OldWestTestBot',
                '-MULTIHOME=127.0.0.1', f'-port={args.port}',
                f'-OldWestLifecycleControl={folder}/b.control.json',
                f'-OldWestLifecycleReport={folder}/b.json'])
            clients['b'] = server
        else:
            server = launch('server', [map_url, '-server', '-MULTIHOME=127.0.0.1', f'-port={args.port}'])
        server_log = folder/('b.log' if listen_host else 'server.log')
        wait('server listens', lambda: server_log.exists() and
             args.port in game_net_driver_ports(server_log.read_text(errors='replace')), 90)
        if listen_host:
            wait('listen host authenticates its local seat', lambda: connected('b', 1))
        start_client('a')
        if not listen_host:
            wait('first native client receives its reserved seat', lambda: connected('a', 1))
            start_client('b')
        wait('two native clients synchronize', agree)
        first = snapshot('a')
        first_match, initial_public, first_seat = first['match_id'], public_state(first), first['seat']
        initial_b_command = snapshot('b')['actions'][0]['command']
        assert {snapshot(n)['seat'] for n in ('a', 'b')} == {0, 1}
        assert all(snapshot(n)['view']['ruleset'] == args.ruleset for n in ('a', 'b'))
        remote_clients = ('a',) if listen_host else ('a', 'b')
        assert all(read(n)['last_address'] == address and read(n)['has_seat_token'] for n in remote_clients)
        if listen_host:
            assert not read('b')['has_seat_token'], 'Listen hosting must not create a remote reconnect profile'
            checked('Listen host and remote guest receive distinct seats; the guest remembers its private reconnect address')
        else:
            checked('Direct-URL clients remember distinct seats and their reconnect address')

        start_client('third')
        wait('third connection is rejected into a usable menu',
             lambda: menu('third') and rejected_or_failed('third') > 0)
        assert not read('third')['has_seat_token']
        assert 'occupied' in read('third')['notice'] or 'reserved' in read('third')['notice']
        assert agree() and public_state(snapshot('a')) == initial_public
        checked('Third connection is rejected without disturbing either player or leaking a seat token')

        command('a', 'leave')
        wait('leave returns to menu and reserves the disconnected seat', lambda: menu('a') and connected('b', 1))
        assert read('a')['same_seat_token'] and read('a')['last_address'] == address
        assert snapshot('b')['actions'] == []
        command('b', 'submit', command=initial_b_command, revision=0, match_id=first_match)
        wait('server rejects an action while the other seat is disconnected',
             lambda: 'Waiting for the other player' in read('b').get('notice', ''))
        assert public_state(snapshot('b')) == initial_public
        before_failure_count = rejected_or_failed('a')
        # The same occupied server at another host name rejects this tokenless
        # attempt. It must preserve the credential for the original address.
        command('a', 'join', address=f'localhost:{args.port}')
        wait('unsuccessful different-address join returns to menu', lambda: menu('a') and
             rejected_or_failed('a') > before_failure_count)
        assert read('a')['same_seat_token'] and read('a')['last_address'] == address
        rejoin_a(first_match, initial_public, first_seat)
        checked('Leave, failed join elsewhere, and reconnect preserve the original private seat and complete match state')

        before_failure_count = read('a')['network_failures']
        timeout_state = read('a').get('network', {})
        expected_timeouts = (60, 60) if args.production_timeouts else (5, 10)
        for name in ('a', 'b'):
            network = read(name).get('network', {})
            assert (network.get('connection_timeout'), network.get('initial_timeout')) == expected_timeouts \
                and not network.get('timeouts_disabled'), \
                f'Unexpected {name} connection timeout settings: {network}'
            if name in remote_clients:
                assert network.get('effective_timeout') in expected_timeouts, f'Unexpected {name} effective timeout: {network}'
        loss_started = time.monotonic()
        # UNetConnection::FlushNet bypasses outgoing packet emulation while
        # closing. A client-only fault can therefore deliver a final packet
        # at 60 s and reset the host's receive timer. Drop incoming traffic on
        # the host too, to model the continuously broken link under test.
        if loss_model == 'both_endpoints':
            command('b', 'packet_loss', percent=100)
        command('a', 'packet_loss', percent=100)
        for name in (('a', 'b') if loss_model == 'both_endpoints' else ('a',)):
            peers = read(name).get('network', {}).get('peers', [])
            assert peers and all(peer.get('simulated_incoming_loss') == 100 and
                                 peer.get('simulated_outgoing_loss') == 100 for peer in peers), \
                f'Packet-loss emulation was not applied to {name}'
        wait('real packet loss times out both sides of the connection', lambda: menu('a') and
             connected('b', 1) and read('a').get('network_failures', 0) > before_failure_count,
             timeout=timeout_state['effective_timeout']+15)
        packet_loss_seconds = round(time.monotonic()-loss_started, 2)
        assert snapshot('b')['actions'] == []
        assert read('a')['notice'] and read('a')['same_seat_token']
        if loss_model == 'both_endpoints':
            command('b', 'packet_loss', percent=0)
        rejoin_a(first_match, initial_public, first_seat)
        checked('UDP packet-loss timeout returns to menu, pauses the opponent, and reconnects the same seat')

        command('a', 'resume')
        command('b', 'resume')
        wait('native match finishes', lambda: agree() and
             all(snapshot(n).get('view', {}).get('status') in ('won', 'draw') for n in ('a', 'b')), args.timeout)
        command('a', 'pause')
        command('b', 'pause')
        finished_public = public_state(snapshot('a'))
        command('a', 'rematch')
        wait('first rematch vote reaches both clients', lambda: all(
             snapshot(n).get('rematch_votes', [False, False])[first_seat] for n in ('a', 'b')))
        command('a', 'leave')
        wait('disconnection clears its rematch vote', lambda: menu('a') and connected('b', 1) and
             snapshot('b').get('rematch_votes') == [False, False])
        command('b', 'rematch')
        wait('rematch while disconnected is rejected', lambda: 'reconnect' in read('b').get('notice', ''))
        assert snapshot('b')['rematch_votes'] == [False, False]
        rejoin_a(first_match, finished_public, first_seat)
        checked('Leaving clears a rematch vote and a disconnected player cannot consent to a new match')

        command('a', 'rematch')
        command('b', 'rematch')
        wait('both votes start a synchronized fresh match', lambda: agree() and
             snapshot('a').get('match_id') != first_match and snapshot('a')['view']['status'] == 'selection')
        second = snapshot('a')
        assert second['view']['revision'] == 0 and second['rematch_votes'] == [False, False]
        assert second['view']['ruleset'] == args.ruleset
        assert all(read(n)['same_seat_token'] for n in remote_clients)
        checked('Two connected rematch votes reset the game, votes, and client revision while retaining seats')

        valid_command = second['actions'][0]['command']
        command('a', 'submit', command=valid_command, revision=0, match_id=first_match)
        wait('old-match command is rejected', lambda: 'earlier match' in read('a').get('notice', ''))
        assert snapshot('a')['view']['revision'] == 0
        command('a', 'submit', command=valid_command, revision=0, match_id=second['match_id'])
        wait('fresh-match command succeeds', lambda: agree() and snapshot('a')['view']['revision'] > 0)
        for name in ('a', 'b'):
            current = snapshot(name)
            assert 'hand' not in current['view']['players'][1-current['seat']]
            assert 'offers' not in current['view']['players'][1-current['seat']]
            assert all(not column for column in current['view']['players'][1-current['seat']]['columns'])
        checked('Old-match actions cannot mutate a rematch; current actions and private views remain valid')

        result = dict(ok=True, engine='Unreal 5.8.2', transport='native UDP over loopback', ruleset=args.ruleset,
                      topology='listen host and remote guest' if listen_host else 'dedicated Editor server and two remote clients',
                      executable_mode='packaged' if args.package_dir else 'editor_game',
                      package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                      production_timeouts=args.production_timeouts, packet_loss_seconds=packet_loss_seconds,
                      packet_loss_model=loss_model,
                      client_timeout_settings=timeout_state,
                      connected_players=2, rejected_extra_clients=1, checks=checks,
                      elapsed_seconds=round(time.monotonic()-started, 2), logs=str(folder),
                      limitations=['Same-machine test', 'Rendering disabled', 'Internet NAT not tested'])
        publish(result)
        print(json.dumps(result, indent=2), flush=True)
    except Exception as error:
        publish(dict(ok=False, engine='Unreal 5.8.2', ruleset=args.ruleset,
                     executable_mode='packaged' if args.package_dir else 'editor_game',
                     package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                     production_timeouts=args.production_timeouts, packet_loss_model=loss_model,
                     failure=str(error), completed_checks=checks, logs=str(folder),
                     client_network={name: read(name).get('network', {}) for name in clients},
                     elapsed_seconds=round(time.monotonic()-started, 2)))
        raise
    finally:
        (folder/'packet-loss-observations.json').write_text(json.dumps(network_observations, indent=2)+'\n')
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    run()
