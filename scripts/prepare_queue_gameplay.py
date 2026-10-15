#!/usr/bin/env python3
"""Prepare an ordinary legal match covering all public event queue moves.

The bridge exposes only both players' authorized views and offered commands.
This journal is a native replay plan, not rendered evidence.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/cinematics/ability-dispatch'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(bridge, output):
    opening = json.loads((BASE / 'queue-opening.json').read_text())
    process = subprocess.Popen([str(bridge), str(ROOT / 'game/data/cards.json'), str(opening['seed'])],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    journal = []
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']

        def apply(seat, predicate, purpose):
            nonlocal state
            snapshot = state[seat]
            matches = [action for action in snapshot['actions'] if predicate(action)]
            assert len(matches) == 1, f'{purpose}: expected one legal option: {snapshot["actions"]}'
            action = matches[0]
            before_sequence = max((event['sequence'] for event in snapshot['view']['log']), default=-1)
            record = dict(seat=seat, revision=snapshot['view']['revision'], turn=snapshot['view']['turn'],
                          purpose=purpose, command=action['command'], public_label=action['label'],
                          legal_actions_sha256=hashlib.sha256(json.dumps(snapshot['actions'], sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps({'seat': seat, 'command': action['command']}) + '\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            assert reply['accepted']['ok']
            state = reply['public_snapshots']
            events = [[event for event in current['view']['log'] if event['sequence'] > before_sequence]
                      for current in state]
            moves = [[event for event in log if event['type'] == 'event_advance'] for log in events]
            assert moves[0] == moves[1], 'Public event movements differ by viewer'
            record.update(accepted_revision=reply['accepted']['revision'], public_events=events[seat],
                          queues_after=[[card['id'] if card else None for card in p['queue']]
                                        for p in state[seat]['view']['players']])
            journal.append(record)
            print(f'{len(journal):02d} seat {seat}: {action["label"]}', flush=True)

        def command(seat, value, purpose):
            apply(seat, lambda a: a['command'] == value, purpose)

        def end(seat):
            command(seat, {'type': 'end_turn'}, 'Ordinary turn handover and event clock')

        def identity(seat, name):
            player = state[seat]['view']['players'][seat]
            matches = [card['id'] for card in [*player['hand'], *(c for column in player['columns'] for c in column)]
                       if not card.get('punk') and card.get('card_id') == name]
            assert len(matches) == 1, (name, matches)
            return matches[0]

        def activate(seat, name):
            command(seat, dict(type='activate', source=identity(seat, name), ability=0),
                    f'Use printed {name} ability')

        def junk(seat, name):
            command(seat, dict(type='junk', card=identity(seat, name)), f'Use the printed {name} junk effect')

        for selection in opening['journal']:
            command(selection['seat'], selection['command'], 'Choose from this player\'s public camp offer')
        own_opening_hands = [dict(seat=seat, own_hand=state[seat]['view']['players'][seat]['hand']) for seat in (0, 1)]
        junk(1, 'poker_night')  # The first player now has two water.
        activate(1, 'courthouse')
        junk(1, 'widow_with_a_shotgun')  # Advance those same Stampede using an ordinary Raid effect.
        end(1)
        command(0, dict(type='play', card=identity(0, 'prairie_fire')), 'Queue an opposing operation before Stampede resolve')
        end(0)
        apply(0, lambda a: a['command']['type'] == 'choose' and a['label'].startswith('Horse Trader'),
              'Defending player chooses a camp to damage from Stampede')
        # Courthouse has now delayed the enemy Prairie Fire from slot0 to slot1.
        activate(1, 'telegraph_office')
        apply(1, lambda a: a['command']['type'] == 'choose' and a['label'].startswith('Enemy Prairie Fire'),
              'Telegraph Office advances that public event toward resolution')
        activate(1, 'courthouse')
        end(1)  # Prairie Fire resolves normally; no enemy people exist to target.
        end(0)  # The new Stampede advance with the next ordinary turn clock.

        moves = [event for step in journal for event in step['public_events'] if event['type'] == 'event_advance']
        reasons = {event['move_reason'] for event in moves}
        assert reasons == {'turn_start', 'queue_delay', 'chosen_advance', 'raid_ability'}, reasons
        for event in moves:
            assert 0 <= event['from_slot'] < 3 and 0 <= event['to_slot'] < 3
            assert abs(event['from_slot'] - event['to_slot']) == 1
            assert 'card_id' not in event and 'private_peek' not in event
        process.stdin.close()
        assert process.wait(timeout=5) == 0, process.stderr.read()
        result = dict(schema=1, ok=True, scope='CPU public-command rehearsal only; no native or graphics claim',
                      seed=opening['seed'], ruleset='boomtown', journal=journal,
                      own_opening_hands=own_opening_hands, queue_moves=moves,
                      provenance={str(path.relative_to(ROOT)): sha(path) for path in (
                          Path(__file__), ROOT / 'game/data/cards.json',
                          ROOT / 'scripts/oldwest_public_costume_bridge.cpp',
                          ROOT / 'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp',
                          BASE / 'queue-opening.json')}, bridge_sha256=sha(bridge))
        output.write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=BASE / 'queue-gameplay-plan.json')
    args = parser.parse_args()
    prepare(args.bridge.resolve(), args.output.resolve())
