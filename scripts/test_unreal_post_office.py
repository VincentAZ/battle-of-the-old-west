"""Legal two-peer Post Office draw, History, public cargo and hand privacy review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import capture_subject, phase_of, signature
from test_unreal_delivery import validate_delivery
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_wanted_board import WantedBoardScenario


class PostOfficeScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.draw_sequence=min(e['sequence'] for e in self.plan['journal'][-1]['public_events'] if e['type']=='draw_card')
        self.deliveries=[];self.preparations=[];self.final_views=None

    def boot(self):
        if self.args.render_seat==0:WantedBoardScenario.boot(self)
        else:QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        assert self.snapshot()['seat']==self.args.render_seat
        assert self.hud()['region']['index']==self.args.region
        self.check_note(self.plan['holding'],'holding-post-office')
        self.capture('post-office-battlefield')

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        if action['command']==dict(type='activate',source=self.plan['holding'],ability=0):
            views={self.snapshot(p)['seat']:self.snapshot(p)['view']['players'][0] for p in ('a','b')}
            for seat in (0,1):
                assert views[seat]['water']==self.plan['before_draw'][seat]['water']
                assert views[seat]['hand_count']==self.plan['before_draw'][seat]['hand_count']
            assert 'hand' not in views[1]
        return action

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='ability' and c.get('source')==self.plan['holding'] and c.get('impact_resolved'):
            assert not c.get('action_effects'),'Post Office introduced generic machinery'
            holding=next(u for u in c['units'] if u.get('id')==self.plan['holding'])
            parts=holding['holding_components']
            atlas=next(p for p in parts if '/SM_Holding_PostOffice.' in p['mesh'])['textures']
            assert atlas and all(t['resident_mips']==t['allowed_mips'] for t in atlas),'Holding atlas not resident at close-up'
            ground=next(p for p in parts if '/SM_HoldingBase_' in p['mesh'])
            assert ground['ground_fit']['enabled']==1 and ground['ground_fit']['region']==self.args.region
            assert all(abs(a-b)<.001 for a,b in zip(ground['ground_fit']['origin'],ground['location']))
            self.preparations.append(dict(sequence=c['sequence'],elapsed=c['elapsed']))
        if c.get('busy') and c.get('sequence')==self.draw_sequence:
            assert c['kind']=='draw_card' and c['count']==2
            for d in c.get('deliveries',[]):
                validate_delivery(d)
                assert d['cargo_count']==2 and not d['whiskey']
                self.deliveries.append(copy.deepcopy(d))
        if len(self.actions)==len(self.replay) and not c.get('busy') and self.final_views is None:
            self.final_views={self.snapshot(p)['seat']:copy.deepcopy(self.snapshot(p)['view']['players'][0]) for p in ('a','b')}
            for seat in (0,1):
                assert self.final_views[seat]['hand_count']==self.plan['after_draw'][seat]['hand_count']
                assert self.final_views[seat]['water']==self.plan['after_draw'][seat]['water']
            assert 'hand' not in self.final_views[1]
            actual={x['id']:x.get('card_id') for x in self.final_views[0]['hand']}
            assert all(actual[x['id']]==x['card_id'] for x in self.plan['drawn'])

    def capture_phase(self,state):
        c=state.get('cinematic',{})
        if c.get('sequence')!=self.draw_sequence:return super().capture_phase(state)
        captures=set(self.valid_captures);subjects=set(self.valid_subject_captures);arrivals=set(self.valid_delivery_captures)
        phase=phase_of(c);self.valid_captures.discard(('draw_card',phase))
        self.valid_subject_captures.discard(('draw_card',*capture_subject(c),phase))
        self.valid_delivery_captures.discard('draw_card')
        try:super().capture_phase(state)
        finally:
            self.valid_captures.update(captures);self.valid_subject_captures.update(subjects);self.valid_delivery_captures.update(arrivals)

    def run(self):
        self.build['post_office_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        self.build['delivery_validator']=signature(ROOT/'scripts/test_unreal_delivery.py')
        self.build['delivery_component']=signature(ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestDeliveryVisuals.cpp')
        write_json(self.folder/'build.json',self.build)
        try:return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json';result=json.loads(path.read_text())
            moving=any(d['walking'] and 1<d['travel_cm']<d['route_cm']-1 for d in self.deliveries)
            idle=any(not d['walking'] and all(a.get('entry_alpha',0)>=.999 for a in d['animals']) for d in self.deliveries)
            arrival=any(c['sequence']==self.draw_sequence and c.get('delivery_arrived_capture_valid') for c in self.capture_records)
            result['post_office_review']=dict(history=self.notes,rendered_seat=self.args.render_seat,
                final_player_views=self.final_views,preparation_samples=self.preparations,
                draw_sequence=self.draw_sequence,delivery_samples=len(self.deliveries),moving=moving,settled_idle=idle,arrival_capture=arrival,
                limits='One uninterrupted draw-two activation per rendered seat. Other layouts, regions, interruptions, audio and packaging remain.')
            result['ok']=bool(result.get('ok') and self.final_views and self.preparations and moving and idle and arrival
                              and set(self.notes)=={'holding-post-office'})
            write_json(self.folder/'draw-delivery-samples.json',self.deliveries);write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/post-office/gameplay-plan-v001.json')
    parser.add_argument('--render-seat',type=int,choices=[0,1],default=0)
    parser.add_argument('--region',type=int,choices=[0,1,2],default=1)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20099+args.render_seat*10,350
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['draw_card']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='post-office',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True);PostOfficeScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues') or result['post_office_review']
    print('POST_OFFICE_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':main()
