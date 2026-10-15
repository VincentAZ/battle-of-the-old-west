"""Interrupt each sourced Trouble resolution through ordinary native commands."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import ActionShowcase, signature
from test_unreal_delivery_interruptions import InterruptionScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_trouble import TroubleScenario, ASSETS


class TroubleInterruptionScenario(TroubleScenario):
    wait_for_render = InterruptionScenario.wait_for_render

    def __init__(self, *args):
        super().__init__(*args)
        self.interrupted = {}
        self.hidden_ids = set()
        self.hidden_samples = 0
        self.peer_privacy_samples = 0
        self.compilation_samples = []
        self.ready_frame = {}
        self.build['trouble_interruption_harness'] = signature(__file__)
        write_json(self.folder / 'build.json', self.build)

    def resolution_render_ready(self, state, card):
        compilation = state.get('hud', {}).get('portraits', {}).get('compilation', {})
        sequence = state['cinematic']['sequence']
        if not compilation.get('ready'):
            self.ready_frame.pop(sequence, None)
            self.compilation_samples.append(dict(card=card, sequence=sequence,
                elapsed=state['cinematic']['elapsed'], compilation=copy.deepcopy(compilation)))
            return False
        first = self.ready_frame.setdefault(sequence, compilation['frame'])
        return compilation['frame'] - first >= 3

    @staticmethod
    def capture_compiled(shot):
        state = json.loads(Path(shot['image']).with_suffix('.state.json').read_text())
        return all(state[phase]['hud']['portraits']['compilation']['ready']
                   for phase in ('before_request', 'after_completion'))

    def observe(self, state):
        super().observe(state)
        for peer in ('a', 'b'):
            snapshot = self.snapshot(peer)
            if not snapshot.get('hosted') or not snapshot.get('view'):
                continue
            enemy = snapshot['view']['players'][1 - snapshot['seat']]
            assert 'hand' not in enemy and 'offers' not in enemy
            for column in enemy['columns']:
                for card in column:
                    assert 'private_peek' not in card
                    if card.get('punk'):
                        assert 'card_id' not in card and str(card['id']) not in snapshot.get('cosmetics', {})
            self.peer_privacy_samples += 1
        snapshot = state.get('snapshot', {})
        for player in snapshot.get('view', {}).get('players', []):
            for column in player['columns']:
                for card in column:
                    if card.get('punk'):
                        self.hidden_ids.add(card['id'])
                    else:
                        self.hidden_ids.discard(card['id'])
        # Retain a concealed removed card's generic appearance through its
        # presentation, even after it disappears from the latest public board.
        for unit in state.get('cinematic', {}).get('units', []):
            if unit['id'] in self.hidden_ids and not unit.get('hidden'):
                assert unit['visual_id'] == 'punk', (unit['id'], unit['visual_id'])
                self.hidden_samples += 1

    def clear_resolution(self, source):
        c = self.read().get('cinematic', {})
        return (not c.get('busy', True) and not c.get('action_effects') and not c.get('deliveries')
                and all(u['id'] != source for u in c.get('units', [])))

    def check_public_visual_state(self, state):
        units = state['cinematic']['units']
        checked = []
        for player in state['snapshot']['view']['players']:
            for column in player['columns']:
                for card in column:
                    if card.get('destroyed'):
                        continue
                    matches = [u for u in units if u['id'] == card['id'] and not u.get('hidden')]
                    assert len(matches) == 1, ('Public board unit missing or duplicated after interruption', card['id'])
                    unit = matches[0]
                    assert unit['damage'] == card['damage'], ('Visual damage out of sync', card['id'])
                    if card.get('punk'):
                        assert unit['visual_id'] == 'punk'
                    checked.append(dict(id=card['id'], damage=card['damage'], punk=card.get('punk', False)))
        return checked

    def capture_phase(self, state):
        c = state.get('cinematic', {})
        card = self.plan['targets'].get(str(c.get('source')))
        if c.get('kind') != 'event_resolve' or card is None or card in self.interrupted:
            return super().capture_phase(state)
        if not self.resolution_render_ready(state, card):
            return
        # Retain a real painted impact/after-impact frame, then interrupt the
        # still-active effect. No held pose, slowed clock or state injection.
        super().capture_phase(state)
        current = copy.deepcopy(self.read())
        active = current.get('cinematic', {})
        shots = [s for s in self.capture_records if s['sequence'] == c['sequence']
                 and s['actual_phase_bracket_valid'] and s['requested_phase'] in ('impact', 'after-impact')
                 and self.capture_compiled(s)]
        if (not shots or not active.get('busy') or active.get('sequence') != c['sequence']
                or not active.get('action_effects') or not self.resolution_render_ready(current, card)):
            return
        assert len(active['action_effects']) == ASSETS[card][3]
        assert all(e['collision_enabled'] == 0 for e in active['action_effects'])
        before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        record = dict(ok=False, mode=self.args.interrupt, sequence=c['sequence'], source=c['source'],
                      effects_before=active['action_effects'], active_elapsed=active['elapsed'], valid_captures=shots,
                      capture_brackets_compiled=True, pre_interruption_compilation=current['hud']['portraits']['compilation'])
        self.interrupted[card] = record
        write_json(self.folder / (card + '-before-interruption.json'), dict(state=current, snapshots=before))
        if self.args.interrupt == 'skip':
            self.command('a', 'skip_cinematics')
            self.wait('Skip removes ' + card + ' effects and resolved prop', lambda: self.clear_resolution(c['source']))
        else:
            self.command('a', 'leave')
            self.wait('guest leaves during ' + card, lambda:
                      self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('guest restores same match and seat', self.agree, 90)
            self.wait('reconnect removes stale ' + card + ' effects and resolved prop',
                      lambda: self.clear_resolution(c['source']), 60)
        self.wait_for_render()
        after = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        assert before == after, 'Interruption changed canonical state, actions or cosmetic visibility'
        final = copy.deepcopy(self.read())
        assert self.clear_resolution(c['source'])
        assert all(e['id'] != c['source'] for e in final['hud']['fuse_line']['embers'])
        board = self.check_public_visual_state(final)
        self.observe(final)
        self.capture(card + '-after-' + self.args.interrupt)
        assert self.hud()['portraits']['compilation']['ready'] and self.clear_resolution(c['source'])
        record.update(ok=True, both_peer_snapshots_unchanged=True, resolved_prop_and_ember_removed=True,
                      transient_effects_removed=True, public_board_visual_state=board)
        write_json(self.folder / (card + '-after-interruption.json'), dict(state=final, snapshots=after))
        write_json(self.folder / 'resolution-interruptions.json', self.interrupted)

    def run(self):
        # Intentionally skipped damage beats must not be presented as naturally
        # completed. Retain the common native checks and this explicit contract.
        try:
            return ActionShowcase.run(self)
        finally:
            path = self.folder / 'result.json'
            result = json.loads(path.read_text())
            targets = set(self.plan['targets'].values())
            complete = (set(self.interrupted) == targets and all(r['ok'] for r in self.interrupted.values())
                        and set(self.notes) == targets and set(self.landscape_effects) == targets
                        and len(self.actions) == len(self.replay))
            result.update(ok=bool(result['ok'] and complete), resolution_interruptions=self.interrupted,
                          trouble_history=self.notes, effect_checks=self.landscape_effects,
                          hidden_crew_samples=self.hidden_samples, peer_privacy_samples=self.peer_privacy_samples,
                          pending_compilation_samples=self.compilation_samples,
                          interruption_limits=['Rendered guest seat 1, one selected region, active-effect interruption only. '
                                               'Canonical public/private snapshots compared in full. Public board damage synchronized. '
                                               'No claim of natural completion for skipped damage beats or full wounded-pose fit. '
                                               'Host rendering, other timings/targets/regions, audio and packaging remain.'])
            write_json(path, result)


def main(scenario_class=TroubleInterruptionScenario):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--interrupt', choices=['skip', 'reconnect'], required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert not args.output.exists(), 'Use a new version to preserve previous evidence'
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 21079, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal']) - 2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['event_play', 'event_resolve']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='trouble-resolution-' + args.interrupt, policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True)
    scenario_class(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output / '1600x900/result.json').read_text())
    write_json(args.output / 'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues') or {'completed': list(result['resolution_interruptions'])}
    print('TROUBLE_RESOLUTION_INTERRUPTION_PASSED', args.interrupt, sorted(result['resolution_interruptions']), flush=True)


if __name__ == '__main__':
    main()
