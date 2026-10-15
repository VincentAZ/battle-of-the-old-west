#!/usr/bin/env python3
"""Exercise actual Slate drag/drop and battlefield camera gestures in Unreal.

Two ordinary native peers use legal actions to prepare a deterministic match.
Only the rendered player's UI receives pointer events. Deployment assertions
observe authoritative state on both peers; no state or card identities are
injected. Screenshots and exact pointer journals remain available for review.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import struct
import subprocess
import time
from pathlib import Path

from native_launch import (create_native_run_directory, game_net_driver_ports,
                           resolve_native_launch, stop_owned_process_groups)
from native_runtime_checks import assert_runtime_assets
from test_unreal_hud import resolution

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def write_json(path, value):
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def center(widget):
    return tuple((a + b) / 2 for a, b in zip(widget['min'], widget['max']))


def field_cards(snapshot):
    return [card for player in snapshot['view']['players'] for column in player['columns'] for card in column]


def card_handle(widget):
    return int(widget.get('id', widget.get('card', -1)))


def arranged_widget(widget):
    """A rebuilt Slate widget can be reported one frame before arrangement."""
    size, desired = widget.get('allocated_size', []), widget.get('desired_size', [])
    return (len(size) == len(desired) == 2 and all(actual > 1 and actual + 1 >= want
            for actual, want in zip(size, desired)) and widget.get('visible', True) and widget.get('enabled', True))


class InteractionScenario:
    def __init__(self, args, output, dimensions, index):
        self.args, self.dimensions, self.port = args, dimensions, args.port + index
        # Unreal interprets report/profile paths from its own working directory.
        self.folder = output.resolve() / f'{dimensions[0]}x{dimensions[1]}'
        self.folder.mkdir(mode=0o700)
        self.runtime = resolve_native_launch(args.editor, ROOT / 'game/OldWest/OldWest.uproject',
            args.package_dir, run_directory=self.folder, editor_directory=ROOT)
        self.defs = {card['id']: card for card in json.loads((ROOT / 'game/data/cards.json').read_text())['cards']}
        self.processes, self.streams, self.sequences, self.reports = {}, [], {}, {}
        self.checks, self.captures, self.evidence = [], {}, {}
        if not args.package_dir:
            paths = ['game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so',
                     'game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp',
                     'game/OldWest/Source/OldWestGame/Public/OldWestBattlefield.h',
                     'game/OldWest/Source/OldWestGame/Private/OldWestHUD.cpp']
            self.evidence['runtime_inputs_sha256'] = {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}
        self.started, self.pointer = time.monotonic(), (0, 0)

    def read(self, name='a'):
        try:
            self.reports[name] = json.loads((self.folder / f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return self.reports.get(name, {})

    def snapshot(self, name='a'):
        return self.read(name).get('snapshot', {})

    def hud(self):
        return self.read().get('hud', {})

    def hud_dimensions(self):
        return self.hud().get('hud_size', self.dimensions)

    def wait(self, label, predicate, timeout=35):
        end = min(self.started + self.args.timeout, time.monotonic() + timeout)
        progress = time.monotonic()
        while time.monotonic() < end:
            for name, process in self.processes.items():
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited {process.returncode} during {label}')
            result = predicate()
            if result:
                return result
            if time.monotonic() - progress > 20:
                print(f'{self.folder.name}: waiting for {label}', flush=True)
                progress = time.monotonic()
            time.sleep(.07)
        raise AssertionError(f'Timed out: {label}; inspect {self.folder}')

    def command(self, peer, action, **fields):
        sequence = self.sequences[peer] = self.sequences.get(peer, 0) + 1
        payload = dict(sequence=sequence, action=action, **fields)
        with (self.folder / 'commands.jsonl').open('a') as journal:
            journal.write(json.dumps({'peer': peer, 'elapsed': time.monotonic() - self.started, **payload}) + '\n')
        write_json(self.folder / f'{peer}.control.json', payload)
        self.wait(f'{peer} accepts {action}', lambda: self.read(peer).get('sequence', -1) >= sequence, 20)

    def event(self, phase, position=None, button='left', wheel=0):
        self.pointer = position if position is not None else self.pointer
        self.command('a', 'ui_pointer', phase=phase, x=float(self.pointer[0]), y=float(self.pointer[1]),
                     button=button, wheel=wheel)

    def agree(self):
        a, b = self.snapshot('a'), self.snapshot('b')
        return (a.get('connected') == b.get('connected') == 2 and a.get('match_id') == b.get('match_id')
                and a.get('view', {}).get('revision') == b.get('view', {}).get('revision'))

    def submit(self, name, action):
        before = self.snapshot(name)
        self.command(name, 'submit', command=action['command'], revision=before['view']['revision'],
                     match_id=before['match_id'])
        def accepted():
            a,b=self.snapshot('a'),self.snapshot('b')
            return (a.get('connected')==b.get('connected')==2 and a.get('match_id')==b.get('match_id')
                    and a.get('view',{}).get('revision',-1)==b.get('view',{}).get('revision',-2)
                    and a.get('view',{}).get('revision',-1)>before['view']['revision'])
        self.wait('authoritative peers accept legal setup action',accepted)

    def checked(self, description):
        self.checks.append(description)
        print(f'{self.folder.name}: PASS {description}', flush=True)

    def launch(self, name, url, rendered=False):
        stream = (self.folder / f'{name}-console.log').open('w')
        self.streams.append(stream)
        width, height = self.dimensions
        graphics = ['-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}'] if rendered else ['-nullrhi']
        sound = ['-AudioMixer'] if rendered and getattr(self.args, 'audio', False) else ['-nosound']
        render_commands = ','.join(['t.MaxFPS 60', *getattr(self.args, 'extra_render_commands', [])])
        self.processes[name] = subprocess.Popen(self.runtime.argv + [url, '-game', *graphics,
            *getattr(self.args, 'native_extra_args', []),
            '-OldWestLifecycleTest', '-OldWestVisualTest', '-OldWestProductionTimeouts', f'-OldWestTestSeed={self.args.seed}',
            f'-OldWestLifecycleControl={self.folder}/{name}.control.json',
            f'-OldWestLifecycleReport={self.folder}/{name}.json', f'-port={self.port}', '-MULTIHOME=127.0.0.1',
            f'-OldWestProfileRoot={self.folder}/profiles', f'-OldWestProfile={name}',
            f'-GameUserSettingsINI={self.folder}/{name}.settings.ini', f'-abslog={self.folder}/{name}.log',
            '-ExecCmds='+render_commands, *sound, '-unattended', '-nosplash', '-NoLiveCoding',
            '-stdout', '-FullStdOutLogOutput'], cwd=self.runtime.cwd, env=self.runtime.env,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)

    def settle_presentation(self):
        # A setup command can create a short shot. Skipping is an existing
        # local-only control and is not used for camera restoration assertions.
        self.command('a', 'skip_cinematics')
        self.wait('tactical controls available', lambda: self.hud().get('controls_visible') is True)
        time.sleep(.2)

    def capture(self, label):
        time.sleep(self.args.settle)
        path = self.folder / f'{label}.png'
        self.command('a', 'screenshot', filename=str(path))

        def complete():
            try:
                data = path.read_bytes()
                return data if len(data) > 1000 and data[:8] == b'\x89PNG\r\n\x1a\n' and b'IEND' in data[-16:] else None
            except FileNotFoundError:
                return None

        data = self.wait('complete screenshot', complete)
        assert struct.unpack('>II', data[16:24]) == self.dimensions, 'Screenshot resolution differs from requested viewport'
        self.captures[label] = str(path)
        write_json(self.folder / f'{label}.state.json', self.read())

    def boot(self):
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log = self.folder / 'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('rendered menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('both peers in selection', self.agree, 100)
        self.capture('01-camp-selection')
        for name in ('a', 'b'):
            # Maximize legal starting hand size without fabricating a card.
            action = max(self.snapshot(name)['actions'], key=lambda candidate:
                         sum(self.defs[card]['starting_cards'] for card in candidate['command']['camps']))
            self.submit(name, action)
        self.wait('ordinary match begins', lambda: self.snapshot()['view']['status'] == 'actions')
        self.settle_presentation()

    def own_hand(self, name='a'):
        current = self.snapshot(name)
        return {card['id']: card for card in current['view']['players'][current['seat']]['hand']}

    def junk_kind(self, card):
        effect = self.defs.get(card.get('card_id'), {}).get('junk', '')
        return effect if isinstance(effect, str) else effect.get('effect', '')

    def seek(self, predicate, label, max_actions=120):
        """Find a needed ordinary legal action using draws and pass turns."""
        for _ in range(max_actions):
            current = self.snapshot()
            found = next((action for action in current['actions'] if predicate(action, current)), None)
            if found:
                self.settle_presentation()
                return found
            assert current['view']['status'] not in ('won', 'draw'), f'Match ended while seeking {label}'
            acting = next((name for name in ('a', 'b') if self.snapshot(name).get('actions')), None)
            assert acting, f'Neither peer has a legal action while seeking {label}'
            options = self.snapshot(acting)['actions']
            if options[0]['command']['type'] == 'choose':
                action = options[0]
            elif acting == 'a':
                action = next((entry for entry in options if entry['command']['type'] == 'draw'), None)
                action = action or next(entry for entry in options if entry['command']['type'] == 'end_turn')
            else:
                action = next(entry for entry in options if entry['command']['type'] == 'end_turn')
            self.submit(acting, action)
        raise AssertionError(f'Could not reach {label} through {max_actions} legal actions')

    def seek_person(self):
        return self.seek(lambda action, _: action['command']['type'] == 'play' and 'column' in action['command'], 'playable person')

    def visible_hand_widget(self, card):
        master=next((p for p in self.hud().get('dock_panels',[]) if p['id']=='master'),None)
        if master:
            tab=next(e for e in self.hud()['master_tabs'] if e['id']=='your')
            self.event('move',center(tab));self.event('down',center(tab));self.event('up',center(tab))
            self.wait('own hand arranged',lambda:bool(self.hud().get('hand_cards')) and self.hud()['hand_cards'][0]['allocated_size'][0]>1)
        def widget():
            width, height = self.hud_dimensions()
            area=next((p['content'] for p in self.hud().get('dock_panels',[]) if p['id']=='master'),None)
            return next((entry for entry in self.hud().get('hand_cards', [])
                if card_handle(entry) == card and arranged_widget(entry)
                and (not area or all(entry['min'][i]>=area['min'][i] and entry['max'][i]<=area['max'][i] for i in (0,1)))
                and 0 <= center(entry)[0] <= width and 0 <= center(entry)[1] <= height), None)
        result = widget()
        if result:
            return result
        # Horizontal hand strips may contain cards beyond the visible edge.
        # Scroll the actual hand with wheel input, never set a widget offset.
        width, height = self.hud_dimensions()
        camera_before = self.camera_identity(self.camera_state())
        for direction in (-1, 1):
            for _ in range(15):
                point=((master['content']['min'][0]+master['content']['max'][0])/2,center(self.hud()['hand_cards'][0])[1]) if master else (width*.48,height*.89)
                self.event('wheel',point,wheel=direction*3)
                # Slate interpolates wheel scrolling after acknowledging input.
                # Read hit coordinates only after that motion has settled.
                time.sleep(.6)
                assert self.camera_identity(self.camera_state()) == camera_before, 'Scrolling the hand also moved the battlefield camera'
                result = widget()
                if result:
                    return result
        raise AssertionError(f'Hand card {card} has no visible drag widget')

    def begin_drag(self, card, widget=None):
        widget = widget or self.visible_hand_widget(card)
        assert arranged_widget(widget), f'Drag requires a fully arranged widget: {widget}'
        with (self.folder / 'drag-starts.jsonl').open('a') as journal:
            journal.write(json.dumps({'card': card, 'widget': widget, 'revision': self.snapshot()['view']['revision']}) + '\n')
        start = center(widget)
        self.event('move', start)
        self.event('down', start)
        self.event('move', (start[0] + 14, start[1] - 22))
        self.wait('actual Slate card drag starts', lambda: self.hud().get('deployment', {}).get('card') == card)
        hud = self.hud()
        assert hud.get('viewport_size') == list(self.dimensions), 'Native viewport size differs from its actual screenshot size'
        drag_area = hud.get('drag_rect')
        assert drag_area and 'min' in drag_area and 'max' in drag_area, 'The active drag area geometry is missing'
        for target in hud['deployment']['targets']:
            assert target.get('projected'), 'A legal placement projects behind the default deployment camera'
            assert all(low <= coordinate <= high for coordinate, low, high in
                       zip(target['screen'], drag_area['min'], drag_area['max'])), \
                f'A legal placement cannot be reached in the actual visible drag area: {target}'
            painted_pixels = [coordinate * viewport / local for coordinate, viewport, local in
                              zip(target['screen'], hud['viewport_size'], hud['hud_size'])]
            assert max(abs(a-b) for a, b in zip(painted_pixels, target['screen_pixels'])) < 1, \
                'DPI scaling places the painted drop label away from its intended pixel destination'
            # Collision avoidance can displace any badge. The leader endpoint
            # still reports the independent projected world position.
            assert all(math.isfinite(v) for v in target['world_screen_pixels'])
        if 'overlay_unit' in hud:
            targets=deployment_targets=hud['deployment']['targets'];unit=hud['overlay_unit']
            for i,a in enumerate(targets):
                for b in targets[i+1:]:
                    assert abs(a['screen'][0]-b['screen'][0])>=140*unit or abs(a['screen'][1]-b['screen'][1])>=42*unit,'Placement badges overlap'
        with (self.folder / 'drop-projection-samples.jsonl').open('a') as journal:
            journal.write(json.dumps({'hud_size': hud['hud_size'], 'viewport_size': hud['viewport_size'],
                                      'drag_rect': drag_area, 'deployment': hud['deployment']}) + '\n')
        return hud['deployment']

    def target(self, deployment):
        width, height = self.hud_dimensions()
        candidates = [target for target in deployment['targets'] if target.get('projected') and len(target.get('screen', [])) == 2
                      and width * .20 <= target['screen'][0] <= width * .78
                      and height * .15 <= target['screen'][1] <= height * .73]
        assert candidates, f'No legal target lies in the unobstructed viewport: {deployment}'
        return min(candidates, key=lambda target: abs(target['screen'][0] - width * .52)
                   + abs(target['screen'][1] - height * .48))

    def finish_drop(self, target):
        self.event('move', target['screen'])
        self.wait('drop target highlights', lambda: self.hud().get('deployment', {}).get('hovered', -1) >= 0)
        before = self.snapshot()
        self.event('up', target['screen'])
        self.wait('drop changes both authoritative peers', lambda: self.agree()
                  and self.snapshot()['view']['revision'] == before['view']['revision'] + 1)
        return before

    @staticmethod
    def target_offers(target, command):
        return target['command']==command or any(a['command']==command for a in target.get('alternatives',[]))

    def accept_drop_choice(self, target, command, before):
        alternatives=target.get('alternatives',[])
        option=next((a for a in alternatives if a['command']==command),None)
        if not option or (len(alternatives)==1 and not option.get('confirm')):
            return
        assert self.snapshot()['view']==before, 'Drop committed before the explicit choice or confirmation'
        caption=('CONFIRM · ' if option.get('confirm') else '')+option['label']
        entry=self.wait('drop choice arranged',lambda:next((e for e in self.hud()['context_entries'] if e['id']==caption and e['allocated_size'][0]>1),None))
        self.capture('drop-choice-'+str(before['revision']))
        self.event('move',center(entry));self.event('down',center(entry));self.event('up',center(entry))
        self.checked('Shared or destructive drop waits for an explicit menu choice before commitment')

    def camera_state(self):
        return copy.deepcopy(self.read()['cinematic']['tactical_camera'])

    @staticmethod
    def camera_identity(camera):
        return {key: camera[key] for key in ('yaw', 'pitch', 'distance', 'focus')}

    def test_camera(self):
        self.settle_presentation()
        width, height = self.hud_dimensions()
        spot = (width * .58, height * .28)
        before = [self.snapshot(name) for name in ('a', 'b')]
        initial = self.camera_state()
        self.event('wheel', spot, wheel=2)
        self.wait('wheel zoom changes radius', lambda: self.camera_state()['distance'] < initial['distance'])
        zoomed = self.camera_state()
        self.event('down', spot, button='right')
        self.event('move', (spot[0] + 140, spot[1] + 45), button='right')
        self.event('up', button='right')
        self.wait('right drag rotates battlefield', lambda: self.camera_state()['yaw'] != zoomed['yaw'])
        orbited = self.camera_state()
        self.event('down', spot, button='middle')
        self.event('move', (spot[0] - 90, spot[1] + 50), button='middle')
        self.event('up', button='middle')
        self.wait('middle drag pans battlefield', lambda: self.camera_state()['focus'] != orbited['focus'])
        for amount in (100, 100, -100, -100):
            self.event('wheel', spot, wheel=amount)
            current = self.camera_state()
            assert current['minimum_distance'] <= current['distance'] <= current['maximum_distance']
        for delta in (5000, -5000):
            self.event('down', spot, button='right')
            self.event('move', (spot[0], spot[1] + delta), button='right')
            self.event('up', button='right')
            current = self.camera_state()
            assert current['minimum_pitch'] <= current['pitch'] <= current['maximum_pitch']
        pan_edges = []
        for _ in range(40):
            self.event('down', spot, button='middle')
            self.event('move', (spot[0] + 5000, spot[1] + 5000), button='middle')
            self.event('up', button='middle')
            pan_edges.append(self.camera_state()['focus'])
            if len(pan_edges)>1 and pan_edges[-1]==pan_edges[-2]:break
        assert pan_edges[-1] == pan_edges[-2], 'Repeated panning never reaches a battlefield boundary'
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Camera gestures mutated rule state'
        self.evidence['camera'] = dict(initial=initial, zoomed=zoomed, orbited=orbited,
                                      pan_edges=pan_edges, final=self.camera_state())
        self.capture('02-camera-navigation')
        reset = self.wait('reset camera button geometry', lambda: next((entry for entry in self.hud().get('camera_buttons', [])
                          if entry['id'] == 'reset_view' and arranged_widget(entry)), None))
        self.event('move', center(reset))
        self.event('down', center(reset))
        self.event('up', center(reset))
        self.wait('reset restores default tactical camera', lambda: self.camera_identity(self.camera_state()) == self.camera_identity(initial))
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Reset View mutated rule state'
        time.sleep(.6)
        self.checked('Wheel zoom, right-drag orbit and middle-drag pan alter a bounded camera without changing either game state')

    def assert_roster(self):
        hud = self.hud()
        lanes = hud.get('roster_lanes', [])
        assert len(lanes) == 3, f'Expected all three visible roster lanes; got {len(lanes)}'
        width, height = hud['hud_size']
        for lane in lanes:
            assert lane['visible'] and lane['enabled'], f'Roster lane unavailable: {lane}'
            x0, y0 = lane['min']
            x1, y1 = lane['max']
            assert -.5 <= x0 < x1 <= width + .5 and -.5 <= y0 < y1 <= height + .5, f'Roster lane off-screen: {lane}'
            pairs=zip(lane['allocated_size'][1:],lane['desired_size'][1:]) if hud.get('master_cards') else zip(lane['allocated_size'],lane['desired_size'])
            assert all(actual+1>=desired for actual,desired in pairs), f'Roster lane clipped: {lane}'
        self.evidence['roster_lanes'] = lanes
        self.checked('All three actual roster lane widgets fit within the viewport and allocate their complete content')

    def test_person_drag(self):
        action = self.seek_person()
        card = action['command']['card']
        self.settle_presentation()
        before = [self.snapshot(name) for name in ('a', 'b')]
        self.begin_drag(card)
        self.event('move', (8, 8))
        self.event('up', (8, 8))
        self.wait('invalid drop cancels', lambda: self.hud().get('deployment', {}).get('card', -1) == -1)
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Invalid drop submitted an action'
        self.checked('Dropping a hand person outside legal targets cancels without spending water or changing either revision')
        default_camera = self.camera_identity(self.camera_state())
        width, height = self.hud_dimensions()
        self.event('wheel', (width * .58, height * .28), wheel=.5)
        self.wait('custom pre-cinematic camera', lambda: self.camera_identity(self.camera_state()) != default_camera)
        time.sleep(.5)
        deployment = self.begin_drag(card)
        target = self.target(deployment)
        self.event('move', target['screen'])
        self.capture('03-person-drag-targets')
        tactical = self.camera_identity(self.camera_state())
        before = self.finish_drop(target)
        after = self.snapshot()
        assert card not in self.own_hand(), 'Dropped person stayed in hand'
        played = [entry for entry in after['view']['players'][after['seat']]['columns'][target['command']['column']]
                  if entry['id'] == card]
        assert len(played) == 1 and played[0]['type'] == 'person', 'Drop did not place the actual card in the selected lane'
        # Do not skip this shot: the normal cinematic return must preserve the view.
        time.sleep(1)
        self.wait('normal cinematic returns', lambda: self.read()['cinematic']['busy'] is False)
        assert self.camera_identity(self.camera_state()) == tactical, 'Cinematic discarded the user camera'
        figure = next(unit for unit in self.read()['cinematic']['units'] if unit['id'] == card)
        assert max(abs(a-b) for a, b in zip(figure['location'][:2], target['world'][:2])) < 1, \
            'The deployed figure did not occupy the world space highlighted by the drop marker'
        self.evidence['person_drop'] = dict(card=card, target=target, revision_before=before['view']['revision'],
                                           revision_after=after['view']['revision'])
        self.assert_roster()
        self.capture('04-person-deployed')
        self.checked('Real card drag places that person into the selected legal lane and normal cinematic return restores the chosen camera')
        return card

    def test_stale_drag(self):
        action = self.seek_person()
        card = action['command']['card']
        deployment = self.begin_drag(card)
        target = self.target(deployment)
        end_turn = next(entry for entry in self.snapshot()['actions'] if entry['command']['type'] == 'end_turn')
        self.submit('a', end_turn)
        before = [self.snapshot(name) for name in ('a', 'b')]
        self.event('move', target['screen'])
        self.event('up', target['screen'])
        time.sleep(.35)
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'A drag from the previous revision submitted an extra action'
        assert card in self.own_hand(), 'Stale drag deployed its old hand card'
        assert self.hud().get('deployment', {}).get('card', -1) == -1, 'Stale drag left target markers alive'
        self.checked('A revision change while dragging invalidates the drag; release submits no extra action')

    def test_punk_placement(self):
        action = self.seek(lambda action, _: action['command']['type'] == 'junk'
            and self.junk_kind(self.own_hand().get(action['command'].get('card'), {})) == 'punk', 'legal punk junk effect')
        self.submit('a', action)
        self.settle_presentation()
        assert any(entry.get('placement', {}).get('punk') for entry in self.snapshot()['actions']), 'Punk choice lacks spatial legal metadata'
        widget = self.wait('pending-choice drag widget', lambda: next((entry for entry in self.hud().get('placement_drag_buttons', [])
                          if card_handle(entry) == 0 and arranged_widget(entry)), None))
        before_ids = {entry['id'] for entry in field_cards(self.snapshot())}
        deployment = self.begin_drag(0, widget)
        target = self.target(deployment)
        self.finish_drop(target)
        created = [entry for entry in field_cards(self.snapshot()) if entry['id'] not in before_ids]
        assert len(created) == 1 and created[0]['punk'], 'Dragging the generated punk did not create one actual punk'
        self.settle_presentation()
        self.evidence['punk_drop'] = dict(card=created[0]['id'], target=target)
        self.capture('05-punk-deployed')
        self.checked('A generated punk uses a real spatial-choice drag and creates exactly one punk through the rules engine')
        return created[0]['id']

    def test_raiders(self):
        action = self.seek(lambda action, _: action['command']['type'] == 'junk'
            and self.junk_kind(self.own_hand().get(action['command'].get('card'), {})) == 'raid', 'legal raid junk effect')
        self.submit('a', action)
        self.settle_presentation()
        current = self.snapshot()
        raider = next((card for card in current['view']['players'][current['seat']]['queue']
                       if card and card.get('card_id') == 'stampede'), None)
        assert raider, 'Raid did not place Stampede in the public queue'
        self.wait('queued Stampede have a world actor', lambda: any(unit['id'] == raider['id'] and unit['raider']
                  for unit in self.read()['cinematic']['units']))
        self.capture('06-raiders-deployed')
        self.checked('Launching a legal raid creates a visible Stampede actor at its actual queue stage')
        return raider['id']

    def frame_raiders(self, identity):
        """Use ordinary mouse gestures to expose the outer queue in close view."""
        unit = next(entry for entry in self.read()['cinematic']['units'] if entry['id'] == identity)
        width, height = self.hud_dimensions()
        viewport = self.hud()['viewport_size']
        spot = (width * .58, height * .28)
        before = [self.snapshot(name) for name in ('a', 'b')]
        for _ in range(3):
            camera = self.camera_state()
            delta = [unit['location'][axis] - camera['focus'][axis] for axis in range(2)]
            if max(abs(value) for value in delta) < 2:
                break
            yaw = math.radians(camera['yaw'])
            right, forward = (-math.sin(yaw), math.cos(yaw)), (-math.cos(yaw), -math.sin(yaw))
            pan_x = -sum(a*b for a, b in zip(delta, right)) / (camera['distance'] * .0012)
            pan_y = sum(a*b for a, b in zip(delta, forward)) / (camera['distance'] * .0012)
            self.event('down', spot, button='middle')
            self.event('move', (spot[0] + pan_x * width / viewport[0], spot[1] + pan_y * height / viewport[1]), button='middle')
            self.event('up', button='middle')
        self.event('wheel', spot, wheel=math.log(1250 / self.camera_state()['distance']) / math.log(.84))
        time.sleep(.7)
        self.capture('06b-raiders-close-idle')
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Framing the Stampede changed rule state'
        self.evidence['raider_close_view'] = {'id': identity, 'camera': self.camera_state(), 'unit_location': unit['location']}

        # Calibrated grip contacts need front/side renders as well as numerical
        # evidence: a zero component gap alone cannot prove natural fingers.
        self.event('wheel', spot, wheel=math.log(800 / self.camera_state()['distance']) / math.log(.84))
        front = -90 if unit['side'] == 0 else 90
        for name, yaw in (('front', front), ('side', front + 75)):
            for _ in range(3):
                current = self.camera_state()
                delta = (yaw - current['yaw'] + 180) % 360 - 180
                pitch_delta = 15 - current['pitch']
                if abs(delta) < .1 and abs(pitch_delta) < .1:
                    break
                pixels_x = max(-500, min(500, -delta / .22))
                pixels_y = max(-500, min(500, pitch_delta / .18))
                self.event('down', spot, button='right')
                self.event('move', (spot[0] + pixels_x * width / viewport[0],
                                   spot[1] + pixels_y * height / viewport[1]), button='right')
                self.event('up', button='right')
            time.sleep(.6)
            self.capture(f'06c-raiders-grip-{name}')
            self.evidence.setdefault('world_grip_views', []).append(dict(
                angle=name, camera=self.camera_state(),
                unit=next(entry for entry in self.read()['cinematic']['units'] if entry['id'] == identity)))
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Grip inspection camera changed rule state'

    def reset_camera(self):
        reset = next(entry for entry in self.hud()['camera_buttons'] if entry['id'] == 'reset_view' and arranged_widget(entry))
        self.event('move', center(reset))
        self.event('down', center(reset))
        self.event('up', center(reset))
        time.sleep(.5)

    def test_idles(self, identities):
        self.settle_presentation()
        baseline = {unit['id']: unit for unit in self.read()['cinematic']['units'] if unit['id'] in identities}
        assert set(baseline) == set(identities), 'A deployed figure lacks an idle actor'
        samples = []
        for _ in range(12):
            time.sleep(.14)
            sample = {unit['id']: unit for unit in self.read()['cinematic']['units'] if unit['id'] in identities}
            for identity, unit in sample.items():
                assert unit['playing'] and unit['looping'] and not unit['ragdoll'] and not unit['dead'], f'Deployed figure lacks a live loop: {unit}'
                assert unit['root_drift_cm'] < 1, f'Idle root drifts away from its deployment: {unit}'
                if 'Rifle' in unit['idle_clip']:
                    grip = unit.get('weapon_alignment', {})
                    assert grip.get('two_hand_pose') and grip.get('native_forward_axis') == '+Y', f'Rifle lacks calibrated two-hand alignment: {unit}'
                    assert 'M_Portrait_Weapon' in grip.get('material', ''), f'World rifle retains its placeholder material: {unit}'
                    assert max(grip['live_right_palm_gap_cm'], grip['live_left_palm_gap_cm']) < 1.5, f'Animated rifle leaves an actual palm: {unit}'
            samples.append(sample)
        for identity, unit in baseline.items():
            assert any(abs(sample[identity]['animation_position'] - unit['animation_position']) > .03 for sample in samples), f'Idle time is frozen for {identity}'
            assert any(max(abs(a-b) for a, b in zip(sum(sample[identity]['pose_samples'], []), sum(unit['pose_samples'], []))) > .01
                       for sample in samples), f'The pose does not visibly animate for {identity}'
        write_json(self.folder / 'idle-samples.json', {'baseline': baseline, 'samples': samples})
        self.checked('Deployed people, generated punk and Stampede play advancing skeletal loops with stable roots')
        self.checked('Armed idle poses retain calibrated live palm contacts and the dark weapon material')
        camps = [unit for unit in self.read()['cinematic']['units'] if unit['camp']]
        assert len(camps) == 6 and all(unit.get('faces_opponent') for unit in camps), 'A camp entrance faces away from its guard/opponent line'
        self.evidence['camp_facing'] = camps
        self.checked('All six camp structures face their guards and opposing force using the authored front axis')

    def test_event_drag(self):
        def delayed_event(action, _):
            command = action['command']
            card = self.own_hand().get(command.get('card'), {})
            return (command['type'] == 'play' and 'column' not in command
                    and self.defs.get(card.get('card_id'), {}).get('event_delay', 0) > 0)
        action = self.seek(delayed_event, 'playable delayed event')
        card = action['command']['card']
        deployment = self.begin_drag(card)
        assert len(deployment['targets']) == 1, 'A timed event should show its rules-selected queue destination'
        target = deployment['targets'][0]
        width, height = self.hud_dimensions()
        assert 0 <= target['screen'][0] < width and height * .12 <= target['screen'][1] < height * .73, 'Queued event marker is outside the usable battlefield'
        self.event('move', target['screen'])
        self.capture('07-event-drag-target')
        before = self.finish_drop(target)
        self.wait('event removed from hand', lambda: card not in self.own_hand())
        after = self.snapshot()
        queued = [entry for entry in after['view']['players'][after['seat']]['queue'] if entry and entry['id'] == card]
        resolved = any(event.get('source') == card and event.get('type') == 'event_resolve'
                       and event.get('revision') == before['view']['revision'] + 1 for event in after['view']['log'])
        assert len(queued) == 1 or resolved, 'Dragged event neither queued nor resolved under the current camp rules'
        if queued:
            queue = after['view']['players'][after['seat']]['queue']
            slot = next(index for index, entry in enumerate(queue) if entry and entry['id'] == card)
            side = after['seat']
            expected = (1700 if side == 0 else -1700, 2500 + (1 if side == 0 else -1) * (450 + slot * 350))
            assert max(abs(a-b) for a, b in zip(target['world'][:2], expected)) < 1, \
                'The highlighted queue destination differs from the actual rules-selected event slot'
        self.checked('Dragging an event uses its single rules-selected queue target and consumes exactly that hand card')

    def run(self):
        try:
            self.boot()
            self.test_camera()
            person = self.test_person_drag()
            self.test_stale_drag()
            punk = self.test_punk_placement()
            raider = self.test_raiders()
            self.frame_raiders(raider)
            self.test_idles([person, punk])
            self.reset_camera()
            self.test_event_drag()
            self.assert_roster()
            assets = assert_runtime_assets([self.folder / 'a.log', self.folder / 'b.log'])
            self.checked('Both native logs contain no missing game assets, material failures or fatal runtime errors')
            result = dict(ok=True, resolution=f'{self.dimensions[0]}x{self.dimensions[1]}',
                          checks=self.checks, screenshots=self.captures, evidence=self.evidence, runtime_assets=assets,
                          elapsed_seconds=round(time.monotonic()-self.started, 2), logs=str(self.folder))
            write_json(self.folder / 'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder / 'result.json', dict(ok=False, failure=str(error), checks=self.checks,
                screenshots=self.captures, evidence=self.evidence, last_reports=self.reports, logs=str(self.folder)))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='boomtown')
    parser.add_argument('--seed', type=int, default=2623)
    parser.add_argument('--port', type=int, default=19479)
    parser.add_argument('--timeout', type=float, default=600, help='Maximum seconds per resolution')
    parser.add_argument('--settle', type=float, default=.5)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 0 <= args.seed < 2**64:
        parser.error('--seed must be an unsigned 64-bit integer')
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-interactions-')
    output.mkdir(parents=True, exist_ok=True)
    print(f'Native interaction evidence: {output}', flush=True)
    started, results = time.monotonic(), []
    report = dict(ok=False, results=results, logs=str(output), ruleset=args.ruleset, seed=args.seed,
                  executable_mode='packaged' if args.package_dir else 'editor_game',
                  package_dir=str(args.package_dir.resolve()) if args.package_dir else None,
                  limitations=['Loopback peers on one computer.', 'Screenshots require visual review.',
                               'This suite checks deployed examples; it does not claim all-card art coverage.'])
    try:
        for index, size in enumerate(args.resolutions):
            results.append(InteractionScenario(args, output, size, index).run())
        report['ok'] = True
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        destinations = [output / 'result.json', ROOT / 'game/tests/reports/latest-native-interactions.json']
        if args.package_dir:
            destinations.append(ROOT / 'game/tests/reports/latest-packaged-interactions.json')
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_json(destination, report)
        print(json.dumps({key: value for key, value in report.items() if key != 'results'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
