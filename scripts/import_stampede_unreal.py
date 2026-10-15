"""Stage B only: import/read back longhorn study assets, preserving existing Content.

Set OLDWEST_STAMPEDE_VERIFY_ONLY=1 for a separate fresh-process audit.
No gameplay actors, maps, cooking lists or launcher packages are changed.
"""
import hashlib,json,math,os,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/stampede/animation-v001'
CONTENT=ROOT/'game/OldWest/Content'
DEST='/Game/Art/Western/StampedeStudy'
DISK=CONTENT/'Art/Western/StampedeStudy'
VERIFY=os.environ.get('OLDWEST_STAMPEDE_VERIFY_ONLY')=='1'
LIB=unreal.EditorAssetLibrary;MAT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():return {str(p.relative_to(CONTENT)):sha(p) for p in sorted(CONTENT.rglob('*')) if p.is_file() and not p.is_relative_to(DISK)}
def properties(obj,values):
    for k,v in values.items():obj.set_editor_property(k,v)
def coordinates(data):
    properties(data,dict(import_translation=unreal.Vector(0,0,0),import_rotation=unreal.Rotator(0,0,0),import_uniform_scale=1.,convert_scene=True,force_front_x_axis=False,convert_scene_unit=True))
def load(path,cls):
    obj=LIB.load_asset(path);assert isinstance(obj,cls),(path,cls,obj)
    return obj
def imp(name,dest,options=None):
    task=unreal.AssetImportTask()
    properties(task,dict(filename=str(OUT/'exports'/name),destination_path=dest,destination_name=Path(name).stem,automated=True,replace_existing=True,save=False))
    if options:properties(task,dict(options=options,factory=unreal.FbxFactory()))
    TOOLS.import_asset_tasks([task]);return list(task.get_objects())
