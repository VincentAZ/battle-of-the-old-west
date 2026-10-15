"""Local static authoring of a documented, fictional Colorado boarding house."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/boarding-house'
OUT = BASE/'local-source-v004'
BRIEF = BASE/'local-authoring-brief-v004.json'
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
random.seed(1878)

colours = dict(brief['palette'], iron=[34,29,23], glass=[241,248,247], inside=[78,44,21])
regions = {'sign':(8,8,2040,480)}
atlas = Image.new('RGB',(2048,2048),(241,231,208))
rough = Image.new('RGB',(2048,2048),(135,135,135))
trans = Image.new('RGB',(2048,2048),(0,0,0))
d, dr, dt = map(ImageDraw.Draw,(atlas,rough,trans))
for i,(key,colour) in enumerate(colours.items()):
    x,y=i%4*512,512+i//4*512
    regions[key]=(x+8,y+8,x+504,y+504)
    d.rectangle(regions[key],fill=tuple(colour))
    value=12 if key=='glass' else 190 if key in ('wood','roof','inside','brick') else 125
    dr.rectangle(regions[key],fill=(value,)*3)
    dt.rectangle(regions[key],fill=(255,)*3 if key=='glass' else (0,)*3)
    if key in ('wood','roof','inside'):
        for offset in range(12,491,4):
            tint=random.randint(-12,12)
            d.line((x+offset,y+10,x+offset+random.randint(-2,2),y+500),
                   fill=tuple(max(0,min(255,v+tint)) for v in colour),width=1)
    if key=='brick':
        for row in range(8):
            yy=y+8+row*62
            d.line((x+8,yy,x+504,yy),fill=(188,155,116),width=5)
            for col in range(5):
                xx=x+8+col*124+(62 if row%2 else 0)
                d.line((xx,yy,xx,yy+62),fill=(188,155,116),width=5)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf',174)
d.text((1024,244),'BOARDING HOUSE',font=font,fill=(34,43,24),anchor='mm')
d.rectangle((26,60,2022,422),outline=(34,64,36),width=8)
material=bpy.data.materials.new('M_BoardingHouse_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['IOR'].default_value=1.46
for name,img,socket in [('BaseColor',atlas,'Base Color'),('Roughness',rough,'Roughness'),('Transmission',trans,'Transmission Weight')]:
    p=OUT/('BoardingHouse_'+name+'.png');img.save(p)
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(p));node.image.pack()
    if name!='BaseColor':node.image.colorspace_settings.name='Non-Color'
    material.node_tree.links.new(node.outputs['Color'],bsdf.inputs[socket])
objects=[]

def uvmap(o,region):
    mesh=o.data;mesh.update();uv=mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        normal=max(range(3),key=lambda k:abs(face.normal[k]));axes=[k for k in range(3) if k!=normal]
        coords=[mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
        lo=[min(p[k] for p in coords) for k in range(3)];hi=[max(p[k] for p in coords) for k in range(3)]
        tile=region if region!='sign' or face.normal.y<-.5 else 'paint'
        x0,y0,x1,y1=regions[tile];a,b=axes
        if tile in ('wood','roof','inside'):
            b=max(axes,key=lambda k:hi[k]-lo[k]);a=next(k for k in axes if k!=b)
        for loop in face.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co
            u=(v[a]-lo[a])/max(hi[a]-lo[a],1e-8);w=(v[b]-lo[b])/max(hi[b]-lo[b],1e-8)
            uv.data[loop].uv=((x0+8+u*(x1-x0-16))/2048,1-(y1-8-w*(y1-y0-16))/2048)

def box(name,loc,dim,region='wood',rot=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material);uvmap(o,region);o.rotation_euler.z=rot
    objects.append(o);return o

def solid(name,vertices,faces,region):
    m=bpy.data.meshes.new(name);m.from_pydata(vertices,[],faces);m.update()
    bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o)
    m.materials.append(material);uvmap(o,region);objects.append(o);return o

def prism(name,polygon,zfun,depth,region):
    n=len(polygon)
    vertices=[(x,y,zfun(x,y)-depth) for x,y in polygon]+[(x,y,zfun(x,y)) for x,y in polygon]
    return solid(name,vertices,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],region)

# Local wall plane faces -Y. The same function builds true window openings on
# every elevation, then adds glazing and sash without a wall behind the glass.
def wall(name,origin,width,angle,openings):
    c,s=math.cos(angle),math.sin(angle)
    def put(label,u,v,z,w,t,h,region='paint'):
        return box(name+' '+label,(origin[0]+c*u-s*v,origin[1]+s*u+c*v,z),(w,t,h),region,angle)
    cuts=sorted(set([.22,4.10]+[.22+i*.13 for i in range(1,30)]+[h for u,w,b,t,kind in openings for h in (b,t)]))
    for z0,z1 in zip(cuts,cuts[1:]):
        spans=[(-width/2,width/2)]
        for u,w,b,t,kind in openings:
            if z0>=t or z1<=b:continue
            new=[]
            for l,r in spans:
                a,q=u-w/2,u+w/2
                if a>=r or q<=l:new.append((l,r));continue
                if l<a:new.append((l,a))
                if q<r:new.append((q,r))
            spans=new
        for l,r in spans:
            put('wall backing',(l+r)/2,.025,(z0+z1)/2,r-l,.11,z1-z0,'inside')
            put('green clapboard',(l+r)/2,-.043,(z0+z1)/2,r-l,.038,z1-z0-.001,'green')
    for u,w,b,t,kind in openings:
        z=(b+t)/2;h=t-b
        for side in (-1,1):put('opening jamb',u+side*(w/2+.043),-.077,z,.086,.095,h+.12)
        put('projecting sill',u,-.094,b-.039,w+.22,.20,.078)
        put('window head',u,-.086,t+.045,w+.21,.15,.09)
        put('hood cornice',u,-.098,t+.112,w+.29,.20,.045)
        if kind=='window':
            put('clear sash glazing',u,-.018,z,w-.035,.008,h-.035,'glass')
            for du in (-w/2+.024,w/2-.024):put('sash stile',u+du,-.039,z,.048,.045,h)
            for dz in (-h/2+.024,0,h/2-.024):put('sash rail',u,-.052,z+dz,w,.05,.048)
            put('sash central muntin',u,-.051,z,.027,.044,h)
        else:
            put('panel door',u,-.025,z,w,.08,h,'paint')
            for du in (-.21,.21):
                for dz in (-.46,.28):put('recessed door panel',u+du,-.07,z+dz,.26,.016,.50,'green')
            put('iron latch',u+w*.33,-.089,z,.033,.024,.10,'iron')
    for u in (-width/2+.045,width/2-.045):put('corner board',u,-.078,2.16,.09,.074,3.88)
    put('eave frieze',0,-.076,4.015,width,.09,.17)
    # Small square brackets are a disclosed simplification of period ornament.
    for i in range(max(3,round(width/.5))):
        u=-width/2+.16+i*(width-.32)/(max(3,round(width/.5))-1)
        put('eave bracket back',u,-.11,3.86,.075,.12,.23)
        put('eave bracket nose',u,-.18,3.96,.075,.23,.07)

for x0,x1,y0,y1 in [(-2.25,.70,-1.30,1.55),(.70,2.20,-.30,1.55)]:
    box('Grounded timber foundation',((x0+x1)/2,(y0+y1)/2,.07),(x1-x0,y1-y0,.14),'wood')
    for z in (.18,2.24,4.07):box('Timber floor or ceiling',((x0+x1)/2,(y0+y1)/2,z),(x1-x0,y1-y0,.08),'inside')

front=[]
for u in (-1.00,-.12):front.append((u,.49,.66,1.80,'window'))
front.append((.86,.72,.22,1.99,'door'))
front += [(u,.49,2.65,3.79,'window') for u in (-1.00,-.12,.86)]
wall('Main front',(-.775,-1.30),2.95,0,front)
wall('Main west',(-2.25,.125),2.85,-math.pi/2,[(u,.52,b,b+1.14,'window') for u in (-.80,.80) for b in (.66,2.65)])
wall('Rear',(-.025,1.55),4.45,math.pi,[(u,.50,b,b+1.14,'window') for u in (-1.55,-.55,.55,1.55) for b in (.66,2.65)])
wall('Wing east',(2.20,.625),1.85,math.pi/2,[(0,.50,b,b+1.14,'window') for b in (.66,2.65)])
wall('Wing recessed front',(1.45,-.30),1.50,0,[(0,.70,.22,1.99,'door'),(0,.70,2.28,3.98,'door')])
wall('Exposed return',(.70,-.80),1.0,math.pi/2,[])

# Closed timber corner joinery and roof plates bridge the applied trim.
for x,y in [(-2.29,-1.34),(.74,-1.34),(-2.29,1.59),(2.24,1.59),(2.24,-.34)]:
    box('Closed painted corner block',(x,y,2.16),(.16,.16,3.88),'paint')
for x0,x1,y0,y1 in [(-2.25,.70,-1.30,1.55),(.70,2.20,-.30,1.55)]:
    for y in (y0,y1):box('Timber roof plate',((x0+x1)/2,y,4.10),(x1-x0,.14,.14),'paint')
    for x in (x0,x1):box('Timber roof plate',(x,(y0+y1)/2,4.10),(.14,y1-y0,.14),'paint')

# Ground floor porch and the recessed upper porch share supported timber posts.
for x0,x1,y0,y1,z in [(-2.25,.70,-2.12,-1.27,.23),(.70,2.20,-1.45,-.27,.23),(.70,2.20,-1.45,-.27,2.25)]:
    n=math.ceil((x1-x0)/.18)
    for i in range(n):box('Porch floor plank',(x0+(i+.5)*(x1-x0)/n,(y0+y1)/2,z),((x1-x0)/n-.002,y1-y0,.08),'wood')
    for x in (x0+.08,x1-.08):
        box('Porch supporting joist',(x,(y0+y1)/2,z-.085),(.12,y1-y0,.09),'wood')
        if z<1:box('Grounded porch foot',(x,(y0+y1)/2,.065),(.16,y1-y0,.13),'wood')
for x,y,top in [(-2.16,-2.03,2.15),(-1.25,-2.03,2.15),(.61,-2.03,2.15),(.79,-1.36,4.12),(2.11,-1.36,4.12)]:
    box('Painted porch post',(x,y,(.27+top)/2),(.10,.10,top-.27),'paint')
    box('Post foot collar',(x,y,.34),(.15,.15,.14),'paint')
    for level in ([2.10,4.02] if top>3 else [2.10]):
        box('Porch bracket capital',(x,y,level),(.30,.14,.10),'paint')
box('Main porch lintel',(-.775,-2.03,2.16),(2.95,.15,.13),'paint')
box('Upper porch front lintel',(1.45,-1.36,4.055),(1.5,.14,.09),'paint')
box('Upper porch side lintel',(2.11,-.84,4.055),(.14,1.16,.09),'paint')
for i in range(3):
    h=.2025-i*.0675
    box('Entrance step',(.085,-2.18-i*.15,h/2),(.86,.28,h),'wood')
def railing(x0,y0,x1,y1,z):
    length=math.hypot(x1-x0,y1-y0);angle=math.atan2(y1-y0,x1-x0)
    for h in (.10,.67):box('Balcony rail',((x0+x1)/2,(y0+y1)/2,z+h),(length,.065,.065),'paint',angle)
    n=round(length/.12)
    for i in range(1,n):box('Square balcony baluster',(x0+(x1-x0)*i/n,y0+(y1-y0)*i/n,z+.38),(.035,.035,.55),'paint')
railing(.79,-1.36,2.11,-1.36,2.29);railing(2.11,-1.36,2.11,-.30,2.29)
box('Trade sign timber backing',(-.775,-2.18,2.13),(2.32,.20,.30),'wood')
box('Boarding house trade sign',(-.775,-2.29,2.13),(2.25,.035,.27),'sign')

def clip(poly,axis,bound,keep_less):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=(a[axis]-bound)*(1 if keep_less else -1);db=(b[axis]-bound)*(1 if keep_less else -1)
        if da<=1e-9:out.append(a)
        if (da<0 and db>0) or (da>0 and db<0):
            t=da/(da-db);out.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(2)))
    clean=[]
    for p in out:
        if not clean or math.dist(p,clean[-1])>1e-7:clean.append(p)
    if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-7:clean.pop()
    return clean

def roof(name,x0,x1,y0,y1,z,rise):
    cx,cy=(x0+x1)/2,(y0+y1)/2
    run=min(x1-x0,y1-y0)/2;pitch=rise/run
    # Hip faces described independently; shingles are clipped to their borders.
    rx=max(0,(x1-x0)/2-run);ry=max(0,(y1-y0)/2-run)
    r0=(cx-rx,cy-ry);r1=(cx+rx,cy+ry)
    faces=[([(x0,y0),(x1,y0),r1 if rx else r0,r0],lambda x,y:z+(y-y0)*pitch),
           ([(x1,y0),(x1,y1),r1,r1 if rx else r0],lambda x,y:z+(x1-x)*pitch),
           ([(x1,y1),(x0,y1),r0 if rx else r1,r1],lambda x,y:z+(y1-y)*pitch),
           ([(x0,y1),(x0,y0),r0,r0 if rx else r1],lambda x,y:z+(x-x0)*pitch)]
    for poly,zfun in faces:
        clean=[]
        for p in poly:
            if p not in clean:clean.append(p)
        if len(clean)<3:continue
        prism(name+' closed roof boarding',clean,zfun,.07,'inside')
        xmin,xmax=min(p[0] for p in clean),max(p[0] for p in clean)
        ymin,ymax=min(p[1] for p in clean),max(p[1] for p in clean)
        for row in range(math.ceil((ymax-ymin)/.20)):
            for col in range(math.ceil((xmax-xmin)/.23)+1):
                a=xmin+col*.23-(.115 if row%2 else 0);b=ymin+row*.20
                cell=clean
                for axis,bound,less in [(0,a,False),(0,a+.228,True),(1,b,False),(1,b+.199,True)]:
                    if cell:cell=clip(cell,axis,bound,less)
                if len(cell)<3:continue
                area=abs(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(cell,cell[1:]+cell[:1])))/2
                if area<.00008:continue
                prism(name+' sawn shingle',cell,lambda x,y,fn=zfun:fn(x,y)+.027,.027,'roof')
    for y in (y0,y1):box(name+' eave fascia',(cx,y,z-.035),(x1-x0,.07,.12),'paint')
    for x in (x0,x1):box(name+' eave fascia',(x,cy,z-.035),(.07,y1-y0,.12),'paint')
roof('Main hip',-2.46,.91,-1.51,1.76,4.14,.62)
roof('Wing hip',.76,2.40,-1.50,1.74,4.13,.39)
# Main porch roof slopes away from wall. Its rectangular shingles overlap.
prism('Porch roof boarding',[(-2.36,-2.23),(.78,-2.23),(.78,-1.23),(-2.36,-1.23)],lambda x,y:2.22+(y+2.23)*.22,.055,'wood')
for row in range(5):
    for col in range(15):
        a=-2.36+col*3.14/15;b=-2.23+row*.20
        prism('Porch wood shingle',[(a,b),(a+.207,b),(a+.207,b+.225),(a,b+.225)],lambda x,y,r=row:2.242+(y+2.23)*.22+r*.004,.022,'roof')

# Chimneys have closed masonry walls surrounding a genuinely open flue.
for x,y,bottom in [(-1.50,.65,4.35),(1.63,.79,4.32)]:
    top=5.11 if x<0 else 4.98
    for dx,dy,w,t in [(-.14,0,.10,.38),(.14,0,.10,.38),(0,-.14,.18,.10),(0,.14,.18,.10)]:
        box('Brick chimney shaft',(x+dx,y+dy,(bottom+top)/2),(w,t,top-bottom),'brick')
    for level,size in [(top-.06,.43),(top+.01,.47)]:
        for dx,dy,w,t in [(-size/2+.055,0,.11,size),(size/2-.055,0,.11,size),(0,-size/2+.055,size-.22,.11),(0,size/2-.055,size-.22,.11)]:
            box('Corbelled brick chimney rim',(x+dx,y+dy,level),(w,t,.07),'brick')
    box('Dark flue interior',(x,y,bottom+.02),(.20,.20,.04),'inside')

# Modest front fence with an entry gap; no invented elaborate gate or crest.
for l,r in [(-2.35,-.48),(.63,2.30)]:
    for z in (.22,.50):box('Fence horizontal rail',((l+r)/2,-2.70,z),(r-l,.045,.06),'paint')
    n=round((r-l)/.14)
    for i in range(n+1):
        x=l+(r-l)*i/n
        verts=[(x+dx,y,z) for y in (-2.73,-2.69) for dx,z in [(-.035,.02),(.035,.02),(.035,.59),(0,.65),(-.035,.59)]]
        solid('Pointed timber picket',verts,[(0,1,2,3,4),(9,8,7,6,5)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)],'paint')
    for x in (l,r):box('Grounded fence post',(x,-2.70,.34),(.095,.095,.68),'paint')

bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'BoardingHouse.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'BoardingHouse.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('BOARDING_HOUSE_AUTHORED',len(objects),flush=True)
