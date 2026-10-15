"""Verify ordinary Skip and reconnect while a real delivery is moving."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_event_queue import QueueScenario
from test_unreal_delivery import validate_delivery
from test_unreal_action_showcase import signature
from test_unreal_interactions import ROOT,EDITOR,write_json


class InterruptionScenario(QueueScenario):
    def __init__(self,*args):
        super().__init__(*args)
        refills=[e['sequence'] for j in self.plan['journal'][2:] for e in j['public_events'] if e['type']=='water' and e['detail']]
        assert len(refills)>=3
        self.interrupt_at={refills[0]:'skip',refills[1]:'reconnect'};self.completed={}
        self.build['interruption_harness']=signature(__file__)
        self.build['delivery_component']=signature(ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestDeliveryVisuals.cpp')
        write_json(self.folder/'build.json',self.build)

    def capture_tooltips(self):
        self.wait('supply shaders ready',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)

    def observe(self,state):
        super().observe(state)
        c=state.get('cinematic',{})
        for d in c.get('deliveries',[]):validate_delivery(d)
        snapshot=state.get('snapshot',{})
        if snapshot.get('hosted') and 'view' in snapshot:
            enemy=snapshot['view']['players'][1-snapshot['seat']]
            assert 'hand' not in enemy and 'offers' not in enemy
            for col in enemy['columns']:
                for card in col:
                    assert 'private_peek' not in card
                    if card.get('punk'):assert str(card['id']) not in snapshot.get('cosmetics',{})

    def clear_delivery(self):
        c=self.read().get('cinematic',{});counts=c.get('delivery_component_counts',{})
        return not c.get('busy',True) and not c.get('deliveries') and not c.get('action_effects') and counts=={'roots':0,'parts':0}

    def wait_for_render(self):
        first_ready=None
        def stable_ready():
            nonlocal first_ready
            compilation=self.hud().get('portraits',{}).get('compilation',{})
            if not compilation.get('ready'):
                first_ready=None
                return False
            frame=compilation['frame']
            if first_ready is None:first_ready=frame
            return compilation if frame-first_ready>=3 else False
        return self.wait('post-interruption assets compiled and rendered',stable_ready,120)

    def capture_phase(self,state):
        c=state.get('cinematic',{});mode=self.interrupt_at.get(c.get('sequence'))
        deliveries=c.get('deliveries',[])
        if not mode or mode in self.completed or not deliveries or not .4<deliveries[0]['age']<1.7:
            return super().capture_phase(state)
        d=deliveries[0];assert d['walking'] and 0<d['travel_cm']<d['route_cm']
        counts=c['delivery_component_counts'];assert counts['roots']==1 and counts['parts']==len(d['parts'])+4
        record=dict(sequence=c['sequence'],moving_before=copy.deepcopy(d),components_before=counts,ok=False)
        self.completed[mode]=record
        self.capture('delivery-before-'+mode)
        before={p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
        if mode=='skip':
            self.command('a','skip_cinematics')
            self.wait('Skip removes every delivery component',self.clear_delivery)
        else:
            self.command('a','leave')
            self.wait('guest leaves during wagon motion',lambda:self.snapshot().get('hosted') is False and self.snapshot('b').get('connected')==1)
            self.command('a','join',address=f'127.0.0.1:{self.port}')
            self.wait('guest reconnects with original seat',self.agree,90)
            self.wait('reconnect has no stale delivery components or replay',self.clear_delivery,60)
        compilation=self.wait_for_render()
        assert self.clear_delivery(),'Stale delivery returned while assets compiled'
        after={p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
        assert before==after,'Presentation interruption changed authoritative views/actions or cosmetic filtering'
        current=self.read();self.observe(current)
        self.capture('delivery-after-'+mode)
        captured=self.read().get('hud',{}).get('portraits',{}).get('compilation',{})
        assert captured.get('ready'),'Screenshot crossed a new asset compilation'
        record.update(ok=True,components_after=current['cinematic']['delivery_component_counts'],
            compilation_before_capture=compilation,compilation_after_capture=captured,
            canonical_snapshots_unchanged=True,match_id=after['a']['match_id'],revision=after['a']['view']['revision'])
        write_json(self.folder/'interruption-checks.json',self.completed)

    def run(self):
        try:return super().run()
        finally:
            report=json.loads((self.folder/'result.json').read_text())
            complete=set(self.completed)=={'skip','reconnect'} and all(r['ok'] for r in self.completed.values())
            report.update(ok=report['ok'] and complete,delivery_interruptions=self.completed,
                interruption_limits=['Local rendered guest and listen host only. The first two refills are intentionally interrupted; natural completion is covered by the separate delivery replay.'])
            write_json(self.folder/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/whiskey/bonus-v002/gameplay-plan.json')
    args=parser.parse_args();plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor=EDITOR;args.package_dir=None;args.port=20029;args.timeout=450
    args.seed=plan['seed'];args.ruleset=plan['ruleset'];args.max_actions=len(plan['journal'])-2
    args.settle=0;args.prefer_camp=[];args.require_kind=['water'];args.extra_render_commands=[]
    args.profile_renderer=False;args.require_fuse=False
    args.scenario_config=dict(name='delivery-interruptions',policy='public_replay',target_kinds=['water'])
    args.output.mkdir(parents=True,exist_ok=True);InterruptionScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text());write_json(args.output/'result.json',result)
    assert result['ok'],result.get('issues');print('DELIVERY_INTERRUPTION_NATIVE',list(result['delivery_interruptions']),flush=True)


if __name__=='__main__':main()
