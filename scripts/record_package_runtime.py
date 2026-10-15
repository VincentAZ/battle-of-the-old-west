#!/usr/bin/env python3
"""Attach explicitly selected runtime evidence to the package that was tested.

Verifies the current package against its manifest before writing anything. This
does not turn passing automated tests into release approval or certify a copy
that was not actually exercised by the supplied reports.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--note', action='append', default=[])
    args = parser.parse_args()
    package = args.package_dir.resolve(strict=True)
    manifest_path = package/'package-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    validation = manifest['validation']
    assert validation['ok'] is True, 'Packaging validation did not pass'
    verified = []
    for artifact in validation['artifacts']:
        path = (package/artifact['path']).resolve(strict=True)
        assert path.is_relative_to(package), 'Manifest artifact escapes this package'
        assert path.stat().st_size == artifact['bytes'] and digest(path) == artifact['sha256'], \
            f'Package changed since manifest validation: {artifact["path"]}'
        verified.append(artifact)
    selected = []
    for source in args.report:
        source = source.resolve(strict=True)
        report = json.loads(source.read_text())
        tested_package = (report.get('package_directory') or report.get('package_dir')
                          or report.get('build', {}).get('package_root'))
        assert tested_package and Path(tested_package).resolve() == package, \
            f'Report did not exercise this package: {source}'
        assert isinstance(report.get('ok'), bool), f'Report has no explicit outcome: {source}'
        binary = report.get('build', {}).get('executable')
        if binary:
            assert any(item['sha256'] == binary['sha256'] for item in verified), \
                f'Report tested a different executable: {source}'
        selected.append({'source_report': str(source), 'source_report_sha256': digest(source),
                         'result': report})
    result = {'schema_version': 1, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'tested_package_directory': str(package), 'manifest_sha256': digest(manifest_path),
        'verified_artifacts': verified, 'selected_reports': selected,
        'all_selected_checks_passed': all(item['result']['ok'] for item in selected),
        'release_ready': False, 'notes': args.note,
        'limitations': ['These are selected checks, not an exhaustive certification.',
            'Results apply to the recorded artifact hashes and launch conditions.',
            'Two physical computers, Internet connectivity, Windows and human play enjoyment remain unvalidated.',
            'Runtime reports include the original local evidence paths; those files are not bundled here.']}
    destination = package/'runtime-validation.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2)+'\n')
    temporary.replace(destination)
    print(json.dumps({'written': str(destination), 'reports': len(selected),
                      'all_selected_checks_passed': result['all_selected_checks_passed'],
                      'release_ready': False}, indent=2))


if __name__ == '__main__':
    main()
