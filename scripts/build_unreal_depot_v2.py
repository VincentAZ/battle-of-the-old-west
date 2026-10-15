"""Import the textured depot as a separate Unreal map and author its reveal."""
import unreal
import json
import math
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art/water_depot_v2'
BASE='/Game/Art/WaterDepotV2'
MAP='/Game/Maps/WaterDepotV2'
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
lib=unreal.EditorAssetLibrary
at=unreal.AssetToolsHelpers.get_asset_tools()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
edit=unreal.MaterialEditingLibrary
assert not lib.does_asset_exist(MAP), 'Preserve an existing authored map.'
assert levels.new_level(MAP)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

def command(value):unreal.SystemLibrary.execute_console_command(world,value)
for c in ['Interchange.FeatureFlags.Import.FBX 0','sg.ViewDistanceQuality 3',
          'sg.ShadowQuality 3','sg.PostProcessQuality 3','sg.TextureQuality 3',
          'sg.EffectsQuality 3','sg.FoliageQuality 3','sg.ShadingQuality 3',
          'r.ScreenPercentage 100','r.Streaming.PoolSize 8192','r.Tonemapper.Sharpen 0.3',
          'r.Editor.Viewport.ScreenPercentageMode.RealTime 0','r.Editor.Viewport.ScreenPercentageMode.NonRealTime 0',
          'r.Editor.Viewport.ScreenPercentage 100','r.Editor.Viewport.OverridePIEScreenPercentage 0',
          'r.Streaming.FullyLoadUsedTextures 1','r.MaxAnisotropy 16']:
    command(c)

textures={}
def import_texture(rel,kind):
    key=(rel,kind)
    if key in textures:return textures[key]
    path=ROOT/rel
    task=unreal.AssetImportTask();task.filename=str(path)
    task.destination_path=BASE+'/Textures';task.destination_name='T_'+path.stem
    task.automated=True;task.save=True
    existing=lib.load_asset(task.destination_path+'/'+task.destination_name) if lib.does_asset_exist(task.destination_path+'/'+task.destination_name) else None
    if existing:loaded=[existing]
    else:
        at.import_asset_tasks([task]);loaded=task.get_objects()
    assert loaded,'Texture import failed: '+rel
    tex=loaded[0]
    if kind=='normal':
        tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property('srgb',False)
    elif kind in ['arm','rough']:
        tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property('srgb',False)
    tex.set_editor_property('lod_bias',0)
    tex.set_editor_property('max_texture_size',4096)
    lib.save_loaded_asset(tex);textures[key]=tex
    return tex

def expr(mat,cls,x=0,y=0):return edit.create_material_expression(mat,cls,x,y)
def scalar(mat,value):
    node=expr(mat,unreal.MaterialExpressionConstant);node.set_editor_property('r',value);return node
def color(mat,rgb):
    node=expr(mat,unreal.MaterialExpressionConstant3Vector);node.set_editor_property('constant',unreal.LinearColor(*rgb,1));return node
