#!/usr/bin/env python3
"""Preserve the integrated Drifter's editable Mixar source and native assets."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'art/western/drifter'
OUT = ASSET / 'game-v001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for scenario, revision in (('shelter', 'v006'), ('wanted_poster_board', 'v002')):
        assert json.loads((OUT / f'package-{scenario}-{revision}/result.json').read_text())['ok']
    assert json.loads((OUT / 'preservation.json').read_text())['all_existing_content_unchanged']
    files = [ASSET / 'review-v003/review/Drifter-Review.blend']
    animation = ASSET / 'animation-v001'
    files += [animation / name for name in (
        'Drifter-Rigged.blend', 'Drifter-Approved.glb', 'drifter-rigged-original.glb',
        'rig-request.json', 'approval.json', 'rig-validation.json',
        'unreal-import.json', 'unreal-retarget.json', 'unreal-captures.json')]
    files += list((animation / 'exports').glob('*')) + list((animation / 'previews').glob('*.png'))
    files += list((ROOT / 'game/OldWest/Content/Art/Western/Drifter').rglob('*.uasset'))
    files += [ROOT / 'scripts' / name for name in (
        'weather_drifter_review.py',
        'rig_drifter_mixar.py', 'import_drifter_unreal.py', 'retarget_drifter_unreal.py',
        'preview_drifter_unreal.py', 'test_unreal_drifter.py', 'bundle_drifter_game.py')]
    files += [ROOT / 'art/characters/oldwest_survivor/manny-retarget-chains.json']
    files += [ROOT / 'game/DRIFTER_PILOT.md', OUT / 'preservation.json', OUT / 'core-tests.log',
              OUT / 'baseline.json', OUT / 'promotion.json']
    for scenario, revision in (('shelter', 'v006'), ('wanted_poster_board', 'v002')):
        evidence = OUT / f'package-{scenario}-{revision}'
        files += [evidence / 'result.json'] + list(evidence.rglob('drifter-visuals.json'))
        files += list(evidence.rglob('*.png'))
    archive = OUT / 'Drifter-Game-Source.zip'
    manifest = [{'file': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in files]
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, str(path.relative_to(ROOT)))
        bundle.writestr('bundle-files.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    (OUT / 'bundle.json').write_text(json.dumps(dict(file=archive.name,
        sha256=sha(archive), bytes=archive.stat().st_size, files=len(files)), indent=2) + '\n')
    print(archive)


if __name__ == '__main__':
    main()
