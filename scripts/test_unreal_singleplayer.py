#!/usr/bin/env python3
"""Play real native solo games against every AI difficulty and both rule sets.

The human seat uses the existing legal-action test player. The opponent is the
game's actual single-player AI. Each scenario launches one game, enters through
StartSinglePlayer, completes a match, votes once for a rematch, leaves, and quits.
No rule state is injected and no server or second game is launched. Test-only
cinematic skips accelerate the matrix without changing the authoritative game.

With --render, two additional complete games capture the actual menu, selection,
play, result, rematch, and returned menu at 720p and 1080p. Geometry assertions do
not substitute for reviewing those images. Evidence lives in private persistent
run directories so a reboot does not delete it.
"""
import argparse
import hashlib
import json
import os
import secrets
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from native_launch import (create_native_run_directory, game_net_driver_ports,
                           resolve_native_launch, stop_owned_process_groups)
from native_runtime_checks import assert_runtime_assets

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'
DIFFICULTIES = ('easy', 'normal', 'hard')
RULESETS = ('base_2024', 'boomtown')


def write_json(path, value):
    temporary = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def file_signature(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return {'path': str(path.resolve()), 'sha256': digest.hexdigest(), 'bytes': path.stat().st_size,
            'modified_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}


def assert_private_human_view(snapshot):
    assert snapshot['seat'] == 0, 'Single player did not assign the human to seat zero'
    view = snapshot['view']
    assert view['viewer'] == 0, 'Single player sent the AI perspective to the human'
    assert not {'rng', 'deck', 'cards', 'tasks'} & view.keys(), 'Internal rule state leaked into the human view'
    opponent = view['players'][1]
    assert 'hand' not in opponent and 'offers' not in opponent, 'AI private cards leaked to the human'
    assert all('private_peek' not in card for column in opponent['columns'] for card in column), \
        'An AI punk identity leaked to the human'
    choice = view.get('choice')
    if choice and choice['player'] == 1:
        assert 'options' not in choice, 'AI private choice options leaked to the human'


def assert_menu_layout(hud):
    """Validate the actual Slate widget bounds, not an imagined layout."""
    width, height = hud.get('hud_size', [0, 0])
    buttons = hud.get('solo_buttons', [])
    assert width > 0 and height > 0 and buttons, 'Single-player menu widget geometry is missing'
    represented = {button['id'] for button in buttons}
    expected = {*RULESETS, *DIFFICULTIES, 'play_single_player'}
    assert represented == expected, f'The menu does not expose all solo choices: {represented}'
    assert len(buttons) == len(expected), 'Duplicate single-player menu buttons'
    assert hud.get('solo_ruleset') in RULESETS, 'Menu selected ruleset is missing or invalid'
    assert hud.get('solo_difficulty') in DIFFICULTIES, 'Menu selected AI difficulty is missing or invalid'
    for button in buttons:
        assert button['visible'] and button['enabled'], f'Solo choice is unavailable: {button}'
        x0, y0 = button['min']
        x1, y1 = button['max']
        assert -1 <= x0 < x1 <= width + 1 and -1 <= y0 < y1 <= height + 1, \
            f'Solo choice extends outside the HUD: {button}'
        actual, desired = button['allocated_size'], button['desired_size']
        assert all(a + .5 >= d for a, d in zip(actual, desired)), f'Solo choice text is clipped: {button}'
    for index, button in enumerate(buttons):
        for other in buttons[index + 1:]:
            assert (button['max'][0] <= other['min'][0] + 1 or other['max'][0] <= button['min'][0] + 1
                    or button['max'][1] <= other['min'][1] + 1 or other['max'][1] <= button['min'][1] + 1), \
                'Single-player menu buttons overlap'
    return {'hud_size': [width, height], 'buttons': buttons,
            'solo_ruleset': hud['solo_ruleset'], 'solo_difficulty': hud['solo_difficulty']}


class SoloScenario:
    def __init__(self, args, output, ruleset, difficulty, seed, dimensions=None):
        self.args, self.ruleset, self.difficulty, self.seed = args, ruleset, difficulty, seed
        self.dimensions = dimensions
        suffix = f'{dimensions[0]}x{dimensions[1]}' if dimensions else 'headless'
        self.folder = output / f'{ruleset}-{difficulty}-{suffix}'
        self.folder.mkdir(mode=0o700)
        self.runtime = resolve_native_launch(args.editor, ROOT / 'game/OldWest/OldWest.uproject', args.package_dir,
                                             run_directory=self.folder, editor_directory=ROOT)
        self.processes, self.streams = [], []
        self.build = {}
        self.last_report, self.sequence, self.expected_exit = {}, 0, False
        self.started = time.monotonic()
        self.checks, self.captures, self.observed_choices = [], {}, set()
        self.last_key, self.observed_revisions = None, 0
        self.skips, self.max_revision_gap = 0, 0.0
        self.profile = self.folder / 'profiles/human/reconnect.json'
        self.profile.parent.mkdir(parents=True, mode=0o700)
        self.profile.parent.chmod(0o700)
        self.token = secrets.token_hex(16)
        self.saved_endpoint, self.saved_session = '192.0.2.10:7777', secrets.token_hex(16)
        self.profile_bytes = (json.dumps({'version': 1, 'endpoint': self.saved_endpoint,
                                        'server_session': self.saved_session, 'token': self.token}) + '\n').encode()
        self.profile.write_bytes(self.profile_bytes)
        self.profile.chmod(0o600)

    def checked(self, description):
        self.checks.append(description)
        print(f'{self.folder.name}: PASS {description}', flush=True)

    def launch(self):
        if self.runtime.package_root:
            package = self.runtime.package_root
            binaries = package / 'OldWest/Binaries/Linux'
            binary = next((path for path in (binaries/'OldWestGame', binaries/'OldWestGame-Linux-Development') if path.is_file()), None)
            if binary is None:
                raise FileNotFoundError(f'No packaged OldWestGame executable under {binaries}')
            self.build = {'mode': 'packaged_game', 'package_root': str(package),
                          'executable': file_signature(binary),
                          'launcher': file_signature(package/'launch_battle_of_the_old_west.sh'),
                          'manifest': file_signature(package/'package-manifest.json')}
        else:
            self.build = {'mode': 'editor_game',
                          'module': file_signature(ROOT/'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'),
                          'sources': [file_signature(path) for path in sorted((ROOT/'game/OldWest/Source/OldWestGame').rglob('*')) if path.is_file()]}
        write_json(self.folder/'build.json', self.build)
        stream = (self.folder / 'game-console.log').open('w')
        self.streams.append(stream)
        if self.dimensions:
            width, height = self.dimensions
            graphics = ['-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}']
        else:
            graphics = ['-nullrhi']
        startup = [] if self.args.package_dir else ['/Game/Maps/WaterDepotV2']
        self.processes.append(subprocess.Popen(self.runtime.argv + startup + ['-game',
            '-OldWestTestBot', '-OldWestLifecycleTest', '-OldWestVisualTest', '-OldWestTestDelay=0.16',
            *([] if self.args.normal_pacing_only else ['-OldWestAITestDelay=0.03']),
            f'-OldWestTestSeed={self.seed}', '-ExecCmds=t.MaxFPS 60',
            f'-OldWestLifecycleControl={self.folder}/game.control.json',
            f'-OldWestLifecycleReport={self.folder}/game.json', '-OldWestProfile=human',
            f'-OldWestProfileRoot={self.folder}/profiles', f'-GameUserSettingsINI={self.folder}/game.settings.ini',
            '-nosound', '-unattended', '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput',
            f'-abslog={self.folder}/game.log', *graphics], cwd=self.runtime.cwd, env=self.runtime.env,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True))

    def record_build_result(self, result):
        result['build'] = self.build
        if not self.build:
            return
        try:
            for key in ('executable', 'launcher', 'manifest', 'module'):
                if key in self.build:
                    before = self.build[key]
                    assert file_signature(Path(before['path']))['sha256'] == before['sha256'], \
                        f'Tested {key} changed while the single-player scenario was running'
            result['tested_artifacts_unchanged'] = True
        except Exception as error:
            result.update(ok=False, tested_artifacts_unchanged=False, artifact_failure=str(error))

    def read(self):
        try:
            self.last_report = json.loads((self.folder / 'game.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        record = self.last_report
        assert 'network' not in record, 'A standalone match created a network driver'
        current = record.get('snapshot', {})
        if current.get('hosted'):
            assert current.get('mode') == 'single_player', 'StartSinglePlayer entered a different game mode'
            assert current.get('ai_difficulty') == self.difficulty, 'Requested AI difficulty was not applied'
            assert current.get('connected') == 2, 'The human and AI seats are not both available'
            assert current['view']['ruleset'] == self.ruleset, 'Requested ruleset was not applied'
            assert_private_human_view(current)
            key = (current['match_id'], current['view']['revision'])
            if key != self.last_key:
                if self.last_key and key[0] == self.last_key[0]:
                    assert key[1] > self.last_key[1], 'Game revision moved backwards within a match'
                self.last_key = key
                self.observed_revisions += 1
                with (self.folder / 'observed-states.jsonl').open('a') as journal:
                    journal.write(json.dumps({'elapsed': round(time.monotonic() - self.started, 3),
                                              'snapshot': current}, separators=(',', ':')) + '\n')
            choice = current['view'].get('choice')
            if choice and choice['player'] == 1:
                self.observed_choices.add(key)
        return record

    def snapshot(self):
        return self.read().get('snapshot', {})

    def wait(self, description, predicate, timeout=45):
        deadline = min(self.started + self.args.timeout, time.monotonic() + timeout)
        progress = time.monotonic()
        while time.monotonic() < deadline:
            if self.processes and not self.expected_exit and self.processes[0].poll() is not None:
                raise RuntimeError(f'Game exited {self.processes[0].returncode} during {description}')
            result = predicate()
            if result:
                return result
            if time.monotonic() - progress >= 25:
                print(f'{self.folder.name}: waiting for {description}', flush=True)
                progress = time.monotonic()
            time.sleep(.1)
        raise AssertionError(f'Timed out: {description}; inspect {self.folder}')

    def command(self, action, acknowledge=True, **fields):
        self.sequence += 1
        write_json(self.folder / 'game.control.json', dict(sequence=self.sequence, action=action, **fields))
        if acknowledge:
            self.wait(f'accept {action}', lambda: self.read().get('sequence', -1) >= self.sequence, 15)

    def assert_profile(self):
        assert self.profile.read_bytes() == self.profile_bytes, 'Solo play changed the saved remote reconnect profile'
        assert stat.S_IMODE(self.profile.stat().st_mode) == 0o600
        assert stat.S_IMODE(self.profile.parent.stat().st_mode) == 0o700
        assert [path.name for path in self.profile.parent.iterdir()] == ['reconnect.json'], 'Solo play created an extra profile file'
        record = self.read()
        assert record.get('profile_enabled') and record.get('profile_loaded'), 'Existing profile fixture was not loaded'
        assert record.get('has_seat_token') and record.get('same_seat_token'), 'Solo play replaced the loaded remote seat token'
        assert record.get('last_address') == self.saved_endpoint, 'Solo play changed the saved remote endpoint'
        assert record.get('last_server_session') == self.saved_session, 'Solo play changed the saved remote server session'

    def capture(self, label, settle=True):
        if not self.dimensions:
            return
        # Wait through ordinary reports so runtime failures remain observable.
        if settle:
            settle_until = time.monotonic() + self.args.settle
            self.wait('settle the rendered HUD', lambda: self.read() and time.monotonic() >= settle_until, self.args.settle + 10)
        path = self.folder / f'{label}.png'
        self.command('screenshot', filename=str(path))

        def complete():
            try:
                data = path.read_bytes()
            except FileNotFoundError:
                return False
            if data[:8] != b'\x89PNG\r\n\x1a\n' or not data.endswith(b'IEND\xaeB`\x82'):
                return False
            assert (int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')) == self.dimensions, \
                'Native screenshot dimensions do not match the requested resolution'
            return data

        data = self.wait(f'capture {label}', complete, 30)
        self.captures[label] = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        write_json(self.folder / f'{label}.state.json', self.read())
        print(f'{self.folder.name}: captured {label}', flush=True)

    def play_until(self, description, predicate, timeout):
        last_revision = self.last_key
        last_progress, last_skip = time.monotonic(), 0.0

        def advance():
            nonlocal last_revision, last_progress, last_skip
            record = self.read()
            current = record.get('snapshot', {})
            if predicate(current):
                return current
            now = time.monotonic()
            if self.last_key != last_revision:
                self.max_revision_gap = max(self.max_revision_gap, now - last_progress)
                last_revision, last_progress = self.last_key, now
            assert now - last_progress < self.args.stall_timeout, \
                f'AI/human game made no revision progress for {self.args.stall_timeout:g}s; ' \
                f'status={current.get("view", {}).get("status")}, choice={current.get("view", {}).get("choice")}'
            if record.get('hud', {}).get('cinematic_busy') and now - last_skip >= .35:
                self.command('skip_cinematics')
                self.skips += 1
                last_skip = time.monotonic()
            return False

        return self.wait(description, advance, timeout)

    def run(self):
        result = {'ruleset': self.ruleset, 'difficulty': self.difficulty, 'seed': self.seed,
                  'rendered': bool(self.dimensions), 'resolution': self.dimensions, 'logs': str(self.folder)}
        try:
            self.launch()
            self.wait('open the normal player menu', lambda: self.snapshot().get('hosted') is False, 90)
            self.command('pause')
            self.assert_profile()
            self.capture('00-single-player-menu')
            menu_layout = assert_menu_layout(self.read()['hud']) if self.dimensions else None
            if menu_layout:
                write_json(self.folder / 'menu-layout.json', menu_layout)
                self.checked('All six real single-player menu choices fit without overlap or clipped text')
            self.command('single_player', ruleset=self.ruleset, difficulty=self.difficulty)
            self.wait('start the requested solo game', lambda: self.snapshot().get('mode') == 'single_player')
            self.assert_profile()
            first = self.snapshot()
            assert first['view']['status'] == 'selection', 'Solo play skipped human camp selection'
            assert len(first['view']['players'][0]['offers']) == 6, 'Human did not receive six legal camp offers'
            self.checked('StartSinglePlayer creates human seat zero and the requested AI/ruleset without a network driver')
            self.capture('01-human-camp-selection')
            if self.dimensions:
                options = self.read()['hud'].get('camp_options', [])
                assert len(options) == 6, 'The rendered solo draft does not expose six camp options'
                for option in options:
                    assert all(a + .5 >= d for a, d in zip(option['allocated_size'], option['desired_size'])), \
                        f'A solo camp option has clipped text: {option}'
                self.checked('All six actual solo camp descriptions receive their full wrapped text size')
            self.command('resume')
            self.play_until('complete both camp selections', lambda state: state.get('view', {}).get('status') == 'actions', 60)
            if self.dimensions:
                self.command('pause')
                self.command('skip_cinematics')
                self.capture('02-playing-against-ai')
                self.command('resume')
            finished = self.play_until('complete a legal game against the AI',
                lambda state: state.get('view', {}).get('status') in ('won', 'draw'), self.args.match_timeout)
            self.command('pause')
            self.command('skip_cinematics')
            assert finished['view']['revision'] > first['view']['revision'] + 2, 'The game did not play through real turns'
            assert finished['view']['choice'] is None, 'Finished solo game retains an unresolved choice'
            assert finished.get('ai_actions', 0) > 0, 'No actual AI decisions were recorded in the completed game'
            self.checked('The actual AI and legal-action human finish a match without a stalled turn or choice')
            self.capture('03-finished-solo-game')
            write_json(self.folder / 'finished.json', finished)
            self.command('rematch')
            rematch = self.wait('start a rematch from one human vote', lambda: (
                current if (current := self.snapshot()).get('hosted') and current.get('match_id') != finished['match_id']
                and current['view']['status'] == 'selection' else False))
            assert rematch.get('rematch_votes') == [False, False], 'Rematch did not clear its votes'
            self.checked('One human rematch vote creates a fresh solo game with the same difficulty and ruleset')
            self.capture('04-solo-rematch')
            self.command('resume')
            self.play_until('play real actions in the rematch', lambda state:
                state.get('view', {}).get('status') == 'actions' and state['view']['turn'] >= 2, 60)
            self.command('pause')
            self.command('leave')
            self.wait('return to a usable menu', lambda: self.snapshot().get('hosted') is False)
            self.assert_profile()
            self.capture('05-returned-menu')
            if self.dimensions:
                assert_menu_layout(self.read()['hud'])
            self.checked('Leave returns to the normal menu and preserves the existing private remote reconnect profile')
            self.expected_exit = True
            self.command('quit', acknowledge=False)
            self.wait('quit normally', lambda: self.processes[0].poll() is not None, 30)
            assert self.processes[0].returncode == 0, f'Normal Quit returned {self.processes[0].returncode}'
            self.checked('The normal Quit action exits with code zero')
            log_path = self.folder / 'game.log'
            log = log_path.read_text(errors='replace')
            assert not game_net_driver_ports(log), 'Solo play created a GameNetDriver listener'
            assert 'OLDWEST_TEST_ERROR' not in log and 'OLDWEST_AI_ERROR' not in log, 'A native bot rejected or failed an action'
            assert self.token not in log and self.token not in (self.folder / 'game-console.log').read_text(errors='replace'), \
                'The saved remote credential appeared in a game log'
            assets = assert_runtime_assets([log_path])
            self.checked('Human views keep AI private information hidden and the one-game run opens no multiplayer listener')
            result.update(ok=True, checks=self.checks, menu_layout=menu_layout,
                finished_status=finished['view']['status'], winner=finished['view']['winner'],
                final_revision=finished['view']['revision'], turns=finished['view']['turn'], runtime_assets=assets,
                ai_actions=finished['ai_actions'], ai_choices=finished.get('ai_choices', 0),
                game_processes_launched=len(self.processes), transport='standalone; no GameNetDriver',
                observed_revisions=self.observed_revisions, observed_ai_choice_revisions=len(self.observed_choices),
                maximum_observed_progress_gap_seconds=round(self.max_revision_gap, 3),
                cinematic_skips=self.skips, screenshots=self.captures,
                profile={'fixture': 'isolated pre-existing remote reconnect credentials', 'loaded': True,
                         'unchanged': True, 'directory_mode': '0700', 'file_mode': '0600'},
                limitations=['Automated legal-action human; these games do not measure human enjoyment or AI strength.',
                             'Test-only AI pacing bypasses waiting for presentation; cinematic skips also accelerate verification.',
                             'AI choice observations are sampled; zero observations do not prove a choice path was exercised.',
                             'Rendered screenshots require visual review; headless games provide no visual-quality evidence.'])
        except Exception as error:
            result.update(ok=False, failure=str(error), completed_checks=self.checks, screenshots=self.captures)
            # Preserve the most recent complete report even if map travel has
            # temporarily removed its live file or the child has crashed.
            write_json(self.folder / 'last-observed-report.json', self.last_report)
        finally:
            try:
                stop_owned_process_groups(self.processes, self.streams)
            except Exception as error:
                result.update(ok=False, cleanup_failure=str(error))
            self.record_build_result(result)
            result['elapsed_seconds'] = round(time.monotonic() - self.started, 2)
            write_json(self.folder / 'result.json', result)
        return result


class NormalPacingScenario(SoloScenario):
    """Observe production AI timing with a paused human and ordinary actions."""

    @staticmethod
    def ai_can_act(snapshot):
        view = snapshot.get('view', {})
        if view.get('status') == 'selection':
            return not view.get('players', [{}, {}])[1].get('selected', False)
        if view.get('status') != 'actions':
            return False
        choice = view.get('choice')
        return choice.get('player') == 1 if choice else view.get('active_player') == 1

    def human_step(self):
        """Only submit an advertised human command while presentation is idle."""
        record = self.read()
        current = record.get('snapshot', {})
        assert record.get('bot_paused') is True, 'Human TestBot unexpectedly resumed during pacing verification'
        if record.get('cinematic', {}).get('busy') or not current.get('actions'):
            return False
        actions = current['actions']
        # End ordinary human turns promptly, and answer real pending choices.
        # Initial camp selection comes directly from the 120 legal permutations.
        selected = next((action for action in actions if action['command']['type'] == 'end_turn'), actions[0])
        self.command('submit', command=selected['command'], revision=current['view']['revision'],
                     match_id=current['match_id'])
        self.wait('apply a controlled legal human action', lambda:
                  self.snapshot().get('view', {}).get('revision', -1) > current['view']['revision'], 10)
        return True

    def modal_pause(self, modal):
        self.command(modal, **({'open': True} if modal == 'rules' else {'operation': 'open'}))

        def is_open():
            hud = self.read().get('hud', {})
            return hud.get('rules_open') if modal == 'rules' else hud.get('settings', {}).get('open')

        self.wait(f'open {modal}', is_open, 5)
        original = self.snapshot()
        assert self.ai_can_act(original), f'{modal} opened when the AI had no pending decision to pause'
        actions, revision = original['ai_actions'], original['view']['revision']
        until = time.monotonic() + 2.0

        def remains_paused():
            current = self.snapshot()
            assert is_open(), f'{modal} closed during its pause check'
            assert current['ai_actions'] == actions and current['view']['revision'] == revision, \
                f'AI advanced while {modal} covered the game'
            return time.monotonic() >= until

        self.wait(f'hold {modal} over a ready AI for two seconds', remains_paused, 5)
        self.capture(f'normal-pacing-{modal}')
        remains_paused()
        self.command(modal, **({'open': False} if modal == 'rules' else {'operation': 'close'}))
        self.wait(f'close {modal}', lambda: not is_open(), 5)
        self.checked(f'The AI has a legal decision but waits while {modal} stays open for two seconds')
        return {'modal': modal, 'seconds_at_least': 2.0, 'ai_actions': actions, 'revision': revision}

    def run(self):
        result = {'ruleset': self.ruleset, 'difficulty': self.difficulty, 'seed': self.seed,
                  'rendered': bool(self.dimensions), 'resolution': self.dimensions, 'logs': str(self.folder),
                  'normal_pacing_only': True, 'test_ai_delay_override': False, 'cinematic_skips': 0}
        samples, window, verified, natural_end = [], None, None, None
        try:
            self.launch()
            self.wait('open the normal player menu', lambda: self.snapshot().get('hosted') is False, 90)
            self.command('pause')
            self.assert_profile()
            self.command('single_player', ruleset=self.ruleset, difficulty=self.difficulty)
            self.wait('start the requested solo game', lambda: self.snapshot().get('mode') == 'single_player')

            def ready_opportunity():
                current = self.snapshot()
                # A pending draft is also a real AI decision and has no visual
                # side effects. If already selected, advance the human legally.
                if self.ai_can_act(current):
                    return current
                self.human_step()
                return False

            self.wait('reach an ordinary AI decision', ready_opportunity, 30)
            modal_checks = [self.modal_pause('rules'), self.modal_pause('settings')]
            after_modals = self.snapshot()['ai_actions']
            self.wait('AI resumes after both menus close', lambda: self.snapshot()['ai_actions'] > after_modals, 8)
            self.checked('Closing Rules and Settings lets the AI resume with production pacing')

            def observe():
                nonlocal window, verified, natural_end
                record = self.read()
                current = record.get('snapshot', {})
                cinematic = record.get('cinematic', {})
                assert record.get('bot_paused') is True, 'Human TestBot resumed during the cinematic observation'
                assert current['view']['status'] not in ('won', 'draw'), 'Game ended before a usable AI cinematic was observed'
                sample = {'observed_seconds': round(time.monotonic() - self.started, 4),
                    'ai_actions': current['ai_actions'], 'revision': current['view']['revision'],
                    'ai_can_act': self.ai_can_act(current), 'busy': cinematic.get('busy', False),
                    'sequence': cinematic.get('sequence'), 'kind': cinematic.get('kind'),
                    'elapsed': cinematic.get('elapsed', 0),
                    'frames': cinematic.get('frame_timing', {}).get('frames')}
                samples.append(sample)
                if verified is not None:
                    if not sample['busy'] and natural_end is None:
                        natural_end = sample
                    if current['ai_actions'] > verified['ai_actions']:
                        assert natural_end is not None, 'AI advanced before an idle report after the observed cinematic'
                        result['resumed_action'] = sample
                        return True
                    return False
                if sample['busy'] and sample['ai_can_act'] and sample['sequence'] is not None:
                    if window is None or sample['sequence'] != window['sequence']:
                        window = sample
                    else:
                        assert sample['ai_actions'] == window['ai_actions'], 'AI advanced while the same cinematic was still playing'
                        # Native elapsed time and two distinct reports establish
                        # a real ongoing shot rather than repeated stale reads.
                        if sample['elapsed'] - window['elapsed'] >= .25:
                            verified = sample
                            result['cinematic_window'] = {'first': window, 'last': sample,
                                'duration_seconds': round(sample['elapsed'] - window['elapsed'], 4)}
                            self.capture('normal-pacing-ai-cinematic', settle=False)
                elif not sample['busy']:
                    window = None
                    self.human_step()
                return False

            self.wait('observe an AI cinematic and its naturally resumed decision', observe, 120)
            result['natural_cinematic_end'] = natural_end
            result['observed_delay_after_cinematic_seconds'] = round(
                result['resumed_action']['observed_seconds'] - natural_end['observed_seconds'], 4)
            result['ai_actions'] = self.snapshot()['ai_actions']
            result['ai_choices'] = self.snapshot().get('ai_choices', 0)
            write_json(self.folder / 'normal-pacing-samples.json', samples)
            self.checked('AI action count stays fixed throughout an ongoing cinematic, then advances after it ends naturally')
            self.capture('normal-pacing-resumed')
            self.command('leave')
            self.wait('return to the normal menu', lambda: self.snapshot().get('hosted') is False)
            self.assert_profile()
            self.expected_exit = True
            self.command('quit', acknowledge=False)
            self.wait('quit normally', lambda: self.processes[0].poll() is not None, 30)
            assert self.processes[0].returncode == 0, f'Normal Quit returned {self.processes[0].returncode}'
            log_path = self.folder / 'game.log'
            log = log_path.read_text(errors='replace')
            assert not game_net_driver_ports(log), 'Normal solo play opened a multiplayer listener'
            assert 'OLDWEST_AI_ERROR' not in log and 'OLDWEST_TEST_ERROR' not in log
            assert self.token not in log and self.token not in (self.folder / 'game-console.log').read_text(errors='replace')
            self.checked('Normal pacing stays offline, preserves private reconnect credentials, and leaves/quits cleanly')
            result.update(ok=True, checks=self.checks, modal_checks=modal_checks, screenshots=self.captures,
                runtime_assets=assert_runtime_assets([log_path]), observed_revisions=self.observed_revisions,
                game_processes_launched=len(self.processes),
                limitations=['This focused scenario does not complete a match or measure AI strength.',
                             'Assertions sample actual native presentation state; headless runs make no visual-quality claim.',
                             'Rules/Settings use the ordinary UI handlers through nonshipping diagnostic commands.'])
        except Exception as error:
            result.update(ok=False, failure=str(error), completed_checks=self.checks, screenshots=self.captures)
            write_json(self.folder / 'last-observed-report.json', self.last_report)
            write_json(self.folder / 'normal-pacing-samples.json', samples)
        finally:
            try:
                stop_owned_process_groups(self.processes, self.streams)
            except Exception as error:
                result.update(ok=False, cleanup_failure=str(error))
            self.record_build_result(result)
            result['elapsed_seconds'] = round(time.monotonic() - self.started, 2)
            write_json(self.folder / 'result.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--difficulties', nargs='+', choices=DIFFICULTIES, default=list(DIFFICULTIES))
    parser.add_argument('--rulesets', nargs='+', choices=RULESETS, default=list(RULESETS))
    parser.add_argument('--seed', type=int, default=20260911, help='Base seed; each ruleset/difficulty receives a stable legal deal')
    parser.add_argument('--timeout', type=float, default=480, help='Hard wall-clock limit per game process, including startup and shutdown')
    parser.add_argument('--match-timeout', type=float, default=300, help='Maximum seconds to finish the first match in each scenario')
    parser.add_argument('--stall-timeout', type=float, default=35, help='Fail an active match if no game revision advances for this many seconds')
    parser.add_argument('--render', action='store_true', help='After the headless matrix, add complete 720p and 1080p visual scenarios')
    parser.add_argument('--render-only', action='store_true', help='Run only the two rendered scenarios; implies --render')
    parser.add_argument('--normal-pacing-only', action='store_true',
                        help='Focused production-pacing and Rules/Settings pause check; no fast-AI override or cinematic skips')
    parser.add_argument('--settle', type=float, default=1.5, help='Seconds of ordinary rendering before each screenshot')
    args = parser.parse_args()
    if not 0 <= args.seed < 2**64 - 6:
        parser.error('--seed must allow six consecutive unsigned 64-bit seeds')
    if min(args.timeout, args.match_timeout, args.stall_timeout) <= 0 or args.settle < 0:
        parser.error('Timeouts must be positive and --settle must be nonnegative')
    if len(set(args.difficulties)) != len(args.difficulties) or len(set(args.rulesets)) != len(args.rulesets):
        parser.error('Repeated difficulties or rulesets are not allowed')
    folder = create_native_run_directory('oldwest-native-singleplayer-')
    started, results = time.monotonic(), []
    print(f'Native single-player reports: {folder}', flush=True)
    scenarios = []
    if args.normal_pacing_only:
        difficulty = 'normal' if 'normal' in args.difficulties else args.difficulties[0]
        sizes = ((1280, 720), (1920, 1080)) if args.render or args.render_only else (None,)
        scenarios.extend((args.rulesets[0], difficulty, size) for size in sizes)
    elif not args.render_only:
        scenarios.extend((ruleset, difficulty, None) for ruleset in args.rulesets for difficulty in args.difficulties)
    if (args.render or args.render_only) and not args.normal_pacing_only:
        difficulty = 'normal' if 'normal' in args.difficulties else args.difficulties[0]
        scenarios.extend((args.rulesets[0], difficulty, size) for size in ((1280, 720), (1920, 1080)))
    for ruleset, difficulty, dimensions in scenarios:
        seed = args.seed + RULESETS.index(ruleset) * len(DIFFICULTIES) + DIFFICULTIES.index(difficulty)
        scenario_type = NormalPacingScenario if args.normal_pacing_only else SoloScenario
        result = scenario_type(args, folder, ruleset, difficulty, seed, dimensions).run()
        results.append(result)
        artifact_identities = {tuple((key, item.get('build', {}).get(key, {}).get('sha256'))
                                    for key in ('executable', 'launcher', 'manifest', 'module')) for item in results}
        consistent_artifacts = len(artifact_identities) == 1
        aggregate = dict(ok=all(item['ok'] for item in results), complete=len(results) == len(scenarios),
            runtime='packaged Linux game' if args.package_dir else 'Unreal Editor game runtime',
            package_directory=str(args.package_dir.resolve()) if args.package_dir else None,
            logs=str(folder), scenarios_requested=len(scenarios), scenarios_completed=len(results),
            difficulty_ruleset_matrix_requested=not args.render_only and not args.normal_pacing_only,
            normal_pacing_only=args.normal_pacing_only,
            all_difficulties_and_rulesets_requested=not args.render_only and not args.normal_pacing_only and set(args.difficulties) == set(DIFFICULTIES)
                and set(args.rulesets) == set(RULESETS), rendered_requested=args.render or args.render_only,
            actual_ai_actions=sum(item.get('ai_actions', 0) for item in results),
            actual_ai_choices=sum(item.get('ai_choices', 0) for item in results),
            build=results[0].get('build', {}),
            tested_artifacts_unchanged=all(item.get('tested_artifacts_unchanged') is True for item in results),
            same_artifacts_across_scenarios=consistent_artifacts,
            results=results, elapsed_seconds=round(time.monotonic() - started, 2))
        if not consistent_artifacts:
            aggregate.update(ok=False, artifact_failure='The game artifacts changed between single-player scenarios')
        write_json(folder / 'result.json', aggregate)
        # Publish each completed scenario, including failures, so interrupted
        # long matrices remain discoverable. Keep mode-specific aliases too.
        report_dir = ROOT / 'game/tests/reports'
        report_dir.mkdir(parents=True, exist_ok=True)
        names = ['latest-native-singleplayer-pacing.json'] if args.normal_pacing_only else ['latest-native-singleplayer.json']
        if args.package_dir:
            names.append('latest-packaged-singleplayer-pacing.json' if args.normal_pacing_only else 'latest-packaged-singleplayer.json')
        if args.render_only and not args.normal_pacing_only:
            names += ['latest-native-singleplayer-rendered.json']
            if args.package_dir:
                names += ['latest-packaged-singleplayer-rendered.json']
        for name in names:
            write_json(report_dir / name, aggregate)
    print(json.dumps(aggregate, indent=2), flush=True)
    raise SystemExit(0 if aggregate['ok'] and aggregate['complete'] else 1)


if __name__ == '__main__':
    main()
