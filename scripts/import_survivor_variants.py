"""Import reviewed costume candidates into NEW Unreal assets only.

Run in the coordinated UnrealEditor-Cmd asset lane after authoring and studio
review. No command in this script starts an editor or modifies runtime C++.
Original SurvivorA mesh, skeleton, animations and materials are hash-protected.
"""
import hashlib
import json
import os
from pathlib import Path

import unreal

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('OLDWEST_VARIANT_SOURCE',str(ROOT/'art/characters/survivor_variants'))).resolve()
BASE='/Game/Art/Survivors/SurvivorA'
DEST=os.environ.get('OLDWEST_VARIANT_DEST','/Game/Art/Survivors/Variants')
LIB=unreal.EditorAssetLibrary
MAT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA').rglob('*.uasset')}
assert protected
skeleton=LIB.load_asset(BASE+'/SKM_Survivor_A_Cm_Skeleton')
physics=LIB.load_asset(BASE+'/PA_Survivor_Anatomical')
assert skeleton and physics
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')


def import_file(path,name,destination,options=None,factory=None):
    task=unreal.AssetImportTask()
    for key,value in {'filename':str(path),'destination_path':destination,'destination_name':name,
                       'automated':True,'replace_existing':True,'save':False}.items():task.set_editor_property(key,value)
    if options:task.set_editor_property('options',options)
    if factory:task.set_editor_property('factory',factory)
    TOOLS.import_asset_tasks([task])
    return task.get_objects()


def import_hair_material(name,spec):
    texture_path=Path(spec['opacity_texture'])
    assert hashlib.sha256(texture_path.read_bytes()).hexdigest()==spec['opacity_sha256']
    texture_name='T_Identity_Hair_Strands'
    texture=next((o for o in import_file(texture_path,texture_name,DEST+'/Textures')
                  if isinstance(o,unreal.Texture2D)),None)
    assert texture
    texture.set_editor_property('srgb',False)
    texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
    assert LIB.save_loaded_asset(texture)
    path=DEST+'/Materials/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    assert mat
    MAT.delete_all_material_expressions(mat)
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property('two_sided',True)
    mat.set_editor_property('opacity_mask_clip_value',spec['opacity_clip'])
    strands=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-750,0)
    strands.set_editor_property('texture',texture)
    strands.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    uv=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureCoordinate,-1200,-300)
    v=MAT.create_material_expression(mat,unreal.MaterialExpressionComponentMask,-1000,-300)
    v.set_editor_property('r',False);v.set_editor_property('g',True)
    assert MAT.connect_material_expressions(uv,'',v,'')
    # The legacy skeletal FBX importer stores Unreal V = 1 - source V.
    # Blender's root fade (1 - V) therefore becomes V in the native graph.
    # Inverting again faded the tips instead of the roots.
    fade_scale=MAT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-600,-300)
    fade_scale.set_editor_property('const_b',1/(1-spec['root_fade_start']))
    assert MAT.connect_material_expressions(v,'',fade_scale,'A')
    fade=MAT.create_material_expression(mat,unreal.MaterialExpressionSaturate,-400,-300)
    assert MAT.connect_material_expressions(fade_scale,'',fade,'')
    opacity=MAT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-200,-150)
    assert MAT.connect_material_expressions(strands,'R',opacity,'A')
    assert MAT.connect_material_expressions(fade,'',opacity,'B')
    assert MAT.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY_MASK)
    diffuse_path=Path(spec['diffuse_texture'])
    assert hashlib.sha256(diffuse_path.read_bytes()).hexdigest()==spec['diffuse_sha256']
    diffuse_texture=next((o for o in import_file(diffuse_path,'T_Identity_Hair_Diffuse',DEST+'/Textures')
                          if isinstance(o,unreal.Texture2D)),None)
    assert diffuse_texture
    diffuse_texture.set_editor_property('srgb',True)
    assert LIB.save_loaded_asset(diffuse_texture)
    diffuse=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-1200,500)
    diffuse.set_editor_property('texture',diffuse_texture)
    coefficients=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-1200,700)
    coefficients.set_editor_property('constant',unreal.LinearColor(.2126,.7152,.0722,1))
    luminance=MAT.create_material_expression(mat,unreal.MaterialExpressionDotProduct,-1000,500)
    assert MAT.connect_material_expressions(diffuse,'RGB',luminance,'A')
    assert MAT.connect_material_expressions(coefficients,'',luminance,'B')
    value_scale=MAT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-800,500)
    value_scale.set_editor_property('const_b',1/spec['diffuse_luminance_max'])
    assert MAT.connect_material_expressions(luminance,'',value_scale,'A')
    variation=MAT.create_material_expression(mat,unreal.MaterialExpressionSaturate,-600,500)
    assert MAT.connect_material_expressions(value_scale,'',variation,'')
    colors=[]
    for i,amount in enumerate([spec['strand_shadow'],1.]):
        node=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-750,240+i*150)
        node.set_editor_property('constant',unreal.LinearColor(*(v*amount for v in spec['base']),1))
        colors.append(node)
    tint=MAT.create_material_expression(mat,unreal.MaterialExpressionLinearInterpolate,-350,100)
    assert MAT.connect_material_expressions(colors[0],'',tint,'A')
    assert MAT.connect_material_expressions(colors[1],'',tint,'B')
    assert MAT.connect_material_expressions(variation,'',tint,'Alpha')
    assert MAT.connect_material_property(tint,'',unreal.MaterialProperty.MP_BASE_COLOR)
    for i,(value,prop) in enumerate([(spec['roughness'],unreal.MaterialProperty.MP_ROUGHNESS),
                                    (spec['specular'],unreal.MaterialProperty.MP_SPECULAR)]):
        node=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant,-350,400+i*100)
        node.set_editor_property('r',value)
        assert MAT.connect_material_property(node,'',prop)
    for usage in [unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS]:
        MAT.set_base_material_usage(mat,usage,True)
        assert MAT.has_material_usage(mat,usage)
    MAT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat)
    return mat


