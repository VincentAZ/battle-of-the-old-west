"""Rehearse Lookout Ridge's temporary exposure with offered public commands only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def rehearse(bridge,seed):
    process=subprocess.Popen([str(bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    journal=[]
    try:
        state=json.loads(process.stdout.readline())['public_snapshots']
        selections=[a for a in state[0]['actions'] if 'lookout_ridge' in a['command'].get('camps',[])]
        if not selections:return None
        def board(view,owner):return [c for col in state[view]['view']['players'][owner]['columns'] for c in col]
        def apply(seat,predicate,purpose):
            nonlocal state
            current=state[seat];offered=[a for a in current['actions'] if predicate(a)]
            assert offered,purpose
            action=offered[0];last=max((e['sequence'] for e in current['view']['log']),default=-1)
            row=dict(seat=seat,revision=current['view']['revision'],command=action['command'],purpose=purpose,
                     public_label=action['label'],legal_actions_sha256=hashlib.sha256(json.dumps(current['actions'],sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat,command=action['command']))+'\n');process.stdin.flush()
            reply=json.loads(process.stdout.readline());assert reply['accepted']['ok'];state=reply['public_snapshots']
            row['public_events']=[e for e in state[seat]['view']['log'] if e['sequence']>last];journal.append(row)
        def resolve():
            for _ in range(12):
                choices=[s for s in (0,1) if state[s]['view']['choice'] and any(a['command']['type']=='choose' for a in state[s]['actions'])]
                if not choices:return
                apply(choices[0],lambda a:a['command']['type']=='choose','Resolve offered public entry choice')
            raise AssertionError('Unresolved entry choice')
        def wait_for(seat,predicate):
            for _ in range(20):
                if any(predicate(a) for a in state[seat]['actions']):return
                active=next(s for s in (0,1) if any(a['command']['type']=='end_turn' for a in state[s]['actions']))
                apply(active,lambda a:a['command']['type']=='end_turn','Ordinary turn handover');resolve()
            raise AssertionError('Required action unavailable')
        apply(0,lambda a:a==selections[0],'Select offered Lookout Ridge holdings')
        apply(1,lambda a:a['command']['type']=='select_camps','Select offered opponent holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        holding=next(c['id'] for c in board(0,0) if c['card_id']=='lookout_ridge')
        deploy=lambda a:a['category']=='play_person' and a['command'].get('column')==0
        # Two people protect a rear person and a camp on each side.
        for seat in (0,1):
            for _ in range(2):
                wait_for(seat,deploy);apply(seat,deploy,'Deploy an offered crew member in column zero');resolve()
        activate=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        wait_for(0,activate)
        before=json.loads(json.dumps(state));cost_before=state[0]['view']['players'][0]['water']
        protected={owner:[c['id'] for c in board(0,owner) if c['protected']] for owner in (0,1)}
        assert all(protected.values())
        assert all(any(c['protected'] and c['type']==kind for c in board(0,owner)) for owner in (0,1) for kind in ('camp','person'))
        apply(0,activate,'Pay two whiskey to expose both sides for this turn')
        after=json.loads(json.dumps(state));cost_after=state[0]['view']['players'][0]['water']
        assert cost_after==cost_before-2
        assert all(not c['protected'] for view in (0,1) for owner in (0,1) for c in board(view,owner))
        assert any(e['type']=='expose_all' for e in journal[-1]['public_events'])
        apply(0,lambda a:a['command']['type']=='end_turn','End the exposure turn normally');resolve()
        restored=json.loads(json.dumps(state))
        assert all(next(c for c in board(view,owner) if c['id']==uid)['protected'] for view in (0,1) for owner in (0,1) for uid in protected[owner])
        assert all('hand' not in snapshot[s]['view']['players'][1-s] for snapshot in (before,after,restored) for s in (0,1))
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        return dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,holding=holding,
                    own_opening_hands=opening,queue_moves=[],before=before,after=after,restored=restored,
                    previously_protected=protected,cost=dict(before=cost_before,after=cost_after),
                    scope='Legal CPU rehearsal only; native ability, History and privacy presentation remain separate.',
                    provenance={str(p.relative_to(ROOT)):sha(p) for p in files},bridge_sha256=sha(bridge))
    finally:
        process.stdin.close()
        process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();assert not args.output.exists()
    failures=[]
    for seed in range(1,301):
        try:result=rehearse(args.bridge,seed)
        except (AssertionError,StopIteration) as exc:
            failures.append(dict(seed=seed,reason=str(exc)));continue
        if result:
            result['rehearsal_search_failures']=failures
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(ok=True,seed=seed,commands=len(result['journal']),holding=result['holding'],previously_protected=result['previously_protected'])))
            return
    raise AssertionError(f'No complete legal rehearsal in seed range: {failures}')


if __name__=='__main__':main()
