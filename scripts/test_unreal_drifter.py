#!/usr/bin/env python3
"""Run real recruitment/privacy interactions with Drifter visual assertions.

Usage: test_unreal_drifter.py shelter|masquerade [existing scenario options]
The underlying scenarios use legal game commands and actual Slate input.
"""
import json
import sys

import test_unreal_masquerade as masquerade
import test_unreal_punk_shelter as shelter
from test_unreal_interactions import center, field_cards

MESH = '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'


class DrifterVisualChecks:
    def battle_panel(self, opened):
        if self.hud().get('battle_plan_open') != opened:
            self.click(center(next(b for b in self.hud()['camera_buttons']
                                   if b['id'] == 'battle_plan')))
            self.wait('Battle Plan visibility', lambda: self.hud()['battle_plan_open'] == opened)

    def capture(self, name):
        result = super().capture(name)
        report = self.read()
        hud = report.get('hud', {})
        units = [u for u in report.get('cinematic', {}).get('units', [])
                 if u.get('card_id') == 'punk']
        residents = [p['motion'] for p in hud.get('punk_shelter', {}).get('crew', [])]
        portraits = [p for s in hud.get('portraits', {}).get('scenes', [])
                     for p in s.get('people', []) if p.get('card_id') == 'punk']
        for person in units + residents + portraits:
            assert person['visual_mesh'] == MESH, (name, person)
            assert person['unarmed'] and not person['weapon_visible'], (name, person)
        labels = [label for label in hud.get('battlefield_labels', [])
                  if label.get('id') in {u['id'] for u in units}]
        if name == '02-three-punks-outside-gate':
            recruits = [label for label in hud['battlefield_labels'] if -1006 < label['id'] <= -1000]
            assert len(recruits) == 3
            for label in recruits:
                assert label['label'] == 'DRAG DRIFTER'
                for panel in hud['dock_panels']:
                    if not panel['visible']:
                        continue
                    point, rect = label['screen'], panel['panel']
                    assert not all(rect['min'][i] <= point[i] <= rect['max'][i] for i in (0, 1)), (label, panel)
        evidence = dict(capture=name, field=units, residents=residents,
                        portraits=portraits, labels=labels)
        path = self.folder / 'drifter-visuals.json'
        checks = json.loads(path.read_text()) if path.exists() else []
        checks.append(evidence)
        path.write_text(json.dumps(checks, indent=2) + '\n')
        return result


if __name__ == '__main__':
    scenario = sys.argv.pop(1)
    if scenario == 'shelter':
        class DrifterShelter(DrifterVisualChecks, shelter.ShelterScenario):
            def test_raid_junk_menu(self):
                # The current abilities dock covers the left queue's label at
                # this resolution; collapse it with real input before clicking.
                panel = self.panel('ability_reference')
                if panel['visible'] and not panel['collapsed']:
                    self.click(center(panel['collapse_button']))
                    self.wait('abilities dock collapsed', lambda: self.panel('ability_reference')['collapsed'])
                return super().test_raid_junk_menu()

            def activate(self, key):
                source = self.camps[key]
                action = next(a for a in self.snapshot()['actions'] if a['command'].get('source') == source)
                point = next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id'] == source)
                self.event('move', point)
                self.event('down', point, button='right')
                self.event('up', point, button='right')
                card = next(c for c in field_cards(self.snapshot()) if c['id'] == source)
                ability = next(a for a in card['public_abilities'] if a['index'] == action['command']['ability'])
                caption = ability.get('activation_label', action['label'] + (f" · {action['cost']} water" if action.get('cost', 0) else ''))
                caption = caption.replace('Punks', 'Drifters').replace('Punk', 'Drifter').replace('punks', 'drifters').replace('punk', 'drifter').replace('Stampede', 'Stampede')
                row = self.wait('camp context ability', lambda: next((e for e in self.hud()['context_entries'] if e['id'] == caption and e['allocated_size'][0] > 1), None))
                revision = self.snapshot()['view']['revision']
                self.click(center(row))
                self.wait('camp ability accepted', lambda: self.agree() and self.snapshot()['view']['revision'] == revision + 1)
                self.settle_presentation()

            def field_action(self, action):
                # Current UI keeps pending choices in Battle Plan, not the
                # retired field-button strip used by the original scenario.
                self.battle_panel(True)
                self.fold('your.actions', False)
                row = self.wait('choice button', lambda: next((e for e in self.hud()['master_actions'] if json.loads(e['id']) == action['command'] and e['allocated_size'][0] > 1), None))
                revision = self.snapshot()['view']['revision']
                self.click(center(row))
                self.wait('choice accepted', lambda: self.agree() and self.snapshot()['view']['revision'] == revision + 1)
                self.settle_presentation()
                self.battle_panel(False)
        shelter.ShelterScenario = DrifterShelter
        shelter.main()
    elif scenario == 'wanted_poster_board':
        class DrifterMasquerade(DrifterVisualChecks, masquerade.MasqueradeScenario):
            def formation(self):
                self.battle_panel(True)
                return super().formation()
        masquerade.MasqueradeScenario = DrifterMasquerade
        masquerade.main()
    else:
        raise SystemExit('Choose shelter or masquerade')
