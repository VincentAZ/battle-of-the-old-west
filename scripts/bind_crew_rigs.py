"""Bind downloaded Crew guides locally; report ambiguous anatomy for manual review."""
import os
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/crew/playable-v001'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('slugs', nargs='*')
args = p.parse_args()
slugs = args.slugs or sorted(p.parent.name for p in BASE.glob('*/rigged-original.glb'))
results = {}
for slug in slugs:
    out = BASE/slug
    if (out/'rig-validation.json').exists() and json.loads((out/'rig-validation.json').read_text()).get('status') == 'passed':
        continue
    if slug in {'coach-guard', 'gatling-gunner'}:
        continue
    command = [os.path.expanduser('~/.local/bin/mixar'), '--background', '--factory-startup', '--python-exit-code', '1',
               '--python', str(ROOT/'scripts/rig_crew_mixar.py'), '--', slug]
    if (out/'rig-settings.json').exists():
        command += ['--settings', str(out/'rig-settings.json')]
    for filename in ('explicit-bone-mapping.json', 'explicit-mapping.json'):
        if (out/filename).exists():
            command += ['--mapping', str(out/filename)]
            break
    with (out/'rig-binding.log').open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    results[slug] = result.returncode
    print(slug, 'binding', 'passed' if result.returncode == 0 else 'needs inspection', flush=True)
(BASE/'binding-batch-status.json').write_text(json.dumps(results, indent=2)+'\n')
