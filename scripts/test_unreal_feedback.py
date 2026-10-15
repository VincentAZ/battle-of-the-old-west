#!/usr/bin/env python3
"""Native pointer and screenshot checks for September 12 feedback."""
import argparse
import copy
import json
import time
from pathlib import Path
from test_unreal_field_layout import FieldLayoutScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class FeedbackScenario(FieldLayoutScenario):
    def key(self, key):
        for phase in ("down","up"):self.command("a","ui_key",key=key,phase=phase,preserve_focus=True)

    def point(self, card):
        entry = self.wait('visible card label', lambda: next((item for item in self.hud()['battlefield_labels'] if item['id'] == card), None))
        return entry['screen']

    def drag(self, card):
        point=self.point(card)
        self.event('move',point);self.event('down',point)
        self.event('move',(point[0]+16,point[1]-24))
        self.wait('world drag starts',lambda:self.hud()['deployment']['card']==card)
        return self.hud()['deployment']

    def drop_on(self, target):
        hud=self.hud()
        pixels=target['world_screen_pixels']
        point=tuple(pixels[i]*hud['hud_size'][i]/hud['viewport_size'][i] for i in (0,1))
        self.event('move',point);self.event('up',point)

    def action_controls(self):
        draw=self.seek(lambda a,_:a['command']['type']=='draw','paid draw')
        self.click(self.point(-3003))
        button=self.wait('war room draw arranged',lambda:next((b for b in self.hud()['status_buttons']
            if b['id'].startswith('war_action:') and json.loads(b['id'][11:])==draw['command'] and b['allocated_size'][0]>1),None))
        self.capture('06-war-room-actions')
        before=copy.deepcopy(self.snapshot()['view']);seat=self.snapshot()['seat']
        self.click(center(button))
        self.wait('war room draw accepted',lambda:self.agree() and self.snapshot()['view']['revision']>before['revision'])
        assert self.snapshot()['view']['players'][seat]['water']==before['players'][seat]['water']-2
        self.settle_presentation()
        self.checked('War room draw spends exactly two water through the authoritative command')
        draw=self.seek(lambda a,_:a['command']['type']=='draw','water-source draw')
        before=copy.deepcopy(self.snapshot()['view'])
        drag=self.drag(-4000)
        target=next(t for t in drag['targets'] if t['command']==draw['command'])
        assert target['target_card']==-3000
        self.drop_on(target)
        self.wait('physical Supply draw accepted',lambda:self.agree() and self.snapshot()['view']['revision']>before['revision'])
        assert self.snapshot()['view']['players'][seat]['water']==before['players'][seat]['water']-2
        self.settle_presentation()
        self.checked('One water source dropped at physical Supply draws for two water')
        silo=self.seek(lambda a,_:a['command']['type']=='silo','Silo storage')
        before=copy.deepcopy(self.snapshot()['view']);drag=self.drag(-4000)
        self.drop_on(next(t for t in drag['targets'] if t['command']==silo['command']))
        self.wait('Silo storage accepted',lambda:self.agree() and self.snapshot()['view']['revision']>before['revision'])
        mine=self.snapshot()['view']['players'][seat]
        assert mine['water']==before['players'][seat]['water']-1 and mine['silo_in_hand']
        self.settle_presentation()
        self.checked('Water source dropped at Silo stores exactly one water')
        draw=self.seek(lambda a,_:a['command']['type']=='draw','cancelled and stale water drag')
        before=copy.deepcopy(self.snapshot()['view']);self.drag(-4000)
        self.event('move',(-20,-20));self.event('up',(-20,-20))
        self.wait('invalid release cancels',lambda:self.hud()['deployment']['card']==-1)
        assert self.snapshot()['view']==before
        drag=self.drag(-4000)
        target=next(t for t in drag['targets'] if t['command']==draw['command'])
        self.submit('a',draw)
        self.wait('new revision cancels held drag',lambda:self.hud()['deployment']['card']==-1)
        after=copy.deepcopy(self.snapshot()['view'])
        self.drop_on(target);time.sleep(.4)
        assert self.snapshot()['view']==after
        self.settle_presentation()
        self.checked('Invalid and stale water drops cancel without an extra action or payment')
        junk=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='draw','draw junk')
        card=junk['command']['card'];before=copy.deepcopy(self.snapshot()['view'])
        drag=self.drag(card)
        target=next(t for t in drag['targets'] if t['command']==junk['command'] and t['target_card']==-3000)
        self.drop_on(target)
        self.wait('Supply junk accepted',lambda:self.agree() and self.snapshot()['view']['revision']>before['revision'])
        assert card not in self.own_hand()
        assert self.snapshot()['view']['players'][seat]['water']==before['players'][seat]['water']
        self.settle_presentation()
        self.checked('Hand card dropped at Supply applies its draw junk effect without spending water')

    def grouped_drop(self):
        for _ in range(8):
            draw=self.seek(lambda a,_:a['command']['type']=='draw','water for a shared destination')
            before=copy.deepcopy(self.snapshot()['view'])
            deployment=self.drag(-4000)
            target=next((t for t in deployment['targets'] if len(t.get('alternatives',[]))>1
                and all(a['command']['type']=='play' for a in t['alternatives'])),None)
            if target:break
            self.key('Escape');self.event('up')
            self.submit('a',draw)
        assert target, 'Ordinary draws did not produce a shared person-placement destination'
        chosen=target['alternatives'][0]['command']
        self.event('move',target['screen']);self.event('up',target['screen'])
        self.wait('shared destination opens a choice',lambda:any(e['allocated_size'][0]>1 for e in self.hud()['context_entries']))
        assert self.snapshot()['view']==before, 'Ambiguous release committed an action before selection'
        self.capture('07-shared-drop-choice')
        self.key('Escape');time.sleep(.3)
        assert self.snapshot()['view']==before
        self.checked('A shared destination opens an explicit choice; Escape cancels without changing the match')
        deployment=self.drag(-4000)
        target=next(t for t in deployment['targets'] if self.target_offers(t,chosen))
        self.event('move',target['screen']);self.event('up',target['screen'])
        self.accept_drop_choice(target,chosen,before)
        self.wait('selected shared destination command accepted',lambda:self.agree() and self.snapshot()['view']['revision']==before['revision']+1)
        assert chosen['card'] not in self.own_hand()
        self.settle_presentation()
        self.checked('Selecting a shared-destination option plays precisely the chosen hand card')

    def run(self):
        try:
            self.boot()
            before = [copy.deepcopy(self.snapshot(peer)['view']) for peer in ('a', 'b')]
            self.capture('02-feedback-default')
            hand = list(self.own_hand())
            assert len(hand) >= 2
            self.event('move',self.point(hand[0]))
            self.wait('card hover visible',lambda:self.hud()['card_hover']['visible'])
            hover=self.hud()['card_hover']
            assert hover['world_card']==hand[0]
            card=next(c for c in self.snapshot()['view']['players'][self.snapshot()['seat']]['hand'] if c['id']==hand[0])
            assert card['name'].upper() in hover['text'] and len(hover['text'].splitlines())>=2
            self.capture('02b-card-hover')
            for index, card in enumerate(hand[:2]):
                self.click(self.point(card))
                self.wait('card inspector switches', lambda: self.hud()['inspected_card'] == card)
                time.sleep(.4)
                self.capture(f'03-inspector-{index}')
            width, height = self.hud_dimensions()
            self.click((width*.5, height*.40))
            self.wait('empty board dismisses inspection', lambda: self.hud()['inspected_card'] == 0)
            self.checked('Native card clicks open and switch inspection; empty-board click dismisses')
            self.click(self.point(-3003))
            self.wait('Bunkhouse opens dedicated war room', lambda: self.hud()['war_room_open'])
            self.capture('04-war-room')
            self.click((width*.5, height*.78))
            self.wait('outside click dismisses war room', lambda: not self.hud()['war_room_open'])
            self.checked('Bunkhouse left-click opens a separate war room; outside click dismisses')
            assert self.hud()['rules_card_count'] == 104
            assert any(p['id'] == 'ability_reference' for p in self.hud()['dock_panels'])
            self.command('a', 'rules', open=True)
            self.wait('offline rules guide opens', lambda: self.hud()['rules_open'])
            self.capture('05-rules-guide')
            tab=self.wait('camp tab arranged',lambda:next((b for b in self.hud()['status_buttons'] if b['id']=='rules_tab:Camps' and b['allocated_size'][0]>1),None))
            self.click(center(tab))
            self.wait('camp guide visible',lambda:self.hud()['rules_category']=='Camps' and bool(self.hud()['rules_visible_cards']))
            all_camps=len(self.hud()['rules_visible_cards'])
            search=self.wait('rules search arranged',lambda:next((b for b in self.hud()['status_buttons'] if b['id']=='rules_search' and b['allocated_size'][0]>1),None))
            self.click(center(search));self.command('a','ui_text',text='Mercenary')
            for phase in ('down','up'):self.command('a','ui_key',key='Enter',phase=phase,preserve_focus=True)
            self.wait('card search filters content',lambda:'toll_bridge' in self.hud()['rules_visible_cards'] and len(self.hud()['rules_visible_cards'])<all_camps)
            self.capture('05b-mercenary-search')
            self.checked('Native text input and Enter filter the offline camp guide')
            self.command('a', 'rules', open=False)
            self.wait('rules closes', lambda: not self.hud()['rules_open'])
            assert [self.snapshot(peer)['view'] for peer in ('a', 'b')] == before
            self.checked('Offline guide loads all 104 explanations; viewing UI preserves both authoritative states')
            self.action_controls()
            self.grouped_drop()
            result = dict(ok=True, checks=self.checks, evidence=self.evidence, screenshots=self.captures,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder/'result.json', dict(ok=False,error=str(error),checks=self.checks,last_reports=self.reports))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280,720),(1920,1080)])
    parser.add_argument('--ruleset', default='boomtown')
    parser.add_argument('--seed', type=int, default=94)
    parser.add_argument('--port', type=int, default=20981)
    parser.add_argument('--timeout', type=float, default=400)
    parser.add_argument('--settle', type=float, default=.3)
    parser.add_argument('--max-setup-actions', type=int, default=240)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = [FeedbackScenario(args,args.output,size,i).run() for i,size in enumerate(args.resolutions)]
    write_json(args.output/'result.json',dict(ok=True,results=results))


if __name__ == '__main__':
    main()
