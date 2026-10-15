"""Measure the fitted apron triangles against the unchanged terrain source.

Local Mixar background Python; this is an independent geometry check, not a
claim to read back GPU vertices. Original sources are never saved.
"""
import hashlib
import json
from pathlib import Path
import struct

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/ground-fit-v001'
REFERENCE = ROOT/'art/western/holdings/expansion-game-v001/post-office/ground-clearance-v001.json'
BASE = ROOT/'art/western/holdings/expansion-review-v001/post-office/base-v001/post-office-Base.blend'
TERRAIN = ROOT/'art/world/ContinuousTerrain_Collision.blend'
sources = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE,TERRAIN,REFERENCE,OUT/'T_ArenaGroundHeight.tga']}
native = json.loads(REFERENCE.read_text())['native_component']
assert native['scale'] == [1,1,1] and native['quaternion_xyzw'] == [0,0,0,1]
origin = Vector(native['location'])
raw = (OUT/'T_ArenaGroundHeight.tga').read_bytes()
assert struct.unpack('<BBBHHBHHHHBB',raw[:18])[8:12] == (261,261,24,32)


def at(i,j):
    b,g,r=raw[18+(j*261+i)*3:21+(j*261+i)*3]
    return (r*256+g-32768)/16,b>127


def height(p):
    x,y=(p.x+6500)/50,(p.y+6500)/50
    i,j=int(x),int(y);fx,fy=x-i,y-j
    a,rising=at(i,j);b,_=at(i+1,j);c,_=at(i,j+1);d,_=at(i+1,j+1)
    if rising:return a+(b-a)*fx+(d-b)*fy if fy<=fx else a+(d-c)*fx+(c-a)*fy
    return a+(b-a)*fx+(c-a)*fy if fx+fy<=1 else d+(c-d)*(1-fx)+(b-d)*(1-fy)


bpy.ops.wm.open_mainfile(filepath=str(BASE),use_scripts=False)
obj=bpy.data.objects['Holding_Base_Ground'];obj.data.calc_loop_triangles()
original=[];fitted=[]
for v in obj.data.vertices:
    p=obj.matrix_world@v.co
    p=Vector((-p.x*100,p.y*100,p.z*100))+origin
    original.append(p.copy())
    outside=(max(abs(p.x-origin.x)-225,0)**2+max(abs(p.y-origin.y)-133,0)**2)**.5
    t=min(1,outside/60);weight=t*t*(3-2*t)
    delta=height(p)-origin.z
    p.z+=max(delta,delta*weight)+.5*weight
    fitted.append(p)
triangles=[tuple(t.vertices) for t in obj.data.loop_triangles]
bpy.ops.wm.open_mainfile(filepath=str(TERRAIN),use_scripts=False)
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH');obj.data.calc_loop_triangles()
tree=BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],
    [tuple(t.vertices) for t in obj.data.loop_triangles],all_triangles=True)
errors=[]
for triangle in triangles:
    a,b,c=[fitted[i] for i in triangle]
    for p in [(a+b+c)/3,(a+b)/2,(b+c)/2,(c+a)/2]:
        # The structure covers its central foundation. Measure exposed apron.
        if abs(p.x-origin.x)<209 and abs(p.y-origin.y)<118:continue
        hit,_,_,_=tree.ray_cast(Vector((p.x/100,-p.y/100,100)),Vector((0,0,-1)),200)
        assert hit is not None
        errors.append(dict(world_cm=list(p),clearance_cm=p.z-hit.z*100))
assert errors
for p,digest in sources.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
report=dict(scope=__doc__.strip(),native_reference_sha256=sources[REFERENCE],
    source_sha256={str(p.relative_to(ROOT)):digest for p,digest in sources.items()},sources_unchanged=True,
    fitted_vertices=len(fitted),triangles=len(triangles),exposed_surface_samples=len(errors),
    minimum_clearance_cm=min(s['clearance_cm'] for s in errors),maximum_clearance_cm=max(s['clearance_cm'] for s in errors),
    below_terrain_samples=sum(s['clearance_cm']<0 for s in errors),
    worst_samples=sorted(errors,key=lambda s:s['clearance_cm'])[:20],
    limitations='One recorded native placement; sampled triangle interiors and edges, not continuous or GPU vertex readback.')
assert report['below_terrain_samples']==0, report['worst_samples']
(OUT/'surface-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('HOLDING_GROUND_SURFACE',report['minimum_clearance_cm'],report['maximum_clearance_cm'],report['below_terrain_samples'],flush=True)
