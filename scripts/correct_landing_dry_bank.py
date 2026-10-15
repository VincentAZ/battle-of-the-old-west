"""Preserve the split-fit base and author the measured v003 apron lift."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/ground-fit-smugglers-landing-v002/dry-bank-v003'
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002'
LIB, EDIT = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads((OUT/'render-brief.json').read_text())
assert all(sha(ROOT/p)==h for p,h in brief['source_records'].items())
before = {p:sha(p) for p in CONTENT.rglob('*') if p.is_file()}
target = DEST+'/M_LandingDryBankV003'
assert not LIB.does_asset_exist(target)
mat = LIB.duplicate_asset(DEST+'/M_LandingDryBank',target)
assert mat
node = EDIT.get_material_property_input_node(mat,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
assert isinstance(node,unreal.MaterialExpressionCustom)
code = node.get_editor_property('code')
old = '1.5*smoothstep(280,355,-local.y)'
assert code.count(old)==1
node.set_editor_property('code',code.replace(old,'1.5*smoothstep(270,330,-local.y)'))
EDIT.recompile_material(mat)
assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
assert all(sha(p)==h for p,h in before.items())
file = CONTENT/target.removeprefix('/Game/')
file = file.with_suffix('.uasset')
report = dict(ok=True,material=mat.get_path_name(),material_sha256=sha(file),
    existing_content_unchanged=len(before),brief_sha256=sha(OUT/'render-brief.json'),
    source_script_sha256=sha(Path(__file__)),native_review='pending')
(OUT/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
unreal.log('LANDING_DRY_BANK_V003_CREATED')
