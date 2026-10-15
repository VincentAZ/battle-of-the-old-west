#!/usr/bin/env python3
"""Compare shadow casters in one real match, restoring flags after each probe.

Diagnostic screenshots are explicitly marked as such and cannot establish
normal gameplay quality. Only legal actions prepare the match; no rules state
is changed by the local shadow probes. Saves no map or asset.
"""
import argparse
import hashlib
import time
from pathlib import Path
from test_unreal_interactions import InteractionScenario, ROOT, EDITOR, resolution, write_json, center
from native_launch import create_native_run_directory, stop_owned_process_groups

class ShadowScenario(InteractionScenario):
    def probe(self, category, label):
        before = self.snapshot()['view']['revision']
        self.command('a','shadow_probe',category=category)
        self.wait('shadow probe acknowledged',lambda:self.read().get('shadow_probe',{}).get('category')==category)
        # Allow VSM invalidation/recapture and temporal shading to converge.
        frame=self.read()['hud']['paint']['last_frame']
        self.wait('sixty actual painted frames after caster change',
                  lambda:self.read()['hud']['paint']['last_frame']>=frame+60,45)
        self.capture(label)
        assert self.snapshot()['view']['revision']==before, 'Probe changed rules state'
        report=self.read()['shadow_probe']
        assert category=='restore' or len(report['disabled'])>0,category
        self.evidence[label]=report

    def run(self):
        maps=ROOT/'game/OldWest/Content/Maps/WaterDepotV2.umap'
        before=hashlib.sha256(maps.read_bytes()).hexdigest()
        try:
            self.boot()
            # Use real panel controls to expose more of the ground.
            for panel_id in ('crew','actions','hand'):
                panel=next(p for p in self.hud()['dock_panels'] if p['id']==panel_id)
                if panel['visible'] and not panel['collapsed']:
                    self.event('down',center(panel['collapse_button']))
                    self.event('up')
                    self.wait('panel folded',lambda:next(p for p in self.hud()['dock_panels'] if p['id']==panel_id)['collapsed'])
            for category in ('restore','portraits','restore','terrain','restore','units','restore','world','restore','all','restore'):
                self.probe(category,f'{len(self.evidence):02d}-{category}')
            assert hashlib.sha256(maps.read_bytes()).hexdigest()==before
            result={'status':'captured_manual_attribution_required','map_unchanged_sha256':before,
                    'evidence':self.evidence,'screenshots':self.captures,
                    'limitation':'Caster-disabled images are diagnosis, not accepted game lighting.'}
            write_json(self.folder/'result.json',result)
        except Exception as error:
            write_json(self.folder/'result.json',{'status':'failed','failure':str(error),
                       'evidence':self.evidence,'screenshots':self.captures})
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor',type=Path,default=EDITOR)
    parser.add_argument('--package-dir',type=Path)
    parser.add_argument('--resolution',type=resolution,default=(1280,720))
    parser.add_argument('--ruleset',default='boomtown')
    parser.add_argument('--seed',type=int,default=2623)
    parser.add_argument('--port',type=int,default=19939)
    parser.add_argument('--timeout',type=float,default=450)
    parser.add_argument('--settle',type=float,default=.5)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output=args.output.resolve() if args.output else create_native_run_directory('oldwest-shadow-isolation-')
    output.mkdir(parents=True,exist_ok=True)
    print('Shadow isolation evidence: '+str(output),flush=True)
    ShadowScenario(args,output,args.resolution,0).run()

if __name__=='__main__':main()
