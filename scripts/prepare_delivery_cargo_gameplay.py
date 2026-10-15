"""Extend the legal Poker Night rehearsal with a two-card General Store draw."""
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
    args=parser.parse_args()
    source=ROOT/'art/western/trouble/objects-v002/gameplay-plan.json'
    prior=json.loads(source.read_text());journal=[]
    process=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(prior['seed'])],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        state=json.loads(process.stdout.readline())['public_snapshots']
        def apply(seat,predicate,purpose):
            nonlocal state
            current=state[seat];offered=[a for a in current['actions'] if predicate(a)]
            assert offered,(purpose,current['actions'])
            action=offered[0];last=max((e['sequence'] for e in current['view']['log']),default=-1)
            row=dict(seat=seat,revision=current['view']['revision'],command=action['command'],purpose=purpose,
                public_label=action['label'],legal_actions_sha256=hashlib.sha256(json.dumps(current['actions'],sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat,command=action['command']))+'\n');process.stdin.flush()
            reply=json.loads(process.stdout.readline());assert reply['accepted']['ok'];state=reply['public_snapshots']
            row['public_events']=[e for e in state[seat]['view']['log'] if e['sequence']>last];journal.append(row)
        for old in prior['journal']:
            apply(old['seat'],lambda a:a['command']==old['command'],'Replay verified public Poker Night plan')
            assert journal[-1]['legal_actions_sha256']==old['legal_actions_sha256']
            if len(journal)==2:opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        apply(1,lambda a:a['command']==dict(type='activate',source=74,ability=0),'General Store: draw two using the printed General Store ability')
        apply(1,lambda a:a['command']['type']=='choose','Discard one of those two through the offered public choice')
        batches=[]
        for row in journal[2:]:
            for e in row['public_events']:
                if e['type'] not in ('draw_card','discard','reveal_discard','water'):continue
                if e['type']=='water':
                    if not e['detail']:continue
                    count=int(e['detail'])
                else:count=1
                if batches and e['type']!='water' and all(batches[-1][k]==e[k] for k in ('revision','player','type')) and batches[-1]['last_sequence']==e['sequence']-1:
                    batches[-1]['count']+=1;batches[-1]['last_sequence']=e['sequence']
                else:batches.append(dict(sequence=e['sequence'],last_sequence=e['sequence'],revision=e['revision'],player=e['player'],type=e['type'],count=count))
        assert {b['count'] for b in batches}=={1,2,3,4},batches
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),source,ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',
               ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=prior['seed'],ruleset=prior['ruleset'],scope='Legal public-command CPU rehearsal; native review remains separate.',
            journal=journal,own_opening_hands=opening,queue_moves=prior['queue_moves'],cargo_batches=batches,
            provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print('CARGO_PLAN',len(journal)-2,'legal actions; public batch counts',sorted({b['count'] for b in batches}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
