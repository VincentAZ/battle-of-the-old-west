#!/usr/bin/env python3
"""Capture the real Unreal HUD at requested resolutions using two native clients.

The rendered player starts at the menu and joins a loopback server. Match setup
uses the same revision-checked RPC commands as human play. Local inspection,
help, camera and screenshot controls require -OldWestVisualTest and are absent
from shipping builds. No game state, card identities or network state is injected.
"""
import argparse
import hashlib
import json
import struct
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from native_launch import create_native_run_directory, game_net_driver_ports, resolve_native_launch, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_portraits import portraits_ready

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def signature(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return dict(path=str(path.resolve()), sha256=digest.hexdigest(), bytes=path.stat().st_size,
                modified_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())


def resolution(value):
    try:
        width, height = map(int, value.lower().split('x'))
        if 640 <= width <= 3840 and 360 <= height <= 2160:
            return width, height
    except ValueError:
        pass
    raise argparse.ArgumentTypeError('Use WIDTHxHEIGHT, from 640x360 through 3840x2160')


def capture_resolution(args, dimensions, index, output):
    width, height = dimensions
    folder = output/f'{width}x{height}'
    folder.mkdir(parents=True)
    address = f'127.0.0.1:{args.port+index}'
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    if runtime.package_root:
        binaries = runtime.package_root/'OldWest/Binaries/Linux'
        binary = next((path for path in (binaries/'OldWestGame', binaries/'OldWestGame-Linux-Development') if path.is_file()), None)
        if binary is None:
            raise FileNotFoundError(f'No packaged OldWestGame executable under {binaries}')
        build = dict(mode='packaged_game', executable=signature(binary),
                     manifest=signature(runtime.package_root/'package-manifest.json'))
    else:
        binary = ROOT/'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'
        sources = sorted((ROOT/'game/OldWest/Source/OldWestGame').rglob('*'))
        build = dict(mode='editor_game', module=signature(binary),
                     sources=[signature(path) for path in sources if path.is_file()],
                     catalog=signature(ROOT/'game/OldWest/Content/Data/cards.json'))
    (folder/'build.json').write_text(json.dumps(build,indent=2)+'\n')
    base = runtime.argv
    processes, streams, sequences, captures, checks = {}, [], {}, {}, []
    last_reports = {}
    definitions = {card['id']: card for card in json.loads((ROOT/'game/data/cards.json').read_text())['cards']}

    def launch(name, parameters, rendered=False):
        stream = (folder/f'{name}-console.log').open('w')
        streams.append(stream)
        graphics = (['-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}',
                     '-ExecCmds=t.MaxFPS 30'] if rendered else ['-nullrhi'])
        processes[name] = subprocess.Popen(
            base + parameters + graphics +
            ([f'-OldWestTestSeed={args.seed}'] if args.seed is not None else []) +
            ['-nosound', '-unattended', '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput',
             '-OldWestLifecycleTest', '-OldWestVisualTest', f'-GameUserSettingsINI={folder}/{name}.settings.ini', f'-abslog={folder/name}.log'],
            cwd=runtime.cwd, env=runtime.env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)

    def runtime_evidence():
        assets = assert_runtime_assets([folder/f'{name}.log' for name in processes])
        unchanged = signature(binary)['sha256'] == (build.get('module') or build['executable'])['sha256']
        assert unchanged, 'Game binary changed while the rendered HUD audit was running'
        return dict(build=build, runtime_assets=assets, binary_unchanged_during_run=unchanged)

    def read(name):
        try:
            last_reports[name] = json.loads((folder/f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return last_reports.get(name, {})

    def snapshot(name):
        return read(name).get('snapshot', {})

    def wait(description, predicate, timeout=None):
        deadline = time.monotonic() + (timeout or args.timeout)
        progress = time.monotonic()
        while time.monotonic() < deadline:
            for name, process in processes.items():
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited ({process.returncode}); inspect {folder}')
            result = predicate()
            if result:
                return result
            if time.monotonic()-progress > 25:
                print(f'{width}x{height}: waiting for {description}', flush=True)
                progress = time.monotonic()
            time.sleep(.15)
        raise AssertionError(f'Timed out: {description}; inspect {folder}')

    def command(name, action, **fields):
        sequences[name] = sequences.get(name, 0)+1
        path = folder/f'{name}.control.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequences[name], action=action, **fields)))
        temporary.replace(path)
        wait(f'{name} accepts {action}', lambda: read(name).get('sequence', -1) >= sequences[name])

    def agree():
        a, b = snapshot('a'), snapshot('b')
        return (a.get('connected') == b.get('connected') == 2 and a.get('match_id') == b.get('match_id')
                and a.get('view', {}).get('revision') == b.get('view', {}).get('revision'))

    def submit(name, action):
        current = snapshot(name)
        previous = current['view']['revision']
        command(name, 'submit', command=action['command'], revision=previous, match_id=current['match_id'])
        wait('legal action reaches both clients', lambda: agree() and snapshot(name)['view']['revision'] > previous)

    def capture(label, settle=True):
        # Let exposure, streaming and the next Slate rebuild settle before capture.
        if settle:
            time.sleep(args.settle)
        path = folder/f'{label}.png'
        command('a', 'screenshot', filename=str(path))

        def complete_png():
            try:
                data = path.read_bytes()
                return data if len(data) > 1000 and data[:8] == b'\x89PNG\r\n\x1a\n' and b'IEND' in data[-16:] else None
            except FileNotFoundError:
                return None

        data = wait(f'{label} screenshot', complete_png)
        actual = struct.unpack('>II', data[16:24])
        assert actual == dimensions, f'{label}: requested {dimensions}, got {actual}'
        captures[label] = str(path)
        print(f'{width}x{height}: captured {label} ({len(data):,} bytes)', flush=True)

    def inspect(card, owned, label):
        command('a', 'inspect', card=card['id'])
        wait('HUD selects the visible card', lambda: read('a').get('hud', {}).get('inspected_card') == card['id'])
        hud = read('a')['hud']
        assert hud['selected_source'] == (card['id'] if owned else 0)
        assert hud['inspector_side'] == (snapshot('a')['seat'] if owned else 1-snapshot('a')['seat'])
        capture(label)

    def battlefield(player, kind=None):
        cards = [card for column in player['columns'] for card in column]
        return [card for card in cards if kind is None or card['type'] == kind]

    try:
        map_url = f'/Game/Maps/WaterDepotV2?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={args.ruleset}'
        if args.package_dir:
            launch('b', [map_url+'?listen', '-game', '-MULTIHOME=127.0.0.1', f'-port={args.port+index}',
                         f'-OldWestLifecycleControl={folder}/b.control.json',
                         f'-OldWestLifecycleReport={folder}/b.json'])
        else:
            launch('server', [map_url, '-server', '-MULTIHOME=127.0.0.1', f'-port={args.port+index}'])
        server_log = folder/('b.log' if args.package_dir else 'server.log')
        wait('server listens', lambda: server_log.exists() and
             args.port+index in game_net_driver_ports(server_log.read_text(errors='replace')))
        startup_map = [] if args.package_dir else ['/Game/Maps/WaterDepotV2']
        launch('a', startup_map + ['-game',
                     f'-OldWestLifecycleControl={folder}/a.control.json',
                     f'-OldWestLifecycleReport={folder}/a.json'], rendered=True)
        wait('menu HUD appears', lambda: snapshot('a').get('hosted') is False and read('a').get('hud'))
        capture('01-menu')
        command('a', 'join', address=address)
        if not args.package_dir:
            wait('rendered player joins', lambda: snapshot('a').get('connected') == 1)
            launch('b', [address, '-game', f'-OldWestLifecycleControl={folder}/b.control.json',
                         f'-OldWestLifecycleReport={folder}/b.json'])
        wait('both players enter camp selection', agree)
        assert snapshot('a')['view']['status'] == 'selection'
        current = snapshot('a')
        offered = {card['id'] for card in current['view']['players'][current['seat']]['offers']}

        def camp_previews_ready():
            portraits = read('a').get('hud', {}).get('portraits', {})
            scenes = {scene['card_id']: scene for scene in portraits.get('scenes', [])}
            return portraits if (portraits_ready(portraits, offered)
                and all(scenes[card_id].get('camp_visible_parts', 0) > 0 for card_id in offered)) else None

        portraits = wait('all six offered camps have rendered their own scene', camp_previews_ready)
        (folder/'camp-portraits.json').write_text(json.dumps(portraits, indent=2)+'\n')
        checks.append('All six offered camp IDs resolve to ready portraits with visible camp geometry')
        capture('02-camp-selection')
        if args.require_offer_card:
            current=snapshot('a')
            offered={card['id'] for card in current['view']['players'][current['seat']]['offers']}
            assert set(args.require_offer_card)<=offered, f'Required long-description cards absent: {offered}'
        if args.check_camp_layout:
            options=read('a').get('hud',{}).get('camp_options',[])
            assert len(options)==6, 'Expected six actual camp-option widgets'
            (folder/'camp-option-layout.json').write_text(json.dumps(options,indent=2)+'\n')
            for option in options:
                actual,desired=option['allocated_size'],option['desired_size']
                assert all(a+.5>=d for a,d in zip(actual,desired)), f'Camp description is clipped: {option}'
            checks.append('All six camp-option widgets allocate their complete wrapped text size')
        if args.selection_only:
            result=dict(ok=True, resolution=f'{width}x{height}', screenshots=captures,
                        checks=['Menu and camp selection captured at requested dimensions',*checks],
                        selection_only=True, test_seed=args.seed, required_offer_cards=args.require_offer_card,
                        camp_layout_checked=args.check_camp_layout, ruleset=args.ruleset, logs=str(folder),
                        **runtime_evidence())
            (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            return result
        for name in ('a', 'b'):
            # Choose plentiful opening cards; all choices still come from legal actions.
            offered = snapshot(name)['actions']
            choice = max(offered, key=lambda action: sum(definitions[card]['starting_cards']
                         for card in action['command']['camps']))
            submit(name, choice)
        wait('match starts', lambda: snapshot('a')['view']['status'] == 'actions')
        capture('03-match')
        current = snapshot('a')
        seat = current['seat']
        own, enemy = current['view']['players'][seat], current['view']['players'][1-seat]
        assert own['hand'], 'Opening hand needed for its inspector regression'
        inspect(own['hand'][0], True, '04-hand-details')
        inspect(battlefield(own, 'camp')[0], True, '05-own-camp')
        inspect(battlefield(enemy, 'camp')[0], False, '06-enemy-camp')
        checks += ['Menu and camp selection captured at requested dimensions', 'Own hand and camp select their legal actions',
                   'Enemy camp is inspectable without becoming an ability source']

        # Start from a private hand card, which cannot be a rendered world hit.
        # Sample only the unobstructed center in viewport pixels; a successful
        # pick must resolve to an actually visible public battlefield handle.
        command('a', 'inspect', card=own['hand'][0]['id'])
        wait('hand selection precedes world pick', lambda: read('a')['hud']['inspected_card'] == own['hand'][0]['id'])
        public_cards = {card['id']: card for player in current['view']['players'] for card in battlefield(player)}
        picked = None
        for vertical in (.62, .52, .72, .42, .32, .22):
            for horizontal in (.50, .62, .38, .72, .28, .76):
                command('a', 'pick_at', x=round(width*horizontal), y=round(height*vertical))
                selected = read('a')['hud']['inspected_card']
                if selected in public_cards:
                    picked = public_cards[selected]
                    break
            if picked:
                break
        assert picked, 'World picking found no visible camp in the central scene'
        assert read('a')['hud']['selected_source'] == (picked['id'] if picked['owner'] == seat else 0)
        capture('12-world-picking')
        selected_before = read('a')['hud']['inspected_card']
        command('a', 'pick_at', x=-1, y=-1)
        assert read('a')['hud']['inspected_card'] == selected_before
        checks.append('Viewport world picking selects a rendered public card with correct ownership and rejects off-viewport coordinates')

        # Deploy one real person per side through ordinary play. Resolve genuine
        # entry choices and end turns for water; do not fabricate battlefield units.
        accepted = 0
        cinematic_skip_checked = False
        for _ in range(80):
            current = snapshot('a')
            players = current['view']['players']
            have = [any(not card.get('punk') for card in battlefield(player, 'person')) for player in players]
            if (all(have) and current['view']['status'] == 'actions'
                    and all(snapshot(name)['view'].get('choice') is None for name in ('a', 'b'))):
                break
            acting = next((name for name in ('a', 'b') if snapshot(name).get('actions')), None)
            assert acting, 'No legal setup action'
            state = snapshot(acting)
            actions = state['actions']
            choices = [action for action in actions if action['category'] == 'choice']
            deploy = [action for action in actions if action['category'] == 'play_person']
            action = (choices[0] if choices else deploy[0] if deploy and not have[state['seat']] else
                      next(action for action in actions if action['command']['type'] == 'end_turn'))
            submit(acting, action)
            accepted += 1
            if not cinematic_skip_checked and read('a').get('hud', {}).get('cinematic_busy'):
                assert read('a')['hud']['controls_visible'] is False, 'Cinematic must clear inspector, actions and hand'
                capture('11-cinematic-in-progress', settle=False)
                authoritative_before = [snapshot(name) for name in ('a', 'b')]
                command('a', 'skip_cinematics')
                wait('local presentation skips to current state', lambda: read('a').get('hud', {}).get('cinematic_busy') is False)
                assert read('a')['hud']['controls_visible'] is True, 'Skip must immediately restore gameplay controls'
                assert [snapshot(name) for name in ('a', 'b')] == authoritative_before
                cinematic_skip_checked = True
                checks.append('Observed a busy cinematic; local skip clears presentation without changing either authoritative snapshot')
        else:
            raise AssertionError('Could not deploy a person for both players in 80 legal actions')
        current = snapshot('a')
        own, enemy = current['view']['players'][seat], current['view']['players'][1-seat]
        inspect(next(card for card in battlefield(own, 'person') if not card.get('punk')), True, '07-own-person')
        inspect(next(card for card in battlefield(enemy, 'person') if not card.get('punk')), False, '08-enemy-person')
        checks.append('Both players deploy real people; own and enemy person inspectors preserve source ownership')
        before_settings = snapshot('a')
        command('a', 'settings', operation='open')
        wait('match settings panel opens', lambda: read('a').get('hud', {}).get('settings', {}).get('open'))
        capture('13-match-settings')
        command('a', 'settings', operation='close')
        wait('settings return to the match', lambda: not read('a').get('hud', {}).get('settings', {}).get('open'))
        assert snapshot('a') == before_settings
        checks.append('Settings are accessible during a match and return to the same authoritative snapshot.')

        command('a', 'rules', open=True)
        wait('rules overlay opens', lambda: read('a').get('hud', {}).get('rules_open'))
        capture('09-rules')
        command('a', 'rules', open=False)
        wait('rules overlay closes', lambda: read('a').get('hud', {}).get('rules_open') is False)
        command('a', 'camera')
        capture('10-alternate-camera')
        checks.append('Rules overlay and alternate camera render at requested resolution')

        # An opponent's hand handle is known only to the other real client. Give
        # that unavailable handle to the local inspector and verify it is rejected.
        other_hand = snapshot('b')['view']['players'][snapshot('b')['seat']]['hand']
        if other_hand:
            before = read('a')['hud']
            command('a', 'inspect', card=other_hand[0]['id'])
            wait('unknown card inspection is rejected', lambda: 'unavailable card' in read('a').get('notice', ''))
            after = read('a')['hud']
            assert all(after[key] == before[key] for key in ('inspected_card', 'selected_source', 'inspector_side', 'rules_open'))
            checks.append('Inspector rejects a private opponent-hand handle without changing selection')
        for name in ('a', 'b'):
            state = snapshot(name)
            opponent = state['view']['players'][1-state['seat']]
            assert 'hand' not in opponent and 'offers' not in opponent
            assert all('private_peek' not in card for card in battlefield(opponent))
        checks.append('Both native private views omit opponent hands, offers and punk peeks')
        result = dict(ok=True, resolution=f'{width}x{height}', screenshots=captures, checks=checks,
                      setup_commands=accepted+2, cinematic_skip_checked=cinematic_skip_checked,
                      test_seed=args.seed, required_offer_cards=args.require_offer_card,
                      camp_layout_checked=args.check_camp_layout,
                      ruleset=args.ruleset, logs=str(folder), **runtime_evidence())
        (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        return result
    finally:
        stop_owned_process_groups(processes.values(), streams)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path, help='Capture an already cooked Development package')
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--port', type=int, default=19319)
    parser.add_argument('--timeout', type=int, default=180, help='Seconds for each native startup or action')
    parser.add_argument('--settle', type=float, default=2, help='Seconds for rendering to settle before each capture')
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='boomtown')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, help='Use a reproducible legal deal through the existing gated native test hook')
    parser.add_argument('--require-offer-card', action='append', default=[], help='Require this camp in the rendered player\'s initial offers')
    parser.add_argument('--check-camp-layout', action='store_true', help='Check the actual allocated and desired camp-option sizes')
    parser.add_argument('--selection-only', action='store_true', help='Stop after the setup-layout regression; publish separate camp-selection reports')
    args = parser.parse_args()
    if args.seed is not None and not 0<=args.seed<2**64:
        parser.error('--seed must be an unsigned 64-bit integer')
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-hud-')
    output.mkdir(parents=True, exist_ok=True)
    print(f'Native HUD capture output: {output}', flush=True)
    started = time.monotonic()
    results = []
    def publish(report):
        directory = ROOT/'game/tests/reports'
        directory.mkdir(parents=True, exist_ok=True)
        suite='camp-selection' if args.selection_only else 'hud'
        names = [f'latest-native-{suite}.json']
        if args.package_dir:
            names += [f'latest-packaged-{suite}.json']
        for path in [output/'result.json', *(directory/name for name in names)]:
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(report, indent=2)+'\n')
            temporary.replace(path)
    try:
        for index, size in enumerate(args.resolutions):
            results.append(capture_resolution(args, size, index, output))
    except Exception as error:
        publish(dict(ok=False, engine='Unreal 5.8.2', rendered=True, completed_results=results,
            executable_mode='packaged' if args.package_dir else 'editor_game',
            package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
            failure=str(error), logs=str(output), elapsed_seconds=round(time.monotonic()-started, 2)))
        raise
    report = dict(ok=True, engine='Unreal 5.8.2', rendered=True, connected_players=2, results=results,
                  selection_only=args.selection_only, test_seed=args.seed,
                  executable_mode='packaged' if args.package_dir else 'editor_game',
                  package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                  elapsed_seconds=round(time.monotonic()-started, 2),
                  limitations=['Local loopback transport', 'Visual review requires inspecting the PNG captures',
                               'Wanted Poster Board private peek correctness is covered separately by core regressions'])
    publish(report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
