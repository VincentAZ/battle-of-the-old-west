#!/usr/bin/env python3
"""Damaged camp activation and dense placement through actual Slate inputs."""
import argparse,copy,json,time
from pathlib import Path
from test_unreal_battle_journal import JournalScenario
from test_unreal_interactions import EDITOR,center,resolution,write_json,field_cards
from native_launch import game_net_driver_ports,stop_owned_process_groups,create_native_run_directory
from native_runtime_checks import assert_runtime_assets

class FrontlineScenario(JournalScenario):
 def boot(self):
  self.launch('b',f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
  log=self.folder/'b.log';self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
  self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
  self.wait('rendered menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
  self.command('a','join',address=f'127.0.0.1:{self.port}');self.wait('two peers',self.agree,100)
  for peer in ('b','a'):
   options=self.snapshot(peer)['actions']
   action=next((x for x in options if x['command']['camps']==['bunkhouse','telegraph_office','packer_s_cabin']),None) if peer=='a' else None
   self.submit(peer,action or max(options,key=lambda x:sum(self.defs[c]['starting_cards'] for c in x['command']['camps'])))
  self.wait('match starts',lambda:self.snapshot()['view']['status']=='actions');self.settle_presentation()
  own=self.snapshot()['seat'];self.camps={c['card_id']:c['id'] for c in field_cards(self.snapshot()) if c['owner']==own and c['type']=='camp'}
  assert {'bunkhouse','telegraph_office','packer_s_cabin'}==set(self.camps),self.camps
 def own_turn(self):
  self.clear_choices()
  if self.snapshot()['view']['active_player']!=self.snapshot()['seat']:
   self.submit('b',next(a for a in self.snapshot('b')['actions'] if a['command']['type']=='end_turn'))
  self.settle_presentation()
 def round(self):
  self.own_turn();self.submit('a',next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn'));self.own_turn()
 def inspect(self,card):
  self.settle_presentation();self.tab('your')
  if self.panel()['collapsed']:self.click(center(self.panel()['collapse_button']));self.wait('open panel',lambda:not self.panel()['collapsed'])
  self.fold('your.actions',False)
  # Presentation-only inspection selects the same public card; ability itself
  # must be clicked through its actual native button.
  self.command('a','inspect',card=card)
  self.wait('selected source',lambda:self.hud().get('selected_source')==card)
 def click_ability(self,card,label):
  self.inspect(card)
  self.assert_readiness(card,'ready')
  self.fold('your.formation',True)
  def button():
   return next((e for e in self.hud()['master_actions'] if json.loads(e['id']).get('source')==card and e['allocated_size'][0]>1 and self.inside(e)),None)
  entry=self.wait('damaged camp ability button',button)
  before=self.snapshot()['view']['revision'];self.capture(label+'-before');self.click(center(entry))
  self.wait('button accepted by both peers',lambda:self.agree() and self.snapshot()['view']['revision']==before+1)
  self.clear_choices();self.settle_presentation();self.assert_readiness(card,'spent');self.capture(label+'-after')
 def assert_readiness(self,card,expected):
  self.settle_presentation()
  entry=self.wait('visible readiness marker',lambda:next((m for m in self.hud()['battlefield_labels'] if m['id']==card),None))
  assert entry['readiness']==expected,(expected,entry)
  self.evidence.setdefault('readiness_transitions',[]).append(dict(card=card,expected=expected,label=entry))
 def uniform_formation(self,label):
  self.settle_presentation()
  if self.panel()['collapsed']:self.click(center(self.panel()['collapse_button']));self.wait('open panel',lambda:not self.panel()['collapsed'])
  for side in ('your','enemy'):
   self.tab(side)
   outer=self.hud().get('battle_scroll',[self.panel()['content']])[0]
   self.event('wheel',(outer['max'][0]-4,center(outer)[1]),wheel=30);time.sleep(.6)
   for suffix in ('water','hand','events','details'):
    if self.section(side+'.'+suffix):self.fold(side+'.'+suffix,True)
   if self.section('your.actions'):self.fold('your.actions',True)
   self.fold(side+'.formation',False)
   for column in range(1,4):self.fold(side+'.column'+str(column),False)
   outer=self.hud().get('battle_scroll',[self.panel()['content']])[0]
   self.event('wheel',(outer['max'][0]-4,center(outer)[1]),wheel=30);time.sleep(.6)
   h=self.hud();slots=h['formation_slots'];assert len(slots)==9
   assert all(self.inside(s) for s in slots),'Uniform formation slots are clipped'
   for axis in (0,1):
    sizes=[s['allocated_size'][axis] for s in slots]
    assert max(sizes)-min(sizes)<.1,(axis,sizes)
   indexed={s['id']:s for s in slots}
   for row in range(3):
    ys=[indexed[f'{column}:{row}']['min'][1] for column in range(3)]
    assert max(ys)-min(ys)<.1,ys
   for column in range(3):
    xs=[indexed[f'{column}:{row}']['min'][0] for row in range(3)]
    assert max(xs)-min(xs)<.1,xs
   player=self.snapshot()['view']['players'][h['inspector_side']]
   cards=[c for col in player['columns'] for c in col]
   self.evidence.setdefault('formation_layouts',[]).append(dict(label=label,side=side,slots=slots,cards=cards))
   self.capture(label+'-'+side)
   card=next(e for e in h['master_cards'] if self.inside(e))
   self.event('move',center(card))
   self.wait('formation hover',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==int(card['id']))
   tooltip=self.hud()['card_hover']['rect'];panel=self.panel()['panel'];w,height=self.hud_dimensions()
   assert tooltip['min'][0]>=0 and tooltip['min'][1]>=0 and tooltip['max'][0]<=w and tooltip['max'][1]<=height
   assert tooltip['max'][0]<=panel['min'][0] or tooltip['min'][0]>=panel['max'][0],'Hover obscures formation'
   self.evidence.setdefault('formation_hovers',[]).append(dict(side=side,card=card['id'],tooltip=tooltip,panel=panel))
   self.capture(label+'-'+side+'-hover');self.event('move',(100,40))
   for suffix in ('water','hand','events'):
    self.fold(side+'.'+suffix,False)
   if self.section('your.actions'):self.fold('your.actions',False)
  self.tab('your');self.event('wheel',center(self.panel()['content']),wheel=30);time.sleep(.6)
 def damaged_camps(self):
  self.own_turn()
  for name in ('bunkhouse','telegraph_office'):
   self.round();totem=self.camps['packer_s_cabin']
   act=next(a for a in self.snapshot()['actions'] if a['command'].get('source')==totem)
   self.submit('a',act)
   target=next(a for a in self.snapshot()['actions'] if a['label'].startswith(self.defs[name]['name']+' ('))
   self.submit('a',target);self.clear_choices();self.settle_presentation()
   assert next(c for c in field_cards(self.snapshot()) if c['id']==self.camps[name])['damage']==1
  self.round()
  self.click_ability(self.camps['bunkhouse'],'01-damaged-command-post')
  self.round()
  raid=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='raid','raid symbol')
  self.submit('a',raid);self.clear_choices();self.settle_presentation()
  self.click_ability(self.camps['telegraph_office'],'02-damaged-omen-clock')
  self.checked('Damaged Bunkhouse and Telegraph Office retain readiness after full turn changes and activate through real Battle Panel buttons on both network peers')
  self.inspect(self.camps['telegraph_office']);self.capture('03-spent-camp-explanation')
  selected=next(c for c in field_cards(self.snapshot()) if c['id']==self.camps['telegraph_office'])
  assert selected['ability_availability'][0]['reason']=='Already used this turn'
  self.checked('Used damaged camp reports already-used reason, not a generic deployment hint')
 def labels(self,label,allow_empty=False):
  self.settle_presentation()
  h=self.hud();bounds=h['battlefield_rect'];labels=h['battlefield_labels'];assert labels or allow_empty
  for i,m in enumerate(labels):
   r=m['rect'];assert bounds[0]<=r[0]<r[2]<=bounds[2] and bounds[1]<=r[1]<r[3]<=bounds[3]
   pixels=(r[3]-r[1])/h['overlay_unit'];assert pixels<=24,pixels
   for n in labels[i+1:]:
    q=n['rect'];assert min(r[2],q[2])<=max(r[0],q[0]) or min(r[3],q[3])<=max(r[1],q[1]),(m,n)
  self.capture(label)
 def dense_placement(self):
  self.own_turn()
  for _ in range(6):
   people=[c for c in field_cards(self.snapshot()) if c['owner']==self.snapshot()['seat'] and c['type']=='person']
   if len(people)>=6:break
   playable=self.seek(lambda a,s:a['command']['type']=='play' and a['category']=='play_person' and not a['command'].get('replace'),'six deployed people')
   played=playable['command']['card'];identity=self.own_hand()[played]['card_id']
   self.submit('a',playable);self.clear_choices();self.settle_presentation()
   if identity=='prospector':self.assert_readiness(played,'recovering');self.capture('03b-new-person-recovering')
   if identity=='civil_war_veteran':
    self.assert_readiness(played,'damaged');self.capture('03c-wounded-person-not-ready')
  assert len([c for c in field_cards(self.snapshot()) if c['owner']==self.snapshot()['seat'] and c['type']=='person'])==6
  replacement=self.seek(lambda a,s:a['command']['type']=='play' and a['command'].get('replace'),'full board replacement')
  self.uniform_formation('04a-uniform-populated-formation')
  self.settle_presentation();self.tab('your');self.fold('your.formation',True)
  self.labels('04-full-formation-labels')
  # Actual hand widget and pointer drag, without the old helper's fixed-offset assumptions.
  card=replacement['command']['card'];widget=self.visible_hand_widget(card);start=center(widget)
  self.event('move',start);self.event('down',start);self.event('move',(start[0]+14,start[1]-22))
  self.wait('replacement drag',lambda:self.hud()['deployment']['card']==card)
  h=self.hud();targets=h['deployment']['targets'];assert len(targets)==12,len(targets)
  assert all(t['projected'] for t in targets),'A replacement is unreachable'
  u=h['overlay_unit']
  for i,t in enumerate(targets):
   assert 'Replace ' in t['label'] and 'Lane ' in t['label']
   for q in targets[i+1:]:assert abs(t['screen'][0]-q['screen'][0])>=140*u or abs(t['screen'][1]-q['screen'][1])>=42*u,'Replacement badges overlap'
  self.capture('05-twelve-clear-replacement-options')
  chosen=targets[-1];before=self.snapshot();self.finish_drop(chosen);self.clear_choices();self.settle_presentation()
  assert chosen['command']['replace'] not in {c['id'] for c in field_cards(self.snapshot())}
  assert card in {c['id'] for c in field_cards(self.snapshot())}
  self.checked('Twelve full-board replacement choices are non-overlapping and the exact victim and insertion position are submitted through Slate')
  punk=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='punk','Punk identity')
  self.submit('a',punk)
  placement=next(a for a in self.snapshot()['actions'] if a['command']['type']=='choose' and a['label']!='Skip')
  self.submit('a',placement);self.clear_choices();self.settle_presentation()
  visible=[u for u in self.read()['cinematic']['units'] if u.get('card_id')=='punk' and not u.get('preview_only') and not u.get('hidden')]
  assert visible and all('/Identities/SKM_Punk_Cm.' in u['visual_mesh'] and not u['weapon_visible'] for u in visible)
  self.capture('05b-punk-public-identity');self.checked('Face-down Punk uses its own masked mohawk model and no visible rifle')
  wounded=next(c['id'] for c in field_cards(self.snapshot()) if c.get('card_id')=='civil_war_veteran' and c['owner']==self.snapshot()['seat'])
  restore=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='restore','ordinary person restoration')
  self.submit('a',restore)
  self.submit('a',next(a for a in self.snapshot()['actions'] if a['label'].startswith('Civil War Veteran (')))
  self.clear_choices();self.assert_readiness(wounded,'recovering');self.capture('05c-restored-person-recovering')
  self.round();self.assert_readiness(wounded,'ready');self.click_ability(wounded,'05d-person-ready-then-spent')
  self.checked('Ordinarily restored person shows recovering, becomes ready after cleanup, and shows spent after its native ability button is used')
  self.click(center(self.panel()['collapse_button']));self.wait('panel closed',lambda:self.panel()['collapsed'])
  for index,wheel in enumerate((5,5,-10)):
   w,height=self.hud_dimensions();self.event('wheel',(w*.48,height*.34),wheel=wheel);time.sleep(.5);self.labels('06-zoom-'+str(index),allow_empty=index==1)
  self.checked('Screen labels remain compact, non-overlapping and within the actual camera viewport across zoom levels')
  transitions=self.evidence.get('readiness_transitions',[])
  assert {'ready','spent','recovering','damaged'}<={e['expected'] for e in transitions},'Readiness scenario missed a condition'
  self.checked('Damaged camps show ready then spent; newly played Prospector shows recovering; Civil War Veteran shows not ready without losing damage colour')
 def run(self):
  try:
   self.boot();self.uniform_formation('00-uniform-empty-formation');self.damaged_camps();self.dense_placement()
   layouts=self.evidence['formation_layouts']
   cards=[c for layout in layouts for c in layout['cards']]
   assert any(c['destroyed'] for c in cards) and any(c['type']=='person' for c in cards)
   assert any(c['damage'] and not c['destroyed'] for c in cards)
   assert any(len(layout['cards'])<9 for layout in layouts)
   self.checked('All nine formation slots have equal width and height with aligned rows on YOUR and ENEMY tabs, including people, camps, ruins, damaged cards and empty spaces')
   assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
   r=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets);write_json(self.folder/'result.json',r);return r
  except Exception as e:
   write_json(self.folder/'result.json',dict(ok=False,failure=str(e),checks=self.checks,last_reports=self.reports));raise
  finally:
   stop_owned_process_groups(list(self.processes.values()))
   for stream in self.streams:stream.close()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
 p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080),(3133,1423)])
 p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=340);p.add_argument('--port',type=int,default=19941)
 p.add_argument('--timeout',type=float,default=1300);p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240);p.add_argument('--output',type=Path)
 args=p.parse_args();out=args.output or create_native_run_directory('oldwest-frontline-');out.mkdir(parents=True,exist_ok=True);r=dict(ok=False,results=[])
 try:
  for i,size in enumerate(args.resolutions):r['results'].append(FrontlineScenario(args,out,size,i).run())
  r['ok']=True
 finally:write_json(out/'result.json',r)
if __name__=='__main__':main()
