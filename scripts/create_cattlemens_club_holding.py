"""Author a sourced static fictional Wyoming cattle clubhouse in local Mixar."""
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
BASE=ROOT/'art/western/holdings/expansion-review-v001/cattlemens-club'
OUT=BASE/'local-source-v010'
BRIEF=BASE/'local-authoring-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
random.seed(1884)
colours=dict(brief['palette'],brick_plain=brief['palette']['brick']);regions={'sign':(8,8,2040,480)}
maps={k:Image.new('RGB',(2048,2048),v) for k,v in [('BaseColor',(241,227,196)),('Roughness',(180,)*3),('Transmission',(0,)*3),('Metallic',(0,)*3)]}
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
 if key in ('slate','purple_slate'):
  for row in range(16):
   yy=y+8+row*31
   for c in range(-1,9):
    xx=x+8+c*65+(32 if row%2 else 0);tint=random.randint(-10,10)
    box=(max(x+8,xx+1),yy+1,min(x+504,xx+63),min(y+504,yy+30))
    base=colours['purple_slate'] if row in (5,6,11) else col
    if box[0]<box[2]:draw['BaseColor'].rectangle(box,fill=tuple(max(0,min(255,v+tint)) for v in base))
 if key in ('wood','inside'):
  for xx in range(x+12,x+499,5):
   tint=random.randint(-12,12);draw['BaseColor'].line((xx,y+10,xx+random.randint(-2,2),y+500),fill=tuple(max(0,v+tint) for v in col))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf',145)
draw['BaseColor'].text((1024,238),'CATTLEMEN’S CLUB',font=font,fill=(34,29,24),anchor='mm')
draw['BaseColor'].rectangle((38,42,2010,438),outline=(95,64,88),width=9)
material=bpy.data.materials.new('M_CattlemensClub_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['IOR'].default_value=1.46
for name,img in maps.items():
 p=OUT/('CattlemensClub_'+name+'.png');img.save(p)
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
  tile=region if region!='sign' or f.normal.y<-.5 else 'paint';x0,y0,x1,y1=regions[tile]
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

def box(name,loc,dim,region='paint',rot=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);uvmap(o,'brick_plain' if region=='brick' else region);o.rotation_euler.z=rot;objects.append(o);return o

def panel(name,polygon,y0,y1,region='brick'):
 n=len(polygon);verts=[(u,y,z) for y in (y0,y1) for u,z in polygon]
 return solid(name,verts,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],region)

def curve_rod(name,points,radius,region='iron'):
 # Closed tube sections retain real support contacts at bends.
 for a,b in zip(points,points[1:]):
  a,b=Vector(a),Vector(b);d=b-a
  bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=radius,depth=d.length+radius*.3,location=(a+b)/2)
  o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
  o.data.materials.append(material);uvmap(o,region);objects.append(o)

def beam(name,a,b,width=.07,depth=.07,region='paint'):
 a,b=Vector(a),Vector(b);d=b-a
 o=box(name,(a+b)/2,(width,depth,d.length),region)
 o.rotation_euler=d.to_track_quat('Z','Y').to_euler();return o

