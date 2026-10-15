"""Native close-ups of three imported identities in real animation-asset poses.

Run with -ExecutePythonScript, -RenderOffscreen and an isolated settings file.
Requires OLDWEST_VARIANT_SOURCE and OLDWEST_IDENTITY_REVIEW_OUTPUT. Saves
screenshots/reports only; never saves the map or edits a source/native asset.
This is an animation pose study, not a gameplay or ragdoll test.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ['OLDWEST_VARIANT_SOURCE']).resolve()
OUT = Path(os.environ['OLDWEST_IDENTITY_REVIEW_OUTPUT']).resolve()
OUT.mkdir(parents=True, exist_ok=False)
audit = json.loads((SOURCE / 'native-reference-audit.json').read_text())
assert audit['ok'] and len(audit['variants']) == 3
BASE = '/Game/Art/Survivors/SurvivorA'
paths = [ROOT / 'game/OldWest/Content/Maps/WaterDepotV2.umap']
paths += list((ROOT / 'game/OldWest/Content/Art/Survivors').rglob('*.uasset'))
protected = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/WaterDepotV2')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
components = []
origin_z = 50.
for index, record in enumerate(audit['variants']):
    actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor,
                                         unreal.Vector((index - 1) * 85, 2500, origin_z))
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(unreal.load_asset(record['mesh']))
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_update_animation_in_editor(True)
    component.set_forced_lod(1)
    assert all(component.get_bone_index(bone) >= 0 for bone in ('Head', 'Neck', 'Spine2'))
    components.append(component)
camera = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(0, 2840, origin_z + 157))
target = unreal.Vector(0, 2500, origin_z + 157)
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), target), False)
lens = camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length', 50)
lens.set_editor_property('current_aperture', 8)
lens.set_editor_property('filmback', unreal.CameraFilmbackSettings(sensor_width=36, sensor_height=20.25))
focus = unreal.CameraFocusSettings()
focus.focus_method = unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings', focus)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
for command in ('r.ScreenPercentage 100', 'r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 8192'):
    unreal.SystemLibrary.execute_console_command(world, command)
clips = [('idle', 'RA_MM_Idle', 2.), ('rifle-idle', 'RA_MF_Rifle_Idle_ADS', 2.),
         ('hit', 'RA_MM_HitReact_Front_Lgt_01', .20), ('walk', 'RA_MF_Rifle_Walk_Fwd', .45)]
report = {'ok': False, 'scope': 'Native Vulkan animation-pose close-ups; not gameplay/ragdoll or human acceptance',
          'characters_in_world_x_order': [record['card_id'] for record in audit['variants']],
          'protected_sha256': protected, 'captures': []}


def pose(index):
    animation = unreal.load_asset(BASE + '/Animations/' + clips[index][1])
    assert animation
    for component in components:
        component.set_animation(animation)
        component.set_position(clips[index][2], False)
        component.stop()


pose(0)
index, requested, priming = 0, False, True
deadline = time.monotonic() + 35
unreal.EditorPythonScripting.set_keep_python_script_alive(True)


def finish():
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.SystemLibrary.quit_editor()


def tick(delta):
    global index, requested, deadline, priming
    if time.monotonic() < deadline:
        return
    try:
        name, clip, seconds = clips[index]
        path = OUT / ('warmup.png' if priming else name + '.png')
        if not requested:
            unreal.AutomationLibrary.take_high_res_screenshot(2560, 1440, str(path), camera=camera, delay=2)
            requested = True
            deadline = time.monotonic() + 10
            return
        png = path.read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n' and png.endswith(b'IEND\xaeB`\x82')
        assert int.from_bytes(png[16:20], 'big') == 2560 and int.from_bytes(png[20:24], 'big') == 1440
        if priming:
            report['warmup_capture'] = {'path': str(path), 'sha256': hashlib.sha256(png).hexdigest()}
            priming, requested = False, False
            deadline = time.monotonic() + 8
            return
        poses = []
        for component in components:
            points = {}
            for bone in ('Head', 'Neck', 'Spine2'):
                point = component.get_socket_location(bone)
                points[bone] = [point.x, point.y, point.z]
            poses.append(points)
        report['captures'].append({'pose': name, 'animation': BASE + '/Animations/' + clip,
                                   'animation_seconds': seconds, 'bone_locations': poses,
                                   'path': str(path), 'sha256': hashlib.sha256(png).hexdigest()})
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in protected.items())
        index += 1
        if index == len(clips):
            report.update(ok=True, protected_assets_unchanged=True, visual_review_required=True)
            unreal.log('IDENTITY_POLISH_POSES_COMPLETE')
            finish()
            return
        pose(index)
        requested = False
        deadline = time.monotonic() + 4
    except Exception as error:
        report['error'] = repr(error)
        unreal.log_error('IDENTITY_POLISH_POSES_FAILED ' + repr(error))
        finish()


handle = unreal.register_slate_post_tick_callback(tick)
