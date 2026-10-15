"""Native Free Homestead recruitment, optional History and private-identity review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class FreeHomesteadScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.preparations=[]

    def boot(self):
        if self.args.render_seat == 0: WantedBoardScenario.boot(self)
        else: QueueScenario.boot(self)

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='ability' and c.get('impact_resolved') and c.get('source') == self.plan['holding']:
            assert not c.get('action_effects'), 'Western preparation introduced generic mechanism props'
            holding=next(u for u in c['units'] if u['id']==self.plan['holding'])
            assert holding['animated_part_count']==0
            visible=[p for p in holding['holding_components'] if p['visible']]
            assert any('/SM_Holding_FreeHomestead.' in p['mesh'] for p in visible)
            ground=next(p for p in visible if '/SM_HoldingBase_FreeHomestead.' in p['mesh'])
            assert ground['ground_fit']['enabled']==1 and ground['ground_fit']['region']==self.args.region
            assert ground['ground_fit']['foundation_extent']==[240,210,60]
            self.preparations.append(dict(sequence=c['sequence'],source=c['source'],elapsed=c['elapsed'],holding=copy.deepcopy(holding)))

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        self.check_note(self.plan['holding'],'holding-free-homestead')
        self.capture('free_homestead-battlefield')

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        if action['command']['type']=='end_turn' and any(c['id']==self.plan['punk'] for c in field_cards(snapshot)):
            self.check_note(self.plan['punk'],'drifter')
            views=[next(c for c in field_cards(self.snapshot(p)) if c['id']==self.plan['punk']) for p in ('a','b')]
            assert all(c.get('punk') and not c.get('private_peek') and c.get('card_id','punk')=='punk' for c in views)
            unit=next(u for u in self.read()['cinematic']['units'] if u['id']==self.plan['punk'])
            assert unit['visual_id']=='punk' and unit['visual_mesh']=='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            self.privacy=dict(views=views,unit=copy.deepcopy(unit))
            self.capture('recruited-generic-drifter')
        return action

    def run(self):
        self.build['free_homestead_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json'
            result=json.loads(path.read_text())
            result['free_homestead_review']=dict(history=self.notes,private_identity=self.privacy,
                preparation_samples=self.preparations,
                limits='One legal recruitment replay per rendered seat. Other identities/layouts, condition lifecycles, terrain fit, interruptions, audio and packaging remain.')
            ability_capture=any(c['kind']=='ability' and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid') for c in result['captures'])
            result['free_homestead_review']['static_preparation_capture']=ability_capture
            result['free_homestead_review']['rendered_seat']=self.args.render_seat
            result['free_homestead_review']['region']=self.args.region
            result['ok']=bool(result['ok'] and ability_capture and self.privacy and set(self.notes)=={'holding-free-homestead','drifter'}
                              and {p['source'] for p in self.preparations}=={self.plan['holding']})
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/free-homestead/gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0,1], default=0)
    parser.add_argument('--region', type=int, choices=[0,1,2], default=1)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20309+args.render_seat*10,400
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='free_homestead',policy='public_replay',target_kinds=['enter'])
    args.output.mkdir(parents=True,exist_ok=True)
    FreeHomesteadScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('FREE_HOMESTEAD_NATIVE_PASSED',flush=True)


if __name__=='__main__':main()