def slab(name,quad,thick=.065,region='slate'):
 return solid(name,[(x,y,z-d) for d in (thick,0) for x,y,z in quad],
 [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)

def transform_since(start,origin,angle):
 c,s=math.cos(angle),math.sin(angle)
 for o in objects[start:]:
  p=o.location.copy();o.location=Vector(origin)+Vector((c*p.x-s*p.y,s*p.x+c*p.y,p.z));o.rotation_euler.z+=angle

def sash(name,u,z,w,h,y=-.035):
 box(name+' clear glazing',(u,y,z),(w-.06,.009,h-.06),'glass')
 for x in (u-w/2,u+w/2):box(name+' sash stile',(x,y-.018,z),(.045,.072,h+.045))
 for zz in (z-h/2,z,z+h/2):box(name+' sash rail',(u,y-.02,zz),(w+.04,.075,.045))
 box(name+' sash muntin',(u,y-.023,z),(.027,.074,h))
 box(name+' projecting sill',(u,y-.07,z-h/2-.046),(w+.16,.24,.095))

def elevation(name,width,centres,origin,angle=0,door=False):
 start=len(objects);z0=.52;z1=3.03;bot=1.03;top=2.66;w=.57
 holes=[(u-w/2,u+w/2,bot,top,u,False) for u in centres]
 if door:holes.append((-.40,.40,z0,2.68,0,True))
 holes.sort();cursor=-width/2
 for l,r,b,t,u,isdoor in holes:
  if l>cursor:panel(name+' masonry pier',[(cursor,z0),(l,z0),(l,z1),(cursor,z1)],-.10,.10)
  if b>z0:panel(name+' masonry under sash',[(l,z0),(r,z0),(r,b),(l,b)],-.10,.10)
  panel(name+' masonry lintel',[(l,t),(r,t),(r,z1),(l,z1)],-.10,.10)
  if isdoor:
   box(name+' paneled entry',(u,0,1.56),(.8,.09,1.98))
   for x in (-.2,.2):
    for z in (1.06,1.97):box(name+' raised entry panel',(x,-.052,z),(.29,.03,.68))
   box(name+' iron door latch',(.25,-.08,1.63),(.027,.035,.13),'iron')
   box(name+' door head',(0,-.10,2.67),(.95,.18,.10))
  else:sash(name,u,(bot+top)/2,w,top-bot)
  cursor=r
 if cursor<width/2:panel(name+' masonry pier',[(cursor,z0),(width/2,z0),(width/2,z1),(cursor,z1)],-.10,.10)
 transform_since(start,origin,angle)

# The plan and relative heights are a compressed reconstruction, not measured survey data.
box('Masonry ground plinth',(0,0,.26),(4.8,3.10,.52),'brick_plain')
box('Painted main floor deck',(0,0,.55),(4.4,2.7,.10))
elevation('Front',4.8,[-1.91,-.96,.96,1.91],(0,-1.45,0),door=True)
elevation('Rear',4.8,[-1.82,-.91,.91,1.82],(0,1.45,0),math.pi,False)
elevation('West',2.70,[-.78,.78],(-2.3,0,0),-math.pi/2)
elevation('East',2.70,[-.78,.78],(2.3,0,0),math.pi/2)
box('Upper ceiling deck',(0,0,2.985),(4.6,2.9,.09))
for y in (-1.5,1.5):box('Main eave fascia',(0,y,3.075),(5.18,.38,.19))
for x in (-2.4,2.4):box('Main side eave fascia',(x,0,3.075),(.38,2.62,.19))
for y in (-1.50,1.50):
 for i in range(21):
  x=-2.32+i*.232
  box('Paired eave bracket',(x,y,2.96),(.075,.25,.22))
for x in (-2.4,2.4):
 for i in range(12):box('Side eave bracket',(x,-1.32+i*.24,2.96),(.25,.075,.22))

# Front/right veranda, with masonry piers and a continuous structural deck.
box('Front veranda deck',(.35,-1.93,.55),(5.70,1.01,.10))
box('Right veranda deck',(2.75,.0125,.55),(.9,2.875,.10))
for x in (-2.35,-1.20,0,1.2,2.35,3.08):
 box('Veranda foundation pier',(x,-2.32,.255),(.22,.23,.51),'brick_plain')
for y in (-1.12,0,1.2):box('Side veranda foundation pier',(3.07,y,.255),(.22,.23,.51),'brick_plain')
for y in (-2.35,-1.5):box('Front veranda joist',(.35,y,.42),(5.70,.12,.16))
box('Side veranda joist',(3.07,.005,.42),(.12,2.89,.16))
for i in range(5):
 h=.6*(i+1)/5;y=-3.22+i*.175
 box('Front stair tread and riser',(0,y,h/2),(1.18,.185,h))
for i in range(5):
 h=.6*(i+1)/5;x=3.985-i*.175
 box('Side stair tread and riser',(x,.7,h/2),(.185,.78,h))
for x in (-.66,.66):
 beam('Front stair rail',(x,-3.30,.42),(x,-2.32,.99),.06,.06)
 box('Stair newel',(x,-2.36,.76),(.09,.1,.54))
 beam('Front stair cheek',(x,-3.33,.06),(x,-2.34,.55),.09,.12)
for y in (.26,1.14):
 beam('Side stair cheek',(4.11,y,.06),(3.13,y,.55),.09,.12)
 beam('Side stair rail',(4.08,y,.42),(3.10,y,.99),.06,.06)
 box('Side stair newel',(3.13,y,.76),(.10,.09,.54))
porchposts=[(x,-2.34) for x in (-2.35,-1.18,1.18,2.35,3.08)]+[(3.08,y) for y in (-1.43,0,1.36)]
for x,y in porchposts:
 box('Veranda post',(x,y,1.63),(.115,.115,2.16))
 box('Veranda post foot',(x,y,.68),(.17,.17,.21))
 axis=0 if y==-2.34 else 1
 for sign in (-1,1):
  end=[x,y,2.70];end[axis]+=sign*.29
  if axis==0 and not -2.50<=end[0]<=3.18:continue
  if axis==1 and not -2.40<=end[1]<=1.48:continue
  beam('Veranda diagonal brace',(x,y,2.36),end,.064,.075)
box('Veranda front beam',(.335,-2.34,2.69),(5.73,.27,.23))
box('Veranda right beam',(3.08,-.42,2.72),(.17,3.90,.19))
slab('Front veranda slate roof',[(-2.53,-2.48,2.80),(3.20,-2.48,2.80),(2.48,-1.37,3.18),(-2.53,-1.37,3.18)])
slab('Right veranda slate roof',[(3.20,-2.48,2.80),(3.20,1.60,2.80),(2.48,1.60,3.18),(2.48,-1.37,3.18)])
box('Game label fascia',(0,-2.49,2.68),(1.90,.04,.175),'sign')

# Mansard shell: window holes are cut through the actual sloping roof.
roof_front=slab('Main front mansard slate',[(-2.53,-1.60,3.16),(2.53,-1.60,3.16),(2.25,-.96,4.45),(-2.25,-.96,4.45)])
roof_rear=slab('Main rear mansard slate',[(2.53,1.60,3.16),(-2.53,1.60,3.16),(-2.25,.96,4.45),(2.25,.96,4.45)])
roof_west=slab('Main west mansard slate',[(-2.53,1.60,3.16),(-2.53,-1.60,3.16),(-2.25,-.96,4.45),(-2.25,.96,4.45)])
roof_east=slab('Main east mansard slate',[(2.53,-1.60,3.16),(2.53,1.60,3.16),(2.25,.96,4.45),(2.25,-.96,4.45)])
slab('Upper roof front',[(-2.25,-.96,4.45),(2.25,-.96,4.45),(1.81,0,4.79),(-1.81,0,4.79)])
slab('Upper roof rear',[(2.25,.96,4.45),(-2.25,.96,4.45),(-1.81,0,4.79),(1.81,0,4.79)])
slab('Upper roof west',[(-2.25,.96,4.45),(-2.25,-.96,4.45),(-1.81,0,4.79),(-1.81,.001,4.79)])
slab('Upper roof east',[(2.25,-.96,4.45),(2.25,.96,4.45),(1.81,0,4.79),(1.81,-.001,4.79)])

def cut(o,loc,dim):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);c=bpy.context.object;c.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 bpy.context.view_layer.objects.active=o
 mod=o.modifiers.new('Actual dormer opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=c
 bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(c,do_unlink=True)
 uvmap(o,'slate')

def dormer(name,x,side,roof):
 # Rectangular sash and flat projecting hood match the photographed front type.
 y=side*1.61;z=3.73;w=.47;h=.62
 cut(roof,(x,side*1.34,z),(w+.04,.82,h+.04))
 start=len(objects)
 sash(name,x,z,w,h,0)
 for xx in (x-w/2-.07,x+w/2+.07):
  o=panel(name+' cheek',[(0,3.33),(.01,3.09),(.66,4.40),(.75,4.50),(0,4.22)],xx-.05,xx+.05,'paint')
  # panel local X is inward depth; map to global y, its extrusion to global x.
  for v in o.data.vertices:
   a,b=v.co.x,v.co.y;v.co.x=b;v.co.y=a
  uvmap(o,'paint')
 box(name+' header',(x,0,4.14),(.72,.20,.12))
 box(name+' apron',(x,0,3.36),(.69,.16,.12))
 slab(name+' slate hood',[(x-.39,-.14,4.23),(x+.39,-.14,4.23),(x+.39,.75,4.53),(x-.39,.75,4.53)],.05)
 # Transform from front-facing local y to front or rear roof face.
 for o in objects[start:]:
  if side<0:o.location.y+=y
  else:
   # Mirror the complete local depth about its opening plane.
   for v in o.data.vertices:v.co.y*=-1
   o.location.y=y-o.location.y
   bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()

for x in (-1.80,-.94,.94,1.80):dormer('Front dormer',x,-1,roof_front)
for x in (-1.48,0,1.48):dormer('Reconstructed rear dormer',x,1,roof_rear)

# Central tower projects through the main front roof. Twin arched sash are genuine openings.
cut(roof_front,(0,-1.45,3.95),(1.12,1.12,1.9))
for x in (-.55,.55):box('Tower masonry side',(x,-1.215,3.89),(.14,.75,1.68),'brick_plain')
box('Tower rear masonry',(0,-.88,4.48),(1.18,.12,.50),'brick_plain')
start=len(objects)
for l,r in [(-.62,-.43),(-.10,.10),(.43,.62)]:panel('Tower masonry pier',[(l,3.05),(r,3.05),(r,4.75),(l,4.75)],-.11,.11)
for x in (-.265,.265):
 r=.165;bot=3.55;spring=4.27
 panel('Tower masonry sill',[(x-r,3.05),(x+r,3.05),(x+r,bot),(x-r,bot)],-.11,.11)
 arc=[(x+r*math.cos(t*math.pi/16),spring+r*math.sin(t*math.pi/16)) for t in range(17)]
 panel('Tower masonry above arch',[(x-r,4.75),(x+r,4.75)]+arc,-.11,.11)
 shape=[(x-r+.02,bot+.02),(x+r-.02,bot+.02)]+[(x+(r-.02)*math.cos(t*math.pi/16),spring+(r-.02)*math.sin(t*math.pi/16)) for t in range(17)]
 panel('Tower arched clear glazing',shape,-.03,-.021,'glass')
 for xx in (x-r,x+r):box('Tower sash stile',(xx,-.055,(bot+spring)/2),(.035,.07,spring-bot))
 for z in (bot,(bot+spring)/2,spring):box('Tower sash rail',(x,-.055,z),(.33,.075,.034))
 for j in range(16):
  a=j*math.pi/16;b=(j+1)*math.pi/16
  panel('Tower sash curved head',[(x+rr*math.cos(t),spring+rr*math.sin(t)) for rr,t in [(r-.03,a),(r+.008,a),(r+.008,b),(r-.03,b)]],-.095,-.01,'paint')
 box('Tower projecting sill',(x,-.10,bot-.045),(.43,.24,.09))
for o in objects[start:]:o.location.y-=1.70
box('Tower eave',(0,-1.27,4.76),(1.60,1.25,.16))
for x in (-.60,0,.60):box('Tower eave bracket',(x,-1.75,4.62),(.09,.25,.23))
towerfront=slab('Tower front mansard',[(-.75,-1.87,4.85),(.75,-1.87,4.85),(.43,-1.50,5.79),(-.43,-1.50,5.79)])
slab('Tower rear mansard',[(.75,-.67,4.85),(-.75,-.67,4.85),(-.43,-1.04,5.79),(.43,-1.04,5.79)])
slab('Tower west mansard',[(-.75,-.67,4.85),(-.75,-1.87,4.85),(-.43,-1.50,5.79),(-.43,-1.04,5.79)])
slab('Tower east mansard',[(.75,-1.87,4.85),(.75,-.67,4.85),(.43,-1.04,5.79),(.43,-1.50,5.79)])
slab('Tower top front',[(-.43,-1.50,5.79),(.43,-1.50,5.79),(.34,-1.27,5.88),(-.34,-1.27,5.88)],.045)
slab('Tower top rear',[(.43,-1.04,5.79),(-.43,-1.04,5.79),(-.34,-1.27,5.88),(.34,-1.27,5.88)],.045)
slab('Tower top west',[(-.43,-1.04,5.79),(-.43,-1.50,5.79),(-.34,-1.27,5.88),(-.34,-1.269,5.88)],.045)
slab('Tower top east',[(.43,-1.50,5.79),(.43,-1.04,5.79),(.34,-1.27,5.88),(.34,-1.271,5.88)],.045)
cut(towerfront,(0,-1.72,5.31),(.40,.50,.48))
sash('Tower cap dormer',0,5.31,.36,.44,-1.90)
for x in (-.23,.23):
 box('Tower cap dormer cheek',(x,-1.70,5.32),(.08,.45,.62))
box('Tower cap dormer header',(0,-1.71,5.63),(.59,.51,.09))
box('Tower cap dormer apron',(0,-1.88,5.02),(.57,.18,.12))
for x in (-1.32,1.32):
 box('Brick chimney stack',(x,.29,4.59),(.23,.28,1.50),'brick_plain')
 box('Brick chimney cap',(x,.29,5.34),(.31,.36,.10),'brick_plain')
 box('Dark chimney flue',(x,.29,5.397),(.15,.20,.018),'iron')

for o in objects:
 o.data.materials.clear();o.data.materials.append(material)
 for face in o.data.polygons:face.material_index=0
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'CattlemensClub.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'CattlemensClub.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('CATTLEMENS_CLUB_AUTHORED',len(objects),flush=True)
