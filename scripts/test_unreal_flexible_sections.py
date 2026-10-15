#!/usr/bin/env python3
"""Native draggable accordion viewports, persistence and readable card layout."""
import argparse,copy,json,time
from pathlib import Path
from test_unreal_frontline import FrontlineScenario
from test_unreal_interactions import EDITOR,center,resolution,write_json,field_cards
from native_launch import create_native_run_directory,stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class FlexibleScenario(FrontlineScenario):
 def boot(self):
  super().boot()
  if not self.hud().get('battle_plan_open',True):
   self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='battle_plan')))
   self.wait('Battle Plan explicitly opened',lambda:self.hud()['battle_plan_open'])
   self.stable_layout()
 def stable_layout(self):
  last_frame=-1;last_geometry=None;stable=0
  def settled():
   nonlocal last_frame,last_geometry,stable
   h=self.hud();frame=h.get('paint',{}).get('last_frame',0)
   if frame==last_frame:return False
   geometry=json.dumps([(s['id'],s['min'],s['max'],s['collapsed']) for s in h.get('battle_sections',[])])
   stable=stable+1 if geometry==last_geometry else 0
   last_geometry=geometry;last_frame=frame
   return stable>=2
  self.wait('three painted frames of stable layout',settled)

 def body(self,key):
  return next((b for b in self.hud().get('section_bodies',[]) if b['id']==key),None)
 def outer(self):return self.hud()['battle_scroll'][0]
 def outer_wheel(self,delta):
  area=self.outer();self.event('wheel',(area['max'][0]-4,center(area)[1]),wheel=delta);time.sleep(.8)
  self.stable_layout()
 def fold(self,key,closed):
  self.stable_layout()
  for _ in range(30):
   e=self.section(key)
   if e and (key=='your.actions' or self.inside(e,self.outer())):break
   self.outer_wheel(3 if e and e['min'][1]<self.outer()['min'][1] else -3)
  assert e and self.inside(e),f'Unreachable header {key}'
  if e['collapsed']!=closed:
   self.click(center(e));self.wait('fold '+key,lambda:self.section(key) and self.section(key)['collapsed']==closed)
  self.stable_layout()
 def isolate(self,key,side='your'):
  expected=self.snapshot()['seat'] if side=='your' else 1-self.snapshot()['seat']
  if self.hud()['inspector_side']!=expected or self.hud()['history_open']:self.tab(side)
  self.outer_wheel(40)
  for suffix in ('water','hand','formation','events','details'):
   name=side+'.'+suffix
   if self.section(name):self.fold(name,name!=key and not ('.column' in key and suffix=='formation'))
  if self.section('your.actions'):self.fold('your.actions',key!='your.actions')
  self.outer_wheel(40)
  if '.column' in key:
   for i in range(1,4):self.fold(side+'.column'+str(i),False)
  self.wait('body visible '+key,lambda:self.body(key) and self.body(key)['viewport'])
  self.stable_layout()
 def capture(self,label):
  self.event('move',(100,40));time.sleep(.3)
  super().capture(label)
 def resize(self,key,delta):
  before=copy.deepcopy(self.body(key));grip=before['grip'];assert grip
  if key=='target.rules':
   for _ in range(16):
    area=self.body('your.actions')['viewport']
    if self.inside(grip,area):break
    self.event('wheel',center(area),wheel=-3);time.sleep(.2);before=copy.deepcopy(self.body(key));grip=before['grip']
   assert self.inside(grip,area),'Target explanation border is clipped'
  elif not self.inside(grip,self.outer()) and key!='your.actions':
   self.outer_wheel(-3);before=copy.deepcopy(self.body(key));grip=before['grip']
  assert self.inside(grip),('clipped resize grip',key,grip)
  baseline=[copy.deepcopy(self.snapshot(n)['view']) for n in ('a','b')]
  camera=self.camera_identity(self.camera_state())
  scale=(grip['max'][1]-grip['min'][1])/grip['allocated_size'][1]
  point=center(grip);self.event('move',point);self.event('down',point)
  self.wait('capture '+key,lambda:self.body(key)['resizing'])
  self.event('move',(point[0],point[1]+delta*scale));self.event('up')
  self.wait('resize completed '+key,lambda:not self.body(key)['resizing'] and self.body(key)['resize_count']>before['resize_count'])
  after=self.body(key)
  # Desktop cursor positions round to physical pixels (1.5 logical units at 720p).
  assert abs(after['height']-before['height']-delta)<=2,(key,before,after)
  assert [self.snapshot(n)['view'] for n in ('a','b')]==baseline
  assert self.camera_identity(self.camera_state())==camera
  self.evidence.setdefault('resizes',[]).append(dict(key=key,before=before,after=copy.deepcopy(after)))
  return after
 def key(self,key):
  for phase in ('down','up'):self.command('a','ui_key',key=key,phase=phase,preserve_focus=True)
 def check_sections(self):
  self.own_turn()
  while len(self.own_hand())<8:
   options=self.snapshot()['actions'];draw=next((a for a in options if a['command']['type']=='draw'),None)
   if draw:self.submit('a',draw)
   else:self.round()
  self.settle_presentation();self.isolate('your.hand')
  time.sleep(.5)
  initial={e['id']:e['allocated_size'] for e in self.hud()['hand_cards'] if self.inside(e,self.body('your.hand')['viewport'])}
  def fully_visible():
   a=self.body('your.hand')['viewport'];return [e['id'] for e in self.hud()['hand_cards'] if self.inside(e,a)]
  row_height=max(e['allocated_size'][1] for e in self.hud()['hand_cards'])+12
  small=fully_visible();self.resize('your.hand',row_height);large=fully_visible()
  assert len(large)>len(small),(small,large)
  time.sleep(.3)
  after={e['id']:e['allocated_size'] for e in self.hud()['hand_cards']}
  self.evidence['hand_tile_sizes']=dict(before=initial,after=after)
  assert all(after[k]==v for k,v in initial.items()),(initial,after)
  self.capture('01-expanded-wrapped-hand')
  self.resize('your.hand',-row_height)
  before=self.body('your.hand')['height'];grip=center(self.body('your.hand')['grip'])
  self.event('move',grip);self.event('down',grip);self.event('move',(grip[0],grip[1]+50))
  self.key('Escape');self.event('up');self.wait('escape cancels section resize',lambda:not self.body('your.hand')['resizing'])
  assert self.body('your.hand')['height']==before
  assert not self.body('your.hand')['mouse_captured'],'Escape must release the actual desktop cursor'
  # Clicking the grip gives it focus; arrow events retain actual Slate focus.
  self.click(center(self.body('your.hand')['grip']));self.key('Down')
  assert self.body('your.hand')['height']==before+10
  time.sleep(.3)
  self.event('move',center(self.body('your.hand')['grip']));time.sleep(.15)
  self.click(center(self.body('your.hand')['grip']))
  self.event('double',center(self.body('your.hand')['grip']));self.event('up')
  self.wait('double click resets height',lambda:self.body('your.hand')['height']==self.body('your.hand')['default_height'])
  self.checked('Hand border reveals additional wrapped rows without scaling cards; Esc cancels, arrow keys resize, and double-click restores the default')
  for side in ('your','enemy'):
   for suffix,delta in [('water',16),('hand',30),('formation',-80),('column1',-60),('column2',-40),('column3',-20),('events',30)]:
    key=side+'.'+suffix;self.isolate(key,side)
    if '.column' in key:
     # Restore parent viewport room after its independent earlier resize.
     b=self.body(side+'.formation');self.resize(side+'.formation',b['default_height']-b['height'])
    self.resize(key,delta)
    if '.column' in key:
     time.sleep(.3)
     slots=self.hud()['formation_slots'];assert len(slots)==9
     for axis in (0,1):
      sizes=[s['allocated_size'][axis] for s in slots]
      assert max(sizes)-min(sizes)<.1,('Column resizing changed card dimensions',key,axis,sizes)
     self.evidence.setdefault('resized_formation_slots',[]).append(dict(key=key,slots=slots))
  self.checked('Water, hand, formation, all three column accordions and events resize independently on both player tabs without game or camera changes')
  self.isolate('your.formation');self.command('a','inspect',card=self.camps['bunkhouse'])
  self.wait('card details',lambda:self.section('your.details'))
  self.isolate('your.details');self.resize('your.details',40)
  self.isolate('your.actions');self.resize('your.actions',60)
  self.history_tab();self.outer_wheel(40)
  self.fold('history.last',True);self.resize('history.current',60)
  self.fold('history.current',True);self.fold('history.last',False);self.resize('history.last',40)
  self.capture('02-flexible-turn-history')
  self.checked('Selected details, Actions and both rolling-history accordions have working independent resize borders')
 def persistence(self):
  self.tab('your');self.outer_wheel(40)
  ini=(self.folder/'a.settings.ini').read_text();assert '[OldWest.SectionHeights]' in ini
  before={b['id']:b['height'] for b in self.hud()['section_bodies']}
  baseline=copy.deepcopy(self.snapshot()['view'])
  process=self.processes.pop('a');stop_owned_process_groups([process])
  self.wait('disconnect observed',lambda:self.snapshot('b').get('connected')==1,30)
  self.reports.pop('a',None)
  for suffix in ('json','control.json'):(self.folder/f'a.{suffix}').unlink(missing_ok=True)
  self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
  self.wait('fresh menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
  self.command('a','join',address=f'127.0.0.1:{self.port}');self.wait('reconnected',self.agree,100)
  self.settle_presentation();self.tab('your')
  assert self.snapshot()['view']==baseline
  for key,height in before.items():
   if self.body(key):assert abs(self.body(key)['height']-height)<.01,(key,height,self.body(key))
  self.tab('enemy')
  expected=next(r['after']['height'] for r in self.evidence['resizes'] if r['key']=='enemy.water')
  assert abs(self.body('enemy.water')['height']-expected)<.01
  self.evidence['persisted_section_preferences']=ini
  self.checked('Section heights and collapse choices survive a fresh process and reconnect, with independent YOUR/ENEMY settings')
 def required_choice(self):
  self.own_turn();self.isolate('your.actions')
  b=self.body('your.actions');saved_height=self.resize('your.actions',64-b['height'])['height'];self.fold('your.actions',True)
  junk=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='punk','required Punk placement')
  self.submit('a',junk);self.settle_presentation()
  self.wait('required choice forced open',lambda:self.section('your.actions')['forced_open'] and self.body('your.actions')['viewport'])
  assert self.body('your.actions')['height']>=120
  self.resize('your.actions',30);self.capture('03-required-response-remains-usable')
  self.clear_choices();self.settle_presentation()
  assert self.section('your.actions')['collapsed'] and self.body('your.actions')['height']==saved_height
  self.checked('Required responses stay open and resizable with a usable minimum, then restore the ordinary Actions height and collapsed preference')
  self.round()
  attack=next(a for a in self.snapshot()['actions'] if a['command'].get('source')==self.camps['bunkhouse'])
  self.submit('a',attack);self.settle_presentation()
  self.wait('target explanation present',lambda:self.section('target.rules'))
  self.resize('your.actions',400-self.body('your.actions')['height'])
  for _ in range(16):
   area=self.body('your.actions')['viewport'];entry=self.section('target.rules')
   if self.inside(entry,area):break
   self.event('wheel',center(area),wheel=-3);time.sleep(.2)
  assert self.inside(entry,area)
  if entry['collapsed']:self.click(center(entry));time.sleep(.3)
  self.resize('target.rules',30);self.capture('04-resizable-target-explanation')
  self.clear_choices()
  self.checked('The target-rules explanation also resizes inside the required-response area without submitting a game choice')
 def run(self):
  try:
   self.boot();self.check_sections();self.persistence();self.required_choice()
   assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
   r=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets)
   write_json(self.folder/'result.json',r);return r
  except Exception as e:
   write_json(self.folder/'result.json',dict(ok=False,error=str(e),checks=self.checks,evidence=self.evidence,last_reports=self.reports));raise
  finally:
   stop_owned_process_groups(list(self.processes.values()))
   for stream in self.streams:stream.close()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
 p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080),(3133,1423)])
 p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=340);p.add_argument('--port',type=int,default=19961)
 p.add_argument('--timeout',type=float,default=1000);p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240);p.add_argument('--output',type=Path)
 args=p.parse_args();out=args.output or create_native_run_directory('oldwest-flexible-');out.mkdir(parents=True,exist_ok=True)
 result=dict(ok=False,results=[])
 try:
  for index,size in enumerate(args.resolutions):result['results'].append(FlexibleScenario(args,out,size,index).run())
  result['ok']=True
 finally:write_json(out/'result.json',result)
if __name__=='__main__':main()
