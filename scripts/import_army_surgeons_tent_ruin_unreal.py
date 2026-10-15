"""Add the reviewed ArmySurgeonsTent ruin mesh without resaving any existing Content."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT/'game/OldWest/Content'
SOURCE = ROOT/'art/western/holdings/expansion-review-v001/army-surgeons-tent/ruin-source-v004'
OUT = ROOT/'art/western/holdings/expansion-game-v001/army-surgeons-tent/ruin-v001'
DEST = '/Game/Art/Western/ExpansionHoldings/ArmySurgeonsTent'
NAME = 'SM_HoldingRuin_ArmySurgeonsTent'
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
# Dedicated new char material: preserve the existing healthy and soot assets.
material_name='M_CollapsedChar_ArmySurgeonsTent'
assert not LIB.does_asset_exist(DEST+'/Conditions/'+material_name)
material=unreal.AssetToolsHelpers.get_asset_tools().create_asset(material_name,DEST+'/Conditions',unreal.Material,unreal.MaterialFactoryNew())
props(material,dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
mat=unreal.MaterialEditingLibrary
texture=LIB.load_asset(DEST+'/Textures/T_Holding_ArmySurgeonsTent_BaseColor')
assert isinstance(texture,unreal.Texture2D)
sample=mat.create_material_expression(material,unreal.MaterialExpressionTextureSample,-600,0)
sample.set_editor_property('texture',texture)
tint=mat.create_material_expression(material,unreal.MaterialExpressionConstant3Vector,-600,150)
char_tint=json.loads((SOURCE/'authoring.json').read_text())['char_tint_linear']
tint.set_editor_property('constant',unreal.LinearColor(*char_tint,1))
mult=mat.create_material_expression(material,unreal.MaterialExpressionMultiply,-300,0)
assert mat.connect_material_expressions(sample,'RGB',mult,'A')
assert mat.connect_material_expressions(tint,'',mult,'B')
assert mat.connect_material_property(mult,'',unreal.MaterialProperty.MP_BASE_COLOR)
for prop,value,y in [(unreal.MaterialProperty.MP_ROUGHNESS,.96,200),(unreal.MaterialProperty.MP_METALLIC,0,300)]:
    n=mat.create_material_expression(material,unreal.MaterialExpressionConstant,-300,y)
    n.set_editor_property('r',value)
    assert mat.connect_material_property(n,'',prop)
mat.recompile_material(material)
assert LIB.save_loaded_asset(material,only_if_is_dirty=False)
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
print('ARMY_SURGEONS_TENT_RUIN_IMPORTED',flush=True)
