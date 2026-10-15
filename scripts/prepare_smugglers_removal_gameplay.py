"""Rehearse legal damage, ruin and removal of the landing using public actions."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    process = subprocess.Popen([str(args.bridge.resolve()), str(ROOT/'game/data/cards.json'), '22'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    journal, checkpoints = [], {}
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']

        def apply(seat, predicate, purpose):
            nonlocal state
            action = next(a for a in state[seat]['actions'] if predicate(a))
            before = state
            last = max((e['sequence'] for e in before[seat]['view']['log']), default=-1)
            process.stdin.write(json.dumps(dict(seat=seat, command=action['command']))+'\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            assert reply['accepted']['ok']
            state = reply['public_snapshots']
            journal.append(dict(seat=seat, revision=before[seat]['view']['revision'], command=action['command'],
                legal_actions_sha256=hashlib.sha256(json.dumps(before[seat]['actions'], sort_keys=True).encode()).hexdigest(),
                purpose=purpose, public_label=action['label'],
                public_events=[e for e in state[seat]['view']['log'] if e['sequence'] > last]))

        def board(seat):
            return [card for column in state[0]['view']['players'][seat]['columns'] for card in column]

        def end(seat):
            apply(seat, lambda a:a['command']['type']=='end_turn', 'Ordinary turn handover')

        apply(0, lambda a:a['command'].get('camps')==['smuggler_s_landing','boarding_house','pony_express_station'], 'Select landing and ruin-removal holding')
        apply(1, lambda a:a['command'].get('camps')==['artillery_battery','salvage_yard','mountain_hideout'], 'Select offered opposing holdings')
        opening = state
        holding = next(c['id'] for c in board(0) if c.get('card_id')=='smuggler_s_landing')
        remover = next(c['id'] for c in board(0) if c.get('card_id')=='boarding_house')
        launcher = next(c['id'] for c in board(1) if c.get('card_id')=='artillery_battery')
        checkpoints['healthy'] = state
        end(0)
        for condition in ('damaged','ruined'):
            apply(1, lambda a:a['command'].get('source')==launcher and a['command']['type']=='activate', 'Opponent pays for an ordinary hit')
            apply(0, lambda a:a.get('target')==holding and a['command']['type']=='choose', 'Owner chooses landing as the offered hit target')
            card = next(c for c in board(0) if c['id']==holding)
            assert card['damage']==(2 if condition=='ruined' else 1) and card['destroyed']==(condition=='ruined'), card
            checkpoints[condition] = state
            end(1)
            if condition=='damaged':end(0)
        before_remove = state
        apply(0, lambda a:a['command'].get('source')==remover and a['command'].get('ability')==0 and a['command']['type']=='activate', 'Pay one to remove a ruined holding')
        apply(0, lambda a:a.get('target')==holding, 'Choose the ruined landing')
        assert not any(c['id']==holding for c in board(0))
        checkpoints['removed'] = state
        apply(0, lambda a:a.get('target')==launcher, 'Complete required damage against an exposed enemy holding')
        checkpoints['complete'] = state
        assert state[0]['view']['players'][0]['water']==before_remove[0]['view']['players'][0]['water']-1
        assert all('hand' not in s['view']['players'][1-s['seat']] for s in state)
        process.stdin.close()
        assert process.wait(timeout=5)==0
        paths = [Path(__file__), ROOT/'scripts/oldwest_public_costume_bridge.cpp', ROOT/'game/data/cards.json',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report = dict(ok=True,seed=22,ruleset='boomtown',journal=journal,opening=opening,
            own_opening_hands=[dict(seat=i,own_hand=opening[i]['view']['players'][i]['hand']) for i in (0,1)],
            queue_moves=[],holding=holding,remover=remover,launcher=launcher,checkpoints=checkpoints,
            provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest(),
            scope='Public legal CPU rehearsal only; no state injection, native visual or final approval claim.')
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print('SMUGGLERS_REMOVAL_PLAN_PASSED', len(journal), flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__=='__main__':
    main()
