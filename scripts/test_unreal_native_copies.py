#!/usr/bin/env python3
"""Verify all three native models, per-copy art, history, legal return/replay and reconnect on two real peers."""
import argparse
import math
import time
from pathlib import Path
from test_unreal_asset_history import HistoryScenario
from test_unreal_interactions import EDITOR, field_cards, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

MESH = '/Game/Art/Western/Quanah/SK_Quanah.SK_Quanah'


class NativeCopiesScenario(HistoryScenario):
    def tab(self, side):
        # Collapsed/virtualized formation tiles need not be arranged to use
        # the hand. The drag helper separately checks its visible hit target.
        from test_unreal_interactions import center
        entry = self.wait('master tab arranged', lambda: next((x for x in self.hud().get('master_tabs', [])
            if x['id'] == side and x['allocated_size'][0] > 1), None))
        self.click(center(entry))
        expected = self.snapshot()['seat'] if side == 'your' else 1 - self.snapshot()['seat']
        self.wait('selected master side', lambda: self.hud()['inspector_side'] == expected)
        time.sleep(.2)

    def check_crew_portrait(self, identity, visual, mesh):
        # Person portraits are shown by the real Battle Plan drag preview;
        # selecting a world figure only opens its text inspector.
        from test_unreal_interactions import center
        from test_unreal_portraits import portraits_ready
        self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
        self.wait('Battle Plan opens for portrait', lambda: self.hud()['battle_plan_open'])
        hand = self.wait('hand section arranged', lambda: next((b for b in self.hud()['battle_sections']
            if b['id'] == 'your.hand' and b['allocated_size'][0] > 1 and b['min'][0] > 0), None))
        if hand['collapsed']:
            self.click(center(hand))
            self.wait('hand expanded', lambda: not next(b for b in self.hud()['battle_sections'] if b['id'] == 'your.hand')['collapsed'])
        time.sleep(.3)
        formation = next(b for b in self.hud()['battle_sections'] if b['id'] == 'your.formation')
        if formation['collapsed']:
            self.click(center(formation))
            self.wait('formation expanded for hand navigation', lambda: not next(b for b in self.hud()['battle_sections'] if b['id'] == 'your.formation')['collapsed'])
        time.sleep(.3)
        before = {p: self.snapshot(p) for p in ('a', 'b')}
        self.begin_drag(identity)
        self.wait('Crew drag portrait rendered', lambda: portraits_ready(self.hud()['portraits'], [visual]), 60)
        scene = next(s for s in self.hud()['portraits']['scenes'] if s['card_id'] == visual)
        assert scene['people'] and scene['people'][0]['visual_mesh'] == mesh, scene
        self.capture(visual + '-hand-portrait')
        for phase in ('down', 'up'):
            self.command('a', 'ui_key', key='Escape', phase=phase, preserve_focus=True)
        self.event('up')
        self.wait('portrait drag cancelled', lambda: self.hud().get('deployment', {}).get('card', -1) == -1)
        assert {p: self.snapshot(p) for p in ('a', 'b')} == before
        self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
        self.wait('Battle Plan closes after portrait', lambda: not self.hud()['battle_plan_open'])

    def verify_figure(self, identity, visual, canonical, mesh):
        unit = self.wait(visual + ' figure', lambda: next((u for u in self.read()['cinematic']['units'] if u['id'] == identity), None))
        assert unit['card_id'] == canonical and unit['visual_id'] == visual, unit
        assert unit['visual_mesh'] == mesh and unit['unarmed'] and not unit['weapon_visible'], unit
        self.evidence.setdefault('figures', {})[visual] = unit

    def close_model(self, identity, visual):
        unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == identity)
        width, height = self.hud_dimensions()
        viewport = self.hud()['viewport_size']
        spot = (width * .58, height * .28)
        for _ in range(3):
            camera = self.camera_state()
            delta = [unit['location'][axis] - camera['focus'][axis] for axis in range(2)]
            if max(abs(value) for value in delta) < 2:
                break
            yaw = math.radians(camera['yaw'])
            right, forward = (-math.sin(yaw), math.cos(yaw)), (-math.cos(yaw), -math.sin(yaw))
            x = -sum(a*b for a,b in zip(delta,right)) / (camera['distance']*.0012)
            y = sum(a*b for a,b in zip(delta,forward)) / (camera['distance']*.0012)
            self.event('down', spot, button='middle')
            self.event('move', (spot[0]+x*width/viewport[0],spot[1]+y*height/viewport[1]), button='middle')
            self.event('up', button='middle')
        for _ in range(4):
            distance = self.camera_state()['distance']
            if abs(distance-500)<2:break
            self.event('wheel',spot,wheel=max(-10,min(10,math.log(500/distance)/math.log(.88))))
        assert abs(self.camera_state()['distance']-500)<2
        yaw = -90 if unit['side'] == 0 else 90
        for _ in range(4):
            current = self.camera_state()
            delta = (yaw-current['yaw']+180)%360-180
            pitch = 15-current['pitch']
            if abs(delta)<.1 and abs(pitch)<.1:
                break
            self.event('down',spot,button='right')
            self.event('move',(spot[0]+max(-500,min(500,-delta/.22))*width/viewport[0],
                               spot[1]+max(-500,min(500,pitch/.18))*height/viewport[1]),button='right')
            self.event('up',button='right')
        from test_unreal_interactions import center
        text = self.hud().get('battlefield_text_visible',False)
        if text:self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='battlefield_text')))
        self.event('move',spot)
        self.capture(visual+'-close-model')
        if text:self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='battlefield_text')))
        self.reset_camera()

    def settle_choices(self):
        while self.snapshot()['view'].get('choice'):
            actor = next(p for p in ('a', 'b') if self.snapshot(p)['actions'])
            actions = self.snapshot(actor)['actions']
            self.submit(actor, next((a for a in actions if 'Skip' in a['label']), actions[0]))
        self.settle_presentation()

    def run(self):
        try:
            self.boot()
            identities = {}
            specs = [('lozen', 'pinkerton_agent', 'Lozen', 'Lozen'),
                     ('sarah-winnemucca', 'sarah_winnemucca', 'Sarah Winnemucca', 'Sarah'),
                     ('quanah-parker', 'quanah_parker', 'Quanah Parker', 'Quanah')]
            for visual, canonical, display, directory in specs:
                def matches(a, snapshot):
                    identity = a['command'].get('card')
                    card = self.own_hand().get(identity, {})
                    return (a['command']['type'] == 'play' and card.get('card_id') == canonical
                            and snapshot.get('cosmetics', {}).get(str(identity)) == visual)
                action = self.seek(matches, 'draw and afford ' + display, max_actions=440)
                identity = identities[visual] = action['command']['card']
                assert self.own_hand()[identity]['name'] == self.defs[canonical]['name']
                assert str(identity) not in self.snapshot('b').get('cosmetics', {}), 'Private named hand leaked'
                labels = self.wait('named hand label', lambda: [x['label'] for x in self.hud()['battlefield_labels'] if x['id'] == identity])
                assert all(display in label for label in labels), labels
                self.check_note(identity, visual)
                mesh = f'/Game/Art/Western/{directory}/SK_{directory}.SK_{directory}'
                self.check_crew_portrait(identity, visual, mesh)
                self.submit('a', action)
                self.settle_choices()
                self.verify_figure(identity, visual, canonical, mesh)
                for peer in ('a', 'b'):
                    card = next(c for c in field_cards(self.snapshot(peer)) if c['id'] == identity)
                    assert card['card_id'] == canonical and card['name'] == self.defs[canonical]['name']
                    assert self.snapshot(peer)['cosmetics'][str(identity)] == visual
                self.inspect(identity)
                self.capture(visual + '-field')
                self.close_model(identity, visual)
                self.checked(display + ': correct hand/portrait/model/history; canonical card preserved; both peers agree')
            # Use Sarah's original legal return, then replay the very same Lozen copy.
            sarah, lozen = identities['sarah-winnemucca'], identities['lozen']
            if self.snapshot()['view']['players'][self.snapshot()['seat']]['water'] < 1:
                water = next(a for a in self.snapshot()['actions'] if a['command']['type']=='junk' and
                             self.junk_kind(self.own_hand().get(a['command'].get('card'), {}))=='water')
                self.submit('a',water)
                self.settle_choices()
            activate = self.seek(lambda a, _: a['command']['type'] == 'activate' and a['command'].get('source') == sarah,
                                 'Sarah original return ability')
            self.submit('a', activate)
            choice = self.wait('return choice', lambda: self.snapshot()['view'].get('choice'))
            target = next(o for o in choice['options'] if 'Pinkerton Agent' in o['label'])
            self.submit('a', next(a for a in self.snapshot()['actions'] if a['command'].get('option') == target['id']))
            self.settle_choices()
            assert lozen in self.own_hand() and self.snapshot()['cosmetics'][str(lozen)] == 'lozen'
            assert str(lozen) not in self.snapshot('b')['cosmetics']
            replay = self.seek(lambda a, _: a['command']['type'] == 'play' and a['command'].get('card') == lozen, 'replay Lozen')
            self.submit('a', replay)
            self.settle_choices()
            self.verify_figure(lozen, 'lozen', 'pinkerton_agent', '/Game/Art/Western/Lozen/SK_Lozen.SK_Lozen')
            self.capture('lozen-returned-and-replayed')
            self.checked('Sarah returns Lozen through her unchanged ability; private hand masks name; replay retains exact model')
            baseline = {p: self.snapshot(p) for p in ('a', 'b')}
            self.command('a', 'leave')
            self.wait('guest leaves', lambda: self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('guest reconnects', self.agree, 90)
            self.settle_presentation()
            assert {p:self.snapshot(p) for p in ('a', 'b')} == baseline
            for visual, canonical, display, directory in specs:
                self.verify_figure(identities[visual], visual, canonical, f'/Game/Art/Western/{directory}/SK_{directory}.SK_{directory}')
            self.capture('all-three-after-reconnect')
            self.checked('Reconnect restores exact private/public snapshots and all three native models')
            result = dict(ok=True, checks=self.checks, screenshots=self.captures, evidence=self.evidence,
                          package_directory=str(self.runtime.package_root),
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            try:
                self.capture('failure')
            except Exception:
                pass
            write_json(self.folder/'result.json', dict(ok=False, error=str(error), checks=self.checks, last=self.read()))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor', type=Path, default=EDITOR)
    p.add_argument('--package-dir', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280,720), (1920,1080)])
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--port', type=int, default=21579)
    p.add_argument('--ruleset', default='boomtown')
    p.add_argument('--timeout', type=float, default=1200)
    p.add_argument('--settle', type=float, default=.5)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for index, size in enumerate(args.resolutions):
            results.append(NativeCopiesScenario(args, args.output, size, index).run())
    finally:
        write_json(args.output/'result.json', dict(ok=len(results)==len(args.resolutions), results=results))
