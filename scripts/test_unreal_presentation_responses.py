#!/usr/bin/env python3
"""Observe required responses across real cinematics and movable HUD panels.

Only ordinary legal actions arrange the match. The local response is completed
with actual Slate drag input, and every cinematic under review ends naturally.
"""
import argparse
import copy
import hashlib
import time
from pathlib import Path

from test_unreal_presentation_ui import PresentationScenario
from test_unreal_interactions import EDITOR, ROOT, arranged_widget, card_handle, center, field_cards, resolution, write_json
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_action_showcase import painted_beat


class ResponseScenario(PresentationScenario):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.paint_keys = set()
        self.action_paints = set()

    def read(self, name='a'):
        state = super().read(name)
        if name == 'a':
            for transition in state.get('hud', {}).get('paint', {}).get('transitions', []):
                key = (transition.get('match_id'), transition.get('frame'), transition.get('sequence'),
                       transition.get('view_generation'), transition.get('busy'),
                       tuple(transition.get('visible_docks', [])), transition.get('end_panel_visible'))
                if key in self.paint_keys:
                    continue
                self.paint_keys.add(key)
                self.evidence.setdefault('actual_paint_transitions', []).append(copy.deepcopy(transition))
                if transition.get('busy'):
                    self.action_paints.add((transition.get('match_id'), transition.get('sequence')))
                    assert not transition.get('visible_docks'), 'An actual first/action paint contains HUD docks'
                    assert not transition.get('end_panel_visible'), 'An actual action paint contains the match-end panel'
        return state

    def painted_cinematic(self):
        state = self.read()
        beat = painted_beat(state)
        scene = state.get('cinematic', {})
        return state if (scene.get('busy') and beat and beat.get('busy') and
                         beat.get('sequence') == scene.get('sequence') and
                         beat.get('match_id') == state.get('snapshot', {}).get('match_id')) else None

    def seek_punk(self, target):
        for _ in range(160):
            current = self.snapshot(target)
            action = next((a for a in current.get('actions', []) if a['command']['type'] == 'junk'
                           and self.junk_kind(self.own_hand(target).get(a['command'].get('card'), {})) == 'punk'), None)
            if action:
                self.settle_presentation()
                return action
            assert current['view']['status'] == 'actions', 'Match ended during legal response preparation'
            actor = next(n for n in ('a', 'b') if self.snapshot(n).get('actions'))
            options = self.snapshot(actor)['actions']
            if options[0]['command']['type'] == 'choose':
                action = next((a for a in options if a.get('label') == 'Skip'), options[0])
            else:
                action = next((a for a in options if actor == target and a['command']['type'] == 'draw'), None)
                action = action or next(a for a in options if a['command']['type'] == 'end_turn')
            self.submit(actor, action)
            self.settle_presentation()
        raise AssertionError('Could not reach a legal punk response')

    def open_overview(self):
        if not self.hud()['overview_open']:
            button = next(b for b in self.hud()['camera_buttons'] if b['id'] == 'ability_overview')
            self.click(center(button))
        self.wait('overview is visible', lambda: self.hud()['overview_open'] and self.panel('overview')['visible'])
        self.wait('overview camera is settled', lambda: self.camera_state().get('birds_eye') and self.camera_state()['pitch'] >= 75)

    def natural_response_scene(self, actor, action, label):
        self.submit(actor, action)
        state = copy.deepcopy(self.wait('response has a correlated painted cinematic', self.painted_cinematic))
        assert state['snapshot']['view']['choice'] is not None
        assert not state['hud']['chrome_visible']
        assert all(not p['visible'] for p in state['hud']['dock_panels'])
        self.evidence[label + '_during_scene'] = state
        # This is the same HUD setter as G; it must not discard a queued scene.
        self.command('a', 'battle_overview', open=True)
        after = self.read()
        assert after['cinematic']['busy'], 'Overview request interrupted the cinematic'
        assert after['cinematic']['sequence'] == state['cinematic']['sequence'], 'Overview request discarded the current shot'
        self.capture(label + '-cinematic')
        self.wait('cinematic finishes naturally', lambda: not self.read()['cinematic']['busy'], 60)
        self.wait('HUD returns after cinematic', lambda: self.hud()['chrome_visible'])

    def test_responses(self):
        action = self.seek_punk('a')
        actions = self.wait('actions panel', lambda: self.panel('actions'))
        if not actions['collapsed']:
            self.click(center(actions['collapse_button']))
        self.wait('actions panel is folded', lambda: self.panel('actions')['collapsed'])
        self.open_overview()
        self.natural_response_scene('a', action, '03-local-response')
        self.wait('own response surfaces', lambda: not self.hud()['overview_open'] and self.panel('actions')['visible'])
        assert not self.panel('actions')['collapsed'], 'Required response stayed folded'
        self.capture('04-local-response-visible')
        widget = self.wait('visible punk placement button', lambda: next((w for w in self.hud()['placement_drag_buttons']
                           if card_handle(w) == 0 and arranged_widget(w)), None))
        before = {c['id'] for c in field_cards(self.snapshot())}
        deployment = self.begin_drag(0, widget)
        target = self.target(deployment)
        self.finish_drop(target)
        created = [c for c in field_cards(self.snapshot()) if c['id'] not in before]
        assert len(created) == 1 and created[0]['punk']
        self.wait('punk entrance finishes naturally', lambda: not self.read()['cinematic']['busy'], 60)
        self.checked('A required response closes Overview, expands folded Actions after its complete cinematic, and accepts a real placement drag')

        action = self.seek_punk('b')
        self.open_overview()
        self.natural_response_scene('b', action, '05-opponent-response')
        self.wait('observer overview returns', lambda: self.hud()['overview_open'] and self.panel('overview')['visible'])
        assert self.snapshot()['view']['choice']['player'] != self.snapshot()['seat']
        self.capture('06-opponent-response-overview')
        self.checked('The other player\'s required response preserves the observer\'s overview after the complete cinematic')
        response = self.snapshot('b')['actions'][0]
        self.submit('b', response)
        self.wait('opponent response settles', lambda: not self.read()['cinematic']['busy'], 60)

    def run(self):
        try:
            self.boot()
            self.capture('02-dressed-ground-dashboard')
            self.test_responses()
            assert self.action_paints, 'No actual painted action frames were observed'
            self.checked('Every retained actual action paint hides docks and the match-end panel, including first frames')
            assets = assert_runtime_assets([self.folder/'a.log', self.folder/'b.log'])
            result = dict(ok=True, checks=self.checks, evidence=self.evidence, screenshots=self.captures, runtime_assets=assets)
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder/'result.json', dict(ok=False, failure=str(error), checks=self.checks,
                       evidence=self.evidence, screenshots=self.captures, last_reports=self.reports))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1920,1080),(1280,720)])
    parser.add_argument('--ruleset', default='boomtown')
    parser.add_argument('--seed', type=int, default=2623)
    parser.add_argument('--port', type=int, default=19779)
    parser.add_argument('--timeout', type=float, default=500)
    parser.add_argument('--settle', type=float, default=.25)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-presentation-responses-')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(ok=False, results=[], limits=['Same workstation peers; screenshots still require visual review.'],
                  ground_map_sha256=hashlib.sha256((ROOT/'game/OldWest/Content/Maps/WaterDepotV2.umap').read_bytes()).hexdigest())
    print(f'Response UI evidence: {output}', flush=True)
    try:
        for index, size in enumerate(args.resolutions):
            report['results'].append(ResponseScenario(args, output, size, index).run())
        report['ok'] = True
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        write_json(output/'result.json', report)


if __name__ == '__main__':
    main()
