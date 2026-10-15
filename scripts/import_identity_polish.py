"""Import source-reviewed identity polish with a bounded, verified rollback copy.

Run in UnrealEditor-Cmd after source review. The review records exact source
hashes; native deformation and presentation must still be checked after import.
"""
import hashlib
import json
import os
import runpy
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ['OLDWEST_VARIANT_SOURCE']).resolve()
CONTENT = ROOT / 'game/OldWest/Content/Art/Survivors'
DEST = CONTENT / 'Identities'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


review = json.loads((SOURCE / 'source-review.json').read_text())
assert review['source_reviewed'] is True
variants = []
allowed = set()
for item in review['cards']:
    card = item['card_id']
    folder = SOURCE / card
    spec = json.loads((folder / 'manifest.json').read_text())
    name = spec['name']
    assert sha(folder / (name + '.blend')) == item['blend_sha256']
    assert sha(folder / (name + '_Cm.fbx')) == item['fbx_sha256'] == spec['fbx_sha256']
    assert spec['neck_correction']['body_weights_preserved']
    assert spec['neck_correction']['face_vertices_weight_transferred'] > 0
    variants.append((card, name))
    allowed.add(DEST / ('SKM_' + name + '_Cm.uasset'))
    allowed.add(DEST / 'Materials' / (spec['outfit_material'] + '.uasset'))
    for texture in spec['textures'].values():
        allowed.add(DEST / 'Textures' / (Path(texture['path']).stem + '.uasset'))
    for material, details in spec['materials'].items():
        if details.get('kind') == 'solid_detail':
            allowed.add(DEST / 'Materials' / (material + '.uasset'))
        if details.get('kind') == 'masked_hair':
            allowed.add(DEST / 'Materials' / (material + '.uasset'))
            allowed.update(DEST / 'Textures' / (name + '.uasset')
                           for name in ('T_Identity_Hair_Strands', 'T_Identity_Hair_Diffuse'))
assert variants
before = {str(path): sha(path) for path in CONTENT.rglob('*.uasset')}
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
backup = SOURCE / 'native-import-backups' / stamp
backup.mkdir(parents=True, exist_ok=False)
for path in allowed:
    if path.exists():
        target = backup / path.relative_to(CONTENT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        assert sha(target) == before[str(path)]
record = {'ok': False, 'backup': str(backup), 'allowed_assets': sorted(map(str, allowed)),
          'before_sha256': before, 'source_review_sha256': sha(SOURCE / 'source-review.json')}
(backup / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
try:
    os.environ['OLDWEST_VARIANT_DEST'] = '/Game/Art/Survivors/Identities'
    os.environ['OLDWEST_VARIANT_IDS'] = json.dumps(variants)
    runpy.run_path(str(ROOT / 'scripts/import_survivor_variants.py'), run_name='__main__')
    after = {str(path): sha(path) for path in CONTENT.rglob('*.uasset')}
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed <= set(map(str, allowed)), ('Unexpected asset mutation', changed - set(map(str, allowed)))
    assert all(str(DEST / ('SKM_' + name + '_Cm.uasset')) in changed for _, name in variants)
    record.update(ok=True, changed_assets=sorted(changed), after_sha256=after,
                  status='imported; fresh native audit and visual review required')
except Exception as error:
    record.update(error=f'{type(error).__name__}: {error}', status='failed; rollback copy retained')
    raise
finally:
    (backup / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    (SOURCE / 'guarded-import.json').write_text(json.dumps(record, indent=2) + '\n')
