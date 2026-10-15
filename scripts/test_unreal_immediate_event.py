#!/usr/bin/env python3
"""Verify the separate immediate-event slot using legal deals and real pointer input."""
import argparse
import copy
import json
from pathlib import Path

from test_unreal_direct_drags import DirectDragScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class ImmediateEventScenario(DirectDragScenario):
    def prepare_event(self):
        for _ in range(80):
            self.own_turn()
            action = next((a for a in self.snapshot()['actions']
                           if a['category'] == 'play_event' and a['event_slot'] == -1), None)
            if action:
                return action
            draw = next((a for a in self.snapshot()['actions'] if a['command']['type'] == 'draw'), None)
            if draw:
                self.submit('a', draw)
            else:
                self.round()
        raise AssertionError('No legal immediate event found in the deterministic deal')

    def run(self):
        result = dict(ok=False, checks=self.checks, screenshots=self.captures)
        try:
            self.boot()
            action = self.prepare_event()
            card = action['command']['card']
            seat = self.snapshot()['seat']
            self.toggle_panel(True)
            self.isolate('your.events')
            zero = self.wait('dedicated zero surface', lambda: self.surface(side=seat, event_slot=-1))
            one = self.wait('separate first countdown surface', lambda: self.surface(side=seat, event_slot=0))
            assert zero['max'][0] <= one['min'][0], 'Immediate and countdown slots overlap'
            self.capture('02-distinct-event-slots')
            self.fold('your.hand', False)
            widget = self.visible_hand_widget(card)
            deployment = self.start(card, center(widget))
            target = next(t for t in deployment['targets'] if t['command'] == action['command'])
            assert target['event_slot'] == -1 and target['label'] == '0 · PLAY NOW'
            assert all(t['event_slot'] != 0 for t in deployment['targets'] if t['command'] == action['command'])
            self.cancel('Cancelling an immediate-event drag preserves the card and water', escape=True)

            # The same legal card can resolve via either world or panel input.
            # First prove that the world badge points to the new zero position.
            widget = self.visible_hand_widget(card)
            deployment = self.start(card, center(widget))
            target = next(t for t in deployment['targets'] if t['command'] == action['command'])
            assert target['projected']
            assert target['world'][:2] == ([-2250.0, 2500.0] if seat == 0 else [2250.0, 2500.0])
            self.event('move', target['screen'])
            self.wait('world zero highlights', lambda: self.hud()['deployment']['hovered'] >= 0)
            self.capture('03-world-zero-highlight')
            self.cancel('World zero is reachable without committing a play', escape=True)

            widget = self.visible_hand_widget(card)
            self.start(card, center(widget))
            outer = self.outer()
            self.event('move', (center(outer)[0], outer['max'][1]-8))
            one = self.wait('countdown slot visible during drag', lambda: self.surface(side=seat, event_slot=0))
            self.event('move', center(one))
            self.wait('slot one rejects immediate event', lambda: self.hud()['deployment']['hovered'] == -1)
            zero = self.wait('zero visible during drag', lambda: self.surface(side=seat, event_slot=-1))
            self.event('move', center(zero))
            self.wait('panel zero highlights', lambda: self.hud()['deployment']['hovered'] >= 0
                      and self.hud()['deployment']['panel_surface'] >= 0)
            self.capture('04-panel-zero-highlight')
            before = copy.deepcopy(self.snapshot()['view'])
            self.event('up', center(zero))
            self.wait('immediate event commits once', lambda: self.agree()
                      and self.snapshot()['view']['revision'] == before['revision']+1)
            after = self.snapshot()['view']
            player = after['players'][seat]
            assert card not in self.own_hand()
            assert all(c is None or c['id'] != card for c in player['queue'])
            assert player['queue'] == before['players'][seat]['queue']
            assert player['water'] == before['players'][seat]['water']-action['cost']
            self.checked('Slot 1 rejects the immediate event; slot 0 spends its cost once and resolves without queueing')
            self.clear_choices()
            self.settle_presentation()
            self.capture('05-immediate-event-resolved')
            result.update(ok=True, card=card, action=action, before=before, after=after,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
        except Exception as error:
            result['error'] = str(error)
            try:
                self.capture('failure')
            except Exception:
                pass
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()
            write_json(self.folder/'result.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720), (1920, 1080)])
    parser.add_argument('--port', type=int, default=20271)
    parser.add_argument('--timeout', type=float, default=360)
    args = parser.parse_args()
    args.seed, args.ruleset, args.settle = 94, 'base_2024', .3
    output = args.output or create_native_run_directory('oldwest-immediate-event-')
    output.mkdir(parents=True, exist_ok=True)
    results = [ImmediateEventScenario(args, output, size, i).run() for i, size in enumerate(args.resolutions)]
    result = dict(ok=all(r['ok'] for r in results), results=results)
    write_json(output/'result.json', result)
    print(json.dumps(dict(ok=result['ok'], output=str(output), errors=[r.get('error') for r in results])), flush=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
