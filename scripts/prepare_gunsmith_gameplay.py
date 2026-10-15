"""Rehearse Gunsmith recruitment and its granted Drifter hit using legal commands."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    seed,journal=17,[]
    process=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        state=json.loads(process.stdout.readline())['public_snapshots']
        def apply(seat,predicate,purpose):
            nonlocal state
            current=state[seat]
            action=next(a for a in current['actions'] if predicate(a))
            last=max((e['sequence'] for e in current['view']['log']),default=-1)
            row=dict(seat=seat,revision=current['view']['revision'],command=action['command'],purpose=purpose,
                     public_label=action['label'],legal_actions_sha256=hashlib.sha256(json.dumps(current['actions'],sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat,command=action['command']))+'\n');process.stdin.flush()
            reply=json.loads(process.stdout.readline());assert reply['accepted']['ok']
            state=reply['public_snapshots']
            row['public_events']=[e for e in state[seat]['view']['log'] if e['sequence']>last]
            journal.append(row)
        def board(seat,owner):
            return [c for col in state[seat]['view']['players'][owner]['columns'] for c in col]
        def wait_for(predicate):
            for _ in range(6):
                if any(predicate(a) for a in state[0]['actions']):return
                seat=next(s for s in (0,1) if any(a['command']['type']=='end_turn' for a in state[s]['actions']))
                apply(seat,lambda a:a['command']['type']=='end_turn','Ordinary turn handover')
            raise AssertionError('Required legal action did not become available')
        apply(0,lambda a:'gunsmith' in a['command']['camps'],'Choose offered Gunsmith')
        apply(1,lambda a:True,'Opponent chooses offered holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        holding=next(c['id'] for c in board(0,0) if c['card_id']=='gunsmith')
        recruit=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        wait_for(recruit);apply(0,recruit,'Pay printed cost to hire a Drifter')
        while state[0]['view']['choice']:
            apply(0,lambda a:a['command']['type']=='choose','Choose offered Drifter placement')
        punk=next(c['id'] for c in board(0,0) if c.get('punk'))
        attack=lambda a:a['command'].get('type')=='activate' and a['command'].get('source')==punk
        wait_for(attack);apply(0,attack,'Use the Gunsmith-granted Drifter hit')
        while state[0]['view']['choice']:
            apply(0,lambda a:a['command']['type']=='choose','Choose an offered damage target')
        views=[next(c for c in board(s,0) if c['id']==punk) for s in (0,1)]
        assert all(c.get('punk') and not c.get('private_peek') and c.get('card_id','punk')=='punk' for c in views)
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,own_opening_hands=opening,
                    queue_moves=[],holding=holding,punk=punk,final_private_views=views,
                    scope='Legal CPU rehearsal only; native rendering remains separate',
                    provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists()
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'commands':len(journal),'holding':holding,'punk':punk,'events':sorted({e['type'] for r in journal for e in r['public_events']})}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
