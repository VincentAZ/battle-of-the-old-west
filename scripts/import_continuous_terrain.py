"""Import terrain with optional asset-only and fresh-process verification modes.

-TerrainAssetOnly reimports the mesh without loading/saving a level.
-TerrainVerifyOnly checks persisted bounds, material, collision and UVs.
Default mode retains the guarded terrain-actor replacement workflow.
"""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/world'
LIB=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
MAP='/Game/Maps/WaterDepotV2'
BACKUP='/Game/Maps/WaterDepotV2_ArtStudyBackup'
DEST='/Game/Art/WaterDepotV2/Meshes'
ASSET=DEST+'/SM_ContinuousTerrain'
COMMAND=unreal.SystemLibrary.get_command_line()
VERIFY='-TerrainVerifyOnly' in COMMAND
ASSET_ONLY=VERIFY or '-TerrainAssetOnly' in COMMAND
spec=json.loads((OUT/'continuous-terrain.json').read_text())
map_files=[ROOT/'game/OldWest/Content/Maps'/f'{name}.umap' for name in ('WaterDepotV2','WaterDepotV2_ArtStudyBackup')]
map_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in map_files if p.exists()}
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
EDIT=unreal.MaterialEditingLibrary
MATERIAL='/Game/Art/WaterDepotV2/Materials/M_ContinuousTerrain'
original_material_file=ROOT/'game/OldWest/Content/Art/WaterDepotV2/Materials/M_DustAndGravel.uasset'
original_material_hash=hashlib.sha256(original_material_file.read_bytes()).hexdigest()


