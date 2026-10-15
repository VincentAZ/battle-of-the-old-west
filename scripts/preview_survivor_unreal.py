"""Capture actual Unreal survivor poses without saving changes to the map."""
import json
import time
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/characters/oldwest_survivor'
DEST = '/Game/Art/Survivors/SurvivorA'
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/WaterDepotV2')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for cmd in ['r.ScreenPercentage 100', 'r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 8192']:
    unreal.SystemLibrary.execute_console_command(world, cmd)
actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(0, 2500, 40))
component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
mesh = unreal.load_asset(DEST+'/SKM_Survivor_A_Cm')
assert mesh
component.set_skeletal_mesh_asset(mesh)
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
component.set_update_animation_in_editor(True)
camera = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(210, 2020, 180))
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), unreal.Vector(0, 2500, 133)), False)
lens = camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length', 55)
lens.set_editor_property('current_aperture', 8)
lens.set_editor_property('filmback', unreal.CameraFilmbackSettings(sensor_width=36, sensor_height=20.25))
focus = unreal.CameraFocusSettings()
focus.focus_method = unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings', focus)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
clips = [
    ('idle', 'RA_MM_Idle', 2.0), ('rifle_idle', 'RA_MF_Rifle_Idle_ADS', 2.0),
    ('fire', 'RA_MM_Rifle_Fire', .18), ('hit', 'RA_MM_HitReact_Front_Lgt_01', .20),
    ('walk', 'RA_MF_Rifle_Walk_Fwd', .45), ('death', 'RA_MM_Death_Right_01', .85),
]


def pose(index):
    name, clip, seconds = clips[index]
    animation = unreal.load_asset(DEST+'/Animations/'+clip)
    assert animation, clip
    component.set_animation(animation)
    component.set_position(seconds, False)
    component.stop()
    unreal.log('SURVIVOR_PREVIEW_POSE '+name)


pose(0)
index, requested = 0, False
deadline = time.monotonic()+30
report = {'renderer': 'Unreal Vulkan', 'mesh': mesh.get_path_name(), 'captures': [], 'human_review_required': True}


def tick(delta):
    global index, requested, deadline
    if time.monotonic() < deadline:
        return
    try:
        name = clips[index][0]
        path = OUT/f'UnrealSurvivor_{name}.png'
        if not requested:
            # Existing screenshots are regenerated for the current assets.
            if path.exists(): path.unlink()
            unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, str(path), camera=camera, delay=2)
            requested = True
            deadline = time.monotonic()+9
        else:
            assert path.exists(), f'No native screenshot produced: {path}'
            report['captures'].append(str(path))
            index += 1
            if index == len(clips):
                (OUT/'unreal-pose-captures.json').write_text(json.dumps(report, indent=2)+'\n')
                unreal.unregister_slate_post_tick_callback(handle)
                unreal.log('SURVIVOR_PREVIEW_COMPLETE')
                unreal.SystemLibrary.quit_editor()
                return
            pose(index)
            requested = False
            deadline = time.monotonic()+3
    except Exception as error:
        unreal.log_error('SURVIVOR_PREVIEW_FAILED '+repr(error))
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()


handle = unreal.register_slate_post_tick_callback(tick)
