"""Native regional Robbers Roost fitting with legal trait and public-state checks."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from test_unreal_robbers_roost import RoostScenario
from test_unreal_action_showcase import signature
from test_unreal_interactions import EDITOR, ROOT, write_json


class RoostGroundScenario(RoostScenario):
    def observe(self, state):
        super().observe(state)
        if getattr(self.args, 'glass_material', None):
            for effect in state.get('cinematic', {}).get('action_effects', []):
                if 'SM_Action_BonusWhiskeyGlass' in effect.get('mesh', ''):
                    assert effect['materials'] == [self.args.glass_material,
                        '/Game/Art/ActionProps/BonusWhiskey/M_Bonus_Amber.M_Bonus_Amber']
                    if getattr(self.args, 'require_glass_backing', False):
                        # Project the circular rim onto its support plane. The
                        # authored barrel head is 26cm * .9, not its wider belly.
                        camera = state['cinematic']['camera_location']
                        center = effect['location']
                        top = effect['bounds'][1][2]
                        assert camera[2] > top
                        ratio = (camera[2] - center[2]) / (camera[2] - top)
                        radius = (effect['bounds'][1][0] - effect['bounds'][0][0]) / 2
                        projected_radius = math.dist(camera[:2], center[:2]) * (ratio - 1) + radius * ratio
                        margin = 23.4 - projected_radius
                        assert margin >= 1, f'Glass rim lacks wooden backing: {margin:.3f}cm'
                        self.glass_backing_minimum_cm = min(
                            getattr(self, 'glass_backing_minimum_cm', margin), margin)
        for unit in state.get('cinematic', {}).get('units', []):
            if unit.get('card_id') != 'robbers_roost':
                continue
            base = next(p for p in unit['holding_components']
                        if '/SM_HoldingBase_RobbersRoost.' in p['mesh'])
            fit = base['ground_fit']
            assert fit and fit['enabled'] == 1 and fit['region'] == self.args.region
            assert fit['foundation_extent'] == [275, 240, 60]

    def run(self):
        self.build['roost_ground_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            result['robbers_roost_review'].update(
                region=self.args.region, ground_fit_required=True,
                required_glass_material=getattr(self.args, 'glass_material', None),
                glass_backing_minimum_cm=getattr(self, 'glass_backing_minimum_cm', None),
                limits='One legal native placement in this region. Actual image review and independent source-surface/root audit are separate. Other placements, battlefield conditions, interruptions, effects/audio and packaging remain.')
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], required=True)
    parser.add_argument('--glass-material', help='Require this exact clear-glass slot; amber must stay unchanged')
    parser.add_argument('--require-glass-backing', action='store_true',
                        help='Require at least 1cm of wooden head behind the projected circular rim')
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/robbers-roost/gameplay-plan-v002.json')
    args = parser.parse_args()
    assert not args.require_glass_backing or args.glass_material
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20979, 500
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['raid_launch', 'event_advance', 'stampede_charge', 'water']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='robbers_roost_ground', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    RoostGroundScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('ROBBERS_ROOST_GROUND_PASSED', args.region, args.render_seat, flush=True)


if __name__ == '__main__':
    main()
