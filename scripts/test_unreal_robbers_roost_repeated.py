"""Verify two legal Stampede bonuses, relaunch, cleanup and exact public views."""
import argparse
import hashlib
import json
from pathlib import Path
from test_unreal_robbers_roost_ground import RoostGroundScenario
from test_unreal_action_showcase import signature
from test_unreal_interactions import EDITOR, ROOT, write_json


class RepeatedRoostScenario(RoostGroundScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.repeated_checks = {}
        self.repeated_cleanup_samples = {}
        assert len(self.plan['bonuses']) == 2

    def verify_bonus_state(self, bonus, phase):
        key = str(bonus['water_event']['sequence']) + '-' + phase
        if key in self.repeated_checks:
            return
        for peer in ('a', 'b'):
            snapshot = self.snapshot(peer)
            expected = bonus[phase][snapshot['seat']]
            assert snapshot['view'] == expected['view'], key
            assert snapshot['actions'] == expected['actions'], key
            assert 'hand' not in snapshot['view']['players'][1-snapshot['seat']]
        self.repeated_checks[key] = True

    def choose_action(self, name, snapshot):
        for bonus in self.plan['bonuses']:
            if snapshot['view']['revision'] == bonus['before'][0]['view']['revision']:
                self.verify_bonus_state(bonus, 'before')
        return super().choose_action(name, snapshot)

    def observe(self, state):
        super().observe(state)
        c = state.get('cinematic', {})
        for bonus in self.plan['bonuses']:
            sequence = bonus['water_event']['sequence']
            if c.get('busy') and c.get('kind') == 'water' and c.get('sequence') == sequence:
                assert c['resource_only'] and not c['known_target'] and c['target'] == 0
                assert c['source'] == bonus['water_event']['source']
                assert all(u['id'] != c['source'] for u in c['units'])
                self.verify_bonus_state(bonus, 'after')
                self.repeated_cleanup_samples[sequence] = self.repeated_cleanup_samples.get(sequence, 0) + 1

    def run(self):
        self.build['repeated_roost_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            required = {b['water_event']['sequence'] for b in self.plan['bonuses']}
            captures = [c for c in self.capture_records if c['sequence'] in required
                        and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')]
            ok = (len(self.repeated_checks) == 4 and set(self.repeated_cleanup_samples) == required
                  and {c['sequence'] for c in captures} == required)
            result['repeated_bonus_review'] = dict(ok=ok, public_checks=self.repeated_checks,
                cleanup_samples=self.repeated_cleanup_samples, captures=captures,
                scope='Two successive legal bonuses and one relaunch at one placement. Simultaneous bonuses and interruption of a queued relaunch remain.')
            result['ok'] = bool(result['ok'] and ok)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], required=True)
    parser.add_argument('--glass-material', help='Require this exact clear-glass slot; amber must stay unchanged')
    parser.add_argument('--require-glass-backing', action='store_true',
                        help='Require at least 1cm of wooden head behind the projected circular rim')
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/robbers-roost/repeated-gameplay-plan-v001.json')
    args = parser.parse_args()
    assert not args.require_glass_backing or args.glass_material
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 21029, 750
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['raid_launch', 'event_advance', 'stampede_charge', 'water']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='robbers_roost_repeated', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    RepeatedRoostScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('ROBBERS_ROOST_REPEATED_PASSED', args.region, args.render_seat, flush=True)


if __name__ == '__main__':
    main()
