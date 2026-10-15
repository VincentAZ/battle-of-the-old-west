"""Import generated fractured debris and ash drift assets with authored materials."""
import json
from pathlib import Path
import unreal
R=Path(__file__).resolve().parents[1]
E=unreal.EditorAssetLibrary;T=unreal.AssetToolsHelpers.get_asset_tools()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
for item in json.loads((R/'art/camps/ruin-debris/manifest.json').read_text()):
    options=unreal.FbxImportUI()
    for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False).items():options.set_editor_property(k,v)
    options.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
    for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,convert_scene_unit=True,import_uniform_scale=1.,normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,remove_degenerates=True,build_nanite=False).items():options.static_mesh_import_data.set_editor_property(k,v)
    task=unreal.AssetImportTask()
    for k,v in dict(filename=item['fbx'],destination_path='/Game/Art/Camps/Ruins/Meshes',destination_name=item['name'],automated=True,save=False,replace_existing=True,options=options,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
    T.import_asset_tasks([task]);meshes=[o for o in task.get_objects() if isinstance(o,unreal.StaticMesh)];assert len(meshes)==1
    mesh=meshes[0]
    for i,slot in enumerate(mesh.get_editor_property('static_materials')):
        name=str(slot.get_editor_property('material_slot_name'))
        root='/Game/Art/Camps/Materials/' if name=='M_Camp_TreeChar' else '/Game/Art/Camps/Ruins/'
        material=E.load_asset(root+name);assert material,(name,item['name']);mesh.set_material(i,material)
    assert mesh.get_num_triangles(0)>30
    E.save_loaded_asset(mesh)
unreal.log('OLDWEST_RUIN_DEBRIS_IMPORTED')
