"""Sourced canyon-country setting around the unchanged reviewed cabin."""
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

P=ROOT/'art/western/holdings/expansion-review-v001/robbers-roost'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=json.loads((P/'base-evidence-v001.json').read_text())
assert sha(P/'review-v002/robbers-roost-Review.blend')==evidence['source_review_sha256']
assert json.loads((P/'review-v002/validation.json').read_text())['status']=='passed'
for item in evidence['sources']:
    if item.get('file'):assert sha(ROOT/item['file'])==item['sha256']
assert not (P/'base-v001').exists()
original_scatter=base.scatter


def segment(a,b,radius,tint,objects):
    a,b=Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cone_add(vertices=7,radius1=radius,radius2=radius*.67,depth=(b-a).length,location=(a+b)/2)
    ob=bpy.context.object;ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    ob.name='Juniper irregular branch';ob.color=(*base.srgb(tint),1);objects.append(ob)


def scatter(collection_name,rng,outline,kind,count,palette,keep_out,size=1.,**kwargs):
    if kind!='juniper':
        objects=original_scatter(collection_name,rng,outline,kind,count,palette,keep_out,size,**kwargs)
        if kind=='stone':
            # Blocky sandstone, not rounded river gravel: distort faceted solids.
            for ob in objects:
                for v in ob.data.vertices:
                    v.co.x=math.copysign(abs(v.co.x)**.72,v.co.x)
                    v.co.y=math.copysign(abs(v.co.y)**.72,v.co.y)
        return objects
    objects=[]
    for index,angle in enumerate((.18,2.50)):
        r=outline.radius(angle)*.87;x,y=math.cos(angle)*r,math.sin(angle)*r
        # Named positions are outside the actual cabin and away from front door.
        assert abs(x)>keep_out[0] or abs(y)>keep_out[1],(x,y,keep_out)
        height=1.08 if index==0 else 1.30
        foot=Vector((x,y,0));fork=Vector((x+.10,y-.04,height*.39))
        segment(foot,fork,.065,palette['branch'],objects)
        for j in range(6):
            a=j*math.tau/6+rng.uniform(-.3,.3)
            end=fork+Vector((math.cos(a)*rng.uniform(.28,.48),math.sin(a)*rng.uniform(.25,.40),height*rng.uniform(.30,.53)))
            bend=fork.lerp(end,.55)+Vector((.03,-.02,.07))
            segment(fork,bend,.036,palette['branch'],objects)
            segment(bend,end,.020,palette['branch'],objects)
            for k in range(9):
                origin=bend.lerp(end,rng.uniform(.25,1.13))+Vector((rng.uniform(-.17,.17),rng.uniform(-.17,.17),rng.uniform(-.06,.17)))
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=rng.uniform(.075,.14),location=origin)
                ob=bpy.context.object;ob.name='Juniper scale-foliage cluster'
                ob.scale=(rng.uniform(.75,1.2),rng.uniform(.75,1.2),rng.uniform(.85,1.4))
                ob.color=(*base.srgb(base.lerp(palette['shrub'],palette['shrub_alt'],rng.random())),1)
                objects.append(ob)
        # A short bare limb is consistent with the photographed irregular crown.
        segment(fork,fork+Vector((-.28,.12,.15)),.018,palette['branch'],objects)
    return objects


base.scatter=scatter
sys.argv=[str(Path(base.__file__)),'--','--holding',str(P/'holding-base-v001.json'),'--review',str(P/'review-v002'),'--output',str(P/'base-v001'),'--samples','24']
base.main()
(P/'base-v001/source-script.py').write_bytes(Path(__file__).read_bytes())
assert sha(P/'review-v002/robbers-roost-Review.blend')==evidence['source_review_sha256']
