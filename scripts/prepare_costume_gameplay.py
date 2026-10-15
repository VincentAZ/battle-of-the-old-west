#!/usr/bin/env python3
"""Rehearse a bounded, ordinary legal costume-review match in portable Core.

The bridge exposes only two authorized public views and offered commands. The
saved journal is a plan for native replay, not animation or rendered evidence.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/survivor_variants/deformation-v3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(bridge, output):
    probe = json.loads((BASE / 'legal-public-seed.json').read_text())
    process = subprocess.Popen([str(bridge), str(ROOT / 'game/data/cards.json'), str(probe['seed'])],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    journal = []
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']

        def apply(seat, predicate, purpose):
            nonlocal state
            snapshot = state[seat]
            matches = [action for action in snapshot['actions'] if predicate(action)]
            assert len(matches) == 1, f'{purpose}: expected one legal option, found {len(matches)}: {snapshot["actions"]}'
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
            record.update(accepted_revision=reply['accepted']['revision'],
                          public_events=[event for event in state[seat]['view']['log'] if event['sequence'] > before_sequence])
            journal.append(record)
            print(f'{len(journal):02d} seat {seat}: {action["label"]} ({purpose})', flush=True)

        def identity(seat, card_id):
            player = state[seat]['view']['players'][seat]
            cards = [*player['hand'], *(card for column in player['columns'] for card in column)]
            matches = [card['id'] for card in cards if not card.get('punk') and card.get('card_id') == card_id]
            assert len(matches) == 1, f'Ambiguous own public identity: {card_id}'
            return matches[0]

        def end(seat):
            apply(seat, lambda a: a['command']['type'] == 'end_turn', 'Ordinary turn handover')

        def play(seat, card, column, position=0):
            entity = identity(seat, card)
            apply(seat, lambda a: a['command'] == dict(type='play', card=entity, column=column, position=position),
                  f'Deploy {card}; native entry/walk and later idle review')

        def activate(seat, card):
            entity = identity(seat, card)
            apply(seat, lambda a: a['command'] == dict(type='activate', source=entity, ability=0),
                  f'Use printed {card} ability')

        def choose_target(seat, name, purpose):
            apply(seat, lambda a: a['command']['type'] == 'choose' and a['label'].startswith(name + ' (lane '), purpose)

        for selection in probe['selection_journal']:
            apply(selection['seat'], lambda a, c=selection['command']: a['command'] == c,
                  'Choose three cards from this player\'s public camp offer')
        opening = [dict(seat=seat, own_hand=state[seat]['view']['players'][seat]['hand']) for seat in (0, 1)]
        play(0, 'annie_oakley', 0); end(0)
        for column, card in enumerate(('prospector', 'gatling_gunner', 'bounty_hunter')):
            play(1, card, column)
        end(1)
        play(0, 'bartender', 0)  # Real front guard protects Annie Oakley from Gunner.
        play(0, 'widow_with_a_shotgun', 1); end(0)
        activate(1, 'prospector')
        apply(1, lambda a: a['command']['type'] == 'choose' and a['label'].lower() == 'skip',
              'Decline the optional revealed junk effect without changing a test target')
        activate(1, 'gatling_gunner'); end(1)
        end(0)
        activate(1, 'bounty_hunter')
        choose_target(1, 'Widow with a Shotgun', 'Real Bounty Hunter attack on the unprotected opposing Widow with a Shotgun')
        end(1)
        # Every target first receives a nonlethal hit, then a later lethal hit.
        # No card is restored/returned/replaced to manufacture additional poses.
        for card in ('Prospector', 'Gatling Gunner', 'Bounty Hunter'):
            for hit in ('nonlethal hit reaction', 'lethal hit and natural fall'):
                activate(0, 'annie_oakley')
                choose_target(0, card, f'{card}: {hit}')
                end(0); end(1)
        targets = probe['targets']
        events = [event for entry in journal for event in entry['public_events']]
        for target in targets:
            entity = target['entity']
            assert any(event['type'] == 'enter' and event['target'] == entity for event in events), target
            assert any(event['type'] == 'ability' and event['source'] == entity for event in events), target
            assert any(event['type'] == 'damage' and event['target'] == entity for event in events), target
            assert any(event['type'] == 'destroy' and event['target'] == entity for event in events), target
        process.stdin.close()
        assert process.wait(timeout=5) == 0, process.stderr.read()
        result = dict(schema=1, ok=True, scope='CPU public-command rehearsal only; no native/render/physics claim',
                      seed=probe['seed'], ruleset=probe['ruleset'], targets=targets, own_opening_hands=opening,
                      journal=journal, catalog_sha256=sha(ROOT / 'game/data/cards.json'),
                      provenance={str(path.relative_to(ROOT)): sha(path) for path in (
                          Path(__file__), ROOT / 'scripts/oldwest_public_costume_bridge.cpp',
                          ROOT / 'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp',
                          BASE / 'legal-public-seed.json')}, bridge_sha256=sha(bridge))
        output.write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=BASE / 'legal-gameplay-plan.json')
    args = parser.parse_args()
    prepare(args.bridge.resolve(), args.output.resolve())
