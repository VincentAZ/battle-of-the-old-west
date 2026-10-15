"""Native Courthouse activation, opposing Trouble delay, fuse and History review."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class CourthouseScenario(WantedBoardScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.holding = None
        self.preparations = []
        self.final_public = None
        self.stampede_impacts = []

    def boot(self):
        if self.args.render_seat == 0:
            WantedBoardScenario.boot(self)
        else:
            QueueScenario.boot(self)

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)
        assert self.snapshot()['seat'] == self.args.render_seat
        cards = [c for c in field_cards(self.snapshot()) if c.get('card_id') == 'courthouse']
        assert len(cards) == 1 and cards[0]['owner'] == 1
        self.holding = cards[0]['id']
        self.check_note(self.holding, 'holding-courthouse')
        self.capture('courthouse-battlefield')

    def choose_action(self, name, snapshot):
        return QueueScenario.choose_action(self, name, snapshot)

    def observe(self, state):
        QueueScenario.observe(self, state)
        c = state.get('cinematic', {})
        if c.get('busy') and c.get('kind') == 'stampede_charge' and c.get('impact_resolved'):
            events = [e for row in self.plan['journal'] for e in row['public_events']
                      if e['sequence'] == c['sequence'] and e['type'] == 'damage']
            assert len(events) == 1 and events[0]['source'] == c['target']
            self.stampede_impacts.append(dict(sequence=c['sequence'], event=events[0], elapsed=c['elapsed']))
        if c.get('busy') and c.get('kind') == 'ability' and c.get('source') == self.holding and c.get('impact_resolved'):
            assert not c.get('action_effects'), 'Courthouse preparation spawned unrelated mechanism props'
            holding = next(u for u in c['units'] if u['id'] == self.holding)
            visible = [p for p in holding['holding_components'] if p['visible']]
            assert any('/SM_Holding_Courthouse.' in p['mesh'] for p in visible)
            assert any('/SM_HoldingBase_Courthouse.' in p['mesh'] for p in visible)
            ground = next(p for p in visible if '/SM_HoldingBase_Courthouse.' in p['mesh'])
            fit = ground['ground_fit']
            assert fit and fit['enabled'] == 1 and fit['region'] == self.args.region
            assert fit['foundation_extent'] == [250, 305, 60]
            assert all(abs(a-b) < .001 for a, b in zip(fit['origin'], ground['location']))
            self.preparations.append(dict(sequence=c['sequence'], elapsed=c['elapsed'], holding=copy.deepcopy(holding)))
        if len(self.actions) == len(self.replay) and not c.get('busy') and not self.final_public:
            self.final_public = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
            for snapshot in self.final_public.values():
                assert 'hand' not in snapshot['view']['players'][1-snapshot['seat']]
                assert any(card['id'] == self.holding for card in field_cards(snapshot))
                for impact in self.stampede_impacts:
                    target = next(card for card in field_cards(snapshot) if card['id'] == impact['event']['target'])
                    assert target['damage'] == 1 and not target['destroyed']

    def run(self):
        self.build['courthouse_harness'] = signature(__file__)
        self.build['history_helper'] = signature(ROOT/'scripts/test_unreal_wanted_board.py')
        write_json(self.folder/'build.json', self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            delay_sequences = {s for s, e in self.expected_moves.items() if e['move_reason'] == 'queue_delay'}
            assert delay_sequences
            observed_delays = {s['sequence'] for s in self.queue_samples if s['sequence'] in delay_sequences}
            result['courthouse_review'] = dict(history=self.notes, holding=self.holding,
                preparation_samples=len(self.preparations), observed_delay_sequences=sorted(observed_delays),
                stampede_impact_samples=len(self.stampede_impacts),
                final_public=self.final_public, rendered_seat=self.args.render_seat,
                limits='One offered-command match per seat. Broader layouts, condition lifecycles, terrain fitting, interruptions, audio and packaging remain.')
            result['ok'] = bool(result.get('ok') and self.preparations and self.final_public and self.stampede_impacts
                and observed_delays == delay_sequences and 'holding-courthouse' in self.notes)
            write_json(self.folder/'courthouse-preparation-samples.json', self.preparations)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/courthouse/legal-rehearsal-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=1)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20259+args.render_seat*10, 500
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['event_advance', 'raid_launch', 'stampede_charge']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='courthouse', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    CourthouseScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('COURTHOUSE_NATIVE_PASSED', args.render_seat, flush=True)


if __name__ == '__main__':
    main()
