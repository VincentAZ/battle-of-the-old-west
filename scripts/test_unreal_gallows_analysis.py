"""Verify the destroyed public Prospector's three-card response and chosen effect."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_gallows import GallowsScenario
from test_unreal_interactions import EDITOR, ROOT, center, write_json


class GallowsAnalysisScenario(GallowsScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.analysis_observations = []
        self.choice_review = None
        self.choice_click = None

    def click_button(self, button):
        self.event('move', center(button))
        self.event('down', center(button))
        self.event('up', center(button))

    def observe(self, state):
        super().observe(state)
        debug = state.get('cinematic', {}).get('scientist_analysis')
        if debug:
            assert debug['rejected_metadata'] == 0 and debug['untracked_decisions'] == 0
            self.analysis_observations.append(copy.deepcopy(debug))

    def choose_action(self, name, snapshot):
        action = super().choose_action(name, snapshot)
        row = self.replay[len(self.actions)]
        choice = next((e for e in row['public_events'] if e['type'] == 'analysis_choice'), None)
        if choice:
            state = self.read()
            context = next(c for c in state['cinematic']['scientist_analysis']['active']
                           if c['analysis_sequence'] == choice['analysis_sequence'])
            assert context['source'] == self.plan['target']
            assert context['phase'] == 'awaiting_public_choice' and context['reveals_presented']
            assert context['fallback_reason'] == 'western_crew_generic_action' and not context['bespoke']
            assert all(u['id'] != self.plan['target'] for u in state['cinematic']['units'])
            before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
            self.capture('gallows-analysis-choice')
            assert before == {p: self.snapshot(p) for p in ('a', 'b')}
            self.choice_review = dict(context=copy.deepcopy(context), snapshots=before,
                                     image=self.captures['gallows-analysis-choice'])
            if self.args.verify_choice_controls:
                assert name == 'a' and self.snapshot()['seat'] == choice['player']
                self.click_button(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan'))
                def buttons():
                    hud = self.hud()
                    rows = hud['master_actions']
                    offered = {json.dumps(a['command'], sort_keys=True) for a in snapshot['actions']}
                    if (not hud['battle_plan_open'] or not hud['master_actions_visible']
                            or {json.dumps(json.loads(b['id']), sort_keys=True) for b in rows} != offered):
                        return None
                    w, h = self.hud_dimensions()
                    return rows if all(b['visible'] and b['enabled'] and min(b['allocated_size']) > 1
                                       and 0 <= center(b)[0] <= w and 0 <= center(b)[1] <= h for b in rows) else None
                rows = self.wait('all offered analysis buttons arranged in Ledger', buttons)
                assert before == {p: self.snapshot(p) for p in ('a', 'b')}
                self.capture('gallows-analysis-ledger-choice')
                self.choice_review['ledger_buttons'] = copy.deepcopy(rows)
                self.choice_review['ledger_image'] = self.captures['gallows-analysis-ledger-choice']
                write_json(self.folder/'gallows-analysis-ledger-choice.state.json', self.read())
                self.choice_click = copy.deepcopy(action['command'])
        return action

    def submit(self, name, action):
        if self.choice_click is None:
            return super().submit(name, action)
        assert name == 'a' and action['command'] == self.choice_click
        before = copy.deepcopy(self.snapshot())
        button = next(b for b in self.hud()['master_actions'] if json.loads(b['id']) == self.choice_click)
        self.click_button(button)
        self.wait('Ledger click accepted by both authoritative peers', lambda:
                  self.agree() and self.snapshot()['view']['revision'] > before['view']['revision'])
        self.choice_review['real_click_accepted'] = True
        self.choice_review['clicked_command'] = self.choice_click
        self.choice_click = None
        if self.hud()['battle_plan_open']:
            self.click_button(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan'))
            self.wait('Ledger closed after analysis choice', lambda: not self.hud()['battle_plan_open'])

    def event_evidence(self, event, result):
        if event['type'] not in ('reveal_discard', 'analysis_choice'):
            return super().event_evidence(event, result)
        key = event['analysis_sequence']
        contexts = [c for obs in self.analysis_observations for c in obs['active']+obs['history']
                    if c['analysis_sequence'] == key]
        log_match = any(all(e.get(k) == v for k, v in event.items()) for e in self.logged_events)
        if event['type'] == 'analysis_choice':
            completed = [c for c in contexts if c.get('completion_reason') == 'public_decision_recorded_generic_fallback'
                         and c['accepted'] and c['reveals_presented'] and c['decision_sequence'] == event['sequence']
                         and all(c[k] == event[k] for k in ('selection', 'target', 'reveal_index', 'junk_effect'))]
            return dict(sequence=event['sequence'], event=event, mapping='Public decision metadata, not an extra shot',
                        completed=completed[-1:] , choice_view=self.choice_review,
                        passed=bool(log_match and completed and self.choice_review))
        first = min(e['sequence'] for e in self.expected_events.values()
                    if e['type'] == 'reveal_discard' and e['analysis_sequence'] == key)
        samples = [s for s in self.gallows_samples if s['sequence'] == first and s['kind'] == 'reveal_discard'
                   and s['analysis_sequence'] == key and s['analysis_presented_through'] >= event['sequence']
                   and s['count'] == 3]
        captures = [c for c in result['captures'] if c['sequence'] == first and c['kind'] == 'reveal_discard'
                    and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')
                    and c['requested_phase'] in ('impact', 'after-impact')]
        presented = any(r['sequence'] == event['sequence'] and r['target'] == event['target'] and r['presented']
                        for c in contexts for r in c['reveals'])
        return dict(sequence=event['sequence'], event=event, mapping='Three-card public delivery batch',
                    samples=len(samples), captures=captures, individually_presented=presented,
                    passed=bool(log_match and samples and captures and presented))

    def run(self):
        self.build['analysis_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            write_json(self.folder/'analysis-observations.json', self.analysis_observations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=0)
    parser.add_argument('--verify-choice-controls', action='store_true')
    args = parser.parse_args()
    args.manifest = ROOT/'art/western/holdings/expansion-game-v001/gallows/gameplay-analysis-plan-v001.json'
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20919+args.render_seat*10, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter']
    args.region, args.require_final_response, args.capture_late_fall = 1, True, False
    args.profile_renderer, args.require_fuse, args.extra_render_commands = False, False, []
    args.native_extra_args = ['-OldWestRegionReview=1']
    args.scenario_config = dict(name='gallows-analysis', policy='public_replay', target_kinds=['enter', 'destroy', 'damage'])
    args.output.mkdir(parents=True, exist_ok=True)
    GallowsAnalysisScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('GALLOWS_ANALYSIS_NATIVE_PASSED', args.render_seat, flush=True)
