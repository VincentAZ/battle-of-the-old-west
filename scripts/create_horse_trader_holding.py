"""Author the documented fictional Horse Trader static barn and sale yard."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/horse-trader'
OUT = BASE/'local-source-v006'
BRIEF = BASE/'local-authoring-brief-v006.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
for p, digest in brief['source_records'].items():
    assert sha(ROOT/p) == digest, p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
rng = random.Random(1884)
atlas = Image.new('RGB', (2048,2048))
d = ImageDraw.Draw(atlas)
regions = {}
for i,(key,colour) in enumerate(brief['palette'].items()):
    x,y = i%4*512, i//4*512
    regions[key] = (x+8,y+8,x+504,y+504)
    d.rectangle(regions[key],fill=tuple(colour))
    if key in ('wood','roof','inside'):
        for offset in range(10,500,4):
            tint = rng.randint(-14,14)
            d.line((x+offset,y+10,x+offset+rng.randint(-2,2),y+500),
                   fill=tuple(max(0,min(255,v+tint)) for v in colour),width=1)
    if key == 'endgrain':
        for radius in range(12,245,11):
            d.ellipse((x+256-radius,y+256-radius,x+256+radius,y+256+radius),
                      outline=tuple(max(0,v-24) for v in colour),width=2)
    if key == 'stone':
        for j in range(1600):
            xx,yy=rng.randint(x+8,x+503),rng.randint(y+8,y+503)
            tint=rng.randint(-18,18)
            d.point((xx,yy),fill=tuple(max(0,min(255,v+tint)) for v in colour))
regions['lettering'] = (8,1100,2040,1490)
d.rectangle(regions['lettering'],fill=tuple(brief['palette']['sign']))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf',185)
d.text((1024,1295),'HORSE TRADER',font=font,fill=(51,34,18),anchor='mm')
d.rectangle((35,1134,2010,1456),outline=(82,46,19),width=8)
texture=OUT/'HorseTrader_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_HorseTrader_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.72
node=material.node_tree.nodes.new('ShaderNodeTexImage')
node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]

def uvmap(o,region,end_axis=None):
    mesh=o.data;mesh.update();uv=mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        normal=max(range(3),key=lambda k:abs(face.normal[k]))
        axes=[k for k in range(3) if k!=normal]
        coords=[mesh.vertices[i].co for i in face.vertices]
        lo=[min(p[k] for p in coords) for k in range(3)]
        hi=[max(p[k] for p in coords) for k in range(3)]
        tile='endgrain' if end_axis==normal else region
        if region=='lettering' and face.normal.y>-.5:tile='wood'
        x0,y0,x1,y1=regions[tile];a,b=axes
        if tile in ('wood','roof','inside'):
            b=max(axes,key=lambda k:hi[k]-lo[k]);a=next(k for k in axes if k!=b)
        for i in face.loop_indices:
            v=mesh.vertices[mesh.loops[i].vertex_index].co
            u=(v[a]-lo[a])/max(hi[a]-lo[a],1e-8)
            w=(v[b]-lo[b])/max(hi[b]-lo[b],1e-8)
            uv.data[i].uv=((x0+8+u*(x1-x0-16))/2048,1-(y1-8-w*(y1-y0-16))/2048)

def solid(name,vertices,faces,region,end_axis=None):
    m=bpy.data.meshes.new(name);m.from_pydata(vertices,[],faces);m.update()
    bm=bmesh.new();bm.from_mesh(m)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(m);bm.free()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o)
    m.materials.append(material);uvmap(o,region,end_axis);objects.append(o)
    return o

def box(name,loc,dim,region='wood'):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material);uvmap(o,region);objects.append(o)
    return o

def beam(name,a,b,width,depth=None,region='wood',round_log=False):
    a,b=Vector(a),Vector(b);length=(b-a).length;depth=depth or width
    if round_log:
        # Broad hewn flats with chamfered edges; square-joint appearance is a
        # disclosed simplification, not an engineering reconstruction.
        w,h=width/2,depth/2;c=min(w,h)*.28
        cross=[(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]
        verts=[(x,y,z) for z in (-length/2,length/2) for x,y in cross]
        o=solid(name,verts,[tuple(range(7,-1,-1)),tuple(range(8,16))]+
                [(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)],region,2)
    else:
        o=box(name,(0,0,0),(width,depth,length),region)
    o.location=(a+b)/2
    direction=(b-a).normalized()
    up=Vector((0,0,1)) if abs(direction.z)<.99 else Vector((0,1,0))
    u=up.cross(direction).normalized();v=direction.cross(u)
    o.rotation_euler=Matrix((u,v,direction)).transposed().to_euler()
    return o

def prism(name,poly,zfun,depth,region):
    n=len(poly)
    return solid(name,[(x,y,zfun(x,y)-depth) for x,y in poly]+[(x,y,zfun(x,y)) for x,y in poly],
                 [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+
                 [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],region)

# The barn is offset towards the back to make the enclosed sale yard readable.
x0,x1,y0,y1=-1.55,1.55,-.25,2.65
for yy in (y0,y1):
    for j in range(10):
        box('Stone foundation block',(x0+(j+.5)*(x1-x0)/10,yy,.08),((x1-x0)/10,.25,.16),'stone')
for xx in (x0,x1):
    for j in range(9):
        box('Stone foundation block',(xx,y0+(j+.5)*(y1-y0)/9,.08),(.25,(y1-y0)/9,.16),'stone')
box('Barn earth-colour floor',(0,(y0+y1)/2,.045),(3.10,2.90,.09),'stone')
for yy in (y0,y1):beam('Log foundation sill',(x0-.11,yy,.23),(x1+.11,yy,.23),.25,.17,round_log=True)
for xx in (x0,x1):beam('Log foundation sill',(xx,y0-.11,.23),(xx,y1+.11,.23),.25,.17,round_log=True)

# Individual log courses with real doorway void, and pale recessed lime joints.
for row in range(15):
    z=.38+row*.16-(.02 if row==14 else 0)
    log_depth=.10 if row==14 else .15
    for yy in (y0,y1):
        spans=[(x0-.17,x1+.17)]
        if yy==y0 and row<13:spans=[(x0-.17,-.62),(.62,x1+.17)]
        for l,r in spans:
            beam('Hewn horizontal wall log',(l,yy,z),(r,yy,z),.22,log_depth,round_log=True)
            if row<14:box('Recessed pale lime joint',((l+r)/2,yy,z+.08),(r-l-.05,.17,.055),'chink')
    for xx in (x0,x1):
        beam('Hewn side wall log',(xx,y0-.17,z+.018),(xx,y1+.17,z+.018),.22,log_depth,round_log=True)
        if row<14:box('Recessed pale lime joint',(xx,(y0+y1)/2,z+.095),(.17,y1-y0+.22,.055),'chink')

for x in (-.66,.66):box('Horse door jamb',(x,y0-.055,1.3225),(.115,.24,2.085))
box('Horse door header',(0,y0-.055,2.44),(1.45,.24,.15))
for j in range(8):
    box('Closed vertical plank horse door',(-.60+(j+.5)*1.20/8,y0+.012,1.34),(.147,.09,2.04))
for z in (.57,2.10):box('Door timber cross batten',(0,y0-.050,z),(1.20,.06,.10))
beam('Door diagonal brace',(-.54,y0-.048,.63),(.54,y0-.048,2.04),.085,.06)
for z in (.57,2.10):box('Simple iron strap hinge',(-.33,y0-.090,z),(.68,.035,.045),'iron')
box('Iron door latch',(.47,y0-.044,1.32),(.15,.025,.035),'iron')

eave,ridge=2.76,3.73
for yy in (y0,y1):
    for j in range(23):
        l=x0+j*(x1-x0)/23;r=x0+(j+1)*(x1-x0)/23
        top=lambda x:eave+(1-abs(x)/1.55)*(ridge-eave)
        # Board outline follows the gable slope and is extruded as a closed solid.
        profile=[(l,2.63),(r,2.63),(r,top(r)),(l,top(l))]
        vertices=[(x,y,z) for y in (yy-.045,yy+.045) for x,z in profile]
        solid('Vertical gable plank',vertices,[(0,1,2,3),(7,6,5,4)]+
              [(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)],'wood')
for yy in (y0-.08,y1+.08):
    for j in range(6):box('Closed loft hatch plank',(-.33+(j+.5)*.11,yy,3.06),(.108,.075,.55))
    for xx in (-.36,.36):box('Loft hatch stile',(xx,yy,3.06),(.075,.10,.67))
    for z in (2.75,3.37):box('Loft hatch head or sill',(0,yy,z),(.79,.11,.08))
    for z in (2.9,3.21):box('Loft hatch batten',(0,yy+(-.055 if yy<0 else .055),z),(.63,.045,.07))

# Substantial roof boards touch the gables and eave plates. Shingle courses
# overlap with a small rise per course, avoiding coplanar overlapping surfaces.
for xx in (x0,x1):box('Eave timber plate',(xx,(y0+y1)/2,2.595),(.21,3.15,.14))
roof_half=1.78;roof_y0=y0-.22;roof_y1=y1+.22
roofz=lambda x:ridge-abs(x)*(ridge-eave)/1.55
for side in (-1,1):
    a,b=sorted((0,side*roof_half))
    prism('Closed roof boarding',[(a,roof_y0),(b,roof_y0),(b,roof_y1),(a,roof_y1)],lambda x,y:roofz(x),.065,'inside')
    for row in range(9):
        far=roof_half-row*roof_half/9;near=max(0,far-roof_half/9-.028)
        l,r=sorted((side*near,side*far))
        for col in range(16):
            p=roof_y0+col*(roof_y1-roof_y0)/16
            q=p+(roof_y1-roof_y0)/16-.002
            prism('Individual cedar shingle',[(l,p),(r,p),(r,q),(l,q)],
                  lambda x,y,row=row:roofz(x)+.022+row*.0025,.027,'roof')
    for yy in (roof_y0,roof_y1):
        profile=[(0,ridge+.02),(side*roof_half,roofz(roof_half)+.02),
                 (side*roof_half,roofz(roof_half)-.09),(0,ridge-.09)]
        solid('Mitered gable rake board',[(x,y,z) for y in (yy-.04,yy+.04) for x,z in profile],
              [(0,1,2,3),(7,6,5,4)]+[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)],'wood')
box('Timber ridge cap',(0,(roof_y0+roof_y1)/2,ridge+.034),(.11,roof_y1-roof_y0+.035,.065),'roof')

# Post-and-rail corral, connected to the barn with a separately framed gate.
posts=[(-1.58,-.4),(-1.9,-1.55),(-1.9,-2.65),(-.60,-2.65),
       (.60,-2.65),(1.9,-2.65),(1.9,-1.55),(1.58,-.4)]
for x,y in posts:beam('Grounded corral post',(x,y,0),(x,y,1.49),.15,round_log=True)
for i in (0,1,2,4,5,6):
    a,b=posts[i],posts[i+1]
    for z in (.43,.87,1.31):beam('Corral timber rail',(*a,z),(*b,z),.095,round_log=True)
for x in (-.52,.52):box('Gate timber stile',(x,-2.65,.88),(.085,.10,1.0))
for z in (.43,.87,1.31):box('Gate timber rail',(0,-2.65,z),(1.12,.095,.09))
beam('Gate diagonal brace',(-.52,-2.69,.43),(.52,-2.69,1.31),.075,.07)
for z in (.43,1.31):box('Gate iron hinge',(-.57,-2.72,z),(.20,.06,.045),'iron')
box('Gate iron latch',(.57,-2.72,1.31),(.20,.06,.035),'iron')
box('Trade sign backing',(0,y0-.19,2.57),(2.05,.12,.28))
box('Horse Trader presentation label',(0,y0-.263,2.57),(1.99,.027,.245),'lettering')

bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'HorseTrader.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'HorseTrader.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                          export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),
    materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('HORSE_TRADER_AUTHORED',len(objects),flush=True)
