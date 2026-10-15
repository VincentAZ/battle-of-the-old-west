"""Native Wanted Poster Board History, private inspection and public reveal review.

Replays only CPU-rehearsed legal commands and observes the public cloth drop.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from test_unreal_event_queue import QueueScenario
from test_unreal_interactions import EDITOR, ROOT, center, field_cards, write_json
from native_launch import game_net_driver_ports


class WantedBoardScenario(QueueScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.notes, self.privacy, self.reveal_samples = {}, None, []
        self.cloth_samples, self.cloth_landed_capture = [], False

    def boot(self):
        # Render the owner (host seat zero) so the private-peek path is visible.
        self.launch('a', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}', rendered=True)
        log = self.folder/'a.log'
        self.wait('rendered listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('b', '/Game/Maps/WaterDepotV2')
        self.wait('client menu', lambda: self.snapshot('b').get('hosted') is False, 120)
        self.command('b', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('both peers in selection', self.agree, 100)
        for planned in self.plan['journal'][:2]:
            peer = next(p for p in ('a', 'b') if self.snapshot(p)['seat'] == planned['seat'])
            current = self.snapshot(peer)
            assert current['view']['revision'] == planned['revision']
            offered = [a for a in current['actions'] if a['command'] == planned['command']]
            assert len(offered) == 1
            self.submit(peer, offered[0])
        self.wait('ordinary match begins', lambda: self.snapshot()['view']['status'] == 'actions')
        self.settle_presentation()
        for planned in self.plan['own_opening_hands']:
            peer = next(p for p in ('a', 'b') if self.snapshot(p)['seat'] == planned['seat'])
            assert [(c['id'], c.get('card_id')) for c in self.own_hand(peer).values()] == [
                (c['id'], c.get('card_id')) for c in planned['own_hand']]
        self.capture_tooltips()

    def check_note(self, identity, key):
        before = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
        self.command('a', 'inspect', card=identity)
        self.wait('inspected card', lambda: self.hud()['inspected_card'] == identity)

        def link():
            return next((b for b in self.hud()['status_buttons']
                         if b['id'] == 'asset_history' and b['allocated_size'][0] > 1), None)

        # Inspect command acknowledgement can precede the next Slate rebuild.
        # Require the actual matching content as well as arranged geometry.
        button = self.wait('matching optional History arranged', lambda:
                           link() if self.hud().get('asset_history', {}).get('key') == key else None)
        assert not self.hud()['asset_history']['open']
        self.event('move', center(button)); time.sleep(.7)
        assert not self.hud()['asset_history']['open'], 'Hover opened History'
        self.capture(key+'-closed')
        self.event('down', center(button)); self.event('up', center(button))
        self.wait('History explicitly opened', lambda: self.hud()['asset_history']['open'])
        note = copy.deepcopy(self.hud()['asset_history'])
        assert note['key'] == key and len(note['body'].splitlines()) in (2, 3)
        assert note['url'].startswith('https://')
        self.capture(key+'-open')
        for phase in ('down', 'up'):
            self.command('a', 'ui_key', key='Escape', phase=phase, preserve_focus=True)
        self.wait('History closed', lambda: not self.hud()['asset_history']['open'])
        assert {p: self.snapshot(p) for p in ('a', 'b')} == before, 'History changed gameplay'
        self.notes[key] = note

    def capture_tooltips(self):
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)
        assert self.snapshot()['seat'] == 0, 'This replay requires the rendered owner seat'
        self.check_note(self.plan['holding'], 'holding-wanted-poster-board')
        self.capture('wanted-board-battlefield')

    def choose_action(self, name, snapshot):
        action = super().choose_action(name, snapshot)
        if action['command']['type'] == 'flip':
            punk = self.plan['punk']
            own = next(c for c in field_cards(self.snapshot('a')) if c['id'] == punk)
            other = next(c for c in field_cards(self.snapshot('b')) if c['id'] == punk)
            assert own['punk'] and own.get('private_peek') and other['punk']
            assert 'private_peek' not in other and 'card_id' not in other
            self.check_note(punk, 'drifter')
            unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == punk)
            assert unit['visual_id'] == 'punk'
            assert unit['visual_mesh'] == '/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter'
            # Healthy newly hired Drifters have no wound mesh loaded. If one
            # remains from an earlier wound it may only be the generic fit.
            assert unit['bandage']['mesh'] in ('', '/Game/Art/Western/Bandages/SK_Bandage_Drifter.SK_Bandage_Drifter')
            assert not unit['bandage']['visible']
            assert self.read()['cinematic'].get('reveal_cloth_components', 0) == 0
            self.privacy = dict(owner=own, opponent=other, owner_visible_unit=copy.deepcopy(unit))
            self.capture('private-inspection-still-drifter')
        return action

    def observe(self, state):
        super().observe(state)
        c = state.get('cinematic', {})
        if c.get('busy') and c.get('kind') == 'reveal_person':
            unit = next((u for u in c.get('units', []) if u['id'] == self.plan['punk']), None)
            if unit:
                self.reveal_samples.append(dict(sequence=c['sequence'], elapsed=c.get('elapsed'),
                                                impact_resolved=c.get('impact_resolved'), unit=copy.deepcopy(unit)))
            cloth = [e for e in c.get('action_effects', []) if e.get('falling_cloth')]
            if cloth:
                assert len(cloth) == 1 and cloth[0]['collision_enabled'] == 0
                assert c['impact_resolved'], 'Cloth appeared before the public visual reveal'
                self.cloth_samples.append(dict(elapsed=c['elapsed'], cloth=copy.deepcopy(cloth[0]),
                                               registered_components=c['reveal_cloth_components']))
                if cloth[0]['age'] >= cloth[0]['duration'] and not self.cloth_landed_capture:
                    self.cloth_landed_capture = True
                    self.capture('bandana-landed')

    def run(self):
        try:
            return super().run()
        finally:
            path = self.folder/'result.json'
            result = json.loads(path.read_text())
            identities = sorted({s['unit']['visual_id'] for s in self.reveal_samples})
            result['wanted_board_review'] = dict(history=self.notes, privacy=self.privacy,
                reveal_samples=len(self.reveal_samples), sampled_visual_ids=identities,
                bandana_drop_implemented=bool(self.cloth_samples), cloth_samples=len(self.cloth_samples),
                cloth_landed_capture=self.cloth_landed_capture,
                limits='One rendered owner. Opposite rendered seat, interruptions, wider regions/layouts and pixel inspection of cloth motion remain separate checks.')
            final = self.read().get('cinematic', {})
            clean = final.get('reveal_cloth_components') == 0
            result['wanted_board_review']['cloth_components_cleaned'] = clean
            complete = (set(self.notes) == {'holding-wanted-poster-board', 'drifter'} and self.privacy is not None
                        and 'punk' in identities and any(i != 'punk' for i in identities)
                        and self.cloth_samples and self.cloth_landed_capture and clean)
            result['ok'] = result['ok'] and complete
            write_json(self.folder/'reveal-samples.json', self.reveal_samples)
            write_json(self.folder/'cloth-samples.json', self.cloth_samples)
            write_json(path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/wanted-poster-board/gameplay-plan-v001.json')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    for path, digest in plan['provenance'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    args.editor, args.package_dir, args.port, args.timeout = EDITOR, None, 20049, 400
    args.seed, args.ruleset, args.max_actions = plan['seed'], plan['ruleset'], len(plan['journal'])-2
    args.settle, args.prefer_camp, args.require_kind = 0, [], ['reveal_person']
    args.extra_render_commands, args.profile_renderer, args.require_fuse = [], False, False
    args.scenario_config = dict(name='wanted-board', policy='public_replay', target_kinds=['reveal_person'])
    args.output.mkdir(parents=True, exist_ok=True)
    WantedBoardScenario(args, args.output, (1600, 900), 0).run()
    result = json.loads((args.output/'1600x900/result.json').read_text())
    write_json(args.output/'result.json', result)
    assert result['ok'], result.get('failure') or result.get('issues')
    print('WANTED_BOARD_NATIVE', result['wanted_board_review']['sampled_visual_ids'], flush=True)


if __name__ == '__main__':
    main()
