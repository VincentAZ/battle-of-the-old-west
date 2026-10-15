"""Capture Quanah poses in Unreal; transient stage, no map saves."""
import hashlib,json,time,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/native/quanah-game-v001'
DEST='/Game/Art/Western/Quanah'
# The separate editor process reads the saved packages before any rendering.
import os,runpy
os.environ['OLDWEST_QUANAH_VERIFY_ONLY']='1'
runpy.run_path(str(ROOT/'scripts/import_quanah_unreal.py'),run_name='__main__')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for cmd in ['r.ScreenPercentage 100','r.Streaming.FullyLoadUsedTextures 1','r.Streaming.PoolSize 4096','r.MotionBlurQuality 0']:
    unreal.SystemLibrary.execute_console_command(world,cmd)
# A temporary flat review floor permits honest hoof contact inspection.
origin=unreal.Vector(0,2500,150)
floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,origin)
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(200,200,1))
actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,origin)
component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
mesh=unreal.load_asset(DEST+'/SK_Quanah');assert mesh
component.set_skeletal_mesh_asset(mesh)
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
component.set_update_animation_in_editor(True)
component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(-650,3300,450))
lens=camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length',55)
lens.set_editor_property('current_aperture',8)
lens.set_editor_property('filmback',unreal.CameraFilmbackSettings(sensor_width=36,sensor_height=20.25))
focus=unreal.CameraFocusSettings();focus.focus_method=unreal.CameraFocusMethod.DISABLE;lens.set_editor_property('focus_settings',focus)
# Fill light is a temporary native scene light, not a material substitution.
light=actors.spawn_actor_from_class(unreal.RectLight,unreal.Vector(-350,3100,650))
light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(light.get_actor_location(),unreal.Vector(0,2500,260)),False)
lc=light.get_component_by_class(unreal.RectLightComponent)
lc.set_intensity(8000);lc.set_editor_property('source_width',400);lc.set_editor_property('source_height',400)
shots=[
 ('idle-quarter-1080','MM_Idle',1,0,(-240,3100,300),1920,1080),
 ('walk-quarter-1080','MF_Unarmed_Walk_Fwd',.375,0,(-240,3100,300),1920,1080),
 ('walk-side-1080','MF_Unarmed_Walk_Fwd',.75,0,(-650,2500,300),1920,1080),
 ('attack-quarter-1080','MM_Attack_01',.35,0,(-240,3100,300),1920,1080),
 ('hit-quarter-1080','MM_HitReact_Front_Lgt_01',.2,0,(-240,3100,300),1920,1080),
]
sequence=None
previews=OUT/'previews';previews.mkdir(exist_ok=True)
def pose(index):
    name,clip,seconds,yaw,location,w,h=shots[index]
    actor.set_actor_rotation(unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
    camera.set_actor_location(unreal.Vector(*location),False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),unreal.Vector(0,2500,250)),False)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
    anim=unreal.load_asset(DEST+'/Animations/RA_'+clip);assert anim
    component.set_animation(anim);component.set_position(seconds,False);component.stop()
    unreal.log('QUANAH_NATIVE_POSE '+name+' '+str(actor.get_actor_rotation()))
pose(0)
index=0;requested=False;deadline=time.monotonic()+30
report={'ok':False,'renderer':'Unreal Vulkan','scope':'Quanah animation study on a temporary flat review floor; gameplay tested separately','captures':[]}
def tick(delta):
    global index,requested,deadline
    if time.monotonic()<deadline:return
    try:
        name,clip,seconds,yaw,location,w,h=shots[index];path=previews/('Unreal-'+name+'.png')
        if not requested:
            if path.exists():path.unlink()
            unreal.AutomationLibrary.take_high_res_screenshot(w,h,str(path),camera=camera,delay=.2 if sequence else 2)
            requested=True;deadline=time.monotonic()+(2 if sequence else 8)
        else:
            assert path.exists(),path
            report['captures'].append({'file':str(path.relative_to(OUT)),'clip':clip,'seconds':seconds,'heading_yaw':yaw,'size':[w,h],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            index+=1
            if index==len(shots):
                report['ok']=True
                (OUT/('unreal-run-frames.json' if sequence else 'unreal-captures.json')).write_text(json.dumps(report,indent=2)+'\n')
                unreal.unregister_slate_post_tick_callback(handle);unreal.SystemLibrary.quit_editor();return
            pose(index);requested=False;deadline=time.monotonic()+(1 if sequence else 3)
    except Exception as exc:
        report['error']=repr(exc);report['traceback']=traceback.format_exc()
        (OUT/('unreal-run-frames.json' if sequence else 'unreal-captures.json')).write_text(json.dumps(report,indent=2)+'\n')
        unreal.log_error('QUANAH_CAPTURE_FAILED '+repr(exc))
        unreal.unregister_slate_post_tick_callback(handle);unreal.SystemLibrary.quit_editor()
handle=unreal.register_slate_post_tick_callback(tick)
