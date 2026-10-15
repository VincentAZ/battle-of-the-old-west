#!/usr/bin/env python3
"""Render every public catalog card through the production 3D portrait widget.

The nonshipping, VisualTest-gated gallery changes local presentation only. This
suite verifies real capture counts, changing component/pose state, visible pixels,
clipping and reclamation; it never injects cards into an authoritative match.
"""
import argparse
import hashlib
import json
import sys
import math
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from native_launch import create_native_run_directory, resolve_native_launch, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'
# October 9 completion imports: all have setting bases and separate authored ruins.
COMPLETION_HOLDINGS = {'timber_ram': 'TimberRam', 'packer_s_cabin': 'PackersCabin', 'revival_tent': 'RevivalTent', 'vigilance_committee': 'VigilanceCommittee', 'wagon_fort': 'WagonFort', 'coal_yard': 'CoalYard', 'pawn_shop': 'PawnShop', 'nitro_works': 'NitroWorks', 'crimp_house': 'CrimpHouse', 'boot_hill': 'BootHill', 'boarding_house': 'BoardingHouse', 'rustlers_corral': 'RustlersCorral', 'quaker_settlement': 'QuakerSettlement', 'horse_trader': 'HorseTrader', 'dance_hall': 'DanceHall', 'apothecary': 'Apothecary', 'cattlemen_s_club': 'CattlemensClub'}


TROUBLE_MESHES = {
    'hard_winter': ('Landscapes', 'HardWinter'), 'box_canyon': ('Landscapes', 'BoxCanyon'),
    'prairie_fire': ('Landscapes', 'PrairieFire'), 'cholera': ('Objects', 'Quarantine'),
    'poker_night': ('Objects', 'PokerNight'), 'cannonade': ('Schemes', 'Cannonade'),
    'ambush': ('Schemes', 'Ambush'), 'gold_rush': ('Schemes', 'GoldRush'),
    'run_out_of_town': ('Schemes', 'DynamiteCrate'), 'curfew': ('Schemes', 'Curfew'),
}

def portraits_ready(state, ids, minimum_captures=None, minimum_revisions=None):
    """Fail closed on missing telemetry, pending finalization or stale captures."""
    compilation = state.get('compilation', {})
    if not (compilation.get('telemetry_version') == 1
            and compilation.get('available') is True
            and compilation.get('mode') in ('editor_compilers', 'cooked_runtime')
            and compilation.get('required_post_zero_captures') == 2
            and compilation.get('shader_jobs') == 0
            and compilation.get('asset_jobs') == 0
            and compilation.get('shader_active') is False
            and compilation.get('ready') is True):
        return False
    scenes = {scene['card_id']: scene for scene in state.get('scenes', [])}
    for card_id in ids:
        scene = scenes.get(card_id, {})
        zero_capture = scene.get('compilation_zero_capture', -1)
        zero_frame = scene.get('compilation_zero_frame', -1)
        last_ready_frame = scene.get('last_ready_capture_frame', -1)
        if not (scene.get('capture_ready') is True
                and scene.get('post_zero_captures', 0) >= 2
                and zero_capture >= 0 and zero_frame >= 0
                and scene.get('captures', 0) >= zero_capture+3
                and zero_frame < last_ready_frame <= compilation.get('frame', -1)
                and scene.get('captures', 0) >= (minimum_captures or {}).get(card_id, 0)
                and scene.get('condition_revision', -1) >= (minimum_revisions or {}).get(card_id, 0)):
            return False
        render = scene.get('render_readiness')
        if render is not None and not (render.get('display_ready') is True
                and render.get('expected_meshes', 0) > 0
                and all(render.get(key) == 0 for key in ('pending_psos', 'missing_registrations',
                    'missing_render_states', 'dirty_render_states', 'missing_proxies'))
                and render.get('complete_submissions', 0) >= 2
                and render.get('ordered_capture_fence_complete') is True):
            return False
        if scene.get('fire_sheets', 0) > 0:
            textures = scene.get('fire_textures', [])
            if not textures or any(not (texture.get('max_mips', 0) > 0
                    and texture.get('resident_mips', 0) >= texture['max_mips']
                    and texture.get('requested_mips', 0) >= texture['max_mips']) for texture in textures):
                return False
    return bool(ids)


