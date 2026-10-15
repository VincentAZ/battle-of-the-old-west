"""Package the static Holdings review without private generation records."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import REVIEW, ROOT  # noqa: E402
import build_holdings_review  # noqa: E402

PRIVATE_SUFFIXES = ('.job.json', '.log')
SCRIPTS = ('holdings_roster.py', 'validate_holdings_history.py', 'author_holdings_requests.py',
           'run_holdings_generation_jobs.py', 'prepare_holdings_review.py', 'validate_holdings_review.py',
           'build_holdings_review.py', 'bundle_holdings_review.py', 'stampede_mixar_job.py', 'crew_mixar_job.py')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='Holdings-34-Static-Review.zip')
    args = parser.parse_args()
    assert Path(args.name).name == args.name and args.name.endswith('.zip')
    archive_path = REVIEW / args.name
    assert not archive_path.exists(), 'Preserve existing review archives'
    sys.argv = [sys.argv[0]]
    build_holdings_review.main()
    roster = json.loads((REVIEW / 'roster-status.json').read_text())
    assert roster['completion'] in {'ready_for_all_34_appearance_review', 'appearance_approved'}
    files = set()
    for path in REVIEW.rglob('*'):
        if path.is_file() and path.suffix != '.zip' and not path.name.endswith(PRIVATE_SUFFIXES):
            files.add(path)
    files.update(ROOT / 'scripts' / name for name in SCRIPTS)
    files.update({ROOT / 'AGENTS.md', ROOT / '.cursor/rules/historical-accuracy.mdc',
                  ROOT / 'game/REBRAND_GUARDRAILS.md', ROOT / 'game/HOLDINGS_PILOT.md'})
    manifest = {'archive': args.name, 'files': {}}
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            assert path.is_file(), path
            assert not path.name.endswith(PRIVATE_SUFFIXES)
            relative = str(path.relative_to(ROOT))
            archive.write(path, relative)
            manifest['files'][relative] = sha(path)
    manifest['archive_sha256'] = sha(archive_path)
    manifest['archive_bytes'] = archive_path.stat().st_size
    manifest['excluded'] = 'Mixar job state (*.job.json) with temporary download URLs, and local logs'
    (REVIEW / 'bundle-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('HOLDINGS_BUNDLE', json.dumps({k: v for k, v in manifest.items() if k != 'files'}), len(files), 'files')


if __name__ == '__main__':
    main()
