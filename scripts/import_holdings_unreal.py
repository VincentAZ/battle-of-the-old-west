"""Import the 34 static Holdings into /Game/Art/Western/Holdings.

UnrealEditor-Cmd OldWest.uproject -run=pythonscript -script=<this> -nullrhi -unattended
Set OLDWEST_HOLDINGS_VERIFY_ONLY=1 for an independent readback of saved assets.

Each holding gets SM_Holding_<Name>, M_Holding_<Name> (approved atlas PBR with
the review's 0.3 normal strength, 0.6 roughness floor and zero metallic), and
damage/ruin variants under Conditions/ for UOldWestCampVisuals. Existing
Content outside the Holdings folder must stay byte-identical.

From game-v002 each holding also gets SM_HoldingBase_<Name> (its irregular,
setting-specific ground, vertex coloured, shared M_HoldingBase) and, for river
holdings, SM_HoldingWater_<Name> with M_HoldingWater: muddy water whose two
ripple layers pan in different directions so the surface moves. The game
directory follows OLDWEST_HOLDINGS_REVIEW (default review-v002 -> game-v002).
OLDWEST_HOLDINGS_ONLY=slug,slug limits a trial import.
"""
import hashlib, json, os, sys, traceback
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from holdings_roster import HOLDINGS, REVIEW, HOLDINGS_SET  # noqa: E402
GAME = ROOT / 'art/western/holdings' / REVIEW.name.replace('review-', 'game-')
ONLY = [x for x in os.environ.get('OLDWEST_HOLDINGS_ONLY', '').split(',') if x]
# Vertex colours are authored in sRGB; decode them so the base matches the palette.
VERTEX_GAMMA = '2.2'
CONTENT = ROOT / 'game/OldWest/Content'
BASE = '/Game/Art/Western/' + ('ExpansionHoldings' if HOLDINGS_SET == 'boomtown' else 'Holdings')
SHARED = BASE + '/Shared'
DISK = CONTENT / BASE.removeprefix('/Game/')
VERIFY = os.environ.get('OLDWEST_HOLDINGS_VERIFY_ONLY') == '1'
ADDITIVE = os.environ.get('OLDWEST_HOLDINGS_ADDITIVE') == '1'
REPORT_DIR = GAME / os.environ.get('OLDWEST_HOLDINGS_REPORT_SUBDIR', '')
assert REPORT_DIR.resolve().is_relative_to(GAME.resolve())
LIB = unreal.EditorAssetLibrary; MAT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
# Darkening for the existing condition lifecycle: damaged soot, burned-out ruin.
VARIANTS = {'M_Soot_': ((.46, .41, .37), .86), 'M_Ruin_': ((.17, .165, .16), .96)}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(): return {str(p.relative_to(CONTENT)): sha(p) for p in sorted(CONTENT.rglob('*')) if p.is_file() and (ADDITIVE or not p.is_relative_to(DISK))}
def props(obj, values):
    for k, v in values.items(): obj.set_editor_property(k, v)
def save(obj): assert LIB.save_loaded_asset(obj, only_if_is_dirty=False), obj
def load(path, cls):
    obj = LIB.load_asset(path); assert isinstance(obj, cls), (path, cls, obj); return obj


def imp(filename, dest, name, options=None):
    task = unreal.AssetImportTask()
    props(task, dict(filename=str(filename), destination_path=dest, destination_name=name,
                     automated=True, replace_existing=True, save=False))
    if options: props(task, dict(options=options, factory=unreal.FbxFactory()))
    TOOLS.import_asset_tasks([task]); return list(task.get_objects())


def node(mat, kind, x, y, **values):
    n = MAT.create_material_expression(mat, getattr(unreal, kind), x, y)
    for k, v in values.items(): n.set_editor_property(k, v)
    return n


