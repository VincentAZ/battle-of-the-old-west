"""Import the authored repair robot into a new, already-cooked Survivor subtree.

Run only in the coordinated Unreal asset-authoring lane after author_repair_bot.
Creates /Game/Art/Survivors/RepairBot assets. Uses the original survivor skeleton
and anatomical physics asset without saving or changing their files. Re-runs
replace only this robot's mesh/material/textures; the originals are hash-guarded.
"""
import hashlib
import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/repair_bot'
DEST = '/Game/Art/Survivors/RepairBot'
BASE = '/Game/Art/Survivors/SurvivorA'
CONTENT = ROOT / 'game/OldWest/Content/Art/Survivors/SurvivorA'
SPEC = json.loads((SOURCE / 'repair-bot-manifest.json').read_text())
LIB, MAT = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
protected = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in CONTENT.rglob('*.uasset')}
assert protected
skeleton = LIB.load_asset(BASE + '/SKM_Survivor_A_Cm_Skeleton')
physics = LIB.load_asset(BASE + '/PA_Survivor_Anatomical')
assert skeleton and physics
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(WORLD, 'Interchange.FeatureFlags.Import.FBX 0')


def import_asset(filename, path, name, options=None, factory=None):
    task = unreal.AssetImportTask()
    for key, value in {'filename': str(filename), 'destination_path': path,
                       'destination_name': name, 'automated': True,
                       'save': False, 'replace_existing': True}.items():
        task.set_editor_property(key, value)
    if options:
        task.set_editor_property('options', options)
    if factory:
        task.set_editor_property('factory', factory)
    TOOLS.import_asset_tasks([task])
    return task.get_objects()


textures = {}
for channel in ['BaseColor', 'Roughness', 'Metallic', 'Normal', 'Emission']:
    path = SOURCE / 'textures' / ('T_RepairBot_' + channel + '.png')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SPEC['textures'][channel]['sha256']
    objects = import_asset(path, DEST + '/Textures', 'T_RepairBot_' + channel)
    tex = next((o for o in objects if isinstance(o, unreal.Texture2D)), None)
    assert tex, 'Texture import failed: ' + channel
    tex.set_editor_property('srgb', channel == 'BaseColor')
    if channel == 'Normal':
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property('flip_green_channel', True)
    elif channel != 'BaseColor':
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
    assert LIB.save_loaded_asset(tex)
    textures[channel] = tex

name = 'M_RepairBot_Atlas'
material_path = DEST + '/Materials/' + name
mat = LIB.load_asset(material_path) if LIB.does_asset_exist(material_path) else None
if not mat:
    mat = TOOLS.create_asset(name, DEST + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
assert mat
MAT.delete_all_material_expressions(mat)
mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)

samples = {}
for index, channel in enumerate(textures):
    node = MAT.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -650, index * 180)
    node.set_editor_property('texture', textures[channel])
    if channel == 'Normal':
        node.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif channel != 'BaseColor':
        node.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    samples[channel] = node
for channel, pin, prop in [('BaseColor', 'RGB', unreal.MaterialProperty.MP_BASE_COLOR),
                           ('Roughness', 'R', unreal.MaterialProperty.MP_ROUGHNESS),
                           ('Metallic', 'R', unreal.MaterialProperty.MP_METALLIC),
                           ('Normal', 'RGB', unreal.MaterialProperty.MP_NORMAL)]:
    assert MAT.connect_material_property(samples[channel], pin, prop), channel
intensity = MAT.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -620, 1020)
intensity.set_editor_property('parameter_name', 'EmissionScale')
intensity.set_editor_property('default_value', 75.0)
emission = MAT.create_material_expression(mat, unreal.MaterialExpressionMultiply, -300, 780)
assert MAT.connect_material_expressions(samples['Emission'], 'RGB', emission, 'A')
assert MAT.connect_material_expressions(intensity, '', emission, 'B')
assert MAT.connect_material_property(emission, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
specular = MAT.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 1100)
specular.set_editor_property('r', .5)
assert MAT.connect_material_property(specular, '', unreal.MaterialProperty.MP_SPECULAR)
MAT.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH, True)
assert MAT.has_material_usage(mat, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
MAT.recompile_material(mat)
assert LIB.save_loaded_asset(mat)

fbx = SOURCE / 'RepairBot_Cm.fbx'
assert hashlib.sha256(fbx.read_bytes()).hexdigest() == SPEC['fbx_sha256']
options = unreal.FbxImportUI()
for key, value in {'import_mesh': True, 'import_as_skeletal': True,
                   'mesh_type_to_import': unreal.FBXImportType.FBXIT_SKELETAL_MESH,
                   'import_materials': False, 'import_textures': False,
                   'import_animations': False, 'automated_import_should_detect_type': False,
                   'create_physics_asset': False, 'skeleton': skeleton,
                   'physics_asset': physics}.items():
    options.set_editor_property(key, value)
for key, value in {'update_skeleton_reference_pose': False, 'use_t0_as_ref_pose': False,
                   'import_morph_targets': False, 'preserve_smoothing_groups': True,
                   'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():
    options.skeletal_mesh_import_data.set_editor_property(key, value)
objects = import_asset(fbx, DEST, 'SKM_RepairBot_Cm', options, unreal.FbxFactory())
meshes = [o for o in objects if isinstance(o, unreal.SkeletalMesh)]
assert len(meshes) == 1, 'Expected one rigid-skinned mechanical assembly'
mesh = meshes[0]
assert mesh.get_editor_property('skeleton') == skeleton, 'Robot lost the animation skeleton'
assert mesh.get_editor_property('physics_asset') == physics, 'Robot lost the existing body rig'
slots = mesh.get_editor_property('materials')
assert len(slots) == 1
slots[0].set_editor_property('material_interface', mat)
mesh.set_editor_property('materials', slots)
assert LIB.save_loaded_asset(mesh)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in protected.items()), 'Original survivor asset was modified'
report = {'mesh': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(),
          'physics_asset': physics.get_path_name(), 'material': mat.get_path_name(),
          'textures': {k: v.get_path_name() for k, v in textures.items()},
          'original_survivor_assets_unchanged': True, 'protected_sha256': protected,
          'source_fbx_sha256': SPEC['fbx_sha256'], 'one_material_section': True,
          'skeletal_material_usage_verified': True,
          'native_animation_physics_and_visual_review_required': True}
(SOURCE / 'unreal-import.json').write_text(json.dumps(report, indent=2) + '\n')
unreal.log('REPAIR_BOT_IMPORTED ' + json.dumps({k: v for k, v in report.items() if k != 'protected_sha256'}))
