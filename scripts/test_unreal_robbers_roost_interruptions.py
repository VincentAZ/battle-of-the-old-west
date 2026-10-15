"""Interrupt an actual Robbers Roost bonus after its rendered impact."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from test_unreal_action_showcase import signature
from test_unreal_robbers_roost_ground import RoostGroundScenario
from test_unreal_interactions import EDITOR, ROOT, write_json


class RoostInterruptionScenario(RoostGroundScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.interruption = None

    def clear_bonus(self):
        c = self.read().get('cinematic', {})
        source = self.plan['bonus']['water_event']['source']
        return (not c.get('busy', True) and not c.get('action_effects')
                and not c.get('deliveries') and all(u['id'] != source for u in c.get('units', [])))

    def capture_phase(self, state):
        super().capture_phase(state)
        c = self.read().get('cinematic', {})
        sequence = self.plan['bonus']['water_event']['sequence']
        if self.interruption is not None or not c.get('busy') or c.get('kind') != 'water' or c.get('sequence') != sequence:
            return
        captures = [r for r in self.capture_records if r['sequence'] == sequence
                    and r.get('native_phase_bracket_valid') and r.get('painted_beat_bracket_valid')
                    and r['requested_phase'] == 'impact']
        if not captures:
            return
        assert c['resource_only'] and len(c['action_effects']) == 2
        before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        self.interruption = dict(mode=self.args.interrupt, ok=False, sequence=sequence,
                                 before_cinematic=copy.deepcopy(c), valid_impact_captures=captures)
        if self.args.interrupt == 'skip':
            self.command('a', 'skip_cinematics')
            self.wait('Skip clears bonus props and resolved herd', self.clear_bonus)
        else:
            assert self.args.render_seat == 1, 'Reconnect requires the rendered client'
            self.command('a', 'leave')
            self.wait('rendered client leaves', lambda:
                      self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('client rejoins the same match', self.agree, 90)
            self.wait('reconnect clears stale bonus props and herd', self.clear_bonus, 60)
        self.wait('post-interruption shaders ready', lambda:self.hud()['portraits']['compilation']['ready'], 120)
        after = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        assert before == after, 'Interruption changed state, legal actions or private filtering'
        assert self.snapshot()['seat'] == self.args.render_seat and self.clear_bonus()
        self.capture('robbers-roost-after-'+self.args.interrupt)
        self.interruption.update(ok=True, snapshots_unchanged=True, actors_and_effects_cleared=True)
        write_json(self.folder/'interruption-check.json', self.interruption)

    def run(self):
        self.build['roost_interruption_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            path = self.folder/'result.json'; result = json.loads(path.read_text())
            result['bonus_interruption'] = self.interruption
            result['natural_bonus_completion_claimed'] = False
            result['ok'] = bool(result.get('ok') and self.interruption and self.interruption['ok'])
            result['robbers_roost_review']['limits'] = 'One bonus interrupted after a verified native impact capture; no natural completion claim. Exact peer snapshots and cleanup checked. Other interruption timings and battlefield conditions remain.'
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--interrupt', choices=['skip', 'reconnect'], required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/robbers-roost/gameplay-plan-v002.json')
    args = parser.parse_args(); plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20989, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['raid_launch', 'event_advance', 'stampede_charge', 'water']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='robbers_roost_'+args.interrupt, policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    RoostInterruptionScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text()); write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('ROBBERS_ROOST_BONUS_INTERRUPTION_PASSED', args.interrupt, args.render_seat, flush=True)


if __name__ == '__main__':
    main()
