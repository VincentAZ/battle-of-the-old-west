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
from test_unreal_direct_drags import DirectDragScenario
from test_unreal_interactions import InteractionScenario, EDITOR, center, resolution, write_json, field_cards
from native_launch import create_native_run_directory, stop_owned_process_groups, game_net_driver_ports
from native_runtime_checks import assert_runtime_assets


class FieldPlayScenario(DirectDragScenario):
    def inside(self,entry,area=None):
        if area is None:area={'min':[0,0],'max':self.hud_dimensions()}
        return super().inside(entry,area)

    def toggle_panel(self, open):
        assert not open, 'Field-only scenario tried to open Battle Plan'
        assert not self.hud()['battle_plan_open']
        self.hand(False)

    def hand(self, shown):
        present=bool(self.hud()['hand_cards'])
        if present!=shown:
            self.click(center(next(b for b in self.hud()['field_buttons'] if b['id']=='toggle_hand')))
            self.wait('standalone hand toggles',lambda:bool(self.hud()['hand_cards'])==shown)
        self.stable_layout()

    def field_action(self, action):
        command=action['command']
        button=self.wait('field action button',lambda:next((b for b in self.hud()['field_buttons'] if b['id'].startswith('{') and json.loads(b['id'])==command),None))
        before=self.snapshot()['view']['revision']
        self.click(center(button))
        self.wait('field button submits',lambda:self.agree() and self.snapshot()['view']['revision']==before+1)
        self.settle_presentation()
        assert not self.hud()['battle_plan_open']

    def boot(self):
        super().boot()
        assert not self.hud()['battle_plan_open']
        assert not next(p for p in self.hud()['dock_panels'] if p['id']=='master')['visible']
        assert self.hud()['hand_cards']
        self.capture('01-default-field-and-hand')
        scene=self.hud()['scene_rect']
        for card in self.camps.values():
            point=next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==card)
            assert all(scene['min'][i]<point[i]<scene['max'][i] for i in (0,1)), 'Field hand covers a camp name'
        self.checked('Match starts with a standalone playable hand and Battle Plan hidden')
        draw=next(a for a in self.snapshot()['actions'] if a['command']['type']=='draw')
        self.field_action(draw)
        self.checked('Draw is available directly beside the field')
        self.round()
        action=self.seek(lambda a,s:a['command']['type']=='play' and 'column' in a['command'] and a.get('cost',0)<=2,'playable field hand person',max_actions=40)
        self.hand(True)
        card=action['command']['card']
        tile=next((b for b in self.hud()['hand_cards'] if int(b['id'])==card),None)
        # Scroll the horizontal hand if its playable card starts clipped.
        for _ in range(20):
            if tile and self.inside(tile):break
            self.event('wheel',(self.hud_dimensions()[0]-100,self.hud_dimensions()[1]-60),wheel=-3)
            tile=next((b for b in self.hud()['hand_cards'] if int(b['id'])==card),None)
        assert tile and self.inside(tile)
        d=self.start(card,center(tile));target=next(t for t in d['targets'] if t['command']==action['command'])
        self.cancel('Standalone hand drag cancels without playing or paying')
        self.start(card,center(tile));self.event('move',target['screen'])
        self.wait('hand drag field target',lambda:self.hud()['deployment']['hovered']>=0)
        self.capture('02-hand-to-field-release')
        before=self.snapshot()['view']['revision'];self.event('up',target['screen'])
        self.wait('hand person enters field',lambda:self.agree() and self.snapshot()['view']['revision']==before+1)
        self.clear_choices();self.settle_presentation()
        assert not self.hud()['battle_plan_open']
        self.checked('Person dragged from standalone hand onto the battlefield without Battle Plan')
        self.hand(False)
        self.click(next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==self.camps['cattle_ranch']))
        self.wait('clicked camp exposes field ability',lambda:any(b['id'].startswith('{') and json.loads(b['id']).get('source')==self.camps['cattle_ranch'] for b in self.hud()['field_buttons']))
        self.capture('03-clicked-camp-field-actions')
        self.checked('Clicking a camp name on the field exposes its ability outside Battle Plan')
        self.field_action(next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn'))
        self.checked('End turn works directly from the field controls')
        self.own_turn()

    def hand_tile(self,card):
        self.hand(True)
        for _ in range(30):
            tile=next((b for b in self.hud()['hand_cards'] if int(b['id'])==card),None)
            if tile and self.inside(tile):return tile
            self.event('wheel',(self.hud_dimensions()[0]-100,self.hud_dimensions()[1]-60),wheel=-3)
        raise AssertionError('Hand card cannot be reached by scrolling')

    def test_stale_shortcut(self):
        super().test_stale_shortcut()
        self.own_turn()
        action=self.seek(lambda a,s:a['command']['type']=='play' and a.get('category')=='play_event','affordable event',max_actions=50)
        card=action['command']['card'];tile=self.hand_tile(card)
        d=self.start(card,center(tile))
        target=next(t for t in d['targets'] if t['command']==action['command']);self.event('move',target['screen'])
        self.wait('event has lit field destination',lambda:self.hud()['deployment']['hovered']>=0)
        self.capture('10-standalone-event-release')
        before=self.snapshot()['view']['revision'];self.event('up',target['screen'])
        self.wait('event played from field hand',lambda:self.agree() and self.snapshot()['view']['revision']==before+1)
        assert card not in self.own_hand()
        self.clear_choices();self.settle_presentation()
        self.checked('Event dragged from standalone hand to its field destination')
        self.own_turn()
        action=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{})) in ('water','draw'),'simple junk action',max_actions=40)
        card=action['command']['card'];self.click(center(self.hand_tile(card)))
        self.field_action(action)
        assert card not in self.own_hand()
        self.checked('Selected hand card can be junked using its field action')
        assert not self.hud()['battle_plan_open']
        self.capture('11-field-only-complete')

    def test_punks(self):
        arcade = self.camps['livery_barn']
        self.toggle_panel(False)
        start = next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==arcade)
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
        return [c['id'] for c in created]

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
        self.click(next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==raider['id']))
        self.wait('Raider exposes its raid source',lambda:any(b['id'].startswith('{') and json.loads(b['id']).get('source')==garage for b in self.hud()['field_buttons']))
        self.checked('Clicking the Raider exposes the legal raid ability')
        d = self.start(raider['id'], next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==raider['id']))
        target = self.drag_target(d, 'raid')
        before, after = self.release(target, target['screen'], '05-world-raider-advance')
        assert before['view']['players'][before['seat']]['water']-after['view']['players'][after['seat']]['water'] == 1
        self.clear_choices()
        self.checked('Dragging a queued Raider advances or resolves it by paying for Cattle Ranch once')

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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='base_2024');p.add_argument('--seed',type=int,default=94)
    p.add_argument('--port',type=int,default=20361);p.add_argument('--timeout',type=float,default=900)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-field-play-')
    out.mkdir(parents=True,exist_ok=True);result=dict(ok=False,results=[])
    try:
        for i,size in enumerate(args.resolutions):result['results'].append(FieldPlayScenario(args,out,size,i).run())
        result['ok']=True
    finally:write_json(out/'result.json',result)


if __name__=='__main__':main()