def link(node,prop,output=''):edit.connect_material_property(node,output,prop)
materials={}
for name,spec in json.loads((ART/'materials.json').read_text()).items():
    matpath=BASE+'/Materials/M_'+name
    mat=lib.load_asset(matpath) if lib.does_asset_exist(matpath) else at.create_asset('M_'+name,BASE+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    edit.delete_all_material_expressions(mat)
    for kind,rel in spec['textures'].items():
        tex=import_texture(rel,kind)
        sample=expr(mat,unreal.MaterialExpressionTextureSample,-600,100*len(materials))
        sample.set_editor_property('texture',tex)
        sample.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if kind=='normal' else
                                   unreal.MaterialSamplerType.SAMPLERTYPE_MASKS if kind in ['arm','rough'] else
                                   unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if kind=='diff':
            mult=expr(mat,unreal.MaterialExpressionMultiply)
            tint=color(mat,spec['tint'])
            edit.connect_material_expressions(sample,'RGB',mult,'A');edit.connect_material_expressions(tint,'',mult,'B')
            link(mult,unreal.MaterialProperty.MP_BASE_COLOR)
        elif kind=='normal':link(sample,unreal.MaterialProperty.MP_NORMAL,'RGB')
        elif kind=='arm':
            link(sample,unreal.MaterialProperty.MP_ROUGHNESS,'G')
            link(sample,unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,'R')
        elif kind=='rough':link(sample,unreal.MaterialProperty.MP_ROUGHNESS,'R')
    if not spec['textures']:
        link(color(mat,spec['color']),unreal.MaterialProperty.MP_BASE_COLOR)
    if not any(k in spec['textures'] for k in ['arm','rough']):
        link(scalar(mat,spec['roughness']),unreal.MaterialProperty.MP_ROUGHNESS)
    link(scalar(mat,spec['metallic']),unreal.MaterialProperty.MP_METALLIC)
    if spec['emission']:
        link(color(mat,[v*spec['emission']*150 for v in spec['color']]),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name=='DustyCanvas':mat.set_editor_property('two_sided',True)
    edit.recompile_material(mat);lib.save_loaded_asset(mat);materials[name]=mat
print('DEPOT_MATERIALS_READY',len(materials),len(textures))

geometry=json.loads((ART/'geometry.json').read_text())
meshes={}
for name in geometry['meshes']:
    opts=unreal.FbxImportUI();opts.import_mesh=True;opts.import_as_skeletal=False
    opts.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.import_materials=False;opts.import_textures=False;opts.import_animations=False
    opts.automated_import_should_detect_type=False
    opts.static_mesh_import_data.combine_meshes=True
    opts.static_mesh_import_data.auto_generate_collision=False
    opts.static_mesh_import_data.generate_lightmap_u_vs=False
    task=unreal.AssetImportTask();task.filename=str(ART/(name+'.fbx'))
    task.destination_path=BASE+'/Meshes';task.destination_name='SM_'+name
    task.automated=True;task.save=True;task.replace_existing=True;task.options=opts;task.factory=unreal.FbxFactory()
    at.import_asset_tasks([task])
    found=[o for o in task.get_objects() if isinstance(o,unreal.StaticMesh)]
    assert len(found)==1,name
    mesh=found[0]
    for idx,slot in enumerate(mesh.get_editor_property('static_materials')):
        matname=str(slot.get_editor_property('material_slot_name'))
        assert matname in materials,matname
        mesh.set_material(idx,materials[matname])
    mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    lib.save_loaded_asset(mesh);meshes[name]=mesh
    print('DEPOT_MESH_READY',name)

def pos(xyz):return unreal.Vector(xyz[0]*100,-xyz[1]*100,xyz[2]*100)
def spawn(cls,label,loc=None,rot=None):
    actor=actors.spawn_actor_from_class(cls,loc or unreal.Vector(),rot or unreal.Rotator())
    actor.set_actor_label(label);return actor
for name in ['Depot','Props','Terrain','Scrub','Gravel']:
    actor=spawn(unreal.StaticMeshActor,'Water depot — '+name);actor.static_mesh_component.set_static_mesh(meshes[name])
for i,inst in enumerate(geometry['instances']):
    # Blender XYZ Euler to UE pitch/yaw/roll after the handedness conversion.
    rx,ry,rz=inst['rotation']
    rot=unreal.Rotator(pitch=-math.degrees(ry),yaw=-math.degrees(rz),roll=math.degrees(rx))
    actor=spawn(unreal.StaticMeshActor,inst['asset']+' '+str(i),pos(inst['location']),rot)
    actor.static_mesh_component.set_static_mesh(meshes[inst['asset']])
    actor.set_actor_scale3d(unreal.Vector(*inst['scale']))

sun=spawn(unreal.DirectionalLight,'Late afternoon key',pos((-18,-2,8)))
sun.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(sun.get_actor_location(),pos((0,1,0))),False)
lc=sun.get_component_by_class(unreal.DirectionalLightComponent);lc.set_mobility(unreal.ComponentMobility.MOVABLE)
lc.set_intensity(18000);lc.set_light_color(unreal.LinearColor(1,.86,.70,1))
lc.set_editor_property('light_source_angle',1.4);lc.set_editor_property('atmosphere_sun_light',True)
spawn(unreal.SkyAtmosphere,'Atmosphere')
sky=spawn(unreal.SkyLight,'Open sky fill',unreal.Vector(0,0,1000))
sc=sky.get_component_by_class(unreal.SkyLightComponent);sc.set_mobility(unreal.ComponentMobility.MOVABLE)
sc.set_editor_property('real_time_capture',True);sc.set_intensity(2.0)
fog=spawn(unreal.ExponentialHeightFog,'Dust in the distance')
fc=fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fc.set_editor_property('fog_density',.007);fc.set_editor_property('fog_height_falloff',.2)
fill=spawn(unreal.RectLight,'Soft camera-side fill',pos((-3,-9,7)))
fill.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(fill.get_actor_location(),pos((0,1,2))),False)
lc=fill.get_component_by_class(unreal.RectLightComponent);lc.set_mobility(unreal.ComponentMobility.MOVABLE)
lc.set_intensity(450000);lc.set_light_color(unreal.LinearColor(.76,.86,1,1))
lc.set_editor_property('source_width',1000);lc.set_editor_property('source_height',1000);lc.set_editor_property('attenuation_radius',3000)
for x in [2.42,4.12]:
    a=spawn(unreal.PointLight,'Warm service lamp',pos((x,-1,2.68)))
    lc=a.get_component_by_class(unreal.PointLightComponent);lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_intensity(100);lc.set_light_color(unreal.LinearColor(1,.69,.37,1));lc.set_editor_property('attenuation_radius',400)
