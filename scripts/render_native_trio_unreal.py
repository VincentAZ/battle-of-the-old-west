"""Render an isolated 12-second native Unreal animation reel of the approved trio.

Run in Unreal Editor with -EnablePlugins=MovieRenderPipeline. Only the new
NativePreview/Showcase level and sequence are saved; no game map is modified.
"""
import json, time, os
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
PLAYABLE=os.environ.get('OLDWEST_NATIVE_PLAYABLE') == '1'
OUT=ROOT/('art/western/native/playable-v001/trio-review' if PLAYABLE else 'art/western/native/trio-animation-v001')
OUT.mkdir(parents=True, exist_ok=True)
DEST='/Game/Art/Western/NativePreview/' + ('ShowcasePlayableV001' if PLAYABLE else 'ShowcaseV002')
FPS=24
END=288
LIB=unreal.EditorAssetLibrary
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if LIB.does_asset_exist(DEST+'/NativeTrioStage'):
    assert levels.load_level(DEST+'/NativeTrioStage')
else:
    assert levels.new_level_from_template(DEST+'/NativeTrioStage','/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode',unreal.GameModeBase)
for actor in actors.get_all_level_actors():
    if isinstance(actor,unreal.LevelSequenceActor) or actor.get_actor_label() in [
        'Animation review floor','Quanah Parker','Lozen','Sarah Winnemucca',
        'Native trio review camera','Native trio review light']:
        actors.destroy_actor(actor)
for cmd in ['r.ScreenPercentage 100','r.Streaming.FullyLoadUsedTextures 1','r.Streaming.PoolSize 4096','r.MotionBlurQuality 0']:
    unreal.SystemLibrary.execute_console_command(world,cmd)
origin=unreal.Vector(0,2500,150)
floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,origin)
floor.set_actor_label('Animation review floor')
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(200,200,1))
sequence_path=DEST+'/LS_NativeTrio'
if LIB.does_asset_exist(sequence_path):assert LIB.delete_asset(sequence_path)
seq=unreal.AssetToolsHelpers.get_asset_tools().create_asset('LS_NativeTrio',DEST,unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(FPS,1))
seq.set_playback_start(0);seq.set_playback_end(END)
specs=[('Quanah Parker','Quanah','/Game/Art/Western/Quanah',-225),
       ('Lozen','Lozen','/Game/Art/Western/Lozen' if PLAYABLE else '/Game/Art/Western/NativePreview/Lozen',0),
       ('Sarah Winnemucca','Sarah','/Game/Art/Western/Sarah' if PLAYABLE else '/Game/Art/Western/NativePreview/Sarah',225)]
audit=[]
for display,name,directory,x in specs:
    actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(x,2500,150))
    actor.set_actor_label(display)
    component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh=LIB.load_asset(directory+'/SK_'+name);assert mesh
    component.set_skeletal_mesh_asset(mesh)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_update_animation_in_editor(True)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    binding=seq.add_possessable(actor)
    track=binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    clips=[]
    for begin,end,clip in [(0,72,'MM_Idle'),(72,216,'MF_Unarmed_Walk_Fwd'),(216,288,'MM_Idle')]:
        anim=LIB.load_asset(directory+'/Animations/RA_'+clip);assert anim
        section=track.add_section();section.set_range(begin,end)
        params=unreal.MovieSceneSkeletalAnimationParams()
        params.set_editor_property('animation',anim)
        params.set_editor_property('force_custom_mode',True)
        section.set_editor_property('params',params)
        clips.append(dict(start=begin,end=end,asset=anim.get_path_name()))
    audit.append(dict(name=display,mesh=mesh.get_path_name(),clips=clips))
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(0,3570,340))
camera.set_actor_label('Native trio review camera')
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),unreal.Vector(0,2500,238)),False)
lens=camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length',55)
lens.set_editor_property('current_aperture',8)
lens.set_editor_property('filmback',unreal.CameraFilmbackSettings(sensor_width=36,sensor_height=20.25))
focus=unreal.CameraFocusSettings();focus.focus_method=unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings',focus)
binding=seq.add_possessable(camera)
cut=seq.add_track(unreal.MovieSceneCameraCutTrack).add_section()
cut.set_range(0,END);cut.set_camera_binding_id(seq.get_binding_id(binding))
light=actors.spawn_actor_from_class(unreal.RectLight,unreal.Vector(-100,3100,700))
light.set_actor_label('Native trio review light')
light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(light.get_actor_location(),unreal.Vector(0,2500,240)),False)
lc=light.get_component_by_class(unreal.RectLightComponent);lc.set_intensity(11000)
lc.set_editor_property('source_width',800);lc.set_editor_property('source_height',400)
assert LIB.save_loaded_asset(seq)
assert levels.save_current_level()
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
subsystem=unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue=subsystem.get_queue();queue.delete_all_jobs()
job=queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
job.job_name='Native Trio Animation'
job.sequence=unreal.SoftObjectPath(seq.get_path_name())
job.map=unreal.SoftObjectPath(DEST+'/NativeTrioStage.NativeTrioStage')
config=job.get_configuration()
output=config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
output.output_directory=unreal.DirectoryPath(str(OUT/'frames'))
output.file_name_format='Trio.{frame_number}'
output.output_resolution=unreal.IntPoint(1920,1080)
output.use_custom_frame_rate=True;output.output_frame_rate=unreal.FrameRate(FPS,1)
output.zero_pad_frame_numbers=4
output.override_existing_output=True
config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
aa=config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa.spatial_sample_count=1;aa.temporal_sample_count=1
aa.engine_warm_up_count=48;aa.render_warm_up_count=16
aa.override_anti_aliasing=True;aa.anti_aliasing_method=unreal.AntiAliasingMethod.AAM_FXAA
game=config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
game.game_mode_override=unreal.MoviePipelineGameMode
console=config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
for key,value in {'r.ScreenPercentage':100.,'r.MotionBlurQuality':0.,'r.Streaming.FullyLoadUsedTextures':1.}.items():
    assert console.add_or_update_console_variable(key,value)
report=dict(ok=False,renderer='Unreal Movie Render Queue / Vulkan',fps=FPS,frames=END,seconds=END/FPS,characters=audit,map=DEST+'/NativeTrioStage',sequence=seq.get_path_name(),errors=[])
(OUT/'render.json').write_text(json.dumps(report,indent=2)+'\n')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
executor=unreal.MoviePipelinePIEExecutor(subsystem)
def finished(executor,success):
    report['ok']=bool(success)
    report['written_frames']=len(list((OUT/'frames').glob('Trio.*.png')))
    (OUT/'render.json').write_text(json.dumps(report,indent=2)+'\n')
    unreal.SystemLibrary.quit_editor()
def error(executor,pipeline,fatal,message):
    report['errors'].append(dict(fatal=bool(fatal),message=str(message)))
executor.on_executor_finished_delegate.add_callable_unique(finished)
executor.on_executor_errored_delegate.add_callable_unique(error)
subsystem.render_queue_with_executor_instance(executor)
