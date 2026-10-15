"""Keep the map case rigid while blending its fused coat-contact boundary."""
import bpy,json,sys
from pathlib import Path
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1]
slug=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'claim-jumper'
assert slug in {'claim-jumper','annie-oakley','widow-with-a-shotgun'}
OUT=ROOT/'art/western/crew/playable-v001'/slug
record=json.loads((OUT.parent.parent/'review-v003/appearance-approval.json').read_text())['projects'][slug]
bpy.ops.wm.open_mainfile(filepath=str(OUT/(record['asset_name']+'-Rigged.blend')),use_scripts=False)
obj=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review']
s=json.loads((OUT/'rig-settings.json').read_text())
region=set(s['rigid_regions'][0]['vertex_indices'])
assert len(s['rigid_regions'])==1 and s['rigid_regions'][0]['parent']=='Spine2'
points=[obj.matrix_world@v.co for v in obj.data.vertices]
tree=KDTree(len(region))
for i in region:tree.insert(points[i],i)
tree.balance();overrides=[]
for v,p in zip(obj.data.vertices,points):
    if v.index in region:continue
    distance=tree.find(p)[2]
    if distance>=.065:continue
    t=max(0,min(1,distance/.065));t=t*t*(3-2*t)
    weights={obj.vertex_groups[g.group].name:g.weight*t for g in v.groups}
    weights['Spine2']=weights.get('Spine2',0)+(1-t)
    overrides.append({'vertex_indices':[v.index],'weights':weights})
s['weight_overrides']=overrides
s.setdefault('mapping_notes',[]).append('Welded prop-contact vertices share the Spine2 transform, fading into existing coat/strap weights over 6.5 cm to prevent seam tears. No geometry or UV edits.')
(OUT/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n')
print(slug,'rigid attachment boundary blended vertices',len(overrides))
