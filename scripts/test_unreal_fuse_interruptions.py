"""Interrupt legally queued Prairie Fire movement in the rendered native client.

Checks Skip on a public delay and reconnect on a public advance. Existing source
art and rules are unchanged; all commands must match the pinned legal rehearsal.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from test_unreal_action_showcase import ActionShowcase, signature
from test_unreal_delivery_interruptions import InterruptionScenario
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json


class FuseInterruptionScenario(QueueScenario):
    wait_for_render = InterruptionScenario.wait_for_render

    def __init__(self, *args):
        super().__init__(*args)
        self.interrupt_at = {}
        for reason, mode in [('queue_delay', 'skip'), ('chosen_advance', 'reconnect')]:
            events = [e for e in self.expected_moves.values() if e['move_reason'] == reason]
            assert len(events) == 1, (reason, events)
            self.interrupt_at[events[0]['sequence']] = mode
        self.completed = {}
        self.privacy_samples = 0
        self.cord_checks = []
        self.build['fuse_interruption_harness'] = signature(__file__)
        self.build['staging_source'] = signature(ROOT / 'game/OldWest/Source/OldWestGame/Private/OldWestStaging.cpp')
        self.build['historical_evidence'] = [signature(ROOT / 'research/western-presentation' / f)
            for f in ('fuse-line.json', 'trouble-landscapes.json')]
        write_json(self.folder / 'build.json', self.build)

    def capture_tooltips(self):
        self.wait_for_render()

    def observe(self, state):
        super().observe(state)
        fuse = state.get('hud', {}).get('fuse_line') or {}
        if fuse.get('segments'):
            segments = fuse.get('cord_segments', [])
            assert len(segments) == 62, 'Actual rendered cord transform telemetry is required'
            for ember in fuse['embers']:
                # Project onto every real rendered segment and choose the
                # closest horizontal centerline, independently of token Z.
                candidates = []
                for segment in segments:
                    axis, center = segment['axis'], segment['center']
                    distance = (ember['location'][1] - center[1]) / axis[1]
                    if abs(distance) > segment['length_cm'] / 2 + 31:
                        continue
                    point = [p + a * distance for p, a in zip(center, axis)]
                    candidates.append((abs(point[0] - ember['location'][0]), point))
                assert candidates, 'No rendered cord segment near ember'
                horizontal_gap, point = min(candidates)
                height = ember['location'][2] - point[2]
                assert horizontal_gap < .1 and abs(height - 5) < .1, (ember, point, height)
                self.cord_checks.append(dict(id=ember['id'], horizontal_gap_cm=horizontal_gap,
                                             height_above_cord_cm=height))
        for peer in ('a', 'b'):
            snapshot = self.snapshot(peer)
            if not snapshot.get('hosted') or 'view' not in snapshot:
                continue
            enemy = snapshot['view']['players'][1 - snapshot['seat']]
            assert 'hand' not in enemy and 'offers' not in enemy
            for column in enemy['columns']:
                for card in column:
                    assert 'private_peek' not in card
                    if card.get('punk'):
                        assert str(card['id']) not in snapshot.get('cosmetics', {})
            self.privacy_samples += 1
        for unit in state.get('cinematic', {}).get('units', []):
            if unit.get('card_id') != 'prairie_fire' or unit.get('hidden'):
                continue
            parts = [p for p in unit.get('event_equipment', []) if p['visible']]
            assert len(parts) == 1 and 'SM_Trouble_PrairieFire' in parts[0]['mesh'], parts
            assert not parts[0]['wheel'] and parts[0]['collision_enabled'] == 0

    def movement(self, state, event):
        c = state.get('cinematic', {})
        assert c.get('busy') and c.get('kind') == 'event_advance' and c['sequence'] == event['sequence']
        unit = next(u for u in c['units'] if u['id'] == event['source'] and not u['hidden'])
        assert unit['card_id'] == 'prairie_fire'
        side = 1 if event['player'] == 0 else -1
        origin_y = 2500 + side * (400 + event['from_slot'] * 560)
        dest_y = 2500 + side * (400 + event['to_slot'] * 560)
        progress = (unit['location'][1] - origin_y) / (dest_y - origin_y)
        assert .01 < progress < .99, ('interruption must occur during actual motion', progress)
        ember = next(e for e in state['hud']['fuse_line']['embers'] if e['id'] == unit['id'])
        assert abs(ember['location'][1] - unit['location'][1]) < 35
        return dict(progress=progress, unit=copy.deepcopy(unit), ember=copy.deepcopy(ember),
                    sequence=c['sequence'], elapsed=c['elapsed'])

    def settled(self):
        c = self.read().get('cinematic', {})
        return not c.get('busy', True) and not c.get('action_effects') and not c.get('deliveries')

    def check_endpoint(self, state, event):
        c, fuse = state['cinematic'], state['hud']['fuse_line']
        assert self.settled()
        assert fuse['segments'] == 62 and fuse['noncolliding']
        units = [u for u in c['units'] if u['id'] == event['source'] and not u['hidden']]
        embers = [e for e in fuse['embers'] if e['id'] == event['source']]
        assert len(units) == len(embers) == 1, 'Duplicate or missing restored prop/ember'
        unit, ember = units[0], embers[0]
        side = 1 if event['player'] == 0 else -1
        destination = [-2450 * side, 2500 + side * (400 + event['to_slot'] * 560)]
        gap = math.dist(unit['location'][:2], destination)
        assert gap < 2 and abs(ember['location'][1] - unit['location'][1]) < 35
        for peer in ('a', 'b'):
            queued = self.snapshot(peer)['view']['players'][event['player']]['queue'][event['to_slot']]
            assert queued['id'] == event['source'] and queued['card_id'] == 'prairie_fire'
        return dict(unit=unit, ember=ember, destination_gap_cm=gap, fuse=fuse)

    def capture_phase(self, state):
        c = state.get('cinematic', {})
        mode = self.interrupt_at.get(c.get('sequence'))
        if not mode or mode in self.completed or c.get('kind') != 'event_advance':
            return super().capture_phase(state)
        # An ordinary before-impact screenshot can consume the interception
        # window. Wait for actual movement without starting that other capture.
        if c.get('elapsed', 0) <= .13:
            return
        assert c['elapsed'] < .70, ('Missed early moving interruption window', c['sequence'], c['elapsed'])
        event = self.expected_moves[c['sequence']]
        before_motion = self.movement(state, event)
        self.capture('fuse-before-' + mode)
        # Re-read after the screenshot: interruption must still hit moving art.
        interrupted_state = copy.deepcopy(self.read())
        interrupted_motion = self.movement(interrupted_state, event)
        before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        record = dict(ok=False, mode=mode, event=event, before_motion=before_motion,
                      interrupted_motion=interrupted_motion)
        self.completed[mode] = record
        write_json(self.folder / ('fuse-' + mode + '-before.json'), dict(state=interrupted_state, snapshots=before))
        if mode == 'skip':
            self.command('a', 'skip_cinematics')
            self.wait('Skip settles the fuse and prop', self.settled)
        else:
            self.command('a', 'leave')
            self.wait('rendered guest leaves during fuse movement', lambda:
                      self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('guest restores its original seat', self.agree, 90)
            self.wait('reconnect settles without replaying stale motion', self.settled, 60)
        self.wait_for_render()
        after = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        assert before == after, 'Interruption changed game state, legal actions or cosmetic filtering'
        current = copy.deepcopy(self.read())
        endpoint = self.check_endpoint(current, event)
        self.observe(current)
        self.capture('fuse-after-' + mode)
        self.check_endpoint(self.read(), event)
        assert self.hud()['portraits']['compilation']['ready']
        record.update(ok=True, canonical_snapshots_unchanged=True, endpoint=endpoint)
        write_json(self.folder / ('fuse-' + mode + '-after.json'), dict(state=current, snapshots=after))
        write_json(self.folder / 'interruption-checks.json', self.completed)

    def run(self):
        # QueueScenario.run requires natural motion for every move. This replay
        # deliberately interrupts two; use its observations and legal commands,
        # but report this separate interruption contract without waiving failures.
        try:
            return ActionShowcase.run(self)
        finally:
            path = self.folder / 'result.json'
            result = json.loads(path.read_text())
            complete = set(self.completed) == {'skip', 'reconnect'} and all(r['ok'] for r in self.completed.values())
            result.update(ok=bool(result['ok'] and complete and len(self.actions) == len(self.replay)),
                          fuse_interruptions=self.completed, privacy_samples=self.privacy_samples,
                          cord_fit=dict(samples=len(self.cord_checks),
                              max_horizontal_gap_cm=max((c['horizontal_gap_cm'] for c in self.cord_checks), default=None),
                              min_height_cm=min((c['height_above_cord_cm'] for c in self.cord_checks), default=None),
                              max_height_cm=max((c['height_above_cord_cm'] for c in self.cord_checks), default=None)),
                          natural_completion_claimed_for_interrupted_moves=False,
                          interruption_limits=['One public Prairie Fire, rendered guest seat 1, local listen host. '
                                               'No hidden Crew staged; privacy checks cover the actual peer views. '
                                               'Other Trouble types, interruption timings, host rendering, audio and packaged release remain.'])
            write_json(self.folder / 'fuse-motion-samples.json', self.fuse_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'art/western/trouble/fuse-v001/queue-gameplay-plan.json')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert not args.output.exists(), 'Use a fresh version to preserve prior native evidence'
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 21039, 500
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal']) - 2
    args.settle, args.prefer_camp = 0, []
    args.require_kind = ['event_play', 'event_advance', 'event_resolve']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='fuse-interruptions', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True)
    FuseInterruptionScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output / '1600x900/result.json').read_text())
    write_json(args.output / 'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues') or {
        'completed_interruptions': list(result.get('fuse_interruptions', {})), 'result': str(args.output / 'result.json')}
    print('FUSE_INTERRUPTION_NATIVE_PASSED', args.region, flush=True)


if __name__ == '__main__':
    main()
