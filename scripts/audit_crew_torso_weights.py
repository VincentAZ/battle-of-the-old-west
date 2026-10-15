"""Read-only central torso influence audit for common extreme-pose deformation."""
import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'art/western/crew/playable-v001';a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'];rows=[]
for slug in ['barn-burner','jesse-james','claim-jumper','laudanum-doctor','doc-holliday','duelist','bartender','bass-reeves','annie-oakley']:
 d=base/slug;bpy.ops.wm.open_mainfile(filepath=str(d/(a[slug]['asset_name']+'-Rigged.blend')),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];samples=[]
 for v in o.data.vertices:
  x,y,z=o.matrix_world@v.co
  if not(abs(x)<.11 and y>.035 and 1.0<z<1.40):continue
  w={o.vertex_groups[g.group].name:g.weight for g in v.groups};aw=sum(v for n,v in w.items() if any(q in n for q in ['Arm','Shoulder','Hand']));samples.append(dict(vertex=v.index,position=[x,y,z],arm_weight=aw,weights=w))
 r=json.loads((d/'rig-validation.json').read_text());row=dict(slug=slug,project_sha256=r['project_sha256'],central_back_vertices=len(samples),count_arm_weight_over_point25=sum(x['arm_weight']>.25 for x in samples),worst=sorted(samples,key=lambda x:-x['arm_weight'])[:20]);rows.append(row);print('TORSO',slug,row['central_back_vertices'],row['count_arm_weight_over_point25'],row['worst'][:1],flush=True)
(base/'integration/torso-influence-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
