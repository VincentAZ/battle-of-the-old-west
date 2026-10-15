"""Rehearse Trouble props using only authorized views and legal commands."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=1229)
    parser.add_argument('--cards',nargs='+',default=['hard_winter','box_canyon','prairie_fire'])
    parser.add_argument('--stage-crew',action='store_true',help='Legally play one crew member per side before the target events')
    args=parser.parse_args();journal=[];seed=args.seed
    bridge=args.bridge.resolve()
    process=subprocess.Popen([str(bridge),str(ROOT/'game/data/cards.json'),str(seed)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        state=json.loads(process.stdout.readline())['public_snapshots']
        def apply(seat,action):
            nonlocal state
            s=state[seat];last=max((e['sequence'] for e in s['view']['log']),default=-1)
            record=dict(seat=seat,revision=s['view']['revision'],command=action['command'],
                public_label=action['label'],legal_actions_sha256=hashlib.sha256(json.dumps(s['actions'],sort_keys=True).encode()).hexdigest())
            process.stdin.write(json.dumps(dict(seat=seat,command=action['command']))+'\n');process.stdin.flush()
            reply=json.loads(process.stdout.readline());assert reply['accepted']['ok'];state=reply['public_snapshots']
            record['public_events']=[e for e in state[seat]['view']['log'] if e['sequence']>last]
            journal.append(record)
        for seat in (0,1):apply(seat,state[seat]['actions'][0])
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        targets={c['id']:c['card_id'] for c in opening[1]['own_hand'] if c['card_id'] in args.cards}
        assert set(targets.values())==set(args.cards)
        played=set();resolved=set();staged={}
        for _ in range(60):
            seat=next(s for s in (0,1) if state[s]['actions']);actions=state[seat]['actions']
            chosen=None
            if args.stage_crew and seat not in staged:
                people={c['id'] for c in state[seat]['view']['players'][seat]['hand'] if c.get('type')=='person'}
                chosen=next((a for a in actions if a['command']['type']=='play' and a['command'].get('card') in people),None)
                if chosen:staged[seat]=chosen['command']['card']
            pending=[card for name in args.cards for card,kind in targets.items() if kind==name and card not in played]
            playable=set(pending[:1]) if args.stage_crew else set(targets)
            if chosen is None and (not args.stage_crew or len(staged)==2):
                chosen=next((a for a in actions if seat==1 and a['command']['type']=='play' and a['command'].get('card') in playable),None)
            if chosen is None:chosen=next((a for a in actions if a['command']['type']=='choose'),None)
            if chosen is None and seat==1 and pending:
                # Cannonade costs four. Bank the public Hip Flask on an earlier
                # turn, then hock it at three resources; never grant test money.
                player=state[seat]['view']['players'][seat]
                wanted=next((c for c in player['hand'] if c['id']==pending[0]),None)
                cost=wanted.get('play_availability',{}).get('cost',0) if wanted else 0
                flask=next((c['id'] for c in player['hand'] if c['card_id']=='hip_flask'),None)
                if cost>3 and flask is not None and player['water']>=cost-1:
                    chosen=next((a for a in actions if a['command']['type']=='junk' and a['command'].get('card')==flask),None)
                elif cost>3 and flask is None:
                    chosen=next((a for a in actions if a['command']['type']=='silo'),None)
            if chosen is None:chosen=next(a for a in actions if a['command']['type']=='end_turn')
            if chosen['command']['type']=='play' and chosen['command']['card'] in targets:played.add(chosen['command']['card'])
            apply(seat,chosen)
            resolved.update(e['source'] for e in journal[-1]['public_events'] if e['type']=='event_resolve' and e.get('source') in targets)
            if resolved==set(targets) and not any(a['command']['type']=='choose' for s in state for a in s['actions']):break
        assert played==resolved==set(targets),(played,resolved)
        if args.stage_crew:assert len(staged)==2,staged
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',
               ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        result=dict(ok=True,seed=seed,ruleset='boomtown',scope='Public-command CPU rehearsal, not native evidence.',
            journal=journal,own_opening_hands=opening,targets=targets,
            staged_crew=staged,
            queue_moves=[e for j in journal for e in j['public_events'] if e['type']=='event_advance'],
            provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            bridge_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest())
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print('TROUBLE_PUBLIC_REHEARSAL',len(journal),'commands;',targets)
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
