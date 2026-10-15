#!/usr/bin/env python3
"""Replay public queue movement and capture its actual native presentation.

No private state injection, pose holds, extra renderer settings or rule edits.
Retains exact public-log correspondence, physical equipment movement and
same-beat painted captures for every cause of queue movement.
"""
import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path

from native_launch import create_native_run_directory, game_net_driver_ports
from test_unreal_action_showcase import ActionShowcase, capture_subject, phase_of, signature
from test_unreal_interactions import EDITOR, ROOT, center, resolution, write_json

DEFAULT_PLAN = ROOT / 'art/cinematics/ability-dispatch/queue-gameplay-plan.json'


class QueueScenario(ActionShowcase):
    def __init__(self, args, output, dimensions, index):
        super().__init__(args, output, dimensions, index)
        self.plan = json.loads(args.manifest.read_text())
        self.replay = self.plan['journal'][2:]
        self.expected_moves = {event['sequence']: event for event in self.plan['queue_moves']}
        self.queue_samples, self.queue_keys, self.tooltip_views = [], set(), []
        self.queue_endpoints = {}
        self.fuse_samples = []
        self.build['queue_harness'] = signature(__file__)
        self.build['queue_plan'] = signature(args.manifest)
        self.build['core'] = signature(ROOT / 'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp')
        write_json(self.folder / 'build.json', self.build)

    def boot(self):
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log = self.folder / 'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('rendered menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('both peers in selection', self.agree, 100)
        for planned in self.plan['journal'][:2]:
            peer = next(name for name in ('a', 'b') if self.snapshot(name)['seat'] == planned['seat'])
            current = self.snapshot(peer)
            assert current['view']['revision'] == planned['revision']
            options = [a for a in current['actions'] if a['command'] == planned['command']]
            assert len(options) == 1, 'Public camp selection is not offered'
            self.submit(peer, options[0])
        self.wait('ordinary match begins', lambda: self.snapshot()['view']['status'] == 'actions')
        self.settle_presentation()  # Setup only; subsequent actions all complete naturally.
        for planned in self.plan['own_opening_hands']:
            peer = next(name for name in ('a', 'b') if self.snapshot(name)['seat'] == planned['seat'])
            assert [(c['id'], c.get('card_id')) for c in self.own_hand(peer).values()] == [
                (c['id'], c.get('card_id')) for c in planned['own_hand']]
        self.capture_tooltips()

    def capture_tooltips(self):
        baseline = [copy.deepcopy(self.snapshot(name)) for name in ('a', 'b')]
        camera = self.camera_identity(self.camera_state())

        def panel():
            # The Ledger is closed in ordinary field view. Exercise the visible
            # information dock, never stale zero-sized geometry for a hidden UI.
            return next(p for p in self.hud()['dock_panels']
                        if p['visible'] and p['id'] in ('field_you', 'master', 'crew'))

        for label, widget in (('move', 'header'), ('resize', 'resize_grip'), ('collapse', 'collapse_button')):
            geometry = panel()[widget]
            self.event('move', center(geometry))
            time.sleep(1.15)  # Ordinary pointer hover; no tooltip command or forced paint.
            self.capture('tooltip-' + label)
            self.tooltip_views.append(dict(kind=label, image=self.captures['tooltip-' + label],
                                           pointer=copy.deepcopy(self.pointer)))
        self.event('down', center(panel()['collapse_button'])); self.event('up')
        self.wait('crew panel collapses after tooltip', lambda: panel()['collapsed'])
        self.event('move', (10, 100))
        self.event('move', center(panel()['collapse_button']))
        time.sleep(1.15)
        self.capture('tooltip-expand')
        self.tooltip_views.append(dict(kind='expand', image=self.captures['tooltip-expand']))
        self.event('down', center(panel()['collapse_button'])); self.event('up')
        self.wait('crew panel expands', lambda: not panel()['collapsed'])
        self.event('move', (10, 100))
        assert [self.snapshot(name) for name in ('a', 'b')] == baseline
        assert self.camera_identity(self.camera_state()) == camera
        write_json(self.folder / 'tooltip-review-inputs.json', dict(
            actual_hover_captures=self.tooltip_views, ordinary_collapse_expand_pass=True,
            unchanged_authoritative_views=True, unchanged_camera=True, manual_review='pending'))

    def choose_action(self, name, snapshot):
        expected = self.replay[len(self.actions)]
        assert snapshot['seat'] == expected['seat'] and snapshot['view']['revision'] == expected['revision'], \
            'Acting player/revision diverged from ordinary public rehearsal'
        assert hashlib.sha256(json.dumps(snapshot['actions'], sort_keys=True).encode()).hexdigest() == expected['legal_actions_sha256']
        offered = [action for action in snapshot['actions'] if action['command'] == expected['command']]
        assert len(offered) == 1, 'Rehearsed command is not currently legal'
        return offered[0]

    def observe(self, state):
        super().observe(state)
        cinematic = state.get('cinematic', {})
        # A polling interval can straddle the last animated frame. Retain an
        # independently observed settled position after that exact beat, while
        # preserving all motion samples and their original timestamps.
        for previous in reversed(self.queue_samples):
            sequence = previous['sequence']
            if sequence in self.queue_endpoints or cinematic.get('sequence') == sequence:
                continue
            expected = self.expected_moves[sequence]
            if any(s['sequence'] > sequence and s['target'] == expected['source'] for s in self.queue_samples):
                continue
            unit = next((u for u in cinematic.get('units', []) if u['id'] == expected['source'] and not u.get('hidden')), None)
            side = 1 if expected['player'] == 0 else -1
            destination = [-2450*side, 2500+side*(400+expected['to_slot']*560)]
            if unit and math.dist(unit['location'][:2], destination) < 2:
                self.queue_endpoints[sequence] = dict(position=copy.deepcopy(unit['location']),
                    observed_sequence=cinematic.get('sequence'), observed_frame=cinematic.get('frame_timing'),
                    source=expected['source'], after_transition=True)
        if getattr(self.args, 'require_fuse', False):
            fuse = state.get('hud', {}).get('fuse_line')
            if fuse and fuse.get('segments'):
                assert fuse['segments'] == 62 and fuse['noncolliding'], 'Both complete fuse tracks must be visual-only'
                self.fuse_samples.append(dict(sequence=cinematic.get('sequence'), kind=cinematic.get('kind'),
                                              fuse=copy.deepcopy(fuse), units=copy.deepcopy(cinematic.get('units', []))))
                public_ids = {u['id'] for u in cinematic.get('units', []) if u.get('event_token') and not u.get('hidden')}
                assert all(e['id'] in public_ids for e in fuse['embers']), 'Fuse exposes a nonpublic or hidden hand card'
        if not cinematic.get('busy') or cinematic.get('kind') != 'event_advance':
            return
        key = (state['snapshot']['match_id'], cinematic['sequence'], cinematic['frame_timing']['frames'])
        if key in self.queue_keys:
            return
        self.queue_keys.add(key)
        record = copy.deepcopy(cinematic)
        record['match_id'] = key[0]
        self.queue_samples.append(record)
        with (self.folder / 'queue-motion-samples.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        try:
            expected = self.expected_moves[cinematic['sequence']]
            movement = cinematic['queue_transition']
            assert movement['valid'] and cinematic['target'] == expected['source']
            assert all(movement[field] == expected[field] for field in ('from_slot', 'to_slot', 'cause_source', 'move_reason'))
            assert cinematic['player'] == expected['player']
            unit = next(u for u in cinematic['units'] if u['id'] == expected['source'])
            assert (unit.get('event_token') or (unit.get('raider') and unit.get('card_id') == 'stampede')) and not unit.get('ragdoll')
            assert len(unit['location']) == 3 and all(math.isfinite(x) for x in unit['location'])
        except (AssertionError, KeyError, StopIteration) as error:
            self.issue(f'Queue movement does not match its public event: {error}', sequence=cinematic.get('sequence'))

    def capture_phase(self, state):
        cinematic = state.get('cinematic', {})
        prior_captures, prior_subjects = set(self.valid_captures), set(self.valid_subject_captures)
        if cinematic.get('kind') == 'event_advance':
            phase = phase_of(cinematic)
            # Capture each actual transition, including repeated Napalm/Raiders
            # identities. The base class still enforces one attempt per phase
            # and exact native/paint brackets.
            self.valid_captures.discard(('event_advance', phase))
            self.valid_subject_captures.discard(('event_advance', *capture_subject(cinematic), phase))
        try:
            super().capture_phase(state)
        finally:
            # Per-transition forcing must never erase cumulative evidence used
            # by the inherited strict coverage checks, even on a repeated poll.
            self.valid_captures.update(prior_captures)
            self.valid_subject_captures.update(prior_subjects)

    def run(self):
        result = None
        try:
            result = super().run()
            return result
        finally:
            retained = result or json.loads((self.folder / 'result.json').read_text())
            coverage = []
            for sequence, event in self.expected_moves.items():
                samples = [s for s in self.queue_samples if s['sequence'] == sequence]
                positions = [s.get('target_location') for s in samples if s.get('target_location')]
                motion = max((math.dist(a, b) for a in positions for b in positions), default=0.)
                side = 1 if event['player'] == 0 else -1
                destination = [-2450 * side, 2500 + side * (400 + event['to_slot'] * 560)]
                origin = [-2450 * side, 2500 + side * (400 + event['from_slot'] * 560)]
                endpoint = self.queue_endpoints.get(sequence)
                final_position = endpoint['position'] if endpoint else (positions[-1] if positions else None)
                final_gap = math.dist(final_position[:2], destination) if final_position else None
                start_gap = math.dist(positions[0][:2], origin) if positions else None
                progress = [(p[1] - origin[1]) / (destination[1] - origin[1]) for p in positions]
                direction_valid = bool(progress and all(-.01 <= value <= 1.01 for value in progress) and
                                       all(b >= a - .01 for a, b in zip(progress, progress[1:])))
                captures = [c for c in self.capture_records if c['sequence'] == sequence and c['actual_phase_bracket_valid']
                            and c['requested_phase'] in ('impact', 'after-impact')]
                logs = [e for e in self.logged_events if e['sequence'] == sequence and e['type'] == 'event_advance']
                log_match = bool(logs and all(all(e.get(k) == v for k, v in event.items()) for e in logs))
                passed = bool(samples and motion > 100 and start_gap is not None and start_gap < 100 and
                              final_gap is not None and final_gap < 2 and direction_valid and captures and log_match)
                coverage.append(dict(sequence=sequence, reason=event['move_reason'], passed=passed,
                                     settled_endpoint=endpoint,
                                     sample_count=len(samples), movement_cm=motion, destination_gap_cm=final_gap,
                                     initial_observed_gap_cm=start_gap, directed_progress_valid=direction_valid,
                                     public_log_matches=log_match, valid_captures=captures))
            complete = len(self.actions) == len(self.replay) and all(row['passed'] for row in coverage)
            if getattr(self.args, 'require_fuse', False):
                fuse_coverage = []
                for sequence, event in self.expected_moves.items():
                    points, gaps = [], []
                    for sample in self.fuse_samples:
                        if sample['sequence'] != sequence or sample['kind'] != 'event_advance': continue
                        ember = next((e for e in sample['fuse']['embers'] if e['id'] == event['source']), None)
                        unit = next((u for u in sample['units'] if u['id'] == event['source']), None)
                        if ember and unit:
                            points.append(ember['location'])
                            gaps.append(abs(ember['location'][1] - unit['location'][1]))
                    travel = max((abs(a[1]-b[1]) for a in points for b in points), default=0)
                    passed = len(points)>2 and travel>100 and max(gaps, default=999)<35
                    fuse_coverage.append(dict(sequence=sequence, reason=event['move_reason'], samples=len(points),
                                              travel_cm=travel, max_token_gap_cm=max(gaps,default=None), passed=passed))
                write_json(self.folder/'fuse-motion-samples.json',self.fuse_samples)
                retained['fuse_coverage'] = fuse_coverage
                complete = complete and all(row['passed'] for row in fuse_coverage)
            retained.update(queue_coverage=coverage, queue_coverage_complete=complete,
                            tooltip_views=self.tooltip_views, manual_visual_review='pending',
                            ok=retained.get('ok', False) and complete)
            write_json(self.folder / 'result.json', retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--port', type=int, default=19939)
    parser.add_argument('--timeout', type=float, default=500)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-fuse', action='store_true', help='Verify fuse embers follow public tokens through every queue movement')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for name, expected in plan['provenance'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f'Stale public plan: {name}'
    args.seed, args.ruleset = plan['seed'], plan['ruleset']
    args.max_actions, args.settle = len(plan['journal']) - 2, 0.
    args.package_dir = None
    args.prefer_camp, args.require_kind, args.extra_render_commands, args.profile_renderer = [], ['event_advance'], [], False
    args.scenario_config = dict(name='public-queue-transition-replay', policy='public_replay', target_kinds=['event_advance'])
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-event-queue-')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(ok=False, logs=str(output), results=[])
    print(f'Native event-queue evidence: {output}', flush=True)
    try:
        for index, dimensions in enumerate(args.resolutions):
            report['results'].append(QueueScenario(copy.copy(args), output, dimensions, index).run())
        report['ok'] = all(result['ok'] for result in report['results'])
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        write_json(output / 'result.json', report)
        print(json.dumps(dict(ok=report['ok'], logs=str(output), failure=report.get('failure')), indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
