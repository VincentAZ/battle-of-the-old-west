"""Check saved Crimp House visible joinery overlaps and roof clearance."""
from pathlib import Path
import sys,json,hashlib
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
D=Path(sys.argv[sys.argv.index('--')+1]).resolve();P=D/'CrimpHouse.blend'
bpy.ops.wm.open_mainfile(filepath=str(P),use_scripts=False)
obs=[o for o in bpy.context.scene.objects if o.type=='MESH']
def tree(objects):
 pts=[];faces=[]
 for o in objects:
  n=len(pts);pts.extend(o.matrix_world@v.co for v in o.data.vertices);faces.extend([n+i for i in f.vertices]for f in o.data.polygons)
 return BVHTree.FromPolygons(pts,faces)
roof=tree([o for o in obs if 'Roof sheet metal'in o.name])
protrusions=[];count=0
for o in obs:
 if not any(s in o.name for s in('Roof bearing beam','Roof timber deck')):continue
 points=[o.matrix_world@v.co for v in o.data.vertices];top=max(p.z for p in points)
 for p in points:
  if p.z<top-.08:continue
  hit=roof.ray_cast(p+Vector((0,0,5)),Vector((0,0,-1)),10)[0];count+=1
  if hit is not None and p.z>hit.z+1e-5:protrusions.append(dict(object=o.name,point=list(p),roof_z=hit.z))
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
   if(dp>=0)!=(dq>=0):
    t=dp/(dp-dq);poly.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
 return poly
# Joinery and large flat panels, checking same-normal coplanar area only.
groups={};overlaps=[];countfaces=0
for o in obs:
 if not any(s in o.name for s in('jamb','rail','crossbar','mullion','pillar','beam','hood','sill','cornice','Cornice')):continue
 for face in o.data.polygons:
  pts=[o.matrix_world@o.data.vertices[i].co for i in face.vertices];normal=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized();axis=max(range(3),key=lambda k:abs(normal[k]));axes=[k for k in range(3)if k!=axis]
  key=tuple(round(v,5)for v in normal)+(round(normal.dot(pts[0]),5),);poly=[tuple(p[k]for k in axes)for p in pts]
  for name,other in groups.get(key,[]):
   if name==o.name:continue
   if any(max(p[k]for p in poly)<=min(p[k]for p in other)+1e-7 or max(p[k]for p in other)<=min(p[k]for p in poly)+1e-7 for k in(0,1)):continue
   a=area(clip(poly,other))
   if a>1e-7:overlaps.append(dict(a=o.name,b=name,area_m2=a))
  groups.setdefault(key,[]).append((o.name,poly));countfaces+=1
r=dict(status='failed'if protrusions or overlaps else'passed',project_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),scope='Selected joinery planar overlaps and actual roof envelope clearance; not exhaustive intersections or engineering certification.',roof_samples=count,roof_protrusions=protrusions,selected_faces=countfaces,coplanar_overlaps=overlaps)
(D/'surface-audit.json').write_text(json.dumps(r,indent=2)+'\n');(D/'surface-validator-source.py').write_bytes(Path(__file__).read_bytes());print('CRIMP_SURFACE',r['status'],len(protrusions),len(overlaps),flush=True)
assert r['status']=='passed'
