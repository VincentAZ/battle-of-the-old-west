"""Prove inspected coat/right-finger vertices no longer move with unrelated left fingers."""
import bpy,json,sys,hashlib,math
from pathlib import Path
from mathutils import Euler
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug;qa=out/'rig-mask-qa';a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug];r=json.loads((out/'rig-validation.json').read_text());p=out/(a['asset_name']+'-Rigged.blend');assert hashlib.sha256(p.read_bytes()).hexdigest()==r['project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(p),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];arm=bpy.data.objects['Armature'];ids=[i for x in json.loads((qa/'hand-residue-provenance.json').read_text())['updates'] for i in x['vertex_indices']]
def points():
 e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();v={i:e.matrix_world@m.vertices[i].co for i in ids};e.to_mesh_clear();return v
rest=points();tests=[]
for n,angles in [('LeftArm',(0,0,-70)),('LeftForeArm',(0,45,0)),('LeftHand',(0,0,35))]:
 arm.pose.bones[n].rotation_quaternion=Euler([math.radians(x) for x in angles]).to_quaternion();bpy.context.view_layer.update();cur=points();error=max((cur[i]-rest[i]).length for i in ids);tests.append(dict(bone=n,angles=angles,unrelated_motion_max_displacement_m=error))
assert max(x['unrelated_motion_max_displacement_m'] for x in tests)<1e-5
(qa/'hand-residue-stress-review.json').write_text(json.dumps(dict(status='passed',project_sha256=r['project_sha256'],vertices=ids,tests=tests,source_saved=False),indent=2)+'\n');print(tests,flush=True)
