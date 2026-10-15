"""Package the complete static Crew review without private generation records."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from build_crew_review import ROOT, OUT, EXISTING, main as audit


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='Crew-46-Unique-Static-Review.zip')
    args = parser.parse_args()
    assert Path(args.name).name == args.name and args.name.endswith('.zip')
    archive_path = OUT / args.name
    assert not archive_path.exists(), 'Preserve existing review archives'
    audit()
    roster = json.loads((OUT / 'roster-status.json').read_text())
    assert roster['completion'] == 'ready_for_all_46_appearance_review'
    files = {OUT / name for name in ('baseline.json', 'catalog.json', 'roster-status.json', 'index.html')}
    if (OUT / 'historical-revisions.json').is_file():
        files.add(OUT / 'historical-revisions.json')
    files.update((ROOT / 'research/crew-history-audit').glob('*.json'))
    files.update({ROOT / 'AGENTS.md', ROOT / '.cursor/rules/historical-accuracy.mdc'})
    native = ROOT / 'art/western/native/review-v001'
    approval = json.loads((native / 'appearance-approval.json').read_text())
    files.add(native / 'appearance-approval.json')
    for slug, asset in roster['assets'].items():
        directory = ROOT / asset['directory']
        if (directory.parent / 'baseline.json').is_file():
            files.add(directory.parent / 'baseline.json')
        review = directory / 'review'
        manifest = json.loads((review / 'manifest.json').read_text())
        project = review / manifest['project']
        if slug in EXISTING:
            assert sha(project) == approval['projects'][slug]['sha256']
        files.update({directory / 'character.json', project, review / 'manifest.json', review / 'validation.json'})
        if slug not in EXISTING:
            files.add(review / 'visual-review.json')
        source = Path(manifest['source_glb'])
        assert source.is_relative_to(ROOT) and sha(source) == manifest['source_sha256']
        files.add(source)
        for item in manifest['textures'] + manifest['previews']:
            files.add(review / item['file'])
        # Deliberate allowlist: no job responses, private URLs, or process logs.
        files.update(directory.glob('reference*.png'))
        files.update(directory.glob('reference*-review.json'))
        files.update(directory.glob('source-*.png'))
        files.update(directory.glob('source-*.jpg'))
        files.update(directory.glob('weapon-*.png'))
        files.update(directory.glob('final-weapon-*.png'))
        files.update(directory.glob('*.glb'))
        files.update(directory.glob('*.py'))
        files.update(directory.glob('*provenance*.json'))
        for pattern in ('reference*-request.json', 'model*-request.json'):
            for request in directory.glob(pattern):
                data = json.loads(request.read_text())
                assert data['service'] in {'image_gen', 'model_3d'}
                files.add(request)
                if data.get('historical_evidence'):
                    evidence = (directory / data['historical_evidence']).resolve()
                    assert evidence.is_relative_to(directory.resolve())
                    files.add(evidence)
        for name in ('historical-sources.json', 'historical-evidence.json', 'historical-review.json', 'appearance-sources.json', 'sources.json', 'reference-inspection.json', 'reference-review.json', 'reference-rejections.json'):
            if (directory / name).is_file():
                files.add(directory / name)
        if slug == 'gatling-gunner' and (directory / 'ground-tripod-foot.py').exists():
            files.add(directory / 'ground-tripod-foot.py')
        if slug == 'wild-bill-hickok' and (directory / 'repair_grip_depth.py').exists():
            files.update(directory / name for name in
                         ('repair_grip_depth.py', 'repair-provenance.json', 'original.glb'))
        if slug == 'coach-guard' and (directory / 'archive-weapon-v1').exists():
            files.update(directory / name for name in
                         ('reference_edit_job.py', 'reference-edit-provenance.json',
                          'weapon-revision-provenance.json', 'archive-weapon-v1/original.glb'))
            for name in ('character.json', 'reference.png', 'reference-request.json', 'model-request.json'):
                path = directory / 'archive-weapon-v1' / name
                if path.is_file():
                    files.add(path)
        prior_name = {'gatling-gunner': 'review-before-tripod-contact-fix',
                      'wild-bill-hickok': 'review-before-grip-repair-v001',
                      'coach-guard': 'archive-weapon-v1/review'}.get(slug)
        if prior_name and (directory / prior_name).exists():
            prior = directory / prior_name
            prior_manifest = json.loads((prior / 'manifest.json').read_text())
            files.update({prior / prior_manifest['project'], prior / 'manifest.json',
                          prior / 'validation.json'})
            files.update(prior / item['file'] for item in
                         prior_manifest['textures'] + prior_manifest['previews'])
            if (prior / 'visual-review.json').is_file():
                files.add(prior / 'visual-review.json')
        # Versioned historical corrections retain rejected reviews as evidence.
        for prior in directory.glob('review-*'):
            if prior.name in {'review-correction-draft', 'review-corrected'}:
                continue
            if not (prior / 'manifest.json').is_file():
                continue
            previous = json.loads((prior / 'manifest.json').read_text())
            files.update({prior / previous['project'], prior / 'manifest.json'})
            files.update(prior / item['file'] for item in previous['textures'] + previous['previews'])
            files.update(prior / name for name in ('validation.json', 'visual-review.json') if (prior / name).is_file())
    for name in ('stampede_mixar_job.py', 'crew_mixar_job.py', 'prepare_crew_review.py',
                 'validate_crew_review.py', 'validate_crew_history.py', 'build_crew_review.py', 'bundle_crew_review.py', 'crew_geometry.py'):
        files.add(ROOT / 'scripts' / name)
    files.add(ROOT / 'scripts/compose_crew_contacts.py')
    files.update(ROOT / 'game' / name for name in ('CREW_APPEARANCE_REVIEW.md', 'REBRAND_GUARDRAILS.md'))
    for image in OUT.glob('Crew-Static-Contact-*.jpg'):
        files.add(image)
    records = []
    with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            assert path.is_file() and '.job.' not in path.name
            relative = str(path.relative_to(ROOT))
            archive.write(path, relative)
            records.append({'file': relative, 'sha256': sha(path)})
        archive.writestr('bundle-files.json', json.dumps(records, indent=2) + '\n')
        archive.writestr('OPEN-REVIEW.html', '<!doctype html><meta charset="utf-8"><title>Crew static review</title><p><a href="art/western/crew/review-v002/index.html">Open all 46 Crew card copies</a></p>')
        archive.writestr('READ-ME.txt', 'Complete static appearance review: 46 copies, 46 unique appearances, including three previously approved Native models.\nOpen OPEN-REVIEW.html after extracting the entire archive. The Mixar sources have packed textures.\nNo new rigs, animations or game imports. User appearance approval is pending. Native tribal review remains separate.\nHistorical likenesses and exact tailoring are artistic interpretations. Reference images are retained for provenance; use the mesh renders for approval.\nThe preservation validator applies to the original repository; bundle-files.json and ZIP CRCs verify this archive independently.\n')
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for item in records:
            assert hashlib.sha256(archive.read(item['file'])).hexdigest() == item['sha256']
    current = {'directory': OUT.name, 'status': 'awaiting_all_46_appearance_approval',
               'counts': roster['counts'], 'review_index': str((OUT / 'index.html').relative_to(OUT.parent)),
               'bundle': str(archive_path.relative_to(OUT.parent)), 'bundle_sha256': sha(archive_path),
               'bundle_bytes': archive_path.stat().st_size, 'all_46_approved': False,
               'animation_authorized': False, 'game_integrated': False}
    (OUT.parent / 'CURRENT.json').write_text(json.dumps(current, indent=2) + '\n')
    print(json.dumps(current, indent=2))


if __name__ == '__main__':
    main()
