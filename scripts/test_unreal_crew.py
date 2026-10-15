#!/usr/bin/env python3
"""Exercise distinct Crew copies, portraits, optional history and reconnect on two peers."""
import argparse
import hashlib
import json
from pathlib import Path
from test_unreal_native_copies import NativeCopiesScenario
from test_unreal_interactions import EDITOR, field_cards, resolution, write_json
from test_unreal_portraits import portraits_ready
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_event_queue import QueueScenario

ROOT = Path(__file__).resolve().parents[1]


def expected_mesh(slug, name):
    directory = f'/Game/Art/Western/Crew/{name}'
    path = ROOT/'art/western/crew/playable-overrides.json'
    overrides = json.loads(path.read_text()) if path.exists() else {}
    if slug in overrides:
        override = overrides[slug]
        verification = ROOT/override['verification']
        assert hashlib.sha256(verification.read_bytes()).hexdigest() == override['verification_sha256']
        report = json.loads(verification.read_text())
        assert report['ok'] and report['existing_content_unchanged']
        assert override['mesh_directory'].startswith(directory+'/')
        directory = override['mesh_directory']
        assert report['destination'] == directory
        for asset, digest in report['content_sha256'].items():
            assert hashlib.sha256((ROOT/asset).read_bytes()).hexdigest() == digest, asset
    return f'{directory}/SK_{name}.SK_{name}'


