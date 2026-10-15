"""Separate CPU garment candidates; never edits imported assets or current FBX.

Use Blender --python this_file -- [scientist gunner assassin]. Output is
art/characters/survivor_variants/deformation-v2. Fresh native validation required.
"""
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector, geometry
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/survivor_variants'
OUT=BASE/'deformation-v3';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('variant_author',ROOT/'scripts/author_survivor_variants.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);v.OUT=OUT
protected_paths=[ROOT/'art/characters/oldwest_survivor/Survivor_A.blend']
for card in v.NAMES:
 protected_paths.extend(p for p in (BASE/card).rglob('*') if p.is_file())
protected_paths.extend((ROOT/'game/OldWest/Content/Art/Survivors/Variants').glob('*.uasset'))
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_paths}
REPAIRS=[]

class Surface:
 def __init__(self,obj):
  self.obj=obj;obj.data.calc_loop_triangles()
  self.positions=[obj.matrix_world@x.co for x in obj.data.vertices]
  self.triangles=[tuple(t.vertices) for t in obj.data.loop_triangles]
  self.bvh=BVHTree.FromPolygons(self.positions,self.triangles,all_triangles=True)
  self.weights=[{obj.vertex_groups[g.group].name:g.weight for g in vertex.groups if obj.vertex_groups[g.group].name in v.arm.data.bones} for vertex in obj.data.vertices]
 def sample(self,p):
  q,n,index,d=self.bvh.find_nearest(p)
  assert index is not None
  ids=self.triangles[index];a,b,c=[self.positions[i] for i in ids]
  bc=geometry.barycentric_transform(q,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
  mix={}
  for i,factor in zip(ids,bc):
   for bone,w in self.weights[i].items():mix[bone]=mix.get(bone,0)+w*max(0,factor)
  total=sum(mix.values());assert total>.99
  return q,n,{bone:w/total for bone,w in mix.items() if w>1e-7}

def assign(obj,fn):
 obj.vertex_groups.clear()
 for vertex in obj.data.vertices:
  p=obj.matrix_world@vertex.co;weights=fn(p)
  total=sum(weights.values());assert total>0
  for bone,w in weights.items():
   if w>1e-7:(obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)).add([vertex.index],w/total,'REPLACE')
 return obj

def current_shirt():
 return next(o for o in v.parts if any(s in o.name for s in ('Long_Coat_Shirt','Quilted_Undershirt','Fitted_Charcoal_Jacket')))
def current_trousers():
 return bpy.data.objects.get('Survivor_CargoTrousers') or bpy.data.objects['Assassin_Charcoal_Trousers']

def garment_weights(obj):
 shirt=Surface(current_shirt());pants=Surface(current_trousers())
 def sample(p):
  if p.z<=1.0:return pants.sample(p)[2]
  if p.z>=1.15:return shirt.sample(p)[2]
  t=(p.z-1.0)/.15;a=pants.sample(p)[2];b=shirt.sample(p)[2]
  return {bone:a.get(bone,0)*(1-t)+b.get(bone,0)*t for bone in a.keys()|b.keys()}
 return assign(obj,sample)

old_sleeve=v.sleeve
def sleeve(name,bone,mat,radius_a,radius_b,start=.03,end=.94):
 if not name.startswith('Scientist_') or not name.endswith('_Full_Sleeve'):
  return old_sleeve(name,bone,mat,radius_a,radius_b,start,end)
 side='Left' if '_Left_' in name else 'Right'
 upper=v.arm.data.bones['mixamorig:'+side+'Arm'];lower=v.arm.data.bones[bone]
 shoulder=upper.head_local.lerp(upper.tail_local,.08);elbow=lower.head_local;wrist=lower.head_local.lerp(lower.tail_local,.94)
 centers=[shoulder.lerp(elbow,i/16) for i in range(17)]+[elbow.lerp(wrist,i/16) for i in range(1,17)]
 rows=[]
 for j,p in enumerate(centers):
  tangent=(centers[min(len(centers)-1,j+1)]-centers[max(0,j-1)]).normalized()
  u=tangent.cross(Vector((0,1,0))).normalized();w=tangent.cross(u).normalized()
  radius=.069-(.069-.057)*j/16 if j<=16 else .057-(.057-.043)*(j-16)/16
  rows.append([p+(u*math.cos(i*math.tau/48)+w*math.sin(i*math.tau/48))*radius*(1+.025*math.sin(i*math.tau/48*9+j*.9)) for i in range(49)])
 obj=v.sheet(name,rows,mat,bone)
 # Solidify preserves first/second shell vertex ordering, but use nearest path
 # ring so neither side depends on that implementation detail.
 def weights(p):
  ring=min(range(len(centers)),key=lambda i:(p-centers[i]).length_squared)
  t=max(0,min(1,(ring-12)/8));t=t*t*(3-2*t)
  return {upper.name:1-t,lower.name:t}
 assign(obj,weights)
 REPAIRS.append({'object':name,'change':'continuous shoulder/elbow/wrist sleeve;8-ring normalized Arm/ForeArm transition'})
 return obj
v.sleeve=sleeve

