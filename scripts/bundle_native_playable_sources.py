"""Preserve the integrated native trio, editable sources and runtime implementation with an explicit allowlist."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/native/playable-v001'
paths = []
for name, directory in [
    ('Quanah', ROOT / 'art/western/native/quanah-game-v001'),
    ('Lozen', ROOT / 'art/western/native/lozen-cloth-v004'),
    ('Sarah', OUT / 'sarah-winnemucca'),
]:
    paths.append(directory / (name + '-Rigged.blend'))
    paths += list((directory / 'exports').glob('*.fbx'))
    paths += list((directory / 'exports').glob('*.png'))
    for filename in ['rig-validation.json','unreal-import.json','unreal-readback.json','unreal-retarget.json']:
        if (directory / filename).exists():
            paths.append(directory / filename)
    paths += list((ROOT / 'game/OldWest/Content/Art/Western' / name).rglob('*.uasset'))
paths += [ROOT / 'scripts' / name for name in [
    'repair_lozen_cloth_mixar.py', 'import_native_preview_unreal.py',
    'retarget_native_preview_unreal.py', 'prepare_native_playable_unreal.py',
    'validate_native_playable_sources.py', 'preview_lozen_cloth_unreal.py',
    'validate_lozen_cloth_captures.py',
    'export_lozen_pose_diagnostics.py', 'render_native_trio_unreal.py',
    'encode_native_trio_preview.py', 'bundle_native_playable_sources.py',
    'weather_drifter_review.py', 'test_unreal_native_copies.py', 'package_oldwest.py',
]]
paths += [OUT / 'integration/preservation.json', OUT / 'integration/core-tests-release.log',
    OUT / 'integration/packaged-release/result.json',
    OUT / 'source-validation.json', ROOT / 'game/NATIVE_CHARACTERS_PILOT.md',
    ROOT / 'game/OldWest/Source/OldWestGame/Private/OldWestAssetAuthoring.cpp',
    ROOT / 'game/OldWest/Source/OldWestGame/Public/OldWestAssetAuthoring.h']
paths += [ROOT / 'game/REBRAND_GUARDRAILS.md', ROOT / 'game/ASSET_HISTORY.md',
          ROOT / 'game/data/cards.json']
for folder in ('game/OldWest/Source', 'game/OldWest/Config', 'game/tests/core', 'game/tests/presentation'):
    paths += [p for p in (ROOT / folder).rglob('*') if p.is_file() and '.local.' not in p.name and p.suffix in ('.h', '.cpp', '.cs', '.ini', '.txt')]
paths = sorted(set(paths))
assert all(p.is_file() for p in paths)
manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
archive = OUT / 'Native-Trio-Game-Source.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as bundle:
    for path in paths:
        bundle.write(path, str(path.relative_to(ROOT)))
    bundle.writestr('manifest.json', json.dumps({'scope':'Integrated native trio: editable models, native assets, cosmetic copy mapping, source and tests', 'files':manifest}, indent=2)+'\n')
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
print(json.dumps({'file':str(archive),'files':len(paths),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))
