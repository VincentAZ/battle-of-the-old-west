"""Give the terrain exact arena collision and Nanite rendering in Unreal.

Run as an editor Python commandlet after export_terrain_collision.py. A separate
fresh process with -TerrainOptimizationVerifyOnly checks persisted settings.
No level or source terrain is modified. The existing material receives only
the Nanite shader-usage flag; its color and surface expression graph are kept.
"""
import hashlib
import json
import shutil
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/world'
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/WaterDepotV2/Meshes'
TERRAIN = DEST+'/SM_ContinuousTerrain'
COLLISION = DEST+'/SM_ContinuousTerrain_Collision'
VERIFY = '-TerrainOptimizationVerifyOnly' in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
EDIT = (unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        or unreal.get_default_object(unreal.StaticMeshEditorSubsystem))
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
preserve = [OUT/'ContinuousTerrain.blend', OUT/'ContinuousTerrain.fbx',
    CONTENT/'Maps/WaterDepotV2.umap', CONTENT/'Maps/WaterDepotV2_ArtStudyBackup.umap']
hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in preserve}
geometry = json.loads((OUT/'terrain-collision-geometry.json').read_text())
assert geometry['ok'] and geometry['exact_source_vertices_and_faces']
assert hashes['art/world/ContinuousTerrain.blend'] == geometry['source_sha256'], 'Re-export collision after changing the terrain source'

if not VERIFY:
    backup = OUT/'backups/SM_ContinuousTerrain-before-runtime-optimization.uasset'
    if not backup.exists():
        shutil.copy2(CONTENT/'Art/WaterDepotV2/Meshes/SM_ContinuousTerrain.uasset', backup)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    options = unreal.FbxImportUI()
    for key, value in {'import_mesh': True, 'import_as_skeletal': False,
        'import_materials': False, 'import_textures': False, 'import_animations': False,
        'automated_import_should_detect_type': False}.items():
        options.set_editor_property(key, value)
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    data = options.static_mesh_import_data
    data.combine_meshes = True
    data.auto_generate_collision = False
    data.generate_lightmap_u_vs = False
    task = unreal.AssetImportTask()
    for key, value in {'filename': str(OUT/'ContinuousTerrain_Collision.fbx'),
        'destination_path': DEST, 'destination_name': 'SM_ContinuousTerrain_Collision',
        'options': options, 'factory': unreal.FbxFactory(), 'automated': True,
        'replace_existing': True, 'save': True}.items():
        task.set_editor_property(key, value)
    TOOLS.import_asset_tasks([task])

terrain, collision = LIB.load_asset(TERRAIN), LIB.load_asset(COLLISION)
assert isinstance(terrain, unreal.StaticMesh) and isinstance(collision, unreal.StaticMesh)
assert collision != terrain
body = terrain.get_editor_property('body_setup')
material = terrain.get_material(0)
if not VERIFY:
    material_file = CONTENT/'Art/WaterDepotV2/Materials/M_ContinuousTerrain.uasset'
    material_backup = OUT/'backups/M_ContinuousTerrain-before-nanite-usage.uasset'
    if not material_backup.exists():
        shutil.copy2(material_file, material_backup)
    unreal.MaterialEditingLibrary.set_base_material_usage(material, unreal.MaterialUsage.MATUSAGE_NANITE, True)
    unreal.MaterialEditingLibrary.recompile_material(material)
    assert LIB.save_loaded_asset(material, only_if_is_dirty=False)
    collision_body = collision.get_editor_property('body_setup')
    collision_body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    assert LIB.save_loaded_asset(collision, only_if_is_dirty=False)
    # This property edit invalidates/rebuilds physics through UStaticMesh's
    # PostEditChangeProperty, so its cooked shape uses the separate arena mesh.
    terrain.set_editor_property('complex_collision_mesh', collision)
    body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    nanite = EDIT.get_nanite_settings(terrain)
    nanite.set_editor_property('enabled', True)
    # Preserve a full-detail conventional fallback; the Nanite mesh itself
    # streams by visible detail. This does not simplify the authored surface.
    nanite.set_editor_property('fallback_relative_error', 0.0)
    nanite.set_editor_property('fallback_percent_triangles', 1.0)
    EDIT.set_nanite_settings(terrain, nanite, True)
    assert LIB.save_loaded_asset(terrain, only_if_is_dirty=False)

nanite = EDIT.get_nanite_settings(terrain)
assert nanite.get_editor_property('enabled')
assert float(nanite.get_editor_property('fallback_relative_error')) == 0.0
assert float(nanite.get_editor_property('fallback_percent_triangles')) == 1.0
assert terrain.get_editor_property('complex_collision_mesh') == collision
assert 'USE_COMPLEX_AS_SIMPLE' in str(body.get_editor_property('collision_trace_flag'))
bounds = collision.get_bounds()
assert abs(bounds.box_extent.x*2-13000) < 1 and abs(bounds.box_extent.y*2-13000) < 1
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected for path, expected in hashes.items())
report = dict(ok=True, fresh_reload=VERIFY, terrain=terrain.get_path_name(),
    collision_mesh=collision.get_path_name(), collision_triangles=geometry['triangles'],
    collision_extent_m=[-65, 65], nanite_enabled=True, full_detail_fallback=True,
    preserved_sha256=hashes, runtime_ground_contact_verified=False, visual_review_passed=False)
report['nanite_material_usage'] = unreal.MaterialEditingLibrary.has_material_usage(
    material, unreal.MaterialUsage.MATUSAGE_NANITE)
assert report['nanite_material_usage'], 'Nanite material would fall back in the game runtime'
report['material_change'] = 'Nanite shader-usage flag enabled; expression graph and visual values unchanged'
filename = 'terrain-runtime-optimization-validation.json' if VERIFY else 'terrain-runtime-optimization.json'
(OUT/filename).write_text(json.dumps(report, indent=2)+'\n')
unreal.log('TERRAIN_RUNTIME_OPTIMIZED '+json.dumps(report))
