"""Native legal Jailhouse recruitment/restore, History and identity review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class JailhouseScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.target_states={}
        self.preparations=[]
        self.travel=[]

    def boot(self):
        if self.args.render_seat==0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        assert self.snapshot()['seat']==self.args.render_seat
        self.check_note(self.plan['holding'],'holding-jailhouse')
        self.capture('jailhouse-battlefield')

    def target_state(self,label,owner,damage,history=True):
        identity=self.plan['target']
        views=[next(c for c in field_cards(self.snapshot(p))if c['id']==identity)for p in ('a','b')]
        assert all(c['owner']==owner and c['damage']==damage and not c['punk']for c in views)
        unit=next(u for u in self.read()['cinematic']['units']if u['id']==identity)
        if self.target_states:
            original=self.target_states['before']['unit']
            assert unit['visual_mesh']==original['visual_mesh'],'Recruitment changed the physical Crew appearance'
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
            self.target_state('before',1,1)
            self.capture('wounded-enemy-before-recruitment')
        if command==dict(type='activate',source=self.plan['wanted'],ability=0):
            self.target_state('recruited',0,1)
            self.capture('same-veteran-after-recruitment')
        if command==dict(type='activate',source=self.plan['holding'],ability=1):
            punk=self.plan['punk']
            self.check_note(punk,'drifter')
            views={self.snapshot(p)['seat']:next(c for c in field_cards(self.snapshot(p))if c['id']==punk)for p in ('a','b')}
            assert views[0].get('private_peek') and not views[1].get('private_peek')
            assert all(c.get('card_id','punk')=='punk'for c in views.values())
            unit=next(u for u in self.read()['cinematic']['units']if u['id']==punk)
            assert unit['visual_id']=='punk' and unit['visual_mesh']=='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            self.privacy=dict(views=copy.deepcopy(views),rendered_seat=self.args.render_seat,unit=copy.deepcopy(unit))
            self.capture('private-inspection-stays-generic')
        return action

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='ability' and c.get('source')==self.plan['holding'] and c.get('impact_resolved'):
            assert not c.get('action_effects'),'Jailhouse preparation introduced generic mechanism props'
            self.preparations.append(dict(sequence=c['sequence'],elapsed=c['elapsed']))
        if c.get('busy') and c.get('kind')=='recruit_id':
            unit=next((u for u in c.get('units',[])if u['id']==self.plan['target']),None)
            if unit:self.travel.append(dict(sequence=c['sequence'],elapsed=c['elapsed'],unit=copy.deepcopy(unit)))
        if len(self.actions)==len(self.replay) and not c.get('busy') and 'restored' not in self.target_states:
            self.target_state('restored',0,0,history=False)

    def run(self):
        self.build['jailhouse_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json'
            result=json.loads(path.read_text())
            review=dict(history=self.notes,targets=self.target_states,private_identity=self.privacy,
                        preparation_samples=self.preparations,travel_samples=len(self.travel),rendered_seat=self.args.render_seat,
                        limits='One legal Veteran capture/restore chain per view; other identities, interrupted travel, regional layouts and packaging remain.')
            result['jailhouse_review']=review
            complete=(set(self.target_states)=={'before','recruited','restored'} and self.privacy
                      and {'holding-jailhouse','drifter'}<=set(self.notes) and self.preparations and self.travel)
            result['ok']=bool(result.get('ok') and complete)
            write_json(self.folder/'recruitment-samples.json',self.travel)
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/jailhouse/gameplay-plan-v001.json')
    parser.add_argument('--render-seat',type=int,choices=[0,1],default=0)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20079+args.render_seat*10,450
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter','damage','recruit_id','restore']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.scenario_config=dict(name='jailhouse',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    JailhouseScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure')or result.get('issues')
    print('JAILHOUSE_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':main()
