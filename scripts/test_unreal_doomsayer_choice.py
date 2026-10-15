#!/usr/bin/env python3
"""Exercise Pinkerton Agent's printed 'may' through two real packaged Linux peers.

Only legal draws, passes and plays prepare the position. No state injection.
720p declines the effect; 1080p accepts it using the actual Slate button.
"""
import argparse
import json
from pathlib import Path
from test_unreal_raiders_vehicle import VehicleScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class DoomsayerScenario(VehicleScenario):
    def run(self):
        try:
            self.boot()
            play = self.seek(lambda a, s: a['command']['type'] == 'play'
                and self.own_hand().get(a['command'].get('card'), {}).get('card_id') == 'pinkerton_agent',
                'Pinkerton Agent', max_actions=180)
            card = play['command']['card']
            raid = self.find_raid('b')
            self.submit('b', raid)
            self.pass_turn('b')
            self.settle_presentation()
            enemy = self.snapshot('b')['seat']
            before = self.snapshot()['view']['players'][enemy]['queue']
            assert before[1] and before[1]['card_id'] == 'stampede' and not before[2]
            play = next(a for a in self.snapshot()['actions'] if a['command']['type'] == 'play'
                        and a['command'].get('card') == card)
            self.submit('a', play)
            self.settle_presentation()
            pending = self.snapshot()
            assert pending['view']['players'][enemy]['queue'] == before, 'Events moved before the optional decision'
            assert 'Pinkerton Agent' in pending['view']['choice']['prompt']
            assert len(pending['actions']) == 2 and not self.snapshot('b')['actions']
            assert 'options' not in self.snapshot('b')['view']['choice'], 'Private choices leaked to the other player'
            delay = self.dimensions[0] >= 1920
            wanted = next(a for a in pending['actions'] if a['label'].startswith('Delay') == delay)
            def arranged():
                return next((w for w in self.hud().get('master_actions', [])
                    if json.loads(w['id']) == wanted['command']
                    and all(size > 1 for size in w.get('allocated_size', [])) and self.inside(w)), None)
            button = self.wait('Pinkerton Agent choice arranged', arranged)
            self.capture('doomsayer-optional-delay')
            self.click(center(button))
            self.wait('choice accepted by both peers', lambda: self.agree()
                and self.snapshot()['view']['revision'] > pending['view']['revision'])
            self.settle_presentation()
            after = self.snapshot()['view']['players'][enemy]['queue']
            assert self.snapshot()['view']['choice'] is None
            assert after == ([None, None, before[1]] if delay else before), (before, after, delay)
            assert after == self.snapshot('b')['view']['players'][enemy]['queue']
            self.checked('Pinkerton Agent presents an optional decision before moving events; real Slate '
                         + ('Delay moves Stampede from slot 2 to 3' if delay else 'Skip preserves the enemy queue')
                         + '; both network peers agree')
            self.capture('doomsayer-choice-resolved')
            result = dict(ok=True, checks=self.checks, screenshots=self.captures,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder/'result.json', dict(ok=False, error=str(error), last=self.read()))
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
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--port', type=int, default=19959)
    parser.add_argument('--ruleset', default='boomtown')
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--settle', type=float, default=.5)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for index, dimensions in enumerate(args.resolutions):
            results.append(DoomsayerScenario(args, args.output, dimensions, index).run())
    finally:
        write_json(args.output/'result.json', dict(ok=len(results) == len(args.resolutions), results=results))
