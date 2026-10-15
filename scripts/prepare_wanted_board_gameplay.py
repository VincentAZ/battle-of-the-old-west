"""Rehearse private inspection and public reveal using offered commands only."""
import argparse
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
    seed, journal = 14, []
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
            print(len(journal), purpose, action['command'], flush=True)

        def command(seat, value, purpose):
            apply(seat, lambda a: a['command'] == value, purpose)

        def end(seat):
            command(seat, dict(type='end_turn'), 'Ordinary turn handover')

        def board(seat, owner):
            return [c for col in state[seat]['view']['players'][owner]['columns'] for c in col]

        apply(0, lambda a: 'wanted_poster_board' in a['command']['camps'], 'Choose offered Wanted Poster Board')
        apply(1, lambda a: True, 'Opponent chooses offered holdings')
        opening = [dict(seat=s, own_hand=state[s]['view']['players'][s]['hand']) for s in (0, 1)]
        holding = next(c['id'] for c in board(0, 0) if c['card_id'] == 'wanted_poster_board')
        end(0); end(1)
        command(0, dict(type='activate', source=holding, ability=0), 'Hire a Drifter using the printed holding ability')
        while state[0]['view']['choice']:
            apply(0, lambda a: a['command']['type'] == 'choose', 'Choose offered Drifter placement')
        punk = next(c for c in board(0, 0) if c.get('punk'))
        hidden = next(c for c in board(1, 0) if c['id'] == punk['id'])
        assert punk.get('private_peek') and not hidden.get('private_peek')
        assert hidden.get('card_id', 'punk') == 'punk' and punk.get('card_id', 'punk') == 'punk'
        inspection = dict(owner=punk, opponent=hidden)
        if not any(a['command']['type'] == 'flip' for a in state[0]['actions']):
            end(0); end(1)
        command(0, dict(type='flip', card=punk['id']), 'Pay printed cost to reveal the Drifter publicly')
        while state[0]['view']['choice']:
            apply(0, lambda a: a['command']['type'] == 'choose', 'Resolve the revealed card printed entry effect')
        revealed = [next(c for c in board(s, 0) if c['id'] == punk['id']) for s in (0, 1)]
        assert all(not c['punk'] and c['card_id'] == punk['private_peek']['card_id'] for c in revealed)
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        files = [Path(__file__), ROOT/'scripts/oldwest_public_costume_bridge.cpp', ROOT/'game/data/cards.json',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report = dict(ok=True, seed=seed, ruleset='boomtown', journal=journal,
                      own_opening_hands=opening, queue_moves=[], holding=holding, punk=punk['id'],
                      private_inspection=inspection, public_revealed=revealed,
                      scope='Legal public-command rehearsal; no native appearance or animation claim.',
                      provenance={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                      bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        assert not args.output.exists(), 'Preserve prior rehearsals'
        args.output.write_text(json.dumps(report, indent=2)+'\n')
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)


if __name__ == '__main__':
    main()
