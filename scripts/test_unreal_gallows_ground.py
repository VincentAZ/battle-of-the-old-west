"""Native Gallows terrain fitting, full legal response and public identity checks."""
import argparse
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_gallows import GallowsScenario
from test_unreal_interactions import EDITOR, ROOT, write_json


class GallowsGroundScenario(GallowsScenario):
    def observe(self, state):
        super().observe(state)
        for unit in state.get('cinematic', {}).get('units', []):
            if unit.get('card_id') != 'gallows':
                continue
            ground = next(p for p in unit['holding_components']
                          if '/SM_HoldingBase_Gallows.' in p['mesh'])
            fit = ground['ground_fit']
            assert fit and fit['enabled'] == 1 and fit['region'] == self.args.region
            assert fit['foundation_extent'] == [205, 260, 60]

    def run(self):
        self.build['gallows_ground_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            p = self.folder/'result.json'
            r = json.loads(p.read_text())
            r['gallows_review']['ground_fit_required'] = True
            r['gallows_review']['limits'] = (
                'One legal replay and native placement in the selected region. '
                'Exact public views/actions, optional History, public performer identity, '
                'response cleanup and ground-fit parameters checked. '
                'Actual image review and independent source-surface audit are separate. '
                'Broader abilities, conditions, effects/audio and packaging remain.')
            write_json(p, r)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20879, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.require_final_response = True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='gallows_ground', policy='public_replay', target_kinds=['enter', 'destroy', 'damage'])
    args.output.mkdir(parents=True, exist_ok=True)
    GallowsGroundScenario(args, args.output, (1600, 900), 0).run()
    r = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', r)
    assert r['ok'], r.get('failure') or r.get('issues')
    print('GALLOWS_GROUND_PASSED', args.region, args.render_seat, flush=True)


if __name__ == '__main__':
    main()
