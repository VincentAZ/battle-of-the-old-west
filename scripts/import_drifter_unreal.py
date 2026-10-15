"""Import the approved Mixar Drifter without altering pre-existing Content.

Set OLDWEST_DRIFTER_VERIFY_ONLY=1 for a separate fresh-process audit.
No gameplay actors, maps, cooking lists or launcher packages are changed.
"""
import hashlib,json,math,os,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/drifter/animation-v001'
CONTENT=ROOT/'game/OldWest/Content'
DEST='/Game/Art/Western/Drifter'
DISK=CONTENT/'Art/Western/Drifter'
VERIFY=os.environ.get('OLDWEST_DRIFTER_VERIFY_ONLY')=='1'
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
report={'ok':False,'mode':'fresh_readback' if VERIFY else 'import','destination':DEST}
before=snapshot()
try:
    exports=json.loads((OUT/'rig-validation.json').read_text())
    assert sha(OUT/'Drifter-Rigged.blend')==exports['project_sha256']
    for name,digest in exports['files'].items():assert sha(OUT/'exports'/name)==digest
    if not VERIFY:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
        textures={}
        for channel in ['BaseColor','ORM','Normal']:
            t=next(o for o in imp('T_Drifter_'+channel+'.png',DEST+'/Textures') if isinstance(o,unreal.Texture2D))
            t.set_editor_property('srgb',channel=='BaseColor')
            if channel=='Normal':properties(t,dict(compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP,flip_green_channel=True))
            elif channel=='ORM':t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
            save(t);textures[channel]=t
        path=DEST+'/M_Drifter'
        mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('M_Drifter',DEST,unreal.Material,unreal.MaterialFactoryNew())
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
        floor=MAT.create_material_expression(mat,unreal.MaterialExpressionMax,-200,350)
        floor.set_editor_property('const_b',.6)
        assert MAT.connect_material_expressions(nodes['ORM'],'G',floor,'A')
        assert MAT.connect_material_property(floor,'',unreal.MaterialProperty.MP_ROUGHNESS)
        MAT.set_base_material_usage(mat,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,True)
        MAT.recompile_material(mat);save(mat)
        opt=unreal.FbxImportUI()
        properties(opt,dict(import_mesh=True,import_as_skeletal=True,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False,create_physics_asset=False))
        coordinates(opt.skeletal_mesh_import_data)
        properties(opt.skeletal_mesh_import_data,dict(update_skeleton_reference_pose=False,use_t0_as_ref_pose=False,preserve_smoothing_groups=True,normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS))
        mesh=next(o for o in imp('SK_Drifter.fbx',DEST,opt) if isinstance(o,unreal.SkeletalMesh))
        skeleton=mesh.get_editor_property('skeleton');assert skeleton
        mesh.modify();slots=mesh.get_editor_property('materials');assert len(slots)==1
        slot=slots[0];slot.set_editor_property('material_interface',mat);slots[0]=slot;mesh.set_editor_property('materials',slots)
        save(mesh);save(skeleton)

        physics=unreal.OldWestAssetAuthoring.create_survivor_physics_asset(True,True,True)
        assert physics
        save(physics)
        mesh.set_editor_property('physics_asset',physics);save(mesh)
    mesh=load(DEST+'/SK_Drifter',unreal.SkeletalMesh)
    skeleton=mesh.get_editor_property('skeleton');assert skeleton
    mat=load(DEST+'/M_Drifter',unreal.Material)
    assert mesh.get_editor_property('materials')[0].get_editor_property('material_interface')==mat
    physics=load(DEST+'/PA_Drifter',unreal.PhysicsAsset)
    assert mesh.get_editor_property('physics_asset')==physics
    physical=json.loads(unreal.OldWestAssetAuthoring.describe_survivor_physics_asset(physics))
    assert physical['body_count']==16 and physical['constraint_count']==15
    component=unreal.SkeletalMeshComponent();component.set_skeletal_mesh_asset(mesh)
    bones=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    for name in ['root','Hips','Head','Spine','Spine1','Spine2','LeftHandMiddle3','RightToeBase']:assert name in bones,name
    report['textures']={}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncTextureCompilationFinishAll')
    for channel in ['BaseColor','Normal','ORM']:
        tex=load(DEST+'/Textures/T_Drifter_'+channel,unreal.Texture2D)
        size=[tex.blueprint_get_size_x(),tex.blueprint_get_size_y()];assert size==[2048,2048],size
        assert tex.get_editor_property('srgb')==(channel=='BaseColor')
        report['textures'][channel]={'size':size,'asset':tex.get_path_name()}
    report.update(ok=True,mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),bones=bones,physics=physical)
except Exception as exc:
    report['error']=repr(exc);report['traceback']=traceback.format_exc();raise
finally:
    after=snapshot();report['existing_content_unchanged']=before==after
    report['new_assets_sha256']={str(p.relative_to(CONTENT)):sha(p) for p in DISK.rglob('*') if p.is_file()}
    (OUT/('unreal-readback.json' if VERIFY else 'unreal-import.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert before==after,'Existing Content changed'
    unreal.log('DRIFTER_NATIVE_AUDIT '+json.dumps({k:v for k,v in report.items() if k not in ['physics','new_assets_sha256','traceback']}))
