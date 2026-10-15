"""Replay legal medical deliveries to Quanah Parker and a generic crew member."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_event_queue import QueueScenario
from test_unreal_delivery import validate_delivery
from test_unreal_action_showcase import capture_subject,phase_of,signature
from test_unreal_interactions import ROOT,EDITOR,write_json


class MedicalScenario(QueueScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.medical={e['sequence']:e for e in self.plan['medical_events']}
        self.medical_samples={};self.other_deliveries=0
        for name in ['test_unreal_medical_delivery.py','test_unreal_delivery.py']:
            self.build[name]=signature(ROOT/'scripts'/name)
        for name in ['OldWestDeliveryVisuals.cpp','OldWestDeliveryVisuals.h']:
            self.build[name]=signature(ROOT/'game/OldWest/Source/OldWestGame/Private'/name)
        write_json(self.folder/'build.json',self.build)

    def capture_tooltips(self):
        self.wait('supply shaders ready',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)

    def observe(self,state):
        super().observe(state)
        c=state.get('cinematic',{})
        if not c.get('busy'):return
        for delivery in c.get('deliveries',[]):validate_delivery(delivery)
        event=self.medical.get(c.get('sequence'))
        if not event:
            self.other_deliveries+=len(c.get('deliveries',[]));return
        if not c.get('deliveries'):return
        assert c['kind']=='restore' and c['target']==event['target']
        unit=next(u for u in c['units'] if u['id']==event['target'])
        if event['target']==self.plan['native_target']:
            assert unit['card_id']=='quanah_parker' and unit['visual_id']=='quanah-parker' and '/Quanah/SK_Quanah' in unit['visual_mesh'],unit
        deliveries=c['deliveries'];assert len(deliveries)==1
        d=deliveries[0];assert not d['whiskey'] and d['cargo_count']==1
        assert not any('Whiskey' in p['mesh'] or 'BonusWhiskeyGlass' in p['mesh'] for p in c['action_effects'])
        assert sum('/Engine/BasicShapes/Cube' in p['mesh'] for p in d['parts'])==2,'Missing medical cross'
        self.medical_samples.setdefault(c['sequence'],[]).append(dict(delivery=copy.deepcopy(d),target=copy.deepcopy(unit)))

    def capture_phase(self,state):
        c=state.get('cinematic',{})
        if c.get('sequence') not in self.medical:return super().capture_phase(state)
        captures=set(self.valid_captures);subjects=set(self.valid_subject_captures);arrivals=set(self.valid_delivery_captures)
        phase=phase_of(c);self.valid_captures.discard(('restore',phase))
        self.valid_subject_captures.discard(('restore',*capture_subject(c),phase))
        self.valid_delivery_captures.discard('restore')
        try:super().capture_phase(state)
        finally:
            self.valid_captures.update(captures);self.valid_subject_captures.update(subjects);self.valid_delivery_captures.update(arrivals)

    def run(self):
        try:return super().run()
        finally:
            report=json.loads((self.folder/'result.json').read_text());complete=set(self.medical_samples)==set(self.medical)
            coverage=[]
            for seq,event in self.medical.items():
                rows=self.medical_samples.get(seq,[])
                moving=any(r['delivery']['walking'] and 1<r['delivery']['travel_cm']<r['delivery']['route_cm']-1 for r in rows)
                idle=any(not r['delivery']['walking'] and all(a.get('entry_alpha',0)>=.999 for a in r['delivery']['animals']) for r in rows)
                captures=[c for c in self.capture_records if c['sequence']==seq and c['actual_phase_bracket_valid']]
                arrived=any(c.get('delivery_arrived_capture_valid') for c in captures)
                complete &= bool(moving and idle and arrived)
                coverage.append(dict(sequence=seq,target=event['target'],samples=len(rows),moving=moving,settled_idle=idle,arrived_capture=arrived,captures=captures))
            report.update(ok=report['ok'] and complete,medical_coverage=coverage,
                medical_limits=['Quanah target and generic crew medical cases only; other Native appearances, hospital movement, all cargo counts, skip/reconnect and all-region review remain.'])
            write_json(self.folder/'medical-samples.json',self.medical_samples);write_json(self.folder/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/delivery/medical-gameplay-plan.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor=EDITOR;args.package_dir=None;args.port=20019;args.timeout=450
    args.seed=plan['seed'];args.ruleset=plan['ruleset'];args.max_actions=len(plan['journal'])-2
    args.settle=0;args.prefer_camp=[];args.require_kind=['restore'];args.extra_render_commands=[]
    args.profile_renderer=False;args.require_fuse=False
    args.scenario_config=dict(name='medical-delivery',policy='public_replay',target_kinds=['restore'])
    args.output.mkdir(parents=True,exist_ok=True);MedicalScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('issues');print('MEDICAL_DELIVERY_NATIVE',[(r['target'],r['samples']) for r in result['medical_coverage']],flush=True)


if __name__=='__main__':main()
