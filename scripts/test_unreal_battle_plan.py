#!/usr/bin/env python3
"""Battle Plan edge/corner gestures and graphic deployment in real native play."""
import argparse
import copy
import time
from pathlib import Path
from test_unreal_flexible_sections import FlexibleScenario
from test_unreal_interactions import InteractionScenario, EDITOR, center, resolution, write_json
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class BattlePlanScenario(FlexibleScenario):
    def capture(self, label):
        if self.hud().get('deployment',{}).get('card',-1)!=-1:
            return InteractionScenario.capture(self,label)
        return super().capture(label)

    def visible_hand_widget(self, card):
        self.isolate('your.hand')
        return super().visible_hand_widget(card)

    def assert_roster(self):
        self.isolate('your.formation')
        time.sleep(.3)
        return super().assert_roster()

    def panel_edges(self):
        self.own_turn()
        self.settle_presentation()
        baseline = [copy.deepcopy(self.snapshot(n)['view']) for n in ('a', 'b')]
        camera = self.camera_identity(self.camera_state())
        p = self.panel()
        scale = p['panel']['allocated_size'][0]
        scale = (p['panel']['max'][0] - p['panel']['min'][0]) / scale
        self.drag(center(p['header']), (-520 * scale, 0))
        time.sleep(.3)
        # Shrink to create room above and below, then move away from boundaries.
        self.drag(center(self.panel()['resize_grip']), (0, -220 * scale))
        self.drag(center(self.panel()['header']), (0, 110 * scale))
        for name, axes in [('left',(-1,0)), ('right',(1,0)), ('top',(0,-1)), ('bottom',(0,1)),
                           ('top-left',(-1,-1)), ('top-right',(1,-1)), ('bottom-left',(-1,1)), ('bottom-right',(1,1))]:
            before = copy.deepcopy(self.panel())
            r = before['panel']
            pt = tuple(r['min'][i] + 3*scale if axes[i]<0 else r['max'][i]-3*scale if axes[i]>0 else center(r)[i] for i in (0,1))
            self.event('move', pt)
            self.event('down', pt)
            self.wait('capture '+name, lambda:self.panel()['operation']=='resize')
            self.event('move', tuple(pt[i]+axes[i]*24*scale for i in (0,1)))
            self.event('up')
            self.wait('finish '+name, lambda:not self.panel()['interacting'])
            after = copy.deepcopy(self.panel())
            for i in (0,1):
                assert abs(after['expanded_size'][i]-before['expanded_size'][i]-(24 if axes[i] else 0))<2, (name,before,after)
                expected = before['position'][i] - (24 if axes[i]<0 else 0)
                assert abs(after['position'][i]-expected)<2, (name,before,after)
            self.evidence.setdefault('edge_resizes',[]).append(dict(edge=name,before=before,after=after))
        before = copy.deepcopy(self.panel())
        r = before['panel'];pt=(r['min'][0]+3*scale,center(r)[1])
        self.event('move',pt);self.event('down',pt);self.event('move',(pt[0]-40*scale,pt[1]))
        self.key('Escape');self.event('up')
        assert self.panel()['expanded_size']==before['expanded_size']
        assert self.panel()['position']==before['position']
        assert [self.snapshot(n)['view'] for n in ('a','b')]==baseline
        assert self.camera_identity(self.camera_state())==camera
        self.checked('All eight resize directions preserve the opposite edge; Esc restores size and position; gestures preserve game and camera')
        self.capture('01-eight-edge-resizing')
        # Compact layout retains actual response controls and outer scrolling.
        remembered=self.body('your.actions')['height']
        p=self.panel();expanded=copy.deepcopy(p['expanded_size']);self.drag(center(p['resize_grip']),tuple((p['min_size'][i]-p['expanded_size'][i])*scale for i in (0,1)))
        time.sleep(.4)
        p=self.panel();assert all(abs(p['expanded_size'][i]-p['min_size'][i])<2 for i in (0,1))
        for e in self.hud()['master_tabs']:assert self.inside(e),e
        self.capture('02-minimum-size')
        self.drag(center(self.panel()['resize_grip']),tuple((expanded[i]-self.panel()['expanded_size'][i])*scale for i in (0,1)))
        time.sleep(.3)
        assert abs(self.body('your.actions')['height']-remembered)<2, 'Dock resize discarded the chosen Actions height'
        self.checked('Shrinking and expanding the dock restores the chosen section height')
        reset=next(e for e in self.hud()['camera_buttons'] if e['id']=='reset_panels')
        self.click(center(reset));time.sleep(.4)
        self.capture('03-command-center')

    def run(self):
        try:
            self.boot();self.panel_edges()
            if not self.args.smoke:
                self.check_sections();self.persistence()
            self.required_choice()
            self.clear_choices();self.own_turn();self.settle_presentation()
            # Exercise actual authoritative placement, cancellation and event targets.
            self.test_person_drag();self.settle_presentation();self.test_event_drag()
            self.settle_presentation();self.test_stale_drag()
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result=dict(ok=True,package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets)
            write_json(self.folder/'result.json',result);return result
        except Exception as error:
            write_json(self.folder/'result.json',dict(ok=False,package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,error=str(error),checks=self.checks,evidence=self.evidence,last_reports=self.reports))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=340)
    p.add_argument('--port',type=int,default=20041);p.add_argument('--timeout',type=float,default=1300)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    p.add_argument('--smoke',action='store_true',help='Check edge gestures, required responses and card drops; skip the full section/persistence matrix')
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-battle-plan-')
    out.mkdir(parents=True,exist_ok=True);result=dict(ok=False,results=[])
    try:
        for i,size in enumerate(args.resolutions):result['results'].append(BattlePlanScenario(args,out,size,i).run())
        result['ok']=True
    finally:write_json(out/'result.json',result)


if __name__=='__main__':main()
