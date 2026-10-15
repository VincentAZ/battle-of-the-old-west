"""Transient native wagon/draft-ox review; no map or gameplay changes."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import time
import traceback
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/delivery/native-study-v002'
OUT.mkdir(parents=True,exist_ok=True)
os.environ['OLDWEST_DELIVERY_OXEN_VERIFY_ONLY']='1'
runpy.run_path(str(ROOT/'scripts/import_delivery_oxen.py'),run_name='__main__')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for cmd in ['r.ScreenPercentage 100','r.Streaming.FullyLoadUsedTextures 1','r.Streaming.PoolSize 4096','r.MotionBlurQuality 0']:
    unreal.SystemLibrary.execute_console_command(world,cmd)
origin=unreal.Vector(0,2500,150)
floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,origin)
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(200,200,1))
ox=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,origin)
component=ox.get_component_by_class(unreal.SkeletalMeshComponent)
dest='/Game/Art/ActionProps/Delivery'
component.set_skeletal_mesh_asset(unreal.load_asset(dest+'/Oxen/SK_DraftOx'))
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
component.set_update_animation_in_editor(True)
component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
parts=[]
manifest=json.loads((ROOT/'art/western/delivery/wagon-v003/manifest.json').read_text())
for record in manifest['assets']:
    xyz=record['placement_m']
    actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,origin+unreal.Vector(xyz[0]*100,-xyz[1]*100,xyz[2]*100))
    actor.static_mesh_component.set_static_mesh(unreal.load_asset(dest+'/Meshes/'+record['name']))
    actor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    parts.append(actor)
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,origin+unreal.Vector(-650,800,300))
lens=camera.get_cine_camera_component();lens.set_editor_property('current_focal_length',55)
lens.set_editor_property('current_aperture',8)
lens.set_editor_property('filmback',unreal.CameraFilmbackSettings(sensor_width=36,sensor_height=20.25))
focus=unreal.CameraFocusSettings();focus.focus_method=unreal.CameraFocusMethod.DISABLE;lens.set_editor_property('focus_settings',focus)
light=actors.spawn_actor_from_class(unreal.RectLight,origin+unreal.Vector(-350,600,500))
light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(light.get_actor_location(),origin+unreal.Vector(0,0,120)),False)
lc=light.get_component_by_class(unreal.RectLightComponent);lc.set_intensity(8000)
lc.set_editor_property('source_width',400);lc.set_editor_property('source_height',400)
shots=[('wagon-front','wagon',0,(-1100,1500,600),(0,90,130)),
       ('wagon-rear','wagon',0,(-1100,-1500,600),(0,90,130)),
       ('wagon-side','wagon',0,(-1700,90,390),(0,90,130)),
       ('ox-front','Idle',0,(0,850,250),(0,0,100)),
       ('ox-quarter','Idle',0,(-650,800,300),(0,0,100))]
shots += [('ox-walk-%02d'%f,'Walk',f/30,(-950,0,190),(0,0,100)) for f in [0,9,18,27]]
index=0;requested=False;finishing=False;deadline=time.monotonic()+30
report={'ok':False,'scope':'Separate source assets in a transient native studio; no team/hitch or gameplay delivery yet','captures':[]}


def pose(i):
    name,clip,seconds,position,target=shots[i];wagon=clip=='wagon'
    ox.set_actor_hidden_in_game(wagon);ox.set_is_temporarily_hidden_in_editor(wagon)
    for part in parts:
        part.set_actor_hidden_in_game(not wagon);part.set_is_temporarily_hidden_in_editor(not wagon)
    if not wagon:
        component.set_animation(unreal.load_asset(dest+'/Oxen/Animations/A_DraftOx_'+clip))
        component.set_position(seconds,False);component.stop()
    camera.set_actor_location(origin+unreal.Vector(*position),False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),origin+unreal.Vector(*target)),False)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())


pose(0)


def tick(delta):
    global index,requested,finishing,deadline
    if time.monotonic()<deadline:return
    if finishing:
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor();return
    try:
        name,clip,seconds,position,target=shots[index];path=OUT/(name+'.png')
        if not requested:
            assert not path.exists(),path
            unreal.AutomationLibrary.take_high_res_screenshot(1600,900,str(path),camera=camera,delay=.5)
            requested=True;deadline=time.monotonic()+5
        else:
            assert path.exists(),path
            report['captures'].append(dict(file=path.name,clip=clip,seconds=seconds,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            index+=1
            if index==len(shots):
                report['ok']=True
                (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                # Release transient render/animation objects before editor
                # teardown, after the final screenshot has completed.
                component.stop();component.set_animation(None)
                component.set_skeletal_mesh_asset(None)
                for actor in parts+[ox,floor,light,camera]:actors.destroy_actor(actor)
                finishing=True;deadline=time.monotonic()+4;return
            pose(index);requested=False;deadline=time.monotonic()+2
    except Exception as exc:
        report.update(error=repr(exc),traceback=traceback.format_exc())
        (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        unreal.log_error('DELIVERY_ASSET_CAPTURE_FAILED '+repr(exc))
        unreal.unregister_slate_post_tick_callback(handle);unreal.SystemLibrary.quit_editor()


handle=unreal.register_slate_post_tick_callback(tick)
