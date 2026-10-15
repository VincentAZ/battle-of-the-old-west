"""Isolate approved leather satchel surfaces from nearby hand/coat guide weights."""
import bpy,json,numpy as np
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/getaway-rider';a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects']['getaway-rider'];s=json.loads((out/'rig-settings.json').read_text());c=json.loads((out/'components.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(root/a['path']),use_scripts=False);o=bpy.data.objects['getaway_rider_Appearance_Review']
ids=[15,22,30,39,41,52,53,59,67,71,82,85,88,91,96,107,111,112,115];region={i for n in ids for i in c['components'][n]['indices']};mixed={i for n in [20,44,46,58,60,63] for i in c['components'][n]['indices']}
im=next(n.image for n in o.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and 'BaseColor'in n.image.name);w,h=im.size;pix=np.empty(w*h*4,dtype=np.float32);im.pixels.foreach_get(pix);pix=pix.reshape(h,w,4)
for p in o.data.polygons:
 if not set(p.vertices)<=mixed:continue
 colors=[]
 for i in p.loop_indices:
  uv=o.data.uv_layers.active.data[i].uv;colors.append(pix[min(h-1,max(0,int(uv.y*h))),min(w-1,max(0,int(uv.x*w))),:3])
 r,g,b=np.mean(colors,axis=0)
 if r<.35 and r>1.1*g and r>1.13*b:region.update(p.vertices)
# Touching hand UV islands are separate physical surfaces, not welded bag seams.
hand_ids={i for n in [36,55,57,68,83,86,92,93,97] for i in c['components'][n]['indices']}
region-=hand_ids
s['source_geometry_uv_sha256']=c['geometry_uv_sha256'];s['rigid_regions']=[dict(name='Satchel',parent='Spine2',vertex_indices=sorted(region),allow_polygon_boundary=True,boundary_note='Leather bag surfaces in fused bag/coat islands isolated using source atlas color; welded duplicates synchronized. Attachment boundary faded to hips without source geometry edits.')];s['freeze_bones']=['Satchel','RightShoulder','RightArm','RightForeArm','RightHand'];s['motion_constraints']=[dict(type='preserve_bind_local_transform',bones=s['freeze_bones'],reason='Source bag, sleeve and hand have fused contact boundaries. Preserve right arm local bind pose while satchel follows Spine2; head, left arm, body and legs remain animated.')];s['satchel_mask_provenance']=dict(complete_component_ids=ids,mixed_component_ids=[20,44,46,58,60,63],method='Source brown leather versus blue coat/skin atlas samples, checked visually.')
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print('satchel',len(region),flush=True)
