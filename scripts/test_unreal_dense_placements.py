#!/usr/bin/env python3
"""Exercise dense replacement and Box Canyon through actual native Slate drags.

Setup uses only public legal commands in an ordinary two-peer match. No save
state, deck manipulation, fabricated entity, or injected placement is used.
The reusable interaction harness owns launch, pointer delivery and cleanup.
"""
import argparse
import copy
import json
import math
import time
from pathlib import Path

from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_hud import resolution
from test_unreal_interactions import (EDITOR, ROOT, InteractionScenario,
                                     arranged_widget, card_handle, write_json)


class DensePlacementScenario(InteractionScenario):
    # These entry effects alter population or create another decision; avoid
    # them for the one-for-one replacement assertion, not for normal setup.
    ENTRY_CHOICES = {'wyatt_earp', 'duelist', 'blacksmith', 'civil_war_veteran'}

    def own_columns(self, snapshot=None):
        current = snapshot or self.snapshot()
        return current['view']['players'][current['seat']]['columns']

    def own_people(self, snapshot=None):
        return [card for column in self.own_columns(snapshot) for card in column
                if card['type'] == 'person']

    def population(self, column):
        return sum(card['type'] == 'person' for card in column)

    def full(self):
        return all(self.population(column) == (2 if any(card['type'] == 'camp' for card in column) else 3)
                   for column in self.own_columns())

    def prep_step(self, fill=False):
        """Make one deterministic, public legal setup decision."""
        current = self.snapshot()
        assert current['view']['status'] == 'actions', 'Match ended during legal dense-board setup'
        acting = next((name for name in ('a', 'b') if self.snapshot(name).get('actions')), None)
        assert acting, 'Neither peer has a legal setup action'
        options = self.snapshot(acting)['actions']
        if options[0]['command']['type'] == 'choose':
            placements = [entry for entry in options if entry.get('placement', {}).get('punk')]
            if acting == 'a' and fill and placements and not self.full():
                action = min(placements, key=lambda entry:
                             self.population(self.own_columns()[entry['placement']['column']]))
            else:
                action = next((entry for entry in options if entry.get('label') == 'Skip'), options[0])
        elif acting == 'b':
            action = next(entry for entry in options if entry['command']['type'] == 'end_turn')
        else:
            hand = self.own_hand()
            people = [entry for entry in options if entry.get('category') == 'play_person'
                      and 'replace' not in entry['command']]
            if fill and people and not self.full():
                action = min(people, key=lambda entry: (entry.get('cost', 0),
                             self.population(self.own_columns()[entry['command']['column']]),
                             entry['command']['card'], entry['command']['position']))
            else:
                action = None
                if fill and not self.full():
                    action = next((entry for entry in options if entry['command']['type'] == 'junk'
                                   and self.junk_kind(hand.get(entry['command'].get('card'), {})) == 'punk'), None)
                action = action or next((entry for entry in options if entry['command']['type'] == 'draw'), None)
                action = action or next(entry for entry in options if entry['command']['type'] == 'end_turn')
        self.submit(acting, action)

    def replacement_candidate(self):
        hand = self.own_hand()
        return next((entry for entry in self.snapshot().get('actions', [])
                     if entry.get('category') == 'play_person' and 'replace' in entry['command']
                     and hand[entry['command']['card']].get('card_id') not in self.ENTRY_CHOICES), None)

    def prepare_dense_board(self):
        for step in range(self.args.max_setup_actions):
            if self.full() and self.replacement_candidate():
                self.settle_presentation()
                self.evidence['legal_setup'] = dict(actions=step, snapshot=copy.deepcopy(self.snapshot()))
                self.capture('02-full-board')
                self.checked('Public legal draws, plays and punk choices fill the board and produce a legal replacement')
                return
            self.prep_step(fill=True)
        raise AssertionError(f'Could not legally fill the board within {self.args.max_setup_actions} actions')

    def check_dense_labels(self, deployment, label):
        hud = self.hud()
        scale = hud['hud_size'][0] / 1920
        area = hud['drag_rect']
        boxes = []
        for index, target in enumerate(deployment['targets']):
            assert target['projected'], f'{label}: marker projects behind camera'
            x, y = target['screen']
            # Native OnPaint's published badge dimensions, in the HUD's units.
            width = 148 * scale
            height = (54 if '\n' in target['label'] else 44) * scale
            box = [x - width / 2, y - height / 2, x + width / 2, y + height / 2]
            assert area['min'][0] - .5 <= box[0] < box[2] <= area['max'][0] + .5, \
                f'{label}: marker label falls outside horizontal drag area: {target}'
            assert area['min'][1] - .5 <= box[1] < box[3] <= area['max'][1] + .5, \
                f'{label}: marker label falls outside vertical drag area: {target}'
            for previous in boxes:
                other = previous['box']
                overlap_x = min(box[2], other[2]) - max(box[0], other[0])
                overlap_y = min(box[3], other[3]) - max(box[1], other[1])
                assert overlap_x <= .5 or overlap_y <= .5, \
                    f'{label}: visible drop badges overlap: {previous["target"]} and {target}'
            boxes.append(dict(index=index, box=box, target=target))
        self.evidence.setdefault('dense_label_geometry', []).append(dict(label=label, drag_rect=area, labels=boxes))
        self.check_hint(deployment, label)

    def check_hint(self, deployment, label, expected_name=None):
        """Check the reported native banner, without recreating its placement algorithm."""
        hud = self.hud()
        rectangle = deployment.get('hint_rect', [])
        assert len(rectangle) == 4 and all(math.isfinite(value) for value in rectangle), \
            f'{label}: native drag instruction lacks a finite rectangle'
        left, top, right, bottom = rectangle
        width, height = hud['hud_size']
        area = hud['drag_rect']
        assert 0 <= left < right <= width and 0 <= top < bottom <= height, \
            f'{label}: drag instruction extends beyond the HUD: {rectangle}'
        assert area['min'][0] <= left < right <= area['max'][0] and \
               area['min'][1] <= top < bottom <= area['max'][1], \
            f'{label}: drag instruction extends outside the active scene: {rectangle}'
        assert top >= hud['scene_rect']['min'][1], \
            f'{label}: drag instruction covers the persistent top controls'
        scale = width / 1920
        for target in deployment['targets']:
            x, y = target['screen']
            half_width = 148 * scale / 2
            half_height = (54 if '\n' in target['label'] else 44) * scale / 2
            overlap_x = min(right, x + half_width) - max(left, x - half_width)
            overlap_y = min(bottom, y + half_height) - max(top, y - half_height)
            assert overlap_x <= .5 or overlap_y <= .5, \
                f'{label}: drag instruction conceals a placement badge: {target}'
        if expected_name is not None:
            assert deployment.get('name') == expected_name, \
                f'{label}: drag instruction identifies {deployment.get("name")!r}, expected public person {expected_name!r}'
            assert deployment.get('hint', '').startswith(expected_name), \
                f'{label}: visible drag instruction omits the dragged person name'
        self.evidence.setdefault('native_hint_geometry', []).append(dict(
            label=label, hint_rect=rectangle, drag_rect=area, name=deployment.get('name'),
            hint=deployment.get('hint'), expected_name=expected_name, hovered=deployment.get('hovered')))

    def hover_exact(self, target):
        self.event('move', target['screen'])

        def exact():
            deployment = self.hud().get('deployment', {})
            index = deployment.get('hovered', -1)
            targets = deployment.get('targets', [])
            return 0 <= index < len(targets) and targets[index]['command'] == target['command']

        self.wait('the exact dense alternative highlights', exact, 8)
        self.check_hint(self.hud()['deployment'], 'hovered dense alternative')

    def test_replacement(self):
        action = self.replacement_candidate()
        assert action, 'Prepared board lost its replacement candidate'
        incoming = action['command']['card']
        before = copy.deepcopy(self.snapshot())
        old_people = {card['id']: card for card in self.own_people(before)}
        deployment = self.begin_drag(incoming)
        self.capture('03-dense-replacement-targets')
        self.check_dense_labels(deployment, 'replacement')
        targets = deployment['targets']
        assert all('replace' in target['command'] for target in targets), 'Full board offered a non-replacement drop'
        assert {target['command']['replace'] for target in targets} == set(old_people), \
            'Some legal replacement victims lack their own marker'
        assert len({tuple(round(v, 3) for v in target['screen']) for target in targets}) == len(targets), \
            'Distinct replacement alternatives occupy the same marker center'
        # Every offered victim/position must be individually hit-testable.
        for target in targets:
            victim = old_people[target['command']['replace']]
            assert victim['name'] in target['label'], 'Replacement marker omits its actual visible victim name'
            self.hover_exact(target)
        chosen = next((target for target in reversed(targets)
                       if not old_people[target['command']['replace']].get('punk')), targets[-1])
        self.hover_exact(chosen)
        self.capture('03-dense-replacement-targets')
        self.finish_drop(chosen)
        self.settle_presentation()
        after = self.snapshot()
        new_people = {card['id']: card for card in self.own_people(after)}
        victim = chosen['command']['replace']
        assert set(new_people) == (set(old_people) - {victim}) | {incoming}, \
            'Dense drop did not replace exactly its selected victim'
        assert incoming not in self.own_hand(), 'Replacement left the incoming card in hand'
        assert incoming in {card['id'] for card in self.own_columns()[chosen['command']['column']]}, \
            'Incoming person entered a different lane'
        figure = next(unit for unit in self.read()['cinematic']['units'] if unit['id'] == incoming)
        assert max(abs(a-b) for a, b in zip(figure['location'][:2], chosen['world'][:2])) < 1, \
            'Replacement figure differs from the unoffset world destination'
        self.evidence['replacement'] = dict(incoming=incoming, victim=victim, selected=chosen,
                                           before=before, after=copy.deepcopy(after))
        self.capture('04-exact-victim-replaced')
        self.checked('Every dense marker is distinct and reachable; real drag replaces only the selected named victim')

    def seek_high_ground(self):
        for _ in range(self.args.max_setup_actions):
            hand = self.own_hand()
            action = next((entry for entry in self.snapshot().get('actions', [])
                           if entry.get('category') == 'play_event'
                           and hand[entry['command']['card']].get('card_id') == 'box_canyon'), None)
            if action:
                self.settle_presentation()
                deployment = self.begin_drag(action['command']['card'])
                assert len(deployment['targets']) == 1, 'Box Canyon should have one rules-selected event destination'
                self.finish_drop(deployment['targets'][0])
                return
            self.prep_step()
        raise AssertionError('Box Canyon was not reachable in the rendered player hand through legal play')

    def resolve_to_rearrangement(self):
        for _ in range(30):
            current = self.snapshot()
            choice = current['view'].get('choice')
            if choice and choice.get('player') == current['seat']:
                if any('row' in entry.get('placement', {}) for entry in current['actions']):
                    return
                confirmation = next((entry for entry in current['actions'] if entry.get('label') == 'Rearrange'), None)
                if confirmation:
                    self.submit('a', confirmation)
                    continue
            # Passing advances the ordinary event clock without spending water
            # on more draws once Box Canyon has been queued.
            acting = next((name for name in ('a', 'b') if self.snapshot(name).get('actions')), None)
            assert acting, 'No actor can advance the queued Box Canyon'
            options = self.snapshot(acting)['actions']
            action = next((entry for entry in options if entry['command']['type'] == 'end_turn'), None)
            action = action or next((entry for entry in options if entry.get('label') == 'Skip'), options[0])
            self.submit(acting, action)
        raise AssertionError('Box Canyon never exposed its rearrangement drag choices')

    def test_high_ground(self):
        self.seek_high_ground()
        self.resolve_to_rearrangement()
        original = copy.deepcopy(self.snapshot())
        original_columns = self.own_columns(original)
        lookup = {card['id']: card for column in original_columns for card in column}
        old_people = {card['id'] for card in self.own_people(original)}
        old_lanes = {card['id']: column for column, cards in enumerate(original_columns) for card in cards}
        planned = [[card['id'] for card in column if card['type'] == 'camp'] for column in original_columns]
        decisions = []
        for index in range(len(old_people)):
            self.settle_presentation()
            actions = [entry for entry in self.snapshot()['actions'] if 'row' in entry.get('placement', {})]
            subjects = {entry['placement']['card'] for entry in actions}
            assert len(subjects) == 1, 'Each Box Canyon step must name one public person'
            subject = subjects.pop()
            widget = self.wait('Box Canyon drag widget is arranged', lambda: next((entry for entry in
                               self.hud().get('placement_drag_buttons', [])
                               if card_handle(entry) == subject and arranged_widget(entry)), None))
            deployment = self.begin_drag(subject, widget)
            self.capture(f'05-rearrange-{index + 1:02d}')
            self.check_hint(deployment, f'rearrangement-person-{index + 1}', lookup[subject]['name'])
            self.check_dense_labels(deployment, f'rearrangement-{index + 1}')
            preferred = (old_lanes[subject] + 1) % 3
            chosen_action = min(actions, key=lambda entry: (entry['placement']['column'] != preferred,
                                len(planned[entry['placement']['column']]), entry['placement']['position']))
            target = next(entry for entry in deployment['targets'] if entry['command'] == chosen_action['command'])
            placement = chosen_action['placement']
            column = planned[placement['column']]
            column.insert(placement['position'], subject)
            camp = next((identity for identity in column if lookup[identity]['type'] == 'camp'), None)
            if camp is not None and not lookup[camp]['destroyed']:
                advance = lookup[camp].get('advance', 0)
                if advance == 2 or (advance == 1 and len(column) == 3):
                    column.remove(camp)
                    column.insert(0 if advance == 2 else 1, camp)
            row = (3 - len(column) + column.index(subject) if camp is None else
                   2 - lookup[camp].get('advance', 0) + column.index(subject) - column.index(camp))
            assert placement['row'] == row, 'Public placement row differs from the accumulated public arrangement'
            expected = ((placement['column'] - 1) * 1100,
                        2500 + (1 if original['seat'] == 0 else -1) * (450 + row * 350))
            assert max(abs(a-b) for a, b in zip(target['world'][:2], expected)) < 1, \
                'Rearrangement marker uses the old board instead of the chosen pending formation'
            self.hover_exact(target)
            self.check_hint(self.hud()['deployment'], f'rearrangement-release-{index + 1}', lookup[subject]['name'])
            self.capture(f'05-rearrange-{index + 1:02d}')
            self.finish_drop(target)
            decisions.append(dict(subject=subject, placement=placement, target=target,
                                  planned=copy.deepcopy(planned)))
            current_ids = [[card['id'] for card in cards] for cards in self.own_columns()]
            if index + 1 < len(old_people):
                assert current_ids == [[card['id'] for card in cards] for cards in original_columns], \
                    'Box Canyon changed the authoritative formation before the final choice'
            else:
                assert current_ids == planned, 'Completed rearrangement differs from the exact drag choices'
        self.settle_presentation()
        assert {card['id'] for card in self.own_people()} == old_people, 'Rearrangement created or removed a person'
        assert any(old_lanes[identity] != column for column, ids in enumerate(planned)
                   for identity in ids if identity in old_people), 'Scenario did not actually move anyone to a new lane'
        assert not self.snapshot()['view'].get('choice'), 'Last rearrangement drag left a pending choice'
        self.evidence['box_canyon'] = dict(before=original, decisions=decisions, after=copy.deepcopy(self.snapshot()))
        self.capture('06-high-ground-rearranged')
        self.checked('Box Canyon uses one real drag per person, projects the pending formation, and commits the exact final arrangement')
        self.checked('Native drag instructions name each public person and fit the active scene without covering any placement badge')

    def run(self):
        try:
            self.boot()
            self.prepare_dense_board()
            self.test_replacement()
            self.test_high_ground()
            assets = assert_runtime_assets([self.folder / 'a.log', self.folder / 'b.log'])
            self.checked('Both native peers report no missing assets, material failures or fatal errors')
            result = dict(ok=True, resolution=f'{self.dimensions[0]}x{self.dimensions[1]}', checks=self.checks,
                          screenshots=self.captures, evidence=self.evidence, runtime_assets=assets,
                          elapsed_seconds=round(time.monotonic() - self.started, 2), logs=str(self.folder))
            write_json(self.folder / 'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder / 'result.json', dict(ok=False, failure=str(error), checks=self.checks,
                       screenshots=self.captures, evidence=self.evidence, last_reports=self.reports, logs=str(self.folder)))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'], default='boomtown')
    parser.add_argument('--seed', type=int, default=2623)
    parser.add_argument('--port', type=int, default=19579)
    parser.add_argument('--timeout', type=float, default=1200, help='Maximum seconds per resolution')
    parser.add_argument('--max-setup-actions', type=int, default=160)
    parser.add_argument('--settle', type=float, default=.35)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 0 <= args.seed < 2**64:
        parser.error('--seed must be an unsigned 64-bit integer')
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-dense-placements-')
    output.mkdir(parents=True, exist_ok=True)
    print(f'Native dense placement evidence: {output}', flush=True)
    report = dict(ok=False, results=[], logs=str(output), ruleset=args.ruleset, seed=args.seed,
                  executable_mode='packaged' if args.package_dir else 'editor_game',
                  limitations=['Loopback native peers on one computer.',
                               'The setup fills ordinary camp columns; three-person camp-removed columns are a separate case.',
                               'The supplied seed/ruleset must naturally deal Box Canyon to the rendered player.'])
    started = time.monotonic()
    try:
        for index, size in enumerate(args.resolutions):
            report['results'].append(DensePlacementScenario(args, output, size, index).run())
        report['ok'] = True
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        destinations = [output / 'result.json', ROOT / 'game/tests/reports/latest-native-dense-placements.json']
        if args.package_dir:
            destinations.append(ROOT / 'game/tests/reports/latest-packaged-dense-placements.json')
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_json(destination, report)
        print(json.dumps({key: value for key, value in report.items() if key != 'results'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
