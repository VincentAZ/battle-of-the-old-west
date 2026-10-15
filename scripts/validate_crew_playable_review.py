#!/usr/bin/env python3
"""Check current source, import, capture and human visual-review evidence for all Crew rigs."""
import json
import hashlib
from pathlib import Path
from crew_unreal_contract import BASE, CONTENT, NATIVE, character, load_manifest, sha
from crew_capture_reuse import audit_reuse


def main():
    manifest = load_manifest()
    reference_audit = json.loads((BASE / 'integration/skeleton-reference-audit.json').read_text())
    references = {r['slug']: r for r in reference_audit['characters']}
    results = {}
    for slug in sorted(set(manifest['characters']) - NATIVE):
        try:
            item = character(slug, manifest)
            out = item['out']
            capture_path = out / 'unreal-pose-captures.json'
            captures = json.loads(capture_path.read_text())
            assets = json.loads((out / 'unreal-assets.json').read_text())
            reference = references[slug]
            assert not reference_audit['content_modified'], 'Reference audit changed Content'
            assert not reference['mismatched_bones'], 'Mesh and skeleton reference poses differ'
            assert reference['rig_project_sha256'] == item['validation']['project_sha256']
            assert reference['unreal_assets_sha256'] == sha(out / 'unreal-assets.json'), 'Skeleton reference audit is stale'
            assert assets['approved_source_sha256'] == item['source_sha256']
            gesture = json.loads((out / 'attack-gesture-validation.json').read_text())
            assert gesture['alpha_from_bind'] == .35 and gesture['all_non_attack_packages_unchanged']
            assert gesture['rig_project_sha256'] == item['validation']['project_sha256']
            attack_files = [h for p, h in assets['files'].items() if p.endswith('/Animations/RA_MM_Attack_01.uasset')]
            assert attack_files == [gesture['adjusted_attack_package_sha256']], 'Attack adjustment evidence is stale'
            for filename, digest in assets['files'].items():
                package = (CONTENT / filename).resolve()
                assert package.is_relative_to(CONTENT.resolve()), 'Asset path outside Content'
                assert sha(package) == digest, 'Imported package changed: ' + filename
            assert captures['ok'] and captures['component_pose_verified']
            assert captures['existing_content_unchanged']
            assert captures['rig_project_sha256'] == item['validation']['project_sha256'] == assets['rig_project_sha256']
            assert captures['rig_validation_sha256'] == sha(out / 'rig-validation.json') == assets['rig_validation_sha256']
            assert captures['unreal_assets_sha256'] == sha(out / 'unreal-assets.json')
            assert len(captures['captures']) == 24
            assert len({r['file'] for r in captures['captures']}) == 24, 'Duplicate capture filename'
            expected = {(f'Unreal-walk-{view}-{phase:02d}.png', 'MF_Unarmed_Walk_Fwd', fraction)
                        for view in ('front', 'side', 'rear') for phase, fraction in enumerate((0., .13, .33, .58))}
            expected.update((f'Unreal-{clip}-{phase:02d}.png', clip, phase/4)
                            for clip in ('MM_Idle', 'MM_Attack_01', 'MM_HitReact_Front_Lgt_01') for phase in range(4))
            assert {(Path(r['file']).name, r['clip'], r['fraction']) for r in captures['captures']} == expected, 'Incomplete pose coverage'
            audit_reuse(out, captures)
            for record in captures['captures']:
                assert sha(out / record['file']) == record['sha256'], 'Captured image changed'
                assert record['component_pose_sha256'] == hashlib.sha256(json.dumps(record['component_local_pose'], sort_keys=True).encode()).hexdigest(), 'Component pose evidence changed'
                error = record['pose_error']
                assert error['translation_cm'] < .025 and error['quaternion_error'] < .002 and error['time_seconds'] < .0001
            review_path = out / 'animation-visual-review.json'
            if not review_path.exists():
                review_path = out / 'visual-review.json'
            review = json.loads(review_path.read_text())
            assert review['status'] == 'passed', 'Visual inspection failed'
            assert review['capture_manifest_sha256'] == sha(capture_path), 'Visual inspection is stale'
            assert review['rig_project_sha256'] == item['validation']['project_sha256']
            assert review.get('views_reviewed', len(review.get('captures_reviewed', []))) == 24
            results[slug] = {'ok': True, 'rig_project_sha256': review['rig_project_sha256'],
                             'visual_review_sha256': sha(review_path)}
        except (AssertionError, KeyError, OSError, ValueError) as error:
            results[slug] = {'ok': False, 'error': str(error) or 'Evidence assertion failed'}
    report = {'ok': all(x['ok'] for x in results.values()), 'new_rigs': len(results),
              'reused_native_rigs': sorted(NATIVE), 'characters': results}
    target = BASE / 'integration/playable-review-validation.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
