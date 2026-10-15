"""Read-only connected-component bounds for an approved Crew project."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
slug=sys.argv[sys.argv.index('--')+1]
r=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug]
bpy.ops.wm.open_mainfile(filepath=str(root/r['path']),use_scripts=False)
o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];p=list(range(len(o.data.vertices)))
def find(i):
 while p[i]!=i:p[i]=p[p[i]];i=p[i]
 return i
for e in o.data.edges:
 a,b=map(find,e.vertices);p[a]=b
parts={}
for v in o.data.vertices:parts.setdefault(find(v.index),[]).append(v.index)
result=[]
for ids in parts.values():
 points=[o.matrix_world@o.data.vertices[i].co for i in ids]
 result.append(dict(vertices=len(ids),indices=ids,min=[min(p[j] for p in points) for j in range(3)],max=[max(p[j] for p in points) for j in range(3)]))
result.sort(key=lambda c:c['vertices'],reverse=True)
from weather_drifter_review import geometry_hash
out=root/'art/western/crew/playable-v001'/slug/'components.json'
out.write_text(json.dumps(dict(matrix_world=[list(row) for row in o.matrix_world],geometry_uv_sha256=geometry_hash(o),components=result),indent=2)+'\n')
print('COMPONENTS',json.dumps([{k:v for k,v in c.items() if k!='indices'} for c in result[:25]]),flush=True)
