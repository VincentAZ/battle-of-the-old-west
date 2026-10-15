"""Render actual forced-LOD deformation comparisons in Unreal; save no assets.

Requires saved LODs and their fresh-validation report. Run only in a coordinated
GPU window with -ExecutePythonScript, -RenderOffscreen, -ForceRes and an isolated
temporary -GameUserSettingsINI. Wide pose frames contain LOD0,1,2,3 left to right. Face frames isolate
one forced LOD, and distance frames measure the automatic LOD selection.
"""
import hashlib
import json
import shlex
import time
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/oldwest_survivor/lods'
assert (OUT/'fresh-validation.json').exists(),'Freshly verify generated LODs before visual QA'
BASE='/Game/Art/Survivors/SurvivorA'
protected=[ROOT/'game/OldWest/Content/Maps/WaterDepotV2.umap',
           ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm.uasset']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
mesh=unreal.load_asset(BASE+'/SKM_Survivor_A_Cm')
assert mesh
components=[]
origins=[]
for lod,x in enumerate([-270,-90,90,270]):
    hit=unreal.SystemLibrary.line_trace_single(world,unreal.Vector(x,2500,1000),
        unreal.Vector(x,2500,-1000),unreal.TraceTypeQuery.ECC_VISIBILITY,True,[],
        unreal.DrawDebugTrace.NONE,True)
    if isinstance(hit,tuple):
        hit=next((part for part in hit if isinstance(part,unreal.HitResult)),None)
    assert hit,'Preview requires a terrain hit result'
    # The Python binding exposes the native break function as to_tuple().
    # Its first and sixth outputs are blocking_hit and impact_point.
    fields=hit.to_tuple()
    assert fields[0],'Preview requires traced terrain contact'
    ground=fields[5]
    origins.append(unreal.Vector(x,2500,ground.z+.3))
    actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,origins[-1])
    component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(mesh)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_update_animation_in_editor(True)
    component.set_forced_lod(lod+1)
    components.append(component)
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(0,3500,145))
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
    camera.get_actor_location(),unreal.Vector(0,2500,135)),False)
lens=camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length',45)
lens.set_editor_property('current_aperture',8)
lens.set_editor_property('filmback',unreal.CameraFilmbackSettings(sensor_width=36,sensor_height=20.25))
focus=unreal.CameraFocusSettings()
focus.focus_method=unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings',focus)
for cmd in ['r.ScreenPercentage 100','r.Streaming.FullyLoadUsedTextures 1','r.Streaming.PoolSize 8192']:
    unreal.SystemLibrary.execute_console_command(world,cmd)
clips=[{'name':name,'clip':clip,'seconds':seconds,'mode':'wide'} for name,clip,seconds in [
    ('rifle-idle','RA_MF_Rifle_Idle_ADS',2.0),('rifle-fire','RA_MM_Rifle_Fire',.18),
    ('hit','RA_MM_HitReact_Front_Lgt_01',.20),('walk','RA_MF_Rifle_Walk_Fwd',.45)]]
clips += [{'name':f'face-{expression}-lod{lod}','clip':'RA_MM_Idle','seconds':2.0,
           'mode':'face','lod':lod,'expression':expression=='expression'}
          for expression in ['neutral','expression'] for lod in range(4)]
clips += [{'name':f'auto-{meters}m','clip':'RA_MF_Rifle_Idle_ADS','seconds':2.0,
           'mode':'auto','distance_cm':meters*100} for meters in [6,9,15,30,45]]
selected=next((arg.split('=',1)[1] for arg in shlex.split(unreal.SystemLibrary.get_command_line())
               if arg.startswith('-SurvivorLODPreviewShot=')),None)
if selected:
    clips=[shot for shot in clips if shot['name']==selected]
    assert len(clips)==1,'Unknown requested LOD preview shot'
def progress(phase,shot):
    (OUT/'preview-progress.json').write_text(json.dumps({'phase':phase,'shot':shot,'time':time.time()},indent=2)+'\n')
    unreal.log('SURVIVOR_LOD_PROGRESS '+phase+' '+shot['name'])
morphs=[str(name) for name in mesh.get_all_morph_target_names()]
expression_names={suffix:next((name for name in morphs if name.endswith(suffix)),None)
                  for suffix in ['Eyes_Closed_Max','Jaw_Lower','Eyebrows_Frown_Left','Eyebrows_Frown_Right']}
assert all(expression_names.values()),expression_names

