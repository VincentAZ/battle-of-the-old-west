"""Unreal Editor import helper for the reviewed Survivor_A FBX and PBR maps.

Run by the project owner with -ExecutePythonScript after the Blender export.
Creates assets only under /Game/Art/Survivors/SurvivorA. Does not change a map,
start PIE, retarget animations, or replace runtime characters.
"""
import json
import re
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/oldwest_survivor'
DEST = '/Game/Art/Survivors/SurvivorA'
MESH_NAME = 'SKM_Survivor_A_Cm'
FBX_FILE = SOURCE / 'Survivor_A_Cm.fbx'
assert FBX_FILE.exists(), 'Run export_survivor_centimeters.py first'
SPEC = json.loads((SOURCE / 'survivor-manifest.json').read_text())
LIB = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MAT = unreal.MaterialEditingLibrary
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(WORLD, 'Interchange.FeatureFlags.Import.FBX 0')


def import_task(filename, path, name, options=None, factory=None, replace=False):
    task = unreal.AssetImportTask()
    task.set_editor_property('filename', str(filename))
    task.set_editor_property('destination_path', path)
    task.set_editor_property('destination_name', name)
    task.set_editor_property('automated', True)
    task.set_editor_property('save', True)
    task.set_editor_property('replace_existing', replace)
    if options is not None:
        task.set_editor_property('options', options)
    if factory is not None:
        task.set_editor_property('factory', factory)
    TOOLS.import_asset_tasks([task])
    return task.get_objects()


texture_cache = {}


def texture(filename, usage):
    key = (filename, usage)
    if key in texture_cache:
        return texture_cache[key]
    name = 'T_' + re.sub(r'[^A-Za-z0-9_]', '_', Path(filename).stem) + '_' + usage
    path = DEST + '/Textures/' + name
    if LIB.does_asset_exist(path):
        obj = LIB.load_asset(path)
    else:
        objs = import_task(SOURCE / 'textures' / filename, DEST + '/Textures', name)
        obj = next(o for o in objs if isinstance(o, unreal.Texture2D))
    obj.set_editor_property('srgb', usage == 'Color')
    if usage == 'Normal':
        obj.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
        obj.set_editor_property('flip_green_channel', True)
    elif usage != 'Color':
        obj.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
    LIB.save_loaded_asset(obj)
    texture_cache[key] = obj
    return obj


def scalar(mat, value, property, y):
    node = MAT.create_material_expression(mat, unreal.MaterialExpressionConstant, -200, y)
    node.set_editor_property('r', value)
    MAT.connect_material_property(node, '', property)
    return node


