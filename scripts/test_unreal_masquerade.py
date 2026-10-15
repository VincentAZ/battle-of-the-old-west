#!/usr/bin/env python3
"""Exercise private punk inspection and paid flips through real Slate input."""
import argparse
import json
import time
from pathlib import Path

from test_unreal_battle_journal import JournalScenario
from test_unreal_interactions import EDITOR, center, field_cards, resolution, write_json
from native_launch import create_native_run_directory, game_net_driver_ports, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class MasqueradeScenario(JournalScenario):
    def boot(self):
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log = self.folder / 'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('rendered menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('two peers', self.agree, 100)
        for peer in ('b', 'a'):
            choices = self.snapshot(peer)['actions']
            if peer == 'a':
                choices = [a for a in choices if 'wanted_poster_board' in a['command']['camps']]
            self.submit(peer, max(choices, key=lambda a: sum(self.defs[c]['starting_cards'] for c in a['command']['camps'])))
        self.wait('match starts', lambda: self.snapshot()['view']['status'] == 'actions')
        self.mask = next(c['id'] for c in field_cards(self.snapshot()) if c.get('card_id') == 'wanted_poster_board')
        self.own_turn()

    def own_turn(self):
        self.clear_choices()
        if self.snapshot()['view']['active_player'] != self.snapshot()['seat']:
            self.submit('b', next(a for a in self.snapshot('b')['actions'] if a['command']['type'] == 'end_turn'))
        self.settle_presentation()

    def round(self):
        self.own_turn()
        self.submit('a', next(a for a in self.snapshot()['actions'] if a['command']['type'] == 'end_turn'))
        self.own_turn()

    def punks(self):
        return [c for c in field_cards(self.snapshot()) if c.get('private_peek')]

    def prepare_punks(self):
        for attempt in range(7):
            faces = self.punks()
            if sum(c['private_peek']['type'] == 'person' for c in faces) >= 2 and any(c['private_peek']['type'] == 'event' for c in faces):
                break
            self.round()
            if attempt == 0:
                self.submit('a', next(a for a in self.snapshot()['actions'] if a['command']['type'] == 'draw'))
                self.round()
            self.submit('a', next(a for a in self.snapshot()['actions'] if a['command'].get('source') == self.mask))
            placements = [a for a in self.snapshot()['actions'] if 'placement' in a and not a['placement'].get('replace')]
            assert placements
            self.submit('a', placements[0])
            self.clear_choices()
        else:
            raise AssertionError('Could not reach event and person punks through legal camp activations')
        self.round()
        self.evidence['private_punks'] = self.punks()
        for card in self.punks():
            public = next(c for c in field_cards(self.snapshot('b')) if c['id'] == card['id'])
            assert public['name'] == 'Punk' and 'card_id' not in public and 'private_peek' not in public
        self.checked('Owner receives the private faces; the other network peer sees only Punk')

    def formation(self):
        self.tab('your')
        if self.panel()['collapsed']:
            self.click(center(self.panel()['collapse_button']))
            self.wait('open panel', lambda: not self.panel()['collapsed'])
        for suffix in ('water', 'hand', 'events', 'details'):
            if self.section('your.' + suffix):
                self.fold('your.' + suffix, True)
        self.fold('your.formation', False)
        for column in range(1, 4):
            self.fold('your.column' + str(column), False)
        self.fold('your.actions', True)
        outer = self.hud()['battle_scroll'][0]
        self.event('wheel', (outer['max'][0] - 4, center(outer)[1]), wheel=30)
        time.sleep(.4)

    def card_widget(self, card):
        return self.wait('visible formation card', lambda: next((w for w in self.hud()['master_cards'] if int(w['id']) == card and w['allocated_size'][0] > 1 and self.inside(w, self.hud()['battle_scroll'][0])), None))

    def inspect_punk(self, card, label):
        self.formation()
        widget = self.card_widget(card['id'])
        before = self.snapshot()['view']
        self.event('move', center(widget))
        self.wait('authorized punk hover', lambda: self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card'] == card['id'])
        hover = self.hud()['card_hover']['text']
        assert card['private_peek']['name'] in hover and 'PRIVATE INSPECTION' in hover
        assert self.snapshot()['view'] == before, 'Inspection changed authoritative state'
        self.capture(label + '-hover')
        self.click(center(widget))
        self.wait('punk selected and details opened', lambda: self.hud()['selected_source'] == card['id'] and self.section('your.details') and not self.section('your.details')['collapsed'] and self.inside(self.section('your.details'), self.hud()['battle_scroll'][0]))
        assert not self.section('your.actions')['collapsed']
        self.capture(label + '-selected')
        self.evidence.setdefault('inspections', []).append(dict(card=card['id'], hover=hover))

    def flip_button(self, card):
        self.wait('flip offered', lambda: any(json.loads(w['id']).get('type') == 'flip' and json.loads(w['id']).get('card') == card for w in self.hud()['master_actions']))
        for _ in range(25):
            body = next(b['viewport'] for b in self.hud()['section_bodies'] if b['id'] == 'your.actions')
            widget = next(w for w in self.hud()['master_actions'] if json.loads(w['id']).get('type') == 'flip' and json.loads(w['id']).get('card') == card)
            if widget['allocated_size'][0] > 1 and self.inside(widget, body):
                return widget
            self.event('wheel', center(body), wheel=-2)
            time.sleep(.2)
        raise AssertionError('Flip button cannot be reached through action scrolling')

    def click_flip(self, card, label):
        before = self.snapshot()
        seat = before['seat']
        column = next(i for i, col in enumerate(before['view']['players'][seat]['columns']) if any(c['id'] == card['id'] for c in col))
        order = [c['id'] for c in before['view']['players'][seat]['columns'][column]]
        cost = next(a['cost'] for a in before['actions'] if a['command'].get('type') == 'flip' and a['command']['card'] == card['id'])
        self.click(center(self.flip_button(card['id'])))
        self.wait('flip accepted by both peers', lambda: self.agree() and self.snapshot()['view']['revision'] == before['view']['revision'] + 1)
        after = self.snapshot()
        assert after['view']['players'][seat]['water'] == before['view']['players'][seat]['water'] - cost
        assert [c['id'] for c in after['view']['players'][seat]['columns'][column]] == order
        for peer in ('a', 'b'):
            flipped = next(c for c in field_cards(self.snapshot(peer)) if c['id'] == card['id'])
            assert not flipped['punk'] and flipped['card_id'] == card['private_peek']['card_id'] and 'private_peek' not in flipped
            assert flipped['ready'] or flipped['card_id'] == 'civil_war_veteran'
        self.clear_choices()
        self.settle_presentation()
        self.capture(label)

    def run(self):
        try:
            self.boot()
            self.prepare_punks()
            event = next(c for c in self.punks() if c['private_peek']['type'] == 'event')
            self.inspect_punk(event, '01-event')
            assert not any(json.loads(w['id']).get('type') == 'flip' for w in self.hud()['master_actions'])
            assert 'cannot flip events' in self.evidence['inspections'][-1]['hover']
            self.checked('Event punk can be inspected through hover and click, with no flip offered')
            people = sorted((c for c in self.punks() if c['private_peek']['type'] == 'person'), key=lambda c: c['private_peek']['flip_cost'])
            self.inspect_punk(people[0], '02-person')
            self.flip_button(people[0]['id'])
            self.checked('Clicking a punk opens private details and its paid flip despite collapsed action controls')
            self.tab('your')
            self.flip_button(people[0]['id'])
            self.capture('03-all-actions')
            self.checked('All Actions includes affordable Wanted Poster Board flips without selecting a punk')
            self.formation()
            self.click(center(self.card_widget(self.mask)))
            self.wait('Wanted Poster Board selected', lambda: self.hud()['selected_source'] == self.mask)
            self.capture('04-camp-actions')
            self.click_flip(people[0], '05-flip-from-camp')
            self.checked('Selecting Wanted Poster Board exposes a working flip button: correct payment, same position, public identity after entry')
            self.round()
            person = next(c for c in self.punks() if c['private_peek']['type'] == 'person' and c['private_peek']['flip_available'])
            self.inspect_punk(person, '06-next-person')
            self.click_flip(person, '07-flip-from-punk')
            self.checked('Selecting the punk also flips it through the real button and synchronizes both peers')
            result = dict(ok=True, checks=self.checks, evidence=self.evidence, screenshots=self.captures,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder / 'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder / 'result.json', dict(ok=False, failure=str(error), checks=self.checks))
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
    parser.add_argument('--ruleset', default='boomtown')
    parser.add_argument('--seed', type=int, default=350)
    parser.add_argument('--port', type=int, default=19971)
    parser.add_argument('--timeout', type=float, default=700)
    parser.add_argument('--settle', type=float, default=.3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or create_native_run_directory('oldwest-masquerade-')
    output.mkdir(parents=True, exist_ok=True)
    result = dict(ok=False, results=[])
    try:
        for index, size in enumerate(args.resolutions):
            result['results'].append(MasqueradeScenario(args, output, size, index).run())
        result['ok'] = True
    finally:
        write_json(output / 'result.json', result)


if __name__ == '__main__':
    main()