def signature(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return dict(path=str(path.resolve()), sha256=digest.hexdigest(), bytes=path.stat().st_size,
                modified_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())


def person_motion_resumed(before, after):
    """Check skeletal movement; the scene motion hash covers static props."""
    earlier, later = before.get('people', []), after.get('people', [])
    if not earlier or len(earlier) != len(later):
        return False
    for a, b in zip(earlier, later):
        poses_a, poses_b = a.get('pose_samples', []), b.get('pose_samples', [])
        if not poses_a or len(poses_a) != len(poses_b):
            return False
        if not (b.get('playing') and b.get('looping')
                and abs(a['animation_position'] - b['animation_position']) > .001
                and max((abs(x-y) for p,q in zip(poses_a, poses_b) for x,y in zip(p,q)), default=0.) > .001):
            return False
    return True


def validate_camp_composition(scene):
    """Check explicitly named solid/flame geometry, retaining full smoke overflow."""
    c = scene['camp_composition']
    assert c['semantics'] == 'solid_bounds_and_full_flame_sheets_v1'
    assert c['smoke_policy'] == 'rendered_soft_overflow'
    solids, flames = c['solid_points'], c['flame_points']
    assert solids and len(solids) % 8 == 0 and len(flames) % 4 == 0
    # Ground is intentionally separate from camp_visible_parts. The tent's
    # low collapsed ruin now opts into framing its complete setting base.
    base_assets = {'army_surgeon_s_tent': 'ArmySurgeonsTent', 'rockslide_ridge': 'RockslideRidge', 'lookout_ridge': 'LookoutRidge', 'courthouse': 'Courthouse', 'free_homestead': 'FreeHomestead', 'chuckwagon': 'Chuckwagon', 'pony_express_station': 'PonyExpressStation', 'gallows': 'Gallows', 'robbers_roost': 'RobbersRoost', 'smuggler_s_landing': 'SmugglersLanding', 'bounty_office': 'BountyOffice'}
    base_assets.update(COMPLETION_HOLDINGS)
    framed_base = [m for m in scene.get('camp_visible_meshes', [])
                   if '/SM_HoldingBase_' in m['mesh']]
    if scene['card_id'] in base_assets:
        asset = base_assets[scene['card_id']]
        assert len(framed_base) == 1 and f'/SM_HoldingBase_{asset}.' in framed_base[0]['mesh'], \
            'Portrait lost its reviewed setting base'
    else:
        # Telemetry lists visible ground even when the composition contract
        # intentionally frames only the structure (e.g. Gunsmith/Jailhouse).
        framed_base = []
    framed_water = [m for m in scene.get('camp_visible_meshes', []) if '/SM_HoldingWater_' in m['mesh']]
    if scene['card_id'] == 'smuggler_s_landing':
        assert len(framed_water) == 1 and '/SM_HoldingWater_SmugglersLanding.' in framed_water[0]['mesh'], 'Portrait lost its river surface'
    assert len(solids)//8 == scene['camp_visible_parts'] - scene['fire_sheets'] + len(framed_base) + len(framed_water), \
        'A visible solid or opted-in setting base was omitted from composition'
    assert len(flames)//4 + c['excluded_smoke_sheets'] == scene['fire_sheets']
    assert c['excluded_smoke_sheets'] >= 0
    assert all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in solids+flames)
    basis = [c['camera_forward'], c['camera_right'], c['camera_up']]
    dot = lambda a,b: sum(x*y for x,y in zip(a,b))
    assert all(math.isclose(dot(axis,axis),1.,abs_tol=1e-5) for axis in basis)
    assert all(abs(dot(basis[a],basis[b]))<1e-5 for a,b in ((0,1),(0,2),(1,2)))
    tan_h = math.tan(math.radians(c['horizontal_fov_degrees']*.5))
    assert tan_h>0 and math.isclose(c['aspect_ratio'],1.5,abs_tol=1e-6)
    points, depths = [], []
    for point in solids+flames:
        relative = [a-b for a,b in zip(point,c['camera_location'])]
        depth = dot(relative,basis[0]); assert depth>0, 'Composition subject is behind the camera'
        depths.append(depth)
        points.append([dot(relative,basis[1])/(depth*tan_h),dot(relative,basis[2])/(depth*tan_h/1.5)])
    lo,hi = [min(p[i] for p in points) for i in (0,1)],[max(p[i] for p in points) for i in (0,1)]
    assert min(lo)>=-1. and max(hi)<=1., f'Solid/flame geometry clips outside portrait: {lo}, {hi}'
    assert all(math.isclose(a,b,abs_tol=1e-5) for a,b in zip(lo+hi,c['coverage']['min']+c['coverage']['max']))
    assert math.isclose(min(depths),c['minimum_depth_cm'],abs_tol=1e-4)
    assert not c['fit_fallback'], 'View-specific composition fit fell back; candidate remains unverified'
    if flames:
        assert c['fit_active'] and 1<=c['fit_iterations']<=8
    full = scene['camp_frame_coverage']
    assert full and all(math.isfinite(v) for v in full['min']+full['max'])
    overflow = min(full['min']) < -1. or max(full['max']) > 1.
    assert overflow == c['full_culling_envelope_overflows']
    # The full renderer envelope can overflow even without smoke because its
    # all-view flame box is wider than this actual camera's full flame sheets.
    # Keep that exact fact in scene evidence rather than relabeling it clipped
    # solid geometry or claiming the entire smoke envelope fits.
    return dict(coverage=dict(min=lo,max=hi),full_culling_envelope_overflows=overflow,
                excluded_smoke_sheets=c['excluded_smoke_sheets'])


