#!/usr/bin/env python3
"""Native pointer verification of movable field info and expanded camera controls."""
import argparse
import copy
import time
from pathlib import Path
from test_unreal_interactions import InteractionScenario, EDITOR, center, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class FieldLayoutScenario(InteractionScenario):
    def click(self, point):
        self.event("move",point);self.event("down",point);self.event("up")
    def capture(self,label):
        if label=="01-camp-selection":time.sleep(4)
        return super().capture(label)
    def dock(self, key):
        return next(p for p in self.hud()['dock_panels'] if p['id']==key)
    def gesture(self, point, delta):
        self.event('move',point);self.event('down',point)
        self.event('move',tuple(point[i]+delta[i] for i in (0,1)));self.event('up')
        time.sleep(.4)
    def run(self):
        try:
            self.boot()
            before=[copy.deepcopy(self.snapshot(n)['view']) for n in ('a','b')]
            self.capture('02-default-info')
            for key,delta in [('field_you',(180,80)),('field_enemy',(-220,100))]:
                p=copy.deepcopy(self.dock(key))
                self.gesture(center(p['header']),delta)
                moved=copy.deepcopy(self.dock(key))
                assert moved['position']!=p['position'],(key,p,moved)
                self.gesture(center(moved['resize_grip']),(-60,90))
                resized=copy.deepcopy(self.dock(key))
                assert resized['expanded_size']!=moved['expanded_size']
                self.evidence[key]=dict(before=p,moved=moved,resized=resized)
            self.capture('03-moved-resized-info')
            # Trigger a rebuild and ensure the panel state survives.
            button=next(b for b in self.hud()['status_buttons'] if b['id']=='own_stats')
            self.click(center(button));time.sleep(.4)
            for key in ('field_you','field_enemy'):
                assert self.dock(key)['position']==self.evidence[key]['resized']['position']
                assert self.dock(key)['expanded_size']==self.evidence[key]['resized']['expanded_size']
            self.click(center(next(b for b in self.hud()['status_buttons'] if b['id']=='own_stats')));time.sleep(.4)
            self.checked('Both info panels move and resize through real pointer gestures and retain layout across rebuilds')
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='reset_panels')));time.sleep(.4)
            initial=self.camera_state()
            mapping={'zoom_in':'distance','zoom_out':'distance','pan_left':'focus','pan_right':'focus','pan_up':'focus','pan_down':'focus','orbit_left':'yaw','orbit_right':'yaw','tilt_up':'pitch','tilt_down':'pitch'}
            for key,field in mapping.items():
                prior=copy.deepcopy(self.camera_state())
                self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']==key)))
                self.wait('camera button '+key,lambda:self.camera_state()[field]!=prior[field])
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='reset_view')))
            self.wait('reset camera',lambda:self.camera_identity(self.camera_state())==self.camera_identity(initial))
            spot=(self.hud_dimensions()[0]*.52,self.hud_dimensions()[1]*.4)
            for wheel,endpoint,label in [(100,'minimum_distance','04-close-camera'),(-100,'maximum_distance','05-far-camera')]:
                for _ in range(7):self.event('wheel',spot,wheel=wheel)
                self.wait('camera endpoint',lambda:abs(self.camera_state()['distance']-self.camera_state()[endpoint])<.1)
                self.capture(label)
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='reset_view')));time.sleep(.4)
            self.test_camera()
            assert [self.snapshot(n)['view'] for n in ('a','b')]==before
            self.checked('Ten visible camera controls, close/far limits, reset and mouse gestures preserve authoritative game state')
            result=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
            write_json(self.folder/'result.json',result);return result
        except Exception as error:
            write_json(self.folder/'result.json',dict(ok=False,error=str(error),checks=self.checks,last_reports=self.reports));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=94)
    p.add_argument('--port',type=int,default=20881);p.add_argument('--timeout',type=float,default=400)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,size in enumerate(args.resolutions):results.append(FieldLayoutScenario(args,args.output,size,i).run())
    write_json(args.output/'result.json',dict(ok=True,results=results))
if __name__=='__main__':main()
