"""Actual Unreal reference-pose collider fit screenshots; saves no game assets.

Launch only in a coordinated GPU window with -ExecutePythonScript,
-RenderOffscreen, -ForceRes, and a unique temporary -GameUserSettingsINI.
The cyan overlay comes directly from persisted collision shapes and bone
transforms; it is engine debug geometry, not an image edit.
"""
import hashlib
import json
import time
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/oldwest_survivor/physics'
BASE='/Game/Art/Survivors/SurvivorA'
protected=[ROOT/'game/OldWest/Content/Maps/WaterDepotV2.umap',
           ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA/PA_Survivor_Anatomical.uasset']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,2500,40))
component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
component.set_skeletal_mesh_asset(unreal.load_asset(BASE+'/SKM_Survivor_A_Cm'))
component.set_physics_asset(unreal.load_asset(BASE+'/PA_Survivor_Anatomical'),True)
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
component.set_update_animation_in_editor(True)
report=json.loads(unreal.OldWestAssetAuthoring.describe_survivor_physics_asset(
    unreal.load_asset(BASE+'/PA_Survivor_Anatomical')))
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(0,3050,135))
lens=camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length',55)
lens.set_editor_property('current_aperture',8)
lens.set_editor_property('filmback',unreal.CameraFilmbackSettings(sensor_width=36,sensor_height=20.25))
focus=unreal.CameraFocusSettings()
focus.focus_method=unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings',focus)
for cmd in ['r.ScreenPercentage 100','r.Streaming.FullyLoadUsedTextures 1','r.Streaming.PoolSize 8192']:
    unreal.SystemLibrary.execute_console_command(world,cmd)

def position(index):
    camera.set_actor_location(unreal.Vector(*shots[index][1]),False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
        camera.get_actor_location(),unreal.Vector(0,2500,132)),False)

def overlay():
    color=unreal.LinearColor(.08,1,.85,1)
    for body in report['bodies']:
        bone=component.get_socket_transform(body['bone'],unreal.RelativeTransformSpace.RTS_WORLD)
        for kind,shapes in [('capsule',body['capsules']),('box',body['boxes'])]:
            for shape in shapes:
                center=unreal.MathLibrary.transform_location(bone,unreal.Vector(*shape['center_local_cm']))
                roll,pitch,yaw=shape['rotation_local_degrees']
                rotation=unreal.MathLibrary.transform_rotation(bone,unreal.Rotator(pitch,yaw,roll))
                common=dict(rotation=rotation,line_color=color,duration=0,thickness=1.1,
                            depth_priority=unreal.DrawDebugSceneDepthPriorityGroup.FOREGROUND)
                if kind=='capsule':
                    unreal.SystemLibrary.draw_debug_capsule(world,center,
                        shape['cylinder_length_cm']*.5+shape['radius_cm'],shape['radius_cm'],**common)
                else:
                    unreal.SystemLibrary.draw_debug_box(world,center,
                        unreal.Vector(*(n*.5 for n in shape['size_cm'])),**common)
        for shape in body.get('convexes',[]):
            roll,pitch,yaw=shape['rotation_local_degrees']
            local=unreal.Transform(location=unreal.Vector(*shape['center_local_cm']),
                rotation=unreal.Rotator(pitch,yaw,roll))
            vertices=[unreal.MathLibrary.transform_location(bone,
                unreal.MathLibrary.transform_location(local,unreal.Vector(*point)))
                for point in shape['vertices_cm']]
            indices=shape['indices']
            for i in range(0,len(indices),3):
                for edge in range(3):
                    unreal.SystemLibrary.draw_debug_line(world,
                        vertices[indices[i+edge]],vertices[indices[i+(edge+1)%3]],color,
                        duration=0,thickness=1.1,
                        depth_priority=unreal.DrawDebugSceneDepthPriorityGroup.FOREGROUND)

shots=[('reference-front',(0,3050,135)),('reference-side',(550,2500,135)),
       ('reference-three-quarter',(390,2890,135))]
index,requested=0,False
deadline=time.monotonic()+25
captures=[]
position(0)

def tick(delta):
    global index,requested,deadline
    try:
        overlay()
        if time.monotonic()<deadline:return
        path=OUT/(shots[index][0]+'.png')
        if not requested:
            if path.exists():path.unlink()
            unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,str(path),camera=camera,delay=2)
            requested=True
            deadline=time.monotonic()+7
        else:
            assert path.exists() and path.stat().st_size>10000
            captures.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            index+=1
            if index==len(shots):
                assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
                (OUT/'body-fit-captures.json').write_text(json.dumps({
                    'renderer':'Unreal Vulkan','pose':'reference','overlay':'persisted collision geometry',
                    'captures':captures,'protected_sha256':hashes,'human_review_required':True},indent=2)+'\n')
                unreal.unregister_slate_post_tick_callback(handle)
                unreal.log('SURVIVOR_PHYSICS_PREVIEW_COMPLETE')
                unreal.SystemLibrary.quit_editor()
                return
            position(index)
            requested=False
            deadline=time.monotonic()+2
    except Exception as error:
        unreal.log_error('SURVIVOR_PHYSICS_PREVIEW_FAILED '+repr(error))
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()

handle=unreal.register_slate_post_tick_callback(tick)
