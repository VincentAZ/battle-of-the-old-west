#!/usr/bin/env python3
"""Observe real native matches and capture local cinematic timing/poses.

Uses legal TestBot actions and the existing opt-in visual/lifecycle bridge.
Does not inject state, edit rule results, or manufacture screenshots.
"""
import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from native_runtime_checks import assert_runtime_assets
from native_launch import create_native_run_directory, game_net_driver_ports, resolve_native_launch, stop_owned_process_groups

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path, help='Run the bundled launcher from an actual cooked Linux package')
    parser.add_argument('--port', type=int, default=19286)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--ruleset', default='boomtown', choices=['base_2024', 'boomtown'])
    parser.add_argument('--audio', action='store_true', help='Enable live audio on the rendered client (not an audio quality test)')
    parser.add_argument('--profile-renderer', action='store_true',
                        help='Retain native frame counters and lifecycle report costs without changing rendering or physics settings')
    parser.add_argument('--record-contacts', action='store_true',
                        help='Record engine collision notifications and capture slow falls; does not change settling or solver settings')
    parser.add_argument('--physics-only', action='store_true',
                        help='Run the real scene with NullRHI and record physics/state only; publishes a separate diagnostic report')
    parser.add_argument('--require-rig-iterations', action='store_true',
                        help='Require the authored 12/4/1 iteration overrides on every live ragdoll body')
    parser.add_argument('--diagnostic-fall', action='store_true',
                        help='Opt-in non-shipping hold records failed falls through 3.5 s; strict assertions still fail')
    parser.add_argument('--disable-nanite', action='store_true',
                        help='Disable Nanite on the rendered client for a diagnostic comparison; no asset changes')
    parser.add_argument('--seed', type=int, default=731846,
                        help='Explicit server test seed for repeatable deals; only the gated native test hook accepts it')
    parser.add_argument('--physics-substeps', action='store_true',
                        help='Diagnostic per-client INI override: at most eight 1/120 s physics substeps; no config file edits')
    parser.add_argument('--solver-velocity-iterations', type=int,
                        help='Diagnostic world-solver velocity iteration override on client A; does not change the saved rig')
    parser.add_argument('--projection-velocity-alpha', type=float,
                        help='Diagnostic projection velocity feedback factor; preserves position projection and hard joint limits')
    parser.add_argument('--joint-damping', type=float,
                        help='Diagnostic passive angular joint damping with zero stiffness/velocity target; requires --diagnostic-fall')
    parser.add_argument('--nonlinear-joints', action='store_true',
                        help='Request nonlinear joints on older diagnostic builds; current production already uses them')
    parser.add_argument('--natural-joint-mass', action='store_true',
                        help='Request joint conditioning off on older builds; current production already disables it')
    parser.add_argument('--no-joint-projection', action='store_true',
                        help='Request joint projection off on older builds; current production already disables it')
    parser.add_argument('--diagnostic-fall-limit', type=float,
                        help='Override the local fall ceiling for a diagnostic; use --completion-deadline to reproduce an older acceptance limit')
    parser.add_argument('--completion-deadline', type=float, default=6.15,
                        help='Maximum observed completed-shot time; default matches the six-second ceiling plus frame tolerance; 4.15 reproduces the former contract')
    parser.add_argument('--build-label', default='', help='Coordinator build identifier recorded with source/module hashes')
    parser.add_argument('--capture-crowded-entrance', action='store_true',
                        help='Also capture an entrance beside another living person for deployment-layout review')
    parser.add_argument('--controlled-actions', action='store_true',
                        help='Keep native bots paused and submit a repeatable legal action stream after each presentation')
    parser.add_argument('--capture-settled-target', type=int,
                        help='Capture a requested public target during its stable fall interval for anatomical visual review')
    parser.add_argument('--capture-fall-card', choices=sorted(
        card['id'] for card in json.loads((ROOT / 'game/data/cards.json').read_text())['cards'] if card['type'] == 'person'),
                        help='Capture late and settled falls of this public character across rematches')
    parser.add_argument('--require-shader-platform', choices=['VULKAN_SM5', 'VULKAN_SM6'],
                        help='Fail if the rendered client actually initializes a different shader platform')
    parser.add_argument('--early-settle-deadline', type=float,
                        help='Optional legacy diagnostic: require settling by this shot time, regardless of actual shot completion')
    parser.add_argument('--frame-cap', type=int, default=60,
                        help='Explicit rendered-client maximum FPS for repeatable comparisons (default: 60)')
    parser.add_argument('--compare-baseline', type=Path,
                        help='Record whether another run has matching binary/assets, seed, shader platform, cap and legal action prefix')
    parser.add_argument('--physics-trial', choices=['none', 'no_projection', 'no_restitution', 'no_projection_no_restitution'], default='none',
                        help='Diagnostic physics overrides; comparison counts projection and restitution as separate changed conditions')
    args = parser.parse_args()
    if args.physics_only and (args.audio or args.require_shader_platform or args.disable_nanite):
        parser.error('--physics-only cannot assess audio, shader platforms or Nanite')
    if not 0 <= args.seed < 2**64: parser.error('--seed must be an unsigned 64-bit integer')
    if not 1 <= args.frame_cap <= 240: parser.error('--frame-cap must be between 1 and 240')
    if args.early_settle_deadline is not None and not 0 < args.early_settle_deadline <= 4:
        parser.error('--early-settle-deadline must be greater than 0 and at most 4 seconds')
    if args.solver_velocity_iterations is not None and not 1 <= args.solver_velocity_iterations <= 32:
        parser.error('--solver-velocity-iterations must be between 1 and 32')
    if args.projection_velocity_alpha is not None and not 0 <= args.projection_velocity_alpha <= 1:
        parser.error('--projection-velocity-alpha must be between zero and one')
    if args.joint_damping is not None and (not args.diagnostic_fall or not 0 < args.joint_damping <= 100):
        parser.error('--joint-damping requires --diagnostic-fall and a value greater than 0 and at most 100')
    if args.diagnostic_fall_limit is not None and not 4 <= args.diagnostic_fall_limit <= 6:
        parser.error('--diagnostic-fall-limit must be between 4 and 6 seconds')
    if not 1.95 <= args.completion_deadline <= 6.15:
        parser.error('--completion-deadline must be between 1.95 and 6.15 seconds')
    folder = create_native_run_directory('oldwest-native-cinematics-')
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=folder, editor_directory=ROOT)
    kind = 'physics' if args.physics_only else 'cinematics'
    report_path = ROOT/'game/tests/reports'/f'latest-{"packaged" if runtime.package_root else "native"}-{kind}.json'
    def signature(path):
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    modified_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
    if runtime.package_root:
        binaries = runtime.package_root/'OldWest/Binaries/Linux'
        executable = next((path for path in (binaries/'OldWestGame', binaries/'OldWestGame-Linux-Development') if path.is_file()), None)
        if executable is None: raise FileNotFoundError(f'No packaged OldWestGame executable under {binaries}')
        build = dict(label=args.build_label, mode='packaged_game', package_root=str(runtime.package_root),
                     executable=signature(executable), manifest=signature(runtime.package_root/'package-manifest.json'))
    else:
        build = dict(label=args.build_label, mode='editor_game',
                 module=signature(ROOT/'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'),
                 source=signature(ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp'),
                 assets=[signature(ROOT/'game/OldWest/Content'/name) for name in (
                     'Art/Survivors/SurvivorA/SKM_Survivor_A_Cm.uasset',
                     'Art/Survivors/SurvivorA/PA_Survivor_Anatomical.uasset',
                     'Art/WaterDepotV2/Meshes/SM_ContinuousTerrain.uasset',
                     'Art/WaterDepotV2/Meshes/SM_ContinuousTerrain_Collision.uasset',
                     'Maps/WaterDepotV2.umap')])
        build['identity_meshes'] = [signature(path) for path in sorted(
            (ROOT/'game/OldWest/Content/Art/Survivors/Identities').glob('SKM_*.uasset'))]
    (folder/'build.json').write_text(json.dumps(build, indent=2)+'\n')
    processes, streams, controls = {}, [], {'a': 0, 'b': 0}
    performance_keys, performance_enabled_peers = set(), set()
    revision_stability_samples = []
    observed, captures, frames, seen, captured = set(), {}, [], set(), set()
    started = time.monotonic()
    deadline = started + args.timeout
    audio_started = False
    max_root_drift = 0.
    max_follow_error = 0.
    minimum_physics_time_ratio = 1.
    action_trace = []
    completed_falls, completed_keys = [], set()
    diagnostic_trajectory_sequence = None
    action_random = {name: random.Random(args.seed + index) for index, name in enumerate(('a', 'b'))}
    next_action_at = started
    def trial_conditions(trial):
        return {'joint_projection_disabled': trial in ('no_projection', 'no_projection_no_restitution'),
                'collision_restitution_disabled': trial in ('no_restitution', 'no_projection_no_restitution')}
    conditions = trial_conditions(args.physics_trial)
    trial_cvars = [cvar for key, cvar in (
        ('joint_projection_disabled', 'p.Chaos.Solver.Iterations.Projection'),
        ('collision_restitution_disabled', 'p.CollisionRestitution')) if conditions[key]]
    solver_cvar = 'p.Chaos.Solver.Iterations.Velocity'
    projection_velocity_cvar = 'p.Chaos.Joint.VelProjectionAlpha'
    renders = ['-RenderOffscreen', '-windowed', '-ForceRes', '-ResX=1920', '-ResY=1080']

    def launch(name, parameters, render=False):
        stream = (folder/f'{name}-console.log').open('w'); streams.append(stream)
        options = ['-unattended', '-nosplash', '-NoLiveCoding', '-stdout', '-FullStdOutLogOutput',
                   '-OldWestLifecycleTest', '-OldWestVisualTest', f'-abslog={folder/name}.log',
                   f'-GameUserSettingsINI={folder}/{name}-settings.ini']
        if not render or not args.audio: options.append('-nosound')
        if args.profile_renderer: options.append('-OldWestPresentationProfile')
        if render and args.record_contacts:
            options.append(f'-OldWestRagdollContactReport={folder}/ragdoll-contacts.jsonl')
        if render and args.diagnostic_fall: options.append('-OldWestCinematicDiagnostic')
        if render and args.joint_damping is not None:
            options.append(f'-OldWestRagdollJointDamping={args.joint_damping}')
        if render and args.nonlinear_joints:
            options.append('-OldWestRagdollNonlinearSolver')
        if render and args.natural_joint_mass:
            options.append('-OldWestRagdollNaturalMass')
        if render and args.no_joint_projection:
            options.append('-OldWestRagdollNoJointProjection')
        if render and args.diagnostic_fall_limit is not None:
            options.append(f'-OldWestFallTimeLimit={args.diagnostic_fall_limit}')
        if render:
            exec_commands = [f't.MaxFPS {args.frame_cap}']
            if args.disable_nanite: exec_commands.append('r.Nanite 0')
            for cvar in trial_cvars: exec_commands.extend([cvar + ' 0', cvar])
            if args.solver_velocity_iterations is not None:
                exec_commands.extend([f'{solver_cvar} {args.solver_velocity_iterations}', solver_cvar])
            if args.projection_velocity_alpha is not None:
                exec_commands.extend([f'{projection_velocity_cvar} {args.projection_velocity_alpha}', projection_velocity_cvar])
            else:
                exec_commands.append(projection_velocity_cvar)
            options.append('-ExecCmds=' + ','.join(exec_commands))
        if render and args.physics_substeps:
            options.extend('-ini:Engine:[/Script/Engine.PhysicsSettings]:' + value for value in (
                'bSubstepping=True', 'MaxSubstepDeltaTime=0.008333333', 'MaxSubsteps=8'))
        process = subprocess.Popen([*runtime.argv, *parameters, *options, *(renders if render and not args.physics_only else ['-nullrhi'])],
                                   cwd=runtime.cwd, env=runtime.env, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes[name] = process
        (folder/'native-launches.json').write_text(json.dumps(
            {peer: child.args for peer, child in processes.items()}, indent=2)+'\n')

    def read(name):
        try: state = json.loads((folder/f'{name}.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError): return {}
        if args.profile_renderer:
            if state.get('cinematic', {}).get('frame_performance', {}).get('enabled'):
                performance_enabled_peers.add(name)
            profile = state.get('lifecycle_profile_previous_report')
            if isinstance(profile, dict):
                key = (name, profile.get('match_id'), profile.get('native_frame'), profile.get('command_sequence'))
                if key not in performance_keys:
                    performance_keys.add(key)
                    record = {'peer': name, **profile,
                        'observed_snapshot_revision': state.get('snapshot', {}).get('view', {}).get('revision'),
                        'observed_cinematic_sequence': state.get('cinematic', {}).get('sequence')}
                    with (folder/'lifecycle-performance.jsonl').open('a') as stream:
                        stream.write(json.dumps(record)+'\n')
        return state

    def renderer_evidence():
        path = folder/'a.log'
        log = path.read_text(errors='replace') if path.is_file() else ''
        found = re.findall(r'Metadata set\s*:\s*shaderplatform="([^"]+)"', log)
        shader_source = 'csv_metadata'
        if not found:
            found = re.findall(r'Vulkan RHI ShaderPlatform for [^:\r\n]+:\s*(VULKAN_SM[56])', log)
            shader_source = 'vulkan_rhi_initialization' if found else None
        terrain = read('a').get('cinematic', {}).get('terrain_renderer') or {}
        cap_confirmed = bool(re.search(r't\.MaxFPS\s*=\s*"?' + str(args.frame_cap) + r'(?:\.0+)?"?(?:\s|$)', log))
        trial_confirmed = bool(trial_cvars) and all(re.search(re.escape(cvar) + r'\s*=\s*"?0(?:\.0+)?"?(?:\s|$)', log) for cvar in trial_cvars)
        solver_confirmed = args.solver_velocity_iterations is not None and bool(re.search(
            re.escape(solver_cvar) + r'\s*=\s*"?' + str(args.solver_velocity_iterations) + r'"?(?:\s|$)', log))
        projection_values = re.findall(re.escape(projection_velocity_cvar) + r'\s*=\s*"?([0-9.]+)', log)
        projection_alpha = float(projection_values[-1]) if projection_values else None
        return dict(shader_platform=found[-1] if found else None,
                    shader_platform_source=shader_source,
                    requested_frame_cap=args.frame_cap, frame_cap_log_confirmed=cap_confirmed,
                    physics_trial_cvars=trial_cvars, physics_trial_zero_log_confirmed=trial_confirmed,
                    solver_velocity_iterations_override=args.solver_velocity_iterations,
                    solver_velocity_override_log_confirmed=solver_confirmed,
                    projection_velocity_alpha_actual=projection_alpha,
                    nanite_disable_requested=args.disable_nanite,
                    terrain=terrain, nanite_active=terrain.get('nanite_mesh_proxy'),
                    note='Nanite evidence comes from the live terrain scene proxy; null means not observed')

    def comparison_evidence():
        if not args.compare_baseline: return None
        baseline = args.compare_baseline.expanduser().resolve()
        previous = json.loads((baseline/'result.json').read_text())
        previous_actions = json.loads((baseline/'controlled-actions.json').read_text())
        def fingerprints(data):
            entries = list(data.get('assets', []))
            entries += [data[key] for key in ('module', 'executable', 'manifest') if key in data]
            return {Path(item['path']).name: item['sha256'] for item in entries}
        count = min(len(previous_actions), len(action_trace))
        varying = {}
        previous_conditions = {**trial_conditions(previous.get('physics_trial', 'none')),
            'nonlinear_joints': previous.get('nonlinear_joints', False),
            'natural_joint_mass': previous.get('natural_joint_mass', False),
            'no_joint_projection': previous.get('no_joint_projection', False),
            'diagnostic_fall_limit': previous.get('diagnostic_fall_limit'),
            'passive_joint_damping': previous.get('passive_joint_damping'),
            'solver_velocity_iterations_override': previous.get('solver_velocity_iterations_override'),
            'projection_velocity_alpha_override': previous.get('projection_velocity_alpha_override'),
            'rendering_disabled': previous.get('physics_only', False),
            'diagnostic_physics_substeps': previous.get('diagnostic_physics_substeps', False),
            'nanite_disabled': previous.get('nanite_disabled', False)}
        previous_conditions['record_contacts'] = previous.get('record_contacts', False)
        current_conditions = {**conditions, 'rendering_disabled': args.physics_only,
                              'nonlinear_joints': args.nonlinear_joints,
                              'natural_joint_mass': args.natural_joint_mass,
                              'no_joint_projection': args.no_joint_projection,
                              'diagnostic_fall_limit': args.diagnostic_fall_limit,
                              'passive_joint_damping': args.joint_damping,
                              'solver_velocity_iterations_override': args.solver_velocity_iterations,
                              'projection_velocity_alpha_override': args.projection_velocity_alpha,
                              'diagnostic_physics_substeps': args.physics_substeps,
                              'nanite_disabled': args.disable_nanite}
        current_conditions['record_contacts'] = args.record_contacts
        for key, value in current_conditions.items():
            if previous_conditions[key] != value:
                varying[key] = [previous_conditions[key], value]
        checks = dict(controlled_actions=args.controlled_actions and previous.get('controlled_actions', False),
                      same_seed=previous.get('server_test_seed') == args.seed,
                      same_ruleset=previous.get('ruleset') == args.ruleset,
                      same_diagnostic_hold=previous.get('diagnostic_fall_hold') == args.diagnostic_fall,
                      same_completion_deadline=previous.get('completion_deadline_seconds', 4.15) == args.completion_deadline,
                      same_artifacts=fingerprints(previous['build']) == fingerprints(build),
                      same_shader_platform=previous.get('renderer', {}).get('shader_platform') == renderer_evidence()['shader_platform'],
                      same_frame_cap=previous.get('renderer', {}).get('requested_frame_cap') == args.frame_cap,
                      same_legal_action_prefix=count > 0 and previous_actions[:count] == action_trace[:count],
                      at_most_one_condition_changed=len(varying) <= 1)
        reference = previous.get('failure_frame', {})
        event_fields = ('sequence', 'target', 'source', 'kind', 'before_damage', 'after_damage', 'target_location')
        reference_event = {key: reference[key] for key in event_fields if key in reference}
        matching_samples = [frame['cinematic'] for frame in frames if reference_event and all(
            frame['cinematic'].get(key) == value for key, value in reference_event.items())]
        return dict(ok=all(checks.values()), checks=checks, baseline=str(baseline), matched_action_count=count,
                    baseline_action_prefix_fully_replayed=len(action_trace) >= len(previous_actions),
                    baseline_failure_event=reference_event, baseline_event_samples=matching_samples,
                    varying_conditions=varying,
                    note='Matching inputs/action prefix validate setup. Baseline event samples compare the same public target/event; a different later failure is a separate case')

    def check_alive():
        for name, process in processes.items():
            if process.poll() is not None: raise RuntimeError(f'{name} exited ({process.returncode}); see {folder}')

    def wait(description, predicate, timeout=60):
        until = min(deadline, time.monotonic() + timeout)
        while time.monotonic() < until:
            check_alive()
            value = predicate()
            if value: return value
            time.sleep(.05)
        raise AssertionError(f'Timed out: {description}; {folder}')

    def command(client, action, **fields):
        controls[client] += 1
        path = folder/f'{client}.control.json'; temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=controls[client], action=action, **fields)))
        temporary.replace(path)
        wait(f'{client}: {action}', lambda: read(client).get('sequence', 0) >= controls[client], 10)

    def capture(label, state, match_cinematic=False):
        if args.physics_only:
            (folder/f'{label}.json').write_text(json.dumps(state, indent=2)+'\n')
            print(f'Recorded {label} physics/state (no image)', flush=True)
            return True
        path = folder/f'{label}.png'
        command('a', 'screenshot', filename=str(path))
        # The initial paused overview may still be warming SM6 pipelines.
        # Timed cinematic captures retain their short deadline and beat check.
        wait(f'{label} screenshot', lambda: path.exists() and path.stat().st_size > 10000, 12 if match_cinematic else 60)
        data = path.read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert int.from_bytes(data[16:20], 'big') == 1920 and int.from_bytes(data[20:24], 'big') == 1080
        if match_cinematic:
            current = read('a').get('cinematic', {})
            expected = state.get('cinematic', {})
            if not current.get('busy') or current.get('sequence') != expected.get('sequence'):
                path.rename(folder/f'{label}-missed-{expected.get("sequence", 0)}.png')
                print(f'Retrying {label}: presentation advanced while the screenshot was requested', flush=True)
                return False
        captures[label] = str(path)
        (folder/f'{label}.json').write_text(json.dumps(state, indent=2)+'\n')
        print(f'Captured {label}', flush=True)
        return True

    def capture_fall_followups(expected_sequence):
        # Apply the same screenshot workload whether the first strict check
        # passes or fails. Screenshot I/O affects frame timing on this machine.
        command('a', 'pause'); command('b', 'pause')
        remaining = [2., 2.5, 3., 3.5]
        samples = []
        until = time.monotonic() + 6
        while remaining and time.monotonic() < until:
            check_alive()
            sample = read('a'); current = sample.get('cinematic', {})
            if not current.get('busy') or current.get('sequence') != expected_sequence: break
            samples.append(sample)
            if current.get('elapsed', 0) >= remaining[0]:
                moment = remaining.pop(0)
                label = f'fall-followup-{moment:.1f}s'
                capture(label, sample, match_cinematic=True)
                (folder/f'{label}-completed.json').write_text(json.dumps(read('a'), indent=2)+'\n')
            time.sleep(.04)
        (folder/'failure-motion.json').write_text(json.dumps(
            [sample['cinematic'] for sample in samples], indent=2)+'\n')
        return samples

    def stability_failure(cinematic):
        participants = [cinematic, *cinematic.get('simultaneous_targets', [])]
        for member in participants:
            if not member.get('ragdoll'): continue
            physics = member['physics']
            if not physics.get('ground_found') or not -5 <= physics['pelvis_ground_clearance_cm'] <= 65:
                return 'Ragdoll did not remain near the ground during the diagnostic hold'
            if physics['max_speed_cm_s'] > 20 or physics['max_angular_speed_deg_s'] > 45:
                return 'Ragdoll did not remain settled during the diagnostic hold'
        return None

    print(f'Native cinematic observations: {folder}', flush=True)
    try:
        map_url = f'/Game/Maps/WaterDepotV2?Match=1?Ruleset={args.ruleset}?game=/Script/OldWestGame.OldWestGameMode'
        def player_parameters(name, destination):
            return [destination, '-game', '-OldWestTestBot', '-OldWestTestDelay=0.45',
                    f'-OldWestLifecycleControl={folder}/{name}.control.json',
                    f'-OldWestLifecycleReport={folder}/{name}.json']
        # A packaged Game target is a listen host, not the Editor's -server
        # mode. Exercise its actual local player and one remote game process.
        server_name = 'a' if args.package_dir else 'server'
        if args.package_dir:
            launch('a', player_parameters('a', map_url+'?listen') +
                   ['-MULTIHOME=127.0.0.1', f'-port={args.port}', f'-OldWestTestSeed={args.seed}'], render=True)
        else:
            launch('server', [map_url, '-server', '-MULTIHOME=127.0.0.1',
                              f'-port={args.port}', f'-OldWestTestSeed={args.seed}'])
        server_log = folder/f'{server_name}.log'
        wait('server listens', lambda: server_log.exists() and
             args.port in game_net_driver_ports(server_log.read_text(errors='replace')), 90)
        wait('native diagnostic server honors requested seed', lambda:
             f'OldWest visual test seed: {args.seed}' in server_log.read_text(errors='replace'), 15)
        for name in ('a', 'b'):
            if name not in processes:
                launch(name, player_parameters(name, f'127.0.0.1:{args.port}'), render=name == 'a')
            # Seat assignment must be repeatable as well as the shuffle.
            wait(f'{name} authenticates before the next client starts', lambda: read(name).get('snapshot', {}).get('seat') == (0 if name == 'a' else 1))
        wait('both clients connect', lambda: all(read(n).get('snapshot', {}).get('connected') == 2 for n in ('a', 'b')))
        assert renderer_evidence()['frame_cap_log_confirmed'], 'Native client did not confirm the requested frame cap'
        if args.require_shader_platform:
            assert renderer_evidence()['shader_platform'] == args.require_shader_platform, 'Rendered shader platform differs from the required comparison platform'
        expected_projection_alpha = args.projection_velocity_alpha if args.projection_velocity_alpha is not None else 0.0
        assert renderer_evidence()['projection_velocity_alpha_actual'] == expected_projection_alpha, \
            'Native projection velocity feedback differs from the required production/diagnostic setting'
        if trial_cvars:
            assert renderer_evidence()['physics_trial_zero_log_confirmed'], 'Native client did not confirm the requested physics CVar value'
        if args.audio:
            command('a', 'start_audio_capture'); audio_started = True
        capture('01-tactical-overview', read('a'))
        if not args.controlled_actions:
            command('a', 'resume'); command('b', 'resume')
        last_progress, last_rematch = time.monotonic(), None
        paused_for_fall = False
        required = {'damage_before', 'damage_after', 'destroy_coalesced', 'camp_destroy_after',
                    'person_ragdoll_settled', 'completed_person_fall', 'restore_after', 'group_impact'}
        while time.monotonic() < deadline:
            check_alive()
            state = read('a'); snapshot = state.get('snapshot', {}); view = snapshot.get('view', {})
            cinematic = state.get('cinematic', {})
            for completion in cinematic.get('completion_history', []):
                key = (completion.get('match_id'), completion.get('sequence'))
                if key in completed_keys or not completion.get('waited_for_settling'): continue
                completed_keys.add(key)
                # Explicit user/choice skips are separate from natural completion.
                if completion.get('reason') == 'skipped': continue
                completed_falls.append(completion)
                assert completion.get('reason') == 'settled', 'Person death reached its timeout before settling'
                assert completion.get('all_ragdolls_settled') and completion.get('stable_seconds', 0) >= .25, \
                    'Person death completed without a sustained stable fall'
                assert 1.95 <= completion.get('elapsed', 0) <= args.completion_deadline, 'Death shot exceeded its bounded presentation time'
                fallen = [t for t in completion.get('targets', []) if t.get('ragdoll')]
                assert fallen, 'Settled completion recorded no actual ragdoll'
                for member in fallen:
                    physics = member['physics']
                    assert physics['ground_found'] and -5 <= physics['pelvis_ground_clearance_cm'] <= 65, \
                        'Completed ragdoll did not reach the ground'
                    assert physics['max_speed_cm_s'] <= 20 and physics['max_angular_speed_deg_s'] <= 45, \
                        'Completed ragdoll exceeds unchanged settling velocity limits'
                    assert len(physics['bodies']) == 16, 'Completed ragdoll lost a physics body'
                    pose = physics.get('pose_motion', {})
                    assert pose.get('valid') and pose.get('body_count') == 16, \
                        'Completed ragdoll has no complete pair of actual per-frame poses'
                    assert pose['sample_frame'] == pose['query_frame'] and pose['previous_frame'] + 1 == pose['sample_frame'], \
                        'Completed ragdoll used stale or nonconsecutive pose samples'
                    delta = pose['delta_seconds']
                    assert math.isfinite(delta) and delta > 0, 'Pose sampling has invalid elapsed physics time'
                    samples = pose.get('bodies', [])
                    assert len(samples) == 16 and len({b['bone'] for b in samples}) == 16 and \
                        {b['bone'] for b in samples} == {b['bone'] for b in physics['bodies']}, \
                        'Pose guard omitted or duplicated a live rigid body'
                    reconstructed_linear, reconstructed_angular = [], []
                    for sample in samples:
                        previous, current = sample['previous_com_cm'], sample['current_com_cm']
                        qa, qb = sample['previous_rotation_xyzw'], sample['current_rotation_xyzw']
                        assert len(previous) == len(current) == 3 and len(qa) == len(qb) == 4 and \
                            all(math.isfinite(x) for x in [*previous, *current, *qa, *qb]), 'Invalid cached physical pose'
                        norm_a, norm_b = math.sqrt(sum(x*x for x in qa)), math.sqrt(sum(x*x for x in qb))
                        assert norm_a > 0 and norm_b > 0, 'Zero pose quaternion'
                        linear = math.dist(previous, current) / delta
                        dot = abs(sum(x*y for x,y in zip(qa,qb)) / (norm_a*norm_b))
                        angular = math.degrees(2*math.acos(min(1., max(0., dot)))) / delta
                        assert math.isclose(linear, sample['speed_cm_s'], rel_tol=1e-4, abs_tol=.02) and \
                            math.isclose(angular, sample['angular_speed_deg_s'], rel_tol=1e-4, abs_tol=.02), \
                            'Native pose-motion metric differs from independent transform reconstruction'
                        assert linear <= 20.02 and angular <= 45.02, 'Actual pose still moves despite low reported physics velocity'
                        reconstructed_linear.append(linear); reconstructed_angular.append(angular)
                    assert pose['max_speed_cm_s'] <= 20 and pose['max_angular_speed_deg_s'] <= 45, \
                        'Completed ragdoll exceeds the actual pose-motion limits'
                    assert math.isclose(max(reconstructed_linear), pose['max_speed_cm_s'], rel_tol=1e-4, abs_tol=.02) and \
                        math.isclose(max(reconstructed_angular), pose['max_angular_speed_deg_s'], rel_tol=1e-4, abs_tol=.02), \
                        'Pose-motion maxima omit an actual body'
                observed.add('completed_person_fall')
                (folder/'completed-falls.json').write_text(json.dumps(completed_falls, indent=2)+'\n')
            if cinematic.get('busy'):
                timing = cinematic.get('frame_timing', {})
                if cinematic.get('elapsed', 0) > .2:
                    minimum_physics_time_ratio = min(minimum_physics_time_ratio,
                        timing.get('estimated_physics_seconds', 0) / cinematic['elapsed'])
                if args.physics_substeps:
                    assert timing.get('substepping') and timing.get('maximum_substeps') == 8 and abs(timing.get('maximum_substep_delta_seconds', 0) - 1/120) < .000001, 'Native client did not apply the diagnostic physics settings'
                kind = cinematic.get('kind'); resolved = cinematic.get('impact_resolved', False)
                key = (snapshot.get('match_id'), cinematic.get('sequence'), resolved, cinematic.get('ragdoll', False),
                       int(cinematic.get('elapsed', 0)*4) if cinematic.get('ragdoll') else None)
                if key not in seen:
                    seen.add(key); frames.append(dict(match_id=snapshot.get('match_id'), cinematic=cinematic))
                if args.diagnostic_fall_limit is not None and cinematic.get('settle_hold', {}).get('required'):
                    assert abs(cinematic['settle_hold']['maximum_seconds'] - args.diagnostic_fall_limit) < .001, \
                        'Diagnostic fall ceiling was not applied to the actual presentation'
                    if cinematic.get('elapsed', 0) >= 3.85:
                        label = f'fall-{cinematic.get("sequence")}-near-four-seconds'
                        if label not in captured:
                            captured.add(label)
                            capture(label, state, match_cinematic=True)
                if cinematic.get('known_target') and cinematic.get('target_actor_visible'):
                    assert 'displayed_damage' in cinematic, 'Visible target has no displayed-condition telemetry'
                if cinematic.get('target_actor_visible') is False:
                    assert 'displayed_damage' not in cinematic, 'Hidden actor was reported as a displayed target'
                if 'displayed_damage' in cinematic:
                    expected = cinematic['after_damage'] if resolved else cinematic['before_damage']
                    assert cinematic['displayed_damage'] == expected, 'Displayed condition changed outside its impact phase'
                drift = cinematic.get('root_drift_cm', 0.)
                max_root_drift = max(max_root_drift, drift)
                assert drift < 3., f'Animated root drifted {drift:.2f} cm'
                assert not cinematic.get('camera_obstructed', False), \
                    'Camera is inside or behind scenery: ' + cinematic.get('camera_obstruction_detail', 'detail unavailable')
                if args.capture_crowded_entrance and kind == 'enter' and cinematic.get('elapsed', 0) >= .7 \
                        and 'crowded-entrance' not in captured and cinematic.get('target_location'):
                    nearby = [unit for unit in cinematic.get('units', [])
                              if unit.get('id') != cinematic.get('target') and not unit.get('hidden')
                              and not unit.get('camp') and not unit.get('event_token') and not unit.get('dead')
                              and math.dist(unit['location'][:2], cinematic['target_location'][:2]) < 450]
                    if nearby and capture('crowded-entrance', state, match_cinematic=True):
                        captured.add('crowded-entrance')
                if 'forced_lod' in cinematic and not args.physics_only:
                    assert cinematic['forced_lod'] == 1, 'Cinematic survivor is not requesting full LOD0'
                    if cinematic.get('elapsed', 0) >= .2:
                        assert cinematic['predicted_lod'] == 0, 'Cinematic survivor still displays a reduced LOD'
                        observed.add('cinematic_lod0')
                simultaneous = cinematic.get('simultaneous_targets', [])
                for member in [cinematic, *simultaneous]:
                    if not member.get('ragdoll'): continue
                    physics = member.get('physics', {})
                    assert physics.get('thigh_collision_enabled') is True, 'Ragdoll thighs can pass through each other'
                    assert physics.get('forearm_chest_collision_enabled') == {'LeftForeArm': True, 'RightForeArm': True}, \
                        'Ragdoll forearms can pass through the chest'
                    responses = physics.get('collision_responses', {})
                    bodies = physics.get('bodies', [])
                    assert responses.get('physics_body_blocked') and responses.get('world_static_blocked') and \
                        len(bodies) == 16 and all(b.get('physics_body_blocked') and b.get('world_static_blocked')
                                                 for b in bodies), \
                        'Ragdoll collision filters disable body self-contact or ground contact'
                    if args.record_contacts:
                        contact = physics.get('contact_recording', {})
                        assert contact.get('enabled') and contact.get('fall_id', 0) > 0 and \
                            all(b.get('collision_notifications_enabled') for b in bodies), \
                            'Requested native ragdoll contact recording is not enabled on every body'
                if args.require_rig_iterations:
                    for member in [cinematic, *simultaneous]:
                        if not member.get('ragdoll'): continue
                        bodies = member.get('physics', {}).get('bodies', [])
                        assert len(bodies) == 16 and all(b.get('iteration_overrides_enabled') and
                            (b.get('position_solver_iterations'), b.get('velocity_solver_iterations'),
                             b.get('projection_solver_iterations')) == (12, 4, 1) for b in bodies), \
                            'Ragdoll live bodies are not using their authored 12/4/1 solver overrides'
                if args.joint_damping is not None:
                    for member in [cinematic, *simultaneous]:
                        if not member.get('ragdoll'): continue
                        joints = member.get('physics', {}).get('joints', [])
                        assert len(joints) == 15 and all(j.get('velocity_drive_enabled') and
                            not j.get('orientation_drive_enabled') and j.get('drive_stiffness') == 0 and
                            math.isclose(j.get('drive_damping', -1), args.joint_damping, rel_tol=1e-5)
                            for j in joints), 'Passive joint damping diagnostic did not reach all live joints'
                for member in [cinematic, *simultaneous]:
                    if not member.get('ragdoll'): continue
                    joints = member.get('physics', {}).get('joints', [])
                    assert len(joints) == 15 and all(j.get('linear_solver_profile') is False for j in joints), \
                        'Production nonlinear joint profile was not applied to all live ragdoll joints'
                    assert all(j.get('mass_conditioning_enabled') is False and j.get('projection_enabled') is False
                               for j in joints), 'Production ragdoll still uses joint-local conditioning or projection'
                if args.natural_joint_mass:
                    for member in [cinematic, *simultaneous]:
                        if not member.get('ragdoll'): continue
                        joints = member.get('physics', {}).get('joints', [])
                        assert len(joints) == 15 and all(j.get('mass_conditioning_enabled') is False for j in joints), \
                            'Natural mass diagnostic was not applied to all live ragdoll joints'
                if args.no_joint_projection:
                    for member in [cinematic, *simultaneous]:
                        if not member.get('ragdoll'): continue
                        joints = member.get('physics', {}).get('joints', [])
                        assert len(joints) == 15 and all(j.get('projection_enabled') is False for j in joints), \
                            'Joint projection diagnostic was not applied to all live ragdoll joints'
                for member in simultaneous:
                    expected = member['after_damage'] if resolved else member['before_damage']
                    assert member.get('displayed_damage') == expected, 'Grouped target disappeared or changed outside the shared impact'
                    if not args.physics_only and 'forced_lod' in member and cinematic.get('elapsed', 0) >= .2:
                        assert member['forced_lod'] == 1 and member['predicted_lod'] == 0, 'Grouped cinematic survivor still displays a reduced LOD'
                    if member.get('ragdoll') and args.early_settle_deadline is not None and cinematic.get('elapsed', 0) >= args.early_settle_deadline:
                        physics = member['physics']
                        assert physics['ground_found'] and -5 <= physics['pelvis_ground_clearance_cm'] <= 65, 'Grouped ragdoll did not settle near the ground'
                        assert physics['max_speed_cm_s'] <= 20 and physics['max_angular_speed_deg_s'] <= 45, 'Grouped ragdoll has not settled'
                if simultaneous and resolved:
                    observed.add('group_impact')
                    if 'group-impact' not in captured:
                        if capture('group-impact', state, match_cinematic=True): captured.add('group-impact')
                if kind == 'damage': observed.add('damage_after' if resolved else 'damage_before')
                if kind == 'destroy':
                    target_card = next((unit.get('card_id') for unit in cinematic.get('units', [])
                                        if unit.get('id') == cinematic.get('target')), None)
                    requested_card = args.capture_fall_card and target_card == args.capture_fall_card
                    card_capture_id = f'{target_card}-{snapshot.get("match_id")}-{cinematic.get("sequence")}'
                    if args.record_contacts and cinematic.get('ragdoll') and cinematic.get('elapsed', 0) >= 3.85:
                        label = f'contact-late-{card_capture_id}'
                        if label not in captured and capture(label, state, match_cinematic=True):
                            captured.add(label)
                    if requested_card and .05 <= cinematic.get('elapsed', 0) < .45:
                        label = f'early-card-{card_capture_id}'
                        if label not in captured and capture(label, state, match_cinematic=True):
                            captured.add(label)
                    if requested_card and cinematic.get('ragdoll') and cinematic.get('elapsed', 0) >= 3.85:
                        label = f'late-card-{card_capture_id}'
                        if label not in captured and capture(label, state, match_cinematic=True):
                            captured.add(label)
                    if args.capture_settled_target == cinematic.get('target') and cinematic.get('ragdoll') \
                            and cinematic.get('elapsed', 0) >= 3.85:
                        label = f'late-target-{args.capture_settled_target}'
                        if label not in captured and capture(label, state, match_cinematic=True):
                            captured.add(label)
                    log = view.get('log', [])
                    for index, event in enumerate(log):
                        if event['sequence'] == cinematic.get('sequence') and index > 0:
                            previous = log[index-1]
                            if previous['type'] == 'damage' and previous['target'] == event['target']:
                                observed.add('destroy_coalesced')
                                assert not any(f['match_id'] == snapshot.get('match_id') and
                                    f['cinematic'].get('sequence') == previous['sequence'] and
                                    f['cinematic'].get('kind') == 'damage' for f in frames), 'Lethal damage played as two hits'
                    if resolved and cinematic.get('camp'):
                        observed.add('camp_destroy_after')
                        if 'camp-collapse' not in captured:
                            if capture('camp-collapse', state, match_cinematic=True): captured.add('camp-collapse')
                    if not args.controlled_actions and not cinematic.get('camp') and 'person-fall' not in captured and not paused_for_fall:
                        # Hold only the local legal bots, so an unrelated next
                        # action/choice cannot skip the fall during inspection.
                        command('a', 'pause'); command('b', 'pause'); paused_for_fall = True
                        continue
                    ready_to_observe = cinematic.get('settle_hold', {}).get('all_settled', False)
                    if args.early_settle_deadline is not None:
                        ready_to_observe = cinematic.get('elapsed', 0) >= args.early_settle_deadline
                    minimum_observation_time = args.early_settle_deadline if args.early_settle_deadline is not None else 1.95
                    if cinematic.get('ragdoll') and cinematic.get('elapsed', 0) >= minimum_observation_time and ready_to_observe:
                        body, origin = cinematic['body_focus'], cinematic['target_location']
                        physics = cinematic['physics']
                        assert physics['ground_found'], 'Ragdoll has no terrain underneath it'
                        assert -5 <= physics['pelvis_ground_clearance_cm'] <= 65, 'Ragdoll pelvis did not settle near the ground'
                        assert physics['max_speed_cm_s'] <= 20, 'Ragdoll bodies have not settled: linear speed exceeds20cm/s'
                        assert physics['max_angular_speed_deg_s'] <= 45, 'Ragdoll bodies have not settled: angular speed exceeds45deg/s'
                        assert math.dist(body[:2], origin[:2]) < 250, 'Ragdoll travelled out of its local action area'
                        if not cinematic.get('group_shot'):
                            error = math.dist(body, cinematic['camera_focus']); max_follow_error = max(max_follow_error, error)
                            assert error < 150, 'Camera did not follow the visible body'
                        observed.add('person_ragdoll_settled')
                        if requested_card:
                            label = f'settled-card-{card_capture_id}'
                            if label not in captured and capture(label, state, match_cinematic=True):
                                captured.add(label)
                        if args.capture_settled_target == cinematic.get('target'):
                            label = f'settled-target-{args.capture_settled_target}'
                            if label not in captured and capture(label, state, match_cinematic=True):
                                captured.add(label)
                        if 'person-fall' not in captured:
                            if capture('person-fall', state, match_cinematic=True):
                                captured.add('person-fall')
                                if args.diagnostic_fall and cinematic.get('diagnostic_fall_hold'):
                                    diagnostic_trajectory_sequence = cinematic['sequence']
                                    samples = capture_fall_followups(cinematic['sequence'])
                                    for sample in samples:
                                        problem = stability_failure(sample['cinematic'])
                                        if problem:
                                            state, cinematic = sample, sample['cinematic']
                                            raise AssertionError(problem)
                                    if not args.controlled_actions:
                                        command('a', 'resume'); command('b', 'resume')
                if kind == 'restore' and resolved:
                    observed.add('restore_after')
                    if 'restoration' not in captured:
                        if capture('restoration', state, match_cinematic=True): captured.add('restoration')
            if paused_for_fall and ('person-fall' in captured or not cinematic.get('busy')):
                command('a', 'resume'); command('b', 'resume'); paused_for_fall = False
            requested_captures_ready = (
                (args.capture_settled_target is None or f'settled-target-{args.capture_settled_target}' in captured)
                and (not args.capture_fall_card or any(
                    label.startswith(f'settled-card-{args.capture_fall_card}-') for label in captured)))
            if required <= observed and {'person-fall', 'restoration', 'camp-collapse', 'group-impact'} <= captured \
                    and requested_captures_ready:
                command('a', 'pause'); command('b', 'pause')
                # Bot pause acknowledgement can precede the last in-flight RPC.
                previous_revisions, stable_since = None, time.monotonic()
                pause_check_started = stable_since
                def revisions_stable():
                    nonlocal previous_revisions, stable_since
                    snapshots = [read(n).get('snapshot', {}) for n in ('a', 'b')]
                    revisions = [s.get('view', {}).get('revision') for s in snapshots]
                    matches = [s.get('match_id') for s in snapshots]
                    valid = all(type(r) is int for r in revisions) and all(matches)
                    revision_stability_samples.append(dict(seconds=time.monotonic()-pause_check_started,
                        revisions=revisions, match_ids=matches, valid=bool(valid)))
                    # An unavailable/incomplete telemetry file is not evidence
                    # that the authoritative revision changed. Require valid
                    # endpoints in the same match; revisions cannot go back.
                    if not valid:
                        return None
                    identity = (tuple(matches), tuple(revisions))
                    if identity != previous_revisions or revisions[0] != revisions[1] or matches[0] != matches[1]:
                        previous_revisions, stable_since = identity, time.monotonic()
                    return revisions if time.monotonic() - stable_since >= .7 else None
                before = wait('paused authoritative revisions settle', revisions_stable, 5)
                command('a', 'skip_cinematics')
                wait('skip clears presentation queue', lambda: not read('a').get('cinematic', {}).get('busy', False))
                assert [read(n)['snapshot']['view']['revision'] for n in ('a', 'b')] == before, 'Presentation skip mutated game state'
                assert all(unit['forced_lod'] == 0 for unit in read('a').get('cinematic', {}).get('survivor_lods', [])), 'Skip did not restore automatic survivor LOD selection'
                capture('02-overview-after-skip', read('a'))
                break
            if view.get('status') in ('won', 'draw') and not cinematic.get('busy') and last_rematch != snapshot.get('match_id'):
                last_rematch = snapshot.get('match_id')
                command('a', 'rematch'); command('b', 'rematch')
            if args.controlled_actions and not cinematic.get('busy') and time.monotonic() >= next_action_at:
                states = {name: read(name).get('snapshot', {}) for name in ('a', 'b')}
                revisions = [states[name].get('view', {}).get('revision') for name in ('a', 'b')]
                if revisions[0] == revisions[1] and states['a'].get('match_id') == states['b'].get('match_id'):
                    for name in ('a', 'b'):
                        current = states[name]; choices = current.get('actions', [])
                        if not choices: continue
                        weights = [5 if a.get('category') == 'ability' else 3 if a.get('category') == 'turn' else 1 for a in choices]
                        selected = action_random[name].choices(choices, weights=weights, k=1)[0]
                        revision = current['view']['revision']; match_id = current['match_id']
                        action_trace.append(dict(client=name, revision=revision, command=selected['command']))
                        (folder/'controlled-actions.json').write_text(json.dumps(action_trace, indent=2)+'\n')
                        command(name, 'submit', command=selected['command'], revision=revision, match_id=match_id)
                        wait('controlled legal action reaches both clients', lambda: all(
                            read(n).get('snapshot', {}).get('view', {}).get('revision', -1) > revision for n in ('a', 'b')), 8)
                        next_action_at = time.monotonic() + .2
                        break
            if time.monotonic()-last_progress >= 25:
                print(f'Observed {sorted(observed)}; still need {sorted(required-observed)}', flush=True)
                last_progress = time.monotonic()
            time.sleep(.025)
        else:
            raise AssertionError(f'Incomplete gameplay coverage: missing observations={sorted(required-observed)}, '
                                 f'requested settled target={args.capture_settled_target}, '
                                 f'requested fall card={args.capture_fall_card}; see retained captures')
        if args.capture_settled_target is not None:
            assert f'settled-target-{args.capture_settled_target}' in captured, 'Requested settled target was not captured'
        if args.capture_fall_card:
            assert any(label.startswith(f'settled-card-{args.capture_fall_card}-') for label in captured), \
                'Requested public character was not captured settled'
        if args.audio:
            command('a', 'stop_audio_capture', name='native-cinematic-mix', directory=str(folder))
            audio_started = False
            wait('Unreal submix WAV exported', lambda: (folder/'native-cinematic-mix.wav').is_file() and (folder/'native-cinematic-mix.wav').stat().st_size > 1000, 15)
        runtime_assets = assert_runtime_assets([folder/f'{name}.log' for name in processes])
        if args.profile_renderer:
            assert 'a' in performance_enabled_peers and any(key[0] == 'a' for key in performance_keys), \
                'Requested renderer/report performance telemetry was not observed'
        if args.record_contacts:
            assert (folder/'ragdoll-contacts.jsonl').is_file() and (folder/'ragdoll-contacts.jsonl').stat().st_size > 0, \
                'Requested native collision recording contains no events'
        if args.solver_velocity_iterations is not None:
            assert renderer_evidence()['solver_velocity_override_log_confirmed'], 'Solver velocity diagnostic override was not confirmed in the native log'
        rendered_log = (folder/'a.log').read_text(errors='replace')
        assert not re.search(r'missing usage|default.?material', rendered_log, re.I), 'Skeletal material fallback in rendered log'
        assert not re.search(r'LogPhysics[^\n]*Warning', rendered_log, re.I), 'Physics warning in rendered log'
        if args.audio:
            assert 'Initializing Sound Submixes' in rendered_log, 'Audio mixer did not initialize'
            assert not re.search(r'failed[^\n]*audio|audio[^\n]*error', rendered_log, re.I), 'Audio initialization error'
        result = dict(ok=True, ruleset=args.ruleset, observations=sorted(observed), physics_only=args.physics_only,
                      record_contacts=args.record_contacts,
                      contact_report=str(folder/'ragdoll-contacts.jsonl') if args.record_contacts else None,
                      profile_renderer=args.profile_renderer, performance_enabled_peers=sorted(performance_enabled_peers),
                      lifecycle_performance_report_count=len(performance_keys),
                      rig_iterations_required=args.require_rig_iterations,
                      completed_falls=completed_falls, revision_stability_samples=revision_stability_samples,
                      requested_settled_target_capture=args.capture_settled_target,
                      legacy_early_settle_deadline=args.early_settle_deadline,
                      settling_contract='Death completes after sustained stability (20cm/s,45deg/s,grounded for0.25s);1.95s minimum,6s maximum',
                      completion_deadline_seconds=args.completion_deadline,
                      diagnostic_fall_hold=args.diagnostic_fall,
                      nanite_disabled=args.disable_nanite,
                      server_test_seed=args.seed, diagnostic_physics_substeps=args.physics_substeps,
                      build=build, minimum_estimated_physics_to_shot_time_ratio=minimum_physics_time_ratio,
                      controlled_actions=args.controlled_actions,
                      physics_trial=args.physics_trial,
                      solver_velocity_iterations_override=args.solver_velocity_iterations,
                      projection_velocity_alpha_override=args.projection_velocity_alpha,
                      passive_joint_damping=args.joint_damping,
                      nonlinear_joints=args.nonlinear_joints,
                      natural_joint_mass=args.natural_joint_mass,
                      no_joint_projection=args.no_joint_projection,
                      diagnostic_fall_limit=args.diagnostic_fall_limit,
                      extended_fall_observation_only=args.diagnostic_fall_limit is not None,
                      renderer=renderer_evidence(),
                      comparison=comparison_evidence(),
                      runtime_assets=runtime_assets, physics_warnings=0, audio_mixer_initialized=args.audio,
                      audio_capture=str(folder/'native-cinematic-mix.wav') if args.audio else None,
                      max_root_drift_cm=max_root_drift, max_single_shot_follow_error_cm=max_follow_error,
                      screenshots=captures, logs=str(folder), elapsed_seconds=round(time.monotonic()-started, 2),
                      limitations=(['NullRHI physics/state diagnostic; no rendering, visual LOD or audio acceptance.',
                                    'Compare the actual initial body pose before interpreting against a rendered run.']
                                   if args.physics_only else
                                   ['Actual PNGs still require visual review', 'Audio quality not automatically assessed',
                                    'Local loopback clients; rendering on one client only']))
        (folder/'observations.json').write_text(json.dumps(frames, indent=2)+'\n')
        (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        report_path.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2), flush=True)
    except BaseException as error:
        failure = str(error)
        category = ('camera_obstruction' if 'Camera' in failure else
                    'cinematic_lod' if 'LOD' in failure else
                    'ragdoll_stability' if 'Ragdoll' in failure or 'settled' in failure or 'Person death' in failure else
                    'native_runtime' if 'runtime' in failure.lower() else 'cinematic_validation')
        result = dict(ok=False, ruleset=args.ruleset, physics_only=args.physics_only,
                      record_contacts=args.record_contacts,
                      contact_report=str(folder/'ragdoll-contacts.jsonl') if args.record_contacts else None,
                      profile_renderer=args.profile_renderer, performance_enabled_peers=sorted(performance_enabled_peers),
                      lifecycle_performance_report_count=len(performance_keys),
                      rig_iterations_required=args.require_rig_iterations,
                      completed_falls=completed_falls, revision_stability_samples=revision_stability_samples,
                      requested_settled_target_capture=args.capture_settled_target,
                      legacy_early_settle_deadline=args.early_settle_deadline,
                      settling_contract='Death completes after sustained stability (20cm/s,45deg/s,grounded for0.25s);1.95s minimum,6s maximum',
                      completion_deadline_seconds=args.completion_deadline,
                      validation_scope='physics/state only; no rendered evidence' if args.physics_only else 'rendered cinematic',
                      failure_category=category, failure_type=type(error).__name__,
                      failure=failure, failure_frame=locals().get('cinematic', {}), logs=str(folder), screenshots=captures,
                      diagnostic_fall_hold=args.diagnostic_fall,
                      nanite_disabled=args.disable_nanite,
                      server_test_seed=args.seed, diagnostic_physics_substeps=args.physics_substeps,
                      build=build, minimum_estimated_physics_to_shot_time_ratio=minimum_physics_time_ratio,
                      controlled_actions=args.controlled_actions,
                      physics_trial=args.physics_trial,
                      solver_velocity_iterations_override=args.solver_velocity_iterations,
                      projection_velocity_alpha_override=args.projection_velocity_alpha,
                      passive_joint_damping=args.joint_damping,
                      nonlinear_joints=args.nonlinear_joints,
                      natural_joint_mass=args.natural_joint_mass,
                      no_joint_projection=args.no_joint_projection,
                      diagnostic_fall_limit=args.diagnostic_fall_limit,
                      extended_fall_observation_only=args.diagnostic_fall_limit is not None,
                      renderer=renderer_evidence(),
                      observations=sorted(observed), failure_elapsed_seconds=round(time.monotonic()-started, 2))
        # Keep the original assertion and collect actual rendered evidence while
        # its actors still exist. Diagnostic duration is local, explicitly
        # non-shipping, and never changes the authoritative action or thresholds.
        if diagnostic_trajectory_sequence is not None and diagnostic_trajectory_sequence == result['failure_frame'].get('sequence'):
            result['failure_motion'] = str(folder/'failure-motion.json')
        elif category in ('camera_obstruction', 'ragdoll_stability', 'cinematic_lod') and processes.get('a') and processes['a'].poll() is None:
            deadline = max(deadline, time.monotonic() + 15)
            diagnostic_frames = []
            try:
                failed_state = locals().get('state', read('a'))
                expected_sequence = result['failure_frame'].get('sequence')
                if not capture('failure-frame', failed_state, match_cinematic=True):
                    result['failure_capture_error'] = 'The failed beat ended before the screenshot completed'
                if args.diagnostic_fall and result['failure_frame'].get('diagnostic_fall_hold'):
                    diagnostic_frames = [sample['cinematic'] for sample in capture_fall_followups(expected_sequence)]
                (folder/'failure-motion.json').write_text(json.dumps(diagnostic_frames, indent=2)+'\n')
                result['failure_motion'] = str(folder/'failure-motion.json')
            except Exception as capture_error:
                result['failure_capture_error'] = str(capture_error)
        if audio_started and processes.get('a') and processes['a'].poll() is None:
            deadline = max(deadline, time.monotonic() + 12)
            try:
                command('a', 'stop_audio_capture', name='native-cinematic-mix', directory=str(folder))
                wait('failed-run Unreal submix WAV export', lambda: (folder/'native-cinematic-mix.wav').is_file(), 10)
                result['audio_capture'] = str(folder/'native-cinematic-mix.wav')
            except Exception as export_error:
                result['audio_export_error'] = str(export_error)
        result['elapsed_seconds'] = round(time.monotonic()-started, 2)
        try:
            result['comparison'] = comparison_evidence()
        except Exception as comparison_error:
            result['comparison'] = dict(ok=False, error=str(comparison_error))
        (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        report_path.write_text(json.dumps(result, indent=2)+'\n')
        raise
    finally:
        (folder/'observations.json').write_text(json.dumps(frames, indent=2)+'\n')
        try:
            stop_owned_process_groups(processes.values(), streams)
        except Exception as cleanup_error:
            result = locals().get('result', dict(ok=False, logs=str(folder)))
            result.update(ok=False, cleanup_error=str(cleanup_error))
            result.setdefault('failure_category', 'process_cleanup')
            (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
            report_path.write_text(json.dumps(result, indent=2)+'\n')
            raise


if __name__ == '__main__':
    main()
