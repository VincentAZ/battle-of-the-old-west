"""Native Gunsmith History, ordinary recruitment and granted Drifter hit review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class GunsmithScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.preparations=[]

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('kind')=='ability' and c.get('impact_resolved') and c.get('source') in (self.plan['holding'],self.plan['punk']):
            assert not c.get('action_effects'), 'Western preparation introduced generic mechanism props'
            self.preparations.append(dict(sequence=c['sequence'],source=c['source'],elapsed=c['elapsed']))

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        self.check_note(self.plan['holding'],'holding-gunsmith')
        self.capture('gunsmith-battlefield')

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        if action['command'].get('source')==self.plan['punk']:
            self.check_note(self.plan['punk'],'drifter')
            views=[next(c for c in field_cards(self.snapshot(p)) if c['id']==self.plan['punk']) for p in ('a','b')]
            assert all(c.get('punk') and not c.get('private_peek') and c.get('card_id','punk')=='punk' for c in views)
            unit=next(u for u in self.read()['cinematic']['units'] if u['id']==self.plan['punk'])
            assert unit['visual_id']=='punk' and unit['visual_mesh']=='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            self.privacy=dict(views=views,unit=copy.deepcopy(unit))
            self.capture('granted-hit-still-generic-drifter')
        return action

    def run(self):
        self.build['gunsmith_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json'
            result=json.loads(path.read_text())
            result['gunsmith_review']=dict(history=self.notes,private_identity=self.privacy,
                preparation_samples=self.preparations,
                limits='One rendered owner and ordinary legal recruitment/hit. Opposite view, interruptions, other layouts/regions and packaging remain.')
            result['ok']=bool(result['ok'] and self.privacy and set(self.notes)=={'holding-gunsmith','drifter'}
                              and {p['source'] for p in self.preparations}=={self.plan['holding'],self.plan['punk']})
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/gunsmith/gameplay-plan-v001.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20069,400
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['ability','enter','damage']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.scenario_config=dict(name='gunsmith',policy='public_replay',target_kinds=['ability','enter','damage'])
    args.output.mkdir(parents=True,exist_ok=True)
    GunsmithScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('GUNSMITH_NATIVE_PASSED',flush=True)


if __name__=='__main__':main()
