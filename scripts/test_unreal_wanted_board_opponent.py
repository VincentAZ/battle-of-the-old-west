"""Rendered opponent view and ordinary Skip/reconnect during a public cloth drop."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from test_unreal_action_showcase import signature
from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, field_cards, write_json
from test_unreal_wanted_board import WantedBoardScenario


class OpponentScenario(WantedBoardScenario):
    boot = QueueScenario.boot

    def __init__(self, *args):
        super().__init__(*args)
        self.interruption = None
        self.build['wanted_board_harness'] = signature(ROOT/'scripts/test_unreal_wanted_board.py')
        self.build['opponent_harness'] = signature(__file__)
        write_json(self.folder/'build.json', self.build)

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)
        assert self.snapshot()['seat'] == 1
        self.check_note(self.plan['holding'], 'holding-wanted-poster-board')
        self.capture('wanted-board-opponent-battlefield')

    def choose_action(self, name, snapshot):
        action = QueueScenario.choose_action(self, name, snapshot)
        if action['command']['type'] == 'flip':
            punk = self.plan['punk']
            own = next(c for c in field_cards(self.snapshot('b')) if c['id'] == punk)
            other = next(c for c in field_cards(self.snapshot('a')) if c['id'] == punk)
            assert own['punk'] and own.get('private_peek') and other['punk']
            assert 'private_peek' not in other and 'card_id' not in other
            self.check_note(punk, 'drifter')
            c = self.read()['cinematic']
            unit = next(u for u in c['units'] if u['id'] == punk)
            assert unit['visual_id'] == 'punk'
            assert unit['visual_mesh'] == '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            assert c['reveal_cloth_components'] == 0
            self.privacy = dict(owner=own, opponent=other, rendered_opponent_unit=copy.deepcopy(unit))
            self.capture('opponent-inspection-still-drifter')
        return action

    def clear_cloth(self):
        c = self.read().get('cinematic', {})
        return not c.get('busy', True) and c.get('reveal_cloth_components') == 0 and not c.get('action_effects')

    def wait_for_render(self):
        first = None
        def ready():
            nonlocal first
            c = self.hud().get('portraits', {}).get('compilation', {})
            if not c.get('ready'):
                first = None
                return False
            if first is None:
                first = c['frame']
            return c if c['frame']-first >= 3 else False
        return self.wait('post-interruption rendered assets ready', ready, 120)

    def capture_phase(self, state):
        c = state.get('cinematic', {})
        cloth = next((e for e in c.get('action_effects', []) if e.get('falling_cloth')), None)
        if (self.args.interrupt == 'none' or self.interruption is not None or not cloth
                or c.get('kind') != 'reveal_person' or not .25 < cloth['age'] < .75):
            return super().capture_phase(state)
        assert c['impact_resolved'] and c['reveal_cloth_components'] == 1
        mode = self.args.interrupt
        self.interruption = dict(mode=mode, ok=False, sequence=c['sequence'], moving_before=copy.deepcopy(cloth))
        self.capture('bandana-before-'+mode)
        before = {p:copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        if mode == 'skip':
            self.command('a', 'skip_cinematics')
            self.wait('Skip removes cloth and pending effects', self.clear_cloth)
        else:
            self.command('a', 'leave')
            self.wait('rendered guest leaves during reveal', lambda:
                      self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('guest reconnects with same seat', self.agree, 90)
            self.wait('reconnect has no stale cloth or replay', self.clear_cloth, 60)
        compilation = self.wait_for_render()
        after = {p:copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        assert before == after, 'Interruption changed authoritative snapshots or cosmetic filtering'
        assert self.clear_cloth()
        self.capture('bandana-after-'+mode)
        assert self.hud()['portraits']['compilation']['ready']
        self.interruption.update(ok=True, full_snapshots_unchanged=True,
            registered_cloths_after=self.read()['cinematic']['reveal_cloth_components'], compilation=compilation)
        write_json(self.folder/'interruption-check.json', self.interruption)

    def run(self):
        if self.args.interrupt == 'none':
            return super().run()
        # Interrupted runs intentionally cannot certify natural landing.
        try:
            return QueueScenario.run(self)
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            complete = (self.privacy is not None and set(self.notes) == {'holding-wanted-poster-board', 'drifter'}
                        and self.cloth_samples and self.interruption and self.interruption['ok'] and self.clear_cloth())
            result.update(ok=bool(result['ok'] and complete), wanted_board_interruption=self.interruption,
                          wanted_board_history=self.notes, wanted_board_privacy=self.privacy,
                          rendered_seat=1, natural_landing_verified=False)
            write_json(self.folder/'cloth-samples.json', self.cloth_samples)
            write_json(self.folder/'reveal-samples.json', self.reveal_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--interrupt', choices=['none', 'skip', 'reconnect'], default='none')
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/wanted-poster-board/gameplay-plan-v001.json')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20059, 450
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['reveal_person']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.scenario_config = dict(name='wanted-board-opponent-'+args.interrupt, policy='public_replay', target_kinds=['reveal_person'])
    args.output.mkdir(parents=True, exist_ok=True)
    OpponentScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('WANTED_BOARD_OPPONENT_NATIVE', args.interrupt, flush=True)


if __name__ == '__main__':
    main()