def author_material(path, textures, tint=None, roughness=None):
    name = path.rsplit('/', 1)[1]; folder = path.rsplit('/', 1)[0]
    mat = LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    MAT.delete_all_material_expressions(mat)
    # Thin generated boards, canvas and fence rails must not vanish from behind.
    props(mat, dict(shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT, blend_mode=unreal.BlendMode.BLEND_OPAQUE, two_sided=True))
    if name == 'M_Ruin_M_Holding_WantedPosterBoard':
        # This reviewed atlas stores timber in its left half and pasted paper
        # in its right half. Burned-out notices are consumed, not white signs.
        props(mat, dict(blend_mode=unreal.BlendMode.BLEND_MASKED))
        uv = node(mat, 'MaterialExpressionTextureCoordinate', -1100, -500)
        mask = node(mat, 'MaterialExpressionCustom', -800, -500,
                    description='Consume paper notices in burned-out board',
                    output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        entry = unreal.CustomInput(); entry.set_editor_property('input_name', 'UV')
        mask.set_editor_property('inputs', [entry])
        mask.set_editor_property('code', 'return UV.x < 0.5 ? 1.0 : 0.0;')
        assert MAT.connect_material_expressions(uv, '', mask, 'UV')
        assert MAT.connect_material_property(mask, '', unreal.MaterialProperty.MP_OPACITY_MASK)
    base = node(mat, 'MaterialExpressionTextureSample', -900, -200, texture=textures['BaseColor'])
    orm = node(mat, 'MaterialExpressionTextureSample', -900, 100, texture=textures['ORM'], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS) if 'ORM' in textures else None
    nrm = node(mat, 'MaterialExpressionTextureSample', -900, 400, texture=textures['Normal'], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL) if 'Normal' in textures else None
    color_out = base
    if tint:
        tint_node = node(mat, 'MaterialExpressionConstant3Vector', -600, -320, constant=unreal.LinearColor(*tint, 1))
        mult = node(mat, 'MaterialExpressionMultiply', -400, -200)
        assert MAT.connect_material_expressions(base, 'RGB', mult, 'A'); assert MAT.connect_material_expressions(tint_node, '', mult, 'B')
        assert MAT.connect_material_property(mult, '', unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        assert MAT.connect_material_property(base, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    if 'Transmission' in textures:
        # Clear authored panes remain open in the opaque architectural pass.
        # Reflection/refraction polish can follow without filling window holes.
        props(mat, dict(blend_mode=unreal.BlendMode.BLEND_MASKED))
        transmission = node(mat, 'MaterialExpressionTextureSample', -900, 650,
            texture=textures['Transmission'], sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        opaque = node(mat, 'MaterialExpressionOneMinus', -600, 650)
        assert MAT.connect_material_expressions(transmission, 'R', opaque, '')
        assert MAT.connect_material_property(opaque, '', unreal.MaterialProperty.MP_OPACITY_MASK)
    if orm:
        assert MAT.connect_material_property(orm, 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    if roughness is None and orm:
        floor = node(mat, 'MaterialExpressionConstant', -600, 160, r=.6)
        rmax = node(mat, 'MaterialExpressionMax', -400, 120)
        assert MAT.connect_material_expressions(orm, 'G', rmax, 'A'); assert MAT.connect_material_expressions(floor, '', rmax, 'B')
        assert MAT.connect_material_property(rmax, '', unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -400, 160, r=.85 if roughness is None else roughness), '', unreal.MaterialProperty.MP_ROUGHNESS)
    assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -400, 260, r=0.), '', unreal.MaterialProperty.MP_METALLIC)
    # Match the approved review's 0.3 normal strength: lerp from a flat normal.
    if nrm:
        flat = node(mat, 'MaterialExpressionConstant3Vector', -600, 380, constant=unreal.LinearColor(0, 0, 1, 1))
        alpha = node(mat, 'MaterialExpressionConstant', -600, 520, r=.3)
        lerp = node(mat, 'MaterialExpressionLinearInterpolate', -400, 420)
        assert MAT.connect_material_expressions(flat, '', lerp, 'A'); assert MAT.connect_material_expressions(nrm, 'RGB', lerp, 'B')
        assert MAT.connect_material_expressions(alpha, '', lerp, 'Alpha')
        assert MAT.connect_material_property(lerp, '', unreal.MaterialProperty.MP_NORMAL)
    MAT.recompile_material(mat); save(mat)
    return mat


def linear(c): return tuple(((x + .055) / 1.055) ** 2.4 if x > .04045 else x / 12.92 for x in c)


def base_material():
    """Setting colour from vertex RGB, given the board dirt's grain, fading into that dirt by vertex alpha."""
    path = SHARED + '/M_HoldingBase'
    if ADDITIVE and LIB.does_asset_exist(path):
        return load(path, unreal.Material)
    mat = LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('M_HoldingBase', SHARED, unreal.Material, unreal.MaterialFactoryNew())
    MAT.delete_all_material_expressions(mat)
    props(mat, dict(shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT, blend_mode=unreal.BlendMode.BLEND_OPAQUE, two_sided=True))
    vc = node(mat, 'MaterialExpressionVertexColor', -1100, -200)
    world = node(mat, 'MaterialExpressionWorldPosition', -1500, 150)
    mask = node(mat, 'MaterialExpressionComponentMask', -1300, 150, r=True, g=True, b=False, a=False)
    assert MAT.connect_material_expressions(world, '', mask, '')
    scale = node(mat, 'MaterialExpressionConstant', -1300, 280, r=1 / 600.)
    uv = node(mat, 'MaterialExpressionMultiply', -1100, 200)
    assert MAT.connect_material_expressions(mask, '', uv, 'A'); assert MAT.connect_material_expressions(scale, '', uv, 'B')
    dirt = node(mat, 'MaterialExpressionTextureSample', -900, 200, texture=load('/Game/Art/WaterDepotV2/Textures/T_dirt_diff_4k', unreal.Texture2D))
    assert MAT.connect_material_expressions(uv, '', dirt, 'UVs')
    blend = node(mat, 'MaterialExpressionCustom', -500, 0, description='Holding base: setting colour with board grain, rim fades to board dirt',
                 output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    entries = []
    for name in ('Setting', 'Fade', 'Dirt'):
        entry = unreal.CustomInput(); entry.set_editor_property('input_name', name); entries.append(entry)
    blend.set_editor_property('inputs', entries)
    # Dirt is tinted exactly as M_ContinuousTerrain tints it; 0.094 is that tinted texture's mean luminance.
    blend.set_editor_property('code', '''
float3 board = Dirt * float3(1.1, 1.03, 0.9);
float grain = lerp(1.0, dot(board, float3(.2126, .7152, .0722)) / 0.094, 0.6);
float3 setting = pow(max(Setting, 0.0), %s) * grain;
return lerp(board, setting, saturate(Fade));
''' % VERTEX_GAMMA)
    rgb = node(mat, 'MaterialExpressionComponentMask', -800, -200, r=True, g=True, b=True, a=False)
    assert MAT.connect_material_expressions(vc, '', rgb, '')
    assert MAT.connect_material_expressions(rgb, '', blend, 'Setting')
    assert MAT.connect_material_expressions(vc, 'A', blend, 'Fade')
    assert MAT.connect_material_expressions(dirt, 'RGB', blend, 'Dirt')
    assert MAT.connect_material_property(blend, '', unreal.MaterialProperty.MP_BASE_COLOR)
    assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -450, 120, r=.93), '', unreal.MaterialProperty.MP_ROUGHNESS)
    assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -450, 200, r=.25), '', unreal.MaterialProperty.MP_SPECULAR)
    MAT.recompile_material(mat); save(mat); return mat


