"""Version the expansion water normal-space correction; preserve old material."""
import hashlib,json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'art/western/holdings/expansion-game-v001/smugglers-landing/water-v002'
CONTENT=ROOT/'game/OldWest/Content'
DEST='/Game/Art/Western/ExpansionHoldings/SmugglersLanding'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
snapshot=lambda:{str(p.relative_to(CONTENT)):sha(p) for p in CONTENT.rglob('*') if p.is_file()}
before=snapshot();lib=unreal.EditorAssetLibrary
assert not lib.does_asset_exist(DEST+'/M_HoldingWaterWorldV002')
material=lib.duplicate_asset(DEST+'/M_HoldingWater',DEST+'/M_HoldingWaterWorldV002')
assert material
old=material.get_editor_property('tangent_space_normal')
assert old
material.set_editor_property('tangent_space_normal',False)
unreal.MaterialEditingLibrary.recompile_material(material)
assert lib.save_loaded_asset(material,only_if_is_dirty=False)
mesh=lib.load_asset(DEST+'/SM_HoldingWater_SmugglersLanding')
mesh.set_material(0,material)
assert lib.save_loaded_asset(mesh,only_if_is_dirty=False)
after=snapshot();changed={p for p,h in before.items() if after.get(p)!=h}
assert changed=={'Art/Western/ExpansionHoldings/SmugglersLanding/SM_HoldingWater_SmugglersLanding.uasset'},changed
report=dict(ok=True,old_tangent_space_normal=old,new_tangent_space_normal=material.get_editor_property('tangent_space_normal'),material=material.get_path_name(),changed={p:{'before':before[p],'after':after[p]} for p in changed},added={p:h for p,h in after.items() if p not in before},all_other_existing_content_unchanged=True)
(P/'unreal-change.json').write_text(json.dumps(report,indent=2)+'\n')
print('SMUGGLERS_WATER_NORMAL_SPACE_CORRECTED',flush=True)
