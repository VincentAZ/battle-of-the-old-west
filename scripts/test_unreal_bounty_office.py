"""Both-seat legal Bounty Office hit/recruit/decline, History and privacy review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import capture_subject, phase_of, signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class BountyOfficeScenario(QueueScenario):
    check_note = WantedBoardScenario.check_note

    def __init__(self, *args):
        super().__init__(*args)
        self.notes, self.public_checks, self.effect_samples = {}, {}, []
        self.holding_sample, self.privacy = None, None
        self.expected_events = {}
        for row in self.plan['journal']:
            for event in row['public_events']:
                if not ((event['type'] in ('ability','damage') and event['source']==self.plan['holding'])
                        or (event['type']=='enter' and event['target']==self.plan['punk'])):
                    continue
                native = next((e for e in row['public_events'] if event['type']=='damage'
                               and e['type']=='destroy' and e['target']==event['target']), event)
                self.expected_events[native['sequence']] = dict(event, native_sequence=native['sequence'],
                    native_kind=native['type'], mapping='same-command lethal hit' if native!=event else 'direct')

    def boot(self):
        if self.args.render_seat == 0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda:self.hud()['portraits']['compilation']['ready'], 120)
        assert self.snapshot()['seat']==self.args.render_seat
        assert self.hud()['region']['index']==self.args.region
        self.check_note(self.plan['holding'], 'holding-bounty-office')
        unit = next(u for u in self.read()['cinematic']['units'] if u['id']==self.plan['holding'])
        visible = [p['mesh'] for p in unit['holding_components'] if p['visible']]
        for name in ('SM_Holding_BountyOffice','SM_HoldingBase_BountyOffice'):
            assert any('/'+name+'.' in path for path in visible), name
        assert unit['animated_part_count']==0
        ground = next(p for p in unit['holding_components'] if '/SM_HoldingBase_' in p['mesh'])
        assert ground['ground_fit']['enabled']==1 and ground['ground_fit']['region']==self.args.region
        assert ground['ground_fit']['foundation_extent']==[225,230,55]
        self.holding_sample = copy.deepcopy(unit)
        self.capture('bounty-office-battlefield')

    def check_public(self, phase):
        snapshots = {p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
        for snapshot in snapshots.values():
            expected = self.plan['checkpoints'][phase][snapshot['seat']]
            assert snapshot['view']==expected['view'], phase+': public state diverged'
            assert snapshot['actions']==expected['actions'], phase+': legal actions diverged'
            assert 'hand' not in snapshot['view']['players'][1-snapshot['seat']]
        self.public_checks[phase] = snapshots

    def choose_action(self, name, snapshot):
        for phase, expected in self.plan['checkpoints'].items():
            if snapshot['view']['revision']==expected[0]['view']['revision']:
                self.check_public(phase)
        return QueueScenario.choose_action(self, name, snapshot)

    def observe(self, state):
        QueueScenario.observe(self, state)
        cinematic = state.get('cinematic', {})
        if cinematic.get('busy') and cinematic.get('sequence') in self.expected_events:
            self.effect_samples.append(copy.deepcopy(cinematic))
        if len(self.actions)==len(self.replay) and not cinematic.get('busy') and 'gated_next_turn' not in self.public_checks:
            self.check_public('gated_next_turn')

    def capture_phase(self, state):
        cinematic = state.get('cinematic', {})
        if cinematic.get('sequence') not in self.expected_events:
            return super().capture_phase(state)
        phase, kind = phase_of(cinematic), cinematic['kind']
        key = (cinematic['sequence'], phase)
        if not hasattr(self, 'event_capture_keys'):
            self.event_capture_keys = set()
        if key in self.event_capture_keys:
            return super().capture_phase(state)
        old = set(self.valid_captures)
        subjects = set(self.valid_subject_captures)
        self.valid_captures.discard((kind, phase))
        self.valid_subject_captures.discard((kind, *capture_subject(cinematic), phase))
        before = len(self.capture_records)
        try:
            super().capture_phase(state)
            if len(self.capture_records)>before:
                self.event_capture_keys.add(key)
        finally:
            self.valid_captures.update(old)
            self.valid_subject_captures.update(subjects)

    def coverage(self):
        result = super().coverage()
        if 'gated_next_turn' in self.public_checks and self.privacy is None:
            self.privacy = {'pending':True}
            self.check_note(self.plan['punk'], 'drifter')
            views = {p:copy.deepcopy(self.snapshot(p)) for p in ('a','b')}
            cards = [next(c for c in field_cards(s) if c['id']==self.plan['punk']) for s in views.values()]
            assert all(c['punk'] and 'card_id' not in c for c in cards)
            unit = next(u for u in self.read()['cinematic']['units'] if u['id']==self.plan['punk'])
            assert unit['visual_id']=='punk'
            assert unit['visual_mesh']=='/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            assert not unit['bandage']['visible']
            self.privacy = dict(snapshots=views, rendered_unit=copy.deepcopy(unit), generic_history=True)
            self.capture('bounty-office-recruited-drifter')
        return result

    def run(self):
        self.build['bounty_office_harness'] = signature(__file__)
        self.build['history_helper'] = signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json', self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            events = []
            for sequence, event in self.expected_events.items():
                samples = [s for s in self.effect_samples if s['sequence']==sequence]
                captures = [c for c in result.get('captures',[]) if c['sequence']==sequence
                            and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')]
                events.append(dict(event=event,samples=len(samples),captures=captures,passed=bool(samples and captures)))
            review = dict(rendered_seat=self.args.render_seat,region=self.args.region,history=self.notes,
                holding=self.holding_sample,public_checks=self.public_checks,event_coverage=events,privacy=self.privacy,
                limits='One legal decline then accept sequence, covered camp hit/ruin and subsequent punk gate. Other copies, terrain fitting, interrupts, effects/audio and packaging remain.')
            result['bounty_office_review'] = review
            result['ok'] = bool(result.get('ok') and self.holding_sample and self.privacy
                and self.privacy.get('generic_history') and set(self.public_checks)==set(self.plan['checkpoints'])
                and all(e['passed'] for e in events) and set(self.notes)=={'holding-bounty-office','drifter'})
            write_json(self.folder/'effect-samples.json', self.effect_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/bounty-office/gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0,1], default=0)
    parser.add_argument('--region', type=int, choices=[0,1,2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path,digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest, path
    args.editor,args.package_dir,args.port,args.timeout = EDITOR,None,21349+args.render_seat*10,550
    args.seed,args.ruleset,args.max_actions = plan['seed'],plan['ruleset'],len(plan['journal'])-2
    args.settle,args.prefer_camp,args.require_kind = 0,[],['enter','damage','destroy']
    args.extra_render_commands,args.profile_renderer,args.require_fuse = [],False,False
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='bounty_office',policy='public_replay',target_kinds=args.require_kind)
    args.output.mkdir(parents=True,exist_ok=True)
    BountyOfficeScenario(args,args.output,(1600,900),0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json',result)
    assert result['ok'], result.get('failure') or result.get('issues') or result['bounty_office_review']
    print('BOUNTY_OFFICE_NATIVE_PASSED',args.render_seat,flush=True)


if __name__=='__main__':
    main()
