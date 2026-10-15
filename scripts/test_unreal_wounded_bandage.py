"""Observe wound dressings through legal damage/restoration in two native peers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_medical_delivery import MedicalScenario
from test_unreal_interactions import ROOT, EDITOR, write_json, field_cards


class BandageScenario(MedicalScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.bandage_samples = {}
        self.wounded_seen, self.healed_seen = set(), set()

    def observe(self, state):
        super().observe(state)
        cinematic = state.get('cinematic', {})
        for unit in cinematic.get('units', []):
            if unit.get('camp') or unit.get('event_token'):
                continue
            bandage = unit.get('bandage')
            assert bandage is not None, 'Native component telemetry missing'
            expected = unit.get('damage') == 1 and not unit.get('dead')
            assert bandage['visible'] == expected, (unit['visual_id'], unit.get('damage'), bandage)
            assert bandage['collision_enabled'] == 0
            if expected:
                assert bandage['follows_body'] and bandage['mesh']
                if unit['visual_id'] == 'punk':
                    assert bandage['mesh'].endswith('/SK_Bandage_Drifter.SK_Bandage_Drifter')
            visual = unit['visual_id']
            if visual not in ('doc-holliday', 'quanah-parker'):
                continue
            if expected:
                self.wounded_seen.add(visual)
            if visual in self.wounded_seen and unit.get('damage') == 0 and not unit.get('dead'):
                self.healed_seen.add(visual)
            key = (visual, unit.get('damage'), cinematic.get('kind'), cinematic.get('sequence'))
            if key not in self.bandage_samples:
                self.bandage_samples[key] = dict(unit=copy.deepcopy(unit),
                    sequence=cinematic.get('sequence'), kind=cinematic.get('kind'),
                    elapsed=cinematic.get('elapsed'), busy=cinematic.get('busy'))
        if not cinematic.get('busy') and state.get('snapshot', {}).get('view', {}).get('players'):
            public = {card['id']: card for card in field_cards(state['snapshot'])}
            for unit in cinematic.get('units', []):
                if unit.get('camp') or unit.get('event_token') or unit['id'] not in public:
                    continue
                card = public[unit['id']]
                assert unit['bandage']['visible'] == (card.get('damage', 0) == 1 and not card.get('destroyed', False)), 'Settled wound indicator differs from public gameplay state'

    def run(self):
        try:
            return super().run()
        finally:
            report = json.loads((self.folder / 'result.json').read_text())
            required = {'doc-holliday', 'quanah-parker'}
            report['bandage_coverage'] = dict(wounded=sorted(self.wounded_seen), healed=sorted(self.healed_seen),
                samples=len(self.bandage_samples), limits='Two named characters only; all-roster pose, hidden-card lifecycle and final package review remain.')
            report['ok'] &= self.wounded_seen >= required and self.healed_seen >= required
            write_json(self.folder / 'bandage-samples.json', list(self.bandage_samples.values()))
            write_json(self.folder / 'result.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'art/western/delivery/medical-gameplay-plan.json')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20039, 450
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['restore']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.scenario_config = dict(name='wounded-bandage', policy='public_replay', target_kinds=['restore'])
    args.output.mkdir(parents=True, exist_ok=True)
    BandageScenario(args, args.output, (1600, 900), 0).run()
    report = json.loads((args.output / '1600x900/result.json').read_text())
    write_json(args.output / 'result.json', report)
    assert report['ok'], report.get('issues')
    print('WOUNDED_BANDAGE_NATIVE', report['bandage_coverage'], flush=True)


if __name__ == '__main__':
    main()
