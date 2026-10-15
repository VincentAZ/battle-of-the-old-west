"""Replay legal bonus/refill actions and inspect the real native glass scene."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from test_unreal_event_queue import QueueScenario
from test_unreal_action_showcase import capture_subject, phase_of, signature
from test_unreal_interactions import EDITOR, ROOT, center, write_json


class BonusScenario(QueueScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.water_events={e['sequence']:e for j in self.plan['journal'][2:] for e in j['public_events'] if e['type']=='water'}
        self.bonus_samples={}; self.refill_samples={}; self.note=None
        self.build['bonus_harness']=signature(__file__); write_json(self.folder/'build.json',self.build)

    def capture_tooltips(self):
        self.wait('supply shaders ready',lambda:self.hud().get('portraits',{}).get('compilation',{}).get('ready'),120)

    def choose_action(self,name,snapshot):
        action=super().choose_action(name,snapshot)
        if action['command']=={'type':'junk','card':69}:
            baseline=[copy.deepcopy(self.snapshot(p)) for p in ('a','b')]
            assert self.snapshot('a')['seat']==snapshot['seat']
            assert self.own_hand('a')[69]['card_id']=='hip_flask'
            self.command('a','inspect',card=69)
            self.wait('Hip Flask selected',lambda:self.hud()['inspected_card']==69)
            def link(): return next((b for b in self.hud()['status_buttons'] if b['id']=='asset_history' and b['allocated_size'][0]>1),None)
            self.wait('optional supply history link',link); assert not self.hud()['asset_history']['open']
            position=center(link()); self.event('move',position); self.event('down',position); self.event('up',position)
            self.wait('supply history open',lambda:self.hud()['asset_history'].get('open'))
            self.note=self.hud()['asset_history']; assert self.note['key']=='whiskey-supplies'
            assert len(self.note['body'].splitlines())==3
            self.capture('bonus-whiskey-history')
            for phase in ('down','up'): self.command('a','ui_key',key='Escape',phase=phase,preserve_focus=True)
            self.wait('history closed',lambda:not self.hud()['asset_history'].get('open'))
            assert [self.snapshot(p) for p in ('a','b')]==baseline,'History changed an authoritative view'
        return action

    def observe(self,state):
        super().observe(state)
        c=state.get('cinematic',{}); event=self.water_events.get(c.get('sequence'))
        if not c.get('busy') or c.get('kind')!='water' or not event: return
        effects=c.get('action_effects',[])
        if not effects: return
        glass=[e for e in effects if 'SM_Action_BonusWhiskeyGlass' in e['mesh']]
        if event['detail']=='':
            assert len(glass)==1 and len(effects)==2, effects
            barrel=next(e for e in effects if 'SM_Action_WhiskeyBarrel' in e['mesh'])
            g=glass[0]
            assert c['caption']=='Round on the house'
            assert g['scale']==[4.5,4.5,4.5]
            assert all(e['collision_enabled']==0 for e in effects)
            assert math.dist(g['location'][:2],barrel['location'][:2])<.01
            assert abs(g['location'][2]-barrel['location'][2]-82.4)<.01
            # Both public fuse lines sit240cm inward from their event column.
            # At this legal supply anchor the barrel must leave the cord clear.
            assert abs(abs(barrel['location'][0])-2210)>80,'Bonus barrel covers the fuse'
            assert state['hud']['portraits']['compilation']['ready'],'Glass shaders compiled during bonus beat'
            self.bonus_samples.setdefault(c['sequence'],[]).append(copy.deepcopy(effects))
        else:
            assert not glass,'Ordinary refill displayed the bonus-only glass'
            self.refill_samples[c['sequence']]=dict(caption=c['caption'],effects=len(effects),detail=event['detail'])

    def capture_phase(self,state):
        c=state.get('cinematic',{})
        if c.get('sequence') not in self.water_events: return super().capture_phase(state)
        phase=phase_of(c); prior=set(self.valid_captures); subjects=set(self.valid_subject_captures)
        self.valid_captures.discard(('water',phase))
        self.valid_subject_captures.discard(('water',*capture_subject(c),phase))
        try: super().capture_phase(state)
        finally: self.valid_captures.update(prior); self.valid_subject_captures.update(subjects)

    def run(self):
        try: return super().run()
        finally:
            report=json.loads((self.folder/'result.json').read_text())
            required={s for s,e in self.water_events.items() if e['detail']==''}
            captures=[c for c in self.capture_records if c['sequence'] in required and c['actual_phase_bracket_valid']]
            complete=(set(self.bonus_samples)==required and bool(required) and bool(self.refill_samples) and bool(self.note)
                      and all(sum(c['sequence']==s for c in captures)>=2 for s in required))
            report.update(ok=report['ok'] and complete,bonus_samples={s:len(v) for s,v in self.bonus_samples.items()},
                refill_samples=self.refill_samples,bonus_captures=captures,supply_history=self.note,
                limits=['This replay covers a Hip Flask bonus and ordinary refills. Native-source, multi-bonus, skip and reconnect cases require broader regression.'])
            write_json(self.folder/'bonus-samples.json',self.bonus_samples); write_json(self.folder/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=ROOT/'art/western/whiskey/bonus-v002/gameplay-plan.json')
    args=parser.parse_args(); plan=json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items(): assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    args.editor=EDITOR; args.package_dir=None; args.port=19999; args.timeout=350
    args.seed=plan['seed']; args.ruleset=plan['ruleset']; args.max_actions=len(plan['journal'])-2
    args.settle=0; args.prefer_camp=[]; args.require_kind=['water']; args.extra_render_commands=[]
    args.profile_renderer=False; args.require_fuse=False
    args.scenario_config=dict(name='bonus-whiskey',policy='public_replay',target_kinds=['water'])
    args.output.mkdir(parents=True,exist_ok=True); BonusScenario(args,args.output,(1600,900),0).run()
    result=json.loads((args.output/'1600x900/result.json').read_text()); write_json(args.output/'result.json',result)
    assert result['ok'],result.get('issues'); print('BONUS_WHISKEY_NATIVE',result['bonus_samples'],flush=True)


if __name__=='__main__': main()
