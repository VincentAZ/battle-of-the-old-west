#!/usr/bin/env python3
"""Bundle editable Quanah sources and native assets; exclude Mixar job credentials."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/native/quanah-game-v001'
appearance = OUT.parent/'review-v001/quanah-parker'
files = [OUT/name for name in (
    'Quanah-Approved.glb', 'quanah-rigged-original.glb', 'Quanah-Rigged.blend',
    'rig-request.json', 'rig-validation.json', 'guide-bones.json', 'unreal-import.json',
    'unreal-readback.json', 'unreal-retarget.json', 'unreal-captures.json',
    'preservation.json', 'promotion.json')]
files += [appearance/'original.glb', appearance/'character.json',
          appearance/'review/quanah-parker-Review.blend', appearance/'review/manifest.json',
          OUT.parent/'review-v001/appearance-approval.json']
for folder in (OUT/'exports', OUT/'previews', appearance/'review/textures',
               ROOT/'game/OldWest/Content/Art/Western/Quanah'):
    files += [p for p in folder.rglob('*') if p.is_file()]
files += list((ROOT/'scripts').glob('*quanah*.py'))
files += [ROOT/'game/NATIVE_CHARACTERS_PILOT.md', ROOT/'game/REBRAND_GUARDRAILS.md',
          ROOT/'game/ASSET_HISTORY.md']
manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
assert not any('.job.' in name for name in manifest)
with zipfile.ZipFile(OUT/'Quanah-Game-Source.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for name in manifest:
        bundle.write(ROOT/name, name)
    bundle.writestr('manifest.json', json.dumps(manifest, indent=2)+'\n')
print(f'Bundled {len(manifest)} source and native files')
