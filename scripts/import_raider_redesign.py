"""Unreal Python: import baked Raider assets at the dedicated Redesign runtime paths."""
import unreal, json, hashlib, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art/vehicles/raiders/redesign/game-export'
SPEC=json.loads((ART/'export.json').read_text())
BASE='/Game/Art/Vehicles/Raiders';DEST=BASE+'/Redesign'
lib=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();edit=unreal.MaterialEditingLibrary
report={'source_sha256':SPEC['source_sha256'],'materials':[],'meshes':[],'textures':[]}
for asset in SPEC['assets']:
 assert hashlib.sha256((ART/asset['file']).read_bytes()).hexdigest()==asset['sha256']
for spec in SPEC['bakes'].values():
 for texture in spec['textures'].values():assert hashlib.sha256((ART/texture['file']).read_bytes()).hexdigest()==texture['sha256']
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')

def expression(mat,cls):return edit.create_material_expression(mat,cls)
def scalar(mat,value,prop):
 node=expression(mat,unreal.MaterialExpressionConstant);node.set_editor_property('r',value);edit.connect_material_property(node,'',prop)
def material(name):
 path=DEST+'/Materials/'+name
 m=lib.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
 edit.delete_all_material_expressions(m);m.set_editor_property('two_sided',True);return m
materials={}
for key,bake in SPEC['bakes'].items():
 m=material('M_Raider_'+key)
 for kind,texspec in bake['textures'].items():
  path=ART/texspec['file'];name=path.stem
  task=unreal.AssetImportTask();task.filename=str(path);task.destination_path=DEST+'/Textures';task.destination_name=name
  task.automated=True;task.replace_existing=True;task.save=False;tools.import_asset_tasks([task])
  loaded=task.get_objects();assert loaded,path;tex=loaded[0]
  tex.set_editor_property('srgb',kind=='BaseColor')
  tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if kind=='Normal' else unreal.TextureCompressionSettings.TC_MASKS if kind=='ORM' else unreal.TextureCompressionSettings.TC_DEFAULT)
  if kind=='Normal':tex.set_editor_property('flip_green_channel',True)
  tex.set_editor_property('max_texture_size',bake['size']);tex.set_editor_property('lod_bias',0)
  lib.save_loaded_asset(tex)
  node=expression(m,unreal.MaterialExpressionTextureSample);node.set_editor_property('texture',tex)
  node.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if kind=='Normal' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS if kind=='ORM' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
  if kind=='ORM':
   for channel,prop in [('R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),('G',unreal.MaterialProperty.MP_ROUGHNESS),('B',unreal.MaterialProperty.MP_METALLIC)]:edit.connect_material_property(node,channel,prop)
  else:edit.connect_material_property(node,'RGB',unreal.MaterialProperty.MP_NORMAL if kind=='Normal' else unreal.MaterialProperty.MP_BASE_COLOR)
  report['textures'].append({'path':tex.get_path_name(),'source_sha256':texspec['sha256']})
 edit.recompile_material(m);assert lib.save_loaded_asset(m)
 materials['M_Raider_'+key]=m;report['materials'].append(m.get_path_name())
glass=material('M_Raider_Glass');glass.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
node=expression(glass,unreal.MaterialExpressionConstant3Vector);node.set_editor_property('constant',unreal.LinearColor(.035,.05,.045,1));edit.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
scalar(glass,.24,unreal.MaterialProperty.MP_OPACITY);scalar(glass,.16,unreal.MaterialProperty.MP_ROUGHNESS)
edit.recompile_material(glass);assert lib.save_loaded_asset(glass);materials['M_Raider_Glass']=glass;report['materials'].append(glass.get_path_name())
for asset in SPEC['assets']:
 native=ROOT/'game/OldWest/Content/Art/Vehicles/Raiders'/(asset['name']+'.uasset')
 backup=ART/'previous-native'/native.name
 if native.is_file() and not backup.exists():backup.parent.mkdir(exist_ok=True);shutil.copy2(native,backup)
 opts=unreal.FbxImportUI()
 for k,v in {'import_mesh':True,'import_as_skeletal':False,'import_materials':False,'import_textures':False,'import_animations':False,'automated_import_should_detect_type':False}.items():opts.set_editor_property(k,v)
 opts.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
 for k,v in {'combine_meshes':True,'auto_generate_collision':False,'generate_lightmap_u_vs':False,'convert_scene_unit':True,'import_uniform_scale':1.0,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,'remove_degenerates':True,'build_nanite':False}.items():opts.static_mesh_import_data.set_editor_property(k,v)
 task=unreal.AssetImportTask();task.filename=str(ART/asset['file']);task.destination_path=DEST+'/Meshes';task.destination_name=asset['name'];task.automated=True;task.replace_existing=True;task.save=False;task.options=opts;task.factory=unreal.FbxFactory()
 tools.import_asset_tasks([task]);meshes=[o for o in task.get_objects() if isinstance(o,unreal.StaticMesh)];assert len(meshes)==1
 mesh=meshes[0];bindings=[]
 for i,slot in enumerate(mesh.get_editor_property('static_materials')):
  name=str(slot.get_editor_property('imported_material_slot_name'))
  assert name in materials,(asset['name'],name,list(materials))
  mesh.set_material(i,materials[name]);bindings.append(materials[name].get_path_name())
 assert len(bindings)==len(asset['materials']),(asset['name'],bindings,asset['materials'])
 box=mesh.get_bounding_box();lo=[box.min.x,box.min.y,box.min.z];hi=[box.max.x,box.max.y,box.max.z]
 expected_lo=[asset['bounds_min_m'][0]*100,-asset['bounds_max_m'][1]*100,asset['bounds_min_m'][2]*100]
 expected_hi=[asset['bounds_max_m'][0]*100,-asset['bounds_min_m'][1]*100,asset['bounds_max_m'][2]*100]
 assert max(abs(a-b) for a,b in zip(lo+hi,expected_lo+expected_hi))<.3,(asset['name'],lo,hi,expected_lo,expected_hi)
 assert lib.save_loaded_asset(mesh)
 report['meshes'].append({'path':mesh.get_path_name(),'source_sha256':asset['sha256'],'triangles':asset['triangles'],'materials':bindings,'bounds_min_cm':lo,'bounds_max_cm':hi})
assert lib.save_directory(BASE,only_if_is_dirty=True,recursive=True)
report['asset_files']=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ROOT/'game/OldWest/Content/Art/Vehicles/Raiders').rglob('*.uasset')]
(ART/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
unreal.log('RAIDER_REDESIGN_IMPORTED '+json.dumps(report))
