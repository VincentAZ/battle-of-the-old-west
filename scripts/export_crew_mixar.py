"""Export exact approved Crew appearances for guide rigging in Mixar."""
import bpy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/crew'
approval = json.loads((BASE / 'review-v003/appearance-approval.json').read_text())
assert approval['rigging_authorized']
slugs = sys.argv[sys.argv.index('--') + 1:]
assert slugs
if slugs == ['all']:
    slugs = [s for s in approval['projects'] if s not in {'quanah-parker', 'lozen', 'sarah-winnemucca'}
             and not (BASE / 'playable-v001' / s / 'approved.glb').exists()]
audits = {v['slug']: v for p in (ROOT / 'research/crew-history-audit').glob('audit-*.json') for v in json.loads(p.read_text())}
for slug in slugs:
    record = approval['projects'][slug]
    source = ROOT / record['path']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256']
    out = BASE / 'playable-v001' / slug
    out.mkdir(exist_ok=True)
    target = out / 'approved.glb'
    assert not target.exists(), 'Preserve existing exports'
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    obj = bpy.data.objects[slug.replace('-', '_') + '_Appearance_Review']
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(target), use_selection=True, export_format='GLB')
    evidence = dict(audits[slug])
    selected = ROOT / record['directory'] / 'historical-review.json'
    if selected.exists():
        evidence['approved_revision'] = json.loads(selected.read_text())
    evidence['render_brief'] = 'Rig and animate this exact user-approved appearance; preserve geometry, UVs and materials.'
    (out / 'historical-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    request = {'service': 'tripo_rig', 'model': 'tripo_rig_v2_5', 'mesh': 'approved.glb',
               'input_name': record['display_name'], 'historical_evidence': 'historical-evidence.json',
               'params': {'spec': 'mixamo', 'rig_type': 'biped'}}
    (out / 'rig-request.json').write_text(json.dumps(request, indent=2) + '\n')
    print('CREW_EXPORTED', slug, flush=True)
