"""Rehearse two successive Stampede resolutions and Robbers Roost bonuses using public commands."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bridge',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 assert not args.output.exists()
 seed=5;journal=[]
 p=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),str(seed)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 try:
  state=json.loads(p.stdout.readline())['public_snapshots']
  def apply(seat,predicate,purpose):
   nonlocal state
   current=state[seat];a=next(a for a in current['actions']if predicate(a));last=max((e['sequence']for e in current['view']['log']),default=-1)
   before=state
   row={'seat':seat,'revision':current['view']['revision'],'command':a['command'],'purpose':purpose,'public_label':a['label'],'legal_actions_sha256':hashlib.sha256(json.dumps(current['actions'],sort_keys=True).encode()).hexdigest()}
   p.stdin.write(json.dumps({'seat':seat,'command':a['command']})+'\n');p.stdin.flush();reply=json.loads(p.stdout.readline());assert reply['accepted']['ok'];state=reply['public_snapshots']
   row['public_events']=[e for e in state[seat]['view']['log']if e['sequence']>last];journal.append(row)
   return before,state,row
  apply(0,lambda a:a['command'].get('camps')==['livery_barn','cattle_ranch','robbers_roost'],'Select offered Robbers Roost and a Stampede-launching holding')
  apply(1,lambda a:a['command']['type']=='select_camps','Select offered opposing holdings')
  opening=state
  board=lambda seat,owner:[c for col in state[seat]['view']['players'][owner]['columns']for c in col]
  holding=next(c['id']for c in board(0,0)if c['card_id']=='robbers_roost');garage=next(c['id']for c in board(0,0)if c['card_id']=='cattle_ranch')
  bonus=None;bonuses=[]
  for step in range(48):
   choices=[s for s in (0,1)if any(a['command']['type']=='choose'for a in state[s]['actions'])]
   if choices:
    before,after,row=apply(choices[0],lambda a:a['command']['type']=='choose','Victim selects an offered holding for the Stampede hit')
   elif any(a['command'].get('source')==garage and a['command']['type']=='activate'for a in state[0]['actions']):
    before,after,row=apply(0,lambda a:a['command'].get('source')==garage and a['command']['type']=='activate','Use the legal holding ability to launch or advance the Stampede')
   else:
    seat=next(s for s in (0,1)if any(a['command']['type']=='end_turn'for a in state[s]['actions']))
    before,after,row=apply(seat,lambda a:a['command']['type']=='end_turn','Ordinary turn handover advances the fuse')
   water=[e for e in row['public_events']if e['type']=='water' and e['player']==0 and e['source']!=0]
   if water:
    assert len(water)==1
    event=water[0];damage=[e for r in journal for e in r['public_events']if e['type']=='damage'and e['source']==event['source']]
    assert len(damage)==len(bonuses)+1, (event, row['public_events'], damage)
    assert after[0]['view']['players'][0]['water']==before[0]['view']['players'][0]['water']+1
    assert after[0]['view']['players'][1]['water']==before[0]['view']['players'][1]['water']
    bonus={'before':before,'after':after,'water_event':event,'damage_event':damage[-1]};bonuses.append(bonus)
    if len(bonuses)==2:break
  assert len(bonuses)==2,'Two legal Stampede bonuses were not reached'
  assert bonuses[0]['water_event']['sequence'] < bonuses[1]['water_event']['sequence']
  assert all('hand'not in s['view']['players'][1-s['seat']]for s in state)
  p.stdin.close();assert p.wait(timeout=5)==0
  files=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
  result={'ok':True,'seed':seed,'ruleset':'boomtown','journal':journal,'opening':opening,'own_opening_hands':[{'seat':i,'own_hand':opening[i]['view']['players'][i]['hand']}for i in (0,1)],'holding':holding,'launcher':garage,'bonus':bonus,'bonuses':bonuses,'queue_moves':[e for r in journal for e in r['public_events']if e['type']=='event_advance'],'provenance':{str(f.relative_to(ROOT)):sha(f)for f in files},'bridge_sha256':sha(args.bridge),'scope':'Two legal CPU Stampede resolutions, including relaunch after the first bonus; native rendering remains separate.'}
  args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print('ROBBERS_ROOST_REPEATED_LEGAL_BONUSES',len(journal),holding,event,flush=True)
 finally:
  if p.poll()is None:p.terminate();p.wait(timeout=5)
if __name__=='__main__':main()
