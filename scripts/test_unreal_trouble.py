"""Check sourced Trouble miniatures in a real, legally replayed native match."""
import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path

from test_unreal_event_queue import QueueScenario
from test_unreal_action_showcase import capture_subject,phase_of,signature
from test_unreal_interactions import EDITOR,ROOT,center,write_json

ASSETS={
    'hard_winter':('trouble-hard-winter','SM_Trouble_HardWinter','Landscapes',24),
    'box_canyon':('trouble-box-canyon','SM_Trouble_BoxCanyon','Landscapes',6),
    'prairie_fire':('trouble-prairie-fire','SM_Trouble_PrairieFire','Landscapes',16),
    'cholera':('trouble-cholera','SM_Trouble_Quarantine','Objects',5),
    'poker_night':('trouble-poker-night','SM_Trouble_PokerNight','Objects',4),
    'cannonade':('trouble-cannonade','SM_Trouble_Cannonade','Schemes',7),
    'ambush':('trouble-ambush','SM_Trouble_Ambush','Schemes',3),
    'gold_rush':('trouble-gold-rush','SM_Trouble_GoldRush','Schemes',3),
    'run_out_of_town':('trouble-run-out-of-town','SM_Trouble_DynamiteCrate','Schemes',5),
    'curfew':('trouble-curfew','SM_Trouble_Curfew','Schemes',1),
}

# Authored Blender-space centimetres; FBX's handedness conversion reverses Y.
# Compare to the actual imported component transform, including its owner yaw.
PROP_ANCHORS={'cannonade':((0,-87.2,98),18),'ambush':((79.85,-45.77,83),18),
              'curfew':((0,18,216),1)}


def prop_point(part,source):
    v=[source[0]*part['scale'][0],-source[1]*part['scale'][1],source[2]*part['scale'][2]]
    q=part['quaternion_xyzw'];axis=q[:3]
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    t=[2*x for x in cross(axis,v)];u=cross(axis,t)
    return [p+x+q[3]*y+z for p,x,y,z in zip(part['location'],v,t,u)]


