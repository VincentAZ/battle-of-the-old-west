"""Rehearse medical delivery to a Native and a generic crew member legally."""
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
    args=parser.parse_args();seed=142;journal=[]
    process=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],
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
            print(len(journal),purpose,action['command'],flush=True)
        def command(seat,value,purpose):apply(seat,lambda a:a['command']==value,purpose)
        def end(seat):command(seat,{'type':'end_turn'},'Ordinary turn handover')
        for seat in (0,1):apply(seat,lambda a:True,'Choose first offered legal camp combination')
        opening=[dict(seat=s,own_hand=state[s]['view']['players'][s]['hand']) for s in (0,1)]
        identities={c['card_id']:c['id'] for c in opening[0]['own_hand']}
        mutant=identities['doc_holliday'];quanah=identities['quanah_parker'];restore_card=identities['cannonade']
        command(0,dict(type='play',card=mutant,column=0,position=0),'Play Doc Holliday')
        end(0);end(1)
        command(0,dict(type='play',card=quanah,column=1,position=0),'Play canonical Quanah Parker / Quanah Parker')
        end(0)
        defs={c['id']:c for c in json.loads((ROOT/'game/data/cards.json').read_text())['cards']}
        injuries={c['id'] for c in state[1]['view']['players'][1]['hand'] if defs[c['card_id']].get('junk')=='injure'}
        apply(1,lambda a:a['command']['type']=='junk' and a['command'].get('card') in injuries,'Use a printed injure hock effect')
        apply(1,lambda a:a['command']['type']=='choose' and a.get('target')==quanah,'Choose the exposed Native crew member')
        end(1)
        command(0,dict(type='activate',source=mutant,ability=0),'Use Doc Holliday printed damage/restore ability')
        apply(0,lambda a:a['command']['type']=='choose' and a['label']=='Skip','Decline optional enemy damage')
        apply(0,lambda a:a['command']['type']=='choose' and a.get('target')==quanah,'Restore Quanah through the printed ability')
        command(0,dict(type='junk',card=restore_card),'Use printed Cannonade restore hock effect')
        apply(0,lambda a:a['command']['type']=='choose' and a.get('target')==mutant,'Restore the now-wounded generic crew member')
        restores=[e for j in journal for e in j['public_events'] if e['type']=='restore']
        assert {e['target'] for e in restores}=={quanah,mutant},restores
        process.stdin.close();assert process.wait(timeout=5)==0
        files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',
               ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
        report=dict(ok=True,seed=seed,ruleset='boomtown',scope='Public-command CPU rehearsal only; no native visual claim.',
            journal=journal,own_opening_hands=opening,queue_moves=[],medical_events=restores,
            native_target=quanah,generic_target=mutant,
            provenance={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            bridge_sha256=hashlib.sha256(args.bridge.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
