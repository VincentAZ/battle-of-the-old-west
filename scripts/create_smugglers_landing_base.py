"""Static sourced riverbank for the reviewed Smuggler's Landing reconstruction."""
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import holdings_base as base

P = ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing'
OUT = P/'base-v005'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
evidence = json.loads((P/'base-evidence-v005.json').read_text())
manifest = json.loads((P/'review-v001/manifest.json').read_text())
source = P/'review-v001'/manifest['project']
assert sha(source) == evidence['source_review_sha256']
assert json.loads((P/'review-v001/validation.json').read_text())['status'] == 'passed'
for item in evidence['sources']:
    if item.get('file'):
        assert sha(ROOT/item['file']) == item['sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
bpy.data.objects['Review_only_ground'].location.z = -.015
holding = bpy.data.objects[manifest['mesh_object']]
rng = random.Random(18791885)
outline = base.Outline(rng, 3., 2.638125, 1.20, .18)
material = base.vertex_colour_material('M_Holding_Base')


def shore(x):
    return -.67 + .14*math.sin(x*1.05)


def radial(x, y):
    return math.hypot(x, y)/outline.radius(math.atan2(y, x))


def ground_z(x, y):
    dry = max(.004, .15-max(0., y-shore(x))*.42)
    fade = min(1., max(0., (1-radial(x, y))/.16))
    fade = 1-(1-fade)*min(1.,max(0.,(shore(x)-y)/.65))
    return .002+(dry-.002)*fade


def water_z(x, y):
    return .105


def mesh(name, verts, faces, tints, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces); data.update()
    attr = data.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')
    for poly in data.polygons:
        for loop in poly.loop_indices:
            attr.data[loop].color_srgb = tints[poly.index]
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    data.materials.append(mat)
    return ob


verts = [(0, 0, ground_z(0, 0))]
faces = []
segments, rings = 128, 36
for ring in range(1, rings+1):
    for i in range(segments):
        a = i*math.tau/segments; r = outline.radius(a)*ring/rings
        x, y = r*math.cos(a), r*math.sin(a)
        verts.append((x, y, ground_z(x, y)))
for i in range(segments):
    faces.append((0, 1+i, 1+(i+1)%segments))
for ring in range(rings-1):
    a, b = 1+ring*segments, 1+(ring+1)*segments
    for i in range(segments):
        j = (i+1)%segments
        faces.extend(((a+i,b+i,b+j),(a+i,b+j,a+j)))
tints = []
for face in faces:
    x,y,_ = sum((Vector(verts[i]) for i in face), Vector())/3
    variation = .5+.5*math.sin(x*3.1)*math.cos(y*4.7)
    c = base.lerp((.43,.28,.13),(.66,.48,.27),variation)
    tints.append((*c, max(0., min(1., (1-radial(x,y))/.12))))
ground = mesh('Holding_Base_Ground', verts, faces, tints, material)
for poly in ground.data.polygons:
    poly.use_smooth = True
    for loop in poly.loop_indices:
        x,y,_ = ground.data.vertices[ground.data.loops[loop].vertex_index].co
        variation=.5+.5*math.sin(x*2.1)*math.cos(y*2.7)
        c=base.lerp((.48,.32,.16),(.63,.46,.25),variation)
        ground.data.color_attributes['Col'].data[loop].color_srgb=(*c,max(0.,min(1.,(1-radial(x,y))/.12)))

# Clip each ground triangle against the curved bank contour. The water meets
# the descending bank at the same height and never surrounds the dry post.
wv, wf, wc = [], [], []
def wet(p):
    return p[1]-shore(p[0])-(.15-.105)/.42
for f in faces:
    poly = [Vector(verts[i]) for i in f]; clipped = []
    for a,b in zip(poly,poly[1:]+poly[:1]):
        wa,wb=wet(a),wet(b)
        if wa >= 0: clipped.append(a)
        if (wa >= 0) != (wb >= 0):
            lo,hi=0.,1.
            for _ in range(24):
                t=(lo+hi)/2
                if (wet(a.lerp(b,t))>=0)==(wa>=0):lo=t
                else:hi=t
            clipped.append(a.lerp(b,(lo+hi)/2))
    if len(clipped)<3:continue
    start=len(wv)
    wv.extend((p.x,p.y,water_z(p.x,p.y)) for p in clipped)
    for j in range(1,len(clipped)-1):
        wf.append((start,start+j,start+j+1));wc.append((.44,.37,.23,1))
water = mesh('Holding_Base_Water',wv,wf,wc,base.water_material({'water':(.44,.37,.23)}))
water_bsdf=water.data.materials[0].node_tree.nodes['Principled BSDF']
water_bsdf.inputs['Roughness'].default_value=.30
water_bsdf.inputs['Coat Weight'].default_value=.12
for poly in water.data.polygons:poly.use_smooth=True
# The river is level. Its thin outer cut face describes the miniature crop,
# not a shoreline retaining wall or a slope in the river itself.
edge_vertices=[];edge_faces=[]
for i in range(segments):
    a=i*math.tau/segments;b=(i+1)*math.tau/segments
    p=Vector((outline.radius(a)*math.cos(a),outline.radius(a)*math.sin(a),.105))
    q=Vector((outline.radius(b)*math.cos(b),outline.radius(b)*math.sin(b),.105))
    if wet(p)<0 and wet(q)<0:continue
    if (wet(p)>=0)!=(wet(q)>=0):
        t=wet(p)/(wet(p)-wet(q));at=p.lerp(q,t)
        if wet(p)<0:p=at
        else:q=at
    start=len(edge_vertices)
    edge_vertices.extend([tuple(p),tuple(q),(q.x,q.y,.002),(p.x,p.y,.002)])
    edge_faces.append((start,start+1,start+2,start+3))
edge=mesh('Holding_Base_WaterCut',edge_vertices,edge_faces,[(.44,.37,.23,1)]*len(edge_faces),material)
gv,gf,gc=[],[],[]
for i in range(segments):
    p=Vector(verts[1+(rings-1)*segments+i])
    q=Vector(verts[1+(rings-1)*segments+(i+1)%segments])
    start=len(gv)
    gv.extend([tuple(p),tuple(q),(q.x,q.y,.001),(p.x,p.y,.001)])
    gf.append((start,start+1,start+2,start+3))
    gc.append((*base.BATTLEFIELD_SAND,1))
ground_edge=mesh('Holding_Base_EarthCut',gv,gf,gc,material)

# Narrow lanceolate leaf geometry with alternate attachment and paler backs.
pv,pf,pc=[],[],[]
roots=[]
def segment(a,b,r):
    a,b=Vector(a),Vector(b); axis=(b-a).normalized()
    u=axis.cross(Vector((0,1,0))).normalized();v=axis.cross(u)
    start=len(pv)
    for p,radius in ((a,r),(b,r*.62)):
        for j in range(6):pv.append(tuple(p+radius*(u*math.cos(j*math.tau/6)+v*math.sin(j*math.tau/6))))
    for j in range(6):
        pf.append((start+j,start+(j+1)%6,start+6+(j+1)%6,start+6+j));pc.append((.44,.27,.12,1))
    pf.extend((tuple(start+j for j in reversed(range(6))),tuple(start+6+j for j in range(6))))
    pc.extend([(.44,.27,.12,1)]*2)


def leaf(origin, azimuth, length):
    direction=Vector((math.cos(azimuth),math.sin(azimuth),rng.uniform(-.22,.58))).normalized()
    side=Vector((-math.sin(azimuth),math.cos(azimuth),0))*length/15
    start=len(pv); origin=Vector(origin)
    points=[origin,origin+direction*length*.42+side,origin+direction*length,origin+direction*length*.42-side,origin+direction*length*.46+Vector((0,0,.006))]
    pv.extend(tuple(p) for p in points)
    tint=base.lerp((.12,.40,.19),(.29,.57,.25),rng.random())
    for j in range(4):
        pf.append((start+j,start+(j+1)%4,start+4));pc.append((*tint,1))
    pf.append((start+3,start+2,start+1,start));pc.append((.49,.62,.43,1))


for cx,cy,height in [(-3.15,-.99,1.22),(2.75,-1.15,1.04)]:
    for stem in range(7):
        x,y=cx+rng.uniform(-.15,.15),cy+rng.uniform(-.10,.10)
        z=ground_z(x,y)-.012; roots.append((x,y,z))
        start=Vector((x,y,z));angle=rng.uniform(0,math.tau)
        end=start+Vector((.23*math.cos(angle),.23*math.sin(angle),height*rng.uniform(.75,1.1)))
        segment(start,end,.014)
        for branch in range(5):
            origin=start.lerp(end,.27+branch*.13)
            az=angle+branch*2.4;tip=origin+Vector((.27*math.cos(az),.27*math.sin(az),.20))
            segment(origin,tip,.0045)
            for k in range(9):
                at=origin.lerp(tip,.10+k*.10)
                leaf(at,az+((-1)**k)*1.04,rng.uniform(.09,.125))
willows=mesh('Holding_Base_Willow',pv,pf,pc,material)
objects=[ground,water,willows,edge,ground_edge]
scene=bpy.context.scene;scene.cycles.samples=24
bpy.context.view_layer.update()
points=[ob.matrix_world@v.co for ob in objects+[holding] for v in ob.data.vertices]
camera_frames={}
for name in ('three-quarter','game-camera','overhead'):
    camera=bpy.data.objects['Review_'+name]
    right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0))
    xs=[(p-camera.location).dot(right) for p in points];ys=[(p-camera.location).dot(up) for p in points]
    camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2)
    camera.data.ortho_scale=1.12*max(max(xs)-min(xs),(max(ys)-min(ys))*scene.render.resolution_x/scene.render.resolution_y)
    camera_frames[name]={'ortho_width_m':camera.data.ortho_scale}
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
triangles=0
for ob in objects:ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
record=dict(slug='smugglers-landing',setting='River',objects=[o.name for o in objects],base_triangles=triangles,water_surface=True,water_mode='custom_dry_bank',water_color_srgb=[.44,.37,.23],animated=False,camera_frames=camera_frames,evidence_sha256=sha(P/'base-evidence-v005.json'),source_review_project_sha256=sha(source),willow_roots=roots,scope='Static reconstructed shore; native terrain and condition lifecycle remain.')
(OUT/'base.json').write_text(json.dumps(record,indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'holdings-base-library.py').write_bytes(Path(base.__file__).read_bytes())
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'smugglers-landing-Base.blend'))
assert sha(source)==evidence['source_review_sha256']
print('SMUGGLERS_BASE_READY',triangles,flush=True)
