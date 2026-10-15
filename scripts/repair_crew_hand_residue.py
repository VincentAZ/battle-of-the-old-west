"""Apply two source-inspected, bounded wrong-hand influence corrections only."""
import bpy,json,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];assert slug in ['annie-oakley','getaway-rider'];out=root/'art/western/crew/playable-v001'/slug;qa=out/'rig-mask-qa';a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug];p=out/'rig-settings.json';backup=qa/'settings-before-residue.json';blend=qa/'rig-before-residue.blend'
if not backup.exists():shutil.copyfile(p,backup)
if not blend.exists():shutil.copyfile(out/(a['asset_name']+'-Rigged.blend'),blend)
s=json.loads(backup.read_text());bpy.ops.wm.open_mainfile(filepath=str(blend),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];ids={4943} if slug=='annie-oakley' else {208,240,652,2804,2805,5657};coords={tuple(round(x,6) for x in o.data.vertices[i].co) for i in ids};ids|={v.index for v in o.data.vertices if tuple(round(x,6) for x in v.co) in coords};all_rigid={i for r in s.get('rigid_regions',[]) for i in r['vertex_indices']};assert not(ids&all_rigid)
updates=[]
for i in sorted(ids):
 v=o.data.vertices[i];before={o.vertex_groups[g.group].name:g.weight for g in v.groups};after={n:w for n,w in before.items() if not n.startswith('LeftHand')};bad=sum(w for n,w in before.items() if n.startswith('LeftHand'))
 if slug=='getaway-rider':after['RightHand']=after.get('RightHand',0)+bad
 total=sum(after.values());after={n:w/total for n,w in after.items()};updates.append(dict(vertex_indices=[i],weights=after,before=before))
kept=[]
for entry in s.get('weight_overrides',[]):
 remaining=[i for i in entry['vertex_indices'] if i not in ids]
 if remaining:kept.append(dict(entry,vertex_indices=remaining))
s['weight_overrides']=kept+[dict(vertex_indices=x['vertex_indices'],weights=x['weights']) for x in updates];s['bounded_hand_correction_notes']=['Source-inspected isolated coat contamination (Annie) or contralateral fingertip influence (Getaway); preserve geometry and all prior motion constraints.']
p.write_text(json.dumps(s,indent=2)+'\n');(qa/'hand-residue-provenance.json').write_text(json.dumps(dict(slug=slug,source_project_sha256=json.loads((out/'rig-validation.json').read_text())['source_project_sha256'],updates=updates,source_appearance_modified=False),indent=2)+'\n');print(slug,len(ids),flush=True)
