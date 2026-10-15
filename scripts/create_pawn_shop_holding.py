"""Author a sourced static fictional Colorado pawnshop in local Mixar."""
import hashlib
import json
import math
from pathlib import Path
import random
import bpy
import bmesh
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/pawn-shop'
OUT=BASE/'local-source-v004'
BRIEF=BASE/'local-authoring-brief-v004.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
random.seed(1872)
colours=dict(brief['palette'],brick_plain=brief['palette']['brick']);regions={'sign':(8,8,2040,480)}
maps={k:Image.new('RGB',(2048,2048),v) for k,v in [('BaseColor',(45,128,65)),('Roughness',(180,)*3),('Transmission',(0,)*3),('Metallic',(0,)*3)]}
draw={k:ImageDraw.Draw(v) for k,v in maps.items()}
for i,(key,col) in enumerate(colours.items()):
 x,y=i%4*512,512+i//4*512;regions[key]=(x+8,y+8,x+504,y+504)
 draw['BaseColor'].rectangle(regions[key],fill=tuple(col))
 rv=10 if key=='glass' else 65 if key=='gold' else 120 if key=='roof' else 188
 for k,value in [('Roughness',rv),('Transmission',255 if key=='glass' else 0),('Metallic',255 if key=='gold' else 0)]:draw[k].rectangle(regions[key],fill=(value,)*3)
 if key=='brick':
  for row in range(35):
   yy=y+8+row*14
   for c in range(-1,15):
    xx=x+8+c*36+(18 if row%2 else 0)
    tint=random.randint(-16,16)
    box=(max(x+8,xx+1),yy+1,min(x+504,xx+35),min(y+504,yy+13))
    if box[0]<box[2] and box[1]<box[3]:draw['BaseColor'].rectangle(box,fill=tuple(max(0,min(255,v+tint)) for v in col))
   draw['BaseColor'].line((x+8,yy,x+504,yy),fill=tuple(colours['mortar']),width=1)
   for c in range(15):
    xx=x+8+c*36+(18 if row%2 else 0)
    if xx<x+504:draw['BaseColor'].line((xx,yy,xx,min(y+504,yy+14)),fill=tuple(colours['mortar']),width=1)
 if key in ('wood','inside'):
  for xx in range(x+12,x+499,5):
   tint=random.randint(-12,12);draw['BaseColor'].line((xx,y+10,xx+random.randint(-2,2),y+500),fill=tuple(max(0,v+tint) for v in col))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf',245)
draw['BaseColor'].text((1024,238),'PAWN SHOP',font=font,fill=(241,224,166),anchor='mm')
draw['BaseColor'].rectangle((38,42,2010,438),outline=(222,161,42),width=9)
material=bpy.data.materials.new('M_PawnShop_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['IOR'].default_value=1.46
for name,img in maps.items():
 p=OUT/('PawnShop_'+name+'.png');img.save(p)
 node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(p));node.image.pack()
 if name!='BaseColor':node.image.colorspace_settings.name='Non-Color'
 socket={'BaseColor':'Base Color','Roughness':'Roughness','Transmission':'Transmission Weight','Metallic':'Metallic'}[name]
 material.node_tree.links.new(node.outputs['Color'],bsdf.inputs[socket])
objects=[]

def uvmap(o,region):
 m=o.data;m.update();uv=m.uv_layers.active or m.uv_layers.new()
 for f in m.polygons:
  normal=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3) if k!=normal];a,b=axes
  pts=[m.vertices[m.loops[i].vertex_index].co for i in f.loop_indices]
  lo=[min(p[k] for p in pts) for k in range(3)];hi=[max(p[k] for p in pts) for k in range(3)]
  tile=region if region!='sign' or f.normal.y<-.5 else 'green';x0,y0,x1,y1=regions[tile]
  for i in f.loop_indices:
   p=m.vertices[m.loops[i].vertex_index].co
   u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-8);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-8)
   if tile=='brick':
    u=(p[a]+2.35)/4.7;v=p.z/5.2
   uv.data[i].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-v*(y1-y0-10))/2048)