class CrewScenario(NativeCopiesScenario):
    def boot(self):
        if not self.args.manifest:
            return super().boot()
        self.plan = json.loads(self.args.manifest.read_text())
        assert self.plan['ok'] and self.args.seed == self.plan['seed']
        for path, digest in self.plan['provenance'].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
        self.replay_cursor = 2
        QueueScenario.boot(self)

    def capture_tooltips(self):
        # The optional legal replay supplies setup only; the Crew checks below
        # exercise the actual copy's History and drag portrait.
        self.wait('native shaders ready', lambda: self.hud()['portraits']['compilation']['ready'], 120)

    def seek(self, predicate, label, max_actions=120):
        if not self.args.manifest:
            return super().seek(predicate, label, max_actions)
        for row in self.plan['journal'][self.replay_cursor:]:
            peer = next(p for p in ('a', 'b') if self.snapshot(p)['seat'] == row['seat'])
            current = self.snapshot(peer)
            assert current['view']['revision'] == row['revision']
            assert hashlib.sha256(json.dumps(current['actions'], sort_keys=True).encode()).hexdigest() == row['legal_actions_sha256']
            action = next(a for a in current['actions'] if a['command'] == row['command'])
            self.replay_cursor += 1
            if peer == 'a' and predicate(action, current):
                self.settle_presentation()
                return action
            self.submit(peer, action)
            self.settle_presentation()
        raise AssertionError('Legal replay did not reach ' + label)

    def verify_figure(self, identity, visual, canonical, mesh):
        super().verify_figure(identity, visual, canonical, mesh)
        if visual != 'gatling-gunner':
            return
        # The rendered peer can skip its local entrance while the other peer
        # continues walking. Check battlefield facing after both have arrived.
        self.wait('Gatling entrance completed on both peers', lambda: all(
            not (state := self.read(peer))['cinematic']['busy']
            and any(u['id'] == identity and not u['travelling'] for u in state['cinematic']['units'])
            for peer in ('a', 'b')), 90)
        measured = json.loads((ROOT/'art/western/crew/playable-v001/gatling-gunner/unreal-gatling-direction.json').read_text())
        assert measured['status'] == 'passed'
        package = ROOT/'game/OldWest/Content/Art/Western/Crew/GatlingGunner/SK_GatlingGunner.uasset'
        assert hashlib.sha256(package.read_bytes()).hexdigest() == measured['mesh_package_sha256'], 'Gatling direction evidence is stale'
        vector = measured['muzzle_direction_mesh_local']
        def cross(a, b):
            return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        for peer in ('a', 'b'):
            units = self.read(peer)['cinematic']['units']
            unit = next(u for u in units if u['id'] == identity)
            observation = unit['completed_weapon_observation']
            assert observation['id'] == identity and unit['completed_weapon_observation_age_frames'] <= 1
            q = observation['body_transform']['quaternion_xyzw']
            t = [2*x for x in cross(q[:3], vector)]
            c = cross(q[:3], t)
            world = [vector[i] + q[3]*t[i] + c[i] for i in range(3)]
            camps = [u for u in units if u.get('camp') and u['side'] != unit['side']]
            assert camps, 'No opposing camp for muzzle direction check'
            enemy_y = sum(u['location'][1] for u in camps)/len(camps)
            toward_enemy = 1 if enemy_y > unit['location'][1] else -1
            assert world[1]*toward_enemy > .98, ('Gatling points away from opposing camps', peer, world)
            self.evidence.setdefault('gatling_live_direction', {})[peer] = {
                'side': unit['side'], 'world_muzzle_direction': world, 'toward_enemy_y': toward_enemy,
                'imported_geometry_evidence': measured['mesh_package_sha256']}

    def run(self):
        records = json.loads((ROOT/'art/western/crew/playable-v001/manifest.json').read_text())['characters']
        try:
            self.boot()
            deployed = {}
            for slug in self.args.slugs:
                record = records[slug]
                canonical = record['copies'][0]['canonical_card_id']
                name = record['asset_name']
                mesh = expected_mesh(slug, name)
                def matches(action, snapshot):
                    identity = action['command'].get('card')
                    return (action['command']['type'] == 'play'
                            and snapshot.get('cosmetics', {}).get(str(identity)) == slug)
                action = self.seek(matches, 'draw and afford ' + slug, max_actions=600)
                identity = action['command']['card']
                card = self.own_hand()[identity]
                assert card['card_id'] == canonical and card['name'] == self.defs[canonical]['name']
                assert str(identity) not in self.snapshot('b').get('cosmetics', {}), 'Private hand identity leaked'
                # The physical hand staging actors must use the same copy
                # appearance as portraits and deployed figures.
                for handle, tag in self.snapshot().get('cosmetics', {}).items():
                    if int(handle) not in self.own_hand() or tag not in records:
                        continue
                    labels = [entry['label'] for entry in self.hud()['battlefield_labels'] if entry['id'] == int(handle)]
                    assert labels and all(records[tag]['display_name'] in label for label in labels), (tag, labels)
                self.check_note(identity, slug)
                self.check_crew_portrait(identity, slug, mesh)
                self.submit('a', action)
                self.settle_choices()
                self.verify_figure(identity, slug, canonical, mesh)
                for peer in ('a', 'b'):
                    public = next(c for c in field_cards(self.snapshot(peer)) if c['id'] == identity)
                    assert public['card_id'] == canonical and public['name'] == self.defs[canonical]['name']
                    assert self.snapshot(peer)['cosmetics'][str(identity)] == slug
                self.close_model(identity, slug)
                deployed[identity] = (slug, canonical, mesh)
                self.checked(slug+': distinct approved mesh/portrait/history; canonical rules and private visibility preserved')
            baseline = {p: self.snapshot(p) for p in ('a', 'b')}
            self.command('a', 'leave')
            self.wait('guest leaves', lambda: self.snapshot().get('hosted') is False and self.snapshot('b').get('connected') == 1)
            self.command('a', 'join', address=f'127.0.0.1:{self.port}')
            self.wait('guest reconnects', self.agree, 90)
            self.settle_presentation()
            assert {p: self.snapshot(p) for p in ('a', 'b')} == baseline
            current = {c['id'] for c in field_cards(self.snapshot())}
            for identity, (slug, canonical, mesh) in deployed.items():
                if identity in current:
                    self.verify_figure(identity, slug, canonical, mesh)
            self.checked('Reconnect restores exact snapshots and distinct copy appearances')
            result = dict(ok=True, checks=self.checks, screenshots=self.captures, evidence=self.evidence,
                          package_directory=str(self.runtime.package_root),
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            write_json(self.folder/'result.json', dict(ok=False, error=str(error), checks=self.checks, last=self.read()))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:
                stream.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor', type=Path, default=EDITOR)
    p.add_argument('--package-dir', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--manifest', type=Path, help='Optional verified public replay to reach an exact physical copy')
    p.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280,720)])
    p.add_argument('--slugs', nargs='+', default=['bartender', 'piano-player', 'gatling-gunner'])
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--port', type=int, default=21679)
    p.add_argument('--ruleset', default='boomtown')
    p.add_argument('--timeout', type=float, default=1800)
    p.add_argument('--settle', type=float, default=.5)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for index, size in enumerate(args.resolutions):
            scenario = CrewScenario(args, args.output, size, index)
            scenario.args = args
            results.append(scenario.run())
    finally:
        write_json(args.output/'result.json', dict(ok=len(results)==len(args.resolutions), results=results))
