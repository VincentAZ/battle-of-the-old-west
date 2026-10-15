"""Verify live Trouble routes clear only intersecting saved-map scenery rocks."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_fuse_interruptions import FuseInterruptionScenario
from test_unreal_interactions import EDITOR, ROOT, write_json

INVENTORY = ROOT / 'art/western/trouble/route-clearance-v001/saved-map-inventory.json'
# Independent rectangle from the unchanged canonical route endpoints, fuse,
# entry staging and 190cm horizontal prop envelope plus 25cm clearance.
LANES = [([-2570, 2220], [-2090, 4360]), ([2090, 680], [2570, 2780])]


def intersects(rock):
    return any(all(rock['center'][i] + rock['extent'][i] >= lo[i] and
                   rock['center'][i] - rock['extent'][i] <= hi[i] for i in range(2))
               for lo, hi in LANES)


class TroubleRouteScenario(FuseInterruptionScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.inventory = json.loads(INVENTORY.read_text())
        self.expected = {r['actor'].rsplit('.', 1)[-1] for r in self.inventory['rocks'] if intersects(r)}
        assert len(self.expected) == 10, self.expected
        self.menu_rocks = None
        self.restoration_checks = []
        self.route_samples = 0
        self.moving_samples = 0
        self.build['route_harness'] = signature(__file__)
        self.build['route_inventory'] = signature(INVENTORY)
        self.build['region_source'] = signature(ROOT / 'game/OldWest/Source/OldWestGame/Private/OldWestRegion.cpp')
        self.build['region_header'] = signature(ROOT / 'game/OldWest/Source/OldWestGame/Public/OldWestRegion.h')
        write_json(self.folder / 'build.json', self.build)

    def command(self, name, action, *args, **kwargs):
        if name == 'a' and action == 'join':
            state = copy.deepcopy(self.read())
            assert not state['snapshot']['hosted']
            rocks = {r['actor']: r for r in state['hud']['route_scenery']}
            assert len(rocks) == len(self.inventory['rocks']) == 269
            if self.menu_rocks is None:
                self.menu_rocks = rocks
                write_json(self.folder / 'menu-scenery-baseline.json', rocks)
                # Independently match the saved map's native bounds, not just
                # the runtime helper's chosen count.
                for saved in self.inventory['rocks']:
                    actual = rocks[saved['actor'].rsplit('.', 1)[-1]]
                    for field in ('center', 'extent'):
                        assert max(abs(a-b) for a,b in zip(saved[field], actual[field])) < .001
            else:
                assert rocks == self.menu_rocks, 'Leaving the match did not restore original scenery'
                assert not state['hud'].get('region')
                self.restoration_checks.append(dict(all_269_rocks_restored=True,
                    no_regional_scene=True, check='guest leave before reconnect'))
                write_json(self.folder / 'menu-scenery-restored.json', rocks)
        return super().command(name, action, *args, **kwargs)

    def observe(self, state):
        super().observe(state)
        hud = state.get('hud', {})
        region = hud.get('region')
        if not region:
            return
        assert region['index'] == self.args.region and region['original_collider_retained']
        assert region['noncolliding_scenery'] and region['visible_route_rocks'] == 0
        assert [(r['min_xy'], r['max_xy']) for r in region['trouble_routes']] == LANES
        assert {r['actor'] for r in region['route_rocks']} == self.expected
        assert self.menu_rocks is not None
        rocks = {r['actor']: r for r in hud['route_scenery']}
        assert set(rocks) == set(self.menu_rocks)
        for actor, original in self.menu_rocks.items():
            actual = rocks[actor]
            if actor in self.expected:
                assert actual['hidden'] and not actual['actor_collision']
                assert actual['component_collision'] == 0
                assert intersects(actual)
                for field in ('mesh', 'center', 'extent', 'visible'):
                    assert actual[field] == original[field], (actor, field)
            else:
                assert actual == original, ('Scenery outside the routes changed', actor)
        self.route_samples += 1
        c = state.get('cinematic', {})
        if c.get('kind') == 'event_advance' and c.get('target') == 79 and c.get('busy'):
            self.moving_samples += 1

    def run(self):
        try:
            return super().run()
        finally:
            path = self.folder / 'result.json'
            result = json.loads(path.read_text())
            covered = self.route_samples > 0 and self.moving_samples > 0 and len(self.restoration_checks) == 1
            result.update(ok=bool(result['ok'] and covered), route_clearance=dict(
                region=self.args.region, samples=self.route_samples, moving_prairie_fire_samples=self.moving_samples,
                saved_scenery_rocks=269, suppressed_route_rocks=sorted(self.expected),
                unchanged_outside_route_rocks=259, restoration_checks=self.restoration_checks,
                limitation='Complete saved-map rock bounds checked against both full route rectangles. '
                           'Native motion replay uses one opposing Prairie Fire with Skip/reconnect. '
                           'Other prop identities, crowded queues, host view and packaging remain.'))
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'art/western/trouble/fuse-v001/queue-gameplay-plan.json')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert not args.output.exists(), 'Preserve prior evidence by using a new output version'
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 21059, 550
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal']) - 2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['event_play', 'event_advance', 'event_resolve']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='trouble-route-clearance', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True)
    TroubleRouteScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output / '1600x900/result.json').read_text())
    write_json(args.output / 'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues') or result.get('route_clearance')
    print('TROUBLE_ROUTE_NATIVE_PASSED', args.region, flush=True)


if __name__ == '__main__':
    main()
