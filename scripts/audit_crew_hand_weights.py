"""Read-only audit of hand-weighted vertices much closer to the opposite hand."""
import bpy,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'art/western/crew/playable-v001';approval=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'];report=[]
slugs=sys.argv[sys.argv.index('--')+1:] if '--'in sys.argv else list(approval)
for slug in slugs:
 d=base/slug;p=d/(approval[slug]['asset_name']+'-Rigged.blend')
 if not p.exists():continue
 bpy.ops.wm.open_mainfile(filepath=str(p),use_scripts=False);o=bpy.data.objects.get(slug.replace('-','_')+'_Appearance_Review');a=bpy.data.objects.get('Armature')
 if not o or not a:continue
 hands={s:a.matrix_world@a.data.bones[s+'Hand'].head_local for s in ('Left','Right')};sus=[]
 for v in o.data.vertices:
  pos=o.matrix_world@v.co
  for side,other in [('Left','Right'),('Right','Left')]:
   weight=sum(g.weight for g in v.groups if o.vertex_groups[g.group].name.startswith(side+'Hand'))
   if weight<.02:continue
   own=(pos-hands[side]).length;opp=(pos-hands[other]).length
   if own>.28 and own>opp+.15:sus.append(dict(vertex=v.index,group_side=side,weight=weight,position=list(pos),own_hand_distance_m=own,opposite_hand_distance_m=opp))
 r=json.loads((d/'rig-validation.json').read_text());report.append(dict(slug=slug,project_sha256=r['project_sha256'],suspicious_count=len(sus),vertices=sus));print('HAND_AUDIT',slug,len(sus),flush=True)
(base/'integration/hand-weight-distance-audit.json').write_text(json.dumps(dict(method='Read-only candidate detector; hand-weighted vertices >28cm from own hand and >15cm closer to opposite hand. Candidates require visual/source verification, not automatic failure.',records=report),indent=2)+'\n')
