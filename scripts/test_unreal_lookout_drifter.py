"""Native exposure must preserve Drifter models and generic History despite a private peek."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import capture_subject, phase_of, signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_lookout_ridge import LookoutRidgeScenario


class LookoutDrifterScenario(LookoutRidgeScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.private_phases = {}
        self.generic_samples = []
        self.history_phase = None

    def capture(self, label):
        if self.history_phase:
            label = self.history_phase+'-'+label
        return super().capture(label)

    def check_public(self, phase):
        super().check_public(phase)
        views = {}
        for peer in ('a', 'b'):
            snapshot = self.snapshot(peer)
            card = next(c for c in field_cards(snapshot) if c['id'] == self.plan['punk'])
            assert card['punk'] and card.get('card_id', 'punk') == 'punk'
            assert card['protected'] == (phase != 'exposed')
            if snapshot['seat'] == 0:
                assert card['private_peek']['card_id'] == self.plan['private_inspection']['before'][0]['private_peek']['card_id']
            else:
                assert 'private_peek' not in card
            views[snapshot['seat']] = copy.deepcopy(card)
        self.history_phase = phase
        try:
            self.check_note(self.plan['punk'], 'drifter')
        finally:
            self.history_phase = None
        unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == self.plan['punk'])
        self.assert_generic(unit)
        self.private_phases[phase] = dict(views=views, unit=copy.deepcopy(unit), history=copy.deepcopy(self.notes['drifter']))

    @staticmethod
    def assert_generic(unit):
        assert unit['visual_id'] == 'punk'
        assert unit['visual_mesh'] == '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
        assert not unit['bandage']['visible']
        assert unit['bandage']['mesh'] in ('', '/Game/Art/Western/Bandages/SK_Bandage_Drifter.SK_Bandage_Drifter')

    def observe(self, state):
        super().observe(state)
        cinematic = state.get('cinematic', {})
        if cinematic.get('busy') and cinematic.get('source') == self.plan['holding'] and cinematic.get('kind') in ('ability', 'expose_all'):
            unit = next(u for u in cinematic['units'] if u['id'] == self.plan['punk'])
            self.assert_generic(unit)
            assert cinematic.get('reveal_cloth_components', 0) == 0
            self.generic_samples.append(dict(sequence=cinematic['sequence'], kind=cinematic['kind'], elapsed=cinematic['elapsed'], unit=copy.deepcopy(unit)))

    def capture_phase(self, state):
        cinematic = state.get('cinematic', {})
        if cinematic.get('kind') == 'ability' and cinematic.get('source') == self.plan['holding']:
            phase = phase_of(cinematic)
            # The earlier Wanted Board preparation must not satisfy this shot.
            self.valid_captures.discard(('ability', phase))
            self.valid_subject_captures.discard(('ability', *capture_subject(cinematic), phase))
        QueueScenario.capture_phase(self, state)

    def run(self):
        self.build['lookout_drifter_harness'] = signature(__file__)
        try:
            return super().run()
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            sequences = {s['sequence'] for s in self.generic_samples}
            captures = {kind: [c for c in result['captures'] if c['kind'] == kind and c['sequence'] in sequences
                and c.get('native_phase_bracket_valid') and c.get('painted_beat_bracket_valid')
                and c['requested_phase'] in ('impact', 'after-impact')] for kind in ('ability', 'expose_all')}
            result['lookout_drifter_review'] = dict(private_phases=self.private_phases,
                generic_samples=len(self.generic_samples), captures=captures,
                rendered_seat=self.args.render_seat, region=self.args.region,
                privately_inspected_type=self.plan['private_inspection']['before'][0]['private_peek']['type'],
                limitations='One legal privately inspected Drifter at one placement. No public flip occurs. Other identities, interruptions, battlefield damage/repair, effects/audio and packaging remain.')
            result['lookout_ridge_review']['limits'] = (
                'One legal replay with one privately inspected Drifter and three faceup people. '
                'See lookout_drifter_review for private-face coverage. Other identities, placements, '
                'battlefield condition lifecycles, interruptions, effects/audio and packaging remain.')
            result['ok'] = bool(result['ok'] and set(self.private_phases) == {'protected', 'exposed', 'restored'}
                and self.generic_samples and all(captures.values()) and set(self.notes) == {'drifter', 'holding-lookout-ridge'})
            write_json(self.folder/'drifter-samples.json', self.generic_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--render-seat', type=int, choices=[0, 1], default=0)
    parser.add_argument('--region', type=int, choices=[0, 1, 2], default=1)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20649+args.render_seat*10, 650
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['enter']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.require_ground_fit = True
    args.native_extra_args = [f'-OldWestRegionReview={args.region}']
    args.scenario_config = dict(name='lookout-drifter', policy='public_replay', target_kinds=['enter'])
    args.output.mkdir(parents=True, exist_ok=True)
    LookoutDrifterScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('LOOKOUT_DRIFTER_NATIVE_PASSED', args.render_seat, flush=True)


if __name__ == '__main__':
    main()
