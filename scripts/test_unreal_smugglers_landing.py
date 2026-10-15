"""Native legal Smuggler's Landing hock effect and optional public History."""
import argparse,copy,hashlib,json
from pathlib import Path
from test_unreal_event_queue import QueueScenario
from test_unreal_wanted_board import WantedBoardScenario
from test_unreal_interactions import EDITOR,ROOT,write_json,center
from test_unreal_action_showcase import signature
from test_unreal_portraits import portraits_ready

class LandingScenario(QueueScenario):
 def __init__(self,*args):
  super().__init__(*args);self.notes={};self.public_checks={};self.holding_sample=None;self.effect_samples=[]
  self.expected_events={e['sequence']:e for row in self.plan['journal'] for e in row['public_events'] if row['revision']>=self.plan['ability']['before'][0]['view']['revision']}
 def boot(self):
  if self.args.render_seat==0:WantedBoardScenario.boot(self)
  else:QueueScenario.boot(self)
 check_note=WantedBoardScenario.check_note
 def capture_tooltips(self):
  self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
  self.check_note(self.plan['holding'],'holding-smugglers-landing')
  u=next(u for u in self.read()['cinematic']['units']if u['id']==self.plan['holding'])
  visible=[p['mesh']for p in u['holding_components']if p['visible']]
  for name in ['SM_Holding_SmugglersLanding','SM_HoldingBase_SmugglersLanding','SM_HoldingWater_SmugglersLanding']:
   assert any('/'+name+'.'in m for m in visible),name
  assert u['animated_part_count']==0
  self.holding_sample=copy.deepcopy(u);self.capture('smugglers-landing-battlefield')
  if self.args.require_terrain_fit:
   region=self.hud()['region']
   assert region['index']==self.args.region and region['original_collider_retained']
   assert len(region['landing_foundations'])==1 and region['landing_material']
   assert region['landing_foundations'][0]['profile']=='split_wet_dry_v002'
   base=next(p for p in u['holding_components']if '/SM_HoldingBase_'in p['mesh'])
   assert base['ground_fit']['enabled']==1
   assert base['ground_fit']['material'].endswith('/M_LandingDryBankV003.M_LandingDryBankV003')
  if self.args.preview_exclusion:self.check_preview_exclusion()
 def check_preview_exclusion(self):
  before=copy.deepcopy(self.hud()['region']);snapshots={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')};checks=[]
  def scene():return next((s for s in self.hud()['portraits']['scenes']if s['card_id']=='smuggler_s_landing'),None)
  self.command('a','portrait_gallery',ids=['smuggler_s_landing'],enabled=True)
  self.wait('live holding portrait ready',lambda:portraits_ready(self.hud()['portraits'],['smuggler_s_landing'],{'smuggler_s_landing':3}),120)
  for name,damage,destroyed in [('healthy',0,False),('damaged',1,False),('ruined',2,True),('repaired',0,False)]:
   count=scene()['captures']
   self.command('a','portrait_gallery',conditions=[dict(id='smuggler_s_landing',damage=damage,destroyed=destroyed)])
   self.wait('preview '+name,lambda:scene()['camp_damage']==damage and scene()['camp_destroyed']==destroyed and portraits_ready(self.hud()['portraits'],['smuggler_s_landing'],{'smuggler_s_landing':count+3}),120)
   assert self.hud()['region']==before,'Portrait changed live terrain registration'
   assert all(self.snapshot(p)==snapshots[p]for p in snapshots),'Portrait changed authoritative state'
   self.capture('landing-live-preview-'+name)
   assert portraits_ready(self.hud()['portraits'],['smuggler_s_landing'],{'smuggler_s_landing':count+3})
   checks.append(dict(phase=name,region=copy.deepcopy(self.hud()['region']),unchanged_peer_snapshots=True))
  self.command('a','portrait_gallery',ids=[],enabled=False)
  self.wait('landing preview reclaimed',lambda:not scene(),15)
  assert self.hud()['region']==before
  assert all(self.snapshot(p)==snapshots[p]for p in snapshots)
  checks.append(dict(phase='reclaimed',region=copy.deepcopy(self.hud()['region']),unchanged_peer_snapshots=True))
  self.preview_exclusion_checks=checks
 def check_public(self,phase):
  views={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')}
  for snapshot in views.values():
   expected=self.plan['ability'][phase][snapshot['seat']]
   assert snapshot['view']==expected['view'],phase+': public state diverged'
   assert snapshot['actions']==expected['actions'],phase+': legal actions diverged'
   assert 'hand'not in snapshot['view']['players'][1-snapshot['seat']]
  self.public_checks[phase]=views
 def coverage(self):
  result=super().coverage()
  if getattr(self.args,'rematch',False) and not hasattr(self,'rematch_check') and 'after'in self.public_checks:
   self.check_rematch()
  if getattr(self.args,'lifecycle',False) and not hasattr(self,'lifecycle_checks') and 'after'in self.public_checks:
   self.lifecycle_checks=[]
   assert self.args.render_seat==1,'Lifecycle review requires the rendered client'
   before={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')}
   region=copy.deepcopy(self.hud()['region'])
   assert len(region['landing_foundations'])==1
   self.command('a','leave')
   self.wait('landing client reaches menu',lambda:self.snapshot().get('hosted')is False and self.snapshot('b').get('connected')==1,60)
   self.wait('menu clears landing scene',lambda:not self.hud().get('region') and not self.read().get('cinematic',{}).get('units'),30)
   self.capture('landing-lifecycle-menu')
   self.lifecycle_checks.append(dict(phase='left',region=self.hud().get('region'),units=self.read().get('cinematic',{}).get('units')))
   self.command('a','join',address=f'127.0.0.1:{self.port}')
   self.wait('landing client reconnects',self.agree,90)
   self.wait('landing foundation restored once',lambda:len((self.hud().get('region')or{}).get('landing_foundations',[]))==1 and not self.read().get('cinematic',{}).get('busy',True),90)
   assert before=={p:self.snapshot(p)for p in ('a','b')},'Reconnect changed peer state or legal actions'
   restored=self.hud()['region']
   assert restored['landing_foundations']==region['landing_foundations'] and restored['index']==region['index']
   assert restored['landing_material'] and restored['original_collider_retained']
   self.capture('landing-lifecycle-reconnected')
   self.lifecycle_checks.append(dict(phase='reconnected',region=copy.deepcopy(restored),exact_peer_snapshots=True))
   # Travel through ordinary menus to start an independent match. This is
   # deliberately separate from rematch, which requires a finished game.
   self.command('a','leave')
   self.wait('client menu before new game',lambda:self.snapshot().get('hosted')is False,60)
   self.command('b','leave')
   self.wait('host menu before new game',lambda:self.snapshot('b').get('hosted')is False,60)
   self.command('b','host',ruleset=self.args.ruleset)
   self.wait('new hosted selection',lambda:self.snapshot('b').get('hosted')is True and self.snapshot('b').get('match_id')!=before['b']['match_id'],90)
   self.command('a','join',address=f'127.0.0.1:{self.port}')
   self.wait('fresh synchronized selection',lambda:self.agree() and self.snapshot()['view']['status']=='selection',90)
   assert not self.hud().get('region'),'Selection retained previous regional scenery'
   selections=[]
   for peer in ('b','a'):
    offered=next(a for a in self.snapshot(peer)['actions']if a['command']['type']=='select_camps' and 'smuggler_s_landing'not in a['command']['camps'])
    selections.append(dict(peer=peer,command=copy.deepcopy(offered['command'])))
    self.submit(peer,offered)
   self.wait('fresh match starts without landing',lambda:self.agree() and self.snapshot()['view']['status']=='actions',60)
   self.settle_presentation()
   self.wait('fresh regional terrain has no landing',lambda:self.hud().get('region') and not self.hud()['region']['landing_foundations'] and not self.hud()['region']['landing_material'],60)
   fresh=copy.deepcopy(self.hud()['region'])
   assert fresh['original_collider_retained'] and fresh['index']==self.args.region
   assert all(not any('SmugglersLanding'in p.get('mesh','')for p in u.get('holding_components',[]))for u in self.read()['cinematic']['units'])
   self.capture('landing-lifecycle-fresh-match')
   self.lifecycle_checks.append(dict(phase='fresh_match',region=fresh,legal_selections=selections,snapshots={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')}))
   write_json(self.folder/'lifecycle-checks.json',self.lifecycle_checks)
  return result
 def check_rematch(self):
  before=copy.deepcopy(self.hud()['region']);match=self.snapshot()['match_id']
  self.rematch_check=dict(ok=False,before=before,match_before=match)
  expected=before['landing_restore_material']
  assert expected and before['surface_material']==before['landing_material']
  def click_button(identity):
   button=self.wait('arranged '+identity,lambda:next((b for b in self.hud()['camera_buttons']if b['id']==identity and b['allocated_size'][0]>1),None),20)
   self.event('down',center(button));self.event('up',center(button))
  click_button('new_game')
  click_button('confirm_new_game')
  self.wait('ordinary forfeit finishes match',lambda:self.agree() and self.snapshot()['view']['status']=='won',30)
  assert self.snapshot()['rematch_votes'][self.args.render_seat]
  self.command('b','rematch')
  self.wait('same-map rematch enters selection',lambda:self.agree() and self.snapshot()['match_id']!=match and self.snapshot()['view']['status']=='selection',60)
  selection=copy.deepcopy(self.hud().get('region'))
  choices=[]
  for seat in (0,1):
   peer=next(p for p in ('a','b')if self.snapshot(p)['seat']==seat)
   offered=next(a for a in self.snapshot(peer)['actions']if a['command']['type']=='select_camps' and 'smuggler_s_landing'not in a['command']['camps'])
   choices.append(dict(peer=peer,command=copy.deepcopy(offered['command'])))
   self.submit(peer,offered)
  self.wait('rematch begins without landing',lambda:self.agree() and self.snapshot()['view']['status']=='actions',60)
  self.settle_presentation()
  self.wait('rematch restores ordinary terrain material',lambda:self.hud().get('region') and self.hud()['region']['surface_material']==expected and not self.hud()['region']['landing_foundations'] and not self.hud()['region']['landing_material'],60)
  after=copy.deepcopy(self.hud()['region'])
  assert after['index']==self.args.region and after['original_collider_retained']
  assert not after['landing_restore_material']
  assert all(not any('SmugglersLanding'in p.get('mesh','')for p in u.get('holding_components',[]))for u in self.read()['cinematic']['units'])
  self.capture('landing-same-map-rematch-clean')
  self.rematch_check.update(ok=True,selection_region=selection,after=after,legal_selections=choices,snapshots={p:copy.deepcopy(self.snapshot(p))for p in ('a','b')},no_map_travel_commands=True)
  write_json(self.folder/'rematch-check.json',self.rematch_check)
 def choose_action(self,name,snapshot):
  for phase in ('before','entry_choice','target_choice'):
   if snapshot['view']['revision']==self.plan['ability'][phase][0]['view']['revision']:self.check_public(phase)
  return QueueScenario.choose_action(self,name,snapshot)
 def observe(self,state):
  QueueScenario.observe(self,state);c=state.get('cinematic',{})
  if c.get('busy') and c.get('sequence')in self.expected_events:
   self.effect_samples.append(copy.deepcopy(c))
  if len(self.actions)==len(self.replay)and not c.get('busy')and 'after'not in self.public_checks:
   self.check_public('after')
   unit=next(u for u in c['units']if u['id']==self.plan['person'])
   assert not unit['dead']and not unit['hidden'],'Hock removed its surviving crew performer'
   self.capture('smugglers-landing-crew-retained')
 def run(self):
  self.build['landing_harness']=signature(__file__);write_json(self.folder/'build.json',self.build)
  try:return QueueScenario.run(self)
  finally:
   path=self.folder/'result.json';r=json.loads(path.read_text());coverage=[]
   for seq,event in self.expected_events.items():
    captures=[x for x in r.get('captures',[])if x['sequence']==seq and x.get('native_phase_bracket_valid')and x.get('painted_beat_bracket_valid')]
    samples=[x for x in self.effect_samples if x['sequence']==seq]
    coverage.append(dict(event=event,samples=len(samples),captures=captures,passed=bool(samples and captures)))
   r['smugglers_review']=dict(rendered_seat=self.args.render_seat,region=self.args.region,terrain_fit_required=self.args.require_terrain_fit,history=self.notes,holding=self.holding_sample,public_checks=self.public_checks,event_coverage=coverage,limits='One entered Bartender injury-hock sequence at one placement in the selected region; other junk effects, identities, placements, interrupts and packaging remain.')
   r['smugglers_review']['preview_exclusion_checks']=getattr(self,'preview_exclusion_checks',[])
   r['ok']=bool(r.get('ok')and self.holding_sample and all(x['passed']for x in coverage)and set(self.public_checks)=={'before','entry_choice','target_choice','after'}and 'holding-smugglers-landing'in self.notes)
   if self.args.preview_exclusion:r['ok']=bool(r['ok']and len(getattr(self,'preview_exclusion_checks',[]))==5)
   r['smugglers_review']['lifecycle_checks']=getattr(self,'lifecycle_checks',[])
   if self.args.lifecycle:r['ok']=bool(r['ok']and len(getattr(self,'lifecycle_checks',[]))==3)
   r['smugglers_review']['rematch_check']=getattr(self,'rematch_check',None)
   if self.args.rematch:r['ok']=bool(r['ok']and getattr(self,'rematch_check',{}).get('ok'))
   write_json(self.folder/'effect-samples.json',self.effect_samples);write_json(path,r)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--render-seat',type=int,choices=[0,1],default=0);p.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/smugglers-landing/gameplay-plan-v003.json');p.add_argument('--region',type=int,choices=[0,1,2],default=1);p.add_argument('--require-terrain-fit',action='store_true');p.add_argument('--preview-exclusion',action='store_true');p.add_argument('--lifecycle',action='store_true');p.add_argument('--rematch',action='store_true');args=p.parse_args()
 if args.rematch and args.lifecycle:p.error('Choose one lifecycle mode per run')
 if args.lifecycle and args.render_seat!=1:p.error('--lifecycle requires --render-seat 1')
 plan=json.loads(args.manifest.read_text())
 for path,h in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,21249+args.render_seat*10,500
 args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
 # Entry and hit require motion; the authorized static holding does not.
 # Ability sequence still requires native samples and bracketed captures above.
 args.settle,args.prefer_camp,args.require_kind=0,[],['enter','damage']
 args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
 args.native_extra_args=[f'-OldWestRegionReview={args.region}'];args.scenario_config=dict(name='smugglers_landing',policy='public_replay',target_kinds=args.require_kind)
 args.output.mkdir(parents=True,exist_ok=True);LandingScenario(args,args.output,(1600,900),0).run()
 r=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',r)
 assert r['ok'],r.get('failure')or r.get('issues')or r.get('smugglers_review')
 print('SMUGGLERS_NATIVE_PASSED',args.render_seat,flush=True)
if __name__=='__main__':main()
