"""Import only a separate reveal cloth mesh/material; preserve existing content."""
import hashlib
import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/drifter/reveal-bandana-v001/prop-v002'
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/Western/Reveal'
LIB = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
def props(obj, **values):
    for key, value in values.items():
        obj.set_editor_property(key, value)
def snapshot():
    return {str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*')
            if p.is_file() and not p.is_relative_to(CONTENT/'Art/Western/Reveal')}

manifest = json.loads((OUT/'manifest.json').read_text())
review = json.loads((OUT/'visual-review.json').read_text())
assert review['status'] == 'accepted_for_native_review'
assert review['manifest_sha256'] == sha(OUT/'manifest.json')
assert sha(OUT/manifest['fbx']) == manifest['fbx_sha256']
assert sha(ROOT/manifest['approved_drifter_source']) == manifest['approved_drifter_sha256']
assert not LIB.does_asset_exist(DEST+'/SM_Reveal_Bandana')
assert not LIB.does_asset_exist(DEST+'/M_Reveal_Bandana')
before = snapshot()
(OUT/'content-before.json').write_text(json.dumps(before, indent=2)+'\n')
report = dict(ok=False)
try:
    material = LIB.duplicate_asset(manifest['unreal_material'].split('.')[0], DEST+'/M_Reveal_Bandana')
    assert isinstance(material, unreal.Material)
    props(material, two_sided=True)
    unreal.MaterialEditingLibrary.recompile_material(material)
    assert LIB.save_loaded_asset(material, only_if_is_dirty=False)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    options = unreal.FbxImportUI()
    props(options, import_mesh=True, import_as_skeletal=False, import_materials=False, import_textures=False,
          import_animations=False, automated_import_should_detect_type=False,
          mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH)
    props(options.static_mesh_import_data, combine_meshes=True, auto_generate_collision=False,
          generate_lightmap_u_vs=False, convert_scene=True, convert_scene_unit=True,
          force_front_x_axis=False, build_nanite=False,
          normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task = unreal.AssetImportTask()
    props(task, filename=str(OUT/manifest['fbx']), destination_path=DEST, destination_name=manifest['name'],
          automated=True, replace_existing=False, save=False, options=options, factory=unreal.FbxFactory())
    TOOLS.import_asset_tasks([task])
    mesh = next(o for o in task.get_objects() if isinstance(o, unreal.StaticMesh))
    mesh.set_material(0, material)
    assert LIB.save_loaded_asset(mesh, only_if_is_dirty=False)
    box = mesh.get_bounding_box()
    size = [box.max.x-box.min.x, box.max.y-box.min.y, box.max.z-box.min.z]
    assert all(abs(a-b) < .05 for a,b in zip(size, manifest['size_cm'])), size
    report.update(ok=True, asset=mesh.get_path_name(), size_cm=size, triangles=mesh.get_num_triangles(0),
                  material=material.get_path_name(), manifest_sha256=sha(OUT/'manifest.json'))
finally:
    report['existing_content_unchanged'] = before == snapshot()
    report['preserved_content_files'] = len(before)
    report['ok'] = report['ok'] and report['existing_content_unchanged']
    (OUT/'unreal-import.json').write_text(json.dumps(report, indent=2)+'\n')
assert report['ok']
unreal.log('REVEAL_BANDANA_IMPORTED '+json.dumps(report))