def solid(name,vertices,faces,region):
 m=bpy.data.meshes.new(name);m.from_pydata(vertices,[],faces);m.update()
 bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
 o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);m.materials.append(material);uvmap(o,region);objects.append(o);return o

def box(name,loc,dim,region='green',rot=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);uvmap(o,'brick_plain' if region=='brick' else region);o.rotation_euler.z=rot;objects.append(o);return o

def panel(name,polygon,y0,y1,region='brick'):
 n=len(polygon);verts=[(u,y,z) for y in (y0,y1) for u,z in polygon]
 return solid(name,verts,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],region)

def curve_rod(name,points,radius,region='iron'):
 # Closed six-sided tube sections retain real support contacts at bends.
 for a,b in zip(points,points[1:]):
  a,b=Vector(a),Vector(b);d=b-a
  bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=radius,depth=d.length+radius*.3,location=(a+b)/2)
  o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
  o.data.materials.append(material);uvmap(o,region);objects.append(o)

# Continuous masonry plinth and internal floor decks provide an enclosed shell.
box('Masonry ground plinth',(0,0,.11),(4.28,3.08,.22),'mortar')
for z in (.23,2.55):box('Timber floor deck',(0,0,z),(4.1,2.98,.10),'wood')

def upperwall(name,origin,width,rotation,centres):
 start=len(objects);left=-width/2;right=width/2;r=.35;bottom=3.00;spring=3.88;top=4.40
 cuts=[left]+[v for u in centres for v in (u-r,u+r)]+[right]
 for i,(l,q) in enumerate(zip(cuts,cuts[1:])):
  if i%2==0:panel(name+' masonry pier',[(l,2.54),(q,2.54),(q,top),(l,top)],-.11,.11)
  else:
   u=(l+q)/2
   panel(name+' masonry sill wall',[(l,2.54),(q,2.54),(q,bottom),(l,bottom)],-.11,.11)
   arc=[(u+r*math.cos(t*math.pi/16),spring+r*math.sin(t*math.pi/16)) for t in range(17)]
   panel(name+' masonry above arch',[(l,top),(q,top)]+arc,-.11,.11)
   shape=[(l+.025,bottom+.025),(q-.025,bottom+.025)]+[(u+(r-.025)*math.cos(t*math.pi/16),spring+(r-.025)*math.sin(t*math.pi/16)) for t in range(17)]
   panel(name+' clear sash glazing',shape,-.025,-.017,'glass')
   for x in (l+.023,q-.023):box(name+' sash stile',(x,-.047,(bottom+spring)/2),(.047,.072,spring-bottom),'green')
   for z in (bottom+.023,(bottom+spring)/2,spring):box(name+' sash rail',(u,-.05,z),(2*r,.078,.046),'green')
   box(name+' sash muntin',(u,-.055,(bottom+spring)/2),(.024,.076,spring-bottom),'green')
   box(name+' projecting sill',(u,-.13,bottom-.045),(.88,.32,.09),'mortar')
   for j in range(16):
    a=j*math.pi/16;b=(j+1)*math.pi/16
    poly=[(u+rr*math.cos(t),spring+rr*math.sin(t)) for rr,t in [(r-.046,a),(r,a),(r,b),(r-.046,b)]]
    panel(name+' arched wood sash',poly,-.071,.00,'green')
    poly=[(u+rr*math.cos(t),spring+rr*math.sin(t)) for rr,t in [(r,a),(r+.12,a),(r+.12,b),(r,b)]]
    panel(name+' radial brick arch',poly,-.138,-.095,'brick_plain')
 for o in objects[start:]:o.location=Vector(origin)+o.location;o.rotation_euler.z+=rotation
 # Rotate both local object locations and mesh planes around this elevation origin.
 c,s=math.cos(rotation),math.sin(rotation)
 for o in objects[start:]:
  p=o.location-Vector(origin);o.location=Vector(origin)+Vector((c*p.x-s*p.y,s*p.x+c*p.y,p.z))

