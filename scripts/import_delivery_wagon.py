"""Import the reviewed wagon into its own namespace; never replace old props."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/delivery/wagon-v004'
CONTENT=ROOT/'game/OldWest/Content'
FOLDER='/Game/Art/ActionProps/Delivery'
LIB=unreal.EditorAssetLibrary
EDIT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def snapshot(mutable):
    return {str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*')
            if p.is_file() and str(p.relative_to(CONTENT)) not in mutable}


def material(folder,name,rgb):
    path=folder+'/Materials/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,folder+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat)
    for node_type,value,prop in [
        ('MaterialExpressionConstant3Vector',unreal.LinearColor(*rgb,1),'MP_BASE_COLOR'),
        ('MaterialExpressionConstant',.38 if name.endswith('Iron') else .78,'MP_ROUGHNESS'),
        ('MaterialExpressionConstant',.8 if name.endswith('Iron') else 0.,'MP_METALLIC')]:
        node=EDIT.create_material_expression(mat,getattr(unreal,node_type))
        node.set_editor_property('constant' if node_type.endswith('3Vector') else 'r',value)
        assert EDIT.connect_material_property(node,'',getattr(unreal.MaterialProperty,prop))
    mat.set_editor_property('two_sided',False)
    EDIT.recompile_material(mat);assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat


def import_pack(out,folder,project,evidence):
    manifest=json.loads((out/'manifest.json').read_text());review=json.loads((out/'visual-review.json').read_text())
    assert review['status']=='accepted_for_native_asset_review' and review['manifest_sha256']==sha(out/'manifest.json')
    assert manifest['evidence_sha256']==sha(evidence)
    assert manifest['project_sha256']==sha(out/project)
    for source,digest in manifest.get('sources',{}).items():assert sha(ROOT/source)==digest,source
    relative=folder.removeprefix('/Game/')
    mutable={relative+'/Meshes/'+r['name']+'.uasset' for r in manifest['assets']}
    mutable.update(relative+'/Materials/'+n+'.uasset' for n in manifest['material_linear_rgb'])
    before=snapshot(mutable);report={'ok':False,'assets':[],'permitted_asset_writes':sorted(mutable)}
    try:
        mats={n:material(folder,n,rgb) for n,rgb in manifest['material_linear_rgb'].items()}
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
        for record in manifest['assets']:
            source=out/record['fbx'];assert sha(source)==record['sha256']
            options=unreal.FbxImportUI()
            for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,
                import_animations=False,automated_import_should_detect_type=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():options.set_editor_property(k,v)
            for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
                convert_scene=True,convert_scene_unit=True,force_front_x_axis=False,build_nanite=False,
                normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():options.static_mesh_import_data.set_editor_property(k,v)
            task=unreal.AssetImportTask()
            for k,v in dict(filename=str(source),destination_path=folder+'/Meshes',destination_name=record['name'],
                automated=True,replace_existing=True,save=False,options=options,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
            TOOLS.import_asset_tasks([task]);mesh=next(o for o in task.get_objects() if isinstance(o,unreal.StaticMesh))
            for i,slot in enumerate(mesh.get_editor_property('static_materials')):
                name=str(slot.get_editor_property('imported_material_slot_name'));assert name in mats,name
                mesh.set_material(i,mats[name])
            assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
            box=mesh.get_bounding_box();size=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
            assert all(abs(a-b*100)<.025 for a,b in zip(size,record['size_m'])),(record['name'],size)
            report['assets'].append(dict(asset=mesh.get_path_name(),triangles=mesh.get_num_triangles(0),size_cm=size,
                bounds_min_cm=[box.min.x,box.min.y,box.min.z],bounds_max_cm=[box.max.x,box.max.y,box.max.z]))
        report.update(ok=True,manifest_sha256=sha(out/'manifest.json'),importer_sha256=sha(Path(__file__)))
    finally:
        after=snapshot(mutable);report['existing_content_unchanged']=before==after;report['preserved_files']=len(before)
        report['protected_content_sha256']=before
        report['imported_content_sha256']={p:sha(CONTENT/p) for p in sorted(mutable) if (CONTENT/p).exists()}
        report['ok']=report['ok'] and before==after
        (out/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['ok'];unreal.log('DELIVERY_ASSETS_IMPORTED '+str(out))


def main():
    import_pack(OUT,FOLDER,'Delivery-Wagon.blend',ROOT/'research/western-presentation/delivery-wagon.json')


if __name__=='__main__':main()
