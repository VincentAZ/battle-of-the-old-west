"""Rigid slung long-gun component masks; approved geometry is unchanged."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
slug=sys.argv[1];out=ROOT/'art/western/crew/playable-v001'/slug
c=json.loads((out/'components.json').read_text())
selected={
 'annie-oakley':[31,32,33,35,38,40,45,50,52,53,56,64,67,76,77,78,82,86,88,99,101,111,140,143,147,202],
 'widow-with-a-shotgun':[20,36,51,52,61,64,67,73,76,77,80,91,100,112,120,139,145,150,151]
}[slug]
s=json.loads((out/'rig-settings.json').read_text()) if (out/'rig-settings.json').exists() else {}
s['source_geometry_uv_sha256']=c['geometry_uv_sha256']
s['rigid_regions']=[dict(name='SlungLongGun',parent='Spine2',vertex_indices=sorted(i for n in selected for i in c['components'][n]['indices']))]
s['freeze_bones']=['SlungLongGun']
s['motion_constraints']=[dict(type='preserve_bind_local_transform',bones=['SlungLongGun'],reason='Keep complete slung long gun rigid on upper torso; never blend barrel and stock across spine or hip weights.')]
s['mask_component_ids']=selected
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print(slug,len(s['rigid_regions'][0]['vertex_indices']))
