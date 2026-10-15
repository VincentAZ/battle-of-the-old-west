"""Create an additive clear-glass material; preserve every existing Content asset."""
import hashlib
import json
from pathlib import Path
import unreal
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/whiskey/bonus-glass-v003'
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/ActionProps/BonusGlassV003'
NAME = 'M_Bonus_ClearGlass_V003'
LIB = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    brief = json.loads((OUT/'render-brief.json').read_text())
    for path, digest in brief['source_records'].items():
        assert sha(ROOT/path) == digest, path
    assert not LIB.does_asset_exist(DEST+'/'+NAME), 'Keep earlier candidates immutable'
    before = {p:sha(p) for p in CONTENT.rglob('*') if p.is_file()}
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DEST, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    mat.set_editor_property('refraction_method', unreal.RefractionMode.RM_INDEX_OF_REFRACTION)
    mat.set_editor_property('two_sided', False)
    def node(kind, **values):
        item = EDIT.create_material_expression(mat, getattr(unreal, kind))
        for key, value in values.items(): item.set_editor_property(key, value)
        return item
    def prop(item, name):
        assert EDIT.connect_material_property(item, '', getattr(unreal.MaterialProperty, name))
    prop(node('MaterialExpressionConstant3Vector', constant=unreal.LinearColor(1,1,1,1)), 'MP_BASE_COLOR')
    for name,value in [('MP_METALLIC',1),('MP_ROUGHNESS',.08),('MP_OPACITY',.3)]:
        prop(node('MaterialExpressionConstant', r=value), name)
    fresnel = node('MaterialExpressionFresnel', exponent=5., base_reflect_fraction=.04)
    ior = node('MaterialExpressionLinearInterpolate', const_a=1., const_b=1.52)
    assert EDIT.connect_material_expressions(fresnel, '', ior, 'Alpha')
    prop(ior, 'MP_REFRACTION')
    EDIT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat, only_if_is_dirty=False)
    assert all(sha(p)==h for p,h in before.items())
    disk = CONTENT/'Art/ActionProps/BonusGlassV003'
    report = dict(ok=True, material=mat.get_path_name(), brief_sha256=sha(OUT/'render-brief.json'),
        source_script_sha256=sha(Path(__file__)), existing_content_unchanged=len(before),
        properties={key:str(mat.get_editor_property(key)) for key in ['blend_mode','translucency_lighting_mode','refraction_method','two_sided']},
        content_sha256={str(p.relative_to(ROOT)):sha(p)for p in disk.glob('*.uasset')},
        geometry_and_amber_unchanged=True, native_visual_review='pending')
    (OUT/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('BONUS_GLASS_V003_IMPORTED')


if __name__ == '__main__': main()
