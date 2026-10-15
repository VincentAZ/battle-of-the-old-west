"""Blend a rigid hand region into its welded palm/wrist; preserve other settings."""
import bpy,json,sys,shutil
from pathlib import Path
from mathutils.kdtree import KDTree
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug;s=json.loads((out/'rig-settings.json').read_text());a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug];qa=out/'rig-mask-qa';baseline=qa/'unblended-hand-rig.blend'
if not baseline.exists():shutil.copyfile(out/(a['asset_name']+'-Rigged.blend'),baseline)
bpy.ops.wm.open_mainfile(filepath=str(baseline),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];region=s['rigid_regions'][-1];ids=set(region['vertex_indices']);all_ids={i for r in s['rigid_regions'] for i in r['vertex_indices']};points=[o.matrix_world@v.co for v in o.data.vertices];tree=KDTree(len(ids))
for i in ids:tree.insert(points[i],i)
tree.balance();seams=[i for i,p in enumerate(points) if i not in ids and tree.find(p)[2]<.00001];assert seams
near=KDTree(len(seams))
for i in seams:near.insert(points[i],i)
near.balance();overrides={i:x for x in s.get('weight_overrides',[]) for i in x['vertex_indices']}
for v,p in zip(o.data.vertices,points):
 if v.index in all_ids:continue
 d=near.find(p)[2]
 if d>=.035:continue
 t=min(1,max(0,d/.035));t=t*t*(3-2*t);weights={o.vertex_groups[g.group].name:g.weight*t for g in v.groups};parent=region['parent'];weights[parent]=weights.get(parent,0)+1-t;overrides[v.index]=dict(vertex_indices=[v.index],weights=weights)
s['weight_overrides']=list({json.dumps(x,sort_keys=True):x for x in overrides.values()}.values());s['hand_boundary_notes']=['Rigid free-hand seam duplicates receive matching hand weights, with3.5cm fade into original palm/wrist weights. Original geometry/UV unchanged.']
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print('wrist seams',len(seams),'overrides',len(overrides),flush=True)
