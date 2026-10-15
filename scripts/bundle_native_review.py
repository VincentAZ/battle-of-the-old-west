"""Archive the three validated candidates, excluding private Mixar job records."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=root / 'art/western/native/review-v001')
    source = parser.parse_args().source.resolve()
    files = [source / name for name in ('baseline.json', 'catalog.json', 'core-tests.log',
                                       'REVIEW.txt', 'provenance.json',
                                       'Native-Appearance-three-quarter.png')]
    projects = []
    for slug in ('quanah-parker', 'lozen', 'sarah-winnemucca'):
        directory = source / slug
        review = directory / 'review'
        validation = json.loads((review / 'validation.json').read_text())
        manifest = json.loads((review / 'manifest.json').read_text())
        assert validation['status'] == 'passed'
        assert sha(review / manifest['project']) == validation['project_sha256']
        projects.append(str((review / manifest['project']).relative_to(source)))
        files.extend(directory / name for name in ('character.json', 'reference.png', 'original.glb',
                                                  'reference-request.json', 'model-request.json'))
        files.extend(review / name for name in (manifest['project'], 'manifest.json', 'validation.json'))
        files.extend(review / item['file'] for item in manifest['textures'] + manifest['previews'])
    files.extend(root / 'scripts' / name for name in ('stampede_mixar_job.py', 'prepare_native_review.py',
                 'validate_native_review.py', 'compose_native_review.py', 'bundle_native_review.py'))
    files.append(root / 'game/NATIVE_CHARACTERS_PILOT.md')
    archive = source / 'Native-Appearance-Review.zip'
    assert not archive.exists(), 'Preserve existing archives'
    for path in files:
        assert path.is_file(), path
        assert '.job.' not in path.name
    records = []
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            relative = path.relative_to(source) if path.is_relative_to(source) else path.relative_to(root)
            bundle.write(path, str(relative))
            records.append({'file': str(relative), 'sha256': sha(path)})
        bundle.writestr('bundle-files.json', json.dumps(records, indent=2) + '\n')
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    current = {'stage': 'appearance', 'status': 'awaiting_appearance_review', 'tribal_review': 'pending',
               'projects': projects, 'bundle': archive.name, 'bundle_sha256': sha(archive),
               'bundle_bytes': archive.stat().st_size, 'integrated': False}
    (source / 'CURRENT.json').write_text(json.dumps(current, indent=2) + '\n')
    (source.parent / 'CURRENT.json').write_text(json.dumps({'directory': source.name, **current}, indent=2) + '\n')
    print(json.dumps(current, indent=2))


if __name__ == '__main__':
    main()
