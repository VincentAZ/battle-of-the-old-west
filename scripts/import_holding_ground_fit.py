"""Author a selected additive, render-only holding ground-fit material.

Run via UnrealEditor-Cmd -run=pythonscript -script=... -nullrhi -unattended.
"""
import ast
import hashlib
import json
import os
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
HOLDING = os.environ.get('OLDWEST_GROUND_FIT_HOLDING', 'post-office')
CONFIGS = {
    'bounty-office': ('ground-fit-bounty-office-v001', 'GroundFitBountyOfficeV001', 'M_BountyOfficeGroundFit'),
    'robbers-roost': ('ground-fit-robbers-roost-v001', 'GroundFitRobbersRoostV001', 'M_RobbersRoostGroundFit'),
    'post-office': ('ground-fit-v001', 'GroundFitV001', 'M_PostOfficeGroundFit'),
    'army-surgeons-tent': ('ground-fit-tent-v001', 'GroundFitTentV001', 'M_ArmySurgeonsTentGroundFit'),
    'rockslide-ridge': ('ground-fit-rockslide-v001', 'GroundFitRockslideV001', 'M_RockslideRidgeGroundFit'),
    'courthouse': ('ground-fit-courthouse-v001', 'GroundFitCourthouseV001', 'M_CourthouseGroundFit'),
    'free-homestead': ('ground-fit-free-homestead-v001', 'GroundFitFreeHomesteadV001', 'M_FreeHomesteadGroundFit'),
    'chuckwagon': ('ground-fit-chuckwagon-v001', 'GroundFitChuckwagonV001', 'M_ChuckwagonGroundFit'),
    'pony-express-station': ('ground-fit-pony-express-station-v001', 'GroundFitPonyExpressStationV001', 'M_PonyExpressStationGroundFit'),
    'gallows': ('ground-fit-gallows-v001', 'GroundFitGallowsV001', 'M_GallowsGroundFit'),
    'lookout-ridge': ('ground-fit-lookout-ridge-v001', 'GroundFitLookoutRidgeV001', 'M_LookoutRidgeGroundFit'),
}
FOLDER, ASSET_FOLDER, MATERIAL = CONFIGS[HOLDING]
TENT = HOLDING == 'army-surgeons-tent'
OUT = ROOT/'art/western/holdings'/FOLDER
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/Western/ExpansionHoldings/'+ASSET_FOLDER
DISK = CONTENT/DEST.removeprefix('/Game/')
LIB = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def node(mat, cls, **values):
    n = EDIT.create_material_expression(mat, getattr(unreal, cls))
    for key, value in values.items():
        n.set_editor_property(key, value)
    return n


def wire(src, pin, dst, name):
    assert EDIT.connect_material_expressions(src, pin, dst, name), (pin, name)


def custom(mat, inputs, code, size=3):
    n = node(mat, 'MaterialExpressionCustom', code=code,
        output_type=getattr(unreal.CustomMaterialOutputType, 'CMOT_FLOAT'+str(size)))
    entries = []
    for name, (src, pin) in inputs.items():
        e = unreal.CustomInput(); e.set_editor_property('input_name', name); entries.append(e)
    n.set_editor_property('inputs', entries)
    for name, (src, pin) in inputs.items():
        wire(src, pin, n, name)
    return n


