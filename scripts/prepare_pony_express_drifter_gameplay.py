"""Rehearse the station Drifter-return exception through authorized public views."""
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
    seed, journal = 18, []
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

        apply(0, lambda a: a['command'].get('camps') == ['horse_trader', 'post_office', 'pony_express_station'],
              'Choose offered Pony Express Station and supporting holdings')
        apply(1, lambda a: True, 'Opponent chooses offered holdings')
        opening = [dict(seat=s, own_hand=copy.deepcopy(state[s]['view']['players'][s]['hand'])) for s in (0, 1)]
        holding = next(c['id'] for c in board(0, 0) if c['card_id'] == 'pony_express_station')
        donor = next(c['id'] for c in hand() if c['card_id'] == 'wyatt_earp')
        if not state[0]['actions']:
            end(1)
        command(0, dict(type='junk', card=donor), 'Use the printed junk effect to hire a generic Drifter')
        apply(0, lambda a: a.get('placement', {}).get('column') == 0 and a['placement']['position'] == 0,
              'Place the offered generic Drifter')
        punk = next(c['id'] for c in board(0, 0) if c.get('punk'))
        private_views = [copy.deepcopy(next(c for c in board(s, 0) if c['id'] == punk)) for s in (0, 1)]
        assert all(c.get('punk') and c.get('card_id', 'punk') == 'punk' and 'private_peek' not in c for c in private_views)
        end(0)
        end(1)
        before_return = copy.deepcopy(state)
        old_hand = {c['id'] for c in hand()}
        command(0, dict(type='activate', source=holding, ability=0), 'Pay one whiskey to return the older Drifter')
        apply(0, lambda a: a.get('target') == punk, 'Return a Drifter without imposing a faceup-person reentry restriction')
        after_return = copy.deepcopy(state)
        returned = [c for c in hand() if c['id'] not in old_hand]
        assert len(returned) == 1 and returned[0]['type'] == 'person'
        returned = returned[0]
        # The owner may learn this identity only after the public return to hand.
        assert returned['card_id'] == 'pinkerton_agent' and not returned['punk']
        assert 'hand' not in state[1]['view']['players'][0]
        assert state[1]['view']['players'][0]['hand_count'] == len(hand())
        assert state[0]['view']['players'][0]['water'] == before_return[0]['view']['players'][0]['water']-1
        assert all(c['id'] != punk for c in board(0, 0))
        legal_reentry = [a for a in state[0]['actions'] if a['command']['type'] == 'play' and a['command'].get('card') == returned['id']]
        assert legal_reentry, 'Returned Drifter face must remain legally deployable this turn'
        deploy(returned['id'], 0, 'Legally play the returned Drifter faceup in the same turn')
        while state[0]['view']['choice']:
            apply(0, lambda a: a['command']['type'] == 'choose', 'Resolve the printed optional entry effect')
        entered = [next(c for c in board(s, 0) if c.get('card_id') == 'pinkerton_agent') for s in (0, 1)]
        assert all(not c['punk'] for c in entered)
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        files = [Path(__file__), ROOT/'scripts/oldwest_public_costume_bridge.cpp', ROOT/'game/data/cards.json',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report = dict(ok=True, seed=seed, ruleset='boomtown', journal=journal, own_opening_hands=opening,
                      queue_moves=[], holding=holding, target=punk, punk=punk, returned_face=returned,
                      before_return=before_return, after_return=after_return, generic_views=private_views,
                      same_turn_reentry_actions=legal_reentry, public_reentry=entered,
                      scope='Legal CPU Drifter return, private face filtering and same-turn faceup reentry exception. Native presentation remains separate.',
                      provenance={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                      bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        assert not args.output.exists()
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(ok=True, commands=len(journal), holding=holding, punk=punk, returned_face=returned['card_id'])))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    main()
