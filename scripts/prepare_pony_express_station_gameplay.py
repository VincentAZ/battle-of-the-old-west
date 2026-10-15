"""Rehearse station returns through legal public commands, without rules injection."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    seed, journal = 432, []
    process = subprocess.Popen([str(args.bridge.resolve()), str(ROOT/'game/data/cards.json'), str(seed)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']

        def apply(seat, predicate, purpose):
            nonlocal state
            current = state[seat]
            offered = [a for a in current['actions'] if predicate(a)]
            assert offered, (purpose, current['actions'])
            action = offered[0]
            last = max((e['sequence'] for e in current['view']['log']), default=-1)
            row = dict(seat=seat, revision=current['view']['revision'], command=action['command'],
                       purpose=purpose, public_label=action['label'],
                       legal_actions_sha256=hashlib.sha256(json.dumps(current['actions'], sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat, command=action['command']))+'\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            assert reply['accepted']['ok']
            state = reply['public_snapshots']
            row['public_events'] = [e for e in state[seat]['view']['log'] if e['sequence'] > last]
            journal.append(row)

        def command(seat, value, purpose):
            apply(seat, lambda a: a['command'] == value, purpose)

        def board(viewer, owner):
            return [c for col in state[viewer]['view']['players'][owner]['columns'] for c in col]

        def hand():
            return state[0]['view']['players'][0]['hand']

        def end(seat):
            command(seat, dict(type='end_turn'), 'Ordinary turn handover')

        def deploy(identity, column, purpose):
            command(0, dict(type='play', card=identity, column=column, position=0), purpose)

        apply(0, lambda a: a['command'].get('camps') == ['barn_raising', 'silver_mine', 'pony_express_station'],
              'Choose the offered Pony Express Station and supporting holdings')
        apply(1, lambda a: True, 'Opponent chooses offered holdings')
        opening = [dict(seat=s, own_hand=copy.deepcopy(state[s]['view']['players'][s]['hand'])) for s in (0, 1)]
        holding = next(c['id'] for c in board(0, 0) if c['card_id'] == 'pony_express_station')
        veterans = [c['id'] for c in hand() if c['card_id'] == 'civil_war_veteran']
        assert len(veterans) == 2
        target, duplicate = veterans
        newcomer = next(c['id'] for c in hand() if c['card_id'] == 'hellfire_preacher')
        if not state[0]['actions']:
            end(1)
        deploy(target, 0, 'Deploy the first Veteran; resolve its printed draw and wound')
        assert not state[0]['view']['choice']
        end(0)
        end(1)
        deploy(newcomer, 1, 'Deploy another person this turn to test station target exclusion')
        before_return = copy.deepcopy(state)
        assert any(a['command'].get('card') == duplicate and a['command']['type'] == 'play' for a in state[0]['actions'])
        command(0, dict(type='activate', source=holding, ability=0), 'Pay one whiskey to return an eligible older person')
        targets = copy.deepcopy(state[0]['actions'])
        assert any(a.get('target') == target for a in targets)
        assert all(a.get('target') != newcomer for a in targets)
        apply(0, lambda a: a.get('target') == target, 'Return the older Veteran; newly entered crew are ineligible')
        after_return = copy.deepcopy(state)
        assert all(c['id'] != target for c in board(0, 0))
        returned = [c for c in hand() if c.get('card_id') == 'civil_war_veteran']
        assert len(returned) == 2
        blocked = {c['id'] for c in returned}
        assert state[0]['view']['players'][0]['water'] == before_return[0]['view']['players'][0]['water']-1
        assert state[0]['view']['players'][0]['water'] >= 1, 'Exclusion must not be caused by insufficient resources'
        assert all(not (a['command']['type'] == 'play' and a['command'].get('card') in blocked) for a in state[0]['actions'])
        assert board(0, 1) == [c for col in before_return[0]['view']['players'][1]['columns'] for c in col]
        opponent_player = state[1]['view']['players'][0]
        assert 'hand' not in opponent_player, 'Opponent snapshot exposed private hand objects'
        assert opponent_player['hand_count'] == len(hand())
        end(0)
        end(1)
        restored_actions = copy.deepcopy(state[0]['actions'])
        assert all(any(a['command']['type'] == 'play' and a['command'].get('card') == identity for a in restored_actions) for identity in blocked)
        deploy(duplicate, 2, 'On the following turn the other physical copy may legally enter')
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        files = [Path(__file__), ROOT/'scripts/oldwest_public_costume_bridge.cpp', ROOT/'game/data/cards.json',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report = dict(ok=True, seed=seed, ruleset='boomtown', journal=journal, own_opening_hands=opening,
                      queue_moves=[], holding=holding, target=target, duplicate=duplicate, newcomer=newcomer,
                      before_return=before_return, target_choices=targets, after_return=after_return,
                      blocked_physical_copies=sorted(blocked), next_turn_actions=restored_actions,
                      scope='Legal CPU replay: newly entered exclusion, cost, return, both-copy prohibition, next-turn release and opponent hand privacy. Native presentation remains separate.',
                      provenance={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                      bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        assert not args.output.exists()
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(ok=True, commands=len(journal), holding=holding, target=target, duplicate=duplicate)))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    main()
