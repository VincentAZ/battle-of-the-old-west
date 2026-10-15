"""Rehearse Jailhouse recruitment/restoration through offered commands only."""
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
    seed,journal=187,[]
    process=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        state=json.loads(process.stdout.readline())['public_snapshots']
        def apply(seat,predicate,purpose):
            nonlocal state
            current=state[seat]
            offered=[a for a in current['actions'] if predicate(a)]
            assert offered,(purpose,current['actions'])
            action=offered[0]
            last=max((e['sequence']for e in current['view']['log']),default=-1)
            row=dict(seat=seat,revision=current['view']['revision'],command=action['command'],purpose=purpose,
                     public_label=action['label'],legal_actions_sha256=hashlib.sha256(json.dumps(current['actions'],sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat,command=action['command']))+'\n');process.stdin.flush()
            reply=json.loads(process.stdout.readline());assert reply['accepted']['ok']
            state=reply['public_snapshots']
            row['public_events']=[e for e in state[seat]['view']['log']if e['sequence']>last]
            journal.append(row)
        def command(seat,value,purpose):
            apply(seat,lambda a:a['command']==value,purpose)
        def board(viewer,owner):
            return [c for col in state[viewer]['view']['players'][owner]['columns']for c in col]
        def end(seat):
            command(seat,dict(type='end_turn'),'Ordinary turn handover')
        def wait_for(seat,predicate):
            for _ in range(6):
                if any(predicate(a)for a in state[seat]['actions']):return
                active=next(s for s in (0,1)if any(a['command']['type']=='end_turn'for a in state[s]['actions']))
                end(active)
            raise AssertionError('Required legal action did not become available')
        def choose(seat,purpose):
            while state[seat]['view']['choice']:
                apply(seat,lambda a:a['command']['type']=='choose',purpose)

        apply(0,lambda a:{'jailhouse','wanted_poster_board','gatling_emplacement'}<=set(a['command'].get('camps',[])),
              'Choose offered Jailhouse, Wanted Poster Board and Gatling Emplacement')
        apply(1,lambda a:True,'Opponent chooses offered holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand'])for s in (0,1)]
        holding=next(c['id']for c in board(0,0)if c['card_id']=='jailhouse')
        wanted=next(c['id']for c in board(0,0)if c['card_id']=='wanted_poster_board')
        target=next(c['id']for c in state[1]['view']['players'][1]['hand']if c.get('card_id')=='civil_war_veteran')
        play=lambda a:a['command'].get('type')=='play' and a['command'].get('card')==target
        wait_for(1,play);apply(1,play,'Deploy the offered Veteran; printed entry effect wounds him')
        choose(1,'Resolve offered entry choices')
        before=[next(c for c in board(s,1)if c['id']==target)for s in (0,1)]
        assert all(c['damage']==1 and not c['punk']for c in before)
        recruit=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        wait_for(0,recruit);apply(0,recruit,'Pay Jailhouse cost to recruit the wounded enemy')
        choose(0,'Choose offered Veteran recruitment and destination')
        recruited=[next(c for c in board(s,0)if c['id']==target)for s in (0,1)]
        assert all(c['owner']==0 and c['damage']==1 and not c['punk']for c in recruited)

        hire=lambda a:a['command']==dict(type='activate',source=wanted,ability=0)
        wait_for(0,hire);apply(0,hire,'Hire a privately inspected Drifter for visibility-filter testing')
        choose(0,'Choose offered Drifter position')
        punk=next(c['id']for c in board(0,0)if c.get('punk'))
        hidden=[next(c for c in board(s,0)if c['id']==punk)for s in (0,1)]
        assert hidden[0].get('private_peek') and not hidden[1].get('private_peek')
        assert all(c.get('card_id','punk')=='punk'for c in hidden)

        restore=lambda a:a['command']==dict(type='activate',source=holding,ability=1)
        wait_for(0,restore);apply(0,restore,'Pay Jailhouse cost to restore its recruited Veteran')
        choose(0,'Choose the wounded friendly Veteran for restoration')
        restored=[next(c for c in board(s,0)if c['id']==target)for s in (0,1)]
        assert all(c['owner']==0 and c['damage']==0 and not c['ready']for c in restored)
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,own_opening_hands=opening,
                    queue_moves=[],holding=holding,wanted=wanted,target=target,punk=punk,
                    target_before=before,target_recruited=recruited,target_restored=restored,private_inspection=hidden,
                    scope='Legal CPU rehearsal only; native visual/History/privacy review is separate',
                    provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},
                    bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists()
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'commands':len(journal),'holding':holding,'target':target,'punk':punk,
                          'events':sorted({e['type']for r in journal for e in r['public_events']})}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
