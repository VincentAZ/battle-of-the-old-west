"""Add the sourced Utah setting to the unchanged reviewed station."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import holdings_base as base

P=ROOT/'art/western/holdings/expansion-review-v001/pony-express-station'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=json.loads((P/'base-evidence-v003.json').read_text())
assert sha(P/'review-v003/pony-express-station-Review.blend')==evidence['source_review_sha256']
assert sha(P/'references/NPS-Simpson-Springs.jpg')==evidence['sources'][0]['sha256']
assert not (P/'base-v003').exists()
original_scatter=base.scatter


def shrubs(collection_name,rng,outline,kind,count,palette,keep_out,size=1.,**kwargs):
    if kind!='shrub':
        return original_scatter(collection_name,rng,outline,kind,count,palette,keep_out,size,**kwargs)
    objects=[];planted=[]
    for attempt in range(300):
        if len(planted)==count:break
        a=rng.uniform(0,math.tau);r=outline.radius(a)*rng.uniform(.79,.85)
        x,y=math.cos(a)*r,math.sin(a)*r
        if abs(x)<keep_out[0]+.4 and abs(y)<keep_out[1]+.4:continue
        if abs(x)<.95 and y<0:continue
        if any(math.hypot(x-u,y-v)<1.0 for u,v in planted):continue
        planted.append((x,y));h=rng.uniform(.35,.55)
        stems=[];tips=[]
        for j in range(13):
            angle=j*math.tau/13+rng.uniform(-.12,.12)
            start=Vector((x,y,.0));spread=rng.uniform(.15,.30)
            end=Vector((x+spread*math.cos(angle),y+spread*math.sin(angle),h*rng.uniform(.70,1)))
            mid=start.lerp(end,.48)+Vector((rng.uniform(-.025,.025),rng.uniform(-.025,.025),.035))
            for a,b,radius in [(start,mid,.007),(mid,end,.004)]:
                bpy.ops.mesh.primitive_cone_add(vertices=5,radius1=radius,radius2=radius*.55,depth=(b-a).length,location=(a+b)/2)
                ob=bpy.context.object;ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();stems.append(ob)
            for k in range(3):
                t=.48+k*.16;p=mid.lerp(end,t)
                direction=Vector((math.cos(angle+k*2.1),math.sin(angle+k*2.1),.8)).normalized()
                tip=p+direction*rng.uniform(.065,.13)
                bpy.ops.mesh.primitive_cone_add(vertices=4,radius1=.0025,radius2=.0008,depth=(tip-p).length,location=(tip+p)/2)
                ob=bpy.context.object;ob.rotation_euler=(tip-p).to_track_quat('Z','Y').to_euler();stems.append(ob)
                tips.append((p,tip))
        bpy.ops.object.select_all(action='DESELECT')
        for ob in stems:ob.select_set(True)
        bpy.context.view_layer.objects.active=stems[0];bpy.ops.object.join();wood=bpy.context.object
        wood.name='Station_shrub_branches';wood.color=(*base.srgb(palette['branch']),1);objects.append(wood)
        clusters=[]
        for p,tip in tips:
            for k in range(5):
                origin=p.lerp(tip,.2+k*.2)
                origin+=Vector((rng.uniform(-.012,.012),rng.uniform(-.012,.012),rng.uniform(-.008,.008)))
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=rng.uniform(.023,.040),location=origin)
                ob=bpy.context.object;ob.scale=(rng.uniform(.65,1),rng.uniform(.65,1),rng.uniform(.8,1.25));clusters.append(ob)
        bpy.ops.object.select_all(action='DESELECT')
        for ob in clusters:ob.select_set(True)
        bpy.context.view_layer.objects.active=clusters[0];bpy.ops.object.join();foliage=bpy.context.object
        foliage.name='Station_shrub_leaf_clusters'
        foliage.color=(*base.srgb(base.lerp(palette['shrub'],palette['shrub_alt'],rng.random())),1);objects.append(foliage)
    assert len(planted)==count,planted
    return objects


base.scatter=shrubs
sys.argv=[str(Path(base.__file__)),'--','--holding',str(P/'holding-base-v003.json'),'--review',str(P/'review-v003'),'--output',str(P/'base-v003')]
base.main()
(P/'base-v003/source-script.py').write_bytes(Path(__file__).read_bytes())
assert sha(P/'review-v003/pony-express-station-Review.blend')==evidence['source_review_sha256']
