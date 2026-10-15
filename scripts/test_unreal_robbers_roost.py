"""Native legal Robbers Roost trait, optional History and public-view parity."""
import argparse,copy,hashlib,json
from pathlib import Path
from test_unreal_bonus_whiskey import BonusScenario
from test_unreal_event_queue import QueueScenario
from test_unreal_wanted_board import WantedBoardScenario
from test_unreal_interactions import EDITOR,ROOT,write_json
from test_unreal_action_showcase import signature

class RoostScenario(BonusScenario):
 def __init__(self,*args):
  super().__init__(*args);self.notes={};self.public_checks={};self.holding_sample=None;self.herd_charge_samples=0;self.bonus_cleanup_samples=0
 def boot(self):
  if self.args.render_seat==0:WantedBoardScenario.boot(self)
  else:QueueScenario.boot(self)
 check_note=WantedBoardScenario.check_note
 def capture_tooltips(self):
  self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
  self.check_note(self.plan['holding'],'holding-robbers-roost')
  u=next(u for u in self.read()['cinematic']['units']if u['id']==self.plan['holding'])
  visible=[p['mesh']for p in u['holding_components']if p['visible']]
  assert any('/SM_Holding_RobbersRoost.'in m for m in visible)
  assert any('/SM_HoldingBase_RobbersRoost.'in m for m in visible)
  assert u['animated_part_count']==0
  self.holding_sample=copy.deepcopy(u);self.capture('robbers-roost-battlefield')
 def check_public(self,phase):
  views={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')}
  for snapshot in views.values():
   expected=self.plan['bonus'][phase][snapshot['seat']]
   assert snapshot['view']==expected['view'],f'{phase}: public state diverged'
   assert snapshot['actions']==expected['actions'],f'{phase}: legal actions diverged'
   assert 'hand'not in snapshot['view']['players'][1-snapshot['seat']]
  self.public_checks[phase]=views
 def choose_action(self,name,snapshot):
  if snapshot['view']['revision']==self.plan['bonus']['before'][0]['view']['revision']:
   self.check_public('before')
  return QueueScenario.choose_action(self,name,snapshot)
 def observe(self,state):
  BonusScenario.observe(self,state)
  c=state.get('cinematic',{});source=self.plan['bonus']['water_event']['source']
  if c.get('busy') and c.get('kind')=='stampede_charge':
   herd=next(u for u in c['units']if u['id']==source)
   assert herd['stampede']['animal_count']==3
   self.herd_charge_samples+=1
  if c.get('busy') and c.get('kind')=='water' and c.get('sequence')==self.plan['bonus']['water_event']['sequence']:
   assert c.get('resource_only') and not c['known_target'] and c['target']==0
   assert c['source']==source,'Resource attribution changed'
   assert not any(u['id']==source for u in c['units']),'Resolved herd retained during bonus'
   self.bonus_cleanup_samples+=1
  if len(self.actions)==len(self.replay) and not state.get('cinematic',{}).get('busy') and 'after'not in self.public_checks:
   self.check_public('after')
 def run(self):
  self.build['roost_harness']=signature(__file__);write_json(self.folder/'build.json',self.build)
  try:return QueueScenario.run(self)
  finally:
   path=self.folder/'result.json';r=json.loads(path.read_text());seq=self.plan['bonus']['water_event']['sequence']
   captured=[c for c in r.get('captures',[])if c.get('sequence')==seq and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')]
   r['robbers_roost_review']={'rendered_seat':self.args.render_seat,'history':self.notes,'holding':self.holding_sample,'public_checks':self.public_checks,'bonus_sequence':seq,'bonus_samples':len(self.bonus_samples.get(seq,[])),'bonus_captures':captured,'limits':'One legal Stampede bonus at one pine placement per seat; other layouts, damage lifecycles, interruptions, effects/audio and packaging remain.'}
   r['robbers_roost_review'].update(herd_charge_samples=self.herd_charge_samples,bonus_cleanup_samples=self.bonus_cleanup_samples)
   r['ok']=bool(r.get('ok') and self.herd_charge_samples and self.bonus_cleanup_samples)
   r['ok']=bool(r.get('ok')and self.holding_sample and self.bonus_samples.get(seq)and captured and set(self.public_checks)=={'before','after'}and 'holding-robbers-roost'in self.notes)
   write_json(self.folder/'bonus-samples.json',self.bonus_samples);write_json(path,r)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--render-seat',type=int,choices=[0,1],default=0);p.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/robbers-roost/gameplay-plan-v002.json');args=p.parse_args()
 plan=json.loads(args.manifest.read_text())
 for path,h in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20949+args.render_seat*10,500
 args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
 args.settle,args.prefer_camp,args.require_kind=0,[],['raid_launch','event_advance','stampede_charge','water']
 args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,True
 args.native_extra_args=['-OldWestRegionReview=1'];args.scenario_config={'name':'robbers_roost','policy':'public_replay','target_kinds':args.require_kind}
 args.output.mkdir(parents=True,exist_ok=True);RoostScenario(args,args.output,(1600,900),0).run()
 result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
 assert result['ok'],result.get('failure')or result.get('issues')or result.get('robbers_roost_review')
 print('ROBBERS_ROOST_NATIVE_PASSED',args.render_seat,flush=True)
if __name__=='__main__':main()
