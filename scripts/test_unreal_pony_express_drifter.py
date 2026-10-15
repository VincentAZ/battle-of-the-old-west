"""Native station Drifter return, hidden-face filtering and legal same-turn entry."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature, capture_subject, phase_of
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, write_json
from test_unreal_pony_express_station import StationScenario


class DrifterStationScenario(StationScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.generic_before_return = None
        self.generic_withdrawals = []
        self.public_entries = []

    def choose_action(self, name, snapshot):
        action = StationScenario.choose_action(self, name, snapshot)
        if action['command'] == dict(type='activate', source=self.plan['holding'], ability=0):
            self.check_note(self.plan['punk'], 'drifter')
            peers = []
            for peer in ('a', 'b'):
                view = self.snapshot(peer)['view']
                card = next(c for col in view['players'][0]['columns'] for c in col if c['id'] == self.plan['punk'])
                assert card.get('punk') and card.get('card_id', 'punk') == 'punk' and 'private_peek' not in card
                peers.append(copy.deepcopy(card))
            unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == self.plan['punk'])
            assert unit['visual_id'] == 'punk'
            assert unit['visual_mesh'] == '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            self.generic_before_return = dict(peers=peers, unit=copy.deepcopy(unit))
            self.capture('generic-drifter-before-return')
        return action

    def observe(self, state):
        StationScenario.observe(self, state)
        c = state.get('cinematic', {})
        if not c.get('busy') or c.get('target') != self.plan['punk']:
            return
        unit = next((u for u in c['units'] if u['id'] == self.plan['punk'] and not u['hidden']), None)
        if c.get('kind') == 'return' and unit:
            assert unit['visual_id'] == 'punk', 'Withdrawal exposed the returned Drifter face'
            assert unit['visual_mesh'] == '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            self.generic_withdrawals.append(dict(sequence=c['sequence'], elapsed=c['elapsed'], unit=copy.deepcopy(unit)))
        # The initial Drifter entry and the later faceup entry use the same
        # public handle. Only a public doomsayer entry permits the named mesh.
        if c.get('kind') == 'enter' and unit and unit.get('card_id') == 'pinkerton_agent':
            assert unit['visual_id'] != 'punk'
            self.public_entries.append(dict(sequence=c['sequence'], elapsed=c['elapsed'], unit=copy.deepcopy(unit)))

    def capture_phase(self, state):
        c = state.get('cinematic', {})
        previous, subjects = set(self.valid_captures), set(self.valid_subject_captures)
        if c.get('kind') == 'enter' and c.get('target') == self.plan['punk']:
            # Both entries can share a generic public subject category. Retain
            # a fresh painted capture of each exact entry sequence nonetheless.
            phase = phase_of(c)
            self.valid_captures.discard(('enter', phase))
            self.valid_subject_captures.discard(('enter', *capture_subject(c), phase))
        try:
            QueueScenario.capture_phase(self, state)
        finally:
            self.valid_captures.update(previous)
            self.valid_subject_captures.update(subjects)

    def run(self):
        self.build['drifter_station_harness'] = signature(__file__)
        self.build['station_helper'] = signature(ROOT/'scripts/test_unreal_pony_express_station.py')
        write_json(self.folder/'build.json', self.build)
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            sequences = {p['sequence'] for p in self.preparations}
            return_sequences = {p['sequence'] for p in self.generic_withdrawals}
            entry_sequences = {p['sequence'] for p in self.public_entries}
            def captures(kind, required):
                return [c for c in result['captures'] if c['kind'] == kind and c['sequence'] in required
                        and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')]
            preparation_captures = captures('ability', sequences)
            return_captures = captures('return', return_sequences)
            entry_captures = captures('enter', entry_sequences)
            result['station_review'] = dict(history=self.notes, rendered_seat=self.args.render_seat, region=self.args.region,
                preparations=self.preparations, preparation_captures=preparation_captures,
                return_samples=self.returns, return_captures=return_captures, returned_public_states=self.return_state,
                generic_before_return=self.generic_before_return, generic_withdrawals=self.generic_withdrawals,
                public_entries=self.public_entries, entry_captures=entry_captures,
                limits='One legal Drifter replay at one placement/region per rendered seat. Other identities, placements, interruptions, battlefield conditions, effects/audio and packaging remain.')
            result['ok'] = bool(result['ok'] and self.return_state and self.generic_before_return
                and self.generic_withdrawals and self.public_entries and preparation_captures and return_captures
                and entry_captures and set(self.notes) == {'holding-pony-express-station', 'drifter'})
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/pony-express-station/drifter-gameplay-plan-v001.json')
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=0)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20539+args.render_seat*10, 400
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter', 'return']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='pony-express-drifter', policy='public_replay', target_kinds=args.require_kind)
    args.output.mkdir(parents=True, exist_ok=True)
    DrifterStationScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('PONY_EXPRESS_DRIFTER_NATIVE_PASSED', flush=True)


if __name__ == '__main__':
    main()
