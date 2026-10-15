"""Isolate gun-colored faces in two fused coat/gun islands; preserve all geometry."""
import bpy,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/widow-with-a-shotgun'
s=json.loads((out/'rig-settings.json').read_text());r=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects']['widow-with-a-shotgun']
bpy.ops.wm.open_mainfile(filepath=str(root/r['path']),use_scripts=False);o=bpy.data.objects['widow_with_a_shotgun_Appearance_Review']
c=json.loads((out/'components.json').read_text())['components'];mixed=set(c[37]['indices']+c[57]['indices'])
image=next(n.image for n in o.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and 'BaseColor'in n.image.name)
w,h=image.size;pixels=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(pixels);pixels=pixels.reshape(h,w,4)
region=set(s['rigid_regions'][0]['vertex_indices']);painted=[]
for p in o.data.polygons:
 if not set(p.vertices)<=mixed:continue
 colors=[]
 for i in p.loop_indices:
  uv=o.data.uv_layers.active.data[i].uv;colors.append(pixels[min(h-1,max(0,int(uv.y*h))),min(w-1,max(0,int(uv.x*w))),:3])
 red,green,blue=np.mean(colors,axis=0)
 if red>.065 and red>1.23*green and red>1.45*blue:
  region.update(p.vertices);painted.append(p.index)
# UV seams must retain identical weights at physically shared source positions.
positions={tuple(round(x,6) for x in o.data.vertices[i].co) for i in region}
region.update(v.index for v in o.data.vertices if tuple(round(x,6) for x in v.co) in positions)
s['rigid_regions'][0].update(vertex_indices=sorted(region),allow_polygon_boundary=True,boundary_note='Two fused gun/coat islands use texture-verified gun-face selection with welded duplicate vertices synchronized; torso boundary weights fade over6.5cm and must pass stress QA.')
s['painted_mixed_gun_polygons']=painted
s['mask_notes']=['Most gunparts isolated as complete islands; two source fused gun/back-cloth islands require selected wood-colored faces. No topology/coordinate/UV edits.','Welded UV seam duplicates share rigid selection; parent-Spine2 boundary smoothing required before final export.']
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print('selected',len(region),'painted faces',len(painted),flush=True)
