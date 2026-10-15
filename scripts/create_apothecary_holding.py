"""Author a sourced, fictional 1881–1885 Colorado pharmacy for static review."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/apothecary'
OUT = BASE/'local-source-v003'
BRIEF = BASE/'local-authoring-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
for path, digest in brief['source_records'].items():
    assert sha(ROOT/path) == digest, path
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists()
OUT.mkdir()
random.seed(1881)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# The atlas is shared by all geometry. Optical properties are explicitly
# mapped so timber is matte while window panes and stoppered globes are glass.
regions = {'sign': (8,8,2040,480)}
keys = ['paint','wood','roof','iron','glass','blue','crimson','inside']
colours = {'paint':(239,232,214),'wood':(145,86,39),'roof':(117,76,39),
           'iron':(35,31,27),'glass':(248,251,249),'blue':(18,89,220),
           'crimson':(194,19,37),'inside':(90,54,28)}
roughness = {'paint':.45,'wood':.78,'roof':.86,'iron':.52,'glass':.045,
             'blue':.08,'crimson':.08,'inside':.8,'sign':.47}
transmission = {'glass':1,'blue':.60,'crimson':.60}
atlas = Image.new('RGB',(2048,2048),(239,232,214))
rough = Image.new('RGB',(2048,2048),(120,120,120))
trans = Image.new('RGB',(2048,2048),(0,0,0))
d = ImageDraw.Draw(atlas); dr=ImageDraw.Draw(rough); dt=ImageDraw.Draw(trans)
for i,key in enumerate(keys):
    x,y=(i%4)*512,(i//4)*512+512
    regions[key]=(x+8,y+8,x+504,y+504)
    d.rectangle(regions[key],fill=colours[key])
    v=round(255*roughness[key]);dr.rectangle(regions[key],fill=(v,v,v))
    v=round(255*transmission.get(key,0));dt.rectangle(regions[key],fill=(v,v,v))
    if key in ('wood','roof','inside'):
        for offset in range(12,491,4):
            tint=random.randint(-12,12)
            c=tuple(max(0,min(255,v+tint)) for v in colours[key])
            d.line((x+offset,y+10,x+offset+random.randint(-2,2),y+500),fill=c,width=1)
# Modern font used as an explicitly disclosed approximation to painted serif
# lettering. No historical sign or archive photograph is copied as a texture.
for text,fontsize,cy in [('APOTHECARY',224,185),('DRUGS',101,375)]:
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf',fontsize)
    d.text((1024,cy),text,font=font,fill=(31,29,24),anchor='mm',stroke_width=0)
d.rectangle((26,26,2022,462),outline=(47,38,25),width=9)
material=bpy.data.materials.new('M_Apothecary_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Metallic'].default_value=0
bsdf.inputs['IOR'].default_value=1.46
for name,img,socket in [('BaseColor',atlas,'Base Color'),('Roughness',rough,'Roughness'),('Transmission',trans,'Transmission Weight')]:
    path=OUT/('Apothecary_'+name+'.png');img.save(path)
    node=material.node_tree.nodes.new('ShaderNodeTexImage')
    node.image=bpy.data.images.load(str(path));node.image.pack()
    if name!='BaseColor':node.image.colorspace_settings.name='Non-Color'
    material.node_tree.links.new(node.outputs['Color'],bsdf.inputs[socket])
objects=[]

def uvmap(o,region,sign=False):
    mesh=o.data;mesh.update(); uv=mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        normal=max(range(3),key=lambda k:abs(face.normal[k]))
        axes=[k for k in range(3) if k!=normal]
        coords=[mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
        lo=[min(p[k] for p in coords) for k in range(3)]
        hi=[max(p[k] for p in coords) for k in range(3)]
        tile=region if not sign or face.normal.y<-.5 else 'paint'
        x0,y0,x1,y1=regions[tile]
        for loop in face.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co;a,b=axes
            if tile in ('wood','roof','inside'):
                b=max(axes,key=lambda k:hi[k]-lo[k]);a=next(k for k in axes if k!=b)
            u=(v[a]-lo[a])/max(hi[a]-lo[a],1e-8)
            w=(v[b]-lo[b])/max(hi[b]-lo[b],1e-8)
            uv.data[loop].uv=((x0+8+u*(x1-x0-16))/2048,1-(y1-8-w*(y1-y0-16))/2048)

def box(name,loc,dim,region='wood',rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material);uvmap(o,region,region=='sign')
    if rot:o.rotation_euler=rot
    objects.append(o);return o

def lathe(name,x,y,z,profile,region,scale=.75):
    # Closed revolved profile; rings including r=0 use individual axial points
    # to avoid degenerate triangles along the bottom and liquid surface.
    verts=[];rings=[];segments=32
    for r,h in profile:
        if r==0:
            rings.append([len(verts)]);verts.append((x,y,z+h*scale))
        else:
            rings.append(list(range(len(verts),len(verts)+segments)))
            verts.extend((x+r*scale*math.cos(2*math.pi*i/segments),y+r*scale*math.sin(2*math.pi*i/segments),z+h*scale) for i in range(segments))
    faces=[]
    for a,b in zip(rings,rings[1:]+rings[:1]):
        if len(a)==len(b)==1:continue
        for i in range(segments):
            j=(i+1)%segments
            if len(a)==1:faces.append((a[0],b[j],b[i]))
            elif len(b)==1:faces.append((a[i],a[j],b[0]))
            else:faces.append((a[i],a[j],b[j],b[i]))
    m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o)
    m.materials.append(material);uvmap(o,region)
    for p in m.polygons:p.use_smooth=True
    objects.append(o);return o

# Compact building shell. Front faces -Y. Individual boards are supported by
# a continuous wall backing; real display openings are cut out in both.
box('Closed timber floor',(0,0,.16),(3.6,3.5,.12),'inside')
for x in (-1.65,0,1.65):
    box('Grounded longitudinal sill',(x,0,.06),(.18,3.5,.12),'wood')
# Three front openings: tall windows and central entrance/transom.
openings=[(-1.58,-.66,.72,2.39),(-.41,.41,.22,2.54),(.66,1.58,.72,2.39)]
def facade_strip(z0,z1):
    spans=[(-1.8,1.8)]
    for l,r,b,t in openings:
        if z0>=t or z1<=b:continue
        next_spans=[]
        for a,c in spans:
            if r<=a or l>=c:next_spans.append((a,c));continue
            if a<l:next_spans.append((a,l))
            if c>r:next_spans.append((r,c))
        spans=next_spans
    for a,b in spans:
        box('Front painted horizontal board',((a+b)/2,-1.74,(z0+z1)/2),(b-a,.13,z1-z0),'paint')
# Include each opening boundary in the board breakpoints; no wall crosses glass.
levels=sorted(set([.22,3.83]+[.22+i*.14 for i in range(1,26) if .22+i*.14<3.83]+[v for op in openings for v in op[2:]]))
for a,b in zip(levels,levels[1:]):facade_strip(a,b-.002 if b-a>.01 else b)
for side in (-1,1):
    box('Timber side wall backing',(side*1.75,0,1.36),(.1,3.4,2.28),'inside')
    for row in range(17):
        box('Horizontal timber side siding',(side*1.806,0,.22+(row+.5)*2.28/17),(.055,3.43,2.28/17-.002),'wood')
    box('Front corner trim',(side*1.75,-1.834,1.99),(.11,.085,3.54),'paint')
    box('Rear corner board',(side*1.805,1.705,1.36),(.10,.10,2.28),'wood')
box('Rear continuous timber backing',(0,1.68,1.36),(3.50,.08,2.28),'inside')
for row in range(17):
    box('Rear horizontal siding',(0,1.75,.22+(row+.5)*2.28/17),(3.6,.12,2.28/17-.002),'wood')
# Plain service door is an unglazed reconstructed feature on the rear.
box('Rear service door',(0,1.817,1.12),(.79,.04,1.80),'inside')
for x in (-.45,.45):box('Rear service jamb',(x,1.853,1.13),(.10,.075,1.82),'wood')
box('Rear service lintel',(0,1.853,2.09),(1,.075,.10),'wood')
box('Rear iron latch',(.28,1.875,1.12),(.03,.027,.11),'iron')
box('Rear timber step',(0,1.95,.1),(1,.40,.20),'wood')
# Window framing, actual panes and interiors. Globes remain behind their glass.
for x in (-1.12,1.12):
    for side in (-1,1):
        box('Display-window outer jamb',(x+side*.50,-1.85,1.555),(.10,.13,1.67),'paint')
        box('Display-window head or sill',(x,-1.855,1.555+side*.885),(1.10,.19,.10),'paint')
    box('Display-window dividing rail',(x,-1.857,1.83),(.92,.065,.052),'paint')
    box('Display-window central muntin',(x,-1.852,2.105),(.036,.06,.55),'paint')
    for z,h in [(1.275,1.07),(2.12,.51)]:
        box('Clear display window pane',(x,-1.80,z),(.914,.008,h),'glass')
    box('Interior display shelf',(x,-1.37,.895),(.94,.71,.08),'inside')
    for dx in (-.36,.36):box('Display shelf upright',(x+dx,-1.11,.5475),(.07,.07,.655),'inside')
    box('White-painted window display back',(x,-.975,1.51),(.94,.06,1.19),'paint')
    z=.935
    outer=[(0,.0),(.09,.0),(.13,.018),(.17,.10),(.20,.23),(.18,.36),(.11,.43),(.052,.46),(.05,.59),(.044,.59),(.046,.46),(.106,.424),(.174,.354),(.194,.23),(.164,.105),(.125,.026),(.08,.015),(0,.015)]
    lathe('Clear stoppered show globe',x,-1.43,z,outer,'glass')
    liquid=[(0,.024),(.12,.024),(.158,.105),(.187,.23),(.172,.33),(0,.33)]
    lathe('Blue display liquid' if x<0 else 'Crimson display liquid',x,-1.43,z,liquid,'blue' if x<0 else 'crimson')
    lathe('Glass stopper',x,-1.43,z,[(0,.56),(.037,.56),(.041,.605),(.063,.625),(.072,.66),(.051,.695),(0,.71)],'glass')
# Panel door and transom. This is a wooden shop door, not a modern full-glass slab.
box('Shop door lower panel',(0,-1.77,.69),(.78,.06,.94),'paint')
for x in (-.373,.373):box('Shop door stile',(x,-1.775,1.18),(.075,.075,1.92),'paint')
for z in (1.20,2.12):box('Shop door rail',(0,-1.79,z),(.78,.075,.08),'paint')
box('Clear upper door pane',(0,-1.766,1.66),(.69,.008,.84),'glass')
for x in (-.46,.46):box('Doorway outer jamb',(x,-1.85,1.38),(.10,.12,2.32),'paint')
for z in (2.22,2.59):box('Doorway header',(0,-1.85,z),(.82,.12,.09),'paint')
box('Clear transom pane',(0,-1.78,2.40),(.81,.008,.29),'glass')
box('Small iron door latch',(.267,-1.829,1.11),(.035,.022,.12),'iron')
# Continuous plank step supported by framing, not a floating scenery slab.
for i in range(18):
    box('Front plank step',(-1.8+(i+.5)*.2,-1.99,.17),(.197,.64,.10),'wood')
for x in (-1.6,0,1.6):box('Front step support',(x,-1.99,.06),(.16,.61,.12),'wood')
box('Painted trade sign',(0,-1.842,3.13),(3.32,.042,.80),'sign')
box('False-front cornice',(0,-1.78,3.82),(3.83,.29,.13),'paint')
box('Cornice lower bead',(0,-1.858,3.72),(3.72,.15,.055),'paint')
# Modest gable roof behind the taller false front; discrete overlapping shingles.
run,rise=1.97,.72;angle=math.atan2(rise,run);slope=math.hypot(run,rise)
for end in (-1,1):
    ys=[end*1.70-.06,end*1.70+.06]
    vertices=[(x,y,z) for y in ys for x,z in [(-1.75,2.46),(1.75,2.46),(1.75,2.58),(0,3.23),(-1.75,2.58)]]
    mesh=bpy.data.meshes.new('Closed triangular gable')
    mesh.from_pydata(vertices,[],[(0,1,2,3,4),(9,8,7,6,5)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)])
    mesh.update()
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    o=bpy.data.objects.new('Closed roof gable',mesh);bpy.context.collection.objects.link(o)
    mesh.materials.append(material);uvmap(o,'wood');objects.append(o)
for side in (-1,1):
    box('Roof boarding',(side*run/2,0,2.49+rise/2),(slope,3.58,.065),'inside',(0,side*angle,0))
    for row in range(10):
        t=(row+.5)*slope/10
        for col in range(16):
            a=max(-1.76,-1.76+col*.235-(.1175 if row%2 else 0))
            b=min(1.79,-1.76+(col+1)*.235-(.1175 if row%2 else 0))
            if b-a<.008:continue
            o=box('Overlapping sawn wood shingle',(side*t*math.cos(angle),(a+b)/2,2.49+rise-t*math.sin(angle)+.054),(slope/10+.042,b-a-.002,.018),'roof',(0,side*(angle-.018),0))
    box('Timber eave fascia',(side*1.964,0,2.50),(.07,3.66,.12),'wood')
    rake=box('Rear gable rake trim',(side*run/2,1.841,2.49+rise/2),(slope+.02,.095,.11),'wood',(0,side*angle,0))
    for vertex in rake.data.vertices:
        if vertex.co.x*side<0:
            vertex.co.x=(-rake.location.x-math.sin(side*angle)*vertex.co.z)/math.cos(angle)
    uvmap(rake,'wood')
    for y in (-1.4,-.7,0,.7,1.4):box('Square rafter end',(side*1.85,y,2.40),(.30,.09,.10),'wood')
box('Board ridge cap',(0,0,3.265),(.16,3.6,.08),'roof')
# Positive normals for every disconnected closed component are checked later.
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'Apothecary.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'Apothecary.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('APOTHECARY_AUTHORED',glb,flush=True)
