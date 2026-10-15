"""Rehearse a destroyed Prospector free analysis response through offered public commands."""
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
        selections=[a for a in state[0]['actions'] if 'gallows' in a['command'].get('camps',[])]
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
        apply(0,lambda a:a==selections[0],'Select offered Gallows holdings')
        apply(1,lambda a:a['command']['type']=='select_camps','Select offered opponent holdings')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        holding=next(c['id'] for c in board(0,0) if c['card_id']=='gallows')
        deploy=lambda a:a['category']=='play_person' and a['command'].get('column')==0 and a['command'].get('position')==0
        wait_for(0,deploy);apply(0,deploy,'Deploy an offered friendly target');resolve()
        wait_for(1,deploy);apply(1,deploy,'Deploy an enemy rear person');resolve()
        rear=next(c['id'] for c in board(1,1) if c.get('type')=='person')
        candidates={'prospector'}
        def front_deploy(a):
            hand={c['id']:c['card_id'] for c in state[1]['view']['players'][1]['hand']}
            return deploy(a) and hand.get(a['command'].get('card')) in candidates
        wait_for(1,front_deploy);apply(1,front_deploy,'Deploy an enemy with an actionable ability in front');resolve()
        target=next(c['id'] for c in board(1,1) if c.get('type')=='person' and c['id']!=rear)
        target_card=next(c['card_id'] for c in board(1,1) if c['id']==target)
        activate=lambda a:a['command']==dict(type='activate',source=holding,ability=0)
        wait_for(0,activate)
        before=json.loads(json.dumps(state));cost_before=state[0]['view']['players'][0]['water']
        assert next(c for c in board(0,1) if c['id']==rear)['protected']
        assert not next(c for c in board(0,1) if c['id']==target)['protected']
        apply(0,activate,'Pay two whiskey to destroy an exposed enemy person')
        choices=json.loads(json.dumps(state[0]['actions']))
        assert any(a.get('target')==target for a in choices)
        assert all(a.get('target')!=rear for a in choices)
        allowed={c['id'] for c in board(0,1) if c.get('type')=='person' and not c['protected']}
        assert all(a.get('target') in allowed for a in choices if a.get('target'))
        apply(0,lambda a:a.get('target')==target,'Choose exposed enemy; protected rear crew excluded')
        destroyed=json.loads(json.dumps(state))
        assert all(c['id']!=target for c in board(0,1))
        assert next(c for c in board(0,1) if c['id']==rear)
        assert state[0]['view']['players'][0]['water']==cost_before-2
        free_choices=json.loads(json.dumps(state[1]['actions']))
        assert any(a['label']=='Skip' for a in free_choices)
        water_before_free=state[1]['view']['players'][1]['water']
        apply(1,lambda a:a['command']['type']=='choose' and a['label']!='Skip','Destroyed person controller accepts an offered free ability')
        resolve()
        after=json.loads(json.dumps(state));water_after_free=state[1]['view']['players'][1]['water']
        assert water_before_free==water_after_free,'Free response charged whiskey'
        # Require observable resolution, not an empty choice/skip path.
        response_events=[e for row in journal[-8:] for e in row['public_events'] if e.get('source')==target]
        assert response_events,'No public effect from the destroyed person'
        all_events=[e for row in journal for e in row['public_events']]
        assert any(e['type']=='reveal_discard' for e in all_events), 'No public analysis reveal'
        assert any(e['type']=='analysis_choice' for e in all_events), 'No completed analysis choice'
        assert all('hand' not in snapshot[s]['view']['players'][1-s] for snapshot in (before,destroyed,after) for s in (0,1))
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        return dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,holding=holding,target=target,
                    target_card_id=target_card,protected_rear=rear,own_opening_hands=opening,queue_moves=[],
                    before=before,destroyed=destroyed,after=after,target_choices=choices,free_choices=free_choices,
                    free_water=dict(before=water_before_free,after=water_after_free),response_events=response_events,
                    cost=dict(before=cost_before,after=destroyed[0]['view']['players'][0]['water']),
                    scope='Legal CPU rehearsal: exposed-person targeting, protected rear exclusion, cost two, optional free response and both hands private. Native presentation and Skip path separate.',
                    provenance={str(p.relative_to(ROOT)):sha(p) for p in files},bridge_sha256=sha(bridge))
    finally:
        process.stdin.close()
        process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();assert not args.output.exists()
    failures=[]
    for seed in range(1,1001):
        try:result=rehearse(args.bridge,seed)
        except (AssertionError,StopIteration) as exc:
            failures.append(dict(seed=seed,reason=str(exc)));continue
        if result:
            result['rehearsal_search_failures']=failures
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(ok=True,seed=seed,commands=len(result['journal']),holding=result['holding'],target=result['target'],target_card=result['target_card_id'])))
            return
    raise AssertionError(f'No complete legal rehearsal in seed range: {failures}')


if __name__=='__main__':main()
