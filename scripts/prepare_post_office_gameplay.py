"""Rehearse the Post Office's printed draw-two ability using legal commands."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();seed=5;journal=[]
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
        apply(0,lambda a:'post_office' in a['command'].get('camps',[]),'Choose offered Post Office')
        apply(1,lambda a:True,'Opponent chooses offered holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        holding=next(c['id'] for col in state[0]['view']['players'][0]['columns'] for c in col if c['card_id']=='post_office')
        activate=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        for _ in range(6):
            if any(activate(a) for a in state[0]['actions']):break
            active=next(s for s in (0,1) if any(a['command']['type']=='end_turn' for a in state[s]['actions']))
            apply(active,lambda a:a['command']['type']=='end_turn','Ordinary turn handover')
        before=[s['view']['players'][0] for s in state]
        apply(0,activate,'Pay printed cost of three whiskey to draw two cards')
        after=[s['view']['players'][0] for s in state]
        assert after[0]['hand_count']==before[0]['hand_count']+2
        assert after[0]['water']==before[0]['water']-3
        assert 'hand' not in before[1] and 'hand' not in after[1]
        drawn=[c for c in after[0]['hand'] if c['id'] not in {v['id'] for v in before[0]['hand']}]
        assert len(drawn)==2
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,own_opening_hands=opening,
                    queue_moves=[],holding=holding,before_draw=before,after_draw=after,drawn=drawn,
                    scope='Legal CPU rehearsal only; native presentation review is separate',
                    provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists()
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'commands':len(journal),'holding':holding,'events':sorted({e['type'] for row in journal for e in row['public_events']})}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
