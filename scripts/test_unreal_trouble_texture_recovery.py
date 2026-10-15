"""Observe ordinary texture recovery after a real Trouble reconnect.

Retain early captures, then sample ten seconds without changing camera,
renderer settings, game state or asset residency. This is a diagnostic, not a
declaration that delayed texture recovery is acceptable presentation.
"""
import copy
import json
import time

from test_unreal_action_showcase import signature
from test_unreal_interactions import write_json
from test_unreal_trouble_interruptions import TroubleInterruptionScenario, main


class TextureRecoveryScenario(TroubleInterruptionScenario):
    def __init__(self, *args):
        super().__init__(*args)
        assert self.args.interrupt == 'reconnect'
        self.texture_recovery = {}
        self.build['texture_recovery_harness'] = signature(__file__)
        write_json(self.folder / 'build.json', self.build)

    @staticmethod
    def texture_state(state):
        return [dict(unit=u['id'], card=u['card_id'], mesh=part['mesh'], **texture)
                for u in state['cinematic']['units'] if u.get('camp') and not u.get('hidden')
                for part in u.get('holding_components', []) if part['visible']
                for texture in part.get('textures', [])]

    def capture_phase(self, state):
        previous = set(self.interrupted)
        super().capture_phase(state)
        for card in set(self.interrupted) - previous:
            assert self.interrupted[card]['ok']
            baseline = {p: copy.deepcopy(self.snapshot(p)) for p in ('a', 'b')}
            original = json.loads((self.folder / (card + '-after-reconnect.state.json')).read_text())
            started = time.monotonic()
            samples = []
            captures = [dict(seconds_after_initial_capture=0,
                             image=self.captures[card + '-after-reconnect'],
                             textures=self.texture_state(original))]
            for delay in (1, 3, 10):
                while time.monotonic() - started < delay:
                    current = self.read()
                    self.observe(current)
                    samples.append(dict(seconds=time.monotonic() - started,
                                        textures=self.texture_state(current)))
                    time.sleep(.1)
                label = card + '-texture-recovery-' + str(delay) + 's'
                self.capture(label)
                current = json.loads((self.folder / (label + '.state.json')).read_text())
                assert current['hud']['portraits']['compilation']['ready']
                assert self.clear_resolution(self.interrupted[card]['source'])
                assert baseline == {p: self.snapshot(p) for p in ('a', 'b')}
                captures.append(dict(seconds_after_initial_capture=time.monotonic() - started,
                                     image=self.captures[label], textures=self.texture_state(current)))
            self.texture_recovery[card] = dict(captures=captures, samples=samples,
                                               full_peer_snapshots_unchanged=True)
            write_json(self.folder / 'texture-recovery.json', self.texture_recovery)

    def run(self):
        try:
            return super().run()
        finally:
            path = self.folder / 'result.json'
            report = json.loads(path.read_text())
            report['texture_recovery'] = self.texture_recovery
            report['texture_recovery_visual_review'] = 'pending'
            report['ok'] = report['ok'] and set(self.texture_recovery) == set(self.plan['targets'].values())
            write_json(path, report)


if __name__ == '__main__':
    main(TextureRecoveryScenario)
