"""Native offered-command Rockslide Ridge, optional History and condition review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario

class RockslideRidgeScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.preparations=[];self.collapses=[];self.group_impacts=[];self.final_public=None

    def boot(self):
        if self.args.render_seat==0:WantedBoardScenario.boot(self)
        else:QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        assert self.snapshot()['seat']==self.args.render_seat
        self.check_note(self.plan['holding'],'holding-rockslide-ridge')
        self.capture('rockslide-ridge-battlefield')

    def choose_action(self,name,snapshot):
        return QueueScenario.choose_action(self,name,snapshot)

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        holding=next((u for u in c.get('units',[]) if u.get('id')==self.plan['holding']),None)
        if c.get('busy') and c.get('kind')=='ability' and c.get('source')==self.plan['holding'] and c.get('impact_resolved'):
            assert not c.get('action_effects'),'Ridge preparation spawned unrelated mechanism props'
            assert holding
            self.preparations.append(dict(sequence=c['sequence'],elapsed=c['elapsed'],holding=copy.deepcopy(holding)))
        if c.get('busy') and c.get('group_shot') and c.get('impact_resolved') and c.get('kind')=='destroy':
            members=[dict(target=c['target'],kind=c['kind'],displayed_damage=c['displayed_damage'],subject_frame=c['subject_frame'])]+c['simultaneous_targets']
            expected={(t['id'],'destroy') for t in self.plan['targets']} | {(self.plan['enemy_camp']['id'],'damage'),(self.plan['holding'],'destroy')}
            assert {(m['target'],m['kind']) for m in members}==expected
            assert all(m['displayed_damage']==(1 if m['kind']=='damage' else 2) for m in members)
            if c['elapsed']>.55:
                for member in members:
                    frame=member['subject_frame']
                    assert frame and frame['all_corners_in_front'] and not frame['hidden']
                    assert all(0<=v<=1 for v in frame['normalized_min']+frame['normalized_max']), 'Grouped impact crops a target'
                self.group_impacts.append(copy.deepcopy(members))
        if holding:
            ground=next(p for p in holding['holding_components'] if '/SM_HoldingBase_' in p['mesh'])
            fit=ground['ground_fit']
            assert fit and fit['enabled']==1 and fit['region']==self.args.region
            assert fit['foundation_extent']==[305,275,50]
            visible=[p for p in holding.get('holding_components',[]) if p['visible'] and '/SM_HoldingBase_' not in p['mesh']]
            if any('/SM_HoldingRuin_RockslideRidge.' in p['mesh'] for p in visible):
                assert len(visible)==1,'Collapsed ridge retains another condition mesh'
                self.collapses.append(dict(sequence=c.get('sequence'),elapsed=c.get('elapsed'),holding=copy.deepcopy(holding)))
        if len(self.actions)==len(self.replay) and not c.get('busy') and not self.final_public:
            snapshots={p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
            for snapshot in snapshots.values():
                cards=field_cards(snapshot)
                assert all(not any(c['id']==t['id'] for c in cards) for t in self.plan['targets'])
                ridge=next(c for c in cards if c['id']==self.plan['holding']);assert ridge['destroyed']
                camp=next(c for c in cards if c['id']==self.plan['enemy_camp']['id'])
                assert camp['damage']==self.plan['enemy_camp']['damage']+1
                seat=snapshot['seat'];assert 'hand' not in snapshot['view']['players'][1-seat]
            self.final_public=snapshots

    def run(self):
        self.build['rockslide_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json';result=json.loads(path.read_text())
            review=dict(history=self.notes,preparation_samples=len(self.preparations),collapse_samples=len(self.collapses),group_impact_samples=len(self.group_impacts),
                final_public=self.final_public,rendered_seat=self.args.render_seat,
                limits='One legal two-person enemy-column activation per view; other placements, damage/repair gameplay, interruption, regions, audio and packaging remain.')
            result['rockslide_ridge_review']=review
            result['ok']=bool(result.get('ok') and self.preparations and self.collapses and self.group_impacts and self.final_public and 'holding-rockslide-ridge' in self.notes)
            write_json(self.folder/'ridge-condition-samples.json',dict(preparations=self.preparations,collapses=self.collapses,group_impacts=self.group_impacts))
            write_json(path,result)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/rockslide-ridge/legal-rehearsal-v001.json')
    parser.add_argument('--render-seat',type=int,choices=[0,1],default=0)
    parser.add_argument('--region',type=int,choices=[0,1,2],default=1)
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20219+args.render_seat*10,450
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter','destroy']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    # Preparation is intentionally static; group members above verify damage
    # and all three destroys against their public targets and native states.
    args.scenario_config=dict(name='rockslide_ridge',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    RockslideRidgeScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('ROCKSLIDE_RIDGE_NATIVE_PASSED',args.render_seat,flush=True)

if __name__=='__main__':main()
