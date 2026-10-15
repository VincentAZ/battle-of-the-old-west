"""Capture saved Crew rigs in one Unreal process; transient stage, never save a map.

OLDWEST_CREW_SLUGS=comma,separated UnrealEditor <project> -ExecutePythonScript=<this>
A single OLDWEST_CREW_SLUG is also accepted. Reopens saved packages before
capturing 24 poses each. Render success is not visual QA approval.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import runpy
import sys
import time
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from crew_unreal_contract import BASE, character, snapshot, sha
from crew_capture_reuse import unmodified_captures

requested = os.environ.get('OLDWEST_CREW_SLUGS') or os.environ['OLDWEST_CREW_SLUG']
configs = [character(slug) for slug in requested.split(',')]
CANDIDATE = os.environ.get('OLDWEST_CREW_ATTACK_CANDIDATE') == '1'
assert not (CANDIDATE and os.environ.get('OLDWEST_CREW_ATTACK_ONLY') == '1')
os.environ['OLDWEST_CREW_SLUGS'] = requested
os.environ['OLDWEST_CREW_VERIFY_ONLY'] = '1'
runpy.run_path(str(ROOT/'scripts/prepare_crew_playable_unreal.py'), run_name='__main__')
lock = (BASE/'.unreal-authoring.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
content_before = snapshot()
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/WaterDepotV2')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for command in ('r.ScreenPercentage 100', 'r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 4096', 'r.MotionBlurQuality 0'):
    unreal.SystemLibrary.execute_console_command(world, command)
origin = unreal.Vector(0, 2500, 150)
floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, origin)
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(200, 200, 1))
actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, origin)
component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
component.set_update_animation_in_editor(True)
component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
component.set_editor_property('visibility_based_anim_tick_option', unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
component.set_editor_property('enable_update_rate_optimizations', False)
camera = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(-650, 3300, 450))
lens = camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length', 55)
lens.set_editor_property('current_aperture', 8)
lens.set_editor_property('filmback', unreal.CameraFilmbackSettings(sensor_width=36, sensor_height=20.25))
focus = unreal.CameraFocusSettings()
focus.focus_method = unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings', focus)
light = actors.spawn_actor_from_class(unreal.RectLight, unreal.Vector(-350, 3100, 650))
light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(light.get_actor_location(), unreal.Vector(0, 2500, 260)), False)
light_component = light.get_component_by_class(unreal.RectLightComponent)
light_component.set_intensity(8000)
light_component.set_editor_property('source_width', 400)
light_component.set_editor_property('source_height', 400)
character_index = 0
shot_index = 0
requested_shot = False
reports = []


def activate(index):
    global config, report, shots, previews, target, framing
    config = configs[index]
    mesh = unreal.load_asset(config['dest']+'/SK_'+config['name'])
    assert mesh
    component.set_skeletal_mesh_asset(mesh)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_update_animation_in_editor(True)
    component.set_editor_property('visibility_based_anim_tick_option', unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    target, extent = actor.get_actor_bounds(False)
    framing = max(1., extent.x/95., extent.y/95., extent.z/95.)
    shots = []
    for view, location in [('front', (0,600,20)), ('side', (-600,0,20)), ('rear', (0,-600,20))]:
        for phase in range(4):
            shots.append((f'walk-{view}-{phase:02d}', 'MF_Unarmed_Walk_Fwd', (0., .13, .33, .58)[phase], location))
    for clip in ('MM_Idle', 'MM_Attack_01', 'MM_HitReact_Front_Lgt_01'):
        for phase in range(4):
            shots.append((f'{clip}-{phase:02d}', clip, phase/4, (-240,600,50)))
    previews = config['out']/('attack-candidate-previews' if CANDIDATE else 'previews')
    previews.mkdir(exist_ok=True)
    report = {'ok': False, 'renderer': 'Unreal Vulkan', 'scope': 'Temporary pose stage; gameplay tested separately',
              'slug': config['slug'], 'rig_project_sha256': config['validation']['project_sha256'],
              'rig_validation_sha256': sha(config['out']/'rig-validation.json'),
              'unreal_assets_sha256': sha(config['out']/'unreal-assets.json'),
              'visual_qa_passed': False, 'captures': []}
    reports.append(report)
    if CANDIDATE:
        shots = [shot for shot in shots if shot[1] == 'MM_Attack_01']
        shots.extend((f'MM_Attack_01-{view}-02', 'MM_Attack_01', .5, location)
                     for view, location in [('front', (0,600,20)), ('side', (-600,0,20)), ('rear', (0,-600,20))])
        report['scope'] = 'Seven-view attack candidate; does not replace final 24-pose evidence'
    elif os.environ.get('OLDWEST_CREW_ATTACK_ONLY') == '1':
        reused, proof = unmodified_captures(config['out'])
        report['captures'] = reused
        report['reused_capture_evidence'] = proof
        shots = [shot for shot in shots if shot[1] == 'MM_Attack_01']


POSE_BONES = ('Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder',
              'LeftArm','RightArm','LeftForeArm','RightForeArm','LeftLeg','RightLeg','LeftFoot','RightFoot')


def values(transform):
    p, q, scale = transform.translation, transform.rotation, transform.scale3d
    return (p.x,p.y,p.z,q.x,q.y,q.z,q.w,scale.x,scale.y,scale.z)


def pose(index):
    global expected_pose, pose_timeout, expected_seconds
    name, clip, fraction, location = shots[index]
    camera.set_actor_location(target + unreal.Vector(*(value*framing for value in location)), False, False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), target), False)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
    animation = unreal.load_asset(config['dest']+'/Animations/RA_'+clip)
    assert animation
    expected_seconds = animation.get_play_length()*fraction
    expected = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, expected_seconds, unreal.AnimPoseEvaluationOptions())
    expected_pose = {bone: values(unreal.AnimPoseExtensions.get_bone_pose(expected, bone, unreal.AnimPoseSpaces.LOCAL)) for bone in POSE_BONES}
    # A stopped single-node instance may retain its previous evaluated pose in
    # editor viewports. Keep evaluation active at zero speed after setting time.
    component.play_animation(animation, False)
    component.set_play_rate(0.)
    component.set_position(expected_seconds, False)
    pose_timeout = time.monotonic()+15


def measured_pose():
    actual = {bone: values(component.get_bone_transform(bone, unreal.RelativeTransformSpace.RTS_PARENT_BONE_SPACE)) for bone in POSE_BONES}
    translation, rotation = 0., 0.
    for bone in POSE_BONES:
        want, got = expected_pose[bone], actual[bone]
        translation = max(translation, math.dist(want[:3], got[:3]))
        rotation = max(rotation, min(math.dist(want[3:7], got[3:7]), math.dist(want[3:7], tuple(-v for v in got[3:7]))))
    error = {'translation_cm': translation, 'quaternion_error': rotation, 'time_seconds': abs(component.get_position()-expected_seconds)}
    valid = translation < .025 and rotation < .002 and error['time_seconds'] < .0001
    return valid, actual, error


def save_report():
    filename = 'attack-candidate-captures.json' if CANDIDATE else 'unreal-pose-captures.json'
    (config['out']/filename).write_text(json.dumps(report, indent=2)+'\n')


def finish():
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.SystemLibrary.quit_editor()


activate(0)
pose(0)
deadline = time.monotonic()+30


def tick(delta):
    global character_index, shot_index, requested_shot, deadline, capture_timeout
    if time.monotonic() < deadline:
        return
    try:
        name, clip, fraction, location = shots[shot_index]
        path = previews/('Unreal-'+name+'.png')
        if not requested_shot:
            matched, actual, error = measured_pose()
            if not matched:
                assert time.monotonic() < pose_timeout, 'Component pose does not match requested animation: '+json.dumps(error)
                deadline = time.monotonic()+.1
                return
            if path.exists():
                path.unlink()
            unreal.AutomationLibrary.take_high_res_screenshot(1280,720,str(path),camera=camera,delay=.2)
            requested_shot = True
            deadline = time.monotonic()+.9
            capture_timeout = time.monotonic()+10
            return
        if not path.exists() or not path.read_bytes().endswith(b'IEND\xaeB`\x82'):
            assert time.monotonic() < capture_timeout, 'Screenshot did not finish: '+str(path)
            deadline = time.monotonic()+.1
            return
        matched, actual, error = measured_pose()
        assert matched, 'Pose changed during screenshot: '+json.dumps(error)
        animation = unreal.load_asset(config['dest']+'/Animations/RA_'+clip)
        report['captures'].append({'file': str(path.relative_to(config['out'])), 'clip': clip,
            'seconds': animation.get_play_length()*fraction, 'fraction': fraction, 'size': [1280,720],
            'component_local_pose': actual, 'expected_animation_local_pose': expected_pose, 'pose_error': error,
            'component_pose_sha256': hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest(),
            'component_world_positions': {bone: values(component.get_bone_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD))[:3] for bone in POSE_BONES},
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        shot_index += 1
        if shot_index == len(shots):
            for clip_name in {v['clip'] for v in report['captures']}:
                samples = [v['component_local_pose'] for v in report['captures'] if v['clip']==clip_name]
                assert len({json.dumps(v,sort_keys=True) for v in samples}) > 1, 'Repeated component pose: '+clip_name
            report['component_pose_verified'] = True
            report['existing_content_unchanged'] = snapshot() == content_before
            assert report['existing_content_unchanged'], 'Review changed Content packages'
            report['ok'] = True
            save_report()
            unreal.log_warning('CREW_POSE_CAPTURE_COMPLETE '+config['slug'])
            character_index += 1
            if character_index == len(configs):
                finish()
                return
            activate(character_index)
            shot_index = 0
            pose(shot_index)
            requested_shot = False
            deadline = time.monotonic()+5
            return
        pose(shot_index)
        requested_shot = False
        deadline = time.monotonic()+.4
    except Exception as exc:
        report.update(ok=False, error=repr(exc), traceback=traceback.format_exc())
        save_report()
        unreal.log_error('CREW_CAPTURE_FAILED '+repr(exc))
        finish()


handle = unreal.register_slate_post_tick_callback(tick)
