"""Independent exposed-face overlap and roof-envelope checks on saved source."""
from pathlib import Path
import sys,json,hashlib
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(folder/'VigilanceCommittee.blend'),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
def tree(obs):
 pts=[];polys=[]
 for o in obs:
  start=len(pts);pts.extend(o.matrix_world@v.co for v in o.data.vertices);polys.extend([start+i for i in f.vertices]for f in o.data.polygons)
 return BVHTree.FromPolygons(pts,polys)
roof=tree([o for o in objects if 'roof' in o.name.lower()])
protrusions=[];samples=0
for o in objects:
 if not any(s in o.name for s in ('rubble','mortar core','Rear timber gable')):continue
 for v in o.data.vertices:
  p=o.matrix_world@v.co
  if p.z<3:continue
  samples+=1;hit=roof.ray_cast(p+Vector((0,0,2)),Vector((0,0,-1)),4)[0]
  if hit is None or p.z>hit.z+1e-5:protrusions.append(dict(object=o.name,point=list(p),roof_z=hit.z if hit else None))
def area(p):return abs(sum(a[0]*b[1]-a[1]*b[0]for a,b in zip(p,p[1:]+p[:1])))/2 if p else 0
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def clip(poly,edge):
 sign=1 if sum(a[0]*b[1]-a[1]*b[0]for a,b in zip(edge,edge[1:]+edge[:1]))>0 else -1
 for a,b in zip(edge,edge[1:]+edge[:1]):
  old=poly;poly=[]
  if not old:break
  for p,q in zip(old,old[1:]+old[:1]):
   dp=sign*cross(a,b,p);dq=sign*cross(a,b,q)
   if dp>=-1e-9:poly.append(p)
   if (dp>=0)!=(dq>=0):
    t=dp/(dp-dq);poly.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
 return poly
# Check the exposed front plane of joinery/plaster and all shingle faces.
# Buried back-to-back contacts are opposed normals and excluded naturally.
groups={};overlaps=[];faces=0;comparisons=0
for o in objects:
 isroof='shingle' in o.name
 if not isroof and not any(s in o.name for s in ('French door','Upper sash','Scored lime','Front masonry','Front plaster','Door jamb','Door head')):continue
 for f in o.data.polygons:
  pts=[o.matrix_world@o.data.vertices[i].co for i in f.vertices];normal=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized()
  if not isroof and normal.y>-.999:continue
  key=tuple(round(x,5)for x in normal)+(round(normal.dot(pts[0]),5),)
  axis=max(range(3),key=lambda k:abs(normal[k]));axes=[k for k in range(3)if k!=axis];poly=[tuple(p[k]for k in axes)for p in pts]
  for name,other in groups.get(key,[]):
   if name==o.name:continue
   if any(max(p[k]for p in poly)<=min(p[k]for p in other)+1e-7 or max(p[k]for p in other)<=min(p[k]for p in poly)+1e-7 for k in (0,1)):continue
   comparisons+=1;overlap=area(clip(poly,other))
   if overlap>1e-7:overlaps.append(dict(a=o.name,b=name,area=overlap))
  groups.setdefault(key,[]).append((o.name,poly));faces+=1
d=dict(status='passed'if not protrusions and not overlaps else 'failed',project_sha256=hashlib.sha256((folder/'VigilanceCommittee.blend').read_bytes()).hexdigest(),roof_envelope_samples=samples,roof_protrusions=protrusions,exposed_faces_checked=faces,coplanar_comparisons=comparisons,coplanar_overlaps=overlaps,scope='Selected roof and front exposed surfaces; not an exhaustive intersection or structural analysis.')
(folder/'surface-audit.json').write_text(json.dumps(d,indent=2)+'\n')
(folder/'surface-validator-source.py').write_bytes(Path(__file__).read_bytes())
print('SURFACE_AUDIT',d['status'],samples,len(protrusions),faces,len(overlaps),flush=True)
assert d['status']=='passed'
