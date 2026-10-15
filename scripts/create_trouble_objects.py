"""Locally author a sourced quarantine flag and period-style poker-card fan."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import create_trouble_landscapes as geo

EVIDENCE=ROOT/'research/western-presentation/trouble-objects.json'
OUT=ROOT/'art/western/trouble/objects-v002'
COLOURS={'Earth':(.19,.083,.025),'Wood':(.29,.125,.034),'WoodLight':(.41,.21,.069),
         'WoodDark':(.13,.047,.012),'Iron':(.035,.031,.025),'Yellow':(.95,.59,.006),
         'Seam':(.71,.39,.003),'Paper':(.94,.90,.78),'PaperEdge':(.58,.51,.36),
         'BlackInk':(.007,.008,.011),'RedInk':(.66,.006,.01),'Cloud':(.14,.19,.26)}


def box(name,location,dimensions,material,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location);obj=bpy.context.object;obj.name=name
    obj.dimensions=dimensions;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(geo.MATS[material])
    if bevel:
        mod=obj.modifiers.new('RoundedToolEdges','BEVEL');mod.width=bevel;mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    geo.PARTS.append(obj);return obj


def rod(name,a,b,radius,material):
    a,b=Vector(a),Vector(b);d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=radius,depth=d.length,location=(a+b)/2)
    obj=bpy.context.object;obj.name=name;obj.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    obj.data.materials.append(geo.MATS[material]);geo.PARTS.append(obj);return obj


def curve(name,points,radius,material):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=radius;data.bevel_resolution=1
    sp=data.splines.new('POLY');sp.points.add(len(points)-1)
    for p,xyz in zip(sp.points,points):p.co=(*xyz,1)
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.data.materials.append(geo.MATS[material])
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH');geo.PARTS.append(bpy.context.object)


def quarantine():
    geo.base()
    # Only a doorway fragment: the building beyond is deliberately unspecified.
    for i in range(6):
        x=-.52+i*.155
        box('DoorPlank',(x,.20,.69),(.149,.047,1.12),'WoodLight' if i%3==0 else 'Wood',.004)
        # Shallow grain lines use actual geometry, and survive the material-only import.
        for j in range(3):
            points=[(x-.05+j*.047+.004*math.sin(k*.7+i),.173,.17+k*.068) for k in range(16)]
            curve('WoodGrain',points,.0012,'WoodDark')
    for x in (-.63,.40):box('DoorJamb',(x,.18,.72),(.11,.13,1.28),'WoodDark',.008)
    box('DoorLintel',(-.115,.18,1.39),(1.14,.15,.13),'WoodLight',.008)
    box('DoorBrace',(-.115,.157,.38),(.94,.048,.09),'WoodDark',.004)
    box('DoorBrace',(-.115,.157,1.03),(.94,.048,.09),'WoodDark',.004)
    rod('PlainWoodPole',(-.65,-.24,.08),(-.65,-.24,2.0),.026,'WoodLight')
    def point(u,v):
        return (-.65+1.19*u,-.24+.11*math.sin(u*8-v*2)*u,1.91-.71*v-.10*u*u)
    verts=[point(i/52,j/24) for j in range(25) for i in range(53)]
    faces=[(j*53+i,j*53+i+1,(j+1)*53+i+1,(j+1)*53+i) for j in range(24) for i in range(52)]
    flag=geo.mesh('YellowCloth',verts,faces,['Yellow'],smooth=True)
    bpy.context.view_layer.objects.active=flag;flag.select_set(True)
    solid=flag.modifiers.new('ClothThickness','SOLIDIFY');solid.thickness=.002
    bpy.ops.object.modifier_apply(modifier=solid.name)
    for v in (0,1):curve('SewnEdge',[point(i/60,v) for i in range(61)],.003,'Seam')
    curve('SewnEdge',[point(1,j/30) for j in range(31)],.003,'Seam')
    for z in (1.90,1.21):
        curve('ClothTie',[(-.65+.03*math.cos(i*math.tau/24),-.24+.03*math.sin(i*math.tau/24),z) for i in range(25)],.005,'PaperEdge')


def pip(kind,x,y,z,size):
    # Flat geometric print outlines; no raster photo, brand art or invented face cards.
    if kind=='diamond':points=[(0,1),(.65,0),(0,-1),(-.65,0)]
    elif kind in ('heart','spade'):
        points=[]
        for i in range(64):
            t=i*math.tau/64
            px=16*math.sin(t)**3/17;py=(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))/17
            points.append((px,-py if kind=='spade' else py))
    else:
        points=[]
        # Three rounded lobes joined around one center.
        for i in range(96):
            a=i*math.tau/96;r=.63+.32*math.cos(3*(a-math.pi/2));points.append((r*math.cos(a),r*math.sin(a)))
    mat='RedInk' if kind in ('heart','diamond') else 'BlackInk'
    obj=geo.mesh('PrintedSuit',[(x+px*size,y+py*size,z) for px,py in points],[tuple(range(len(points)))],[mat])
    if kind in ('spade','club'):
        geo.mesh('PrintedStem',[(x-.10*size,y-.40*size,z+.0001),(x+.10*size,y-.40*size,z+.0001),
            (x+.27*size,y-1.08*size,z+.0001),(x-.27*size,y-1.08*size,z+.0001)],[(0,1,2,3)],[mat])
    return obj


def poker():
    # Display support is a game-piece base, not an asserted historic table.
    for i in range(7):box('DisplayPlank',(-.78+i*.26,0,.10),(.255,1.34,.16),'WoodLight' if i%3==0 else 'Wood',.011)
    for x in (-.6,.6):box('BaseBatten',(x,0,.025),(.11,1.18,.045),'WoodDark',.005)
    for i in range(14):box('SquaredDeck',(.56,.36,.192+i*.007),(.28,.43,.006),'Paper' if i%2 else 'PaperEdge',.0007)
    # A fan of As,4c,4s,4h,4d: the period hand explicitly cataloged by the Met.
    for i,kind in enumerate(('spade','club','spade','heart','diamond')):
        start=len(geo.PARTS);z=.205+i*.008
        box('PaperCard',(0,0,z),(.42,.67,.004),'Paper',.001)
        if i==0:pip(kind,0,0,z+.0022,.10)
        else:
            for x in (-.102,.102):
                for y in (-.21,.21):pip(kind,x,y,z+.0022,.052)
        # Card fan rotation applies to both stock and its physically coplanar ink.
        angle=math.radians((i-2)*18);cx=(i-2)*.26;cy=-.10+abs(i-2)*.065
        from mathutils import Matrix
        transform=Matrix.Translation((cx,cy,0)) @ Matrix.Rotation(angle,4,'Z')
        for obj in geo.PARTS[start:]:obj.matrix_world=transform@obj.matrix_world


def main():
    evidence=json.loads(EVIDENCE.read_text());assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for entry,author in zip(evidence['assets'],(quarantine,poker)):
        assert entry['sources'] and entry['render_brief']
        bpy.ops.wm.read_factory_settings(use_empty=True);geo.PARTS.clear();geo.MATS.clear()
        for name,rgb in COLOURS.items():
            mat=bpy.data.materials.new('M_Trouble_'+name);mat.use_nodes=True
            shader=mat.node_tree.nodes['Principled BSDF'];shader.inputs['Base Color'].default_value=(*rgb,1)
            shader.inputs['Roughness'].default_value=.76;geo.MATS[name]=mat
        author();bpy.ops.object.select_all(action='DESELECT')
        for part in geo.PARTS:part.select_set(True)
        bpy.context.view_layer.objects.active=geo.PARTS[0];bpy.ops.object.join();obj=bpy.context.object
        obj.name=entry['name'];bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');obj.data.calc_loop_triangles()
        fbx=OUT/(obj.name+'.fbx');project=OUT/(obj.name+'.blend')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
        bpy.ops.wm.save_as_mainfile(filepath=str(project))
        records.append(dict(name=obj.name,card_id=entry['card_id'],fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
            project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),materials=[m.name for m in obj.data.materials]))
        geo.render(obj,OUT/(entry['card_id']+'.png'),focus=(0,0,1.0 if entry['card_id']=='cholera' else .2),ortho_scale=2.9 if entry['card_id']=='cholera' else 2.5)
    (OUT/'manifest.json').write_text(json.dumps(dict(evidence_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),assets=records,
        material_linear_rgb={'M_Trouble_'+n:c for n,c in COLOURS.items()},visual_review='pending'),indent=2)+'\n')
    print('TROUBLE_OBJECTS_AUTHORED',[(r['card_id'],r['triangles']) for r in records],flush=True)


if __name__=='__main__':main()
