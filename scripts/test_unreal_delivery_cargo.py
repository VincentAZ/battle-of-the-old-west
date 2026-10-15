"""Verify one through four cargo items against real public delivery batches."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_event_queue import QueueScenario
from test_unreal_delivery import validate_delivery
from test_unreal_action_showcase import capture_subject,phase_of,signature
from test_unreal_interactions import ROOT,EDITOR,write_json


class CargoScenario(QueueScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.batches={b['sequence']:b for b in self.plan['cargo_batches']}
        self.cargo_samples={}
        for name in ['test_unreal_delivery_cargo.py','test_unreal_delivery.py']:
            self.build[name]=signature(ROOT/'scripts'/name)
        self.build['delivery_component']=signature(ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestDeliveryVisuals.cpp')
        write_json(self.folder/'build.json',self.build)

    def capture_tooltips(self):
        self.wait('supply shaders ready',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)

    def observe(self,state):
        super().observe(state)
        c=state.get('cinematic',{})
        if not c.get('busy'):return
        for d in c.get('deliveries',[]):
            validate_delivery(d)
            batch=self.batches[c['sequence']]
            assert c['kind']==batch['type'] and c['player']==batch['player']
            assert d['cargo_count']==batch['count']
            assert d['whiskey']==(batch['type']=='water')
            self.cargo_samples.setdefault(c['sequence'],[]).append(copy.deepcopy(d))

    def capture_phase(self,state):
        c=state.get('cinematic',{})
        if c.get('sequence') not in self.batches:return super().capture_phase(state)
        captures=set(self.valid_captures);subjects=set(self.valid_subject_captures);arrivals=set(self.valid_delivery_captures)
        kind=c['kind'];phase=phase_of(c)
        self.valid_captures.discard((kind,phase))
        self.valid_subject_captures.discard((kind,*capture_subject(c),phase))
        self.valid_delivery_captures.discard(kind)
        try:super().capture_phase(state)
        finally:
            self.valid_captures.update(captures);self.valid_subject_captures.update(subjects);self.valid_delivery_captures.update(arrivals)

    def run(self):
        try:return super().run()
        finally:
            report=json.loads((self.folder/'result.json').read_text());coverage=[]
            for seq,batch in self.batches.items():
                rows=self.cargo_samples.get(seq,[])
                moving=any(d['walking'] and 1<d['travel_cm']<d['route_cm']-1 for d in rows)
                settled=any(not d['walking'] and all(a['entry_alpha']>=.999 for a in d['animals']) for d in rows)
                captures=[c for c in self.capture_records if c['sequence']==seq and c['actual_phase_bracket_valid']]
                arrived=any(c.get('delivery_arrived_capture_valid') for c in captures)
                coverage.append(dict(**batch,samples=len(rows),moving=moving,settled_idle=settled,
                    arrived_capture=arrived,captures=captures,passed=bool(moving and settled and arrived)))
            complete=all(b['passed'] for b in coverage) and {b['count'] for b in coverage}=={1,2,3,4}
            report.update(ok=report['ok'] and complete,cargo_coverage=coverage,
                cargo_limits=['Public batches of one through four items only. Five/six-item capacity is not asserted as reached by this legal replay.'])
            write_json(self.folder/'cargo-samples.json',self.cargo_samples);write_json(self.folder/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/delivery/cargo-gameplay-plan.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor=EDITOR;args.package_dir=None;args.port=20039;args.timeout=450
    args.seed=plan['seed'];args.ruleset=plan['ruleset'];args.max_actions=len(plan['journal'])-2
    args.settle=0;args.prefer_camp=[];args.require_kind=['draw_card','discard','water'];args.extra_render_commands=[]
    args.profile_renderer=False;args.require_fuse=False
    args.scenario_config=dict(name='cargo-delivery',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True);CargoScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('issues');print('CARGO_DELIVERY_NATIVE',[(b['count'],b['samples']) for b in result['cargo_coverage']],flush=True)


if __name__=='__main__':main()
