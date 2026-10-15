"""Native station return, optional History and two-copy restriction review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_wanted_board import WantedBoardScenario


class StationScenario(WantedBoardScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.preparations, self.returns, self.return_state = [], [], None

    def boot(self):
        if self.args.render_seat == 0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)
        self.check_note(self.plan['holding'], 'holding-pony-express-station')
        self.capture('pony-express-station-battlefield')

    def observe(self, state):
        QueueScenario.observe(self, state)
        c = state.get('cinematic', {})
        if not c.get('busy'):
            return
        if c.get('kind') == 'ability' and c.get('source') == self.plan['holding']:
            holding = next(u for u in c['units'] if u['id'] == self.plan['holding'])
            assert holding['animated_part_count'] == 0
            visible = [p for p in holding['holding_components'] if p['visible']]
            assert any('/SM_Holding_PonyExpressStation.' in p['mesh'] for p in visible)
            assert any('/SM_HoldingBase_PonyExpressStation.' in p['mesh'] for p in visible)
            ground = next(p for p in visible if '/SM_HoldingBase_PonyExpressStation.' in p['mesh'])
            assert ground['ground_fit']['enabled'] == 1 and ground['ground_fit']['region'] == self.args.region
            assert ground['ground_fit']['foundation_extent'] == [200, 280, 60]
            assert not c.get('action_effects'), 'Station spawned unrelated mechanism props'
            self.preparations.append(dict(sequence=c['sequence'], elapsed=c['elapsed'], holding=copy.deepcopy(holding)))
        if c.get('kind') == 'return' and c.get('target') == self.plan['target']:
            self.returns.append(copy.deepcopy(c))

    def choose_action(self, name, snapshot):
        action = QueueScenario.choose_action(self, name, snapshot)
        if snapshot['view']['revision'] == self.plan['after_return'][0]['view']['revision']:
            peers = {}
            for peer in ('a', 'b'):
                actual = self.snapshot(peer)
                expected = self.plan['after_return'][actual['seat']]
                assert actual['view']['players'] == expected['view']['players']
                assert actual['actions'] == expected['actions']
                peers[peer] = copy.deepcopy(actual)
            self.return_state = peers
            self.capture('returned-veteran-and-copy-blocked')
        return action

    def run(self):
        self.build['station_harness'] = signature(__file__)
        self.build['history_helper'] = signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json', self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            captures = [c for c in result['captures'] if c['kind'] == 'return'
                        and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')]
            sequences = {p['sequence'] for p in self.preparations}
            preparation_captures = [c for c in result['captures'] if c['kind'] == 'ability'
                and c['sequence'] in sequences and c.get('native_phase_bracket_valid')
                and c.get('painted_beat_bracket_valid')]
            result['station_review'] = dict(history=self.notes, rendered_seat=self.args.render_seat,
                region=self.args.region, preparations=self.preparations, return_samples=self.returns,
                returned_public_states=self.return_state, return_captures=captures,
                preparation_captures=preparation_captures,
                limits='One legal two-copy replay at the recorded placement per rendered seat/region. Source ground audit and actual regional visuals require separate review. Drifter exception, interruptions, broader lifecycles, effects/audio and packaging remain.')
            result['ok'] = bool(result['ok'] and self.return_state and self.returns and captures
                                and self.preparations and preparation_captures and set(self.notes) == {'holding-pony-express-station'})
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/pony-express-station/gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=0)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20439+args.render_seat*10, 400
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter', 'damage', 'return']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='pony-express-station', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    StationScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('PONY_EXPRESS_STATION_NATIVE_PASSED', flush=True)


if __name__ == '__main__':
    main()
