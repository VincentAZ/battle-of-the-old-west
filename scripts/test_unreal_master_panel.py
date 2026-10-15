#!/usr/bin/env python3
"""Real Slate input, authorized two-peer play, and renderer checks for the master HUD."""
import argparse
import copy
import json
import time
from pathlib import Path
from test_unreal_presentation_responses import ResponseScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json, field_cards, card_handle
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class MasterScenario(ResponseScenario):
    def click(self, point):
        # A human moves the pointer before clicking. Slate's button release
        # checks its hover path, so do not teleport straight into a down event.
        self.event('move',point)
        time.sleep(.12)
        self.event('down',point)
        self.event('up',point)

    def panel(self, identity='master'):
        # Existing required-response assertions now target the consolidated dock.
        return super().panel('master' if identity in ('actions', 'crew', 'hand') else identity)

    def tab(self, side):
        entry=self.wait('master tab',lambda:next((x for x in self.hud().get('master_tabs',[]) if x['id']==side and x['allocated_size'][0]>1),None))
        self.click(center(entry))
        expected=self.snapshot()['seat'] if side=='your' else 1-self.snapshot()['seat']
        ids={c['id'] for col in self.snapshot()['view']['players'][expected]['columns'] for c in col}
        def arranged_tab():
            h=self.hud()
            return h['inspector_side']==expected and {int(e['id']) for e in h['master_cards']}==ids and (side!='enemy' or not h['hand_cards']) and all(e['allocated_size'][0]>1 for e in h['master_cards'])
        self.wait('selected tab widgets rebuilt and arranged',arranged_tab)
        time.sleep(.2)

    def inside(self, entry, area=None):
        area=area or self.panel()['content']
        return area and all(entry['min'][i]>=area['min'][i]-1 and entry['max'][i]<=area['max'][i]+1 for i in (0,1))

    def visible_hand_widget(self, card):
        self.tab('your')
        if self.hud().get('section_bodies'):
            # Wrapped hands scroll vertically inside their own resizable viewport.
            outer=self.hud()['battle_scroll'][0]
            self.event('wheel',(outer['max'][0]-4,center(outer)[1]),wheel=30);time.sleep(.3)
            def hand_area():
                return next(b['viewport'] for b in self.hud()['section_bodies'] if b['id']=='your.hand')
            def clipped():
                e=next((w for w in self.hud()['hand_cards'] if card_handle(w)==card),None)
                area=hand_area();outer=self.hud()['battle_scroll'][0]
                if not e or not area:return None
                lo=[max(e['min'][i],area['min'][i],outer['min'][i]) for i in (0,1)]
                hi=[min(e['max'][i],area['max'][i],outer['max'][i]) for i in (0,1)]
                return dict(e,min=lo,max=hi) if hi[0]-lo[0]>30 and hi[1]-lo[1]>40 else None
            for direction in (1,-1):
                for _ in range(max(24,len(self.hud()['hand_cards']))):
                    found=clipped()
                    if found:return found
                    self.event('wheel',center(hand_area()),wheel=direction*3);time.sleep(.2)
            found=clipped()
            if found:return found
            raise AssertionError(f'Wrapped hand card {card} is unreachable')
        def visible():
            return next((e for e in self.hud()['hand_cards'] if card_handle(e)==card and self.inside(e)),None)
        result=visible()
        if result:return result
        # First hand tile determines the actual scroll strip's Y, even after resizing.
        entries=self.hud()['hand_cards']
        panel=self.panel()['content']
        point=((panel['min'][0]+panel['max'][0])/2, center(entries[0])[1])
        camera=self.camera_identity(self.camera_state())
        for direction in (-1,1):
            for _ in range(24):
                self.event('wheel',point,wheel=direction*3)
                # Wait for Slate's animated scroll before reading the hit target.
                # Otherwise the next card can slide under the saved coordinates.
                time.sleep(.6)
                assert self.camera_identity(self.camera_state())==camera
                result=visible()
                if result:return result
        raise AssertionError(f'Hand card {card} could not be reached by scrolling')

    def layout_and_hover(self):
        self.wait('master arranged',lambda:self.panel() and self.panel()['visible'] and self.panel()['content'] and self.hud().get('master_cards') and not self.read()['cinematic']['busy'])
        time.sleep(.5)
        docks=self.hud()['dock_panels']
        assert {p['id'] for p in docks}=={'master','overview'}
        assert [p['id'] for p in docks if p['visible']]==['master']
        own=self.snapshot()['seat']
        self.tab('your')
        assert all(self.inside(e) for e in self.hud()['master_cards']), 'Formation clipped at default size'
        w,h=self.hud_dimensions(); box=self.panel()['panel']; obscured=(box['max'][0]-box['min'][0])*(box['max'][1]-box['min'][1])/(w*h)
        assert obscured<.27,obscured
        self.evidence['default_panel_viewport_fraction']=obscured
        self.capture('02-master-your')
        self.tab('enemy')
        assert not self.hud()['hand_cards'], 'Enemy hand faces rendered'
        expected={c['id'] for col in self.snapshot()['view']['players'][1-own]['columns'] for c in col}
        assert {int(e['id']) for e in self.hud()['master_cards']}==expected
        self.capture('03-master-enemy')
        self.checked('One compact dock; all camps visible; enemy tab shows only public formation and hidden hand backs')
        self.tab('your')
        baseline=[copy.deepcopy(self.snapshot(n)) for n in ('a','b')]
        inspected=self.hud()['inspected_card'];camera=self.camera_identity(self.camera_state())
        target=self.hud()['master_cards'][0]
        self.event('move',center(target))
        self.wait('panel card glance',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==int(target['id']))
        self.capture('04-panel-card-hover')
        assert self.hud()['card_hover']['text']
        # Actual projected selection bounds, then the same pointer route used by a human.
        box=self.panel()['panel']
        targets=[t for t in self.hud()['world_hover_targets'] if t['pick']==t['id'] and 0<t['screen'][0]<box['min'][0]-8 and self.hud()['scene_rect']['min'][1]<t['screen'][1]<h]
        assert targets,'No visible world camp target'
        world=targets[0]
        self.event('move',world['screen'])
        self.wait('world camp glance',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==world['id'])
        self.capture('05-world-camp-hover')
        rect=self.hud()['card_hover'].get('rect')
        if rect:
            assert not all(rect['min'][i]<=world['screen'][i]<=rect['max'][i] for i in (0,1)), 'Glance covers hovered camp point'
            assert all(0<=rect['min'][i]<rect['max'][i]<=self.hud_dimensions()[i]+1 for i in (0,1))
        assert [self.snapshot(n) for n in ('a','b')]==baseline
        assert self.hud()['inspected_card']==inspected and self.camera_identity(self.camera_state())==camera
        self.checked('Panel and 3D camp hover show information without selection, camera movement, or game changes')
        self.command('a','settings',operation='open')
        self.command('a','settings',operation='edit',card_hover=False)
        self.command('a','settings',operation='apply')
        self.wait('hover preference applied',lambda:not self.hud()['settings']['card_hover'])
        self.capture('06-hover-setting-off')
        self.command('a','settings',operation='close')
        self.event('move',world['screen']);time.sleep(.5)
        assert not self.hud()['card_hover']['visible']
        self.event('move',center(self.hud()['master_cards'][0]));time.sleep(.5)
        assert not self.hud()['card_hover']['visible']
        assert 'CardHover=False' in (self.folder/'a.settings.ini').read_text()
        self.command('a','settings',operation='open')
        self.command('a','settings',operation='edit',card_hover=True)
        self.command('a','settings',operation='apply')
        self.command('a','settings',operation='close')
        self.event('move',world['screen'])
        self.wait('hover reenabled',lambda:self.hud()['card_hover']['visible'])
        self.checked('Saved hover toggle suppresses both world and panel information and can be reenabled')

    def panel_gestures(self):
        before=copy.deepcopy(self.panel());scale=self.hud_dimensions()[0]/1920
        baseline=[copy.deepcopy(self.snapshot(n)) for n in ('a','b')]
        camera=self.camera_identity(self.camera_state())
        self.drag(center(before['header']),(-280*scale,0))
        self.wait('panel moved',lambda:self.panel()['move_count']>0 and not self.panel()['interacting'])
        assert abs(self.panel()['position'][0]-before['position'][0]+280)<2
        self.drag(center(self.panel()['resize_grip']),(90*scale,-150*scale))
        self.wait('panel resized',lambda:self.panel()['resize_count']>0 and not self.panel()['interacting'])
        assert self.panel()['expanded_size'][0]>before['expanded_size'][0]+80
        assert self.panel()['expanded_size'][1]<before['expanded_size'][1]-140
        self.capture('07-master-moved-resized')
        saved=copy.deepcopy(self.panel())
        self.click(center(self.panel()['collapse_button']))
        self.wait('panel collapsed',lambda:self.panel()['collapsed'])
        assert self.panel()['content'] is None
        self.click(center(self.panel()['collapse_button']))
        self.wait('panel expanded',lambda:not self.panel()['collapsed'])
        assert self.panel()['expanded_size']==saved['expanded_size']
        assert [self.snapshot(n) for n in ('a','b')]==baseline
        assert self.camera_identity(self.camera_state())==camera
        self.command('a','leave');self.wait('menu',lambda:self.snapshot().get('hosted') is False)
        self.command('a','join',address=f'127.0.0.1:{self.port}')
        self.wait('reconnected',lambda:self.agree() and self.panel() and self.panel()['visible'])
        self.settle_presentation()
        assert self.panel()['position']==saved['position'] and self.panel()['expanded_size']==saved['expanded_size']
        assert self.hud()['settings']['card_hover']
        self.checked('Move, resize, collapse, expand and reconnect preserve layout, game state and camera')
        reset=next(e for e in self.hud()['camera_buttons'] if e['id']=='reset_panels')
        self.click(center(reset))
        self.wait('default layout restored',lambda:abs(self.panel()['position'][0]-before['position'][0])<2)
        self.tab('your')

    def assert_roster(self):
        # Titles deliberately ellipsize to their allotted width; their unwrapped
        # desired width is not a clipping failure. Check actual card rectangles.
        assert len(self.hud()['roster_lanes'])==3
        assert all(self.inside(e) for e in self.hud()['master_cards'])
        self.checked('All three formation columns and their card tiles fit inside the master panel')

    def run(self):
        try:
            self.boot()
            if self.args.case=='layout':
                self.layout_and_hover();self.panel_gestures()
                person=self.test_person_drag()
                self.tab('your')
                tile=next(e for e in self.hud()['master_cards'] if int(e['id'])==person)
                self.event('move',center(tile))
                self.wait('played person glance',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==person)
                self.capture('08-played-person-hover')
                self.click(center(self.panel()['collapse_button']))
                self.wait('panel collapsed for unobstructed world hover',lambda:self.panel()['collapsed'])
                self.event('move',(8,8));self.wait('previous glance cleared',lambda:not self.hud()['card_hover']['visible'])
                target=next(t for t in self.hud()['world_hover_targets'] if t['id']==person and t['pick']==person)
                self.event('move',target['screen'])
                self.wait('world person glance',lambda:self.hud()['card_hover']['visible'] and self.hud()['card_hover']['world_card']==person)
                self.capture('09-world-person-hover')
                rect=self.hud()['card_hover'].get('rect')
                if rect: assert not all(rect['min'][i]<=target['screen'][i]<=rect['max'][i] for i in (0,1)), 'Glance covers hovered person point'
                self.click(center(self.panel()['collapse_button']))
                self.wait('panel reexpanded',lambda:not self.panel()['collapsed'])
                self.checked('A newly deployed person exposes current information on both panel and world hover')
                current=self.snapshot()
                if current['view']['active_player']==current['seat']:
                    self.submit('a',next(a for a in current['actions'] if a['command']['type']=='end_turn'))
                self.settle_presentation()
                self.wait('opponent turn hides actions',lambda:not self.hud()['master_actions_visible'] and not self.hud()['master_actions'])
                self.capture('11-opponent-turn-actions-hidden')
                self.checked('Your normal action controls disappear during the opponent turn')
                self.test_event_drag();self.settle_presentation()
            elif self.args.case=='responses':
                self.test_responses()
            elif self.args.case=='dense':
                self.prepare_both_crews();self.tab('your')
                assert len(self.hud()['master_cards'])==9
                assert all(self.inside(e) for e in self.hud()['master_cards']), 'Dense formation clipped at default size'
                self.capture('09-full-formation')
                self.tab('enemy')
                assert len(self.hud()['master_cards'])==9 and not self.hud()['hand_cards']
                assert all(self.inside(e) for e in self.hud()['master_cards'])
                self.capture('09-full-enemy-formation')
                self.test_overview('10-full-overview')
                self.checked('Full own/enemy formations and both-player overview remain usable')
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets)
            write_json(self.folder/'result.json',result);return result
        except Exception as error:
            write_json(self.folder/'result.json',dict(ok=False,failure=str(error),checks=self.checks,evidence=self.evidence,screenshots=self.captures,last_reports=self.reports));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=2623)
    p.add_argument('--port',type=int,default=19879);p.add_argument('--timeout',type=float,default=1000)
    p.add_argument('--settle',type=float,default=.4);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    p.add_argument('--cases',nargs='+',choices=['layout','responses','dense'],default=['layout','responses','dense'])
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-master-panel-')
    out.mkdir(parents=True,exist_ok=True)
    result=dict(ok=False,results=[],limitations=['Two Linux peers on one workstation; no remote or Windows test.','Screenshots require human visual review.'])
    print(f'Master HUD evidence: {out}',flush=True)
    try:
        for case in args.cases:
            args.case=case;case_out=out/case;case_out.mkdir(exist_ok=True)
            for index,size in enumerate(args.resolutions):
                item=MasterScenario(args,case_out,size,index).run();item['case']=case;item['resolution']=size;result['results'].append(item)
                write_json(out/'result.json',result)
        result['ok']=True
    finally:write_json(out/'result.json',result)
if __name__=='__main__':main()
