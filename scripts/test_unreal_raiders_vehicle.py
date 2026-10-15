#!/usr/bin/env python3
"""Exercise the Stampede vehicle using legal play on two native Linux peers."""
import argparse
import json
import math
import time
from pathlib import Path
from test_unreal_master_panel import MasterScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class VehicleScenario(MasterScenario):
    def boot(self):
        # This seed offers Army Fort to the rendered peer. Select it when present,
        # so the defender's damage chooser can show a lethal second hit.
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        from native_launch import game_net_driver_ports
        log=self.folder/'b.log'
        self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
        self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
        self.wait('menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
        self.command('a','join',address=f'127.0.0.1:{self.port}')
        self.wait('selection',self.agree,100)
        for name in ('a','b'):
            candidates=self.snapshot(name)['actions']
            pick=max(candidates,key=lambda a:100*('army_fort' in a['command']['camps'])+sum(self.defs[c]['starting_cards'] for c in a['command']['camps']))
            self.submit(name,pick)
        self.wait('actions',lambda:self.snapshot()['view']['status']=='actions')
        self.settle_presentation()

    def find_raid(self,name):
        for _ in range(180):
            s=self.snapshot(name)
            assert s['view']['status'] not in ('won','draw'),'Match ended seeking a raid'
            cards=self.own_hand(name)
            candidate=next((a for a in s['actions'] if a['command']['type']=='junk' and self.junk_kind(cards.get(a['command'].get('card'),{}))=='raid'),None)
            if candidate:return candidate
            actor=next(n for n in ('a','b') if self.snapshot(n)['actions'])
            actions=self.snapshot(actor)['actions']
            preferred=next((a for a in actions if a['command']['type']==('draw' if actor==name else 'end_turn')),None)
            self.submit(actor,preferred or next((a for a in actions if a['command']['type']=='end_turn'),actions[0]))
            self.settle_presentation()
        raise AssertionError('No raid junk found')

    def vehicle(self,identity):
        return next((u for u in self.read()['cinematic']['units'] if u['id']==identity),None)

    def observe(self,identity,kind):
        samples=[]
        end=time.monotonic()+25
        while time.monotonic()<end:
            report=self.read();unit=self.vehicle(identity)
            if unit:samples.append(dict(kind=report['cinematic'].get('kind'),unit=unit))
            if not report['cinematic']['busy'] and len(samples)>2:break
            time.sleep(.04)
        assert samples,'Vehicle was absent throughout animation'
        self.evidence.setdefault('motion',[]).append(dict(kind=kind,samples=samples))
        # Wheel phase is measured against actual longitudinal displacement,
        # including stationary reports and reverse travel.
        changing=0
        for left,right in zip(samples,samples[1:]):
            a,b=left['unit'],right['unit']
            if a['hidden'] or b['hidden']:continue
            dy=b['location'][1]-a['location'][1]
            phase=b['event_wheel_travel_cm']-a['event_wheel_travel_cm']
            assert abs(dy-phase)<.15,(kind,dy,phase)
            if abs(dy)>.2:changing+=1
        assert changing>=2,f'{kind}: no visible rolling movement sampled'
        self.wait('cinematics finish',lambda:not self.read()['cinematic']['busy'],40)

    def validate(self,identity):
        u=self.vehicle(identity)
        assert u and u['event_token'] and u['raider'] and not u['body_visible'] and not u['weapon_visible']
        assert not u['visual_mesh'] and not u.get('pose_samples')
        equipment=u['event_equipment'];wheels=[p for p in equipment if p['wheel']]
        assert len(wheels)==4 and len(equipment)==6,equipment
        assert all(p['visible'] and '/Game/Art/Vehicles/Raiders/' in p['mesh'] for p in equipment)
        materials = {material for part in equipment for material in part.get('materials', [])}
        expected = {f'/Game/Art/Vehicles/Raiders/Redesign/Materials/M_Raider_{name}.M_Raider_{name}'
                    for name in ('Body', 'Driver', 'Glass', 'Turret', 'Gatling Gunner', 'Wheel')}
        assert materials == expected, ('Redesigned truck and both crew members must be loaded', materials)
        assert u['faces_opponent'] and u['event_wheel_radius_cm']==44
        for p in wheels:assert abs(p['location'][2]-u['location'][2]-44)<.15
        old=u
        new=self.wait('fresh idle turret sample',lambda:(v if (v:=self.vehicle(identity)) and abs(v['turret_yaw']-old['turret_yaw'])>.01 else None),10)
        assert old['event_wheel_travel_cm']==new['event_wheel_travel_cm'],'Stationary wheels rolled'
        assert abs(old['turret_yaw']-new['turret_yaw'])>.01,'Turret surveillance is frozen'
        self.checked(f"Seat {u['side']}: redesigned truck, driver and gunner materials, four grounded wheels, moving turret, correct heading")

    def pass_turn(self,name):
        self.submit(name,next(a for a in self.snapshot(name)['actions'] if a['command']['type']=='end_turn'))

    def capture_driver_side(self, identity, label):
        unit = self.vehicle(identity)
        width, height = self.hud_dimensions()
        viewport = self.hud()['viewport_size']
        spot = (width * .58, height * .28)
        yaw = (-90 if unit['side'] == 0 else 90) - 65
        for _ in range(4):
            current = self.camera_state()
            delta = (yaw - current['yaw'] + 180) % 360 - 180
            pitch_delta = 18 - current['pitch']
            if abs(delta) < .1 and abs(pitch_delta) < .1:
                break
            self.event('down', spot, button='right')
            self.event('move', (spot[0] + max(-500, min(500, -delta / .22)) * width / viewport[0],
                               spot[1] + max(-500, min(500, pitch_delta / .18)) * height / viewport[1]), button='right')
            self.event('up', button='right')
        text_was_visible = self.hud().get('battlefield_text_visible', False)
        if text_was_visible:
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battlefield_text')))
        self.capture(label)
        if text_was_visible:
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id'] == 'battlefield_text')))

    def launch_and_resolve(self,name):
        candidate=self.find_raid(name);self.settle_presentation();seat=self.snapshot(name)['seat']
        self.submit(name,candidate)
        identity=next(c['id'] for c in self.snapshot(name)['view']['players'][seat]['queue'] if c and c.get('card_id')=='stampede')
        self.observe(identity,'launch');self.validate(identity)
        self.frame_raiders(identity)
        self.capture_driver_side(identity, f'{name}-driver-turbo-close')
        self.capture(f'{name}-truck-close')
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
        self.settle_presentation()
        assert all(not c or c['id']!=identity for c in self.snapshot()['view']['players'][seat]['queue'])
        assert self.vehicle(identity) is None,'Resolved truck remains in queue'
        self.checked(f'Seat {seat}: launch, roll to slot1, defender choice, resolution and removal')

    def run(self):
        try:
            self.boot();self.launch_and_resolve('a');self.launch_and_resolve('b')
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result=dict(ok=True,checks=self.checks,screenshots=self.captures,evidence=self.evidence,runtime_assets=assets)
            if self.runtime.package_root:
                result['package_directory'] = str(self.runtime.package_root)
            write_json(self.folder/'result.json',result);return result
        except Exception as e:
            write_json(self.folder/'result.json',dict(ok=False,error=str(e),checks=self.checks,evidence=self.evidence,last=self.read()));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--seed',type=int,default=1);p.add_argument('--port',type=int,default=19929);p.add_argument('--ruleset',default='boomtown');p.add_argument('--timeout',type=float,default=900);p.add_argument('--settle',type=float,default=.5)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);results=[]
    try:
        for i,size in enumerate(a.resolutions):results.append(VehicleScenario(a,a.output,size,i).run())
    finally:
        report=dict(ok=len(results)==len(a.resolutions),results=results)
        if results and results[0].get('package_directory'):
            report['package_directory']=results[0]['package_directory']
        write_json(a.output/'result.json',report)
