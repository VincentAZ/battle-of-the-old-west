"""Import only the new locally authored fuse mesh and three dedicated materials."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/trouble/fuse-v001'
BASE='/Game/Art/Western/Trouble/Fuse'
LIB=unreal.EditorAssetLibrary; MAT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()


def material(name, rgb, glow=0):
    mat=TOOLS.create_asset(name,BASE,unreal.Material,unreal.MaterialFactoryNew()) if not LIB.does_asset_exist(BASE+'/'+name) else LIB.load_asset(BASE+'/'+name)
    MAT.delete_all_material_expressions(mat)
    colour=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-300,0)
    colour.set_editor_property('constant',unreal.LinearColor(*rgb,1))
    assert MAT.connect_material_property(colour,'',unreal.MaterialProperty.MP_BASE_COLOR)
    rough=MAT.create_material_expression(mat,unreal.MaterialExpressionConstant,-300,160); rough.set_editor_property('r',.72)
    assert MAT.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    if glow:
        strength=MAT.create_material_expression(mat,unreal.MaterialExpressionScalarParameter,-500,300)
        strength.set_editor_property('parameter_name','Glow'); strength.set_editor_property('default_value',glow)
        multiply=MAT.create_material_expression(mat,unreal.MaterialExpressionMultiply,-100,280)
        assert MAT.connect_material_expressions(colour,'',multiply,'A')
        assert MAT.connect_material_expressions(strength,'',multiply,'B')
        assert MAT.connect_material_property(multiply,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MAT.recompile_material(mat); assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert hashlib.sha256((OUT/manifest['fbx']).read_bytes()).hexdigest()==manifest['fbx_sha256']
    assert hashlib.sha256((ROOT/'research/western-presentation/fuse-line.json').read_bytes()).hexdigest()==manifest['evidence_sha256']
    cord=material('M_WesternFuseCord',manifest['material_linear_rgb'])
    material('M_WesternFuseAsh',[.008,.008,.006])
    material('M_WesternFuseEmber',[1,.13,.004],5)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    options=unreal.FbxImportUI()
    for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,
                    import_animations=False,automated_import_should_detect_type=False,
                    mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items(): options.set_editor_property(k,v)
    for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
                    convert_scene=True,convert_scene_unit=True,force_front_x_axis=False,build_nanite=False,
                    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items(): options.static_mesh_import_data.set_editor_property(k,v)
    task=unreal.AssetImportTask()
    for k,v in dict(filename=str(OUT/manifest['fbx']),destination_path=BASE,destination_name='SM_WesternFuseCord',
                    automated=True,replace_existing=True,save=False,options=options,factory=unreal.FbxFactory()).items(): task.set_editor_property(k,v)
    TOOLS.import_asset_tasks([task]); mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
    for i in range(len(mesh.get_editor_property('static_materials'))): mesh.set_material(i,cord)
    assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
    box=mesh.get_bounding_box(); dimensions=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
    assert abs(dimensions[0]-100)<.5 and 3<dimensions[1]<5 and 3<dimensions[2]<5, dimensions
    (OUT/'unreal-import.json').write_text(json.dumps({'ok':True,'dimensions_cm':dimensions,'triangles':mesh.get_num_triangles(0),'asset':BASE+'/SM_WesternFuseCord'},indent=2)+'\n')
    unreal.log('WESTERN_FUSE_IMPORTED '+str(dimensions))


if __name__ == '__main__': main()