upperwall('Front',(0,-1.5,0),4.2,0,[-1.28,0,1.28])
upperwall('Rear',(0,1.5,0),4.2,math.pi,[-1.28,0,1.28])
upperwall('West',(-2.1,0,0),3.0,-math.pi/2,[-.78,.78])
upperwall('East',(2.1,0,0),3.0,math.pi/2,[-.78,.78])
# Ground floor side walls and rear door have no false windows painted over masonry.
for x in (-2.1,2.1):
 o=panel('Side lower masonry',[(-1.5,.22),(1.5,.22),(1.5,2.54),(-1.5,2.54)],-.11,.11)
 o.rotation_euler.z=math.pi/2;o.location.x=x
for l,r in [(-2.1,-.43),(.43,2.1)]:
 o=panel('Rear lower masonry',[(l,.22),(r,.22),(r,2.54),(l,2.54)],-.11,.11);o.location.y=1.5
o=panel('Rear door lintel',[(-.43,2.08),(.43,2.08),(.43,2.54),(-.43,2.54)],-.11,.11);o.location.y=1.5
box('Rear panel door',(0,1.51,1.16),(.86,.095,1.88),'green')
for x in (-.22,.22):
 for z in (.70,1.58):box('Rear raised door panel',(x,1.565,z),(.31,.026,.60),'green')
box('Rear iron latch',(.29,1.566,1.19),(.025,.035,.12),'iron')
box('Rear threshold',(0,1.58,.17),(1.03,.43,.34),'mortar')

# Large display windows, raised paneled bulkheads and recessed glazed entry.
for x in (-1.29,1.29):
 box('Display bulkhead',(x,-1.5,.49),(1.49,.17,.55),'green')
 box('Recessed bulkhead panel',(x,-1.594,.48),(1.23,.028,.31),'green')
 box('Display clear glazing',(x,-1.49,1.50),(1.39,.009,1.35),'glass')
 box('Display transom clear glazing',(x,-1.49,2.29),(1.39,.009,.21),'glass')
 for xx in (x-.74,x+.74):box('Storefront timber upright',(xx,-1.52,1.40),(.10,.18,2.35),'green')
 for z,h in [(.78,.09),(2.19,.07),(2.45,.09)]:box('Display timber rail',(x,-1.53,z),(1.49,.18,h),'green')
 box('Transom central bar',(x,-1.53,2.30),(.05,.15,.26),'green')
# Short return windows connect front display to the recessed door.
for x in (-.51,.51):
 box('Entry return bulkhead',(x,-1.29,.49),(.12,.42,.55),'green')
 box('Entry return clear glazing',(x,-1.30,1.50),(.009,.36,1.35),'glass')
 for z in (.79,2.19,2.45):box('Entry return rail',(x,-1.29,z),(.14,.44,.09),'green')
box('Entry recessed door',(0,-1.09,.71),(.96,.10,.92),'green')
box('Entry door clear glazing',(0,-1.09,1.65),(.84,.008,.91),'glass')
for x in (-.47,.47):box('Entry door stile',(x,-1.10,1.27),(.08,.12,2.02),'green')
for z in (1.18,2.15):box('Entry door rail',(0,-1.105,z),(.96,.12,.09),'green')
box('Entry transom clear glazing',(0,-1.09,2.31),(.86,.009,.21),'glass')
box('Entry transom header',(0,-1.10,2.46),(.98,.14,.10),'green')
box('Entry iron latch',(.34,-1.175,1.10),(.03,.035,.13),'iron')
box('Entry threshold',(0,-1.40,.16),(1.08,.80,.32),'mortar')
box('Structural fascia',(0,-1.525,2.62),(4.24,.24,.30),'green')
box('Painted game label',(0,-1.664,2.62),(3.70,.04,.28),'sign')
for z in (2.44,2.82):box('Fascia projecting molding',(0,-1.57,z),(4.34,.29,.075),'green')
for x in (-2.07,2.07):box('Front corner pilaster',(x,-1.54,1.40),(.17,.25,2.36),'green')

