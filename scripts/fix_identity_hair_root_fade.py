"""Correct the existing three identity hair materials, with an exact backup.

Run in an Unreal Python commandlet. This changes the connected root-fade input;
it does not reimport meshes or textures. The regular importer now authors the
same corrected graph for future imports.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from identity_material_checks import hair_root_nodes, verify_hair_root_fade

content = ROOT/'game/OldWest/Content/Art/Survivors'
source = ROOT/'art/characters/identity-face-candidates'
output = ROOT/'art/characters/hair-root-fade-audit'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
output.mkdir(parents=True, exist_ok=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = {str(path):sha(path) for path in content.rglob('*.uasset')}
report = {'ok':False, 'backup':str(output), 'materials':[], 'before_sha256':before}
allowed = set()
try:
    for card in ('quanah_parker','bartender','charles_goodnight'):
        spec = json.loads((source/card/'manifest.json').read_text())
        for name, details in spec['materials'].items():
            if details.get('kind') != 'masked_hair':
                continue
            path = content/'Identities/Materials'/(name+'.uasset')
            allowed.add(str(path))
            shutil.copy2(path,output/path.name)
            assert sha(output/path.name) == before[str(path)]
            material = unreal.load_asset('/Game/Art/Survivors/Identities/Materials/'+name)
            scale, coordinate, inverse = hair_root_nodes(material)
            if inverse:
                material.modify()
                assert unreal.MaterialEditingLibrary.connect_material_expressions(coordinate,'',scale,'A')
                unreal.MaterialEditingLibrary.delete_material_expression(material,inverse)
                unreal.MaterialEditingLibrary.recompile_material(material)
                assert unreal.EditorAssetLibrary.save_loaded_asset(material,only_if_is_dirty=False)
            report['materials'].append(dict(card_id=card,changed=bool(inverse),
                **verify_hair_root_fade(material,details['root_fade_start'])))
    after = {str(path):sha(path) for path in content.rglob('*.uasset')}
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed <= allowed, changed-allowed
    report.update(ok=True,changed_assets=sorted(changed),after_sha256=after,
                  scope='Saved material graphs only; native portrait review remains required')
except Exception as error:
    report['error'] = str(error)
    raise
finally:
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    (output.parent/'latest.json').write_text(json.dumps(report,indent=2)+'\n')
