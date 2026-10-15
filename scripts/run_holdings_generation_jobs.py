"""Idempotent orchestration of the Holdings reference and model generation jobs.

Run: python3 -I scripts/run_holdings_generation_jobs.py STAGE ACTION [slugs...]
  STAGE: reference | model      ACTION: submit | status | download

Each call runs stampede_mixar_job.py through the serialized crew wrapper, so
retries reuse the persisted idempotency key and never pay twice. Downloads
keep the original generated file; the model stage requires a reviewed
reference (reference-review.json with status accepted_for_static_mesh_generation).
"""
import os
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import HOLDINGS, HOLDINGS_SET, REVIEW, ROOT  # noqa: E402

MIXAR = os.path.expanduser('~/.local/bin/mixar')
FINAL = {'DONE', 'FAILED', 'CANCELLED', 'DLQ'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['reference', 'model'])
    parser.add_argument('action', choices=['submit', 'status', 'download'])
    parser.add_argument('slugs', nargs='*')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    authorization = json.loads((REVIEW / 'service-authorization.json').read_text())
    assert authorization['user_message'] and authorization['stages'] == ['reference', 'model']
    if args.action == 'submit' and HOLDINGS_SET == 'boomtown':
        approval_path = REVIEW / 'external-service-approval.json'
        approval = json.loads(approval_path.read_text()) if approval_path.exists() else {}
        assert approval.get('status') == 'approved' and approval.get('user_message'), \
            'External Mixar destination and credit approval is still pending; no job submitted'
    outputs = {'reference': 'reference.png', 'model': 'original.glb'}
    failures = []
    summary = {}
    for card_id, (slug, *_rest) in HOLDINGS.items():
        if args.slugs and slug not in args.slugs:
            continue
        directory = REVIEW / slug
        request = directory / (args.stage + '-request.json')
        # A rejected reference is revised through numbered requests; the newest one is live.
        revisions = sorted(directory.glob(args.stage + '-v*-request.json'))
        if revisions:
            request = revisions[-1]
        if not request.exists():
            summary[slug] = 'no_request'
            continue
        state_path = request.with_suffix('.job.json')
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        status = state.get('response', {}).get('status')
        output = directory / outputs[args.stage]
        if args.action == 'submit' and args.stage == 'reference':
            checks = json.loads((REVIEW / 'history-validation.json').read_text())['holdings'].get(slug)
            evidence = json.loads((directory / 'historical-evidence.json').read_text())
            if not checks or checks['issues']:
                summary[slug] = 'evidence_not_validated'
                continue
            if checks.get('evidence_sha256') != hashlib.sha256((directory / 'historical-evidence.json').read_bytes()).hexdigest():
                summary[slug] = 'evidence_changed_since_validation'
                failures.append(slug)
                continue
            if json.loads(request.read_text())['prompt'] != evidence['render_brief']:
                summary[slug] = 'prompt_differs_from_validated_brief'
                continue
        if args.action == 'submit':
            if state.get('job_id'):
                summary[slug] = 'already_submitted:' + str(status)
                continue
            if args.stage == 'model':
                review_path = directory / 'reference-review.json'
                if not review_path.exists():
                    summary[slug] = 'reference_not_reviewed'
                    continue
                review = json.loads(review_path.read_text())
                if review.get('status') != 'accepted_for_static_mesh_generation':
                    summary[slug] = 'reference_not_accepted'
                    continue
                assert hashlib.sha256((directory / 'reference.png').read_bytes()).hexdigest() == review['reference_sha256']
        elif args.action == 'status':
            if not state.get('job_id') or status in FINAL:
                summary[slug] = 'skip:' + str(status)
                continue
        elif args.action == 'download':
            if status != 'DONE' or output.exists():
                summary[slug] = 'skip:' + ('downloaded' if output.exists() else str(status))
                continue
        command = [MIXAR, '--background', '--factory-startup', '--python-exit-code', '1',
                   '--python', str(ROOT / 'scripts/crew_mixar_job.py'), '--', str(request), args.action]
        if args.action == 'download':
            command += ['--output', str(output)]
        log_path = directory / f'{args.stage}-{args.action}.log'
        with log_path.open('a') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        status = state.get('response', {}).get('status')
        summary[slug] = f'{args.action}:{status}:exit{result.returncode}'
        print(slug, args.stage, args.action, status, 'exit', result.returncode, flush=True)
        if result.returncode:
            text = log_path.read_text()
            if 'InsufficientCredits' in text or 'usage allowance' in text:
                print('Mixar allowance exhausted; remaining requests retained for later.', flush=True)
                failures.append(slug)
                break
            if 'Too many active' in text:
                print('Mixar active-job capacity reached; remaining requests retained for the next batch.', flush=True)
                break
            failures.append(slug)
    print(json.dumps(summary, indent=1))
    if failures:
        raise SystemExit('Failed operations: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
