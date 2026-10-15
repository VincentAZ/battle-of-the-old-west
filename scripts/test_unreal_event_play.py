#!/usr/bin/env python3
"""Reproduce War Room/Bombardment with a legal deal and click its real Play button."""
import argparse
import json
import time
from pathlib import Path

from test_unreal_battle_journal import JournalScenario
from test_unreal_interactions import EDITOR, center, field_cards, write_json
from native_launch import create_native_run_directory, game_net_driver_ports, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class EventPlayScenario(JournalScenario):
    def boot(self):
        self.launch('b', '/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset=boomtown')
        log = self.folder / 'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('two peers', self.agree, 100)
        assert self.snapshot()['seat'] == 1
        selections = {'b': ['nitro_works', 'gunsmith', 'general_store'],
                      'a': ['bunkhouse', 'army_surgeon_s_tent', 'cattlemen_s_club']}
        for peer, camps in selections.items():
            action = next(a for a in self.snapshot(peer)['actions'] if a['command'].get('camps') == camps)
            self.submit(peer, action)
        self.wait('match starts', lambda: self.snapshot()['view']['status'] == 'actions')
        if self.snapshot()['view']['active_player'] == 0:
            self.submit('b', next(a for a in self.snapshot('b')['actions'] if a['command']['type'] == 'end_turn'))
        self.settle_presentation()
        if not self.hud().get('battle_plan_open', True):
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
            self.wait('Battle Plan opened', lambda: self.hud()['battle_plan_open'])

    def play_button(self, card):
        for _ in range(30):
            widget = next((w for w in self.hud()['master_actions']
                           if json.loads(w['id']).get('type') == 'play' and json.loads(w['id']).get('card') == card), None)
            assert widget, 'Legal event Play button is missing from the action panel'
            area = next(b['viewport'] for b in self.hud()['section_bodies'] if b['id'] == 'your.actions')
            if widget['allocated_size'][0] > 1 and self.inside(widget, area):
                return widget
            self.event('wheel', center(area), wheel=3 if widget['min'][1] < area['min'][1] else -3)
            time.sleep(.15)
        raise AssertionError('Event Play button is not reachable')

    def run(self):
        result = {'ok': False, 'package_directory': str(self.runtime.package_root) if self.runtime.package_root else None,
                  'resolution': list(self.dimensions), 'seed': self.args.seed,
                  'limitations': ['Focused legal same-workstation match; not a full human match or cinematic-quality test.']}
        try:
            self.boot()
            seat = self.snapshot()['seat']
            bomb = next(c for c in self.own_hand().values() if c['card_id'] == 'cannonade')
            card = bomb['id']
            room = next(c for c in field_cards(self.snapshot()) if c.get('card_id') == 'cattlemen_s_club' and c['owner'] == seat)
            assert self.snapshot()['view']['players'][seat]['water'] == 3 and room['ready']
            assert bomb['play_availability'] == {'cost': 3, 'event_slot': 2, 'available': True, 'reason': ''}
            action = next(a for a in self.snapshot()['actions'] if a['category'] == 'play_event' and a['command']['card'] == card)
            assert action['cost'] == 3 and action['event_slot'] == 2
            self.tab('your')
            self.fold('your.formation', True)
            self.fold('your.events', True)
            self.fold('your.actions', False)
            self.play_button(card)
            self.capture('01-all-actions')
            self.checked('All Actions offers Play Cannonade at the authoritative three-water cost')
            widget = self.visible_hand_widget(card)
            self.event('move', center(widget))
            self.wait('discounted hover', lambda: self.hud().get('card_hover', {}).get('visible')
                      and self.hud()['card_hover'].get('world_card') == card)
            hover = self.hud()['card_hover']['text']
            assert 'Play 3 water (printed 4)' in hover, hover
            self.click(center(widget))
            self.wait('Cannonade selected', lambda: self.hud()['selected_source'] == card)
            button = self.play_button(card)
            self.event('move', (100, 100))
            self.capture('02-selected-event')
            before = self.snapshot()['view']['revision']
            self.click(center(button))
            self.wait('Play button commits', lambda: self.agree() and self.snapshot()['view']['revision'] > before)
            player = self.snapshot()['view']['players'][seat]
            assert player['water'] == 0 and player['queue'][2]['id'] == card
            assert card not in self.own_hand()
            assert next(c for c in field_cards(self.snapshot()) if c['id'] == room['id'])['ready']
            self.settle_presentation()
            self.fold('your.events', False)
            self.capture('03-event-played')
            self.checked('Selecting the hand event exposes Play; a real click spends exactly three water and queues Cannonade without exhausting Cattlemen's Club')
            result.update(ok=True, hover_text=hover, event=card, camp=room['id'], checks=self.checks,
                          screenshots=self.captures, post_play_player=player,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
        except Exception as error:
            result['error'] = str(error)
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()
            result['elapsed_seconds'] = round(time.monotonic() - self.started, 2)
            write_json(self.folder/'result.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--port', type=int, default=19994)
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    args.seed, args.ruleset, args.settle = 42, 'boomtown', .6
    output = args.output or create_native_run_directory('oldwest-event-play-')
    output.mkdir(parents=True, exist_ok=True)
    result = EventPlayScenario(args, output, (1920, 1080), 0).run()
    print(json.dumps({k: result.get(k) for k in ('ok', 'error', 'checks', 'elapsed_seconds')}, indent=2), flush=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
