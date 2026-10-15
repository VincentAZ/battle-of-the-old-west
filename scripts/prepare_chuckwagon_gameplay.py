"""Rehearse Chuckwagon readying, damaged-crew exclusion and public Drifter privacy using legal commands."""
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
    seed,journal=14,[]
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
        apply(0,lambda a:a['command']['camps']==['chuckwagon','salvage_yard','cattle_ranch'],'Choose offered Chuckwagon with two reusable holdings')
        apply(1,lambda a:a['command']['camps']==['boot_hill','bare_knuckle_ring','gatling_emplacement'],'Choose offered opposing Gatling Emplacement')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        def entity(owner,card_id):return next(c['id']for c in board(owner,owner)if c.get('card_id')==card_id)
        holding=entity(0,'chuckwagon');scavenger=entity(0,'salvage_yard');garage=entity(0,'cattle_ranch');gun=entity(1,'gatling_emplacement')
        assassin=next(c['id']for c in opening[0]['own_hand']if c['card_id']=='bounty_hunter')
        donor=next(c['id']for c in opening[0]['own_hand']if c['card_id']=='cornelius_ashby_railroad_baron')
        discard=next(c['id']for c in opening[0]['own_hand']if c['card_id']=='run_out_of_town')
        def command(seat,value,purpose):apply(seat,lambda a:a['command']==value,purpose)
        command(0,dict(column=0,position=0,type='play',card=assassin),'Deploy one publicly visible crew member')
        command(0,dict(type='end_turn'),'Ordinary turn handover')
        command(1,dict(type='activate',source=gun,ability=0),'Pay for a legal hit against the unprotected crew member')
        apply(1,lambda a:a.get('target')==assassin,'Damage the crew member for the exclusion check')
        command(1,dict(type='end_turn'),'Return to the Chuckwagon owner')
        command(0,dict(type='junk',card=donor),'Use the printed junk effect to gain a generic Drifter')
        apply(0,lambda a:a.get('placement',{}).get('column')==0 and a['placement']['position']==0,'Place the new exhausted Drifter')
        punk=next(c['id']for c in board(0,0)if c.get('punk'))
        command(0,dict(type='activate',source=scavenger,ability=0),'Exhaust a second holding through its printed ability')
        apply(0,lambda a:a.get('target')==discard,'Discard the offered hand card')
        apply(0,lambda a:a['label']=='Gain 1 water','Take the printed resource reward')
        command(0,dict(type='activate',source=garage,ability=0),'Exhaust the third holding through a legal Stampede advance')
        before=dict(water=state[0]['view']['players'][0]['water'],own_board=board(0,0),opponent_board=board(0,1))
        prior={c['id']:c for c in before['own_board']}
        assert all(not prior[i]['ready']for i in (scavenger,garage,punk,assassin))
        assert prior[assassin]['damage']==1 and prior[punk]['damage']==0 and prior[holding]['ready']
        command(0,dict(type='activate',source=holding,ability=0),'Pay one whiskey to ready both other holdings and the undamaged Drifter')
        after=dict(water=state[0]['view']['players'][0]['water'],own_board=board(0,0),opponent_board=board(0,1))
        current={c['id']:c for c in after['own_board']}
        assert after['water']==before['water']-1
        assert all(current[i]['ready']for i in (scavenger,garage,punk))
        assert not current[holding]['ready'] and not current[assassin]['ready']
        assert all(current[i]['damage']==prior[i]['damage']for i in prior)
        assert before['opponent_board']==after['opponent_board']
        assert set(prior)==set(current)
        # The public log exposes the ability beat, not individual ready notes.
        # Check authoritative public card readiness before/after instead.
        views=[next(c for c in board(s,0) if c['id']==punk) for s in (0,1)]
        assert all(c.get('punk') and not c.get('private_peek') and c.get('card_id','punk')=='punk' for c in views)
        command(0,dict(type='end_turn'),'Finish the readying replay and inspect the generic Drifter')
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',journal=journal,own_opening_hands=opening,
                    queue_moves=[e for r in journal for e in r['public_events']if e['type']=='event_advance'],holding=holding,punk=punk,damaged_crew=assassin,readied_holdings=[scavenger,garage],final_private_views=views,before_ready=before,after_ready=after,
                    scope='Legal CPU rehearsal only; native rendering remains separate',
                    provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists()
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'commands':len(journal),'holding':holding,'punk':punk,'events':sorted({e['type'] for r in journal for e in r['public_events']})}))
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