# Simple brick parapet and corbelled cornice; no late catalog ornaments.
o=panel('Front brick parapet',[(-2.1,4.40),(2.1,4.40),(2.1,5.10),(-2.1,5.10)],-.13,.13);o.location.y=-1.5
for z,w,d in [(4.70,4.30,.31),(4.85,4.40,.39),(5.10,4.48,.46)]:box('Brick cornice course',(0,-1.5,z),(w,d,.10),'brick')
for i in range(20):box('Brick dentil',( -1.98+i*3.96/19,-1.66,4.95),(.13,.20,.16),'brick')
def roof_z(y):return 4.92-(y+1.52)*.11
for x in (-2.1,2.1):
 o=panel('Sloped side masonry',[(-1.5,4.40),(1.5,4.40),(1.5,roof_z(1.5)-.09),(-1.5,roof_z(-1.5)-.09)],-.11,.11)
 o.rotation_euler.z=math.pi/2;o.location.x=x
o=panel('Rear roof infill',[(-2.1,4.40),(2.1,4.40),(2.1,roof_z(1.5)-.09),(-2.1,roof_z(1.5)-.09)],-.11,.11);o.location.y=1.5
def roofsheet(name,x0,x1,y0,y1,depth,offset,region):
 poly=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
 return solid(name,[(x,y,roof_z(y)+offset-d) for d in (depth,0) for x,y in poly],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)
roofsheet('Timber roof boarding',-2.25,2.25,-1.51,1.64,.09,0,'wood')
roofsheet('Red tin roof skin',-2.25,2.25,-1.51,1.64,.013,.012,'roof')
for i in range(12):roofsheet('Tin standing seam',-2.20+i*.40-.010,-2.20+i*.40+.010,-1.51,1.64,.045,.047,'roof')
# Small folded apron covers the rear drip edge, fully touching the roof skin.
box('Rear tin drip fold',(0,1.64,roof_z(1.64)-.012),(4.52,.035,.065),'roof')

# Projecting trade emblem, simplified from the museum's iron scroll bracket.
sx=1.84;ywall=-1.635;zarm=3.99
box('Sign wall strap',(sx,ywall,3.71),(.075,.06,.72),'iron')
for z in (3.39,4.03):box('Sign strap mounting plate',(sx,ywall+.015,z),(.16,.075,.10),'iron')
curve_rod('Sign projecting arm',[(sx,ywall,zarm),(sx,-2.63,zarm)],.027)
curve_rod('Sign curved brace',[(sx,ywall,3.43),(sx,-1.86,3.67),(sx,-2.12,3.86),(sx,-2.36,zarm)],.021)
for j,(y,z) in enumerate([(-1.92,3.48),(-2.25,3.64),(-2.60,3.48)]):
 curve_rod('Sign hanging iron',[(sx,y,zarm),(sx,y,z+.155)],.016)
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=.16,location=(sx,y,z))
 o=bpy.context.object;o.name='Gilded trade ball';o.data.materials.append(material);uvmap(o,'gold');objects.append(o)
 for f in o.data.polygons:f.use_smooth=True
 bpy.ops.mesh.primitive_torus_add(major_radius=.160,minor_radius=.008,major_segments=20,minor_segments=6,location=(sx,y,z))
 o=bpy.context.object;o.name='Gilded ball equatorial seam';o.data.materials.append(material);uvmap(o,'gold');objects.append(o)

bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'PawnShop.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'PawnShop.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('PAWN_SHOP_AUTHORED',len(objects),flush=True)
