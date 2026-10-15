"""Native legal Army Surgeon's Tent treatment, Stampede and optional History review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class ArmySurgeonsTentScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.target_states={}
        self.preparations=[]
        self.travel=[]
        self.transfer_captures=set()

    def boot(self):
        if self.args.render_seat==0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        assert self.snapshot()['seat']==self.args.render_seat
        self.check_note(self.plan['holding'],'holding-army-surgeons-tent')
        assert self.hud()['region']['index']==self.args.region
        self.capture('army-surgeons-tent-battlefield')

    def target_state(self,label,owner,damage,history=True):
        identity=self.plan['target']
        views=[next(c for c in field_cards(self.snapshot(p))if c['id']==identity)for p in ('a','b')]
        assert all(c['owner']==owner and c['damage']==damage and not c['punk']for c in views)
        unit=next(u for u in self.read()['cinematic']['units']if u['id']==identity)
        if self.target_states:
            original=self.target_states['before']['unit']
            assert unit['visual_mesh']==original['visual_mesh'],'Treatment changed the physical Crew appearance'
        assert unit['bandage']['visible']==bool(damage),'Wound accessory did not follow public condition'
        keys={'/Game/Art/Western/Crew/CivilWarVeteran/SK_CivilWarVeteran.SK_CivilWarVeteran':'civil-war-veteran',
              '/Game/Art/Western/Crew/BuffaloSoldierVeteran/SK_BuffaloSoldierVeteran.SK_BuffaloSoldierVeteran':'buffalo-soldier-veteran'}
        key=keys[unit['visual_mesh']]
        if history:self.check_note(identity,key)
        self.target_states[label]=dict(views=copy.deepcopy(views),unit=copy.deepcopy(unit),history_key=key)

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        command=action['command']
        if command==dict(type='activate',source=self.plan['holding'],ability=0):
            self.target_state('before',0,1)
            self.capture('wounded-veteran-before-treatment')
        if command.get('type')=='end_turn' and 'before' in self.target_states and 'restored' not in self.target_states:
            self.target_state('restored',0,0)
            self.capture('same-veteran-after-treatment')
            views={self.snapshot(p)['seat']:copy.deepcopy(self.snapshot(p)['view']['players'])for p in ('a','b')}
            assert all('hand' not in views[seat][1-seat]for seat in (0,1))
            self.privacy=dict(rendered_seat=self.args.render_seat,player_views=views)
        return action

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='ability' and c.get('source')==self.plan['holding'] and c.get('impact_resolved'):
            assert not c.get('action_effects'),'Tent preparation introduced generic mechanism props'
            holding=next(u for u in c['units'] if u.get('id')==self.plan['holding'])
            ground=next(p for p in holding['holding_components'] if '/SM_HoldingBase_' in p['mesh'])
            fit=ground['ground_fit']
            assert fit and fit['enabled']==1 and fit['region']==self.args.region
            assert fit['foundation_extent']==[145,180,60]
            assert all(abs(a-b)<.001 for a,b in zip(fit['origin'],ground['location']))
            self.preparations.append(dict(sequence=c['sequence'],elapsed=c['elapsed']))
        if c.get('busy') and c.get('kind')=='hospital_id':
            unit=next((u for u in c.get('units',[])if u['id']==self.plan['target']),None)
            assert not c.get('deliveries'),'Transfer spawned a duplicate treatment wagon'
            assert not c.get('effect_framing'),'Transfer camera is pinned to a supply effect'
            frame=c.get('subject_frame',{})
            if unit:
                self.travel.append(dict(sequence=c['sequence'],elapsed=c['elapsed'],unit=copy.deepcopy(unit),
                                        subject_frame=copy.deepcopy(frame),camera_focus=c.get('camera_focus')))
                if c['elapsed']>.5:
                    assert frame.get('target')==self.plan['target'] and not frame.get('hidden')
                    assert frame.get('all_corners_in_front'),'Patient is behind the transfer camera'
                    assert all(0<=v<=1 for v in frame['normalized_min']+frame['normalized_max']), \
                        'Patient leaves the transfer camera frame'
        if len(self.actions)==len(self.replay) and not c.get('busy') and 'restored' not in self.target_states:
            self.target_state('restored',0,0,history=False)

    def capture_phase(self,state):
        super().capture_phase(state)
        current=self.read()
        c=current.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='hospital_id':
            unit=next((u for u in c.get('units',[])if u['id']==self.plan['target']),{})
            fraction=unit.get('travel_elapsed',0)/max(.01,unit.get('travel_duration',0))
            for label,threshold in [('transfer-midpoint',.45),('transfer-arrival',.90)]:
                if fraction>=threshold and label not in self.transfer_captures:
                    self.transfer_captures.add(label)
                    self.capture(label)

    def run(self):
        self.build['army_surgeons_tent_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json'
            result=json.loads(path.read_text())
            review=dict(history=self.notes,targets=self.target_states,private_identity=self.privacy,
                        preparation_samples=self.preparations,travel_samples=len(self.travel),rendered_seat=self.args.render_seat,
                        transfer_captures=sorted(self.transfer_captures),
                        limits='One legal Veteran treatment and Stampede activation per view; other identities, interrupted travel, layouts, regional fitting, audio and packaging remain.')
            result['army_surgeons_tent_review']=review
            complete=(set(self.target_states)=={'before','restored'} and self.privacy
                      and 'holding-army-surgeons-tent' in self.notes and self.preparations and self.travel
                      and self.transfer_captures=={'transfer-midpoint','transfer-arrival'})
            result['ok']=bool(result.get('ok') and complete)
            write_json(self.folder/'treatment-travel-samples.json',self.travel)
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/army-surgeons-tent/legal-rehearsal-v001.json')
    parser.add_argument('--render-seat',type=int,choices=[0,1],default=0)
    parser.add_argument('--region',type=int,choices=[0,1,2],default=1)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20139+args.render_seat*10,450
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter','damage','hospital_id','restore','raid_launch']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='army_surgeons_tent',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    ArmySurgeonsTentScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure')or result.get('issues')
    print('ARMY_SURGEONS_TENT_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':main()
