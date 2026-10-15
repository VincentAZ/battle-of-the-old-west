"""Skip or reconnect during an actual Gallows final-response reprise."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_gallows import GallowsScenario
from test_unreal_interactions import EDITOR, ROOT, write_json


class GallowsInterruptionScenario(GallowsScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.interruption = None

    def clear_response(self):
        c = self.read().get('cinematic', {})
        return (not c.get('busy', True) and not c.get('action_effects')
                and all(u['id'] != self.plan['target'] for u in c.get('units', [])))

    def observe(self, state):
        super().observe(state)
        c = state.get('cinematic', {})
        # Reconnecting intentionally abandons the in-flight cosmetic shot.
        # A new scene may have no former public frame. Any recreated performer
        # must still be exactly the earlier public visual, never a private face.
        if self.interruption and self.interruption.get('ok'):
            for u in c.get('units', []):
                if u['id'] == self.plan['target']:
                    assert {k: u[k] for k in self.public_target_visual} == self.public_target_visual

    def capture_phase(self, state):
        super().capture_phase(state)
        c = self.read().get('cinematic', {})
        if (self.interruption is not None or not c.get('busy') or c.get('kind') != 'ability'
                or c.get('source') != self.plan['target']):
            return
        captures = [r for r in self.capture_records if r['sequence'] == c['sequence']
                    and r.get('actual_phase_bracket_valid') and r['requested_phase'] in ('impact', 'after-impact')]
        if not captures:
            return
        assert c['final_action_reprise'] and c['caption'].endswith(' · last moments')
        unit = next(u for u in c['units'] if u['id'] == self.plan['target'])
        assert {k: unit[k] for k in self.public_target_visual} == self.public_target_visual
        assert not c.get('action_effects')
        before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        self.interruption = dict(mode=self.args.interrupt, ok=False, sequence=c['sequence'],
            before_cinematic=copy.deepcopy(c), valid_preinterruption_captures=captures)
        if self.args.interrupt == 'skip':
            self.command('a', 'skip_cinematics')
            self.wait('Skip removes the cosmetic response actor', self.clear_response)
        else:
            self.command('a', 'leave')
            self.wait('rendered controller leaves', lambda:
                self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('controller reconnects to same seat', self.agree, 90)
            self.wait('reconnect removes stale response and effects', self.clear_response, 60)
        self.wait('post-interruption shaders ready', lambda:self.hud()['portraits']['compilation']['ready'], 120)
        after = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        assert after == before, 'Interruption changed public state, legal choices or cosmetic filtering'
        assert self.snapshot()['seat'] == 1 and self.clear_response()
        self.capture('gallows-after-'+self.args.interrupt)
        self.interruption.update(ok=True, snapshots_unchanged=True, actor_and_effects_cleared=True)
        write_json(self.folder/'interruption-check.json', self.interruption)

    def run(self):
        self.build['gallows_interruption_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            p = self.folder/'result.json'
            r = json.loads(p.read_text())
            r['gallows_interruption'] = self.interruption
            r['natural_final_response_completion_claimed'] = False
            r['gallows_review']['limits'] = ('Explicitly interrupted reprise, then remaining legal response resolves. '
                'Reconnect may lack a former public-frame cache and must not infer a private appearance. '
                'No claim of natural completion for the interrupted shot. Other placements and abilities remain.')
            r['ok'] = bool(r.get('ok') and self.interruption and self.interruption['ok']
                           and self.final_actor_cleaned)
            write_json(p, r)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--interrupt', choices=['skip', 'reconnect'], required=True)
    args = parser.parse_args(); plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20859, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.render_seat, args.region = 1, 1
    args.require_final_response = args.interrupt == 'skip'
    args.native_extra_args = ['-OldWestRegionReview=1']
    args.scenario_config = dict(name='gallows-'+args.interrupt, policy='public_replay', target_kinds=['enter'])
    args.output.mkdir(parents=True, exist_ok=True)
    GallowsInterruptionScenario(args, args.output, (1600, 900), 0).run()
    r = json.loads((args.output/'1600x900/result.json').read_text()); write_json(args.output/'result.json', r)
    assert r['ok'], r.get('failure') or r.get('issues')
    print('GALLOWS_INTERRUPTION_PASSED', args.interrupt, flush=True)


if __name__ == '__main__':
    main()
