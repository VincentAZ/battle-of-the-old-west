#!/usr/bin/env python3
"""Exercise movable panels and the actual both-crew ability overview.

Captures the real renderer. A pass verifies interaction/geometry, not AAA art
acceptance; every resulting screen still requires visual review.
"""
import argparse
import copy
import json
import time
from pathlib import Path
from test_unreal_interactions import InteractionScenario, EDITOR, ROOT, center, field_cards, resolution, write_json
from native_runtime_checks import assert_runtime_assets
from native_launch import create_native_run_directory, stop_owned_process_groups


class PresentationScenario(InteractionScenario):
    def panel(self, identity):
        panels=self.hud().get('dock_panels', [])
        if identity in ('crew','hand','actions') and any(p['id']=='master' for p in panels): identity='master'
        return next((p for p in panels if p['id']==identity),None)

    def click(self, point):
        self.event('move', point)
        time.sleep(.12)
        self.event('down', point)
        self.event('up', point)

    def drag(self, point, delta):
        self.event('down', point)
        self.event('move', (point[0] + delta[0], point[1] + delta[1]))
        self.event('up')

    def test_panels(self):
        self.wait('arranged dock panels', lambda: self.panel('crew') and self.panel('crew')['panel']['allocated_size'][0] > 100)
        scale = self.hud_dimensions()[0] / 1920
        baseline = [copy.deepcopy(self.snapshot(n)) for n in ('a', 'b')]
        camera = self.camera_identity(self.camera_state())
        before = copy.deepcopy(self.panel('crew'))
        modern=before['id']=='master'
        dx,dy=(-280,0) if modern else (120,55)
        self.drag(center(before['header']), (dx * scale, dy * scale))
        moved = self.wait('panel drag completes', lambda: self.panel('crew') if self.panel('crew')['move_count'] > 0 and not self.panel('crew')['interacting'] else None)
        assert abs(moved['position'][0] - before['position'][0] - dx) < 2
        assert abs(moved['position'][1] - before['position'][1] - dy) < 2
        self.drag(center(moved['resize_grip']), (90 * scale, (-150 if modern else 70) * scale))
        resized = self.wait('resize completes', lambda: self.panel('crew') if self.panel('crew')['resize_count'] > 0 and not self.panel('crew')['interacting'] else None)
        assert resized['expanded_size'][0] > before['expanded_size'][0] + 80
        assert (resized['expanded_size'][1] < before['expanded_size'][1] - 140) if modern else (resized['expanded_size'][1] > before['expanded_size'][1] + 60)
        saved_size = resized['expanded_size']
        self.capture('03-panel-moved-and-resized')
        self.click(center(resized['collapse_button']))
        self.wait('panel collapses', lambda: self.panel('crew')['collapsed'])
        collapsed = self.panel('crew')
        assert collapsed['content'] is None and collapsed['resize_grip'] is None
        assert abs(collapsed['effective_size'][1] - collapsed['header_height']) < .1
        self.capture('04-panel-collapsed')
        self.click(center(collapsed['collapse_button']))
        self.wait('panel expands', lambda: not self.panel('crew')['collapsed'])
        assert self.panel('crew')['expanded_size'] == saved_size
        # Background header interaction must not leak to the camera.
        spot = center(self.panel('crew')['header'])
        self.event('wheel', spot, wheel=4)
        for button in ('right', 'middle'):
            self.event('down', spot, button=button)
            self.event('move', (spot[0]+35, spot[1]+25), button=button)
            self.event('up', button=button)
        assert self.camera_identity(self.camera_state()) == camera
        assert [self.snapshot(n) for n in ('a', 'b')] == baseline
        self.checked('Real move/resize/collapse/expand preserves game state and camera; expanded size is retained')
        self.evidence['panel_manipulation'] = dict(before=before, after=copy.deepcopy(self.panel('crew')))
        saved = copy.deepcopy(self.panel('crew'))
        # Travel creates a new HUD; it must read the saved layout from its isolated INI.
        self.command('a', 'leave')
        self.wait('leave reaches menu', lambda: self.snapshot().get('hosted') is False)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('seat reconnect and new HUD', lambda: self.agree() and self.panel('crew') and self.panel('crew')['visible'])
        self.settle_presentation()
        assert self.panel('crew')['position'] == saved['position']
        assert self.panel('crew')['expanded_size'] == saved['expanded_size']
        self.checked('Panel layout persists through a fresh HUD after leaving and reconnecting')

    def prepare_both_crews(self):
        def population(column):
            return sum(c.get('type') != 'camp' for c in column)
        for step in range(self.args.max_setup_actions):
            snap = self.snapshot()
            players = snap['view']['players']
            if all(sum(population(c) for c in p['columns']) >= 6 for p in players) and snap['view']['choice'] is None:
                self.settle_presentation()
                self.evidence['dense_setup'] = dict(actions=step, snapshot=copy.deepcopy(self.snapshot()))
                return
            assert snap['view']['status'] == 'actions', 'Match ended while arranging the overview'
            acting = next(n for n in ('a','b') if self.snapshot(n).get('actions'))
            current = self.snapshot(acting)
            own = current['view']['players'][current['seat']]
            options = current['actions']
            full = sum(population(c) for c in own['columns']) >= 6
            if options[0]['command']['type'] == 'choose':
                placements = [a for a in options if a.get('placement',{}).get('punk')]
                action = min(placements,key=lambda a:population(own['columns'][a['placement']['column']])) if placements and not full else next((a for a in options if a.get('label')=='Skip'),options[0])
            else:
                people = [a for a in options if a.get('category')=='play_person' and 'replace' not in a['command']]
                action = min(people,key=lambda a:(a.get('cost',0),population(own['columns'][a['command']['column']]),a['command']['card'])) if people and not full else None
                hand = self.own_hand(acting)
                if not action and not full:
                    action = next((a for a in options if a['command']['type']=='junk' and self.junk_kind(hand.get(a['command'].get('card'),{}))=='punk'),None)
                if not action and not full: action=next((a for a in options if a['command']['type']=='draw'),None)
                action=action or next(a for a in options if a['command']['type']=='end_turn')
            self.submit(acting, action)
            if step % 5 == 0: self.settle_presentation()
        raise AssertionError('Could not fill both crews through legal play')

    def test_overview(self, label):
        camera_before = self.camera_identity(self.camera_state())
        toggle = self.wait('overview control',lambda:next((b for b in self.hud().get('camera_buttons',[]) if b['id']=='ability_overview'),None))
        self.click(center(toggle))
        self.wait('overview opens',lambda:self.hud().get('overview_open') and self.panel('overview')['visible'])
        self.wait('camera reaches bird view',lambda:self.camera_state().get('birds_eye') and self.camera_state()['pitch'] >= 75)
        self.capture(label)
        cards=field_cards(self.snapshot())
        widgets=self.hud()['overview_cards']
        assert {int(w['id']) for w in widgets} == {c['id'] for c in cards}
        assert all('public_abilities' in c for c in cards)
        content=self.panel('overview')['content']
        clipped=[]
        for w in widgets:
            if any(w['min'][i]<content['min'][i]-1 or w['max'][i]>content['max'][i]+1 for i in (0,1)):
                clipped.append(w['id'])
        self.evidence.setdefault('overview',[]).append(dict(label=label, cards=cards, widgets=widgets, content=content, clipped_cards=clipped))
        assert not clipped, f'Overview requires scrolling to see cards: {clipped}'
        self.checked(f'{label}: both crews and all {len(cards)} public cards fit together without individual inspection')
        if len(cards) >= 18:
            panel = copy.deepcopy(self.panel('overview'))
            scale = self.hud_dimensions()[0] / 1920
            delta = tuple((minimum-current)*scale for minimum,current in zip(panel['min_size'],panel['expanded_size']))
            self.drag(center(panel['resize_grip']),delta)
            self.wait('overview reaches minimum size',lambda:all(abs(a-b)<2 for a,b in zip(self.panel('overview')['expanded_size'],panel['min_size'])))
            self.capture(label+'-minimum')
            content=self.panel('overview')['content']
            widgets=self.hud()['overview_cards']
            clipped=[w['id'] for w in widgets if any(w['min'][i]<content['min'][i]-1 or w['max'][i]>content['max'][i]+1 for i in (0,1))]
            self.evidence['overview'].append(dict(label=label+'-minimum',cards=cards,widgets=widgets,content=content,clipped_cards=clipped))
            assert not clipped, f'Minimum overview size hides cards: {clipped}'
            self.checked('All18 public cards also fit at the declared minimum overview size')
        self.command('a','battle_overview',open=False)
        self.wait('overview closes',lambda:not self.hud()['overview_open'])
        self.wait('previous camera restored',lambda:not self.camera_state().get('birds_eye') and self.camera_identity(self.camera_state()) == camera_before)

    def run(self):
        try:
            self.boot()
            self.capture('02-default-dashboard')
            self.test_panels()
            self.test_overview('05-initial-ability-overview')
            self.prepare_both_crews()
            self.test_overview('06-full-both-crews-overview')
            self.capture('07-dense-dashboard')
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            result=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets,logs=str(self.folder))
            write_json(self.folder/'result.json',result)
            return result
        except Exception as error:
            write_json(self.folder/'result.json',dict(ok=False,failure=str(error),checks=self.checks,evidence=self.evidence,screenshots=self.captures,last_reports=self.reports))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor',type=Path,default=EDITOR)
    parser.add_argument('--package-dir',type=Path)
    parser.add_argument('--resolutions',nargs='+',type=resolution,default=[(1920,1080),(1280,720)])
    parser.add_argument('--ruleset',default='boomtown')
    parser.add_argument('--seed',type=int,default=2623)
    parser.add_argument('--port',type=int,default=19679)
    parser.add_argument('--timeout',type=float,default=700)
    parser.add_argument('--settle',type=float,default=.6)
    parser.add_argument('--max-setup-actions',type=int,default=240)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output=args.output.resolve() if args.output else create_native_run_directory('oldwest-presentation-ui-')
    output.mkdir(parents=True,exist_ok=True)
    report=dict(ok=False,results=[],logs=str(output),package_dir=str(args.package_dir.resolve()) if args.package_dir else None,limitations=['Same-workstation peers.','All screenshots require visual review; geometry tests do not certify AAA quality.'])
    print(f'Presentation UI evidence: {output}',flush=True)
    try:
        for i,size in enumerate(args.resolutions):report['results'].append(PresentationScenario(args,output,size,i).run())
        report['ok']=True
    except Exception as error:
        report['failure']=str(error)
        raise
    finally:
        write_json(output/'result.json',report)

if __name__=='__main__':main()
