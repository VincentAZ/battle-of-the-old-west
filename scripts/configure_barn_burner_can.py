"""Bind the approved Barn Burner kerosene can to its carrying right hand."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/barn-burner'
s=json.loads((out/'rig-settings.json').read_text());c=json.loads((out/'components.json').read_text())
ids=[10,28,34,56,62,69,71,72,78,80,84,85,86,87,88,92,96,99]
indices=sorted({i for n in ids for i in c['components'][n]['indices']})
s['source_geometry_uv_sha256']=c['geometry_uv_sha256'];s['rigid_regions']=[{'name':'KeroseneCan','parent':'RightHand','vertex_indices':indices}]
tool_ids=[39,47,68,97,98]
s['rigid_regions'].append({'name':'BeltTool','parent':'Hips','vertex_indices':sorted({i for n in tool_ids for i in c['components'][n]['indices']})})
s['freeze_bones']=['KeroseneCan','BeltTool'];s['motion_constraints']=[{'type':'preserve_bind_local_transform','bones':['KeroseneCan'],'reason':'The metal kerosene can and wire handle follow the carrying right hand rigidly.'}]
s['can_mask_provenance']={'method':'Complete source UV islands inspected against approved metal can and arched handle. Gloves remain separate unless grip seam correction is required.','component_ids':ids}
s['motion_constraints'].append({'type':'preserve_bind_local_transform','bones':['BeltTool'],'reason':'Belt tool remains rigid relative to hips.'})
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print(len(indices))