materials = {}
for name, spec in SPEC['materials'].items():
    path = DEST + '/Materials/' + name
    if LIB.does_asset_exist(path):
        materials[name] = LIB.load_asset(path)
        continue
    mat = TOOLS.create_asset(name, DEST + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    uv = MAT.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1000, 0)
    uv.set_editor_property('u_tiling', spec['uv_scale'])
    uv.set_editor_property('v_tiling', spec['uv_scale'])

    def sample(filename, usage, y):
        node = MAT.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -780, y)
        node.set_editor_property('texture', texture(filename, usage))
        if usage == 'Normal':
            node.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif usage != 'Color':
            node.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        MAT.connect_material_expressions(uv, '', node, 'Coordinates')
        return node

    color = MAT.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -580, -200)
    color.set_editor_property('constant', unreal.LinearColor(*spec['base_color'], 1))
    if spec['base_color_texture']:
        albedo = sample(spec['base_color_texture'], 'Color', -280)
        tint = MAT.create_material_expression(mat, unreal.MaterialExpressionMultiply, -320, -100)
        MAT.connect_material_expressions(albedo, 'RGB', tint, 'A')
        MAT.connect_material_expressions(color, '', tint, 'B')
        MAT.connect_material_property(tint, '', unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        MAT.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    if spec['normal_texture']:
        normal = sample(spec['normal_texture'], 'Normal', 150)
        strength = MAT.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -550, 300)
        strength.set_editor_property('constant', unreal.LinearColor(spec['normal_strength'], spec['normal_strength'], 1, 1))
        multiply = MAT.create_material_expression(mat, unreal.MaterialExpressionMultiply, -340, 150)
        normalize = MAT.create_material_expression(mat, unreal.MaterialExpressionNormalize, -120, 150)
        MAT.connect_material_expressions(normal, 'RGB', multiply, 'A')
        MAT.connect_material_expressions(strength, '', multiply, 'B')
        MAT.connect_material_expressions(multiply, '', normalize, 'VectorInput')
        MAT.connect_material_property(normalize, '', unreal.MaterialProperty.MP_NORMAL)
    if spec['roughness_texture']:
        rough = sample(spec['roughness_texture'], 'Mask', 450)
        MAT.connect_material_property(rough, 'R', unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        scalar(mat, spec['roughness'], unreal.MaterialProperty.MP_ROUGHNESS, 450)
    scalar(mat, spec['metallic'], unreal.MaterialProperty.MP_METALLIC, 530)
    scalar(mat, .3, unreal.MaterialProperty.MP_SPECULAR, 610)
    if spec['subsurface']:
        mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_SUBSURFACE)
        subsurface = MAT.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, 750)
        subsurface.set_editor_property('constant', unreal.LinearColor(.35, .10, .045, 1))
        MAT.connect_material_property(subsurface, '', unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    if spec['opacity_texture']:
        mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        mat.set_editor_property('two_sided', True)
        mat.set_editor_property('opacity_mask_clip_value', .33)
        opacity = sample(spec['opacity_texture'], 'Mask', 850)
        MAT.connect_material_property(opacity, 'R', unreal.MaterialProperty.MP_OPACITY_MASK)
    if spec.get('transmission'):
        # A thin, low-opacity glossy shell preserves iris visibility in Unreal.
        mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        scalar(mat, .08, unreal.MaterialProperty.MP_OPACITY, 900)
        scalar(mat, 1.376, unreal.MaterialProperty.MP_REFRACTION, 990)
    MAT.recompile_material(mat)
    LIB.save_loaded_asset(mat)
    materials[name] = mat

# Creating and assigning a material in a commandlet does not enable skeletal
# shader permutations automatically. Without these saved usage flags, -game
# replaces every survivor surface with the default gray material.
for mat in materials.values():
    for usage in (unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH, unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS):
        MAT.set_base_material_usage(mat, usage, True)
        assert MAT.has_material_usage(mat, usage), f'Missing runtime usage on {mat.get_path_name()}'
    MAT.recompile_material(mat)
    LIB.save_loaded_asset(mat)

mesh_path = DEST + '/' + MESH_NAME
mesh = LIB.load_asset(mesh_path) if LIB.does_asset_exist(mesh_path) else None
if mesh is None or mesh.get_editor_property('skeleton') is None:
    options = unreal.FbxImportUI()
    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_as_skeletal', True)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_animations', False)
    options.set_editor_property('automated_import_should_detect_type', False)
    options.skeletal_mesh_import_data.set_editor_property('import_morph_targets', True)
    objs = import_task(FBX_FILE, DEST, MESH_NAME, options, unreal.FbxFactory(), replace=mesh is not None)
    meshes = [o for o in objs if isinstance(o, unreal.SkeletalMesh)]
    assert len(meshes) == 1, f'Expected one combined survivor skeletal mesh: {meshes}'
    mesh = meshes[0]
    for imported in objs:
        LIB.save_loaded_asset(imported)
# The FBX importer returns a live generated skeleton, but commandlet imports
# must explicitly save that dependency; saving only the mesh loses it on reload.
skeleton = mesh.get_editor_property('skeleton')
assert skeleton is not None, 'Survivor must have a saved skeleton'
LIB.save_loaded_asset(skeleton)
physics = mesh.get_editor_property('physics_asset')
if physics is not None:
    LIB.save_loaded_asset(physics)
slots = mesh.get_editor_property('materials')
for slot in slots:
    name = str(slot.get_editor_property('material_slot_name'))
    assert name in materials, f'Unknown survivor material slot {name}'
    slot.set_editor_property('material_interface', materials[name])
mesh.set_editor_property('materials', slots)
LIB.save_loaded_asset(mesh)
report = {'mesh': mesh.get_path_name(), 'skeleton': mesh.get_editor_property('skeleton').get_path_name(),
          'materials': len(slots), 'texture_assets': len(LIB.list_assets(DEST+'/Textures', recursive=True, include_folder=False)),
          'skeletal_material_usage_verified': True, 'morph_target_material_usage_verified': True,
          'units': 'centimeters; unit skeleton root scale',
          'animation_retargeted': False, 'runtime_replacement_performed': False}
(SOURCE / 'unreal-import.json').write_text(json.dumps(report, indent=2) + '\n')
unreal.log('SURVIVOR_IMPORTED ' + json.dumps(report))
