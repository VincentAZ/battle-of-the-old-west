"""Author a documented, static Rio Grande landing reconstruction in Mixar."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing'
OUT = BASE/'local-source-v002'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads((BASE/'local-brief-v002.json').read_text())
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
assert sha(BASE/'reference-review-v001.json') == brief['reference_review_sha256']
for path, digest in json.loads((BASE/'reference-review-v001.json').read_text())['references'].items():
    assert sha(ROOT/path) == digest, path
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1879)
rng = np.random.default_rng(1879)
atlas = Image.new('RGB', (2048,2048))
draw = ImageDraw.Draw(atlas)
colours = [(137,83,40),(178,119,61),(190,141,84),(153,107,58),
           (49,45,36),(171,130,78),(123,72,35),(178,126,72)]
for tile, colour in enumerate(colours):
    x0,y0=(tile%4)*512,(tile//4)*1024
    draw.rectangle((x0,y0,x0+511,y0+1023),fill=colour)
    for x in range(x0+2,x0+510,3):
        tone=random.randint(-15,15);c=tuple(max(0,min(255,a+tone))for a in colour)
        if tile==4:
            draw.line((x,y0,x,y0+1023),fill=c,width=1)
        else:
            points=[(x+3*math.sin(y*.021+x*.032)+2*math.sin(y*.005+x),y)
                    for y in range(y0+2,y0+1022,8)]
            draw.line(points,fill=c,width=1)
    if tile not in (4,5):
        for _ in range(12):
            x=random.randint(x0+15,x0+490);y=random.randint(y0+20,y0+980)
            draw.line([(x,y),(x+1,min(y0+1010,y+random.randint(10,100)))],
                      fill=tuple(int(a*.67)for a in colour),width=1)
    if tile==5:
        for y in range(y0, y0+1024,10):
            draw.line((x0,y,x0+511,y+180),fill=(116,84,48),width=2)
pixels=np.asarray(atlas).astype(np.int16)+rng.integers(-3,4,(2048,2048,1),dtype=np.int16)
texture=OUT/'SmugglersLanding_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
mat=bpy.data.materials.new('M_SmugglersLanding_Atlas');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.77
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]


def solid(name, vertices, faces, tile, bevel=0):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    mesh.materials.append(mat);uv=mesh.uv_layers.new()
    for poly in mesh.polygons:
        pts=[mesh.vertices[i].co for i in poly.vertices]
        lo=[min(v[k]for v in pts)for k in range(3)];hi=[max(v[k]for v in pts)for k in range(3)]
        axes=sorted(range(3),key=lambda k:hi[k]-lo[k],reverse=True)[:2]
        for loop in poly.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co
            along=(v[axes[0]]-lo[axes[0]])/max(.00001,hi[axes[0]]-lo[axes[0]])
            across=(v[axes[1]]-lo[axes[1]])/max(.00001,hi[axes[1]]-lo[axes[1]])
            uv.data[loop].uv=((tile%4*512+8+across*496)/2048,
                              1-(tile//4*1024+8+(1-along)*1008)/2048)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    if bevel:
        bpy.context.view_layer.objects.active=ob;ob.select_set(True)
        mod=ob.modifiers.new('Subtle timber edge','BEVEL');mod.width=bevel;mod.segments=1
        bpy.ops.object.modifier_apply(modifier=mod.name);ob.select_set(False)
    objects.append(ob)
    return ob


def box(name, centre, size, tile=1):
    c=Vector(centre);h=Vector(size)*.5
    vertices=[tuple(c+Vector((a*h.x,b*h.y,d*h.z)))for a,b,d in
              [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    return solid(name,vertices,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],tile,
                 min(.004,min(size)*.075))


def slab(name, quad, offset, tile=0):
    v=[Vector(p)for p in quad];off=Vector(offset)
    return solid(name,[tuple(p)for p in v]+[tuple(p+off)for p in v],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],tile)


def tube(name, points, radius, tile=5, sides=8):
    pts=[Vector(p)for p in points];verts=[]
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        u=tangent.cross(Vector((0,0,1)) if abs(tangent.z)<.9 else Vector((0,1,0))).normalized()
        v=tangent.cross(u).normalized()
        for j in range(sides):
            a=j*math.tau/sides;verts.append(tuple(p+radius*(u*math.cos(a)+v*math.sin(a))))
    faces=[tuple(range(sides-1,-1,-1)),tuple((len(pts)-1)*sides+j for j in range(sides))]
    for i in range(len(pts)-1):
        for j in range(sides):
            k=(j+1)%sides;faces.append((i*sides+j,i*sides+k,(i+1)*sides+k,(i+1)*sides+j))
    return solid(name,verts,faces,tile)


CY=-.65
# A shallow square-ended hull; exact dimensions and interior framing are reconstructed.
for j in range(10):
    box('Punt bottom plank', (0,CY-.65+(j+.5)*.13,.045),(4.30,.129,.09),j%2)
for sign in (-1,1):
    for j in range(4):
        low=.085+j*.138;high=low+.138
        def corner(z,xsign):return (xsign*(2.15+.25*z/.637),CY+sign*(.65+.20*z/.637),z)
        slab('Longitudinal hull side plank',[corner(low,-1),corner(low,1),corner(high,1),corner(high,-1)],(0,-sign*.036,0),j%2)
    # Sloping square transom closes the end; separate planks follow the rake.
    for j in range(4):
        low=.085+j*.138;high=low+.138
        def corner(z,ysign):return (sign*(2.15+.25*z/.637),CY+ysign*(.65+.20*z/.637),z)
        slab('Raked square transom plank',[corner(low,-1),corner(low,1),corner(high,1),corner(high,-1)],(-sign*.042,0,0),0)
    # Raked bottom extension up to end board: flat midbody, very modest rising ends.
    slab('Punt end bottom closure',[(sign*2.14,CY-.65,.09),(sign*2.19,CY-.69,.10),
        (sign*2.19,CY+.69,.10),(sign*2.14,CY+.65,.09)],(0,0,-.07),0)
    box('Wooden gunwale cap',(0,CY+sign*.834,.648),(4.79,.074,.045),3)
for i,x in enumerate([-1.80,-1.05,-.30,.45,1.20,1.95]):
    box('Transverse bottom frame',(x,CY,.122),(.068,1.27,.062),3)
    for sign in (-1,1):
        a=Vector((x,CY+sign*.65,.14));b=Vector((x,CY+sign*.795,.59))
        tube('Interior side frame',[a,b],.032,tile=3,sides=4)
# Removable longitudinal flooring bears on the transverse frames.
for j in range(9):
    box('Interior removable floorboard',(0,CY-.57+(j+.5)*.126,.142),(4.15,.124,.030),1+j%2)
# Three closed freight cases with sawn boards and restrained iron corner straps.
def crate(x,y,z,dx,dy,dz):
    for face in (-1,1):
        for j in range(3):
            box('Freight case side board',(x,y+face*(dy/2-.013),z+(j+.5)*dz/3),(dx,.026,dz/3-.002),2)
        for j in range(3):
            box('Freight case end board',(x+face*(dx/2-.013),y,z+(j+.5)*dz/3),(.026,dy-.052,dz/3-.002),2)
    for j in range(4):
        for h in (.013,dz-.013):box('Freight case lid or bottom',(x,y-dy/2+(j+.5)*dy/4,z+h),(dx-.052,dy/4-.002,.026),2)
    for a in (-1,1):
        for b in (-1,1):
            box('Case iron corner strap',(x+a*(dx/2+.001),y+b*(dy/2-.033),z+dz/2),(.006,.065,dz-.035),4)
            box('Case iron corner strap return',(x+a*(dx/2-.032),y+b*(dy/2+.001),z+dz/2),(.063,.006,dz-.035),4)
crate(-1.35,CY-.04,.157,.63,.51,.45)
crate(-.67,CY-.15,.157,.55,.45,.38)
crate(-1.28,CY-.04,.607,.47,.37,.32)
# A small step provides a plausible descent from the boarding rim into the punt.
for x in (.34,.97):
    for y in (CY+.22,CY+.58):box('Boarding step leg',(x,y,.21),(.055,.055,.22),3)
for j in range(3):box('Boarding step tread',(.65,CY+.22+(j+.5)*.12,.335),(.76,.116,.046),1)
# Narrow landing ramp slopes down to an earthen bank supplied by the separate base.
for j in range(6):
    x=.12+j*.18
    slab('Landing ramp plank',[(x-.086,.15,.676),(x+.086,.15,.676),(x+.086,2.70,.12),(x-.086,2.70,.12)],(0,0,-.045),1+j%2)
for x in (.10,.97):
    slab('Ramp underside stringer',[(x-.037,.16,.625),(x+.037,.16,.625),(x+.037,2.65,.080),(x-.037,2.65,.080)],(0,0,-.065),3)
# Post and rope sit beside the approach, with no cable-ferry mechanism implied.
box('Plain timber mooring post',(1.48,2.38,.64),(.17,.17,1.28),0)
points=[]
for i in range(33):
    t=i/32;a=Vector((2.20,CY+.73,.58));b=Vector((1.48,2.29,1.08));q=a.lerp(b,t);q.z-=.22*math.sin(math.pi*t);points.append(tuple(q))
tube('Mooring line',points,.014)
points=[]
for i in range(161):
    a=i/160*math.tau*4;points.append((1.48+.11*math.cos(a),2.38+.11*math.sin(a),1.04+i/160*.12))
tube('Post rope turns',points,.014)

# Audit the actual source components before exporting an unrigged static GLB.
audit=[];triangles=0
for ob in objects:
    bm=bmesh.new();bm.from_mesh(ob.data);nm=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);area=min(f.calc_area()for f in bm.faces);bm.free()
    assert nm==0 and volume>1e-10 and area>1e-12,(ob.name,nm,volume,area)
    ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
    audit.append(dict(name=ob.name,nonmanifold_edges=nm,volume=volume,minimum_face_area=area))
assert triangles<=30000
bpy.ops.object.select_all(action='DESELECT')
for ob in objects:ob.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'SmugglersLanding.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'SmugglersLanding.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BASE/'local-brief-v002.json'),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('SMUGGLERS_LANDING_AUTHORED',triangles,flush=True)
