"""Blend welded satchel/cloth contact while excluding nearby free arm/hand surfaces."""
import bpy,json,sys
from pathlib import Path
from mathutils.kdtree import KDTree
root=Path(__file__).resolve().parents[1];slug='getaway-rider';out=root/'art/western/crew/playable-v001'/slug
bpy.ops.wm.open_mainfile(filepath=str(out/'rig-mask-qa/unblended-rig.blend'),use_scripts=False)
o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];s=json.loads((out/'rig-settings.json').read_text());region=set(s['rigid_regions'][0]['vertex_indices']);all_rigid={i for r in s['rigid_regions'] for i in r['vertex_indices']};points=[o.matrix_world@v.co for v in o.data.vertices]
prop=KDTree(len(region))
for i in region:prop.insert(points[i],i)
prop.balance();seam_ids=[i for i,p in enumerate(points) if i not in region and prop.find(p)[2]<.00001]
# Include actual mixed-face boundary control points; no proximity-only hand binding.
seeds=set(seam_ids)
for edge in o.data.edges:
 a,b=edge.vertices
 if (a in region)!=(b in region):seeds.add(a if a in region else b)
assert seeds
seams=KDTree(len(seeds))
for i in seeds:seams.insert(points[i],i)
seams.balance();overrides=[];excluded=0
for v,p in zip(o.data.vertices,points):
 if v.index in all_rigid:continue
 distance=seams.find(p)[2]
 if distance>=.065:continue
 original={o.vertex_groups[g.group].name:g.weight for g in v.groups}
 arm_weight=sum(w for n,w in original.items() if any(x in n for x in ('Shoulder','Arm','Hand')))
 if arm_weight>.2 and v.index not in seam_ids:
  excluded+=1;continue
 t=min(1,max(0,distance/.065));t=t*t*(3-2*t);weights={n:w*t for n,w in original.items()};weights['Spine2']=weights.get('Spine2',0)+1-t
 overrides.append(dict(vertex_indices=[v.index],weights=weights))
# Keep the cloth immediately behind the shoulder strap in the same transform,
# so rigid leather cannot disappear into differently bending coat surfaces.
by_index={x['vertex_indices'][0]:x for x in overrides}
for v,p in zip(o.data.vertices,points):
 if v.index in all_rigid:continue
 x,y,z=p
 if not (-.27<x<.24 and .025<y and .86<z<1.44):continue
 f=min(1,(y-.025)/.045)*min(1,(z-.86)/.09)
 if f<=0:continue
 original=by_index.get(v.index,{}).get('weights') or {o.vertex_groups[g.group].name:g.weight for g in v.groups}
 weights={n:w*(1-f) for n,w in original.items()};weights['Spine2']=weights.get('Spine2',0)+f
 by_index[v.index]=dict(vertex_indices=[v.index],weights=weights)
overrides=list(by_index.values())
s['weight_overrides']=overrides;s['boundary_blend_notes']=['Fade from actual welded or mixed-face tool/cloth attachment boundaries over6.5cm; free arm/hand surfaces excluded unless physically welded contact.','Original unblended skin weights retained in rig-mask-qa/unblended-rig.blend; no repeated accumulation of smoothing.'];s['boundary_blend_counts']=dict(seam_vertices=len(seam_ids),overrides=len(overrides),free_arm_vertices_excluded=excluded)
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print(s['boundary_blend_counts'],flush=True)
