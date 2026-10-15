"""Bundle the validated Drifter appearance checkpoint without private job URLs."""

import hashlib
import json
from pathlib import Path
import zipfile
import argparse


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=root / 'art/western/drifter/review-v001')
    source = parser.parse_args().source.resolve()
    review = source / 'review'
    validation = json.loads((review / 'validation.json').read_text())
    assert validation['status'] == 'passed'
    manifest = json.loads((review / 'manifest.json').read_text())
    assert sha(review / manifest['project']) == validation['project_sha256']
    files = [source / name for name in (
        'drifter-reference.png', 'drifter-original.glb', 'reference-request.json',
        'model-request.json', 'provenance.json', 'baseline.json',
        'baseline-core-tests.log', 'REVIEW.txt')]
    files += [review / name for name in ('Drifter-Review.blend', 'manifest.json', 'validation.json')]
    files += [review / item['file'] for item in manifest['textures'] + manifest['previews']]
    scripts = [root / 'scripts' / name for name in (
        'stampede_mixar_job.py', 'prepare_drifter_review.py',
        'validate_drifter_review.py', 'bundle_drifter_review.py')]
    if manifest.get('source_project'):
        files.append(Path(manifest['source_project']))
        files.append(source / 'before-wear-manifest.json')
        if (source / 'wear-settings.json').exists():
            files.append(source / 'wear-settings.json')
        scripts.append(root / 'scripts/weather_drifter_review.py')
    if (source / 'Drifter-Before-After.png').exists():
        files.append(source / 'Drifter-Before-After.png')
        scripts.append(root / 'scripts/compare_drifter_review.py')
    archive = source / 'Drifter-Appearance-Review.zip'
    assert not archive.exists(), 'Preserve an existing review bundle'
    records = []
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in files + scripts + [root / 'game/DRIFTER_PILOT.md']:
            relative = path.relative_to(source) if path.is_relative_to(source) else path.relative_to(root)
            bundle.write(path, str(relative))
            records.append({'file': str(relative), 'sha256': sha(path)})
        bundle.writestr('bundle-files.json', json.dumps(records, indent=2) + '\n')
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    current = {
        'asset': 'Drifter', 'stage': 'A', 'approval': 'awaiting_appearance_review',
        'project': 'review/Drifter-Review.blend', 'bundle': archive.name,
        'bundle_sha256': sha(archive), 'bundle_bytes': archive.stat().st_size,
        'next': 'User appearance approval before rigging or animation',
    }
    (source / 'CURRENT.json').write_text(json.dumps(current, indent=2) + '\n')
    print(json.dumps(current, indent=2))


if __name__ == '__main__':
    main()
