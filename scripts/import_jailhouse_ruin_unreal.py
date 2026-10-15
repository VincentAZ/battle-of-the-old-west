"""Add the reviewed Jailhouse ruin mesh without resaving any existing Content."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT/'game/OldWest/Content'
SOURCE = ROOT/'art/western/holdings/expansion-review-v001/jailhouse/ruin-source-v003'
OUT = ROOT/'art/western/holdings/expansion-game-v001/jailhouse/ruin-v001'
DEST = '/Game/Art/Western/ExpansionHoldings/Jailhouse'
NAME = 'SM_HoldingRuin_Jailhouse'
LIB = unreal.EditorAssetLibrary
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
snapshot = lambda: {str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*') if p.is_file()}
def props(obj, values):
    for key,value in values.items():obj.set_editor_property(key,value)

assert not OUT.exists()
assert not LIB.does_asset_exist(DEST+'/'+NAME)
record=json.loads((SOURCE/'validation.json').read_text())
assert record['status']=='passed'
assert json.loads((SOURCE/'visual-review.json').read_text())['status']=='agent_static_visual_review_passed_native_pending'
fbx=SOURCE/(NAME+'.fbx')
assert sha(fbx)==record['fbx_sha256']
before=snapshot()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
options=unreal.FbxImportUI()
props(options,dict(import_mesh=True,import_as_skeletal=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH,
    import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False))
props(options.static_mesh_import_data,dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
    convert_scene=True,force_front_x_axis=False,convert_scene_unit=True,import_uniform_scale=1.,
    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
    remove_degenerates=True,build_nanite=False))
task=unreal.AssetImportTask()
props(task,dict(filename=str(fbx),destination_path=DEST,destination_name=NAME,automated=True,
    replace_existing=False,save=False,options=options,factory=unreal.FbxFactory()))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
assert mesh.get_num_sections(0)==1 and mesh.get_num_triangles(0)==record['triangles']
material=LIB.load_asset(DEST+'/Conditions/M_Ruin_M_Holding_Jailhouse')
assert material
mesh.set_material(0,material)
mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
box=mesh.get_bounding_box()
assert abs(box.min.z)<.1
after=snapshot()
assert all(after.get(p)==h for p,h in before.items()),'Existing Content changed'
OUT.mkdir()
(OUT/'unreal-import.json').write_text(json.dumps(dict(ok=True,mesh=mesh.get_path_name(),material=material.get_path_name(),
    triangles=mesh.get_num_triangles(0),min_cm=[box.min.x,box.min.y,box.min.z],max_cm=[box.max.x,box.max.y,box.max.z],
    fbx_sha256=sha(fbx),existing_content_files_checked=len(before),existing_content_unchanged=True,
    new_assets={p:h for p,h in after.items() if p not in before}),indent=2)+'\n')
print('JAILHOUSE_RUIN_IMPORTED',flush=True)
