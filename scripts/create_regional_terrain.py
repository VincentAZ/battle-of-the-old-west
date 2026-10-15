"""Create a river-channel visual variant while preserving the playing surface.

The original continuous terrain is never saved over. All vertices inside 80m
remain bit-for-bit identical. The original terrain retains runtime collision.
"""
import hashlib
import json
import math
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/regions/terrain-v001'
SOURCE=ROOT/'art/world/ContinuousTerrain.blend'
EVIDENCE=ROOT/'research/western-presentation/regional-battlefields.json'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def river_x(y):return 127+18*math.sin(y/130)+8*math.sin(y/57)


def smooth(a,b,t):
    t=max(0,min(1,(t-a)/(b-a)));return t*t*(3-2*t)


def export(ob):
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    path=OUT/(ob.name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
    return {'name':ob.name,'fbx':path.name,'sha256':digest(path)}


def main():
    assert json.loads(EVIDENCE.read_text())['regions']
    OUT.mkdir(parents=True,exist_ok=True);source_hash=digest(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    ob=next(o for o in bpy.context.scene.objects if o.type=='MESH');ob.name='SM_Region_RiverTerrain'
    protected=[(v.index,tuple(v.co)) for v in ob.data.vertices if v.co.x*v.co.x+v.co.y*v.co.y<=80**2]
    changed=0
    for vertex in ob.data.vertices:
        x,y,z=vertex.co; r=math.hypot(x,y);d=abs(x-river_x(y))
        if r<=80 or abs(y)>1000:continue
        blend=(1-smooth(19,40,d))*smooth(80,100,r)*(1-smooth(900,1000,abs(y)))
        if blend>0:
            vertex.co.z=z*(1-blend)+(-3.1)*blend;changed+=1
    assert all(tuple(ob.data.vertices[i].co)==p for i,p in protected)
    assets=[export(ob)]
    verts=[];faces=[]
    # Channel narrows to a point at both ends beyond the scene's distant hills.
    for i in range(1001):
        y=-950+i*1.9;w=16*(1-smooth(880,950,abs(y)))
        x=river_x(y)
        verts.extend([(x-w,y,-2.75),(x+w,y,-2.75)])
        if i:faces.append((2*i-2,2*i-1,2*i+1,2*i))
    mesh=bpy.data.meshes.new('RiverSurface');mesh.from_pydata(verts,[],faces);mesh.update()
    water=bpy.data.objects.new('SM_Region_RiverWater',mesh);bpy.context.collection.objects.link(water)
    assets.append(export(water));bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'RiverTerrain.blend'))
    assert digest(SOURCE)==source_hash
    report=dict(evidence_sha256=digest(EVIDENCE),source_sha256=source_hash,source_unchanged=True,
                protected_radius_m=80,protected_vertex_count=len(protected),maximum_protected_displacement_m=0,
                changed_vertices=changed,assets=assets,collision='Original source collider retained; new visual meshes have no collision',
                river_course='Reconstructed, not a survey',visual_review='pending')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('REGIONAL_TERRAIN_AUTHORED',changed,flush=True)


if __name__=='__main__':main()
