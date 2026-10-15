"""Add the reviewed expansion ruin meshes; retain every existing asset byte."""
from pathlib import Path
import json,hashlib,os
import unreal
R=Path(__file__).resolve().parents[1];G=R/'art/western/holdings/expansion-game-v001';C=R/'game/OldWest/Content'
VERSION=os.environ.get('OLDWEST_COMPLETION_RUINS_VERSION','v001')
assert VERSION in {'v001','v002'}
OUT=G/('completion-ruins-'+VERSION);assert not OUT.exists();OUT.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before={str(p.relative_to(C)):sha(p)for p in C.rglob('*')if p.is_file()};lib=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();ml=unreal.MaterialEditingLibrary
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
def props(o,kw):
 for k,v in kw.items():o.set_editor_property(k,v)
def save(o):assert lib.save_loaded_asset(o,only_if_is_dirty=False)
def imp(p,d,n,opt=None):
 t=unreal.AssetImportTask();props(t,dict(filename=str(p),destination_path=d,destination_name=n,automated=True,replace_existing=False,save=False))
 if opt:props(t,dict(options=opt,factory=unreal.FbxFactory()))
 tools.import_asset_tasks([t]);return t.get_objects()
records={}
try:
 for p in sorted(G.glob('*/completion-exports-'+VERSION+'/export.json')):
  d=json.loads(p.read_text())
  if 'fbx'not in d:continue
  slug=d['slug'];name=''.join(x.title()for x in slug.split('-'));dest='/Game/Art/Western/ExpansionHoldings/'+name;mn='SM_HoldingRuin_'+name;assert not lib.does_asset_exist(dest+'/'+mn);f=p.parent/d['fbx'];assert sha(f)==d['fbx_sha256']
  opt=unreal.FbxImportUI();props(opt,dict(import_mesh=True,import_as_skeletal=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH,import_materials=False,import_textures=False,import_animations=False,automated_import_should_detect_type=False));props(opt.static_mesh_import_data,dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,convert_scene=True,force_front_x_axis=False,convert_scene_unit=True,import_uniform_scale=1.,normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,remove_degenerates=True,build_nanite=False))
  mesh=next(x for x in imp(f,dest,mn,opt)if isinstance(x,unreal.StaticMesh));assert mesh.get_num_sections(0)==1;assert mesh.get_num_triangles(0)==d['triangles']
  folder=dest+'/Conditions/AuthoredRuin';tex=next(x for x in imp(p.parent/d['texture'],folder,'T_'+name+'_AuthoredRuin')if isinstance(x,unreal.Texture2D));tex.set_editor_property('srgb',True);save(tex)
  mat=tools.create_asset('M_'+name+'_AuthoredRuin',folder,unreal.Material,unreal.MaterialFactoryNew());props(mat,dict(two_sided=True));sample=ml.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-400,0);sample.set_editor_property('texture',tex);assert ml.connect_material_property(sample,'RGB',unreal.MaterialProperty.MP_BASE_COLOR);rough=ml.create_material_expression(mat,unreal.MaterialExpressionConstant,-400,200);rough.set_editor_property('r',.96);assert ml.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS);ml.recompile_material(mat);save(mat);mesh.set_material(0,mat);save(mesh);records[slug]=dict(mesh=mesh.get_path_name(),triangles=mesh.get_num_triangles(0),source_export=str(p.relative_to(R)));print('RUIN_IMPORTED',slug,flush=True)
finally:
 after={str(p.relative_to(C)):sha(p)for p in C.rglob('*')if p.is_file()};changed=[p for p,h in before.items()if after.get(p)!=h];report=dict(ok=len(records)==(13 if VERSION=='v001'else 4) and not changed,holdings=records,existing_assets_checked=len(before),existing_assets_changed=changed,new_assets={p:h for p,h in after.items()if p not in before});(OUT/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
 assert not changed,changed
