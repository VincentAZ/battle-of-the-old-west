"""Native legal Gallows destruction and free response, with both public views."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import capture_subject, painted_beat, phase_of, signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_wanted_board import WantedBoardScenario


class GallowsScenario(WantedBoardScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.public_checks = {}
        self.gallows_samples = []
        self.public_target_visual = None
        self.final_actor_cleaned = False
        self.late_fall_captures = []
        self.late_fall_capture_keys = set()
        self.expected_events = {e['sequence']: e for row in self.plan['journal']
                                for e in row['public_events']
                                if row['revision'] >= self.plan['before'][0]['view']['revision']}

    def boot(self):
        if self.args.render_seat == 0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)
        assert self.snapshot()['seat'] == self.args.render_seat
        self.check_note(self.plan['holding'], 'holding-gallows')
        self.capture('gallows-battlefield')

    def check_public(self, phase):
        snapshots = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        for snapshot in snapshots.values():
            seat = snapshot['seat']
            expected = self.plan[phase][seat]
            assert snapshot['view'] == expected['view'], f'{phase}: public view diverged for seat {seat}'
            assert snapshot['actions'] == expected['actions'], f'{phase}: legal actions diverged for seat {seat}'
            assert 'hand' not in snapshot['view']['players'][1-seat]
        self.public_checks[phase] = snapshots
        if phase == 'before':
            unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == self.plan['target'])
            self.public_target_visual = {k: unit[k] for k in ('visual_id', 'visual_mesh')}
            if 'private_inspection' in self.plan:
                assert self.public_target_visual == dict(visual_id='punk',
                    visual_mesh='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter')
                self.check_note(self.plan['target'], 'drifter')
        self.capture('gallows-public-'+phase)

    def choose_action(self, name, snapshot):
        action = QueueScenario.choose_action(self, name, snapshot)
        for phase in ('before', 'destroyed'):
            if snapshot['view']['revision'] == self.plan[phase][0]['view']['revision']:
                self.check_public(phase)
        return action

    def observe(self, state):
        QueueScenario.observe(self, state)
        c = state.get('cinematic', {})
        expected = self.expected_events.get(c.get('sequence'))
        if c.get('busy') and expected and c.get('kind') == expected['type']:
            if self.args.require_final_response and expected['source'] == self.plan['target']:
                assert c['final_action_reprise'], 'Missing departed public performer'
                performer = next(u for u in c['units'] if u['id'] == self.plan['target'])
                assert {k: performer[k] for k in self.public_target_visual} == self.public_target_visual
                assert not performer['hidden'] and not performer['dead']
                if c['kind'] == 'ability':
                    assert c['caption'].endswith(' · last moments')
                    assert not c.get('action_effects'), 'Final response spawned unrelated props'
                    if 'private_inspection' in self.plan:
                        assert c['caption'] == 'Drifter · last moments'
                        assert c['final_action_visual_id'] == 'punk'
                        assert not performer['bandage']['visible']
                        assert performer['bandage']['mesh'] in ('', '/Game/Art/Western/Bandages/SK_Bandage_Drifter.SK_Bandage_Drifter')
            if c['source'] == self.plan['holding']:
                unit = next(u for u in c['units'] if u['id'] == self.plan['holding'])
                assert unit['animated_part_count'] == 0
                visible = [p for p in unit['holding_components'] if p['visible']]
                assert any('/SM_Holding_Gallows.' in p['mesh'] for p in visible)
                assert any('/SM_HoldingBase_Gallows.' in p['mesh'] for p in visible)
                frame = c.get('subject_frame')
                if c['elapsed'] > .55:
                    assert frame and frame['all_corners_in_front'] and not frame['hidden']
                    assert all(0 <= v <= 1 for v in frame['normalized_min']+frame['normalized_max'])
            self.gallows_samples.append(copy.deepcopy(c))
        if len(self.actions) == len(self.replay) and not c.get('busy') and 'after' not in self.public_checks:
            self.final_actor_cleaned = all(u['id'] != self.plan['target'] for u in c['units'])
            if self.args.require_final_response:
                assert self.final_actor_cleaned, 'Cosmetic final-action actor survived the response'
            self.check_public('after')

    def capture_phase(self, state):
        c = state.get('cinematic', {})
        if c.get('sequence') in self.expected_events:
            # Earlier hiring/preparation shots cannot stand in for a later
            # final response by another instance of the same generic Drifter.
            phase = phase_of(c)
            self.valid_captures.discard((c['kind'], phase))
            self.valid_subject_captures.discard((c['kind'], *capture_subject(c), phase))
        QueueScenario.capture_phase(self, state)
        if not getattr(self.args, 'capture_late_fall', False):
            return
        state = self.read()
        c = state.get('cinematic', {})
        if (not c.get('busy') or c.get('kind') != 'destroy'
                or c.get('target') != self.plan['target'] or not (c.get('physics') or {}).get('bodies')):
            return
        elapsed = c['elapsed']
        phase = 'late-fall' if elapsed >= 5.15 else 'developed-fall' if elapsed >= 2. else None
        key = (c['sequence'], phase)
        paint = painted_beat(state)
        if (not phase or key in self.late_fall_capture_keys or not paint
                or not paint.get('busy') or paint.get('sequence') != c['sequence']):
            return
        self.late_fall_capture_keys.add(key)
        before = copy.deepcopy(state)
        label = f'gallows-{c["sequence"]}-{phase}'
        self.capture(label)
        after = self.read()
        self.observe(after)
        end, end_paint = after.get('cinematic', {}), painted_beat(after)
        valid = bool(end.get('busy') and end.get('sequence') == c['sequence'] and end_paint
                     and end_paint.get('busy') and end_paint.get('sequence') == c['sequence']
                     and end_paint.get('match_id') == paint.get('match_id') == state['snapshot']['match_id'])
        row = dict(sequence=c['sequence'], target=c['target'], phase=phase, image=self.captures[label],
                   same_active_fall_bracket=valid, before_seconds=elapsed, after_seconds=end.get('elapsed'),
                   semantics='Natural ongoing fall, with unchanged timeout and physics; not a settled-pose claim.')
        self.late_fall_captures.append(row)
        write_json(self.folder/f'{label}.state.json', dict(capture=row, before_request=before, after_completion=after))
        write_json(self.folder/'gallows-late-fall-captures.json', self.late_fall_captures)

    def event_evidence(self, event, result):
        sequence = event['sequence']
        samples = [s for s in self.gallows_samples if s['sequence'] == sequence]
        captures = [c for c in result['captures'] if c['sequence'] == sequence and c['kind'] == event['type']
                    and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')
                    and c['requested_phase'] in ('impact', 'after-impact')]
        logs = [e for e in self.logged_events if e['sequence'] == sequence]
        passed = bool(samples and captures and any(all(e.get(k) == v for k, v in event.items()) for e in logs))
        return dict(sequence=sequence, event=event, samples=len(samples), captures=captures, passed=passed)

    def run(self):
        self.build['gallows_harness'] = signature(__file__)
        self.build['history_helper'] = signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json', self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            coverage = [self.event_evidence(event, result) for event in self.expected_events.values()]
            result['gallows_review'] = dict(history=self.notes, public_checks=self.public_checks,
                event_coverage=coverage, rendered_seat=self.args.render_seat, region=self.args.region,
                final_response_required=self.args.require_final_response,
                final_actor_cleaned=self.final_actor_cleaned, public_target_visual=self.public_target_visual,
                late_fall_captures=self.late_fall_captures,
                limits='One legal replay. Optional History, exact public views/actions and private hands checked. Pixel review, other identities/abilities, placements, interruptions, effects/audio and packaging remain separate. Late-fall captures, when requested, document ongoing motion without holding or extending the shot.')
            result['ok'] = bool(result.get('ok') and all(r['passed'] for r in coverage)
                                and set(self.public_checks) == {'before', 'destroyed', 'after'}
                                and 'holding-gallows' in self.notes)
            write_json(self.folder/'gallows-samples.json', self.gallows_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/gallows/gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=0)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    parser.add_argument('--require-final-response', action='store_true')
    parser.add_argument('--capture-late-fall', action='store_true')
    parser.add_argument('--extra-render-command', dest='extra_render_commands', action='append', default=[])
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20749+args.render_seat*10, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter']
    args.profile_renderer, args.require_fuse = False, False
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='gallows', policy='public_replay', target_kinds=['enter', 'destroy', 'damage'])
    args.output.mkdir(parents=True, exist_ok=True)
    GallowsScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('GALLOWS_NATIVE_PASSED', args.render_seat, flush=True)


if __name__ == '__main__':
    main()