def import_solid_detail(name,spec):
    path=DEST+'/Materials/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    assert mat
    MAT.delete_all_material_expressions(mat)
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property('two_sided',spec['two_sided'])
    color=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-400,0)
    color.set_editor_property('constant',unreal.LinearColor(*spec['base'],1))
    assert MAT.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    for i,(value,prop) in enumerate([(spec['roughness'],unreal.MaterialProperty.MP_ROUGHNESS),
                                    (spec['specular'],unreal.MaterialProperty.MP_SPECULAR)]):
        node=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant,-400,160+i*120)
        node.set_editor_property('r',value)
        assert MAT.connect_material_property(node,'',prop)
    for usage in [unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS]:
        MAT.set_base_material_usage(mat,usage,True)
        assert MAT.has_material_usage(mat,usage)
    MAT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat)
    return mat


reports=[]
variants=json.loads(os.environ['OLDWEST_VARIANT_IDS']) if 'OLDWEST_VARIANT_IDS' in os.environ else [('prospector','Prospector'),('gatling_gunner','Gatling Gunner'),('bounty_hunter','Bounty Hunter')]
for card,name in variants:
    source=SOURCE/card
    spec=json.loads((source/'manifest.json').read_text())
    assert spec['original_rig_unchanged'] and spec['rig_bones']==53
    assert spec['armature_object_name']=='Survivor_Rig' and not spec['source_animation_actions_included']
    textures={}
    for channel,record in spec['textures'].items():
        path=Path(record['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
        tex=next((o for o in import_file(path,path.stem,DEST+'/Textures') if isinstance(o,unreal.Texture2D)),None)
        assert tex,'Missing '+channel
        tex.set_editor_property('srgb',channel=='BaseColor')
        if channel=='Normal':
            tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property('flip_green_channel',True)
        elif channel!='BaseColor':tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
        assert LIB.save_loaded_asset(tex)
        textures[channel]=tex
    material_name=spec['outfit_material'];path=DEST+'/Materials/'+material_name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(material_name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    assert mat
    MAT.delete_all_material_expressions(mat)
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
    for index,(channel,prop) in enumerate([('BaseColor',unreal.MaterialProperty.MP_BASE_COLOR),
        ('Roughness',unreal.MaterialProperty.MP_ROUGHNESS),('Metallic',unreal.MaterialProperty.MP_METALLIC),
        ('Normal',unreal.MaterialProperty.MP_NORMAL)]):
        node=MAT.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-500,index*190)
        node.set_editor_property('texture',textures[channel])
        if channel=='Normal':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif channel!='BaseColor':node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        assert MAT.connect_material_property(node,'RGB' if channel in ['BaseColor','Normal'] else 'R',prop)
    for usage in [unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS]:
        MAT.set_base_material_usage(mat,usage,True);assert MAT.has_material_usage(mat,usage)
    MAT.recompile_material(mat);assert LIB.save_loaded_asset(mat)
    extra_materials={name:import_hair_material(name,record) for name,record in spec.get('materials',{}).items()
                     if record.get('kind')=='masked_hair'}
    extra_materials.update({name:import_solid_detail(name,record) for name,record in spec.get('materials',{}).items()
                            if record.get('kind')=='solid_detail'})
    fbx=source/(name+'_Cm.fbx');assert hashlib.sha256(fbx.read_bytes()).hexdigest()==spec['fbx_sha256']
    options=unreal.FbxImportUI()
    for key,value in {'import_mesh':True,'import_as_skeletal':True,'mesh_type_to_import':unreal.FBXImportType.FBXIT_SKELETAL_MESH,
        'import_materials':False,'import_textures':False,'import_animations':False,'automated_import_should_detect_type':False,
        'create_physics_asset':False,'skeleton':skeleton,'physics_asset':physics}.items():options.set_editor_property(key,value)
    for key,value in {'update_skeleton_reference_pose':False,'use_t0_as_ref_pose':False,'import_morph_targets':True,
        'preserve_smoothing_groups':True,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():options.skeletal_mesh_import_data.set_editor_property(key,value)
    meshes=[o for o in import_file(fbx,'SKM_'+name+'_Cm',DEST,options,unreal.FbxFactory()) if isinstance(o,unreal.SkeletalMesh)]
    assert len(meshes)==1
    mesh=meshes[0];assert mesh.get_editor_property('skeleton')==skeleton and mesh.get_editor_property('physics_asset')==physics
    mesh.modify()
    slots=mesh.get_editor_property('materials');mapped=[]
    for index,slot in enumerate(slots):
        slot_name=str(slot.get_editor_property('material_slot_name'))
        assert slot_name in spec['material_names'],slot_name
        original_path=BASE+'/Materials/'+slot_name
        material=mat if slot_name==material_name else extra_materials.get(slot_name) or LIB.load_asset(original_path)
        assert material,'Unknown material '+slot_name
        slot.set_editor_property('material_interface',material)
        # Unreal.Array iteration yields a struct value. Explicitly write the
        # edited value back rather than relying on a borrowed property wrapper.
        slots[index]=slot
        mapped.append({'slot':slot_name,'material':material.get_path_name()})
    mesh.set_editor_property('materials',slots);assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in protected.items()),'Original survivor files changed'
    report={'card_id':card,'mesh':mesh.get_path_name(),'skeleton':skeleton.get_path_name(),'physics_asset':physics.get_path_name(),
        'source_fbx_sha256':spec['fbx_sha256'],'materials':mapped,'textures':{k:v.get_path_name() for k,v in textures.items()},
        'original_assets_unchanged':True,'hero_mesh_imported':True,'generated_lods':False,
        'native_animation_and_visual_review_required':True}
    (source/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    unreal.log('SURVIVOR_VARIANT_IMPORTED '+json.dumps(report))
(SOURCE/'unreal-import.json').write_text(json.dumps({'variants':reports,'protected_sha256':protected},indent=2)+'\n')
