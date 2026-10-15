#!/usr/bin/env python3
"""Review every regional scene in native gameplay; no authoritative state injection."""
import argparse
import copy
import json
import math
import time
from pathlib import Path

from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json, center


class RegionScenario(QueueScenario):
    def capture_tooltips(self): pass

    def click(self, point):
        self.event('down',point,button='left')
        self.event('up',point,button='left')

    def run(self):
        result={'ok':False,'region':self.args.region}
        try:
            self.boot()
            self.wait('regional shader and asset finalization',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)
            time.sleep(1)
            before=[copy.deepcopy(self.snapshot(p)) for p in ('a','b')]
            state=self.read();region=state['hud']['region']
            assert region['index']==self.args.region and region['original_collider_retained']
            if self.args.region == 0:
                assert region['name'] == 'Sonoran Desert', region
                assert 'Desert' in region['surface_material'], region
            assert region['noncolliding_scenery']
            assert region['tree_count']==(0 if self.args.region==0 else 180),region
            assert region['visual_parts']==(3 if self.args.region==0 else 2 if self.args.region==2 else 0),region
            if self.args.clean_view:
                if self.hud().get('battlefield_text_visible'):
                    self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='battlefield_text')))
                    self.wait('hide battlefield labels',lambda:not self.hud()['battlefield_text_visible'])
                identifiers=[p['id'] for p in self.hud()['dock_panels'] if p['visible'] and not p['collapsed']]
                for identifier in identifiers:
                    panel=next(p for p in self.hud()['dock_panels'] if p['id']==identifier)
                    self.click(center(panel['collapse_button']))
                    self.wait('collapse scenery-review panel',lambda:any(p['id']==identifier and p['collapsed'] for p in self.hud()['dock_panels']))
                width,height=self.hud_dimensions()
                self.event('move',(width*.5,height*.18))
                time.sleep(.3)
            self.capture('01-board')
            width,height=self.hud_dimensions();spot=(width*.54,height*.35)
            self.event('wheel',spot,wheel=math.log(20000/self.camera_state()['distance'])/math.log(.88))
            self.wait('wide scenery camera',lambda:abs(self.camera_state()['distance']-20000)<100)
            time.sleep(1);self.capture('02-region-wide')
            self.event('down',spot,button='right')
            self.event('move',(spot[0]+160,spot[1]+80),button='right');self.event('up',button='right')
            time.sleep(1);self.capture('03-region-angle')
            assert [self.snapshot(p) for p in ('a','b')]==before
            assert self.hud()['region']==region,'Camera altered selected scenery'
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result.update(ok=True,scenery=region,authoritative_views_unchanged=True,runtime_assets=assets,
                          captures=self.captures,manual_visual_review='pending')
        except Exception as error:
            result['failure']=str(error);raise
        finally:
            write_json(self.folder/'result.json',result)
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--package-dir',type=Path,help='Review the cooked build through its bundled launcher')
    parser.add_argument('--regions',type=int,nargs='+',default=[0,1,2])
    parser.add_argument('--clean-view',action='store_true',help='Hide labels and collapse panels for scenery review')
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/trouble/fuse-v001/queue-gameplay-plan.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    args.editor=EDITOR;args.port=19989;args.timeout=180
    args.seed=plan['seed'];args.ruleset=plan['ruleset'];args.max_actions=0;args.settle=0
    args.prefer_camp=[];args.require_kind=[];args.extra_render_commands=[];args.profile_renderer=False
    args.scenario_config=dict(name='regional-scenery-review',policy='public_replay',target_kinds=[])
    args.output.mkdir(parents=True,exist_ok=True);results=[]
    for region in args.regions:
        current=copy.copy(args);current.region=region;current.native_extra_args=[f'-OldWestRegionReview={region}']
        out=args.output/str(region);out.mkdir()
        results.append(RegionScenario(current,out,(1600,900),region).run())
    write_json(args.output/'result.json',dict(ok=all(r['ok'] for r in results),results=results))
    print('REGIONAL_RUNTIME_CHECKS',[(r['region'],r['ok']) for r in results])


if __name__=='__main__':main()
