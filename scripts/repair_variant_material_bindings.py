"""Repair only the three newly imported costume material arrays, then save."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/survivor_variants'
report=json.loads((OUT/'unreal-import.json').read_text())
for path,digest in report['protected_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
for variant in report['variants']:
    mesh=unreal.EditorAssetLibrary.load_asset(variant['mesh'])
    mesh.modify()
    slots=mesh.get_editor_property('materials')
    expected={row['slot']:row['material'] for row in variant['materials']}
    for index in range(len(slots)):
        slot=slots[index];name=str(slot.get_editor_property('material_slot_name'))
        mat=unreal.EditorAssetLibrary.load_asset(expected[name]);assert mat
        slot.set_editor_property('material_interface',mat);slots[index]=slot
    mesh.set_editor_property('materials',slots)
    assert all(s.get_editor_property('material_interface') for s in mesh.get_editor_property('materials'))
    assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False)
    unreal.log('VARIANT_MATERIAL_BINDINGS_REPAIRED '+variant['card_id'])
for path,digest in report['protected_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
