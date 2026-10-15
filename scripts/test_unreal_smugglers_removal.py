"""Verify landing terrain through legal battlefield damage, ruin and removal."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_wanted_board import WantedBoardScenario


class RemovalScenario(QueueScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.conditions = {}
        self.notes = {}

    def boot(self):
        if self.args.render_seat==0:WantedBoardScenario.boot(self)
        else:super().boot()

    def capture_tooltips(self):
        self.wait('compiled landing scene',lambda:self.hud()['portraits']['compilation']['ready'],120)
        self.original_material = self.hud()['region']['landing_restore_material']
        assert self.original_material
        self.check_condition('healthy')

    def check_condition(self, condition):
        expected = self.plan['checkpoints'][condition]
        snapshots = {peer:copy.deepcopy(self.snapshot(peer)) for peer in ('a','b')}
        for snapshot in snapshots.values():
            assert snapshot['view']==expected[snapshot['seat']]['view'], condition+': state mismatch'
            assert snapshot['actions']==expected[snapshot['seat']]['actions'], condition+': legal action mismatch'
            assert 'hand' not in snapshot['view']['players'][1-snapshot['seat']]
        def cleared():
            region=self.hud()['region']
            unit=next((u for u in self.read()['cinematic']['units'] if u['id']==self.plan['holding']),None)
            return not region['landing_foundations'] and not region['landing_material'] and (not unit or unit['hidden'])
        if condition in ('removed','complete'):
            self.wait('removed landing releases terrain',cleared,30)
        region=copy.deepcopy(self.hud()['region'])
        unit=next((u for u in self.read()['cinematic']['units'] if u['id']==self.plan['holding']),None)
        assert region['index']==self.args.region and region['original_collider_retained']
        if condition in ('removed','complete'):
            assert region['surface_material']==self.original_material
            assert not region['landing_restore_material']
        else:
            assert len(region['landing_foundations'])==1
            assert region['surface_material']==region['landing_material']
            assert unit and not unit['hidden']
            visible=[p['mesh'] for p in unit['holding_components'] if p['visible']]
            if condition=='ruined':
                assert any('/SM_HoldingRuin_SmugglersLanding.' in mesh for mesh in visible),visible
                assert not any('/SM_Holding_SmugglersLanding.' in mesh for mesh in visible)
            else:assert any('/SM_Holding_SmugglersLanding.' in mesh for mesh in visible)
        self.capture('landing-condition-'+condition)
        self.conditions[condition]=dict(snapshots=snapshots,region=region,holding=copy.deepcopy(unit))
        write_json(self.folder/'condition-checks.json',self.conditions)

    def observe(self, state):
        super().observe(state)
        if state.get('cinematic',{}).get('busy',True):return
        revision=self.snapshot().get('view',{}).get('revision')
        for condition,expected in self.plan['checkpoints'].items():
            if condition not in self.conditions and revision==expected[0]['view']['revision']:
                self.check_condition(condition)

    def run(self):
        self.build['removal_harness']=signature(__file__)
        try:return super().run()
        finally:
            path=self.folder/'result.json';r=json.loads(path.read_text())
            r['landing_removal']=dict(conditions=self.conditions,region=self.args.region,rendered_seat=self.args.render_seat,
                scope='Exact legal states/actions and settled terrain/material/mesh conditions. No broad visual quality, audio or interruption claim.')
            r['ok']=bool(r.get('ok') and set(self.conditions)==set(self.plan['checkpoints']))
            write_json(path,r)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--render-seat',type=int,choices=(0,1),default=0)
    parser.add_argument('--region',type=int,choices=(0,1,2),default=1)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/holdings/expansion-game-v001/smugglers-landing/removal-plan-v001.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text());assert plan['ok']
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor,args.package_dir,args.port,args.timeout=EDITOR,None,21309+args.render_seat*10,600
    args.seed,args.ruleset,args.max_actions=plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind=0,[],['damage']
    args.extra_render_commands,args.profile_renderer,args.require_fuse=[],False,False
    args.native_extra_args=[f'-OldWestRegionReview={args.region}']
    args.scenario_config=dict(name='smugglers_removal',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    RemovalScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('failure') or result.get('issues')
    print('SMUGGLERS_REMOVAL_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':main()
