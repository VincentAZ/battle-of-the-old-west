#!/usr/bin/env python3
"""Reuse the Raider's legal two-peer lifecycle regression with herd assertions."""
import argparse,json,time,hashlib
from pathlib import Path
from test_unreal_raiders_vehicle import VehicleScenario
from test_unreal_interactions import EDITOR,center,resolution,write_json

class StampedeScenario(VehicleScenario):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.runtime.package_root:
            root=self.runtime.package_root
            self.evidence['packaged_inputs_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'OldWest/Binaries/Linux/OldWestGame',root/'package-manifest.json')}

    def validate(self,identity):
        u=self.vehicle(identity)
        assert u and u['event_token'] and u['raider'] and not u['body_visible'] and not u['weapon_visible']
        herd=u['stampede'];assert herd['animal_count']==3 and len(herd['animals'])==3
        assert u['event_equipment']==[] and u['event_wheel_radius_cm']==0 and u['turret_yaw']==0
        assert u['faces_opponent']
        for animal in herd['animals']:
            assert '/Game/Art/Western/StampedeStudy/SK_Longhorn' in animal['mesh']
            assert animal['visible'] and animal['collision']==0 and animal['root_drift_cm']<.01
            assert abs(animal['scale']-.72)<.001
        old=[a['seconds'] for a in herd['animals']]
        assert all(abs(a-b)>.05 for i,a in enumerate(old) for b in old[i+1:]),old
        current=self.wait('live idle herd',lambda:(v if (v:=self.vehicle(identity)) and not v['stampede']['running'] and all(a['clip']=='A_Longhorn_Idle' for a in v['stampede']['animals']) and abs(v['stampede']['animals'][0]['seconds']-old[0])>.05 else None),10)
        assert all(a['root_drift_cm']<.01 for a in current['stampede']['animals'])
        self.checked(f"Seat {u['side']}: three collision-free longhorns, staggered idle, fixed roots, correct heading, no truck or turret")

    def observe(self,identity,kind):
        samples=[];end=time.monotonic()+25
        while time.monotonic()<end:
            report=self.read();unit=self.vehicle(identity)
            if unit:samples.append(dict(kind=report['cinematic'].get('kind'),unit=unit))
            if not report['cinematic']['busy'] and len(samples)>2:break
            if getattr(self.args,'capture_gameplay',False) and report['cinematic'].get('kind') in ('raid_launch','event_advance','stampede_charge') and len(self.evidence.get('motion',[]))<3:
                frames=self.evidence.setdefault('capture_frames',[])
                path=self.folder/f"gameplay-{len(frames):04d}.png"
                self.command('a','screenshot',filename=str(path))
                frames.append(dict(path=str(path),seconds=time.monotonic(),kind=kind))
            time.sleep(.04)
        assert samples,'Herd absent throughout presentation'
        self.evidence.setdefault('motion',[]).append(dict(kind=kind,samples=samples))
        moving=[s['unit']['stampede'] for s in samples if s['unit']['stampede']['running']]
        assert len(moving)>=2,f'{kind}: no running herd observed'
        assert all(h['animal_count']==3 and all(a['clip']=='A_Longhorn_Run' and a['root_drift_cm']<.01 for a in h['animals']) for h in moving)
        assert max(h['travel_cm'] for h in moving)>5
        if kind=='authoritative-charge':
            assert any(s['kind']=='stampede_charge' for s in samples), 'Missing charge after authoritative hit'
            self.checked('Authoritative chosen holding triggers herd charge, followed by damage and removal')
        self.wait('cinematics finish',lambda:not self.read()['cinematic']['busy'],40)

    def launch_and_resolve(self,name):
        candidate=self.find_raid(name);self.settle_presentation();seat=self.snapshot(name)['seat']
        self.submit(name,candidate)
        identity=next(c['id'] for c in self.snapshot(name)['view']['players'][seat]['queue'] if c and c.get('card_id')=='stampede')
        self.observe(identity,'launch');self.validate(identity)
        self.frame_raiders(identity)
        target=self.wait('herd selection bounds',lambda:next((t for t in self.hud()['world_hover_targets'] if t['id']==identity and t['pick']==identity),None))
        self.event('move',target['screen'])
        self.wait('Stampede hover',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==identity)
        assert 'STAMPEDE' in self.hud()['card_hover']['text'].upper() and 'STAMPEDE' not in self.hud()['card_hover']['text'].upper()
        self.capture(f'{name}-herd-selection')
        self.event('move',(10,100))
        self.checked('Actual herd selection bounds expose a Stampede hover label')
        self.capture_driver_side(identity, f'{name}-herd-close')
        self.capture(f'{name}-herd-tactical')
        self.reset_camera()
        # Launch is delay2. An owner's next start moves into slot1; resolution
        # waits for the following start and the defender chooses the camp.
        other='b' if name=='a' else 'a'
        self.pass_turn(name);self.settle_presentation();self.pass_turn(other)
        self.observe(identity,'advance');self.validate(identity)
        assert self.snapshot()['view']['players'][seat]['queue'][0]['id']==identity
        self.pass_turn(name);self.settle_presentation();self.pass_turn(other)
        self.wait('defender camp choice',lambda:self.snapshot(other)['view']['choice'] and self.snapshot(other)['view']['choice']['player']==self.snapshot(other)['seat'])
        self.wait('event scene completes',lambda:not self.read()['cinematic']['busy'],40)
        waiting=self.vehicle(identity)
        assert waiting and not waiting['stampede']['running'], 'Herd must wait for authoritative defender choice'
        position=waiting['location'];time.sleep(.4)
        assert self.vehicle(identity)['location']==position, 'Herd moved toward a holding before the choice'
        self.checked('Herd remains idle at the queue while defender choice is pending')
        if other=='a':
            s=self.snapshot();assert 'ignores protection' in s['view']['choice']['help']
            assert all('target_detail' in a and 'CAMP' in a['target_detail'] for a in s['actions'])
            damaged=next((a for a in s['actions'] if 'DAMAGED · This hit destroys' in a['target_detail']),None)
            assert damaged,'Missing lethal damaged-camp description'
            self.capture('defender-damaged-camp-choice')
            action=damaged
            if not self.hud().get('battle_plan_open'):
                self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battle_plan')))
            self.wait('response buttons arranged',lambda:all(e['allocated_size'][0]>1 for e in self.hud()['master_actions']))
            widget=next(e for e in self.hud()['master_actions'] if json.loads(e['id'])==action['command'])
            self.click(center(widget));self.wait('real pointer accepts camp choice',lambda:self.agree() and self.snapshot()['view']['revision']>s['view']['revision'])
            self.checked('Rendered defender sees damaged camp / lethal hit text and resolves via real Slate click')
        else:self.submit(other,self.snapshot(other)['actions'][0])
        self.observe(identity,'authoritative-charge')
        self.settle_presentation()
        assert all(not c or c['id']!=identity for c in self.snapshot()['view']['players'][seat]['queue'])
        assert self.vehicle(identity) is None,'Resolved herd remains in queue'
        self.checked(f'Seat {seat}: launch, run to slot1, defender choice, resolution and removal')

    def capture(self,label):
        return super().capture(label.replace('truck','herd').replace('driver-turbo','herd'))

    def capture_driver_side(self,identity,label):
        super().capture_driver_side(identity,label.replace('driver-turbo','stampede'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--seed',type=int,default=1);p.add_argument('--port',type=int,default=20129);p.add_argument('--ruleset',default='boomtown');p.add_argument('--timeout',type=float,default=1200);p.add_argument('--settle',type=float,default=.5)
    p.add_argument('--capture-gameplay',action='store_true')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True);results=[]
    try:
        for index,size in enumerate(args.resolutions):results.append(StampedeScenario(args,args.output,size,index).run())
    finally:write_json(args.output/'result.json',dict(ok=len(results)==len(args.resolutions),results=results))