def run(args):
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-card-portraits-')
    output.mkdir(parents=True, exist_ok=True)
    runtime = resolve_native_launch(args.editor, ROOT/'game/OldWest/OldWest.uproject', args.package_dir,
                                    run_directory=output, editor_directory=ROOT)
    if runtime.package_root:
        binaries = runtime.package_root/'OldWest/Binaries/Linux'
        binary = next((path for path in (binaries/'OldWestGame', binaries/'OldWestGame-Linux-Development') if path.is_file()), None)
        if binary is None:
            raise FileNotFoundError(f'No packaged OldWestGame executable under {binaries}')
        build = dict(mode='packaged_game', executable=signature(binary),
                     manifest=signature(runtime.package_root/'package-manifest.json'))
    else:
        binary = ROOT/'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'
        sources = sorted((ROOT/'game/OldWest/Source/OldWestGame').rglob('*'))
        assets = sorted((ROOT/'game/OldWest/Content/Art/CardPortraits').glob('*.uasset'))
        build = dict(mode='editor_game', module=signature(binary),
                     sources=[signature(path) for path in sources if path.is_file()],
                     portrait_assets=[signature(path) for path in assets],
                     identity_assets=[signature(path) for path in sorted((ROOT/'game/OldWest/Content/Art/Survivors/Identities').rglob('*.uasset'))],
                     variant_assets=[signature(path) for path in sorted((ROOT/'game/OldWest/Content/Art/Survivors/Variants').rglob('*.uasset'))],
                     survivor_assets=[signature(path) for path in sorted((ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA').rglob('*.uasset'))],
                     repair_bot_assets=[signature(path) for path in sorted((ROOT/'game/OldWest/Content/Art/Survivors/RepairBot').rglob('*.uasset'))],
                     catalog=signature(ROOT/'game/OldWest/Content/Data/cards.json'))
    build['harness'] = signature(Path(__file__))
    (output/'build.json').write_text(json.dumps(build,indent=2)+'\n')
    report_path, control = output/'player.json', output/'player.control.json'
    catalog = json.loads((ROOT/'game/OldWest/Content/Data/cards.json').read_text())['cards']
    if args.card_types:
        catalog = [c for c in catalog if c['type'] in args.card_types]
    if args.cards:
        wanted = set(args.cards)
        catalog = [c for c in catalog if c['id'] in wanted]
        assert {c['id'] for c in catalog} == wanted, 'Unknown card ID requested'
    # First groups exercise distinct effects and body poses for prompt visual QA.
    order = {'stampede': 0, 'prairie_fire': 1, 'hip_flask': 2, 'prospector': 3,
             'annie_oakley': 4, 'hellfire_preacher': 5, 'cholera': 6, 'ambush': 7,
             'run_out_of_town': 8, 'curfew': 9, 'hard_winter': 10, 'box_canyon': 11}
    catalog.sort(key=lambda c: (order.get(c['id'], 100), c['type'], c['id']))
    width, height = map(int, args.resolution.split('x'))
    # Base camps render a single static Western holding mesh by design: no
    # machinery loop exists to observe, so motion checks apply to other camps.
    sys.path.insert(0, str(ROOT/'scripts'))
    from holdings_roster import HOLDINGS
    holding_ids = set(HOLDINGS) | set(COMPLETION_HOLDINGS)
    # Reviewed expansion structures are static, like the base holdings.
    holding_ids.update({'wanted_poster_board', 'gunsmith', 'jailhouse', 'post_office', 'army_surgeon_s_tent', 'rockslide_ridge', 'lookout_ridge', 'courthouse', 'free_homestead', 'chuckwagon', 'pony_express_station', 'gallows', 'robbers_roost', 'smuggler_s_landing', 'bounty_office'})
    stream = (output/'player-console.log').open('w')
    process = None
    sequence, latest = 0, {}
    result = dict(ok=False, full_catalog=not args.cards and not args.card_types, card_types=args.card_types,
                  card_count=len(catalog), cards=[],
                  camp_conditions=[], conditions_checked=not args.skip_conditions, resolution=args.resolution, package_dir=str(args.package_dir) if args.package_dir else None,
                  output=str(output), limitations=['Captured local catalog gallery; human visual review is still required.'])
    result['face_reviews'] = []
    result['build'] = build
    result['shader_readiness'] = []
    readiness_stream = (output/'render-readiness.jsonl').open('w')
    readiness_frames = set()
    readiness_summary = dict(observed=False, samples=0, placeholder_samples=0,
                             peak_pending_psos=0, peak_missing_proxies=0)

    def read():
        nonlocal latest
        try:
            latest = json.loads(report_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
        state = latest.get('hud', {}).get('portraits', {})
        frame = state.get('compilation', {}).get('frame')
        scenes = [{key: scene.get(key) for key in ('card_id', 'captures', 'condition_revision',
                    'visible_frames_ago', 'render_readiness')}
                  for scene in state.get('scenes', []) if scene.get('render_readiness') is not None]
        if scenes and frame not in readiness_frames:
            readiness_frames.add(frame)
            readiness_stream.write(json.dumps(dict(query_frame=frame, scenes=scenes), separators=(',', ':'))+'\n')
            readiness_summary['observed'] = True
            for scene in scenes:
                render = scene['render_readiness']
                readiness_summary['samples'] += 1
                readiness_summary['placeholder_samples'] += int(render.get('last_painted_placeholder') is True
                                                                 and render.get('last_painted_frame', 0) > 0)
                readiness_summary['peak_pending_psos'] = max(readiness_summary['peak_pending_psos'], render.get('pending_psos', 0))
                readiness_summary['peak_missing_proxies'] = max(readiness_summary['peak_missing_proxies'], render.get('missing_proxies', 0))
        return latest

    def wait(label, predicate, timeout=60):
        until = time.monotonic()+timeout
        while time.monotonic() < until:
            if process.poll() is not None:
                raise AssertionError(f'Native player exited {process.returncode} while waiting for {label}')
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(f'Timeout waiting for {label}')

    def command(action, **fields):
        nonlocal sequence
        sequence += 1
        temporary = control.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(sequence=sequence, action=action, **fields)))
        temporary.replace(control)
        wait(action, lambda: read().get('sequence', -1) >= sequence)

    def portrait_state():
        return read().get('hud', {}).get('portraits', {})

    def current_scenes():
        return {c['card_id']: c for c in portrait_state().get('scenes', [])}

    def verify_person_textures(scene):
        textures=scene['person_textures']
        assert textures, (scene['card_id'],'No character texture evidence')
        assert all(t['fully_streamed_in'] for t in textures), (scene['card_id'],'Portrait painted before texture detail was resident')
        for texture in textures:
            minimum=1024 if 'Hair_Strands' in texture['path'] else 512 if 'vit_face_bc_Color' in texture['path'] else 0
            assert min(texture['estimated_resident_top_size'])>=minimum, (scene['card_id'],texture)

    def wait_portraits_ready(label, ids, minimum_captures=None, minimum_revisions=None):
        started = time.monotonic()
        evidence = dict(label=label, ids=ids, shader_jobs_peak=0, asset_jobs_peak=0,
                        observed_busy=False, minimum_captures=minimum_captures,
                        minimum_revisions=minimum_revisions, passed=False)
        result['shader_readiness'].append(evidence)

        def ready():
            state = portrait_state()
            compilation = state.get('compilation', {})
            expected_mode = 'cooked_runtime' if args.package_dir else 'editor_compilers'
            assert compilation.get('telemetry_version') == 1, 'Portrait shader-readiness telemetry missing; rebuild the tested binary'
            assert compilation.get('mode') == expected_mode, f'Unexpected compiler telemetry mode: {compilation}'
            evidence['shader_jobs_peak'] = max(evidence['shader_jobs_peak'], compilation.get('shader_jobs', 0))
            evidence['asset_jobs_peak'] = max(evidence['asset_jobs_peak'], compilation.get('asset_jobs', 0))
            evidence['observed_busy'] |= not compilation.get('ready', False)
            evidence['last_compilation'] = compilation
            evidence['last_scenes'] = {scene['card_id']: {key: scene.get(key) for key in
                ('captures', 'condition_revision', 'compilation_zero_capture', 'compilation_zero_frame',
                 'post_zero_submissions', 'post_zero_captures', 'last_ready_capture_frame', 'capture_ready')}
                for scene in state.get('scenes', []) if scene['card_id'] in ids}
            return state if portraits_ready(state, ids, minimum_captures, minimum_revisions) else False

        state = wait(label+' shader queues and post-zero captures', ready, args.timeout)
        evidence['elapsed_seconds'] = time.monotonic()-started
        evidence['passed'] = True
        return state

    def capture(name, ids, minimum_captures=None, minimum_revisions=None):
        wait_portraits_ready(name, ids, minimum_captures, minimum_revisions)
        path = output/f'{name}.png'
        command('screenshot', filename=str(path))
        def png_complete():
            try:
                data = path.read_bytes()
                return len(data)>1000 and data.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in data[-16:]
            except OSError:
                return False
        wait(name, png_complete)
        assert portraits_ready(portrait_state(), ids, minimum_captures, minimum_revisions), \
            f'{name}: compilation/readiness changed while capturing; preserve this image as failed evidence'
        image = Image.open(path).convert('RGB')
        assert image.size == (width,height), (name,image.size)
        return image,path

    try:
        argv = runtime.argv + ([] if args.package_dir else ['/Game/Maps/WaterDepotV2']) + [
            '-game', '-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}',
            '-ExecCmds=t.MaxFPS 30', '-nosound', '-unattended', '-nosplash', '-NoLiveCoding', '-stdout',
            '-FullStdOutLogOutput', '-OldWestLifecycleTest', '-OldWestVisualTest',
            f'-OldWestLifecycleControl={control}', f'-OldWestLifecycleReport={report_path}',
            f'-GameUserSettingsINI={output}/player-settings.ini', f'-abslog={output}/player.log']
        process = subprocess.Popen(argv, cwd=runtime.cwd, env=runtime.env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        wait('menu HUD', lambda: read().get('hud') and read().get('snapshot', {}).get('hosted') is False, args.timeout)
        initial_snapshot = read()['snapshot']
        for offset in range(0,len(catalog),6):
            cards = catalog[offset:offset+6]
            ids = [c['id'] for c in cards]
            command('portrait_gallery', ids=ids, enabled=True)
            wait('real portrait captures', lambda: all(current_scenes().get(i,{}).get('captures',0)>=5 for i in ids), args.timeout)
            wait_portraits_ready('healthy '+','.join(ids), ids, {i: 5 for i in ids})
            time.sleep(args.settle)
            # Measure steady capture delivery without screenshot encoding/I/O
            # stalls. This is capture throughput under t.MaxFPS30, not GPU FPS.
            steady_first = current_scenes()
            time.sleep(2.)
            steady_second = current_scenes()
            first = {i: current_scenes()[i] for i in ids}
            a,a_path = capture(f'{offset//6+1:02d}-first', ids)
            time.sleep(.7)
            b,b_path = capture(f'{offset//6+1:02d}-loop', ids)
            second = current_scenes()
            hud = read().get('hud',{})
            assert hud.get('viewport_size') == [width,height], 'Reported physical viewport differs from screenshot'
            hud_width,hud_height = hud['hud_size']
            scale_x,scale_y = width/hud_width,height/hud_height
            rectangles = {}
            for raw in hud.get('portrait_gallery_cards',[]):
                rect = dict(raw, hud_min=raw['min'], hud_max=raw['max'])
                rect['min'] = [raw['min'][0]*scale_x,raw['min'][1]*scale_y]
                rect['max'] = [raw['max'][0]*scale_x,raw['max'][1]*scale_y]
                rectangles[raw['id']] = rect
            assert all(i in rectangles for i in ids), f'Actual portrait geometry absent: {ids}'
            evidence = []
            for card in cards:
                i = card['id']
                before,after = first[i],second[i]
                expected_target = [768,512] if card['type']=='person' else [384,256]
                assert before['target_size'] == after['target_size'] == expected_target, f'{i}: incorrect actual render target size'
                assert abs(after['capture_interval_seconds']-1/15)<1e-6, f'{i}: unexpected portrait capture budget'
                assert after['captures'] > before['captures'], f'{i}: capture did not advance'
                assert after['show_only_count'] == after['actors'], f'{i}: incomplete isolated show-only scene'
                assert after['visible_frames_ago'] <= 2, f'{i}: visible portrait is stale'
                if i=='stampede':
                    assert not after['people'] and len(after['vehicles'])==1, 'Stampede portrait still contains people'
                    vehicle=after['vehicles'][0]
                    assert vehicle['event_token'] and not vehicle['body_visible'] and not vehicle['weapon_visible']
                    assert not vehicle['event_equipment'] and vehicle['faces_opponent']
                    herd=vehicle['stampede']; old=before['vehicles'][0]['stampede']
                    assert herd['animal_count']==3 and len(herd['animals'])==3
                    assert all(a['clip']=='A_Longhorn_Idle' and a['collision']==0 and a['root_drift_cm']<.01 for a in herd['animals'])
                    assert all(a['seconds']!=b['seconds'] for a,b in zip(herd['animals'],old['animals'])), 'Stampede portrait is frozen'
                static_holding = i in holding_ids
                static_trouble = i in TROUBLE_MESHES
                if card['type']=='camp':
                    if static_holding:
                        assert after['camp_part_count'] >= 1 and after['camp_animated_parts'] == 0, f'{i}: holding design absent'
                    else:
                        assert after['camp_part_count'] >= 5 and after['camp_animated_parts'] > 0, f'{i}: camp design absent'
                    validate_camp_composition(after)
                    changed = static_holding or before['motion_signature'] != after['motion_signature']
                elif static_trouble:
                    folder, name = TROUBLE_MESHES[i]
                    mesh = f'SM_Trouble_{name}'
                    assert after['trouble_mesh'] == f'/Game/Art/Western/Trouble/{folder}/Meshes/{mesh}.{mesh}', f'{i}: wrong Trouble miniature'
                    assert not after['people'] and not after['vehicles'] and after['trouble_collision'] == 0
                    changed = True  # Authored static miniature; capture freshness is still checked.
                else:
                    assert after['skeletal_loops'] or after['animated_props'], f'{i}: no animated content'
                    changed = before['motion_signature'] != after['motion_signature']
                    if card['type']=='person':
                        verify_person_textures(after)
                        name=''.join(word.title() for word in i.split('_'))
                        if i=='blacksmith':expected_mesh='/Game/Art/Survivors/RepairBot/SKM_RepairBot_Cm.SKM_RepairBot_Cm'
                        elif i=='quanah_parker':expected_mesh='/Game/Art/Western/Quanah/SK_Quanah.SK_Quanah'
                        elif i in ('prospector','gatling_gunner','bounty_hunter'):expected_mesh=f'/Game/Art/Survivors/Variants/SKM_{name}_Cm.SKM_{name}_Cm'
                        else:expected_mesh=f'/Game/Art/Survivors/Identities/SKM_{name}_Cm.SKM_{name}_Cm'
                        assert after['people'] and all(p['visual_mesh']==expected_mesh for p in after['people']),f'{i}: wrong public identity mesh'
                    for earlier,later in zip(before.get('people',[]),after.get('people',[])):
                        assert later['playing'] and later['looping'], f'{i}: person is not in looping idle'
                        alignment=later.get('weapon_alignment',{})
                        if alignment.get('two_hand_pose'):
                            assert alignment['native_forward_axis']=='+Y', f'{i}: rifle uses the wrong mesh axis'
                            assert max(alignment['right_contact_gap_cm'],alignment['left_contact_gap_cm'])<2., f'{i}: weapon misses its palm contacts'
                            assert max(alignment['live_right_palm_gap_cm'],alignment['live_left_palm_gap_cm'])<3., f'{i}: visible live hand pose drifts from the weapon'
                        changed |= abs(earlier['animation_position']-later['animation_position']) > .001
                        pose_delta = max((abs(a-b) for p,q in zip(earlier.get('pose_samples',[]),later.get('pose_samples',[]))
                                          for a,b in zip(p,q)),default=0.)
                        assert pose_delta > .001, f'{i}: skeletal animation clock advanced but actual bone pose is frozen'
                assert changed, f'{i}: transforms and skeletal pose time did not change'
                rect = rectangles[i]
                x0,y0 = rect['min']; x1,y1 = rect['max']
                assert 0 <= x0 < x1 <= width+1 and 0 <= y0 < y1 <= height+1, f'{i}: portrait clipped {rect}'
                box = tuple(map(round,(x0,y0,x1,y1)))
                crop_a,crop_b = a.crop(box),b.crop(box)
                spread = sum(ImageStat.Stat(crop_b).stddev)/3
                diff = ImageStat.Stat(ImageChops.difference(crop_a,crop_b))
                difference = sum(diff.mean)/3
                red_channel,green_channel,blue_channel = crop_b.split()
                white_mask = ImageChops.darker(red_channel,ImageChops.darker(green_channel,blue_channel)).point(lambda value: 255 if value>=248 else 0)
                white_fraction = white_mask.histogram()[255]/(crop_b.width*crop_b.height)
                assert white_fraction < .15, f'{i}: blown highlights obscure portrait ({white_fraction:.1%} pure white)'
                # State motion alone does not prove the card has been displayed.
                # Require a nonblank scene and visible frame change inside its own bounds.
                assert spread > 4., f'{i}: blank/flat portrait (standard deviation {spread:.3f})'
                assert static_holding or static_trouble or difference > .015, f'{i}: rendered loop did not visibly move ({difference:.5f})'
                crop_b.save(output/f'card-{i}.png')
                capture_window = after['loop_time']-before['loop_time']
                assert capture_window > 0, f'{i}: nonpositive capture observation interval'
                steady_window = steady_second[i]['loop_time']-steady_first[i]['loop_time']
                steady_captures = steady_second[i]['captures']-steady_first[i]['captures']
                assert steady_window > 0 and steady_captures > 0, f'{i}: no steady portrait captures'
                item = dict(id=i,type=card['type'],before=before,after=after,rectangle=rect,
                            observed_capture_seconds=capture_window,
                            observed_capture_fps=(after['captures']-before['captures'])/capture_window,
                            steady_capture_seconds=steady_window,steady_capture_delta=steady_captures,
                            steady_capture_fps=steady_captures/steady_window,
                            frame_difference=difference,pixel_spread=spread,white_fraction=white_fraction,first=str(a_path),loop=str(b_path))
                result['cards'].append(item); evidence.append(item)
            (output/f'{offset//6+1:02d}-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
            if args.face_review:
                assert all(card['type']=='person' for card in cards), 'Face review requires only person cards'
                for expression,expected in [('neutral',{}),('blink',{'Eyes_Closed_Max':1.}),
                    ('jaw-open',{'Jaw_Lower':.6,'Mouth_Large_Opened':.35}),('smile',{'Smile_Lips_Closed':.8}),
                    ('brows-raised',{'Eyebrows_Raised_Left':.85,'Eyebrows_Raised_Right':.85}),
                    ('brows-frown',{'Eyebrows_Frown_Left':.85,'Eyebrows_Frown_Right':.85})]:
                    revisions={i:current_scenes()[i]['condition_revision']+1 for i in ids}
                    command('portrait_gallery',details=[dict(id=i,enabled=True,expression=expression) for i in ids])
                    face_image,face_path=capture(f'{offset//6+1:02d}-face-{expression}',ids,minimum_revisions=revisions)
                    for i in ids:
                        scene=current_scenes()[i]
                        assert scene['detail_review'] and scene['detail_expression']==expression
                        verify_person_textures(scene)
                        person=scene['people'][0]
                        assert person['manual_presentation']['animation_asset'].endswith('/RA_MM_Idle.RA_MM_Idle')
                        assert not person['playing'] and not person['weapon_visible']
                        weights=scene['detail_morph_weights']
                        assert len(weights)==len(expected)
                        for suffix,value in expected.items():
                            matches=[weight for name,weight in weights.items() if name.endswith(suffix)]
                            assert len(matches)==1 and abs(matches[0]-value)<1e-5,(i,expression,weights)
                        rect=rectangles[i];box=tuple(map(round,rect['min']+rect['max']))
                        crop=face_image.crop(box)
                        assert sum(ImageStat.Stat(crop).stddev)/3>4., 'Blank close-up capture'
                        crop_path=output/f'face-{i}-{expression}.png';crop.save(crop_path)
                        result['face_reviews'].append(dict(id=i,expression=expression,morph_weights=weights,
                            capture=str(crop_path),sha256=hashlib.sha256(crop_path.read_bytes()).hexdigest(),scene=scene))
                revisions={i:current_scenes()[i]['condition_revision']+1 for i in ids}
                command('portrait_gallery',details=[dict(id=i,enabled=False,expression='neutral') for i in ids])
                wait_portraits_ready('restored full portraits',ids,minimum_revisions=revisions)
                assert all(not current_scenes()[i]['detail_review'] for i in ids)
                assert all(not current_scenes()[i]['detail_morph_weights'] for i in ids)
                for i in ids:
                    restored=current_scenes()[i]['people'][0]
                    original=second[i]['people'][0]
                    for key in ('playing','looping','weapon_visible','active_clip','animation_play_rate'):
                        assert restored[key]==original[key], (i,'Review did not restore '+key)
                    assert restored['manual_presentation']['animation_asset']==original['manual_presentation']['animation_asset']
                # A person can animate entirely through its skeletal mesh,
                # leaving the static-prop motion signature unchanged.
                restored_a, restored_a_path = capture(f'{offset//6+1:02d}-restored-first', ids)
                resume = current_scenes()
                wait('full portrait motion resumes',
                     lambda: all(person_motion_resumed(resume[i], current_scenes()[i]) for i in ids), 10)
                time.sleep(.7)
                restored_b, restored_b_path = capture(f'{offset//6+1:02d}-restored-loop', ids)
                resumed = current_scenes()
                for i in ids:
                    assert person_motion_resumed(resume[i], resumed[i]), (i, 'Restored skeletal pose is frozen')
                    rect = rectangles[i]
                    box = tuple(map(round, rect['min']+rect['max']))
                    difference = sum(ImageStat.Stat(ImageChops.difference(
                        restored_a.crop(box), restored_b.crop(box))).mean)/3
                    assert difference > .015, (i, 'Restored portrait does not visibly move', difference)
                    result.setdefault('face_review_motion_restore', []).append(dict(
                        id=i, first=str(restored_a_path), loop=str(restored_b_path), pixel_difference=difference,
                        before_people=resume[i]['people'], after_people=resumed[i]['people']))
                result['face_review_restore_passed']=True
            camp_ids = [c['id'] for c in cards if c['type']=='camp']
            if camp_ids and not args.skip_conditions:
                healthy = {i: second[i] for i in camp_ids}
                previous_image = b
                phase_evidence = {i: [] for i in camp_ids}
                for phase,damage,destroyed in [('damaged',1,False),('ruined',2,True),('repaired',0,False)]:
                    previous_counts = {i: current_scenes()[i]['captures'] for i in camp_ids}
                    next_revisions = {i: current_scenes()[i]['condition_revision']+1 for i in camp_ids}
                    command('portrait_gallery',conditions=[dict(id=i,damage=damage,destroyed=destroyed) for i in camp_ids])
                    wait('camp '+phase, lambda: all(current_scenes().get(i,{}).get('camp_damage')==damage
                         and current_scenes()[i]['camp_destroyed']==destroyed
                         and current_scenes()[i]['captures']>previous_counts[i]+2 for i in camp_ids))
                    state_image,state_path = capture(f'{offset//6+1:02d}-{phase}', ids,
                        {i: previous_counts[i]+3 for i in camp_ids}, next_revisions)
                    states = current_scenes()
                    for i in camp_ids:
                        state = states[i]
                        assert state['camp_part_count']==healthy[i]['camp_part_count'], f'{i}: condition lost scene parts'
                        bounds = state['camp_bounds']
                        assert bounds and all(lo<hi for lo,hi in zip(bounds['min'],bounds['max'])), f'{i}: invalid {phase} bounds'
                        assert state['camp_ruin_smoke_parts']==(18 if destroyed and i not in {'rockslide_ridge', 'lookout_ridge'} else 0), f'{i}: ruin smoke visibility does not match condition'
                        if i in {'rockslide_ridge', 'lookout_ridge'}:
                            asset = {'rockslide_ridge': 'RockslideRidge', 'lookout_ridge': 'LookoutRidge'}[i]
                            assert state['fire_sheets'] == 0, 'Geological condition spawned fire or smoke'
                            visible = state['camp_visible_meshes']
                            rocks = [m for m in visible if '/SM_HoldingBase_' not in m['mesh']]
                            suffix = 'Ruin' if destroyed else ('Damaged' if damage else '')
                            assert len(rocks) == 1 and f'/SM_Holding{suffix}_{asset}.' in rocks[0]['mesh']
                            assert rocks[0]['materials'] == [f'/Game/Art/Western/ExpansionHoldings/{asset}/M_Holding_{asset}.M_Holding_{asset}'], 'Geological condition received soot/char materials'
                        if destroyed:
                            if i in COMPLETION_HOLDINGS:
                                asset = COMPLETION_HOLDINGS[i]
                                visible = [m['mesh'] for m in state['camp_visible_meshes']]
                                assert any(f'/SM_HoldingRuin_{asset}.' in mesh for mesh in visible), f'{asset}: authored ruin missing'
                                assert not any(f'/SM_Holding_{asset}.' in mesh for mesh in visible), f'{asset}: healthy mesh visible after destruction'
                            if i in {'gunsmith', 'jailhouse', 'post_office', 'army_surgeon_s_tent', 'courthouse', 'free_homestead', 'chuckwagon', 'pony_express_station', 'gallows', 'robbers_roost', 'smuggler_s_landing', 'bounty_office'}:
                                asset = {'gunsmith': 'Gunsmith', 'jailhouse': 'Jailhouse', 'post_office': 'PostOffice',
                                         'army_surgeon_s_tent': 'ArmySurgeonsTent', 'courthouse': 'Courthouse', 'free_homestead': 'FreeHomestead', 'chuckwagon': 'Chuckwagon', 'pony_express_station': 'PonyExpressStation', 'gallows': 'Gallows', 'robbers_roost': 'RobbersRoost', 'smuggler_s_landing': 'SmugglersLanding', 'bounty_office': 'BountyOffice'}[i]
                                visible = [m['mesh'] for m in state['camp_visible_meshes']]
                                assert any(f'/SM_HoldingRuin_{asset}.' in m for m in visible), f'{asset} has no dedicated ruin'
                                assert not any(f'/SM_Holding_{asset}.' in m for m in visible), f'Healthy {asset} still visible in ruin'
                                if i in {'courthouse', 'free_homestead', 'chuckwagon', 'pony_express_station', 'gallows', 'robbers_roost', 'smuggler_s_landing', 'bounty_office'}:
                                    ruins = [m for m in state['camp_visible_meshes'] if f'/SM_HoldingRuin_{asset}.' in m['mesh']]
                                    assert len(ruins) == 1 and ruins[0]['materials'] == [
                                        f'/Game/Art/Western/ExpansionHoldings/{asset}/Conditions/AuthoredRuin/M_{asset}_AuthoredRuin.M_{asset}_AuthoredRuin'
                                    ], f'{asset} lost its authored soot texture'
                            # Portrait framing includes the landscape. Embedded
                            # rocks can extend below zero; check each rendered
                            # building remnant independently of that terrain.
                            remnants = [m for m in state['camp_visible_meshes']
                                        if '/SM_HoldingBase_' not in m['mesh']
                                        and '/SM_HoldingWater_' not in m['mesh']]
                            assert remnants, f'{i}: no rendered ruin meshes'
                            assert all(m['bounds']['min'][2]>=-.5 for m in remnants), \
                                f'{i}: ruined geometry is buried under the ground'
                            assert state['camp_visible_parts']>0, f'{i}: ruin contains no visible remnants'
                            assert state['camp_max_abs_part_ground_gap_cm']<=.5, f'{i}: an individual ruined part is floating or buried ({state["camp_max_abs_part_ground_gap_cm"]:.3f}cm)'
                        validate_camp_composition(state)
                        rect = rectangles[i]
                        box = tuple(map(round,(*rect['min'],*rect['max'])))
                        delta = sum(ImageStat.Stat(ImageChops.difference(previous_image.crop(box),state_image.crop(box))).mean)/3
                        assert delta>.03, f'{i}: {phase} has no visible scene change'
                        phase_evidence[i].append(dict(phase=phase,scene=state,frame_difference=delta,screenshot=str(state_path)))
                        if phase=='repaired':
                            if i in holding_ids:
                                assert state['camp_visible_meshes'] == healthy[i]['camp_visible_meshes'], f'{i}: repair changed mesh, material, transform or collision'
                            assert state['camp_visible_parts']==healthy[i]['camp_visible_parts'], f'{i}: repair did not restore every healthy visible part'
                            old = healthy[i]['camp_bounds']
                            for axis in range(3):
                                old_size = old['max'][axis]-old['min'][axis]
                                new_size = bounds['max'][axis]-bounds['min'][axis]
                                assert abs(new_size-old_size)<max(8.,old_size*.35), f'{i}: repaired geometry did not return to its healthy scale'
                    previous_image=state_image
                    assert read()['snapshot'] == initial_snapshot, 'Preview damage changed authoritative game state'
                resume = {i: current_scenes()[i] for i in camp_ids}
                moving = [i for i in camp_ids if i not in holding_ids]
                wait('repaired camp loops resume', lambda: all(current_scenes().get(i,{}).get('motion_signature')!=resume[i]['motion_signature'] for i in moving),10)
                for i in camp_ids:
                    result['camp_conditions'].append(dict(id=i,phases=phase_evidence[i],motion_resumed=i not in holding_ids,static_holding=i in holding_ids))
            assert read()['snapshot'] == initial_snapshot, 'Gallery changed authoritative game state'
            if offset == 0:
                # A duplicated card uses the same scene, and an ordinary HUD
                # rebuild preserves its running loop instead of restarting it.
                previous_count = second[ids[0]]['captures']
                command('portrait_gallery', ids=[ids[0],ids[0]], enabled=True)
                wait('shared portrait survives widget rebuild', lambda: current_scenes().get(ids[0],{}).get('captures',0)>previous_count)
                wait('unused scene retirement', lambda: portrait_state().get('scene_count')==1, 10)
                assert len(current_scenes()) == 1, 'Duplicate card allocated duplicate scenes'
                result['shared_scene_passed']=True
                result['rebuild_continuity_passed']=True
            print(f"Portraits {min(offset+6,len(catalog))}/{len(catalog)} passed: {', '.join(ids)}",flush=True)
        command('portrait_gallery',enabled=False,ids=[])
        wait('portrait actors reclaimed', lambda: portrait_state().get('scene_count') == 0, 10)
        result['reclamation_passed']=True
        log = (output/'player.log').read_text(errors='replace')
        errors = re.findall(r'^.*(?:OLDWEST_PORTRAIT_ERROR|OLDWEST_CAMP_VISUAL_ERROR|Failed to compile Material|missing usage flag|is not a valid parent for MaterialInstanceDynamic|Assertion failed:|Fatal error:).*$' ,log,re.M)
        assert not errors, errors[:10]
        command('quit')
        process.wait(timeout=30)
        result['process_exit_code']=process.returncode
        assert process.returncode == 0, f'Quit returned {process.returncode}'
        result['runtime_assets']=assert_runtime_assets([output/'player.log'])
        result['binary_unchanged_during_run'] = signature(binary)['sha256'] == (build.get('module') or build['executable'])['sha256']
        assert result['binary_unchanged_during_run'], 'Game binary changed while the rendered audit was running'
        if not runtime.package_root:
            recorded_assets = [asset for key in ('portrait_assets', 'identity_assets', 'variant_assets',
                                                 'survivor_assets', 'repair_bot_assets') for asset in build[key]]
            changed_assets = [asset['path'] for asset in recorded_assets
                              if signature(Path(asset['path']))['sha256'] != asset['sha256']]
            result['source_assets_unchanged_during_run'] = not changed_assets
            assert not changed_assets, f'Portrait source assets changed during the run: {changed_assets[:10]}'
        result['ok']=True
    except Exception as error:
        result['error']=str(error)
        import traceback
        result['traceback']=traceback.format_exc()
    finally:
        if process and process.poll() is None:
            stop_owned_process_groups([process])
        stream.close()
        readiness_stream.close()
        result['render_readiness_observation'] = dict(readiness_summary, samples_file=str(output/'render-readiness.jsonl'),
            limitation='Polling samples retain their query and prior actual paint frames; these are not every rendered frame or GPU readbacks.')
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(ok=result['ok'],cards_checked=len(result['cards']),report=str(output/'result.json'),error=result.get('error')),indent=2),flush=True)
    return result['ok']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor',type=Path,default=EDITOR)
    parser.add_argument('--package-dir',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--cards',nargs='+')
    parser.add_argument('--card-types',nargs='+',choices=['camp','person','event','resource'],help='Audit every card in selected catalog types')
    parser.add_argument('--resolution',default='1920x1080',choices=['1280x720','1920x1080'])
    parser.add_argument('--settle',type=float,default=1.7)
    parser.add_argument('--skip-conditions',action='store_true',help='Debug a healthy-only gallery; full regression includes every camp damage/ruin/repair')
    parser.add_argument('--face-review',action='store_true',help='Capture face close-ups and verify six expression states on selected people')
    parser.add_argument('--timeout',type=float,default=120)
    raise SystemExit(0 if run(parser.parse_args()) else 1)
