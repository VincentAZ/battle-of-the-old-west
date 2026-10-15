"""Read corrected approved source; export mesh points and barrel landmarks for Unreal readback."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'art/western/crew/playable-v001/gatling-gunner';p=ROOT/'art/western/crew/review-v004/gatling-gunner/review/gatling-gunner-Review.blend'
bpy.ops.wm.open_mainfile(filepath=str(p),use_scripts=False);o=bpy.data.objects['gatling_gunner_Appearance_Review'];vs=[list(o.matrix_world@v.co) for v in o.data.vertices];mask=set(json.loads((out/'rig-settings.json').read_text())['rigid_regions'][0]['vertex_indices'])
front=[i for i in mask if vs[i][1]<-1.47 and vs[i][2]>.97]
back=[i for i in mask if -.67<vs[i][1]<-.55 and -.29<vs[i][0]<-.026 and 1.<vs[i][2]<1.24]
assert len(front)>100 and len(back)>30
r={'source_project_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'vertices_m':vs,'muzzle_front_vertices':front,'barrel_rear_vertices':back,'selection_note':'Front muzzle ring (Y<-1.47m,Z>.97m); rear barrel section (-.67<Y<-.55m,-.29<X<-.026m,1<Z<1.24m). Actual imported nearest vertices determine direction; basis inferred from complete geometry.'}
(out/'gatling-direction-landmarks.json').write_text(json.dumps(r)+'\n');print(len(front),len(back))
