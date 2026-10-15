#!/usr/bin/env python3
"""Verify opt-in history through real Slate clicks and legal two-peer setup."""
import argparse
import copy
from pathlib import Path
import time

from test_unreal_raiders_vehicle import VehicleScenario
from test_unreal_interactions import EDITOR, center, field_cards, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class HistoryScenario(VehicleScenario):
    def inspect(self, identity):
        self.command('a', 'inspect', card=identity)
        self.wait('selected asset', lambda: self.hud()['inspected_card'] == identity)
        time.sleep(.3)

    def history_link(self):
        return next((b for b in self.hud()['status_buttons']
                     if b['id'] == 'asset_history' and b['allocated_size'][0] > 1), None)

    def check_note(self, identity, key):
        self.inspect(identity)
        note = self.wait('history link arranged', lambda: self.history_link())
        assert self.hud()['asset_history']['key'] == key
        assert not self.hud()['asset_history']['open'], 'History must start closed'
        self.event('move', center(note))
        time.sleep(.7)
        assert not self.hud()['asset_history']['open'], 'Hover must not open history'
        before = {peer: copy.deepcopy(self.snapshot(peer)) for peer in ('a', 'b')}
        self.capture(key + '-closed')
        self.click(center(note))
        self.wait('history open by explicit click', lambda: self.hud()['asset_history'].get('open'))
        history = self.hud()['asset_history']
        assert len(history['body'].splitlines()) == 3
        assert history['url'].startswith('https://')
        width, height = self.hud_dimensions()
        self.event('move', (width * .5, height * .35))
        self.capture(key + '-open')
        for peer in ('a', 'b'):
            assert self.snapshot(peer)['view'] == before[peer]['view']
            assert self.snapshot(peer)['actions'] == before[peer]['actions']
        for phase in ('down', 'up'):
            self.command('a', 'ui_key', key='Escape', phase=phase, preserve_focus=True)
        self.wait('Escape closes history', lambda: not self.hud().get('asset_history', {}).get('open', False))
        # A second explicit click opens it again; an outside click closes it.
        self.inspect(identity)
        self.click(center(self.wait('history reopens', self.history_link)))
        self.wait('history reopened', lambda: self.hud()['asset_history'].get('open'))
        width, height = self.hud_dimensions()
        self.click((width * .5, height * .35))
        self.wait('outside click closes history', lambda: not self.hud().get('asset_history', {}).get('open', False))
        for peer in ('a', 'b'):
            assert self.snapshot(peer)['view'] == before[peer]['view']
            assert self.snapshot(peer)['actions'] == before[peer]['actions']
        # The same optional note is available in the existing Battle Plan.
        self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
        self.wait('Battle Plan opens', lambda: self.hud()['battle_plan_open'])
        self.inspect(identity)
        # Compact the existing sections so details are reachable at 720p too.
        for section_id in ('your.hand', 'your.formation', 'your.events'):
            section = next(b for b in self.hud()['battle_sections'] if b['id'] == section_id)
            if not section['collapsed']:
                following = {'your.hand': 'your.formation', 'your.formation': 'your.events',
                             'your.events': 'your.details'}[section_id]
                old_rect = next(b for b in self.hud()['battle_sections'] if b['id'] == following)['min']
                self.click(center(section))
                self.wait('section collapsed', lambda: next(b for b in self.hud()['battle_sections']
                          if b['id'] == section_id)['collapsed'])
                self.wait('collapsed layout arranged', lambda: next((b for b in self.hud()['battle_sections']
                          if b['id'] == following and b['allocated_size'][0] > 1 and b['min'] != old_rect), None))
        self.click(center(self.wait('Battle Plan history link', self.history_link)))
        self.wait('Battle Plan history opens', lambda: self.hud()['asset_history'].get('open'))
        assert self.hud()['asset_history']['key'] == key
        self.capture(key + '-battle-plan')
        for phase in ('down', 'up'):
            self.command('a', 'ui_key', key='Escape', phase=phase, preserve_focus=True)
        self.wait('Battle Plan history closes', lambda: not self.hud().get('asset_history', {}).get('open', False))
        self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
        self.wait('Battle Plan closes', lambda: not self.hud()['battle_plan_open'])
        for peer in ('a', 'b'):
            assert self.snapshot(peer)['view'] == before[peer]['view']
            assert self.snapshot(peer)['actions'] == before[peer]['actions']
        self.evidence[key] = history
        self.checked(key + ': closed on selection/hover; opens in inspector/Battle Plan; closes on Escape/outside; both peers unchanged')

    def run(self):
        try:
            self.boot()
            raid = self.find_raid('a')
            self.submit('a', raid)
            self.settle_presentation()
            seat = self.snapshot()['seat']
            herd = next(c for c in self.snapshot()['view']['players'][seat]['queue']
                        if c and c.get('card_id') == 'stampede')
            self.check_note(herd['id'], 'stampede')
            camp = next(c for c in field_cards(self.snapshot()) if c['type'] == 'camp')
            self.inspect(camp['id'])
            assert not self.history_link(), 'Unrebranded assets must not get invented history'
            self.checked('Unrebranded assets have no History link')
            action = self.seek(lambda a, _: a['command']['type'] == 'junk' and
                               self.junk_kind(self.own_hand().get(a['command'].get('card'), {})) == 'punk',
                               'legal drifter recruitment')
            self.submit('a', action)
            placement = self.wait('drifter placement', lambda: next((a for a in self.snapshot()['actions']
                                  if a.get('placement', {}).get('punk')), None))
            self.submit('a', placement)
            self.settle_presentation()
            drifter = next(c for c in field_cards(self.snapshot()) if c.get('punk'))
            self.check_note(drifter['id'], 'drifter')
            assert self.evidence['drifter']['title'] == 'Drifter - a fictional frontier hand'
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280,720), (1920,1080)])
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--port', type=int, default=21179)
    parser.add_argument('--ruleset', default='boomtown')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--settle', type=float, default=.3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for index, size in enumerate(args.resolutions):
            results.append(HistoryScenario(args, args.output, size, index).run())
    finally:
        write_json(args.output/'result.json', dict(ok=len(results)==len(args.resolutions), results=results))
