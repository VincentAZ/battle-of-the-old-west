"""Legal public-command rehearsal: hock newly entered crew without removing it."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--bridge',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 assert not args.output.exists()
 p=subprocess.Popen([str(args.bridge.resolve()),str(ROOT/'game/data/cards.json'),'9'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 journal=[]
 try:
  state=json.loads(p.stdout.readline())['public_snapshots']
  def apply(seat,predicate,purpose):
   nonlocal state
   a=next(a for a in state[seat]['actions'] if predicate(a));before=state
   last=max((e['sequence']for e in state[seat]['view']['log']),default=-1)
   p.stdin.write(json.dumps({'seat':seat,'command':a['command']})+'\n');p.stdin.flush()
   reply=json.loads(p.stdout.readline());assert reply['accepted']['ok'];state=reply['public_snapshots']
   journal.append(dict(seat=seat,revision=before[seat]['view']['revision'],command=a['command'],legal_actions_sha256=hashlib.sha256(json.dumps(before[seat]['actions'],sort_keys=True).encode()).hexdigest(),purpose=purpose,public_label=a['label'],public_events=[e for e in state[seat]['view']['log']if e['sequence']>last]))
   return before,state
  apply(0,lambda a:a['command'].get('camps')==['smuggler_s_landing','railroad_work_camp','general_store'],'Select offered Smuggler’s Landing')
  apply(1,lambda a:a['command']['type']=='select_camps','Select offered opposing holdings')
  opening=state
  board=lambda owner:[c for col in state[0]['view']['players'][owner]['columns']for c in col]
  source=next(c['id']for c in board(0)if c.get('card_id')=='smuggler_s_landing')
  apply(1,lambda a:a['category']=='play_person'and 'Annie Oakley'in a['label'],'Deploy an opposing person for a legal injury target')
  victim=next(c['id']for c in board(1)if c.get('card_id')=='annie_oakley')
  apply(1,lambda a:a['command']['type']=='end_turn','Ordinary turn handover')
  assert not any(a['command'].get('source')==source for a in state[0]['actions'])
  apply(0,lambda a:a['category']=='play_person'and 'Bartender'in a['label'],'Enter crew whose hock effect is injury')
  person=next(c['id']for c in board(0)if c.get('card_id')=='bartender')
  before=state;crew_before=next(c for c in board(0)if c['id']==person)
  apply(0,lambda a:a['command'].get('source')==source,'Pay one to use the newly entered person’s hock effect')
  assert state[0]['view']['players'][0]['water']==before[0]['view']['players'][0]['water']-1
  entry_choice=state
  assert len(state[0]['actions'])==1 and 'Bartender'in state[0]['actions'][0]['label']
  apply(0,lambda a:a['command']['type']=='choose','Choose only the newly entered Bartender')
  target_choice=state
  apply(0,lambda a:a.get('target')==victim,'Choose the offered opposing injury target')
  after=state
  assert next(c for c in board(0)if c['id']==person)==crew_before,'Hock removed or mutated its crew source'
  assert next(c for c in board(1)if c['id']==victim)['damage']==1
  assert before[0]['view']['discard_count']==after[0]['view']['discard_count']
  assert not any(a['command'].get('source')==source for a in state[0]['actions']),'Spent holding remained usable'
  assert all('hand'not in s['view']['players'][1-s['seat']]for s in state)
  p.stdin.close();assert p.wait(timeout=5)==0
  paths=[Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp']
  report=dict(ok=True,seed=9,ruleset='boomtown',journal=journal,opening=opening,own_opening_hands=[dict(seat=i,own_hand=opening[i]['view']['players'][i]['hand']) for i in (0,1)],queue_moves=[],holding=source,person=person,victim=victim,ability=dict(before=before,entry_choice=entry_choice,target_choice=target_choice,after=after),provenance={str(f.relative_to(ROOT)):sha(f)for f in paths},bridge_sha256=sha(args.bridge),scope='Legal CPU rehearsal: cost one, entered-person eligibility, actual injury and crew retained. Native presentation and broader cases remain.')
  args.output.write_text(json.dumps(report,indent=2)+'\n');print('SMUGGLERS_LEGAL_HOCK_PASS',len(journal),flush=True)
 finally:
  if p.poll()is None:p.terminate();p.wait(timeout=5)
if __name__=='__main__':main()
