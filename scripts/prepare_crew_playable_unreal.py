"""Import approved Crew rigs, build physics/retarget assets, or audit saved results.

Preflight without Unreal: python3 scripts/prepare_crew_playable_unreal.py --plan
UnrealEditor-Cmd OldWest.uproject -run=pythonscript -script=<this> -nullrhi
OLDWEST_CREW_SLUGS=comma,separated,slugs limits a batch (default: all43new).
OLDWEST_CREW_VERIFY_ONLY=1 must run in a NEW editor process after import.
All selected exports must pass preflight before any Content writes. Existing
Native assets and every Content package outside the selected Crew folders are
hashed before/after. A process lock prevents concurrent Crew writers/auditors.
Animation measurements are technical checks; visual approval is never inferred.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from crew_unreal_contract import BASE, CONTENT, NATIVE, character, load_manifest, snapshot, sha


def main():
    plan_only = '--plan' in sys.argv
    verify = os.environ.get('OLDWEST_CREW_VERIFY_ONLY') == '1'
    report = {'ok': False, 'mode': 'plan' if plan_only else 'fresh_readback' if verify else 'import_and_retarget',
              'characters': [], 'visual_qa_passed': False}
    with (BASE / '.unreal-authoring.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_manifest()
        requested = os.environ.get('OLDWEST_CREW_SLUGS', '')
        slugs = requested.split(',') if requested else sorted(set(manifest['characters']) - NATIVE)
        assert slugs and len(slugs) == len(set(slugs)), 'Empty or duplicate selection'
        # Pure preflight deliberately gathers all failures, without importing Unreal.
        configs, errors = [], {}
        for slug in slugs:
            try:
                configs.append(character(slug, manifest, require_exports=not plan_only))
            except Exception as exc:
                errors[slug] = repr(exc)
        if errors:
            report['preflight_errors'] = errors
            (BASE / 'unreal-preflight-failure.json').write_text(json.dumps(report, indent=2)+'\n')
            raise AssertionError('No Content changed; failed preflight: '+json.dumps(errors))
        if plan_only:
            for config in configs:
                report['characters'].append({k: str(v) for k,v in config.items() if k != 'validation'})
            report.update(ok=True, existing_native_preserved=sorted(NATIVE))
            print(json.dumps(report, indent=2))
            return
        destinations = [CONTENT / config['dest'].removeprefix('/Game/') for config in configs]
        before = snapshot(() if verify else destinations)
        try:
            for config in configs:
                os.environ['OLDWEST_CREW_SLUG'] = config['slug']
                entry = {'slug': config['slug'], 'destination': config['dest'], 'ok': False}
                report['characters'].append(entry)
                destination = CONTENT / config['dest'].removeprefix('/Game/')
                asset_report_path = config['out'] / 'unreal-assets.json'
                def asset_hashes():
                    return {str(path.relative_to(CONTENT)): sha(path) for path in sorted(destination.rglob('*')) if path.is_file()}
                if verify:
                    saved = json.loads(asset_report_path.read_text())
                    assert saved['approved_source_sha256'] == config['source_sha256']
                    assert saved['rig_project_sha256'] == config['validation']['project_sha256']
                    assert saved['rig_validation_sha256'] == sha(config['out']/'rig-validation.json'), 'Rig constraints changed since import'
                    assert saved['files'] == asset_hashes(), 'Saved Unreal assets changed since import'
                for helper in ('import_crew_playable_unreal.py', 'retarget_crew_playable_unreal.py'):
                    runpy.run_path(str(ROOT/'scripts'/helper), run_name='__main__')
                if not verify:
                    asset_report_path.write_text(json.dumps({
                        'approved_source_sha256': config['source_sha256'],
                        'rig_project_sha256': config['validation']['project_sha256'],
                        'rig_validation_sha256': sha(config['out']/'rig-validation.json'),
                        'files': asset_hashes(), 'visual_qa_passed': False}, indent=2)+'\n')
                entry['ok'] = True
            report['ok'] = True
        except Exception as exc:
            report.update(error=repr(exc), traceback=traceback.format_exc())
            raise
        finally:
            after = snapshot(() if verify else destinations)
            report['existing_content_unchanged'] = before == after
            report['unexpected_content_changes'] = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
            if before != after:
                report['ok'] = False
            # Per-selection reports avoid a later subset overwriting all-Crew evidence.
            selection = 'all' if len(slugs) == 43 else slugs[0] if len(slugs) == 1 else 'batch-'+hashlib.sha256(','.join(slugs).encode()).hexdigest()[:12]
            report_path = BASE / ('unreal-'+('readback' if verify else 'import')+'-'+selection+'.json')
            report_path.write_text(json.dumps(report, indent=2)+'\n')
            assert before == after, 'Unexpected Content changes; see '+str(report_path)


if __name__ == '__main__':
    main()
