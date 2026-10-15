"""Native legal Lookout Ridge exposure, History and public-hand privacy review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, center, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class LookoutRidgeScenario(WantedBoardScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.preparations=[];self.exposures=[];self.public_checks={}

    def boot(self):
        if self.args.render_seat==0:WantedBoardScenario.boot(self)
        else:QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready',lambda:self.hud()['portraits']['compilation']['ready'],120)
        assert self.snapshot()['seat']==self.args.render_seat
        self.check_note(self.plan['holding'],'holding-lookout-ridge')
        self.capture('lookout-ridge-battlefield')

    def check_public(self,phase):
        snapshots={p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
        for snapshot in snapshots.values():
            seat=snapshot['seat'];players=snapshot['view']['players']
            assert 'hand' not in players[1-seat]
            cards=field_cards(snapshot)
            if phase=='exposed':
                assert all(not c['protected'] for c in cards)
                assert players[0]['water']==self.plan['cost']['after']
            else:
                for ids in self.plan['previously_protected'].values():
                    assert all(next(c for c in cards if c['id']==uid)['protected'] for uid in ids)
        self.public_checks[phase]=snapshots
        button=next(b for b in self.hud()['camera_buttons'] if b['id']=='ability_overview')
        self.event('move',center(button));self.event('down',center(button));self.event('up',center(button))
        self.wait('public ability overview open',lambda:self.hud()['overview_open'])
        self.capture('both-outfits-'+phase)
        button=next(b for b in self.hud()['camera_buttons'] if b['id']=='ability_overview')
        self.event('move',center(button));self.event('down',center(button));self.event('up',center(button))
        self.wait('public ability overview closed',lambda:not self.hud()['overview_open'])
        assert {p:self.snapshot(p) for p in ('a','b')}==snapshots,'Overview changed gameplay'

    def choose_action(self,name,snapshot):
        action=QueueScenario.choose_action(self,name,snapshot)
        if action['command']==dict(type='activate',source=self.plan['holding'],ability=0):
            self.check_public('protected')
        elif snapshot['view']['revision']==self.plan['after'][0]['view']['revision']:
            self.check_public('exposed')
        return action

    def observe(self,state):
        QueueScenario.observe(self,state)
        c=state.get('cinematic',{})
        if c.get('busy') and c.get('source')==self.plan['holding'] and c.get('kind') in ('ability','expose_all'):
            unit=next(u for u in c['units'] if u['id']==self.plan['holding'])
            assert unit['animated_part_count']==0
            visible=[p for p in unit['holding_components'] if p['visible']]
            assert any('/SM_Holding_LookoutRidge.' in p['mesh'] for p in visible)
            assert any('/SM_HoldingBase_LookoutRidge.' in p['mesh'] for p in visible)
            if self.args.require_ground_fit:
                ground=next(p for p in visible if '/SM_HoldingBase_LookoutRidge.' in p['mesh'])
                fit=ground['ground_fit']
                assert fit and fit['enabled']==1 and fit['region']==self.args.region
                assert fit['foundation_extent']==[305,195,60]
            assert not c.get('action_effects'),'Geological exposure spawned unrelated mechanism props'
            frame=c.get('subject_frame')
            if c['elapsed']>.55:
                assert frame and frame['all_corners_in_front'] and not frame['hidden']
                assert all(0<=v<=1 for v in frame['normalized_min']+frame['normalized_max'])
            row=dict(sequence=c['sequence'],elapsed=c['elapsed'],impact_resolved=c['impact_resolved'],
                     holding=copy.deepcopy(unit),subject_frame=copy.deepcopy(frame))
            (self.preparations if c['kind']=='ability' else self.exposures).append(row)
        if len(self.actions)==len(self.replay) and not c.get('busy') and 'restored' not in self.public_checks:
            self.check_public('restored')

    def run(self):
        self.build['lookout_harness']=signature(__file__)
        self.build['history_helper']=signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json',self.build)
        try:return QueueScenario.run(self)
        finally:
            path=self.folder/'result.json';result=json.loads(path.read_text())
            captured={kind:any(c['kind']==kind and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')
                              and c['requested_phase'] in ('impact','after-impact') for c in result['captures']) for kind in ('ability','expose_all')}
            result['lookout_ridge_review']=dict(history=self.notes,public_checks=self.public_checks,
                preparation_samples=len(self.preparations),exposure_samples=len(self.exposures),valid_static_captures=captured,
                rendered_seat=self.args.render_seat,region=self.args.region,
                required_ground_fit=self.args.require_ground_fit,
                limits='One legal replay per view with four faceup people. Opponent hand privacy checked. Ground-fit metadata is checked only when required; actual appearance needs separate visual review. Drifter/private-peek identities, other placements/lifecycles, interruptions, effects/audio and packaging remain.')
            result['ok']=bool(result.get('ok') and self.preparations and self.exposures and all(captured.values())
                              and set(self.public_checks)=={'protected','exposed','restored'} and 'holding-lookout-ridge' in self.notes)
            write_json(self.folder/'lookout-samples.json',dict(preparations=self.preparations,exposures=self.exposures))
            write_json(path,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/lookout-ridge/gameplay-plan-v001.json')
    parser.add_argument('--render-seat',type=int,choices=[0,1],default=0)
    parser.add_argument('--region',type=int,choices=[0,1,2],default=1)
    parser.add_argument('--require-ground-fit',action='store_true')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,20449+args.render_seat*10,450
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['enter']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='lookout_ridge',policy='public_replay',target_kinds=['enter'])
    args.output.mkdir(parents=True,exist_ok=True)
    LookoutRidgeScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('LOOKOUT_RIDGE_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':main()