def build_terrain_material():
    """A terrain-only material; preserve the old local shading through 80m.

    Distant ground uses the existing CC0 aerial dirt scan with triplanar
    projection, broad color variation and restrained distance desaturation.
    The source material and map fog are not modified.
    """
    mat=LIB.load_asset(MATERIAL) if LIB.does_asset_exist(MATERIAL) else TOOLS.create_asset(
        'M_ContinuousTerrain','/Game/Art/WaterDepotV2/Materials',unreal.Material,unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat)
    def node(cls):return EDIT.create_material_expression(mat,cls)
    def connect(a,output,b,input):
        assert EDIT.connect_material_expressions(a,output,b,input),(output,input)
    def constant(value):
        n=node(unreal.MaterialExpressionConstant);n.set_editor_property('r',value);return n
    def texture(name,usage):
        asset=LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_'+name)
        assert asset,name
        n=node(unreal.MaterialExpressionTextureSample);n.set_editor_property('texture',asset)
        n.set_editor_property('sampler_type',usage)
        return n
    diffuse=texture('dirt_diff_4k',unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    normal=texture('dirt_nor_dx_4k',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    arm=texture('dirt_arm_4k',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    tint=node(unreal.MaterialExpressionConstant3Vector)
    tint.set_editor_property('constant',unreal.LinearColor(1.1,1.03,.9,1))
    original=node(unreal.MaterialExpressionMultiply)
    connect(diffuse,'RGB',original,'A');connect(tint,'',original,'B')
    scan=LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_dirt_aerial_03_diff_4k')
    assert scan
    scan_object=node(unreal.MaterialExpressionTextureObject)
    scan_object.set_editor_property('texture',scan)
    position=node(unreal.MaterialExpressionWorldPosition)
    vertex_normal=node(unreal.MaterialExpressionVertexNormalWS)
    camera=node(unreal.MaterialExpressionCameraPositionWS)
    custom=node(unreal.MaterialExpressionCustom)
    custom.set_editor_property('description','Terrain-only distant scan and restrained aerial color separation')
    custom.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs=[]
    for name in ['Original','World','Camera','NormalWS','Scan']:
        entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
    custom.set_editor_property('inputs',inputs)
    custom.set_editor_property('code','''
float distant = smoothstep(8000.0,20000.0,length(World.xy));
float3 w = pow(abs(NormalWS),4.0);
w /= max(w.x+w.y+w.z,0.0001);
float3 scanX = Texture2DSample(Scan,ScanSampler,World.yz/2700.0).rgb;
float3 scanY = Texture2DSample(Scan,ScanSampler,World.xz/2700.0).rgb;
float3 scanZ = Texture2DSample(Scan,ScanSampler,World.xy/2700.0).rgb;
float3 ground = scanX*w.x+scanY*w.y+scanZ*w.z;
float3 broad = Texture2DSample(Scan,ScanSampler,World.xy/13700.0+float2(.17,.39)).rgb;
ground = lerp(ground,broad,0.28)*float3(.98,1.01,1.02);
float gray = dot(ground,float3(.2126,.7152,.0722));
ground = lerp(ground,gray.xxx,0.22);
float aerial = smoothstep(35000.0,125000.0,length(World-Camera))*0.24;
ground = lerp(ground,float3(.20,.22,.225),aerial);
return lerp(Original,ground,distant);
''')
    for n,output,name in [(original,'','Original'),(position,'','World'),(camera,'','Camera'),
                          (vertex_normal,'','NormalWS'),(scan_object,'','Scan')]:connect(n,output,custom,name)
    assert EDIT.connect_material_property(custom,'',unreal.MaterialProperty.MP_BASE_COLOR)
    # Fade only the far subpixel normal texture, retaining exact near shading.
    fade=node(unreal.MaterialExpressionCustom)
    fade.set_editor_property('description','Preserve local shading; soften distant subpixel dirt normals')
    fade.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs=[]
    for name in ['World','Normal']:
        entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
    fade.set_editor_property('inputs',inputs)
    fade.set_editor_property('code','return lerp(Normal,float3(0,0,1),smoothstep(8000.0,22000.0,length(World.xy))*0.9);')
    connect(position,'',fade,'World');connect(normal,'RGB',fade,'Normal')
    EDIT.connect_material_property(fade,'',unreal.MaterialProperty.MP_NORMAL)
    EDIT.connect_material_property(arm,'G',unreal.MaterialProperty.MP_ROUGHNESS)
    EDIT.connect_material_property(arm,'R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    EDIT.connect_material_property(constant(0),'',unreal.MaterialProperty.MP_METALLIC)
    EDIT.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_NANITE, True)
    assert EDIT.has_material_usage(mat, unreal.MaterialUsage.MATUSAGE_NANITE)
    EDIT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    assert hashlib.sha256(original_material_file.read_bytes()).hexdigest()==original_material_hash
    return mat

if not VERIFY:
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    options=unreal.FbxImportUI()
    for key,value in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,
                      'import_textures':False,'import_animations':False,'automated_import_should_detect_type':False}.items():
        options.set_editor_property(key,value)
    options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    options.static_mesh_import_data.combine_meshes=True
    options.static_mesh_import_data.auto_generate_collision=False
    options.static_mesh_import_data.generate_lightmap_u_vs=False
    options.static_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    task=unreal.AssetImportTask()
    for key,value in {'filename':str(OUT/'ContinuousTerrain.fbx'),'destination_path':DEST,
                      'destination_name':'SM_ContinuousTerrain','options':options,'factory':unreal.FbxFactory(),
                      'automated':True,'replace_existing':True,'save':True}.items():
        task.set_editor_property(key,value)
    TOOLS.import_asset_tasks([task])

mesh=LIB.load_asset(ASSET)
assert isinstance(mesh,unreal.StaticMesh)
material=LIB.load_asset(MATERIAL) if VERIFY else build_terrain_material()
assert material
body=mesh.get_editor_property('body_setup')
assert body
if not VERIFY:
    mesh.set_material(0,material)
    body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)

bounds=mesh.get_bounds()
dimensions=[float(bounds.box_extent.x*2),float(bounds.box_extent.y*2),float(bounds.box_extent.z*2)]
expected=[spec['extent_m']*200,spec['extent_m']*200,(spec['height_range_m'][1]-spec['height_range_m'][0])*100]
assert all(abs(a-b)<max(1,b*.00001) for a,b in zip(dimensions,expected)),(dimensions,expected)
slots=mesh.get_editor_property('static_materials')
assert len(slots)==1 and slots[0].get_editor_property('material_interface')==material
assert 'USE_COMPLEX_AS_SIMPLE' in str(body.get_editor_property('collision_trace_flag'))
edit=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
uvs=edit.get_num_uv_channels(mesh,0)
assert uvs==1
report={'asset':mesh.get_path_name(),'bounds_cm':dimensions,'uv_channels':uvs,
        'material':material.get_path_name(),'collision':'complex_as_simple','fresh_reload':VERIFY,
        'original_material_unchanged':hashlib.sha256(original_material_file.read_bytes()).hexdigest()==original_material_hash,
        'map_modified':False,'original_art_study_backup_modified':False,'visual_qa_passed':False}

if not ASSET_ONLY:
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert levels and actors,'Use -TerrainAssetOnly in a NullRHI commandlet'
    if not LIB.does_asset_exist(BACKUP):
        assert LIB.duplicate_asset(MAP,BACKUP)
        LIB.save_asset(BACKUP)
    assert levels.load_level(MAP)
    targets=[a for a in actors.get_all_level_actors() if a.get_actor_label()=='Water depot — Terrain']
    assert len(targets)==1,'Expected one authored terrain actor'
    component=targets[0].get_component_by_class(unreal.StaticMeshComponent)
    report['previous_mesh']=component.get_editor_property('static_mesh').get_path_name()
    component.set_static_mesh(mesh)
    assert levels.save_current_level()
    report['map_modified']=True
else:
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in map_hashes.items()),'A map file unexpectedly changed'
    report['unchanged_map_sha256']=map_hashes

(OUT/('unreal-terrain-validation.json' if VERIFY else 'unreal-terrain-import.json')).write_text(json.dumps(report,indent=2)+'\n')
unreal.log(('CONTINUOUS_TERRAIN_VERIFIED ' if VERIFY else 'CONTINUOUS_TERRAIN_IMPORTED ')+json.dumps(report))
