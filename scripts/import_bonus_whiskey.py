"""Import only the reviewed bonus tumbler and its two new materials."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/whiskey/bonus-v002'
LIB=unreal.EditorAssetLibrary; EDIT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
CONTENT=ROOT/'game/OldWest/Content'
FOLDER='/Game/Art/ActionProps/BonusWhiskey'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    exclusions={'Art/ActionProps/Meshes/SM_Action_BonusWhiskeyGlass.uasset',
                'Art/ActionProps/BonusWhiskey/M_Bonus_ClearGlass.uasset',
                'Art/ActionProps/BonusWhiskey/M_Bonus_Amber.uasset'}
    return {str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*')
            if p.is_file() and str(p.relative_to(CONTENT)) not in exclusions}


def material(name, glass):
    path=FOLDER+'/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,FOLDER,unreal.Material,unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat)
    def node(kind, **props):
        n=EDIT.create_material_expression(mat,getattr(unreal,kind))
        for key,value in props.items(): n.set_editor_property(key,value)
        return n
    def prop(n, key): assert EDIT.connect_material_property(n,'',getattr(unreal.MaterialProperty,key))
    rgb=(.95,.985,.98) if glass else (.22,.055,.002)
    prop(node('MaterialExpressionConstant3Vector',constant=unreal.LinearColor(*rgb,1)),'MP_BASE_COLOR')
    prop(node('MaterialExpressionConstant',r=.08 if glass else .12),'MP_ROUGHNESS')
    prop(node('MaterialExpressionConstant',r=.5),'MP_SPECULAR')
    mat.set_editor_property('two_sided',False)
    if glass:
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        edge=node('MaterialExpressionFresnel',exponent=4.,base_reflect_fraction=.08)
        opacity=node('MaterialExpressionMultiply',const_b=.6)
        assert EDIT.connect_material_expressions(edge,'',opacity,'A')
        prop(opacity,'MP_OPACITY')
    else:
        # Thin visible amber volume: preserve light through the glass instead
        # of the opaque yellow reading of the first native material review.
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        prop(node('MaterialExpressionConstant',r=.72),'MP_OPACITY')
    EDIT.recompile_material(mat); assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    review=json.loads((OUT/'visual-review.json').read_text())
    assert review['status']=='accepted_for_native_review' and review['manifest_sha256']==sha(OUT/'manifest.json')
    assert manifest['evidence_sha256']==sha(ROOT/'research/western-presentation/bonus-whiskey.json')
    fbx=OUT/manifest['fbx']; assert sha(fbx)==manifest['sha256']
    before=snapshot(); report={'ok':False}
    try:
        materials={n:material(n,n.endswith('ClearGlass')) for n in manifest['materials']}
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
        for k,v in dict(filename=str(fbx),destination_path='/Game/Art/ActionProps/Meshes',destination_name=manifest['name'],
            automated=True,replace_existing=True,save=False,options=options,factory=unreal.FbxFactory()).items(): task.set_editor_property(k,v)
        TOOLS.import_asset_tasks([task]); mesh=next(o for o in task.get_objects() if isinstance(o,unreal.StaticMesh))
        for i,slot in enumerate(mesh.get_editor_property('static_materials')):
            name=str(slot.get_editor_property('imported_material_slot_name')); assert name in materials,name
            mesh.set_material(i,materials[name])
        assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
        box=mesh.get_bounding_box(); size=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
        assert all(abs(a-b)<.01 for a,b in zip(size,manifest['size_cm'])),size
        report.update(ok=True,asset=mesh.get_path_name(),size_cm=size,triangles=mesh.get_num_triangles(0),
            manifest_sha256=sha(OUT/'manifest.json'),importer_sha256=sha(Path(__file__)))
    finally:
        after=snapshot(); report['existing_content_unchanged']=before==after
        report['preserved_files']=len(before); report['ok']=report['ok'] and before==after
        (OUT/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['ok']; unreal.log('BONUS_WHISKEY_IMPORTED '+json.dumps(report))


if __name__=='__main__': main()
