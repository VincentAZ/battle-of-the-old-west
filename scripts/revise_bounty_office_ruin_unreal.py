"""Replace only the newly reviewed BountyOffice ruin mesh; archive its original asset bytes."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT/'game/OldWest/Content'
SOURCE = ROOT/'art/western/holdings/expansion-review-v001/bounty-office/ruin-source-v003'
OUT = ROOT/'art/western/holdings/expansion-game-v001/bounty-office/ruin-v002'
DEST = '/Game/Art/Western/ExpansionHoldings/BountyOffice'
NAME = 'SM_HoldingRuin_BountyOffice'
LIB = unreal.EditorAssetLibrary
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
snapshot = lambda: {str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*') if p.is_file()}
def props(obj, values):
    for key,value in values.items():obj.set_editor_property(key,value)

assert not OUT.exists()
assert LIB.does_asset_exist(DEST+'/'+NAME)
assert LIB.does_asset_exist(DEST+'/Conditions/AuthoredRuin/M_BountyOffice_AuthoredRuin')
record=json.loads((SOURCE/'validation.json').read_text())
assert record['status']=='passed'
assert json.loads((SOURCE/'visual-review.json').read_text())['status']=='agent_static_visual_review_passed_native_pending'
fbx=SOURCE/(NAME+'.fbx')
assert sha(fbx)==record['fbx_sha256']
before=snapshot()
relative=Path(DEST.removeprefix('/Game/'))/(NAME+'.uasset')
OUT.mkdir()
(OUT/(NAME+'.uasset.before')).write_bytes((CONTENT/relative).read_bytes())
assert json.loads((SOURCE/'support-validation.json').read_text())['status']=='passed' 
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
    replace_existing=True,save=False,options=options,factory=unreal.FbxFactory()))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
assert mesh.get_num_sections(0)==1 and mesh.get_num_triangles(0)==record['triangles']
# Geometry-only revision: retain the exact previously imported atlas/material.
texture_path=SOURCE/'BountyOffice_Ruin_BaseColor.png'
authoring=json.loads((SOURCE/'authoring.json').read_text())
prior=ROOT/'art/western/holdings/expansion-review-v001/bounty-office/ruin-source-v002/BountyOffice_Ruin_BaseColor.png'
assert sha(texture_path)==sha(prior)
material=LIB.load_asset(DEST+'/Conditions/AuthoredRuin/M_BountyOffice_AuthoredRuin')
assert isinstance(material,unreal.Material)
mesh.set_material(0,material)
mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
box=mesh.get_bounding_box()
assert abs(box.min.z)<.1
after=snapshot()
assert all(after.get(p)==h for p,h in before.items() if p!=str(relative)),'Unrelated Content changed'
(OUT/'unreal-import.json').write_text(json.dumps(dict(ok=True,mesh=mesh.get_path_name(),material=material.get_path_name(),
    triangles=mesh.get_num_triangles(0),min_cm=[box.min.x,box.min.y,box.min.z],max_cm=[box.max.x,box.max.y,box.max.z],
    fbx_sha256=sha(fbx),texture_sha256=sha(texture_path),existing_content_files_checked=len(before),unrelated_content_unchanged=True,
    previous_mesh_sha256=before[str(relative)],revised_mesh_sha256=after[str(relative)],
    new_assets={p:h for p,h in after.items() if p not in before}),indent=2)+'\n')
print('BOUNTY_OFFICE_RUIN_IMPORTED',flush=True)
