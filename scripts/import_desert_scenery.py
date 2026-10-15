"""Import additive dunes/cacti; preserve all prior materials and source assets."""
import hashlib
import json
import sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import import_regional_scenery as base
OUT=ROOT/'art/western/regions/desert-v004'
LIB,EDIT=unreal.EditorAssetLibrary,unreal.MaterialEditingLibrary
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert manifest['brief_sha256']==sha(ROOT/'research/western-presentation/desert-v002.json')
    content=ROOT/'game/OldWest/Content'
    before={p:sha(p) for p in content.rglob('*') if p.is_file()}
    mats={}
    for name,rgb in manifest['material_linear_rgb'].items():
        assert not LIB.does_asset_exist(base.BASE+'/Materials/'+name)
        if name=='M_Region_DuneSandV004':
            mat=LIB.duplicate_asset(base.BASE+'/Materials/M_Region_DesertGround',base.BASE+'/Materials/'+name)
            original=EDIT.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR)
            world=EDIT.create_material_expression(mat,unreal.MaterialExpressionWorldPosition)
            vc=EDIT.create_material_expression(mat,unreal.MaterialExpressionVertexColor)
            grain=base.custom(mat,['Base','World','Fade'],'''
float wave=sin(World.x/9+sin(World.y/220)*2.5);
float3 sand=Base*float3(1.10,1.02,.83)*(.97+.03*wave);
return lerp(Base,sand,saturate(Fade));''')
            for src,out,pin in [(original,'','Base'),(world,'','World'),(vc,'A','Fade')]:
                assert EDIT.connect_material_expressions(src,out,grain,pin)
            assert EDIT.connect_material_property(grain,'',unreal.MaterialProperty.MP_BASE_COLOR)
            normal=EDIT.create_material_expression(mat,unreal.MaterialExpressionVertexNormalWS)
            ripples=base.custom(mat,['World','Normal','Fade'],
                'return normalize(Normal+float3(.075*cos(World.x/9+sin(World.y/220)*2.5),.014*cos(World.y/220),0)*saturate(Fade));')
            for src,out,pin in [(world,'','World'),(normal,'','Normal'),(vc,'A','Fade')]:
                assert EDIT.connect_material_expressions(src,out,ripples,pin)
            mat.set_editor_property('tangent_space_normal',False)
            assert EDIT.connect_material_property(ripples,'',unreal.MaterialProperty.MP_NORMAL)
            mats[name]=base.finish(mat)
        else:mats[name]=base.finish(base.material(name,rgb))
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    imports=[]
    for record in manifest['assets']:
        file=OUT/record['fbx'];assert sha(file)==record['sha256']
        opts=unreal.FbxImportUI()
        for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,
            import_animations=False,automated_import_should_detect_type=False,
            mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():opts.set_editor_property(k,v)
        for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
            convert_scene=True,convert_scene_unit=True,force_front_x_axis=False,build_nanite=False,
            vertex_color_import_option=unreal.VertexColorImportOption.REPLACE,
            normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():opts.static_mesh_import_data.set_editor_property(k,v)
        task=unreal.AssetImportTask()
        for k,v in dict(filename=str(file),destination_path=base.BASE+'/Meshes',destination_name=record['name'],
            automated=True,replace_existing=False,save=False,options=opts,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
        base.TOOLS.import_asset_tasks([task]);mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
        for index,slot in enumerate(mesh.get_editor_property('static_materials')):
            name=str(slot.get_editor_property('imported_material_slot_name'));mesh.set_material(index,mats[name])
        assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
        imports.append(dict(asset=mesh.get_path_name(),triangles=mesh.get_num_triangles(0)))
    assert all(sha(p)==h for p,h in before.items())
    (OUT/'unreal-import.json').write_text(json.dumps(dict(ok=True,assets=imports,
        existing_content_unchanged=len(before),brief_sha256=manifest['brief_sha256'],visual_review='pending'),indent=2)+'\n')
    unreal.log('DESERT_SCENERY_IMPORTED')

if __name__=='__main__':main()
