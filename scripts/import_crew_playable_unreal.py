"""Internal Crew import/readback worker; run through prepare_crew_playable_unreal.py."""
import hashlib,json,math,os,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT/'scripts'))
from crew_unreal_contract import character
CONFIG=character(os.environ['OLDWEST_CREW_SLUG'])
SLUG,NAME,OUT,DEST=(CONFIG[k] for k in ('slug','name','out','dest'))
CONTENT=ROOT/'game/OldWest/Content'
DISK=CONTENT/DEST.removeprefix('/Game/')
VERIFY=os.environ.get('OLDWEST_CREW_VERIFY_ONLY')=='1'
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
report={'ok':False,'approved_source_sha256':CONFIG['source_sha256'],'rig_project_sha256':CONFIG['validation']['project_sha256'],'mode':'fresh_readback' if VERIFY else 'import','destination':DEST}
before=snapshot()
try:
    exports=json.loads((OUT/'rig-validation.json').read_text())
    assert sha(OUT/(NAME+'-Rigged.blend'))==exports['project_sha256']
    for name,digest in exports['files'].items():assert sha(OUT/'exports'/name)==digest
    if not VERIFY:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
        textures={}
        for channel in ['BaseColor','ORM','Normal']:
            t=next(o for o in imp('T_'+NAME+'_' +channel+'.png',DEST+'/Textures') if isinstance(o,unreal.Texture2D))
            t.set_editor_property('srgb',channel=='BaseColor')
            if channel=='Normal':properties(t,dict(compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP,flip_green_channel=True))
            elif channel=='ORM':t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
            save(t);textures[channel]=t
        path=DEST+'/M_'+NAME
        mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('M_'+NAME,DEST,unreal.Material,unreal.MaterialFactoryNew())
        MAT.delete_all_material_expressions(mat)
        # The approved Mixar garments render both sides. Preserve the inside of
        # the skirt hem in Unreal instead of culling it as the legs move.
        properties(mat,dict(shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE,two_sided=True))
        nodes={}
        for i,(channel,t) in enumerate(textures.items()):
            node=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-800,i*250)
            node.set_editor_property('texture',t)
            if channel!='BaseColor':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if channel=='Normal' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            nodes[channel]=node
        for channel,socket,prop in [('BaseColor','RGB',unreal.MaterialProperty.MP_BASE_COLOR),('ORM','R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),('ORM','G',unreal.MaterialProperty.MP_ROUGHNESS)]:
            assert MAT.connect_material_property(nodes[channel],socket,prop)
        # Preserve approved atlas PBR instead of Native-specific cloth tuning.
        assert MAT.connect_material_property(nodes['Normal'],'RGB',unreal.MaterialProperty.MP_NORMAL)
        assert MAT.connect_material_property(nodes['ORM'],'B',unreal.MaterialProperty.MP_METALLIC)
        MAT.set_base_material_usage(mat,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,True)
        MAT.recompile_material(mat);save(mat)
        opt=unreal.FbxImportUI()
        properties(opt,dict(import_mesh=True,import_as_skeletal=True,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False,create_physics_asset=False))
        if LIB.does_asset_exist(DEST+'/SK_'+NAME):
            existing_skeleton=load(DEST+'/SK_'+NAME,unreal.SkeletalMesh).get_editor_property('skeleton')
            assert existing_skeleton and existing_skeleton.get_path_name().startswith(DEST+'/')
            # FBX's reference-update branch requires an explicitly selected
            # skeleton; merely rediscovering the existing skeleton skips it.
            opt.set_editor_property('skeleton',existing_skeleton)
        coordinates(opt.skeletal_mesh_import_data)
        # Each Crew character owns its skeleton. A repaired FBX must refresh
        # that skeleton's rest transforms, not retain an earlier rig's pose.
        properties(opt.skeletal_mesh_import_data,dict(update_skeleton_reference_pose=True,use_t0_as_ref_pose=False,preserve_smoothing_groups=True,normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS))
        mesh=next(o for o in imp('SK_'+NAME+'.fbx',DEST,opt) if isinstance(o,unreal.SkeletalMesh))
        skeleton=mesh.get_editor_property('skeleton');assert skeleton
        # Some legacy FBX reimport paths retain the prior USkeleton reference
        # despite the import flag. Use the editor's explicit reference update
        # operation, scoped by the helper to this character's unique skeleton.
        assert unreal.OldWestAssetAuthoring.refresh_crew_skeleton_reference(mesh)
        mesh.modify();slots=mesh.get_editor_property('materials');assert len(slots)==1
        slot=slots[0];slot.set_editor_property('material_interface',mat);slots[0]=slot;mesh.set_editor_property('materials',slots)
        save(mesh);save(skeleton)
        physics = unreal.OldWestAssetAuthoring.create_survivor_physics_asset(True, True, False, False, 'Crew/'+NAME)
        assert physics, 'Crew physics helper unavailable; build updated editor module'
        save(physics)
        mesh.set_editor_property('physics_asset', physics)
        save(mesh)

    mesh=load(DEST+'/SK_'+NAME,unreal.SkeletalMesh)
    skeleton=mesh.get_editor_property('skeleton');assert skeleton
    mat=load(DEST+'/M_'+NAME,unreal.Material)
    assert mat.get_editor_property('two_sided'), 'Approved garment interiors must remain visible'
    assert skeleton.get_path_name().startswith(DEST+'/'), 'Unexpected shared skeleton'
    assert len(mesh.get_editor_property('materials')) == 1
    assert mesh.get_editor_property('materials')[0].get_editor_property('material_interface')==mat
    component=unreal.SkeletalMeshComponent();component.set_skeletal_mesh_asset(mesh)
    bones=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    for name in ['root','Hips','Head','Spine','Spine1','Spine2','LeftHandMiddle3','RightToeBase']:assert name in bones,name
    reference=unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    reference_errors={'translation_cm':0.,'quaternion':0.,'scale':0.}
    for i,name in enumerate(bones):
        actual=component.get_ref_pose_transform(i)
        saved=unreal.AnimPoseExtensions.get_bone_pose(reference,name,unreal.AnimPoseSpaces.LOCAL)
        xyz=lambda v:[v.x,v.y,v.z]
        a=[actual.rotation.x,actual.rotation.y,actual.rotation.z,actual.rotation.w]
        b=[saved.rotation.x,saved.rotation.y,saved.rotation.z,saved.rotation.w]
        reference_errors['translation_cm']=max(reference_errors['translation_cm'],math.dist(xyz(actual.translation),xyz(saved.translation)))
        reference_errors['quaternion']=max(reference_errors['quaternion'],min(math.dist(a,b),math.dist(a,[-v for v in b])))
        reference_errors['scale']=max(reference_errors['scale'],math.dist(xyz(actual.scale3d),xyz(saved.scale3d)))
    report['mesh_skeleton_reference_max_errors']=reference_errors
    assert reference_errors['translation_cm']<.001 and reference_errors['quaternion']<.0001 and reference_errors['scale']<.00001, ('Stale skeleton reference pose',reference_errors)
    report['textures']={}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncTextureCompilationFinishAll')
    for channel in ['BaseColor','Normal','ORM']:
        tex=load(DEST+'/Textures/T_'+NAME+'_'+channel,unreal.Texture2D)
        size=[tex.blueprint_get_size_x(),tex.blueprint_get_size_y()];assert size==[2048,2048],size
        assert tex.get_editor_property('srgb')==(channel=='BaseColor')
        report['textures'][channel]={'size':size,'asset':tex.get_path_name()}
    physical = None
    physics = load(DEST+'/PA_'+NAME, unreal.PhysicsAsset)
    assert mesh.get_editor_property('physics_asset') == physics
    physical = json.loads(unreal.OldWestAssetAuthoring.describe_survivor_physics_asset(physics))
    assert physical['body_count'] == 16 and physical['constraint_count'] == 15
    report.update(ok=True,mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),bones=bones,physics=physical,two_sided=True)
except Exception as exc:
    report['error']=repr(exc);report['traceback']=traceback.format_exc();raise
finally:
    after=snapshot();report['existing_content_unchanged']=before==after
    if before != after: report['ok']=False
    report['new_assets_sha256']={str(p.relative_to(CONTENT)):sha(p) for p in DISK.rglob('*') if p.is_file()}
    (OUT/('unreal-readback.json' if VERIFY else 'unreal-import.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert before==after,'Existing Content changed'
    unreal.log('CREW_IMPORT_AUDIT '+json.dumps({k:v for k,v in report.items() if k not in ['physics','new_assets_sha256','traceback']}))