def main():
    protected = {p: sha(p) for p in CONTENT.rglob('*') if p.is_file() and not p.is_relative_to(DISK)}
    brief = OUT/('winter-render-brief.json' if TENT else 'render-brief.json')
    evidence = json.loads(brief.read_text())
    apron_clearance = float(evidence.get('apron_clearance_cm', .5))
    assert 0 <= apron_clearance <= 5
    for p, digest in evidence['source_records'].items():
        assert sha(ROOT/p) == digest
    spec = json.loads((OUT/'heightmap.json').read_text())
    source = OUT/'T_ArenaGroundHeight.tga'
    assert sha(source) == spec['texture_sha256']
    task = unreal.AssetImportTask()
    for key, value in dict(filename=str(source), destination_path=DEST,
        destination_name='T_ArenaGroundHeight', automated=True, replace_existing=True, save=False).items():
        task.set_editor_property(key, value)
    TOOLS.import_asset_tasks([task])
    height = next(x for x in task.get_objects() if isinstance(x, unreal.Texture2D))
    for key, value in dict(srgb=False, compression_settings=unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        mip_gen_settings=unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS, never_stream=True,
        filter=unreal.TextureFilter.TF_NEAREST, address_x=unreal.TextureAddress.TA_CLAMP,
        address_y=unreal.TextureAddress.TA_CLAMP).items():
        height.set_editor_property(key, value)
    assert LIB.save_loaded_asset(height, only_if_is_dirty=False)
    name = MATERIAL
    mat = LIB.load_asset(DEST+'/'+name) if LIB.does_asset_exist(DEST+'/'+name) else TOOLS.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided', True)
    mat.set_editor_property('tangent_space_normal', False)
    # Expand culling bounds for the thin apron, whose undeformed Z extent is
    # only centimetres. This also caps any unexpected displacement at 2 metres.
    mat.set_editor_property('max_world_position_offset_displacement', 200)
    world = node(mat, 'MaterialExpressionWorldPosition', world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    local = node(mat, 'MaterialExpressionTransformPosition', transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
        transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    wire(world, '', local, '')
    vc = node(mat, 'MaterialExpressionVertexColor')
    rgb = node(mat, 'MaterialExpressionComponentMask', r=True, g=True, b=True, a=False)
    wire(vc, '', rgb, '')
    normal = node(mat, 'MaterialExpressionVertexNormalWS')
    origin = node(mat, 'MaterialExpressionVectorParameter', parameter_name='GroundOrigin', default_value=unreal.LinearColor(0, 0, 0, 1))
    extent = node(mat, 'MaterialExpressionVectorParameter', parameter_name='FoundationExtent', default_value=unreal.LinearColor(225, 133, 60, 1))
    enabled = node(mat, 'MaterialExpressionScalarParameter', parameter_name='FitEnabled', default_value=0)
    region = node(mat, 'MaterialExpressionScalarParameter', parameter_name='Region', default_value=1)
    tex = node(mat, 'MaterialExpressionTextureObject', texture=height, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    sample = custom(mat, {'World': (world, ''), 'Height': (tex, '')}, '''
float2 p=clamp((World.xy+6500)/50,0,259.9999);
float2 cell=floor(p), f=frac(p);
float4 a=Texture2DSampleLevel(Height,HeightSampler,(cell+.5)/261,0);
float4 b=Texture2DSampleLevel(Height,HeightSampler,(cell+float2(1.5,.5))/261,0);
float4 c=Texture2DSampleLevel(Height,HeightSampler,(cell+float2(.5,1.5))/261,0);
float4 d=Texture2DSampleLevel(Height,HeightSampler,(cell+1.5)/261,0);
float4 h=(round(float4(a.r,b.r,c.r,d.r)*255)*256+round(float4(a.g,b.g,c.g,d.g)*255)-32768)/16;
float z,dx,dy;
if(a.b>.5) {
 if(f.y<=f.x) { dx=h.y-h.x;dy=h.w-h.y;z=h.x+dx*f.x+dy*f.y; }
 else { dx=h.w-h.z;dy=h.z-h.x;z=h.x+dx*f.x+dy*f.y; }
} else {
 if(f.x+f.y<=1) { dx=h.y-h.x;dy=h.z-h.x;z=h.x+dx*f.x+dy*f.y; }
 else { dx=h.w-h.z;dy=h.w-h.y;z=h.w-dx*(1-f.x)-dy*(1-f.y); }
}
return float4(z,normalize(float3(-dx/50,-dy/50,1)));
''', 4)
    weight = custom(mat, {'Local': (local, ''), 'Extent': (extent, ''), 'Enabled': (enabled, ''), 'World': (world, '')}, '''
float outside=length(max(abs(Local.xy)-Extent.xy,0));
return smoothstep(0,Extent.z,outside)*Enabled*(max(abs(World.x),abs(World.y))<6450);
''', 1)
    offset = custom(mat, {'Terrain': (sample, ''), 'Origin': (origin, ''), 'Weight': (weight, ''), 'Enabled': (enabled, ''), 'World': (world, '')},
        f'float d=Terrain.x-Origin.z; return float3(0,0,(max(d,d*Weight)+{apron_clearance}*Weight)*Enabled*(max(abs(World.x),abs(World.y))<6450));')
    assert EDIT.connect_material_property(offset, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    # Reuse the exact regional colour expressions without reimporting or editing
    # any regional asset. Pin their source hash in the import evidence.
    regional_source = ROOT/'scripts/import_regional_scenery.py'
    function = next(n for n in ast.parse(regional_source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'ground')
    common = next(ast.literal_eval(n.value) for n in function.body if isinstance(n, ast.Assign) and n.targets[0].id == 'common')
    cases = next(ast.literal_eval(n.value.value) for n in function.body if isinstance(n, ast.Assign) and n.targets[0].id == 'code')
    scan = node(mat, 'MaterialExpressionTextureObject', texture=LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_dirt_aerial_03_diff_4k'))
    terrain_normal = custom(mat, {'Terrain': (sample, '')}, 'return Terrain.yzw;')
    # Region zero became desert after the user's October 9 terrain review.
    # Keep the original winter recipe in the regional source for provenance.
    desert_source = ast.parse((ROOT/'scripts/import_desert_region.py').read_text())
    DESERT = next(ast.literal_eval(n.value) for n in desert_source.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'DESERT')
    regional = custom(mat, {'World': (world, ''), 'Normal': (terrain_normal, ''), 'Scan': (scan, ''), 'Region': (region, '')},
        common+'\nif(Region<.5) { '+DESERT+' }\nif(Region<1.5) { '+cases['pine']+' }\n'+cases['river'])
    dirt = node(mat, 'MaterialExpressionTextureObject', texture=LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_dirt_diff_4k'))
    colour_code = '''
float3 board=Texture2DSample(Dirt,DirtSampler,World.xy/600).rgb*float3(1.1,1.03,.9);
float grain=lerp(1,dot(board,float3(.2126,.7152,.0722))/.094,.6);
float3 setting=pow(max(Setting,0),2.2)*grain;
'''
    colour_inputs = {'World': (world, ''), 'Setting': (rgb, ''), 'Fade': (vc, 'A'), 'Regional': (regional, ''), 'Dirt': (dirt, ''), 'Enabled': (enabled, '')}
    if HOLDING in ('army-surgeons-tent', 'rockslide-ridge', 'free-homestead', 'chuckwagon', 'gallows', 'robbers-roost'):
        colour_inputs.update({'Local': (local, ''), 'Region': (region, '')})
        colour_code += '''
if(Enabled>.5 && Region<.5) {
 float vegetation=saturate((Setting.g-max(Setting.r,Setting.b)-.015)/.06);
 float exposedBlade=smoothstep(5,11,Local.z);
 float3 bronze=pow(float3(.56,.34,.15),2.2)*grain;
 setting=lerp(setting,lerp(Regional,bronze,exposedBlade),vegetation);
}
'''
    if HOLDING == 'robbers-roost':
        # Reviewed blades end at 31.1 cm; evergreen juniper crowns are separate.
        colour_code = colour_code.replace(
            'float vegetation=saturate((Setting.g-max(Setting.r,Setting.b)-.015)/.06);',
            'float vegetation=saturate((Setting.g-max(Setting.r,Setting.b)-.015)/.06)*(1-smoothstep(32,35,Local.z));')
    colour_code += 'return lerp(lerp(board,Regional,Enabled),setting,saturate(Fade));'
    color = custom(mat, colour_inputs, colour_code)
    assert EDIT.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    fitted_normal = custom(mat, {'Original': (normal, ''), 'Terrain': (sample, ''), 'Weight': (weight, ''), 'Origin': (origin, ''), 'Enabled': (enabled, '')},
        'return normalize(lerp(Original,Terrain.yzw,Terrain.x>Origin.z?Enabled:Weight));')
    assert EDIT.connect_material_property(fitted_normal, '', unreal.MaterialProperty.MP_NORMAL)
    for prop, value in [(unreal.MaterialProperty.MP_ROUGHNESS, .93), (unreal.MaterialProperty.MP_SPECULAR, .25)]:
        assert EDIT.connect_material_property(node(mat, 'MaterialExpressionConstant', r=value), '', prop)
    EDIT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat, only_if_is_dirty=False)
    assert all(sha(p) == digest for p, digest in protected.items())
    report = dict(ok=True, material=mat.get_path_name(), height_texture=height.get_path_name(),
        apron_clearance_cm=apron_clearance,
        protected_files_unchanged=len(protected), heightmap_spec_sha256=sha(OUT/'heightmap.json'),
        regional_shader_source_sha256=sha(regional_source), brief_sha256=sha(brief),
        visual_review='pending native review', source_meshes_and_collision_unchanged=True,
        importer_sha256=sha(Path(__file__)),
        content_sha256={str(p.relative_to(ROOT)):sha(p) for p in DISK.glob('*.uasset')})
    (OUT/'unreal-import.json').write_text(json.dumps(report, indent=2)+'\n')
    unreal.log('HOLDING_GROUND_FIT_IMPORTED')


if __name__ == '__main__':
    main()
