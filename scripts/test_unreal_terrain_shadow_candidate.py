#!/usr/bin/env python3
"""Fresh gameplay check of Nanite streaming shadow invalidation.

No caster is toggled, no terrain geometry is changed, and no renderer cache or
DDC is deleted. The experimental cvar is confined to these isolated peers.
"""
import argparse
import hashlib
from pathlib import Path
from test_unreal_interactions import InteractionScenario, ROOT, EDITOR, resolution, write_json, center
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class TerrainShadowCandidate(InteractionScenario):
    def frames(self, count=90):
        frame=self.read()['hud']['paint']['last_frame']
        self.wait('actual rendered frames',lambda:self.read()['hud']['paint']['last_frame']>=frame+count,60)

    def run(self):
        terrain=ROOT/'game/OldWest/Content/Art/WaterDepotV2'
        paths=[ROOT/'game/OldWest/Content/Maps/WaterDepotV2.umap', *terrain.rglob('*.uasset')]
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        try:
            self.boot()
            self.wait('shader and asset finalization',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)
            for panel_id in ('crew','actions','hand'):
                panel=self.wait('visible settled panel',lambda:next((p for p in self.hud()['dock_panels'] if p['id']==panel_id and p['visible']),None))
                if not panel['collapsed']:
                    self.event('down',center(panel['collapse_button']))
                    self.event('up')
                    self.wait('panel folded',lambda:next(p for p in self.hud()['dock_panels'] if p['id']==panel_id)['collapsed'])
            self.frames()
            self.capture('02-initial-field')
            self.command('a','camera')
            self.frames()
            self.capture('03-reverse-field')
            self.command('a','camera')
            self.frames(180)
            self.capture('04-returned-field')
            self.command('a','leave')
            self.wait('menu after leave',lambda:self.snapshot().get('hosted') is False)
            self.frames()
            self.capture('05-menu-after-travel')
            self.command('a','join',address=f'127.0.0.1:{self.port}')
            self.wait('same seat rejoined',self.agree,100)
            self.settle_presentation()
            self.frames()
            self.capture('06-rejoined-field')
            assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in before.items())
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result={'status':'fresh_candidate_captured_manual_visual_review_required',
                    'extra_render_commands':self.args.extra_render_commands,'protected_assets_unchanged':before,
                    'evidence':self.evidence,'screenshots':self.captures,'runtime_assets':assets,
                    'limits':['No shadow-caster toggles performed. Experimental Nanite invalidation cvar only; no production config promotion.',
                              'GPU/performance comparison remains separate from these visual captures.']}
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
    parser.add_argument('--port',type=int,default=19949)
    parser.add_argument('--timeout',type=float,default=450)
    parser.add_argument('--settle',type=float,default=.5)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    args.extra_render_commands=['r.Nanite.VSMInvalidateOnLODDelta 1']
    output=args.output.resolve() if args.output else create_native_run_directory('oldwest-terrain-shadow-candidate-')
    output.mkdir(parents=True,exist_ok=True)
    print('Terrain shadow candidate: '+str(output),flush=True)
    TerrainShadowCandidate(args,output,args.resolution,0).run()

if __name__=='__main__':main()
