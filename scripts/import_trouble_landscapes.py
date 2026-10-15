"""Import locally reviewed Trouble meshes into a dedicated presentation folder."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/trouble/landscapes-v002'
BASE='/Game/Art/Western/Trouble/Landscapes'
LIB=unreal.EditorAssetLibrary;EDIT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()


def material(name,rgb):
    path=BASE+'/Materials/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,BASE+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True)
    colour=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
    colour.set_editor_property('constant',unreal.LinearColor(*rgb,1))
    assert EDIT.connect_material_property(colour,'',unreal.MaterialProperty.MP_BASE_COLOR)
    metal=BASE.endswith('/Schemes') and name.removeprefix('M_Trouble_') in {'Iron','Steel','Bronze','Copper','Gold','PanMetal'}
    glass=BASE.endswith('/Schemes') and name.endswith('_Glass')
    smoke=BASE.endswith('/Schemes') and name.endswith('_Smoke')
    rough=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant);rough.set_editor_property('r',.12 if glass else .38 if metal else .87)
    assert EDIT.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    if metal:
        metallic=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant);metallic.set_editor_property('r',.8)
        assert EDIT.connect_material_property(metallic,'',unreal.MaterialProperty.MP_METALLIC)
    if glass:
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        opacity=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant);opacity.set_editor_property('r',.055)
        assert EDIT.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY)
    if smoke:
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property('two_sided',False)
        edge=EDIT.create_material_expression(mat,unreal.MaterialExpressionFresnel)
        edge.set_editor_property('exponent',1.)
        fade=EDIT.create_material_expression(mat,unreal.MaterialExpressionOneMinus)
        assert EDIT.connect_material_expressions(edge,'',fade,'')
        opacity=EDIT.create_material_expression(mat,unreal.MaterialExpressionMultiply);opacity.set_editor_property('const_b',.22)
        assert EDIT.connect_material_expressions(fade,'',opacity,'A')
        assert EDIT.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY)
        daylight=EDIT.create_material_expression(mat,unreal.MaterialExpressionMultiply);daylight.set_editor_property('const_b',1500.)
        assert EDIT.connect_material_expressions(colour,'',daylight,'A')
        assert EDIT.connect_material_property(daylight,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if 'Flame' in name:
        glow=EDIT.create_material_expression(mat,unreal.MaterialExpressionMultiply)
        glow.set_editor_property('const_b',.7)
        assert EDIT.connect_material_expressions(colour,'',glow,'A')
        assert EDIT.connect_material_property(glow,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    EDIT.recompile_material(mat);assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat


def main():
    global OUT,BASE
    evidence=ROOT/'research/western-presentation/trouble-landscapes.json'
    objects='-TroubleObjects' in unreal.SystemLibrary.get_command_line()
    schemes='-TroubleSchemes' in unreal.SystemLibrary.get_command_line()
    assert not (objects and schemes)
    if objects:
        OUT=ROOT/'art/western/trouble/objects-v002';BASE='/Game/Art/Western/Trouble/Objects'
        evidence=ROOT/'research/western-presentation/trouble-objects.json'
    if schemes:
        OUT=ROOT/'art/western/trouble/schemes-v003';BASE='/Game/Art/Western/Trouble/Schemes'
        evidence=ROOT/'research/western-presentation/trouble-schemes.json'
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert manifest['evidence_sha256']==hashlib.sha256(evidence.read_bytes()).hexdigest()
    review=json.loads((OUT/'visual-review.json').read_text())
    assert review['status']=='accepted_for_native_review'
    assert review['manifest_sha256']==hashlib.sha256((OUT/'manifest.json').read_bytes()).hexdigest()
    if '-TroubleEffectsOnly' in unreal.SystemLibrary.get_command_line():
        assert schemes
        effect_path=ROOT/'research/western-presentation/trouble-schemes-effects.json'
        effects=json.loads(effect_path.read_text())
        paths=[material(name,settings['linear_rgb']).get_path_name() for name,settings in effects['effect_materials'].items()]
        (OUT/'unreal-effects-import.json').write_text(json.dumps(dict(ok=True,materials=paths,
            evidence_sha256=hashlib.sha256(effect_path.read_bytes()).hexdigest()),indent=2)+'\n')
        unreal.log('TROUBLE_EFFECT_MATERIALS_IMPORTED '+str(len(paths)))
        return
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    materials={name:material(name,rgb) for name,rgb in manifest['material_linear_rgb'].items()}
    if schemes:
        effects=json.loads((ROOT/'research/western-presentation/trouble-schemes-effects.json').read_text())
        for name,settings in effects['effect_materials'].items():materials[name]=material(name,settings['linear_rgb'])
    records=[]
    for record in manifest['assets']:
        file=OUT/record['fbx'];assert hashlib.sha256(file.read_bytes()).hexdigest()==record['sha256']
        opts=unreal.FbxImportUI()
        for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,
            import_animations=False,automated_import_should_detect_type=False,
            mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():opts.set_editor_property(k,v)
        for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
            convert_scene=True,convert_scene_unit=True,force_front_x_axis=False,build_nanite=False,
            normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():opts.static_mesh_import_data.set_editor_property(k,v)
        task=unreal.AssetImportTask()
        for k,v in dict(filename=str(file),destination_path=BASE+'/Meshes',destination_name=record['name'],
            automated=True,replace_existing=True,save=False,options=opts,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
        TOOLS.import_asset_tasks([task]);mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
        for i,slot in enumerate(mesh.get_editor_property('static_materials')):
            key=str(slot.get_editor_property('imported_material_slot_name'));assert key in materials,key
            mesh.set_material(i,materials[key])
        assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
        box=mesh.get_bounding_box();dimensions=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
        if schemes:assert 175<dimensions[0]<200 and 135<dimensions[1]<170 and 25<dimensions[2]<280,dimensions
        elif objects:assert 175<dimensions[0]<200 and 125<dimensions[1]<150 and 10<dimensions[2]<220,dimensions
        else:assert 175<dimensions[0]<200 and 135<dimensions[1]<150 and 60<dimensions[2]<170,dimensions
        records.append(dict(card_id=record['card_id'],asset=mesh.get_path_name(),dimensions_cm=dimensions,
            triangles=mesh.get_num_triangles(0),material_count=len(mesh.get_editor_property('static_materials'))))
    (OUT/'unreal-import.json').write_text(json.dumps(dict(ok=True,assets=records,evidence_sha256=manifest['evidence_sha256']),indent=2)+'\n')
    unreal.log('TROUBLE_LANDSCAPES_IMPORTED '+str(len(records)))


if __name__=='__main__':main()