def water_material(normal_texture, color, folder=SHARED):
    path = folder + '/M_HoldingWater'
    mat = LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('M_HoldingWater', folder, unreal.Material, unreal.MaterialFactoryNew())
    MAT.delete_all_material_expressions(mat)
    props(mat, dict(shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT, blend_mode=unreal.BlendMode.BLEND_OPAQUE, two_sided=False))
    base = node(mat, 'MaterialExpressionVectorParameter', -900, -400, parameter_name='WaterColor', default_value=unreal.LinearColor(*linear(color), 1))
    # Portrait captures have no sky to reflect, so a grazing-angle sheen of pale
    # overcast sky keeps the surface reading as water rather than wet sand.
    sky = node(mat, 'MaterialExpressionVectorParameter', -900, -250, parameter_name='SkySheen', default_value=unreal.LinearColor(.32, .36, .40, 1))
    fresnel = node(mat, 'MaterialExpressionFresnel', -900, -120, exponent=3.5, base_reflect_fraction=.04)
    sheen = node(mat, 'MaterialExpressionLinearInterpolate', -600, -300)
    assert MAT.connect_material_expressions(base, '', sheen, 'A'); assert MAT.connect_material_expressions(sky, '', sheen, 'B')
    assert MAT.connect_material_expressions(fresnel, '', sheen, 'Alpha')
    assert MAT.connect_material_property(sheen, '', unreal.MaterialProperty.MP_BASE_COLOR)
    assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -500, -150, r=.07), '', unreal.MaterialProperty.MP_ROUGHNESS)
    assert MAT.connect_material_property(node(mat, 'MaterialExpressionConstant', -500, -80, r=.6), '', unreal.MaterialProperty.MP_SPECULAR)
    # World-aligned UVs: the water mesh carries no UVs and ripples keep one size on every holding.
    world = node(mat, 'MaterialExpressionWorldPosition', -1500, 200)
    mask = node(mat, 'MaterialExpressionComponentMask', -1300, 200, r=True, g=True, b=False, a=False)
    assert MAT.connect_material_expressions(world, '', mask, '')
    samples = []
    for i, (scale, sx, sy) in enumerate(((1 / 260., .045, .015), (1 / 170., -.03, .04))):
        k = node(mat, 'MaterialExpressionConstant', -1300, 360 + i * 260, r=scale)
        uv = node(mat, 'MaterialExpressionMultiply', -1100, 260 + i * 260)
        assert MAT.connect_material_expressions(mask, '', uv, 'A'); assert MAT.connect_material_expressions(k, '', uv, 'B')
        pan = node(mat, 'MaterialExpressionPanner', -900, 260 + i * 260, speed_x=sx, speed_y=sy)
        assert MAT.connect_material_expressions(uv, '', pan, 'Coordinate')
        t = node(mat, 'MaterialExpressionTextureSample', -650, 260 + i * 260, texture=normal_texture, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        assert MAT.connect_material_expressions(pan, '', t, 'UVs')
        samples.append(t)
    add = node(mat, 'MaterialExpressionAdd', -400, 380)
    assert MAT.connect_material_expressions(samples[0], 'RGB', add, 'A'); assert MAT.connect_material_expressions(samples[1], 'RGB', add, 'B')
    norm = node(mat, 'MaterialExpressionNormalize', -200, 380)
    assert MAT.connect_material_expressions(add, '', norm, '')
    assert MAT.connect_material_property(norm, '', unreal.MaterialProperty.MP_NORMAL)
    MAT.recompile_material(mat); save(mat); return mat


def import_static(fbx, dest, name, vertex_colors=False):
    opt = unreal.FbxImportUI()
    props(opt, dict(import_mesh=True, import_as_skeletal=False, mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH,
                    import_materials=False, import_textures=False, import_animations=False, automated_import_should_detect_type=False))
    props(opt.static_mesh_import_data, dict(combine_meshes=True, auto_generate_collision=False, generate_lightmap_u_vs=False,
          convert_scene=True, force_front_x_axis=False, convert_scene_unit=True, import_uniform_scale=1.,
          import_translation=unreal.Vector(0, 0, 0), import_rotation=unreal.Rotator(0, 0, 0),
          normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
          remove_degenerates=True, build_nanite=False,
          vertex_color_import_option=unreal.VertexColorImportOption.REPLACE if vertex_colors else unreal.VertexColorImportOption.IGNORE))
    return next(o for o in imp(fbx, dest, name, opt) if isinstance(o, unreal.StaticMesh))


report = {'ok': False, 'mode': 'readback' if VERIFY else 'import', 'base': BASE, 'additive': ADDITIVE, 'holdings': {}}
before = snapshot()
try:
    if not VERIFY:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    shared = {}
    for card_id, (slug, *_rest) in HOLDINGS.items():
        if ONLY and slug not in ONLY:
            continue
        export = json.loads((GAME / slug / 'export.json').read_text())
        name = export['asset_name']; dest = BASE + '/' + name; out = GAME / slug / 'exports'
        if ADDITIVE and not VERIFY:
            assert not (DISK / name).exists(), 'Additive import must target a new holding folder'
        assert sha(out / export['fbx']) == export['fbx_sha256']
        if not VERIFY:
            textures = {}
            for channel, record in export['textures'].items():
                assert sha(out / record['file']) == record['sha256']
                t = next(o for o in imp(out / record['file'], dest + '/Textures', Path(record['file']).stem) if isinstance(o, unreal.Texture2D))
                t.set_editor_property('srgb', channel == 'BaseColor')
                if channel == 'Normal': props(t, dict(compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP, flip_green_channel=True))
                elif channel in {'ORM', 'Transmission'}: t.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
                save(t); textures[channel] = t
            mat = author_material(dest + '/M_Holding_' + name, textures)
            for prefix, (tint, rough) in VARIANTS.items():
                # The reviewed geological holding fractures; rock does not
                # inherit the building lifecycle's char/soot treatment.
                if HOLDINGS_SET == 'boomtown' and slug in {'rockslide-ridge', 'lookout-ridge'}:
                    tint, rough = None, .92
                author_material(dest + '/Conditions/' + prefix + 'M_Holding_' + name, textures, tint, rough)
            opt = unreal.FbxImportUI()
            props(opt, dict(import_mesh=True, import_as_skeletal=False, mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH,
                            import_materials=False, import_textures=False, import_animations=False, automated_import_should_detect_type=False))
            props(opt.static_mesh_import_data, dict(combine_meshes=True, auto_generate_collision=False, generate_lightmap_u_vs=False,
                  convert_scene=True, force_front_x_axis=False, convert_scene_unit=True, import_uniform_scale=1.,
                  import_translation=unreal.Vector(0, 0, 0), import_rotation=unreal.Rotator(0, 0, 0),
                  normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
                  remove_degenerates=True, build_nanite=False))
            mesh = next(o for o in imp(out / export['fbx'], dest, 'SM_Holding_' + name, opt) if isinstance(o, unreal.StaticMesh))
            assert mesh.get_num_sections(0) == 1, 'Holding must keep one material section'
            mesh.set_material(0, mat)
            body = mesh.get_editor_property('body_setup')
            if body: body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            save(mesh)
            base = export.get('base') or {}
            for asset in ('SM_HoldingBase_' + name, 'SM_HoldingWater_' + name):
                if asset not in base:
                    continue
                assert sha(out / base[asset]['fbx']) == base[asset]['fbx_sha256']
                part = import_static(out / base[asset]['fbx'], dest, asset, vertex_colors=asset.startswith('SM_HoldingBase_'))
                if asset.startswith('SM_HoldingBase_'):
                    shared.setdefault('base', base_material())
                    part.set_material(0, shared['base'])
                else:
                    water_key = dest if base.get('water_color_source') == 'reviewed_base' else 'water'
                    if water_key not in shared:
                        ripples = ROOT / base['water_normal']['file']
                        ripple_path = SHARED + '/T_HoldingWater_Ripples_N'
                        if ADDITIVE and LIB.does_asset_exist(ripple_path):
                            tex = load(ripple_path, unreal.Texture2D)
                        else:
                            tex = next(o for o in imp(ripples, SHARED, 'T_HoldingWater_Ripples_N') if isinstance(o, unreal.Texture2D))
                            props(tex, dict(srgb=False, compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP))
                            save(tex)
                        # Keep per-scene historical water colours independent; an
                        # additive import must never recolour an existing river.
                        folder = dest if water_key == dest else SHARED
                        if ADDITIVE and folder == SHARED and LIB.does_asset_exist(folder + '/M_HoldingWater'):
                            shared[water_key] = load(folder + '/M_HoldingWater', unreal.Material)
                        else:
                            shared[water_key] = water_material(tex, base['water_color_srgb'], folder)
                    part.set_material(0, shared[water_key])
                save(part)
        mesh = load(dest + '/SM_Holding_' + name, unreal.StaticMesh)
        mat = load(dest + '/M_Holding_' + name, unreal.Material)
        assert mesh.get_material(0) == mat
        for prefix in VARIANTS: load(dest + '/Conditions/' + prefix + 'M_Holding_' + name, unreal.Material)
        box = mesh.get_bounding_box()
        size = [box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z]
        expected = sorted(export['expected_unreal_size_cm'][:2]) + [export['expected_unreal_size_cm'][2]]
        actual = sorted(size[:2]) + [size[2]]
        assert all(abs(a - e) < 1.5 for a, e in zip(actual, expected)), (slug, size, expected)
        assert abs(box.min.z) < 1.5, (slug, 'ground', box.min.z)
        report['holdings'][slug] = {'card_id': card_id, 'mesh': mesh.get_path_name(), 'material': mat.get_path_name(),
                                    'size_cm': [round(v, 2) for v in size], 'min_cm': [round(box.min.x, 2), round(box.min.y, 2), round(box.min.z, 2)],
                                    'triangles': mesh.get_num_triangles(0), 'fbx_sha256': export['fbx_sha256'],
                                    'ground': {a: load(dest + '/' + a, unreal.StaticMesh).get_num_triangles(0)
                                               for a in ('SM_HoldingBase_' + name, 'SM_HoldingWater_' + name)
                                               if a in (export.get('base') or {})}}
        unreal.log('HOLDING_UNREAL ' + slug)
    report['ok'] = True
except Exception as exc:
    report['error'] = repr(exc); report['traceback'] = traceback.format_exc(); raise
finally:
    after = snapshot()
    preserved = {p: after.get(p) for p in before} if ADDITIVE else after
    report['existing_content_unchanged'] = before == preserved
    report['existing_content_files_checked'] = len(before)
    if before != preserved: report['ok'] = False
    report['new_assets_sha256'] = {str(p.relative_to(CONTENT)): sha(p) for p in DISK.rglob('*') if p.is_file()} if DISK.exists() else {}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / ('unreal-readback.json' if VERIFY else 'unreal-import.json')).write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('HOLDINGS_IMPORT_AUDIT ' + json.dumps({k: report[k] for k in ('ok', 'mode', 'existing_content_unchanged')} | {'count': len(report['holdings'])}))