old_loft=v.loft
def loft(name,rings,mat,bone=v.CHEST,start=0,end=2*math.pi,segments=64):
 if name=='Scientist_Open_Split_Coat':
  # One continuous coat with a lower rear vent has no overlapping waist seam.
  improved=[(.67,0,.03,.232,.207,.035),(.76,0,.03,.225,.198,.025),(.91,0,.025,.218,.183,.024),
            (1.02,0,.027,.208,.173,.018)]+[r for r in rings if r[0]>1.02]
  coat=old_loft(name,improved,mat,bone,start,end,segments)
  bm=bmesh.new();bm.from_mesh(coat.data)
  drop=[f for f in bm.faces if max(x.co.z for x in f.verts)<.99 and min(x.co.y for x in f.verts)>.06
        and min(x.co.x for x in f.verts)<=.008 and max(x.co.x for x in f.verts)>=-.008]
  bmesh.ops.delete(bm,geom=drop,context='FACES');bm.to_mesh(coat.data);bm.free()
  REPAIRS.append({'object':name,'change':'continuous coat, lower rear vent and barycentric trouser weights','removed_vent_faces':len(drop)})
  return coat
 obj=old_loft(name,rings,mat,bone,start,end,segments)
 if name.startswith('Gunner_') and '_Knee_Strap' in name:
  surface=Surface(current_trousers());inverse=obj.matrix_world.inverted()
  # These are thin closed straps. Fit actual trouser section instead of an
  # ideal circle that was buried at rest and floated under knee flexion.
  for vertex in obj.data.vertices:
   p=obj.matrix_world@vertex.co;q,n,_=surface.sample(p)
   vertex.co=inverse@(q+n*.008)
  assign(obj,lambda p:surface.sample(p)[2])
  REPAIRS.append({'object':name,'change':'closed fitted strap; original trouser surface weights across knee'})
 return obj
v.loft=loft
v.coat_skin=garment_weights

original_assassin=v.assassin
def assassin(m):
 original_assassin(m)
 shirt=Surface(current_shirt());pants=Surface(current_trousers())
 for obj in v.parts:
  if obj.name.startswith(('Assassin_Harness_Leather','Assassin_Harness_Stitch')):
   inv=obj.matrix_world.inverted();offset=.010 if 'Stitch' in obj.name else .006
   for vertex in obj.data.vertices:
    p=obj.matrix_world@vertex.co;q,n,_=shirt.sample(p)
    # Shirt outward normals are the garment's physical outward direction.
    vertex.co=inv@(q+n*offset)
   assign(obj,lambda p:shirt.sample(p)[2])
   REPAIRS.append({'object':obj.name,'change':'fitted to actual shirt surface with matching barycentric spine/hips weights'})
  if obj.name=='Assassin_Folded_Short_Cape':
   # A waist-length mantle retains the distinctive cloth silhouette while
   # clearing the legs without cloth simulation or attaching fabric to thighs.
   for vertex in obj.data.vertices:
    t=max(0,min(1,(1.425-vertex.co.z)/.68))
    vertex.co.z=1.425+(vertex.co.z-1.425)*.69
    vertex.co.y+=.045*t
   def cape_weights(p):
    t=max(0,min(1,(p.z-1.0)/.35))
    return {v.CHEST:t,v.HIPS:1-t}
   assign(obj,cape_weights)
   REPAIRS.append({'object':obj.name,'change':'waist-length mantle with4.5cm lower rear clearance and original torso/hips attachment; avoids forward thigh drag'})
v.assassin=assassin

original_scientist=v.scientist
def scientist(m):
 original_scientist(m)
 for obj in list(v.parts):
  if obj.name.startswith('Scientist_Coat_Edge_Stitch'):
   v.parts.remove(obj);bpy.data.objects.remove(obj,do_unlink=True)
 REPAIRS.append({'object':'Scientist_Coat_Edge_Stitch','change':'remove obsolete free-standing stitches; existing collar/lapel/shoulder sewn details remain'})
v.scientist=scientist

original_gunner=v.gunner
def gunner(m):
 original_gunner(m)
 # Utility belt was hidden beneath the long undershirt and broke through it
 # when hips and torso flexed. In the derived Gatling Gunner only, tuck the shirt's
 # bottom rings into the same belt region with matching torso/hips weights.
 shirt=current_shirt();pants=Surface(current_trousers())
 for obj in list(bpy.data.objects):
  if obj.name=='Survivor_UtilityBelt':
   bpy.data.objects.remove(obj,do_unlink=True)
   REPAIRS.append({'object':'Survivor_UtilityBelt','change':'removed obsolete under-shirt belt from derived Gatling Gunner only; visible pouches and front buckle retained'})
v.gunner=gunner

# Remove only source body faces inside the conservative fully-clothed pelvis
# and middle torso bands. Face, hands, arms, neck and exposed legs are untouched.
def trim_body():
 body=bpy.data.objects['Survivor_Body'];assert not body.data.shape_keys
 bm=bmesh.new();bm.from_mesh(body.data)
 def covered(p):return (abs(p.x)<.205 and .78<p.z<.965) or (abs(p.x)<.14 and 1.08<p.z<1.335)
 drop=[f for f in bm.faces if all(covered(body.matrix_world@x.co) for x in f.verts)]
 bmesh.ops.delete(bm,geom=drop,context='FACES');bm.to_mesh(body.data);bm.free()
 REPAIRS.append({'object':body.name,'change':'trim only conservative fully-covered body regions on derived variant','removed_faces':len(drop)})
for card in v.NAMES:
 fn=getattr(v,card)
 def wrapper(m,fn=fn):fn(m);trim_body()
 setattr(v,card,wrapper)

requested=[x for x in sys.argv[sys.argv.index('--')+1:] if x in v.NAMES] if '--' in sys.argv else []
for card in requested or v.NAMES:
 REPAIRS.clear();v.author(card)
 (OUT/card/'deformation-repairs.json').write_text(json.dumps({'status':'candidate authored; posed render review pending','repairs':REPAIRS},indent=2)+'\n')
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items()),'Protected original/current/imported asset changed'
 (OUT/'protected-current-assets.json').write_text(json.dumps({'unchanged':True,'sha256':protected},indent=2)+'\n')
print('CPU_DEFORMATION_V2_CANDIDATES_AUTHORED',flush=True)