def pose(index):
    shot=clips[index]
    progress('prepare_pose',shot)
    animation=unreal.load_asset(BASE+'/Animations/'+shot['clip'])
    assert animation
    for lod,component in enumerate(components):
        progress('pose_component_'+str(lod),shot)
        component.clear_morph_targets()
        component.set_animation(animation)
        component.set_position(shot['seconds'],False)
        component.stop()
        component.set_forced_lod(lod+1 if shot['mode']!='auto' else 0)
        component.set_visibility(shot['mode']!='auto' or lod==0,False)
        if shot.get('expression'):
            for suffix,morph in expression_names.items():
                component.set_morph_target(morph,.9 if suffix=='Eyes_Closed_Max' else .55,False)
    if shot['mode']=='wide':
        z=sum(o.z for o in origins)/len(origins)
        location,target,focal=unreal.Vector(0,3500,z+105),unreal.Vector(0,2500,z+95),45
    elif shot['mode']=='face':
        x=[-270,-90,90,270][shot['lod']]
        z=origins[shot['lod']].z
        location,target,focal=unreal.Vector(x,2700,z+165),unreal.Vector(x,2500,z+163),55
    else:
        z=origins[0].z
        location,target,focal=unreal.Vector(-270,2500+shot['distance_cm'],z+160),unreal.Vector(-270,2500,z+95),32
    camera.set_actor_location(location,False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location,target),False)
    lens.set_editor_property('current_focal_length',focal)
    progress('pose_ready',shot)

index,requested=0,False
screenshot_task=None
shot_deadline=0.0
deadline=time.monotonic()+30
captures=[]
pose(0)

def tick(delta):
    global index,requested,deadline,screenshot_task,shot_deadline
    if time.monotonic()<deadline:return
    try:
        shot=clips[index]
        name=shot['name']
        path=OUT/(name+'-lod-comparison.png')
        if not requested:
            progress('request_capture',shot)
            if path.exists():path.unlink()
            screenshot_task=unreal.AutomationLibrary.take_high_res_screenshot(2560,1440,str(path),camera=camera,delay=2)
            assert screenshot_task and screenshot_task.is_valid_task()
            shot_deadline=time.monotonic()+90
            requested=True
            deadline=time.monotonic()+8
        else:
            progress('check_capture',shot)
            if not screenshot_task.is_task_done():
                assert time.monotonic()<shot_deadline,'Screenshot task timed out'
                deadline=time.monotonic()+2
                return
            assert path.exists() and path.stat().st_size>10000
            progress('record_capture',shot)
            bones=['Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot']
            joint_positions=[]
            for component,origin in zip(components,origins):
                local={}
                for bone in bones:
                    location=component.get_socket_location(bone)
                    local[bone]=[location.x-origin.x,location.y-origin.y,location.z-origin.z]
                joint_positions.append(local)
            captures.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'shot':shot,'left_to_right_lods':[0,1,2,3] if shot['mode']=='wide' else None,
                             'predicted_lods':[c.get_predicted_lod_level() for c in components],
                             'animation_positions':[c.get_position() for c in components],
                             'animation_playing':[c.is_playing() for c in components],
                             'joint_positions_relative_to_ground_cm':joint_positions,
                             'forced_lod_settings':[c.get_forced_lod() for c in components]})
            index+=1
            if index==len(clips):
                assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
                report_name='deformation-captures'+('-'+selected if selected else '')+'.json'
                (OUT/report_name).write_text(json.dumps({
                    'renderer':'Unreal Vulkan','captures':captures,'expression_morph_names':expression_names,
                    'protected_sha256':hashes,'human_review_required':True,
                    'actual_gameplay_camera_transition_validation_required':True,
                    'distance_tests_use_32mm_horizontal_view':True,
                    'origins_cm':[[o.x,o.y,o.z] for o in origins]},indent=2)+'\n')
                unreal.unregister_slate_post_tick_callback(handle)
                unreal.log('SURVIVOR_LOD_PREVIEW_COMPLETE')
                unreal.SystemLibrary.quit_editor()
                return
            pose(index)
            requested=False
            deadline=time.monotonic()+3
    except Exception as error:
        (OUT/'deformation-capture-failure.json').write_text(json.dumps({'error':repr(error),'shot':clips[index]},indent=2)+'\n')
        unreal.log_error('SURVIVOR_LOD_PREVIEW_FAILED '+repr(error))
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle=unreal.register_slate_post_tick_callback(tick)
