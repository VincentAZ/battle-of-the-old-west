#!/usr/bin/env python3
"""Exercise camp/person shortcuts through native Slate input and real RPCs.

No state injection: seed 94 offers Cattle Ranch, Livery Barn and Railroad Work Camp to the joining
player. Setup uses legal camp selection, draws, plays, and turn changes.
"""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path
from test_unreal_flexible_sections import FlexibleScenario
from test_unreal_interactions import InteractionScenario, EDITOR, center, resolution, write_json, field_cards
from native_launch import create_native_run_directory, stop_owned_process_groups, game_net_driver_ports
from native_runtime_checks import assert_runtime_assets


class DirectDragScenario(FlexibleScenario):
    def capture(self, label):
        # Do not move the pointer: the release highlight is part of the evidence.
        return InteractionScenario.capture(self, label)

    def boot(self):
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log = self.folder/'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('rendered menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('two peers', self.agree, 100)
        own = next(a for a in self.snapshot()['actions'] if a['command']['camps'] == ['cattle_ranch', 'livery_barn', 'railroad_work_camp'])
        self.submit('a', own)
        options = self.snapshot('b')['actions']
        self.submit('b', max((a for a in options if 'homestead_cabin' in a['command']['camps']), key=lambda a: sum(self.defs[c]['starting_cards'] for c in a['command']['camps'])))
        self.wait('match starts', lambda: self.snapshot()['view']['status'] == 'actions')
        self.own_turn()
        seat = self.snapshot()['seat']
        self.camps = {c['card_id']: c['id'] for c in field_cards(self.snapshot()) if c['owner'] == seat and c['type'] == 'camp'}
        self.capture('01-direct-controls-start')

    def own_turn(self):
        super().own_turn()
        # Turn-start events can hand a required response to the defender.
        self.clear_choices()
        self.settle_presentation()

    def toggle_panel(self, open):
        if not self.hud().get('battle_plan_open',True):
            if not open:return
            self.click(center(next(b for b in self.hud()['camera_buttons'] if b['id']=='battle_plan')))
            self.wait('Battle Plan shown',lambda:self.hud()['battle_plan_open'])
        self.stable_layout()
        panel = self.wait('panel header arranged after presentation', lambda:
                          self.panel()['visible'] and self.panel()['collapse_button']['allocated_size'][0]>1 and self.panel())
        if panel['collapsed'] == open:
            self.click(center(panel['collapse_button']))
            self.wait('panel expanded' if open else 'panel collapsed', lambda: self.panel()['collapsed'] != open)
        self.stable_layout()

    def surface(self, **fields):
        return next((s for s in self.hud().get('panel_drop_surfaces', [])
                     if all(s[k] == v for k, v in fields.items()) and s['allocated_size'][0] > 1
                     and self.inside(s,self.outer()) and self.inside(s, self.body('your.formation')['viewport'] if fields.get('event_slot', -99) == -99
                                     else self.body('your.events')['viewport'])), None)

    def reveal_surface(self, **fields):
        # Compact field docks scroll; reveal the card with ordinary wheel input
        # instead of assuming the entire formation fits in the default height.
        for _ in range(16):
            visible=self.surface(**fields)
            if visible:return visible
            raw=next((s for s in self.hud().get('panel_drop_surfaces',[]) if all(s[k]==v for k,v in fields.items()) and s['allocated_size'][0]>1),None)
            self.outer_wheel(2 if raw and raw['min'][1]<self.outer()['min'][1] else -2)
            self.stable_layout()
        raise AssertionError(f'Panel card cannot be reached by scrolling: {fields}')

    def world_point(self, card):
        h=self.hud()
        entry=next((t for t in h['world_hover_targets'] if t['id']==card),None)
        assert entry, f'No rendered entity for {card}'
        scene=h['scene_rect'];panel=self.panel()['panel'] if self.panel()['visible'] else {'min':[0,0],'max':[0,0]}
        def exposed(p):
            labels=h.get('battlefield_labels',[])
            covered=any(label['id']!=card and label['rect'][0]<=p[0]<=label['rect'][2] and label['rect'][1]<=p[1]<=label['rect'][3] for label in labels)
            return not covered and all(scene['min'][i]<p[i]<scene['max'][i] for i in (0,1)) and not all(panel['min'][i]<=p[i]<=panel['max'][i] for i in (0,1))
        if entry['pick']==card and exposed(entry['screen']):return entry['screen']
        assert h['deployment']['card']==-1, 'Find the physical drop surface before starting the drag'
        # An open-sided camp can have empty air at the center of its bounds.
        # Find a visible part using the same real mouse hover a player sees.
        for dx,dy in [(0,-40),(40,-40),(-40,-40),(60,0),(-60,0),(0,-75),(75,-40),(-75,-40),(0,40),(100,0),(-100,0)]:
            point=[entry['screen'][0]+dx,entry['screen'][1]+dy]
            if not exposed(point):continue
            self.event('move',point);time.sleep(.18)
            if self.hud()['card_hover']['world_card']==card:return point
        for label in h.get('battlefield_labels',[]):
            if label['id']==card and exposed(label['screen']):return label['screen']
        raise AssertionError(f'No unobstructed physical surface or name label for {card}: {entry}')

    def start(self, card, point):
        baseline = copy.deepcopy(self.snapshot()['view'])
        self.event('move', point)
        self.event('down', point)
        self.event('move', (point[0]+14, point[1]-12))
        d = self.wait('direct drag starts', lambda: self.hud().get('deployment', {}).get('card') == card and self.hud()['deployment'])
        assert self.snapshot()['view'] == baseline, 'Starting a drag spent resources or started a choice'
        assert d['targets'], 'Drag has no destinations'
        return d

    def drag_target(self, deployment, kind, **fields):
        for target in deployment['targets']:
            if not all(target[k]==v for k,v in fields.items()):continue
            for command in [target['command']]+[a['command'] for a in target.get('alternatives',[])]:
                if command.get('kind','raid' if target['event_slot']!=-99 else '')==kind:
                    return {**target,'command':command}
        raise AssertionError(f'No destination offers {kind}: {fields}')

    def cancel(self, label, escape=False):
        before = copy.deepcopy(self.snapshot()['view'])
        if escape:
            self.key('Escape')
            self.event('up')
        else:
            self.event('move', (2, 2))
            self.event('up', (2, 2))
        self.wait('cancelled drag clears', lambda: self.hud()['deployment']['card'] == -1)
        assert self.snapshot()['view'] == before, label
        self.checked(label)

    def release(self, target, point, label, panel=False):
        self.event('move', point)
        self.wait('exact target highlights', lambda: self.hud()['deployment']['hovered'] >= 0)
        d = self.hud()['deployment']
        selected = d['targets'][d['hovered']]
        assert self.target_offers(selected,target['command']), (label, selected, target)
        if panel:
            assert d['panel_surface'] >= 0, 'Panel drop fell through into a world badge'
        self.capture(label+'-ready-to-release')
        # A move that works only on mouse-up still needs honest, stable feedback
        # while the player holds the pointer over the target.
        held=self.hud()['deployment']
        assert held['hovered']>=0 and self.target_offers(held['targets'][held['hovered']],target['command']), 'Release highlight disappeared while held still'
        if panel: assert held['panel_surface']>=0, 'Panel target highlight disappeared'
        before = copy.deepcopy(self.snapshot())
        self.event('up', point)
        self.accept_drop_choice(target,target['command'],before['view'])
        self.wait('one atomic move on both peers', lambda: self.agree() and self.snapshot()['view']['revision'] == before['view']['revision']+1)
        after = self.snapshot()
        source = target['command']['source']
        old = next(c for c in field_cards(before) if c['id'] == source)
        new = next(c for c in field_cards(after) if c['id'] == source)
        assert new['uses'] == old['uses']+1, 'Ability was activated twice or not at all'
        self.evidence[label] = dict(target=target, point=point, panel=panel,
                                   before=before['view'], after=copy.deepcopy(after['view']))
        self.settle_presentation()
        return before, after

    def test_punks(self):
        arcade = self.camps['livery_barn']
        self.toggle_panel(False)
        start = self.world_point(arcade)
        d = self.start(arcade, start)
        self.cancel('World camp drag cancels outside the board without activating or paying')
        d = self.start(arcade, start)
        self.cancel('Escape cancels a world camp drag without activating or paying', escape=True)
        d = self.start(arcade, start)
        target = self.drag_target(d, 'punk', column=1)
        # Land on the actual 3D lane marker, not its displaced text badge.
        point = [p*h/v for p,h,v in zip(target['world_screen_pixels'], self.hud_dimensions(), self.hud()['viewport_size'])]
        before, after = self.release(target, point, '02-world-camp-to-lane')
        old = {c['id'] for c in field_cards(before)}
        created = [c for c in field_cards(after) if c['id'] not in old]
        assert len(created) == 1 and created[0]['punk']
        assert before['view']['players'][before['seat']]['water']-after['view']['players'][after['seat']]['water'] == 1
        self.checked('Dragging the 3D punk camp into a lane creates one punk and pays once')
        self.round()
        self.toggle_panel(True)
        self.isolate('your.formation')
        source = self.reveal_surface(card=arcade)
        d = self.start(arcade, center(source))
        target = self.drag_target(d, 'punk', column=0)
        dest = self.wait('panel lane destination', lambda: self.surface(side=target['side'], column=target['column'], row=target['row']))
        before, after = self.release(target, center(dest), '03-panel-camp-to-lane', panel=True)
        old = {c['id'] for c in field_cards(before)}
        created = [c for c in field_cards(after) if c['id'] not in old]
        assert len(created) == 1 and created[0]['punk']
        self.checked('Dragging a Battle Plan camp onto its lane slot creates exactly one punk')
        return [c['id'] for c in field_cards(after) if c['owner'] == after['seat'] and c.get('punk')]

    def test_raids(self):
        self.round()
        garage = self.camps['cattle_ranch']
        self.toggle_panel(False)
        d = self.start(garage, self.world_point(garage))
        target = self.drag_target(d, 'raid')
        before, after = self.release(target, target['screen'], '04-world-garage-to-event-lane')
        queue = after['view']['players'][after['seat']]['queue']
        raider = next(c for c in queue if c and c['card_id'] == 'stampede')
        assert queue[target['event_slot']]['id'] == raider['id']
        self.checked('Dragging Cattle Ranch launches Stampede at the rules-selected event position')
        self.round()
        self.toggle_panel(False)
        # A queued Raider is itself draggable; its source ability is named in
        # the badge so dragging the model never grants a free raid.
        d = self.start(raider['id'], self.world_point(raider['id']))
        target = self.drag_target(d, 'raid')
        before, after = self.release(target, target['screen'], '05-world-raider-advance')
        assert before['view']['players'][before['seat']]['water']-after['view']['players'][after['seat']]['water'] == 1
        self.clear_choices()
        self.checked('Dragging a queued Raider advances or resolves it by paying for Cattle Ranch once')
        self.round()
        self.toggle_panel(True)
        self.isolate('your.formation')
        # Scroll the lower header into view before opening it; offscreen Slate
        # widgets can retain their geometry from the previous scroll position.
        self.outer_wheel(-40)
        self.stable_layout()
        self.fold('your.events', False)
        source = self.reveal_surface(card=garage)
        d = self.start(garage, center(source))
        target = self.drag_target(d, 'raid')
        outer = self.outer()
        self.event('move', (center(outer)[0], outer['max'][1]-8))
        dest = self.wait('edge scroll reveals event slot', lambda: self.surface(side=self.snapshot()['seat'], event_slot=target['event_slot']))
        self.checked('Holding a direct drag at the panel edge scrolls a clipped event destination into view')
        self.release(target, center(dest), '06-panel-garage-to-event-slot', panel=True)
        self.clear_choices()
        self.checked('Battle Plan Garage-to-event-slot drag launches the same legal raid')

    def test_labor(self, punks):
        # Use a legal opposing attack on an ordinary faceup person. This
        # does not depend on a particular card staying out of either punk pile.
        self.round()
        action = self.seek(lambda a,s: a['command']['type']=='play' and a['command'].get('column')==2
                           and a['command'].get('position')==0 and self.own_hand().get(a['command'].get('card'),{}).get('card_id')!='civil_war_veteran',
                           'affordable person in Railroad Work Camp lane', max_actions=40)
        soldier = action['command']['card']
        self.submit('a', action)
        self.clear_choices()
        self.submit('a', next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn'))
        self.clear_choices()
        pillbox = next(c['id'] for c in field_cards(self.snapshot()) if c.get('card_id')=='homestead_cabin' and c['owner']!=self.snapshot()['seat'])
        attack = next(a for a in self.snapshot('b')['actions'] if a['command'].get('source')==pillbox)
        self.submit('b', attack)
        target = next(a for a in self.snapshot('b')['actions'] if a.get('target')==soldier)
        self.submit('b', target)
        self.own_turn()
        assert next(c for c in field_cards(self.snapshot()) if c['id']==soldier)['damage']==1
        self.toggle_panel(False)
        victim = next(c['id'] for c in field_cards(self.snapshot()) if c['id'] in punks)
        labor = self.camps['railroad_work_camp']
        camp_pick = next(t for t in self.hud()['world_hover_targets'] if t['id']==labor)
        # Explicitly exercise the open interior, not a pixel-perfect fence hit.
        labor_point = camp_pick['screen'] if camp_pick['pick'] in (-1,labor) else self.world_point(labor)
        d = self.start(victim, self.world_point(victim))
        self.cancel('Person-to-camp drag cancellation preserves the person and camp')
        baseline = copy.deepcopy(self.snapshot()['view'])
        self.start(victim, self.world_point(victim))
        self.event('move', self.world_point(self.camps['cattle_ranch']))
        assert self.hud()['deployment']['hovered']==-1, 'An unrelated camp accepted a sacrifice'
        self.event('up')
        self.wait('invalid camp drop clears',lambda:self.hud()['deployment']['card']==-1)
        assert self.snapshot()['view']==baseline
        self.checked('Dropping a person on an unrelated camp does not sacrifice or activate anything')
        d = self.start(victim, self.world_point(victim))
        target = self.drag_target(d, 'sacrifice', target_card=labor)
        baseline = copy.deepcopy(self.snapshot()['view'])
        self.event('move', labor_point)
        self.capture('07-before-sacrifice-release')
        held=self.hud()['deployment']
        assert held['hovered']>=0 and self.target_offers(held['targets'][held['hovered']],target['command']), ('Sacrifice destination did not highlight',labor_point,target,held)
        self.event('up', labor_point)
        self.wait('sacrifice confirmation shown',lambda:any(e['id'].startswith('CONFIRM · ') and e['allocated_size'][0]>1 for e in self.hud()['context_entries']))
        assert self.snapshot()['view']==baseline, 'Sacrifice happened before confirmation'
        self.capture('07a-sacrifice-confirmation')
        self.key('Escape')
        time.sleep(.4)
        assert self.snapshot()['view']==baseline, 'Cancelling confirmation changed the match'
        self.checked('Escape dismisses destructive drop confirmation without sacrificing or spending water')
        d = self.start(victim, self.world_point(victim))
        self.drag_target(d, 'sacrifice', target_card=labor)
        self.event('move', labor_point);self.event('up', labor_point)
        confirmation=self.wait('stale-confirmation fixture',lambda:next((e for e in self.hud()['context_entries'] if e['id'].startswith('CONFIRM · ') and e['allocated_size'][0]>1),None))
        end_turn=next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn')
        self.submit('a',end_turn)
        self.settle_presentation()
        baseline=copy.deepcopy(self.snapshot()['view'])
        if any(e['id']==confirmation['id'] and e['allocated_size'][0]>1 for e in self.hud()['context_entries']):
            self.click(center(confirmation));time.sleep(.5)
        assert self.snapshot()['view']==baseline, 'Stale sacrifice confirmation changed the newer state'
        self.key('Escape')
        self.checked('A revision change invalidates an outstanding sacrifice confirmation')
        self.own_turn()
        camp_pick = next(t for t in self.hud()['world_hover_targets'] if t['id']==labor)
        labor_point = camp_pick['screen'] if camp_pick['pick'] in (-1,labor) else self.world_point(labor)
        d = self.start(victim, self.world_point(victim))
        target = self.drag_target(d, 'sacrifice', target_card=labor)
        before, after = self.release(target, labor_point, '07-world-person-to-labor-camp')
        assert all(c['id']!=victim for c in field_cards(after)), 'Selected sacrifice survived'
        assert after['view']['choice'] and 'restore' in after['view']['choice']['prompt'].lower()
        self.toggle_panel(False)
        baseline = copy.deepcopy(self.snapshot())
        self.click(self.world_point(soldier))
        self.wait('left-click restores the damaged person', lambda: self.agree() and self.snapshot()['view']['revision']==baseline['view']['revision']+1)
        assert next(c for c in field_cards(self.snapshot()) if c['id']==soldier)['damage']==0
        self.settle_presentation()
        self.capture('08-world-restore-complete')
        self.checked('Drop person on the 3D Railroad Work Camp, then left-click another card to restore it')
        self.round()
        self.toggle_panel(True)
        self.isolate('your.formation')
        victim = next(c['id'] for c in field_cards(self.snapshot()) if c['id'] in punks)
        source = self.reveal_surface(card=victim)
        d = self.start(victim, center(source))
        target = self.drag_target(d, 'sacrifice', target_card=labor)
        if not self.surface(card=labor):
            outer=self.outer();self.event('move',(center(outer)[0],outer['max'][1]-8))
        dest = self.wait('Railroad Work Camp panel target', lambda: self.surface(card=labor))
        _, after = self.release(target, center(dest), '09-panel-person-to-labor-camp', panel=True)
        assert all(c['id']!=victim for c in field_cards(after))
        self.clear_choices()
        self.checked('Battle Plan person-to-Labor-Camp drop sacrifices the selected person once')

    def test_stale_shortcut(self):
        self.round()
        self.toggle_panel(False)
        garage = self.camps['cattle_ranch']
        d = self.start(garage, self.world_point(garage))
        target = self.drag_target(d, 'raid')
        # A real competing authoritative move invalidates the cached drag.
        other = next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn')
        self.submit('a', other)
        changed = copy.deepcopy(self.snapshot()['view'])
        self.wait('stale direct drag invalidates', lambda:self.hud()['deployment']['card']==-1)
        self.event('up', target['screen'])
        time.sleep(.3)
        assert self.snapshot()['view']==changed, 'Stale drop submitted an extra move'
        self.checked('A stale direct shortcut cannot spend water or activate its camp')

    def run(self):
        try:
            self.boot()
            punks = self.test_punks()
            if not self.args.only_labor:self.test_raids()
            self.test_labor(punks)
            self.test_stale_shortcut()
            assets = assert_runtime_assets([self.folder/'a.log', self.folder/'b.log'])
            result = dict(ok=True, package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,
                          checks=self.checks, evidence=self.evidence, screenshots=self.captures, runtime_assets=assets)
            if self.runtime.package_root:
                binary = self.runtime.package_root/'OldWest/Binaries/Linux/OldWestGame'
                if not binary.exists(): binary=binary.with_name('OldWestGame-Linux-Development')
                result['build'] = dict(executable=dict(path=str(binary), sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            try: self.capture('failure')
            except Exception: pass
            write_json(self.folder/'result.json',dict(ok=False,error=str(error),package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,checks=self.checks,evidence=self.evidence,last_reports=self.reports))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams: stream.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='base_2024');p.add_argument('--seed',type=int,default=94)
    p.add_argument('--port',type=int,default=20161);p.add_argument('--timeout',type=float,default=900)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    p.add_argument('--only-labor',action='store_true',help='Focus on camp recruitment, sacrifice and stale shortcuts; omit the separate raid scenario')
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-direct-drags-')
    out.mkdir(parents=True,exist_ok=True);result=dict(ok=False,results=[])
    try:
        for i,size in enumerate(args.resolutions):result['results'].append(DirectDragScenario(args,out,size,i).run())
        result['ok']=True
    finally:write_json(out/'result.json',result)


if __name__=='__main__':main()
