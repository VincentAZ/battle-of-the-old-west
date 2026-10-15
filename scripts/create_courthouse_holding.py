"""Static game-scale interpretation of the 1882 Tombstone courthouse.

Run in Mixar; the pinned brief and inspected HABS scans precede authoring.
"""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/courthouse'
OUT = BASE/'local-source-v004'
BRIEF = BASE/'local-authoring-brief-v005.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
for path, digest in brief['source_records'].items():
    assert sha(BASE/path) == digest, path
assert not OUT.exists(), 'Preserve earlier authoring sources'
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1882)
rng = np.random.default_rng(1882)

# One atlas: five stretcher courses followed by an all-header course.
# World-space projection keeps the bond continuous across opening pieces.
atlas = Image.new('RGB', (2048, 2048), (149, 132, 113))
draw = ImageDraw.Draw(atlas)
px = 1536/8
course = .038*px
row = 0
while row*course < 1536:
    y0,y1 = round(row*course),round((row+1)*course)
    width = (.057 if row%6 == 5 else .116)*px
    x = -width/2 if row%2 else 0
    while x < 1536:
        tone = random.randint(-19,18)
        draw.rectangle((round(x+.7),y0+1,round(x+width-.7),y1-1),
                       fill=(180+tone,65+tone//2,40+tone//3))
        x += width
    row += 1
regions = {'stone':(1544,8,2038,490), 'roof':(1544,510,2038,1010),
           'iron':(1544,1030,1775,1280), 'glass':(1795,1030,2038,1280),
           'wood':(1544,1300,2038,1528), 'door':(8,1550,1020,2038),
           'foundation':(1040,1550,2038,2038)}
colours = {'stone':(236,231,215), 'roof':(59,64,68), 'iron':(35,34,30),
           'glass':(33,48,57), 'wood':(223,218,198), 'door':(108,65,32),
           'foundation':(181,170,147)}
for key, rect in regions.items():
    draw.rectangle(rect,fill=colours[key])
for x in range(15,1014,3):
    tone = random.randint(-14,14)
    draw.line((x,1558,x+random.randint(-2,2),2030),fill=(108+tone,65+tone//2,32+tone//3))
pixels = np.asarray(atlas).astype(np.int16)
pixels += rng.integers(-4,5,(2048,2048,1),dtype=np.int16)
texture = OUT/'Courthouse_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_Courthouse_Atlas')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .82
node = material.node_tree.nodes.new('ShaderNodeTexImage')
node.image = bpy.data.images.load(str(texture)); node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects = []


def finish(o, region):
    o.data.materials.append(material)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(o.data); bm.free(); o.data.update()
    uv = o.data.uv_layers.active or o.data.uv_layers.new()
    for face in o.data.polygons:
        axis = max(range(3),key=lambda k:abs(face.normal[k]))
        a,b = [k for k in range(3) if k != axis]
        coords = [o.data.vertices[o.data.loops[i].vertex_index].co for i in face.loop_indices]
        lows = [min(p[k] for p in coords) for k in range(3)]
        highs = [max(p[k] for p in coords) for k in range(3)]
        for loop in face.loop_indices:
            v = o.data.vertices[o.data.loops[loop].vertex_index].co
            if region == 'brick':
                world = o.matrix_world @ v
                h = 1 if axis == 0 else 0
                u = (world[h]+4)/8
                vv = world.z/8 if axis != 2 else (world.y+4)/8
                uv.data[loop].uv = (u*.75,1-vv*.75)
            else:
                x0,y0,x1,y1 = regions[region]
                u = (v[a]-lows[a])/max(highs[a]-lows[a],.00001)
                vv = (v[b]-lows[b])/max(highs[b]-lows[b],.00001)
                uv.data[loop].uv = ((x0+6+u*(x1-x0-12))/2048,
                                    1-(y1-6-vv*(y1-y0-12))/2048)
    objects.append(o)
    return o


def box(name, location, dimensions, region='brick', rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    o = bpy.context.object; o.name = name; o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if rotation:
        o.rotation_euler = rotation
    bpy.context.view_layer.update()
    return finish(o,region)


def solid(name, vertices, faces, region):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces); mesh.update()
    o = bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o)
    return finish(o,region)


def prism(name, polygon, axis, position, thickness, region):
    # Closed extrusion of a 2D polygon in the two other coordinate axes.
    axes = [k for k in range(3) if k != axis]
    vertices = []
    for side in (-1,1):
        for a,b in polygon:
            p = [0,0,0]; p[axis] = position+side*thickness/2
            p[axes[0]],p[axes[1]] = a,b; vertices.append(p)
    n = len(polygon)
    faces = [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return solid(name,vertices,faces,region)


def wall(name, axis, position, low, high, openings, zlow=.12, zhigh=2.38):
    rectangles = [(low,high,zlow,zhigh)]
    for left,right,bottom,top in openings:
        next_rect = []
        for a,b,c,d in rectangles:
            lo,hi = max(a,left),min(b,right); z0,z1 = max(c,bottom),min(d,top)
            if lo >= hi or z0 >= z1:
                next_rect.append((a,b,c,d)); continue
            next_rect.extend([(a,b,c,z0),(a,b,z1,d),(a,lo,z0,z1),(hi,b,z0,z1)])
        rectangles = [r for r in next_rect if r[1]-r[0]>.001 and r[3]-r[2]>.001]
    for a,b,c,d in rectangles:
        if axis == 0: box(name,(position,(a+b)/2,(c+d)/2),(.10,b-a,d-c))
        else: box(name,((a+b)/2,position,(c+d)/2),(b-a,.10,d-c))


def facade_box(name, axis, plane, along, z, width, depth, height, region):
    if axis == 0: return box(name,(plane,along,z),(depth,width,height),region)
    return box(name,(along,plane,z),(width,depth,height),region)


def window(axis, plane, sign, along, bottom, width=.40, height=.76):
    # Eight lights: two across and four tall, as in the inspected window scan.
    centre = bottom+height/2
    def part(name,u,z,w,d,h,region='wood',out=.025):
        return facade_box(name,axis,plane+sign*out,along+u,z,w,d,h,region)
    part('Recessed eight-light glazing',0,centre,width,.014,height,'glass',-.006)
    for side in (-1,1):
        part('Window heavy jamb',side*(width/2+.025),centre,.05,.065,height+.10)
        part('Window head or sill',0,centre+side*(height/2+.025),width,.08,.05)
    part('Window central muntin',0,centre,.017,.028,height,out=.012)
    for k in range(1,4):
        part('Double-hung sash rail',0,bottom+k*height/4,width,.03,.028 if k==2 else .016,out=.015)
    part('Window bracketed cornice',0,bottom+height+.098,width+.18,.12,.045,'stone',.055)
    part('Window cornice upper lip',0,bottom+height+.128,width+.21,.135,.018,'stone',.063)
    for side in (-1,1):
        part('Window cornice bracket',side*(width/2+.045),bottom+height+.047,.045,.11,.084,'stone',.052)


# Nomination proportions: central 40/88, transverse span about 76/88.
A,B,C,Y = 1.364,2.59,1.023,.22
front,rear = -3.,3.
z_eave,rise = 2.38,.40
for loc,dim in [((0,0,.06),(2*A,6,.12)),
                (((A+B)/2,Y,.06),(B-A,2*C,.12)),
                ((-(A+B)/2,Y,.06),(B-A,2*C,.12))]:
    box('Continuous cruciform foundation',loc,dim,'foundation')

# Front and rear ends. The upper centre front bay is a tall sash above porch.
for side,plane in [(-1,front),(1,rear)]:
    openings = []
    for bottom in (.38,1.49):
        for x in (-.86,0,.86):
            if side == -1 and bottom == .38 and x == 0: continue
            openings.append((x-.20,x+.20,bottom,bottom+.76))
    if side == -1: openings.append((-.29,.29,.12,1.12))
    wall('Front brick facade' if side==-1 else 'Reconstructed rear brick facade',1,plane,-A,A,openings)
    for bottom in (.38,1.49):
        for x in (-.86,0,.86):
            if side==-1 and bottom==.38 and x==0: continue
            window(1,plane+side*.05,side,x,bottom)

# Segmented long walls expose the cross plan; no internal faces cross openings.
for side in (-1,1):
    for lo,hi in [(front+.05,Y-C),(Y+C,rear-.05)]:
        centres = [lo+(hi-lo)*t for t in (.27,.73)]
        openings = [(u-.20,u+.20,z,z+.76) for u in centres for z in (.38,1.49)]
        wall('Central shaft side masonry',0,side*A,lo,hi,openings)
        for u in centres:
            for z in (.38,1.49): window(0,side*(A+.05),side,u,z)
    centres = [Y-.64,Y,Y+.64]
    openings = [(u-.20,u+.20,z,z+.76) for u in centres for z in (.38,1.49)]
    wall('Wing gable end masonry',0,side*B,Y-C,Y+C,openings)
    for u in centres:
        for z in (.38,1.49): window(0,side*(B+.05),side,u,z)
    for end in (-1,1):
        lo,hi = (A+.05,B-.05) if side==1 else (-B+.05,-A-.05)
        u = (lo+hi)/2
        openings = [(u-.20,u+.20,z,z+.76) for z in (.38,1.49)]
        wall('Wing return masonry',1,Y+end*C,lo,hi,openings)
        for z in (.38,1.49): window(1,Y+end*(C+.05),end,u,z)

# Exterior stone belt, eaves and alternating corner quoins. The cross outline
# avoids hidden intersecting trim surfaces around the inner re-entrant corners.
outline = [(-A,front),(A,front),(A,Y-C),(B,Y-C),(B,Y+C),(A,Y+C),
           (A,rear),(-A,rear),(-A,Y+C),(-B,Y+C),(-B,Y-C),(-A,Y-C)]
for k,(x,y) in enumerate(outline):
    nx,ny = outline[(k+1)%len(outline)]
    for z,h,depth,region in [(1.31,.066,.12,'stone'),(2.36,.075,.15,'wood'),(2.43,.055,.22,'wood')]:
        box('Perimeter belt or cornice',((x+nx)/2,(y+ny)/2,z),
            (abs(nx-x)-depth if nx!=x else depth,
             abs(ny-y)-depth if ny!=y else depth,h),region)
        box('Cornice butt-joint corner',(x,y,z),(depth,depth,h),region)
    length = math.hypot(nx-x,ny-y)
    for j in range(max(1,round(length/.23))):
        t = (j+.5)/max(1,round(length/.23))
        box('Eave bracket',(x+(nx-x)*t,y+(ny-y)*t,2.34),(.048,.11,.10) if nx!=x else (.11,.048,.10),'wood')
    # Dress only outer convex corners, not inside junctions.
    px,py = outline[k-1]
    convex = (x-px)*(ny-y)-(y-py)*(nx-x) > 0
    if convex:
        for row in range(18):
            w,d = (.21,.13) if row%2 else (.13,.21)
            box('Alternating white stone corner quoin',(x,y,.15+(row+.5)*2.16/18),(w,d,2.16/18-.008),'stone')

# Brick gable faces and white pediments at all four cross ends.
for axis,plane,half,centre,sign in [(1,front,A,0,-1),(1,rear,A,0,1),
                                  (0,-B,C,Y,-1),(0,B,C,Y,1)]:
    prism('Brick pediment',[(centre-half,2.43),(centre+half,2.43),(centre,2.43+rise)],axis,plane,.105,'brick')
    angle = math.atan2(rise,half); slope = math.hypot(rise,half)
    for side in (-1,1):
        if axis == 1:
            box('White gable rake',(centre+side*half/2,plane+sign*.055,2.43+rise/2),
                (slope+.06,.16,.065),'wood',(0,side*angle,0))
        else:
            box('White gable rake',(plane+sign*.055,centre+side*half/2,2.43+rise/2),
                (.16,slope+.06,.065),'wood',(-side*angle,0,0))


def clip(poly, fn):
    result=[]
    for i,p in enumerate(poly):
        q=poly[(i+1)%len(poly)]; a,b=fn(p),fn(q)
        if a>=-1e-8: result.append(p)
        if (a<0) != (b<0):
            t=a/(a-b); result.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    clean=[]
    for p in result:
        if not clean or math.dist(p,clean[-1])>1e-7: clean.append(p)
    if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-7: clean.pop()
    return clean


def roof_patch(poly, height, sx,sy):
    if len(poly)<3: return
    points=[(sx*x,Y+sy*y,height(x,y)) for x,y in poly]
    n=len(points); vertices=points+[(x,y,z-.038) for x,y,z in points]
    faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
    faces += [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
    solid('Closed intersecting gable roof',vertices,faces,'roof')


# Intersect the two roof planes along their valleys; no coplanar overlay roofs.
a,b,c=A+.12,B+.12,C+.12
for sx in (-1,1):
    for sy in (-1,1):
        end=(rear-Y+.12) if sy==1 else (Y-front+.12)
        hm=lambda x,y:2.43+rise*(1-x/a)
        hw=lambda x,y:2.43+rise*(1-y/c)
        overlap=[(0,0),(a,0),(a,c),(0,c)]
        roof_patch(clip(overlap,lambda p:hm(*p)-hw(*p)),hm,sx,sy)
        roof_patch(clip(overlap,lambda p:hw(*p)-hm(*p)),hw,sx,sy)
        roof_patch([(0,c),(a,c),(a,end),(0,end)],hm,sx,sy)
        roof_patch([(a,0),(b,0),(b,c),(a,c)],hw,sx,sy)
box('Main roof ridge cover',(0,0,2.848),(.065,6.22,.04),'roof')
box('Cross roof ridge cover',(0,Y,2.848),(5.41,.065,.04),'roof')

# Entrance: actual opening, recessed double leaves, four-square-pillar porch.
for side in (-1,1):
    box('Entrance double door leaf',(side*.145,front-.025,.535),(.286,.042,.83),'door')
    for z in (.31,.70):
        box('Door recessed panel',(side*.145,front-.05,z),(.215,.014,.285),'door')
    box('Door brass-colour-free iron handle',(side*.045,front-.068,.59),(.015,.02,.07),'iron')
box('Entrance transom glazing',(0,front-.024,1.04),(.58,.018,.15),'glass')
for x in (-.29,0,.29):box('Transom vertical frame',(x,front-.048,1.04),(.024,.035,.19),'wood')
for z in (.947,1.137):box('Transom horizontal frame',(0,front-.05,z),(.63,.05,.027),'wood')
prism('Closed three-step entrance stair',
      [(front-.66,0),(front-.66,.05),(front-.525,.05),(front-.525,.10),
       (front-.39,.10),(front-.39,.15),(front-.11,.15),(front-.11,0)],
      0,0,1.12,'foundation')
for x in (-.48,.48):
    for y in (front-.40,front-.05):
        box('Square porch pillar',(x,y,.67),(.085,.095,1.16),'stone')
        for z in (.15,1.22):box('Porch pillar base or capital',(x,y,z),(.14,.145,.10),'stone')
box('Porch entablature',(0,front-.235,1.27),(1.16,.63,.12),'stone')
box('Porch balcony cornice',(0,front-.235,1.345),(1.22,.67,.045),'stone')
for j in range(9):
    x=-.5+j*.125
    box('Balcony turned baluster lower',(x,front-.515,1.455),(.035,.038,.18),'stone')
    box('Balcony baluster swelling',(x,front-.515,1.45),(.053,.054,.065),'stone')
box('Balcony front handrail',(0,front-.515,1.565),(1.15,.065,.045),'stone')
for side in (-1,1):
    box('Balcony corner pier',(side*.55,front-.515,1.465),(.085,.085,.24),'stone')
    box('Balcony pier cap',(side*.55,front-.515,1.59),(.12,.12,.04),'stone')
    box('Balcony return handrail',(side*.55,front-.255,1.565),(.065,.51,.045),'stone')
    for y in (front-.36,front-.18):box('Balcony return baluster',(side*.55,y,1.455),(.045,.04,.18),'stone')

# Small square cupola: four arched openings, cornice and truncated mansard.
tower=.48
box('Cupola plinth',(0,Y,2.755),(1.12,1.12,.22),'wood')
for axis in (0,1):
    for side in (-1,1):
        plane=side*tower+(Y if axis==1 else 0)
        centre=0 if axis==1 else Y
        wall('Cupola brick wall',axis,plane,centre-tower,centre+tower,
             [(centre-.265,centre+.265,2.91,3.38)],zlow=2.82,zhigh=3.48)
        # Fill the rectangular opening's upper corners above the arched glass.
        r=.265; spring=3.18
        arch=[(centre-r,2.91),(centre+r,2.91),(centre+r,spring)]
        arch += [(centre+r*math.cos(k*math.pi/12),spring+.20*math.sin(k*math.pi/12)) for k in range(1,13)]
        prism('Cupola arched recessed glazing',arch,axis,plane+side*.012,.016,'glass')
        for half in (-1,1):
            curve=[(centre+half*r*math.cos(k*math.pi/12),spring+.20*math.sin(k*math.pi/12)) for k in range(7)]
            poly=curve+[(centre+half*r,3.38)]
            prism('Cupola arch spandrel',poly,axis,plane,.10,'brick')
        for edge in (-1,1):
            facade_box('Cupola window jamb',axis,plane+side*.06,centre+edge*.285,3.045,.04,.06,.30,'wood')
        for k in range(12):
            t0,t1=k*math.pi/12,(k+1)*math.pi/12
            poly=[(centre+rr*math.cos(t),spring+hh*math.sin(t))
                  for rr,hh,t in [(r,.20,t0),(r,.20,t1),(r+.045,.245,t1),(r+.045,.245,t0)]]
            prism('Cupola curved arch trim',poly,axis,plane+side*.064,.035,'wood')
        facade_box('Cupola sash centre',axis,plane+side*.04,centre,3.13,.02,.026,.42,'wood')
        for z in (3.025,3.18):facade_box('Cupola sash rail',axis,plane+side*.042,centre,z,.53,.03,.019,'wood')
        facade_box('Cupola lower sash sill',axis,plane+side*.062,centre,2.91,.59,.065,.045,'wood')
for x in (-tower,tower):
    for y in (Y-tower,Y+tower):box('Cupola corner pilaster',(x,y,3.14),(.13,.13,.64),'wood')
for z,w,h in [(3.47,1.10,.07),(3.52,1.22,.045)]:box('Cupola overhanging cornice',(0,Y,z),(w,w,h),'wood')
verts=[(x*w,Y+y*w,z) for z,w in [(3.545,.57),(4.10,.255)] for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
solid('Truncated mansard cupola roof',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'roof')
box('Cupola roof upper cap',(0,Y,4.105),(.56,.56,.035),'roof')
# Small iron crest, never a clock or a large dome. Sparse points follow HABS.
for side in (-1,1):
    for axis in (0,1):
        pos=side*.26+(Y if axis==1 else 0)
        for z in (4.14,4.22):facade_box('Cupola crest rail',axis,pos,Y if axis==0 else 0,z,.54,.013,.014,'iron')
        for n in range(5):
            u=-.25+n*.125+(Y if axis==0 else 0)
            facade_box('Cupola crest picket',axis,pos,u,4.20,.013,.013,.19,'iron')
            p=(pos,u,4.303) if axis==0 else (u,pos,4.303)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.023,location=p)
            o=bpy.context.object;o.name='Small iron crest finial';finish(o,'iron')

# Two slim brick chimney reconstructions; exact original count is uncertain.
for side in (-1,1):
    box('Slender wing chimney',(side*2.12,Y,2.99),(.19,.21,.58))
    box('Chimney cornice',(side*2.12,Y,3.285),(.27,.28,.055),'stone')
    box('Chimney cap',(side*2.12,Y,3.34),(.23,.24,.065),'roof')
    box('Recessed flue',(side*2.12,Y,3.375),(.10,.11,.008),'iron')

bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'Courthouse.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'Courthouse.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
    export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),
    atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,
    rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('COURTHOUSE_AUTHORED',triangles,str(glb),flush=True)
