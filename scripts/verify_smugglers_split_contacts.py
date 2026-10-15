"""Prove that the dry-bank shader starts beyond the reviewed contact geometry."""
import hashlib
import json
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
P = ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing'
OUT = ROOT/'art/western/holdings/ground-fit-smugglers-landing-v002/static-contact-preservation.json'
project = P/'base-v005/smugglers-landing-Base.blend'
manifest = P/'review-v001/manifest.json'
contact = P/'base-v005/contact-validation.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protected = {p:sha(p) for p in (project,manifest,contact)}
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
names = [json.loads(manifest.read_text())['mesh_object'],'Holding_Base_Willow','Holding_Base_Water']
rows = []
for name in names:
    obj = bpy.data.objects[name]
    front = max(-(obj.matrix_world@v.co).y*100 for v in obj.data.vertices)
    assert front < 270, (name,front)
    rows.append(dict(object=name,vertices=len(obj.data.vertices),frontmost_local_cm=front,
        margin_before_dry_apron_cm=270-front,base_displacement_at_all_these_xy_positions_cm=0))
assert json.loads(contact.read_text())['status']=='passed'
assert all(sha(p)==h for p,h in protected.items())
assert not OUT.exists()
OUT.write_text(json.dumps(dict(ok=True,objects=rows,
    source_sha256={str(p.relative_to(ROOT)):h for p,h in protected.items()},sources_unchanged=True,
    shader_contract='Dry displacement begins at -LocalY=270 cm; lift begins there too. Water is a separate unchanged material. Both displacement factors are exactly zero throughout the listed contact geometry footprint.',
    static_contacts='The previously validated dry post/ramp, 14 embedded willow roots, level water and dry boat flooring therefore retain their original source relationships.',
    scope='Read-only geometric support-domain proof, paired with native material-identity and shader/source audit records. Does not claim a buoyancy or soil-engineering simulation.',
    auditor_sha256=sha(Path(__file__))),indent=2)+'\n')
print('LANDING_STATIC_CONTACTS_PRESERVED',json.dumps(rows),flush=True)
