"""Rehearse expansion Rockslide Ridge with offered public commands only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();seed=25;journal=[]
    process=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
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
        def board(seat,owner):return [c for col in state[seat]['view']['players'][owner]['columns'] for c in col]
        def wait_for(seat,predicate):
            for _ in range(12):
                if any(predicate(a) for a in state[seat]['actions']):return
                active=next(s for s in (0,1) if any(a['command']['type']=='end_turn' for a in state[s]['actions']))
                apply(active,lambda a:a['command']['type']=='end_turn','Ordinary turn handover')
            raise AssertionError('Required public action did not become available')
        apply(0,lambda a:'rockslide_ridge' in a['command'].get('camps',[]),'Select offered Rockslide Ridge')
        apply(1,lambda a:True,'Select offered opponent holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        holding=next(c['id'] for c in board(0,0) if c['card_id']=='rockslide_ridge')
        deploy=lambda a:a['category']=='play_person' and a['command'].get('column')==0
        for n in range(2):
            wait_for(1,deploy);apply(1,deploy,'Deploy an offered opposing crew member in column zero')
            while state[1]['view']['choice']:
                apply(1,lambda a:a['command']['type']=='choose','Resolve an offered entry choice')
        targets=[c for c in state[0]['view']['players'][1]['columns'][0] if c['type']=='person']
        assert len(targets)==2,targets
        enemy_camp=next(c for c in state[0]['view']['players'][1]['columns'][0] if c['type']=='camp')
        activate=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        wait_for(0,activate)
        before=json.loads(json.dumps(state));water_before=state[0]['view']['players'][0]['water']
        apply(0,activate,'Pay three whiskey for Rockslide Ridge')
        while state[0]['view']['choice']:
            apply(0,lambda a:a['command']['type']=='choose','Select the offered first enemy column')
        after=json.loads(json.dumps(state));water_after=state[0]['view']['players'][0]['water']
        assert water_after==water_before-3
        assert all(not any(c['id']==t['id'] for c in board(s,1)) for s in (0,1) for t in targets)
        assert all(next(c for c in board(s,1) if c['id']==enemy_camp['id'])['damage']==enemy_camp['damage']+1 for s in (0,1))
        assert all(next(c for c in board(s,0) if c['id']==holding)['destroyed'] for s in (0,1))
        assert all('hand' not in state[s]['view']['players'][1-s] for s in (0,1))
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,own_opening_hands=opening,
            queue_moves=[],holding=holding,targets=targets,enemy_camp=enemy_camp,before=before,after=after,
            cost=dict(before=water_before,after=water_after),
            scope='Legal CPU rehearsal only; native presentation, History and privacy review separate',
            provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists()
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'commands':len(journal),'holding':holding,'targets':targets,'events':sorted({e['type'] for row in journal for e in row['public_events']})}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)

if __name__=='__main__':main()
