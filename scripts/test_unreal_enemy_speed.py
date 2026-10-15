#!/usr/bin/env python3
"""Exercise the real AI-speed slider and persist it across a native restart."""
import argparse
import copy
import shutil
import time
from pathlib import Path
from test_unreal_singleplayer import SoloScenario, EDITOR, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class SpeedScenario(SoloScenario):
    def pointer(self, phase, p):
        self.command('ui_pointer',phase=phase,x=p[0],y=p[1],button='left',wheel=0)

    def run(self):
        try:
            self.launch()
            self.wait('menu',lambda:self.snapshot().get('hosted') is False,90)
            self.command('pause')
            assert self.read()['hud']['enemy_speed']==.5
            self.command('single_player',ruleset=self.ruleset,difficulty=self.difficulty)
            self.wait('human draft',lambda:bool(self.snapshot().get('actions')))
            s=self.snapshot()
            self.command('submit',command=s['actions'][0]['command'],revision=s['view']['revision'],match_id=s['match_id'])
            self.wait('human turn',lambda:self.snapshot().get('view',{}).get('status')=='actions' and self.snapshot()['view']['active_player']==0 and not self.read().get('cinematic',{}).get('busy'),90)
            time.sleep(.5)
            before=copy.deepcopy(self.snapshot()['view'])
            for value in (.25,2.):
                slider=self.wait('slider layout',lambda:next((b for b in self.read()['hud']['status_buttons'] if b['id']=='enemy_speed' and b['allocated_size'][0]>1),None))
                p=[slider['min'][0]+1 if value==.25 else slider['max'][0]-1,(slider['min'][1]+slider['max'][1])/2]
                for phase in ('move','down','up'):self.pointer(phase,p)
                self.wait('speed changes through real pointer',lambda:abs(self.read()['hud']['enemy_speed']-value)<.001)
                assert self.snapshot()['view']==before,'Slider altered game state'
                self.capture(f'speed-{value}')
            self.checked('Default 0.5x and real slider endpoints 0.25x/2x; no rule-state changes')
            self.expected_exit=True
            self.command('quit',acknowledge=False)
            self.wait('first process exits',lambda:self.processes[-1].poll() is not None,30)
            assert self.processes[-1].returncode==0
            for stream in self.streams:stream.close()
            self.streams=[]
            for name in ('game.log','game-console.log','game.json'):
                shutil.copy2(self.folder/name,self.folder/('before-restart-'+name))
            for name in ('game.control.json','game.json'):(self.folder/name).unlink(missing_ok=True)
            self.sequence=0;self.last_report={};self.expected_exit=False;self.processes=[]
            self.launch()
            self.wait('restarted menu',lambda:self.snapshot().get('hosted') is False,90)
            assert self.read()['hud']['enemy_speed']==2.,'Saved slider value not restored'
            self.checked('Selected enemy speed survives a fresh native process')
            self.expected_exit=True
            self.command('quit',acknowledge=False)
            self.wait('second process exits',lambda:self.processes[-1].poll() is not None,30)
            assert self.processes[-1].returncode==0
            result=dict(ok=True,checks=self.checks,screenshots=self.captures,runtime_assets=assert_runtime_assets([self.folder/'game.log',self.folder/'before-restart-game.log']))
            write_json(self.folder/'result.json',result)
            return result
        except Exception as e:
            write_json(self.folder/'result.json',dict(ok=False,error=str(e),checks=self.checks))
            raise
        finally:
            stop_owned_process_groups(self.processes)
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR)
    p.add_argument('--package-dir',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.normal_pacing_only=True;args.timeout=300;args.settle=.4
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    SpeedScenario(args,args.output,'base_2024','normal',20260912,(1280,720)).run()
if __name__=='__main__':main()
