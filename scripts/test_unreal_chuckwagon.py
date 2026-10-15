"""Native Chuckwagon readying, optional History and private-identity review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature, capture_subject, phase_of
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class ChuckwagonScenario(WantedBoardScenario):
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
            assert any('/SM_Holding_Chuckwagon.' in p['mesh'] for p in visible)
            ground=next(p for p in visible if '/SM_HoldingBase_Chuckwagon.' in p['mesh'])
            assert ground['ground_fit']['enabled']==1 and ground['ground_fit']['region']==self.args.region
            assert ground['ground_fit']['foundation_extent']==[100,255,65]
            self.preparations.append(dict(sequence=c['sequence'],source=c['source'],elapsed=c['elapsed'],holding=copy.deepcopy(holding)))

    def capture_phase(self,state):
        c=state.get('cinematic',{})
        if c.get('kind')=='ability' and c.get('source')==self.plan['holding']:
            phase=phase_of(c)
            self.valid_captures.discard(('ability',phase))
            self.valid_subject_captures.discard(('ability',*capture_subject(c),phase))
        QueueScenario.capture_phase(self,state)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        self.check_note(self.plan['holding'],'holding-chuckwagon')
        self.capture('chuckwagon-battlefield')

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        if action['command']['type']=='end_turn' and any(c['id']==self.plan['punk'] for c in field_cards(snapshot)):
            self.check_note(self.plan['punk'],'drifter')
            views=[next(c for c in field_cards(self.snapshot(p)) if c['id']==self.plan['punk']) for p in ('a','b')]
            assert all(c.get('punk') and not c.get('private_peek') and c.get('card_id','punk')=='punk' for c in views)
            unit=next(u for u in self.read()['cinematic']['units'] if u['id']==self.plan['punk'])
            assert unit['visual_id']=='punk' and unit['visual_mesh']=='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            # The exact legal replay has just activated Chuckwagon. Compare
            # readiness and damage in both authoritative public views.
            expected={c['id']:c for c in self.plan['after_ready']['own_board']}
            readiness=[]
            for peer in ('a','b'):
                snapshot=self.snapshot(peer)
                cards={c['id']:c for col in snapshot['view']['players'][0]['columns'] for c in col}
                assert set(cards)==set(expected)
                for identity,card in expected.items():
                    assert cards[identity]['ready']==card['ready']
                    assert cards[identity]['damage']==card['damage']
                assert snapshot['view']['players'][0]['water']==self.plan['after_ready']['water']
                readiness.append(copy.deepcopy(cards))
            self.privacy=dict(views=views,unit=copy.deepcopy(unit),readiness=readiness)
            self.capture('readying-result-generic-drifter')
        return action

    def run(self):
        self.build['chuckwagon_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json'
            result=json.loads(path.read_text())
            result['chuckwagon_review']=dict(history=self.notes,private_identity=self.privacy,
                preparation_samples=self.preparations,
                limits='One legal readying replay per rendered seat. Other identities/layouts, condition lifecycles, terrain fit, interruptions, audio and packaging remain.')
            ability_sequences={p['sequence'] for p in self.preparations}
            ability_capture=any(c['kind']=='ability' and c['sequence'] in ability_sequences and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid') for c in result['captures'])
            result['chuckwagon_review']['static_preparation_capture']=ability_capture
            result['chuckwagon_review']['rendered_seat']=self.args.render_seat
            result['chuckwagon_review']['region']=self.args.region
            result['ok']=bool(result['ok'] and ability_capture and self.privacy and set(self.notes)=={'holding-chuckwagon','drifter'}
                              and {p['source'] for p in self.preparations}=={self.plan['holding']})
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/chuckwagon/gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0,1], default=0)
    parser.add_argument('--region', type=int, choices=[0,1,2], default=1)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20339+args.render_seat*10,400
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter','damage','raid_launch']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='chuckwagon',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    ChuckwagonScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('CHUCKWAGON_NATIVE_PASSED',flush=True)


if __name__=='__main__':main()
