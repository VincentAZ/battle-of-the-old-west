"""Idempotent local orchestration of the explicitly authorized Mixar rig jobs."""
import os
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/crew/playable-v001'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['submit', 'status', 'download'])
parser.add_argument('slugs', nargs='*')
args = parser.parse_args()
slugs = args.slugs or sorted(p.parent.name for p in BASE.glob('*/rig-request.json'))
failures = []
for slug in slugs:
    directory = BASE / slug
    request = directory / 'rig-request.json'
    state_path = directory / 'rig-request.job.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    status = state.get('response', {}).get('status')
    if args.action == 'submit' and state.get('job_id'):
        continue
    if args.action == 'status' and (not state.get('job_id') or status in {'DONE', 'FAILED', 'CANCELLED', 'DLQ'}):
        continue
    output = directory / 'rigged-original.glb'
    if args.action == 'download' and (status != 'DONE' or output.exists()):
        continue
    command = [os.path.expanduser('~/.local/bin/mixar'), '--background', '--factory-startup', '--python-exit-code', '1',
               '--python', str(ROOT / 'scripts/crew_mixar_job.py'), '--', str(request), args.action]
    if args.action == 'download':
        command += ['--output', str(output)]
    with (directory / ('rig-' + args.action + '.log')).open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    print(slug, args.action, state.get('response', {}).get('status'), 'exit', result.returncode, flush=True)
    if result.returncode:
        log_text = (directory / ('rig-' + args.action + '.log')).read_text()
        if args.action == 'submit' and 'Too many active tripo_rig jobs' in log_text:
            print('Mixar active-job capacity reached; remaining requests retained for the next batch.', flush=True)
            break
        failures.append(slug)
if failures:
    raise SystemExit('Failed operations: ' + ', '.join(failures))
