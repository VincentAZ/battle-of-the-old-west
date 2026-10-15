"""Import the camp FBXs/PBR materials without editing a level or runtime code.

Execute inside Unreal Editor after create_camp_set.py completes. Creates assets
under /Game/Art/Camps and preserves existing assets on repeated invocation.
"""
import json
import re
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art/camps'
SPEC=json.loads((ART/'camp-set-manifest.json').read_text())
DEST='/Game/Art/Camps'
LIB=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
EDIT=unreal.MaterialEditingLibrary
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
texture_cache={}


def import_task(filename,dest,name,options=None,factory=None):
    task=unreal.AssetImportTask()
    for key,value in {'filename':str(filename),'destination_path':dest,'destination_name':name,
                      'automated':True,'save':True,'replace_existing':False}.items():
        task.set_editor_property(key,value)
    if options is not None:task.set_editor_property('options',options)
    if factory is not None:task.set_editor_property('factory',factory)
    TOOLS.import_asset_tasks([task])
    return task.get_objects()


def texture(path,usage,flip=False):
    key=(path,usage,flip)
    if key in texture_cache:return texture_cache[key]
    name='T_'+re.sub(r'[^A-Za-z0-9_]','_',Path(path).stem)+'_'+usage
    target=DEST+'/Textures/'+name
    if LIB.does_asset_exist(target):obj=LIB.load_asset(target)
    else:obj=next(o for o in import_task(ROOT/path,DEST+'/Textures',name) if isinstance(o,unreal.Texture2D))
    obj.set_editor_property('srgb',usage=='Color')
    if usage=='Normal':
        obj.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
        obj.set_editor_property('flip_green_channel',flip)
    elif usage!='Color':obj.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
    LIB.save_loaded_asset(obj)
    texture_cache[key]=obj
    return obj


def constant(mat,value,prop,y):
    node=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant,-220,y)
    node.set_editor_property('r',float(value));EDIT.connect_material_property(node,'',prop)
    return node


materials={}
for name,record in SPEC['materials'].items():
    target=DEST+'/Materials/M_'+name
    if LIB.does_asset_exist(target):materials[name]=LIB.load_asset(target);continue
    mat=TOOLS.create_asset('M_'+name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    def sample(path,usage,y):
        node=EDIT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-740,y)
        node.set_editor_property('texture',texture(path,usage,record.get('normal_convention')=='OpenGL'))
        if usage=='Normal':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif usage!='Color':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        return node
    color=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-500,-240)
    color.set_editor_property('constant',unreal.LinearColor(*(record['tint'] if record['textures'] else record['color']),1))
    if record['textures'].get('diff'):
        diffuse=sample(record['textures']['diff'],'Color',-250)
        multiply=EDIT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-240,-170)
        EDIT.connect_material_expressions(diffuse,'RGB',multiply,'A')
        EDIT.connect_material_expressions(color,'',multiply,'B')
        EDIT.connect_material_property(multiply,'',unreal.MaterialProperty.MP_BASE_COLOR)
    else:EDIT.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    if record['textures'].get('normal'):
        normal=sample(record['textures']['normal'],'Normal',100)
        EDIT.connect_material_property(normal,'RGB',unreal.MaterialProperty.MP_NORMAL)
    if record['textures'].get('arm'):
        packed=sample(record['textures']['arm'],'Mask',330)
        EDIT.connect_material_property(packed,'G',unreal.MaterialProperty.MP_ROUGHNESS)
        EDIT.connect_material_property(packed,'R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    elif record['textures'].get('rough'):
        rough=sample(record['textures']['rough'],'Mask',330)
        EDIT.connect_material_property(rough,'R',unreal.MaterialProperty.MP_ROUGHNESS)
    else:constant(mat,record['roughness'],unreal.MaterialProperty.MP_ROUGHNESS,330)
    constant(mat,record['metallic'],unreal.MaterialProperty.MP_METALLIC,480)
    if record['emission']:
        emit=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-350,650)
        # Project sun uses physical lux; the Blender emission is a lookdev value.
        emit.set_editor_property('constant',unreal.LinearColor(*(c*record['emission']*400 for c in record['color']),1))
        EDIT.connect_material_property(emit,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    EDIT.recompile_material(mat);LIB.save_loaded_asset(mat);materials[name]=mat

result={'camps':{},'material_count':len(materials),'map_modified':False}
for name,camp in SPEC['camps'].items():
    result['camps'][name]={}
    for state,record in camp['variants'].items():
        path=DEST+'/Meshes/'+record['unreal_name']
        if LIB.does_asset_exist(path):mesh=LIB.load_asset(path)
        else:
            options=unreal.FbxImportUI()
            for key,value in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,
                'import_textures':False,'import_animations':False,'automated_import_should_detect_type':False}.items():
                options.set_editor_property(key,value)
            options.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
            options.static_mesh_import_data.set_editor_property('combine_meshes',True)
            options.static_mesh_import_data.set_editor_property('auto_generate_collision',False)
            options.static_mesh_import_data.set_editor_property('generate_lightmap_u_vs',False)
            options.static_mesh_import_data.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
            objs=import_task(ROOT/record['fbx'],DEST+'/Meshes',record['unreal_name'],options,unreal.FbxFactory())
            meshes=[o for o in objs if isinstance(o,unreal.StaticMesh)]
            assert len(meshes)==1,f'Expected one camp static mesh: {name} {state}'
            mesh=meshes[0]
        for index,slot in enumerate(mesh.get_editor_property('static_materials')):
            slotname=str(slot.get_editor_property('material_slot_name'))
            assert slotname in materials,f'Unknown material {slotname}'
            mesh.set_material(index,materials[slotname])
        body=mesh.get_editor_property('body_setup')
        if body:body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        LIB.save_loaded_asset(mesh)
        result['camps'][name][state]=mesh.get_path_name()
assert LIB.save_directory(DEST,only_if_is_dirty=False,recursive=True), 'Camp asset directory failed to save'
result['texture_count']=len(texture_cache)
(ART/'unreal-import.json').write_text(json.dumps(result,indent=2)+'\n')
unreal.log('CAMP_SET_IMPORTED '+json.dumps(result))