def save(obj):assert LIB.save_loaded_asset(obj,only_if_is_dirty=False),obj
report={'ok':False,'mode':'fresh_readback' if VERIFY else 'import','destination':DEST,'animations':{}}
before=snapshot()
try:
    expected=json.loads((OUT/'expected-native-poses.json').read_text())
    exports=json.loads((OUT/'export-settings.json').read_text())
    assert sha(OUT/'Longhorn-Animated.blend')==expected['source_sha256']==exports['source_project_sha256']
    for f,h in exports['files'].items():assert sha(OUT/'exports'/f)==h
    if not VERIFY:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
        textures={}
        for channel in ['BaseColor','ORM','Normal']:
            t=next(o for o in imp('T_Longhorn_'+channel+'.png',DEST+'/Textures') if isinstance(o,unreal.Texture2D))
            t.set_editor_property('srgb',channel=='BaseColor')
            if channel=='Normal':properties(t,dict(compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP,flip_green_channel=True))
            elif channel=='ORM':t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
            save(t);textures[channel]=t
        path=DEST+'/M_Longhorn'
        mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('M_Longhorn',DEST,unreal.Material,unreal.MaterialFactoryNew())
        MAT.delete_all_material_expressions(mat)
        properties(mat,dict(shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
        nodes={}
        for i,(channel,t) in enumerate(textures.items()):
            node=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-800,i*250)
            node.set_editor_property('texture',t)
            if channel!='BaseColor':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if channel=='Normal' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            nodes[channel]=node
        for channel,socket,prop in [('BaseColor','RGB',unreal.MaterialProperty.MP_BASE_COLOR),('ORM','R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),('ORM','G',unreal.MaterialProperty.MP_ROUGHNESS)]:
            assert MAT.connect_material_property(nodes[channel],socket,prop)
        strength=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-600,800)
        strength.set_editor_property('constant',unreal.LinearColor(.3,.3,1,1))
        multiply=MAT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-350,600)
        normal=MAT.create_material_expression(mat,unreal.MaterialExpressionNormalize,-100,600)
        assert MAT.connect_material_expressions(nodes['Normal'],'RGB',multiply,'A')
        assert MAT.connect_material_expressions(strength,'',multiply,'B')
        assert MAT.connect_material_expressions(multiply,'',normal,'VectorInput')
        assert MAT.connect_material_property(normal,'',unreal.MaterialProperty.MP_NORMAL)
        metal=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant,-200,800);metal.set_editor_property('r',0)
        assert MAT.connect_material_property(metal,'',unreal.MaterialProperty.MP_METALLIC)
        MAT.set_base_material_usage(mat,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,True)
        MAT.recompile_material(mat);save(mat)
        opt=unreal.FbxImportUI()
        properties(opt,dict(import_mesh=True,import_as_skeletal=True,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False,create_physics_asset=False))
        coordinates(opt.skeletal_mesh_import_data)
        properties(opt.skeletal_mesh_import_data,dict(update_skeleton_reference_pose=False,use_t0_as_ref_pose=False,preserve_smoothing_groups=True,normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS))
        mesh=next(o for o in imp('SK_Longhorn.fbx',DEST,opt) if isinstance(o,unreal.SkeletalMesh))
        skeleton=mesh.get_editor_property('skeleton');assert skeleton
        mesh.modify();slots=mesh.get_editor_property('materials');assert len(slots)==1
        slot=slots[0];slot.set_editor_property('material_interface',mat);slots[0]=slot;mesh.set_editor_property('materials',slots)
        save(mesh);save(skeleton)
        for clip in ['Idle','Run']:
            opt=unreal.FbxImportUI()
            properties(opt,dict(import_mesh=False,import_as_skeletal=True,import_animations=True,import_materials=False,import_textures=False,skeleton=skeleton,mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION,automated_import_should_detect_type=False))
            coordinates(opt.anim_sequence_import_data)
            properties(opt.anim_sequence_import_data,dict(animation_length=unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME,use_default_sample_rate=True,import_bone_tracks=True,import_custom_attribute=False,add_curve_metadata_to_skeleton=False,preserve_local_transform=True))
            anim=next(o for o in imp('A_Longhorn_'+clip+'.fbx',DEST+'/Animations',opt) if isinstance(o,unreal.AnimSequence))
            anim.set_editor_property('enable_root_motion',False);save(anim)
    mesh=load(DEST+'/SK_Longhorn',unreal.SkeletalMesh)
    skeleton=mesh.get_editor_property('skeleton');assert skeleton
    mat=load(DEST+'/M_Longhorn',unreal.Material)
    assert mesh.get_editor_property('materials')[0].get_editor_property('material_interface')==mat
    assert mesh.get_editor_property('physics_asset') is None
    assert MAT.has_material_usage(mat,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    report['textures']={}
    for channel in ['BaseColor','ORM','Normal']:
        tex=load(DEST+'/Textures/T_Longhorn_'+channel,unreal.Texture2D)
        # A freshly loaded texture reports the 32px placeholder while compiling.
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncTextureCompilationFinishAll')
        size=[tex.blueprint_get_size_x(),tex.blueprint_get_size_y()];assert size==[2048,2048],size
        assert tex.get_editor_property('srgb')==(channel=='BaseColor')
        if channel=='Normal':assert tex.get_editor_property('flip_green_channel')
        report['textures'][channel]={'size':size,'asset':tex.get_path_name()}
    for clip,rows in expected['clips'].items():
        anim=load(DEST+'/Animations/A_Longhorn_'+clip,unreal.AnimSequence)
        assert anim.get_editor_property('skeleton')==skeleton
        assert not anim.get_editor_property('enable_root_motion')
        length=anim.get_play_length();assert abs(length-rows[-1]['seconds'])<.001,(clip,length)
        opts=unreal.AnimPoseEvaluationOptions();opts.set_editor_property('optional_skeletal_mesh',mesh)
        max_position=max_rotation=max_scale=0.;root_positions=[];ends=[]
        for row in rows:
            pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,row['seconds'],opts)
            assert unreal.AnimPoseExtensions.is_valid(pose)
            names=[str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)]
            assert set(names)==set(expected['bones']),names
            transforms={}
            for name,e in row['bones'].items():
                t=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)
                p,q,s=t.translation,t.rotation,t.scale3d
                pos=[p.x,p.y,p.z];quat=[q.x,q.y,q.z,q.w];scale=[s.x,s.y,s.z]
                err=math.dist(pos,e['position'])
                cosine=min(1,abs(sum(a*b for a,b in zip(quat,e['quaternion'])))/math.sqrt(sum(a*a for a in quat)*sum(a*a for a in e['quaternion'])))
                angle=math.degrees(2*math.acos(cosine));sc=max(abs(a-b) for a,b in zip(scale,e['scale']))
                assert err<.2 and angle<.5 and sc<.001,(clip,row['frame'],name,err,angle,sc)
                max_position=max(max_position,err);max_rotation=max(max_rotation,angle);max_scale=max(max_scale,sc)
                transforms[name]=pos
            root_positions.append(transforms['Root'])
            if row is rows[0] or row is rows[-1]:ends.append(transforms)
        drift=max(math.dist(p,root_positions[0]) for p in root_positions)
        loop_error=max(math.dist(ends[0][name],ends[1][name]) for name in ends[0])
        assert drift<.001 and loop_error<.02,(drift,loop_error)
        report['animations'][clip]={'duration_seconds':length,'frames_checked':len(rows),'bones_checked':len(names),'maximum_position_error_cm':max_position,'maximum_angle_error_deg':max_rotation,'maximum_scale_error':max_scale,'root_drift_cm':drift,'endpoint_position_error_cm':loop_error}
    report.update(ok=True,mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),native_heading='+Y',native_up='+Z',native_unit='centimeter',source_project_sha256=expected['source_sha256'])
except Exception as exc:
    report['error']=repr(exc);report['traceback']=traceback.format_exc();raise
finally:
    after=snapshot();report['existing_content_unchanged']=before==after
    report['protected_content_sha256']=before
    report['new_assets_sha256']={str(p.relative_to(CONTENT)):sha(p) for p in DISK.rglob('*') if p.is_file()}
    (OUT/('unreal-readback.json' if VERIFY else 'unreal-import.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert before==after,'Existing content was changed'
    unreal.log('STAMPEDE_NATIVE_AUDIT '+json.dumps({k:v for k,v in report.items() if k not in ['protected_content_sha256','new_assets_sha256','traceback']}))
