#!/usr/bin/env python3
"""Draw and play canonical Karli through legal two-peer actions; verify Quanah visuals."""
import argparse
import time
from pathlib import Path
from test_unreal_asset_history import HistoryScenario
from test_unreal_interactions import EDITOR, field_cards, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

MESH = '/Game/Art/Western/Quanah/SK_Quanah.SK_Quanah'


class QuanahScenario(HistoryScenario):
    def verify_figure(self, identity):
        def figure():
            return next((u for u in self.read()['cinematic']['units'] if u['id'] == identity), None)
        unit = self.wait('Quanah figure', figure)
        assert unit['card_id'] == 'quanah_parker'
        assert unit['visual_mesh'] == MESH, unit
        assert unit['unarmed'] and not unit['weapon_visible']
        return unit

    def run(self):
        try:
            self.boot()
            action = self.seek(lambda a, _: a['command']['type'] == 'play' and
                               self.own_hand().get(a['command'].get('card'), {}).get('card_id') == 'quanah_parker',
                               'draw and afford Quanah Parker', max_actions=240)
            identity = action['command']['card']
            card = self.own_hand()[identity]
            assert card['name'] == 'Quanah Parker', 'Authoritative name must remain canonical'
            labels = self.wait('drawn card label arranged', lambda:
                              [x['label'] for x in self.hud()['battlefield_labels'] if x['id'] == identity])
            assert labels and all('Quanah Parker' in label for label in labels), labels
            self.check_note(identity, 'quanah-parker')
            self.inspect(identity)
            self.capture('quanah-drawn-inspector')
            self.checked('Legally drawn Karli displays Quanah name and sourced history; canonical identity preserved')
            # History is presentation-only, so this previously offered play is still legal.
            self.submit('a', action)
            self.settle_presentation()
            deployed = next(c for c in field_cards(self.snapshot()) if c['id'] == identity)
            assert deployed['card_id'] == 'quanah_parker' and deployed['name'] == 'Quanah Parker'
            assert deployed['ready'], 'Karli/Quanah still enters ready'
            self.verify_figure(identity)
            self.inspect(identity)
            self.capture('quanah-played')
            labels = [x['label'] for x in self.hud()['battlefield_labels'] if x['id'] == identity]
            assert labels and all('Quanah Parker' in label and 'Karli' not in label for label in labels), labels
            for peer in ('a', 'b'):
                other = next(c for c in field_cards(self.snapshot(peer)) if c['id'] == identity)
                assert other['card_id'] == 'quanah_parker' and other['ready']
            self.checked('Both peers retain canonical card and enter-ready trait; field label is Quanah Parker')
            attack = self.seek(lambda a, _: a['command'].get('source') == identity and
                               a['command']['type'] == 'activate', 'Quanah original damage ability')
            self.submit('a', attack)
            while self.snapshot()['view'].get('choice'):
                actor = next(p for p in ('a', 'b') if self.snapshot(p)['actions'])
                self.submit(actor, self.snapshot(actor)['actions'][0])
            self.wait('attack presentation finishes', lambda: not self.read()['cinematic']['busy'], 45)
            self.verify_figure(identity)
            self.capture('quanah-after-original-ability')
            self.checked('Original legal damage ability completes with Quanah presentation')
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
    p.add_argument('--port', type=int, default=21479)
    p.add_argument('--ruleset', default='boomtown')
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--settle', type=float, default=.5)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for index, size in enumerate(args.resolutions):
            results.append(QuanahScenario(args, args.output, size, index).run())
    finally:
        write_json(args.output/'result.json', dict(ok=len(results)==len(args.resolutions), results=results))