post=spawn(unreal.PostProcessVolume,'Fixed cinematic exposure');post.set_editor_property('unbound',True)
settings=post.get_editor_property('settings')
for key,value in dict(auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL,
                      auto_exposure_apply_physical_camera_exposure=True,
                      auto_exposure_bias=1.1,camera_shutter_speed=60.,camera_iso=100.,
                      depth_of_field_fstop=8.,bloom_intensity=.18,
                      vignette_intensity=.16).items():
    settings.set_editor_property('override_'+key,True);settings.set_editor_property(key,value)
post.set_editor_property('settings',settings)

cam=spawn(unreal.CineCameraActor,'Depot reveal camera')
cc=cam.get_cine_camera_component();cc.set_editor_property('current_focal_length',43);cc.set_editor_property('current_aperture',8)
focus=cc.get_editor_property('focus_settings');focus.set_editor_property('focus_method',unreal.CameraFocusMethod.DISABLE);cc.set_editor_property('focus_settings',focus)
film=cc.get_editor_property('filmback');film.set_editor_property('sensor_width',36);film.set_editor_property('sensor_height',20.25);cc.set_editor_property('filmback',film)
seq=at.create_asset('LS_WaterDepotV2','/Game/Cinematics',unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(24,1));seq.set_playback_start(0);seq.set_playback_end(192)
binding=seq.add_possessable(cam);section=binding.add_track(unreal.MovieScene3DTransformTrack).add_section();section.set_range(0,192)
channels=section.get_channels_by_type(unreal.MovieSceneScriptingDoubleChannel)
for frame,xyz,target in json.loads((ART/'camera.json').read_text())['shots']:
    loc=pos(xyz);rot=unreal.MathLibrary.find_look_at_rotation(loc,pos(target))
    for ch,v in zip(channels,[loc.x,loc.y,loc.z,rot.roll,rot.pitch,rot.yaw,1,1,1]):ch.add_key(unreal.FrameNumber(frame-1),v)
    if frame==96:
        cam.set_actor_location_and_rotation(loc,rot,False,False)
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(loc,rot)
        spawn(unreal.PlayerStart,'Depot viewpoint',loc,rot)
cut=seq.add_track(unreal.MovieSceneCameraCutTrack).add_section();cut.set_range(0,192);cut.set_camera_binding_id(seq.get_binding_id(binding))
sa=spawn(unreal.LevelSequenceActor,'Play — depot reveal');sa.set_sequence(seq)
play=sa.get_editor_property('playback_settings');play.set_editor_property('auto_play',True);sa.set_editor_property('playback_settings',play)
lib.save_directory('/Game',only_if_is_dirty=True,recursive=True)
assert levels.save_current_level();actors.set_selected_level_actors([])
(ART/'unreal-build.json').write_text(json.dumps(dict(map=MAP,sequence=seq.get_path_name(),
    mesh_count=len(meshes),material_count=len(materials),unique_texture_count=len(textures),
    scanned_rock_instances=len(geometry['instances']),gameplay_implemented=False),indent=2))
print('DEPOT_UNREAL_READY')

started=time.monotonic();phase=0;play_started=0
def verify(delta):
    global phase,play_started
    elapsed=time.monotonic()-started
    try:
        if phase==0 and elapsed>45:
            phase=1
            unreal.AutomationLibrary.take_high_res_screenshot(3840,2160,str(ART/'UnrealDepot_4K.png'),camera=cam,delay=8)
        elif phase==1 and elapsed>65:
            phase=2;levels.editor_request_begin_play()
        elif phase==2 and levels.is_in_play_in_editor():
            phase=3;play_started=time.monotonic()
        elif phase==3 and time.monotonic()-play_started>3:
            game=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            seqs=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.LevelSequenceActor)
            assert seqs and seqs[0].get_editor_property('sequence_player').is_playing()
            cameras=unreal.GameplayStatics.get_all_actors_of_class(game,unreal.CineCameraActor)
            loc=cameras[0].get_actor_location();assert loc.x>-1375,'Camera did not move'
            (ART/'playback-validation.json').write_text(json.dumps(dict(sequence_playing=True,camera_moved=True,position_cm=[loc.x,loc.y,loc.z]),indent=2))
            levels.editor_request_end_play();unreal.unregister_slate_post_tick_callback(handle)
            print('DEPOT_PLAYBACK_VERIFIED')
        elif elapsed>180:raise RuntimeError('Playback validation timed out')
    except Exception as error:
        unreal.log_error('DEPOT_VERIFY_FAILED '+str(error));levels.editor_request_end_play();unreal.unregister_slate_post_tick_callback(handle)
handle=unreal.register_slate_post_tick_callback(verify)
