"""Exact complete-island rifle/grip mask for approved Sharpshooter, no mesh edits."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/western/crew/playable-v001/sharpshooter'
c=json.loads((OUT/'components.json').read_text());s=json.loads((OUT/'rig-settings.json').read_text())
components=[7,35,39,40,44,45,51,52,53,59,60,68,70,71,77,79,81,84,87,95]
indices=sorted(i for n in components for i in c['components'][n]['indices'])
s['source_geometry_uv_sha256']=c['geometry_uv_sha256']
s['rigid_regions']=[dict(name='Rifle',parent='root',vertex_indices=indices)]
s['freeze_bones']=['root','Hips','Spine','Spine1','Spine2','RightShoulder','RightArm','RightForeArm','RightHand','Rifle']+[side+'Hand'+f+str(i) for side in ('Left','Right') for f in ('Thumb','Index','Middle','Ring','Pinky') for i in range(1,4)]
s['motion_constraints']=[dict(type='preserve_bind_local_transform',bones=s['freeze_bones'],reason='Upright rifle butt remains planted at source ground contact; gripping arm and torso chain stay in approved rest pose. Head and free left arm retain body-clip movement.'),'No walking or gun-aiming clip until separately authored grip and ground-contact poses.']
s['mask_component_ids']=components
s['mask_notes']=['Twenty complete UV islands include rifle and fused gripping hand; adjacent sleeve islands18and50excluded. Restored source pose; no geometric changes.']
(OUT/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n')
print('rifle/grip vertices',len(indices))