class TroubleScenario(QueueScenario):
    def __init__(self,*args):
        super().__init__(*args);self.trouble_samples=[];self.notes={};self.landscape_effects={}
        self.illness_samples=0;self.illness_crew={}
        self.departure_samples={};self.expected_departures={}
        context=None
        for journal in self.plan['journal']:
            for event in journal.get('public_events',[]):
                if event['type'] in ('turn_start','junk','ability'):context=None
                elif event['type']=='event_resolve':context=event
                elif event['type']=='destroy' and context and context['detail']=='Run Out of Town':
                    self.expected_departures[event['sequence']]=event['target']
        self.build['trouble_harness']=signature(__file__);write_json(self.folder/'build.json',self.build)

    def click(self,position):
        self.event('move',position);self.event('down',position);self.event('up',position)

    def capture_tooltips(self):
        self.wait('Trouble shader compilation',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)
        before=[copy.deepcopy(self.snapshot(p)) for p in ('a','b')]
        assert self.snapshot()['seat']==1
        for identity,card in self.plan['targets'].items():
            self.command('a','inspect',card=int(identity))
            self.wait('Trouble selected',lambda:self.hud()['inspected_card']==int(identity))
            def link():
                return next((b for b in self.hud()['status_buttons'] if b['id']=='asset_history' and b['allocated_size'][0]>1),None)
            self.wait('Trouble history link',link)
            assert not self.hud()['asset_history']['open']
            self.click(center(link()));self.wait('Trouble history opened',lambda:self.hud()['asset_history'].get('open'))
            note=self.hud()['asset_history'];assert len(note['body'].splitlines())==3
            assert note['key']==ASSETS[card][0]
            self.notes[card]=note;self.capture(card+'-history')
            for phase in ('down','up'):self.command('a','ui_key',key='Escape',phase=phase,preserve_focus=True)
            self.wait('Trouble history closed',lambda:not self.hud()['asset_history'].get('open'))
        # Frame the ordinary own-hand staging with real mouse camera controls.
        width,height=self.hud_dimensions();viewport=self.hud()['viewport_size'];spot=(width*.53,height*.34)
        for _ in range(3):
            c=self.camera_state();delta=[-1040-c['focus'][0],180-c['focus'][1]];yaw=math.radians(c['yaw'])
            right,forward=(-math.sin(yaw),math.cos(yaw)),(-math.cos(yaw),-math.sin(yaw))
            x=-sum(a*b for a,b in zip(delta,right))/(c['distance']*.0012)
            y=sum(a*b for a,b in zip(delta,forward))/(c['distance']*.0012)
            self.event('down',spot,button='middle');self.event('move',(spot[0]+x*width/viewport[0],spot[1]+y*height/viewport[1]),button='middle');self.event('up',button='middle')
        self.event('wheel',spot,wheel=math.log(1900/self.camera_state()['distance'])/math.log(.88))
        time.sleep(.8);self.capture('trouble-own-hand-close')
        assert [self.snapshot(p) for p in ('a','b')]==before,'History/camera changed authoritative views'
        self.reset_camera()

    def resolution_render_ready(self,state,card):
        assert state.get('hud',{}).get('portraits',{}).get('compilation',{}).get('ready'),(card,'shaders still compiling during resolution')
        return True

    def observe(self,state):
        super().observe(state)
        cinematic=state.get('cinematic',{})
        if cinematic.get('busy') and cinematic.get('sequence') in self.expected_departures:
            sequence=cinematic['sequence'];target=self.expected_departures[sequence]
            assert cinematic['kind']=='destroy' and cinematic['target']==target
            assert cinematic.get('departure') and not cinematic.get('action_effects')
            assert cinematic.get('caption','').endswith(' is run out of town')
            unit=next(u for u in cinematic['units'] if u['id']==target)
            assert not unit['ragdoll'] and not unit['dead']
            assert unit['travelling'] or unit['hidden']
            if unit['travelling']:assert 'Walk' in unit['active_clip']
            self.departure_samples.setdefault(sequence,[]).append(dict(location=unit['location'],hidden=unit['hidden'],travelling=unit['travelling']))
        if (cinematic.get('kind') in ('damage','destroy') and
                self.plan['targets'].get(str(cinematic.get('source')))=='cholera'):
            assert not cinematic.get('action_effects'),'Cholera emitted weapon or impact geometry'
            self.illness_samples+=1
            if cinematic.get('impact_resolved'):
                for unit in cinematic.get('units',[]):
                    if unit.get('id') in self.plan.get('staged_crew',{}).values() and unit.get('damage')==1:
                        joints=unit['injury_joints']
                        assert max(joints['LeftLeg'][2],joints['RightLeg'][2])<30,(unit['id'],joints)
                        assert 25<joints['Hips'][2]<85,(unit['id'],joints)
                        self.illness_crew[unit['id']]=dict(side=unit['side'],damage=unit['damage'],injury_joints=joints)
        if cinematic.get('kind')=='event_resolve':
            card=self.plan['targets'].get(str(cinematic.get('source')))
            expected=ASSETS[card][3] if card in ASSETS else None
            effects=cinematic.get('action_effects',[])
            if expected and effects and self.resolution_render_ready(state,card):
                assert len(effects)==expected,(card,len(effects),expected)
                assert all(e['collision_enabled']==0 for e in effects)
                self.landscape_effects[card]=dict(count=len(effects),noncolliding=True)
                if card in PROP_ANCHORS:
                    unit=next(u for u in cinematic['units'] if u['id']==cinematic['source'])
                    point,tolerance=PROP_ANCHORS[card]
                    anchor=prop_point(unit['event_equipment'][0],point)
                    distance=math.dist(anchor,effects[0]['location'])
                    assert distance<tolerance,(card,'effect detached from prop',distance)
                    self.landscape_effects[card]['anchor_verified']=True
        for unit in state.get('cinematic',{}).get('units',[]):
            card=unit.get('card_id')
            expected=ASSETS[card][1] if card in ASSETS else None
            if not expected or unit.get('hidden'):continue
            equipment=[p for p in unit.get('event_equipment',[]) if p['visible']]
            assert len(equipment)==1 and expected in equipment[0]['mesh'],(card,equipment)
            assert equipment[0]['collision_enabled']==0 and not equipment[0]['wheel']
            assert all('/Western/Trouble/'+ASSETS[card][2]+'/Materials/' in m for m in equipment[0]['materials'])
            self.trouble_samples.append(dict(card=card,kind=state['cinematic'].get('kind'),equipment=equipment))

    def capture_phase(self,state):
        cinematic=state.get('cinematic',{})
        if cinematic.get('kind')!='event_resolve':return super().capture_phase(state)
        # Generic showcase grouping merges all event cards. Retain an actual
        # painted resolution capture for each of these distinct miniatures.
        phase=phase_of(cinematic);prior=set(self.valid_captures);subjects=set(self.valid_subject_captures)
        self.valid_captures.discard(('event_resolve',phase))
        self.valid_subject_captures.discard(('event_resolve',*capture_subject(cinematic),phase))
        try:super().capture_phase(state)
        finally:self.valid_captures.update(prior);self.valid_subject_captures.update(subjects)

    def run(self):
        try:return super().run()
        finally:
            if hasattr(self,'trouble_samples'):
                report=json.loads((self.folder/'result.json').read_text())
                seen={s['card'] for s in self.trouble_samples}
                report['trouble_assets']={c:sum(s['card']==c for s in self.trouble_samples) for c in seen}
                report['trouble_history']=self.notes
                report['landscape_resolution_effects']=self.landscape_effects
                report['illness_wound_samples']=self.illness_samples
                report['illness_wounded_crew']=self.illness_crew
                resolutions={e['sequence']:self.plan['targets'].get(str(e.get('source'))) for j in self.plan['journal']
                             for e in j.get('public_events',[]) if e['type']=='event_resolve'}
                captured={resolutions[c['sequence']] for c in self.capture_records if c['sequence'] in resolutions
                          and c['actual_phase_bracket_valid'] and c['requested_phase'] in ('impact','after-impact')}
                report['landscape_resolution_captures']=sorted(captured)
                departures=[]
                for sequence,target in self.expected_departures.items():
                    samples=self.departure_samples.get(sequence,[])
                    motion=max((math.dist(a['location'],b['location']) for a in samples for b in samples),default=0)
                    shots=[c for c in self.capture_records if c['sequence']==sequence and c['actual_phase_bracket_valid']]
                    completed=[c for c in self.completions if c['sequence']==sequence]
                    public_destroy=any(e['sequence']==sequence and e['type']=='destroy' and e['target']==target for e in self.logged_events)
                    passed=motion>100 and len(shots)>=2 and bool(completed) and public_destroy and all(not c['waited_for_settling'] for c in completed)
                    departures.append(dict(sequence=sequence,target=target,samples=len(samples),movement_cm=motion,valid_captures=shots,
                        public_destroy_preserved=public_destroy,passed=passed))
                report['departures']=departures
                write_json(self.folder/'departure-samples.json',self.departure_samples)
                targets=set(self.plan['targets'].values())
                report['ok']=report['ok'] and targets<=seen and captured==targets and set(self.notes)==targets and set(self.landscape_effects)==targets and all(d['passed'] for d in departures)
                if self.plan.get('staged_crew') and 'cholera' in targets:
                    report['ok']=report['ok'] and self.illness_samples>0 and set(self.illness_crew)==set(self.plan['staged_crew'].values())
                write_json(self.folder/'trouble-model-samples.json',self.trouble_samples)
                write_json(self.folder/'result.json',report)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=ROOT/'art/western/trouble/landscapes-v002/gameplay-plan.json')
    p.add_argument('--package-dir',type=Path,help='Test a cooked package through the normal launcher')
    args=p.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor=EDITOR;args.port=19999;args.timeout=450;args.seed=plan['seed'];args.ruleset=plan['ruleset']
    args.max_actions=len(plan['journal'])-2;args.settle=0;args.prefer_camp=[];args.require_kind=['event_play','event_resolve']
    args.extra_render_commands=[];args.profile_renderer=False;args.require_fuse=False
    args.scenario_config=dict(name='trouble-props',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    TroubleScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());assert result['ok'],result.get('issues')
    write_json(args.output/'result.json',result);print('TROUBLE_NATIVE_REVIEW',result['ok'],result['trouble_assets'])


if __name__=='__main__':main()
