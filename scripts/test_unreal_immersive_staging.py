#!/usr/bin/env python3
"""Native pointer checks for the approved world-hand redesign (no state injection)."""
import argparse
import copy
import math
import time
from pathlib import Path
from test_unreal_direct_drags import DirectDragScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json
from test_unreal_interactions import field_cards
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_singleplayer import file_signature
from western_terms import translate


class StagingScenario(DirectDragScenario):
    def launch(self,name,url,rendered=False):
        return super().launch(name,url,rendered=rendered or self.args.both_views)

    def verify_both_views(self):
        if not self.args.both_views:return
        for peer in ('a','b'):
            self.command(peer,'skip_cinematics')
        time.sleep(.7)
        for peer,other in (('a','b'),('b','a')):
            snapshot=self.snapshot(peer);seat=snapshot['seat']
            own={c['id'] for c in snapshot['view']['players'][seat]['hand']}
            hidden={c['id'] for c in self.snapshot(other)['view']['players'][1-seat]['hand']}
            hud=self.read(peer)['hud']
            labels={e['id'] for e in hud['battlefield_labels']}
            targets={e['id'] for e in hud['world_hover_targets']}
            assert own<=labels,(peer,'Own hand missing from rendered field',own-labels)
            assert not hidden&(labels|targets),(peer,'Opponent hand exposed as a world actor')
            assert 'hand' not in snapshot['view']['players'][1-seat]
            assert hud['punk_shelter'] and hud['enemy_punk_shelter']
            camps=[u for u in self.read(peer)['cinematic']['units'] if 'faces_opponent' in u]
            assert len(camps)==6 and all(u['faces_opponent'] for u in camps)
            path=self.folder/f'view-seat-{seat}.png'
            self.command(peer,'screenshot',filename=str(path))
            self.wait('peer screenshot complete',lambda:path.exists() and path.read_bytes().endswith(b'IEND\xaeB`\x82'))
            write_json(self.folder/f'view-seat-{seat}.state.json',self.read(peer))
            self.captures[f'view-seat-{seat}']=str(path)
        self.checked('Both rendered seats show their own hand only, two pens and six correctly oriented camps')

    def status_controls(self):
        before=[copy.deepcopy(self.snapshot(peer)) for peer in ('a','b')]
        original_hud=copy.deepcopy(self.hud())
        keys={'own_stats':'own_stats_open','enemy_stats':'enemy_stats_open','history':'field_history_open'}
        for key,field in keys.items():
            initial=self.hud()[field]
            for opened in (not initial,initial):
                entry=self.wait('status control arranged',lambda:next((b for b in self.hud()['status_buttons'] if b['id']==key and b['allocated_size'][0]>1),None))
                self.click(center(entry))
                self.wait('status visibility toggles',lambda:self.hud()[field]==opened)
                # Visibility state is published before the next Slate layout;
                # let the following button acquire its rebuilt geometry.
                time.sleep(.5)
                assert all(self.hud()[other]==original_hud[other] for other in keys.values() if other!=field)
        assert [self.snapshot(peer) for peer in ('a','b')]==before
        self.checked('Own stats, enemy stats and history hide independently without changing the match')

    def invalid_and_stale_drags(self):
        self.round()
        action=next(a for a in self.snapshot()['actions'] if a['command']['type']=='draw')
        drag=self.start(-3000,self.point(-3000))
        destination=next(t['screen'] for t in drag['targets'] if t['command']==action['command'])
        # A separate valid server action changes the revision while held.
        self.submit('a',action)
        self.wait('stale drag clears',lambda:self.hud()['deployment']['card']==-1)
        after=copy.deepcopy(self.snapshot()['view'])
        self.event('up',destination)
        time.sleep(.4)
        assert self.snapshot()['view']==after,'Stale release executed another move'
        self.checked('A changed authoritative revision cancels the held drag without a second move')
        self.round()
        before=copy.deepcopy(self.snapshot()['view'])
        self.start(-3000,self.point(-3000))
        self.event('move',(-20,-20));self.event('up',(-20,-20))
        self.wait('invalid drop clears',lambda:self.hud()['deployment']['card']==-1)
        assert self.snapshot()['view']==before
        enemy=next(c for c in field_cards(self.snapshot()) if c['owner']!=self.snapshot()['seat'] and c['type']=='camp')
        point=self.point(enemy['id'])
        self.event('move',point);self.event('down',point)
        self.event('move',(point[0]+25,point[1]+15));self.event('up')
        self.wait('illegal-source notice',lambda:bool(self.read().get('notice')))
        time.sleep(.5)
        self.capture('09-readable-notice')
        dismiss=next(b for b in self.hud()['status_buttons'] if b['id']=='dismiss_notice')
        self.click(center(dismiss))
        self.wait('notice dismissed',lambda:not self.read().get('notice'))
        assert self.snapshot()['view']==before
        self.checked('Invalid destinations and enemy-source drags spend nothing; notice dismisses through its button')

    def finish_match(self):
        pyro=next(c for c in field_cards(self.snapshot()) if c.get('card_id')=='barn_burner' and c['owner']==self.snapshot()['seat'])
        for hit in range(7):
            if self.snapshot()['view']['status']=='won':break
            action=next((a for a in self.snapshot()['actions'] if a['command'].get('source')==pyro['id']),None)
            if action is None:
                end=next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn')
                self.perform_drag(-3001,end,'Pass through the world signal during final battle')
                self.own_turn()
                action=next(a for a in self.snapshot()['actions'] if a['command'].get('source')==pyro['id'])
            gesture=self.perform_menu if hit%2==0 else self.perform_drag
            gesture(pyro['id'],action,f'Final battle attack {hit+1}')
            target=self.snapshot()['actions'][0]
            if hit%2==0:self.perform_drag(-3003,target,f'Final battle target {hit+1}')
            else:self.perform_menu(target['target'],target,f'Final battle target {hit+1}')
        assert self.snapshot()['view']['status']=='won',self.snapshot()['view']['status']
        assert self.snapshot()['view']['winner']==self.snapshot()['seat']
        self.settle_presentation();self.capture('10-field-only-victory')
        assert not self.hud()['battle_plan_open']
        self.checked('World controls finish a native match using right-click and drag choices with Battle Plan closed')

    def event_and_punk(self):
        self.own_turn()
        event=next(a for a in self.snapshot()['actions'] if a['category']=='play_event' and a.get('event_slot',-1)>=0)
        identity=event['command']['card']
        self.perform_drag(identity,event,'Drag event prop into its labelled event lane')
        assert any(c and c['id']==identity for c in self.snapshot()['view']['players'][self.snapshot()['seat']]['queue'])
        self.clear_choices()
        instant=self.seek(lambda a,s:a.get('category')=='play_event' and a.get('event_slot',0)==-1
            and self.own_hand().get(a['command'].get('card'),{}).get('card_id')=='ambush','immediate Ambush',max_actions=110)
        self.perform_drag(instant['command']['card'],instant,'Immediate Ambush uses the physical PLAY NOW event destination')
        self.clear_choices()
        junk=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='punk','punk junk',max_actions=110)
        self.perform_menu(junk['command']['card'],junk,'Right-click junk creates a pending punk recruit')
        pen=self.wait('recruit walks clear of gate',lambda:any(p['can_drag'] for p in self.hud()['punk_shelter']['crew']) and self.hud()['punk_shelter'])
        opponent=copy.deepcopy(self.hud()['enemy_punk_shelter'])
        recruit=next(p for p in pen['crew'] if p['can_drag'])
        self.capture('08-punk-clear-of-gate')
        token=recruit['token']
        self.start(token,self.point(token))
        self.cancel('Cancelling a punk drag preserves the required choice',escape=True)
        # Cancellation returns that resident home; another can step out to
        # satisfy the same outstanding legal placement.
        replacement=self.wait('a recruit ready again',lambda:next((p for p in self.hud()['punk_shelter']['crew'] if p['can_drag']),None))
        token=replacement['token']
        action=next(a for a in self.snapshot()['actions'] if a.get('placement',{}).get('punk'))
        self.perform_drag(token,action,'Deploy recruit from own Punk Pen')
        self.clear_choices()
        assert opponent['available']==0 and self.hud()['enemy_punk_shelter']['available']==0
        self.checked('Own recruitment and enemy Punk Pen remain independent')

    def close_view(self, identity, label, distance=1000):
        """Frame a real entity using only ordinary camera gestures."""
        before = [copy.deepcopy(self.snapshot(peer)) for peer in ('a', 'b')]
        unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == identity)
        width, height = self.hud_dimensions()
        viewport = self.hud()['viewport_size']
        spot = (width * .5, height * .3)
        for _ in range(4):
            camera = self.camera_state()
            delta = [unit['location'][axis] - camera['focus'][axis] for axis in range(2)]
            yaw = math.radians(camera['yaw'])
            right, forward = (-math.sin(yaw), math.cos(yaw)), (-math.cos(yaw), -math.sin(yaw))
            dx = -sum(a*b for a,b in zip(delta,right))/(camera['distance']*.0012)
            dy = sum(a*b for a,b in zip(delta,forward))/(camera['distance']*.0012)
            self.event('down',spot,button='middle')
            self.event('move',(spot[0]+dx*width/viewport[0],spot[1]+dy*height/viewport[1]),button='middle')
            self.event('up',button='middle')
        self.event('wheel',spot,wheel=math.log(distance/self.camera_state()['distance'])/math.log(.84))
        self.event('move',(width*.5,height*.93))
        time.sleep(.8)
        self.capture(label)
        assert [self.snapshot(peer) for peer in ('a','b')] == before, 'Visual inspection changed game state'
        self.reset_camera()

    def perform_menu(self, entity, action, label):
        point=self.point(entity)
        self.event('move',point)
        self.event('down',point,button='right')
        self.event('up',point,button='right')
        self.wait('right-click offers exact legal command',lambda:any(a['command']==action['command'] for a in self.hud()['context_actions']))
        # Menu entries show the Western presentation of the HUD's label for this exact command:
        # live copies carry their own crew name, so translate the HUD label, not the canonical one.
        hud_label=next((a['label'] for a in self.hud()['context_actions'] if a['command']==action['command']),action['label'])
        shown=(action['label'],translate(action['label']),hud_label,translate(hud_label))
        entry=self.wait('menu entry arranged',lambda:next((e for e in self.hud()['context_entries'] if e['id'].startswith(shown) and e['allocated_size'][0]>1),None))
        before=self.snapshot()['view']['revision']
        self.click(center(entry))
        self.wait('right-click action committed',lambda:self.agree() and self.snapshot()['view']['revision']==before+1)
        self.settle_presentation()
        self.checked(label)

    def damage_visuals(self):
        self.round()
        pyro=next(c for c in field_cards(self.snapshot()) if c.get('card_id')=='barn_burner')
        ability=next(a for a in self.snapshot()['actions'] if a['command'].get('source')==pyro['id'])
        self.perform_menu(pyro['id'],ability,'Right-click person activates camp attack')
        target=self.snapshot()['actions'][0]
        self.perform_drag(-3003,target,'Required attack target selected by Bunkhouse drag')
        self.clear_choices()
        self.event('move',(self.hud_dimensions()[0]*.5,self.hud_dimensions()[1]*.93))
        self.capture('04-camp-damage-fire')
        damaged=next(c for c in field_cards(self.snapshot()) if c.get('type')=='camp' and c.get('damage')==1)
        visual=next(u for u in self.read()['cinematic']['units'] if u['id']==damaged['id'])
        assert visual['visible_damage_fire_parts']>0,visual
        self.close_view(damaged['id'],'04b-camp-fire-close',1400)
        soldier=self.seek(lambda a,s:a['command']['type']=='play' and self.own_hand().get(a['command'].get('card'),{}).get('card_id')=='civil_war_veteran','Civil War Veteran',max_actions=110)
        person=soldier['command']['card']
        labels=self.wait('crowded hand labels arranged',lambda: self.hud()['battlefield_labels'])
        hand_ids=set(self.own_hand())
        missing=hand_ids-{label['id'] for label in labels}
        assert not missing, f'Crowded hand has inaccessible labels: {missing}'
        bottom=self.hud()['battlefield_rect'][3]
        assert all(label['rect'][3]<bottom for label in labels), 'A card label overlaps the bottom prompt'
        self.capture('04c-crowded-hand-access')
        self.checked('All accumulated hand cards retain accessible names above the bottom prompt')
        self.perform_menu(person,soldier,'Right-click staged Civil War Veteran deploys')
        self.clear_choices()
        self.settle_presentation()
        self.capture('05-injured-person-kneeling')
        unit=next(u for u in self.read()['cinematic']['units'] if u['id']==person)
        assert unit['active_clip']=='Injured_Kneeling',unit
        joints=unit['injury_joints']
        assert max(joints['LeftLeg'][2],joints['RightLeg'][2])<25,joints
        assert joints['Hips'][2]>max(joints['LeftLeg'][2],joints['RightLeg'][2])+20,joints
        self.checked('Injured person has both knees near ground and upright hips')
        self.close_view(person,'05b-injured-person-close',800)
        junk=next(a for a in self.snapshot()['actions'] if a['command']['type']=='junk' and 'restore' in a['label'])
        self.perform_drag(junk['command']['card'],junk,'Junk staged event at Junk to restore')
        choice=next(a for a in self.snapshot()['actions'] if a.get('target')==person)
        self.perform_menu(person,choice,'Right-click injured person selects restoration')
        restored=next(u for u in self.read()['cinematic']['units'] if u['id']==person)
        assert restored['damage']==0 and restored['active_clip']!='Injured_Kneeling',restored
        self.close_view(person,'05c-restored-person-standing',800)
        self.checked('Restoration returns injured person to standing')

        self.perform_menu(-3001,next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn'),'Right-click Pass Turn')
        # Opponent uses its private legal hand; the rendered peer receives only
        # the resulting public camp restoration, never that hand's contents.
        junk=next(a for a in self.snapshot('b')['actions'] if a['command']['type']=='junk' and 'restore' in a['label'])
        self.submit('b',junk)
        self.submit('b',next(a for a in self.snapshot('b')['actions'] if a.get('target')==damaged['id']))
        self.settle_presentation()
        healed=next(u for u in self.read()['cinematic']['units'] if u['id']==damaged['id'])
        assert healed['visible_damage_fire_parts']==0,healed
        self.capture('06-restored-camp-fire-extinguished')
        self.checked('Opponent restoration extinguishes camp damage flames')
        for hit in range(2):
            self.own_turn()
            attack=next(a for a in self.snapshot()['actions'] if a['command'].get('source')==pyro['id'])
            self.perform_drag(pyro['id'],attack,f'Drag person to activate camp attack {hit+1}')
            target=next(a for a in self.snapshot()['actions'] if a.get('target')==damaged['id'])
            self.perform_menu(damaged['id'],target,f'Right-click camp attack target {hit+1}')
            if hit==0:self.round()
        ruined=next(c for c in field_cards(self.snapshot()) if c['id']==damaged['id'])
        assert ruined['destroyed'],ruined
        visual=next(u for u in self.read()['cinematic']['units'] if u['id']==damaged['id'])
        assert visual['visible_damage_fire_parts']==0,visual
        self.close_view(damaged['id'],'07-ruined-camp',1400)
        self.checked('Second damage destroys camp and removes active damage fire')
    def point(self, entity):
        return self.wait('visible world label', lambda: next((x['screen'] for x in
            self.hud().get('battlefield_labels', []) if x['id'] == entity), None))

    def perform_drag(self, entity, action, label):
        before = copy.deepcopy(self.snapshot())
        deployment = self.start(entity, self.point(entity))
        target = next(t for t in deployment['targets'] if self.target_offers(t,action['command']))
        self.event('move', target['screen'])
        self.wait('destination highlighted', lambda: self.hud()['deployment']['hovered'] >= 0)
        self.capture(label+'-preview')
        self.event('up', target['screen'])
        self.accept_drop_choice(target,action['command'],before['view'])
        self.wait('one authoritative move', lambda: self.agree() and
            self.snapshot()['view']['revision'] == before['view']['revision']+1)
        if action.get('category')=='play_event':
            expected_kind='event_resolve' if action.get('event_slot',0)<0 else 'event_play'
            self.wait('event receives its own visible presentation',lambda:self.read()['cinematic'].get('kind')==expected_kind)
            assert not self.hud()['controls_visible'] and not self.hud()['chrome_visible']
            assert not self.hud()['battlefield_labels'], 'World labels obscure the event presentation'
            self.capture('event-play-cinematic-'+str(entity))
            self.checked('Played event has a dedicated presentation with distracting overlays hidden')
        self.settle_presentation()
        assert not self.hud()['battle_plan_open']
        self.checked(label)

    def run(self):
        try:
            self.boot()
            self.verify_both_views()
            self.status_controls()
            self.capture('02-world-hand-layout')
            assert not self.hud()['battle_plan_open']
            assert not self.hud()['field_buttons']
            hand = self.snapshot()['view']['players'][self.snapshot()['seat']]['hand']
            labels = {x['id'] for x in self.hud()['battlefield_labels']}
            assert all(c['id'] in labels for c in hand), 'Own staged hand missing accessible names'
            assert 'hand' not in self.snapshot()['view']['players'][1-self.snapshot()['seat']]
            self.checked('Own hand has world actors; opponent snapshot has no private hand; bottom controls removed')
            action = next(a for a in self.snapshot()['actions'] if a['command']['type']=='draw')
            deployment = self.start(-3000, self.point(-3000))
            self.cancel('Supply drag cancellation leaves the authoritative state unchanged', escape=True)
            self.perform_drag(-3000, action, 'Draw from physical supply')
            action = next(a for a in self.snapshot()['actions'] if a['command']['type']=='end_turn')
            self.perform_drag(-3001, action, 'Pass turn with physical signal')
            self.own_turn()
            action = self.seek(lambda a,s: a['command']['type']=='play' and a.get('category')=='play_person', 'playable person', max_actions=40)
            self.perform_drag(action['command']['card'], action, 'Deploy actual staged person')
            self.clear_choices()
            self.own_turn()
            action = next(a for a in self.snapshot()['actions'] if a['command']['type']=='silo')
            self.perform_drag(-3002, action, 'Store water through silo drag')
            self.capture('03-staging-after-moves')
            if not self.args.skip_damage:self.damage_visuals()
            self.event_and_punk()
            self.invalid_and_stale_drags()
            if self.args.finish_match:self.finish_match()
            result = dict(ok=True, checks=self.checks, screenshots=self.captures,
                runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            if self.runtime.package_root:
                root=self.runtime.package_root
                binary=next(p for p in (root/'OldWest/Binaries/Linux/OldWestGame',root/'OldWest/Binaries/Linux/OldWestGame-Linux-Development') if p.is_file())
                result['package_directory']=str(root)
                result['artifacts']=[file_signature(p) for p in (binary,root/'package-manifest.json',root/'launch_battle_of_the_old_west.sh')]
            write_json(self.folder/'result.json',result)
            return result
        except Exception as error:
            try:self.capture('failure')
            except Exception:pass
            write_json(self.folder/'result.json',dict(ok=False,error=str(error),checks=self.checks))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR)
    p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720)])
    p.add_argument('--ruleset',default='base_2024')
    p.add_argument('--seed',type=int,default=94)
    p.add_argument('--port',type=int,default=20761)
    p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--settle',type=float,default=.3)
    p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    p.add_argument('--skip-damage',action='store_true',help='Check field controls/event/recruitment without repeating the separately verified damage scenario')
    p.add_argument('--both-views',action='store_true',help='Render and verify both local hand perspectives')
    p.add_argument('--finish-match',action='store_true',help='Continue the legal scenario to victory using actual world gestures')
    args=p.parse_args()
    out=args.output or create_native_run_directory('oldwest-staging-')
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,size in enumerate(args.resolutions):results.append(StagingScenario(args,out,size,i).run())
    write_json(out/'result.json',dict(ok=True,results=results))

if __name__=='__main__':main()
