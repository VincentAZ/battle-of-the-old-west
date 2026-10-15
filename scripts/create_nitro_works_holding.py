"""Author the sourced fictional 1890s Nitro Works exterior, static and local."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];A=R/'art/western/holdings/expansion-review-v001/nitro-works';O=A/'local-source-v003';B=A/'local-authoring-brief-v003.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads(B.read_text());assert b['pre_modeling_review']['completed'];assert sha(A/'historical-evidence.json')==b['historical_evidence_sha256']
for p,h in b['source_records'].items():assert sha(R/p)==h,p
assert not O.exists();O.mkdir();bpy.ops.wm.read_factory_settings(use_empty=True)
rng=random.Random(1895);regions={};imgs={k:Image.new('RGB',(2048,2048),(0,0,0))for k in('BaseColor','ORM','Transmission')}
for i,(key,c)in enumerate(b['palette'].items()):
 x=i%4*512;y=i//4*512;regions[key]=(x+8,y+8,x+504,y+504)
 for name,img in imgs.items():
  color=tuple(c)if name=='BaseColor'else (255,14 if key=='glass'else 125 if key in('metal','iron')else 192,255 if key in('metal','iron')else 0)if name=='ORM'else (255,255,255)if key=='glass'else(0,0,0)
  ImageDraw.Draw(img).rectangle((x,y,x+511,y+511),fill=color)
 d=ImageDraw.Draw(imgs['BaseColor'])
 if key in('wood','inside'):
  for yy in range(y+8,y+505,4):
   v=rng.randint(-13,13);d.line([(x+xx,yy+math.sin(xx*.025+yy)*1.4)for xx in range(8,505,8)],fill=tuple(max(0,min(255,a+v))for a in c))
 elif key in('metal','yellow'):
  for j in range(7000):
   v=rng.randint(-7,7);d.point((rng.randint(x+8,x+504),rng.randint(y+8,y+504)),fill=tuple(max(0,min(255,a+v))for a in c))
m=bpy.data.materials.new('M_NitroWorks_Atlas');m.use_nodes=True;nt=m.node_tree;bs=nt.nodes['Principled BSDF'];bs.inputs['IOR'].default_value=1.46
for name,img in imgs.items():
 p=O/f'NitroWorks_{name}.png';img.save(p);n=nt.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(p));n.image.pack()
 if name!='BaseColor':n.image.colorspace_settings.name='Non-Color'
 if name=='ORM':
  sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(n.outputs['Color'],sep.inputs['Color']);nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
 else:nt.links.new(n.outputs['Color'],bs.inputs['Base Color'if name=='BaseColor'else'Transmission Weight'])
objects=[]
def uv(o,key):
 me=o.data;me.update();lay=me.uv_layers.active or me.uv_layers.new();x0,y0,x1,y1=regions[key]
 for f in me.polygons:
  ax=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3)if k!=ax];pts=[me.vertices[i].co for i in f.vertices];lo=[min(v[k]for v in pts)for k in range(3)];hi=[max(v[k]for v in pts)for k in range(3)];a=max(axes,key=lambda k:hi[k]-lo[k]);bb=next(k for k in axes if k!=a)
  for j in f.loop_indices:
   p=me.vertices[me.loops[j].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-8);v=(p[bb]-lo[bb])/max(hi[bb]-lo[bb],1e-8);lay.data[j].uv=((x0+3+u*(x1-x0-6))/2048,1-(y1-3-v*(y1-y0-6))/2048)
def solid(name,vs,fs,key='wood'):
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);me.materials.append(m);uv(o,key);objects.append(o);o['surface_palette']=key;return o
def box(name,loc,dim,key='wood'):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);uv(o,key);objects.append(o);o['surface_palette']=key;return o
def beam(name,p,q,w,d=None,key='wood'):
 from mathutils import Vector
 p=Vector(p);q=Vector(q);o=box(name,(p+q)/2,(w,d or w,(q-p).length),key);o.rotation_euler=(q-p).to_track_quat('Z','Y').to_euler();return o
# Corrugation extruded as a closed ribbon: a solid web with a sinusoidal face.
# u is global horizontal coordinate, v is elevation; f maps local sheet coords.
def sheet(name,u0,u1,v0,v1,f,key='metal',pitch=.11,depth=.014):
 n=max(2,math.ceil((u1-u0)/pitch*6));us=[u0+(u1-u0)*j/n for j in range(n+1)];N=n+1;vs=[]
 for v in(v0,v1):
  for back in(True,False):
   for u in us:vs.append(f(u,v,-.032 if back else depth*(.5+.5*math.cos(2*math.pi*u/pitch))))
 fs=[]
 for i in range(n):fs.extend([(i,i+1,2*N+i+1,2*N+i),(N+i,3*N+i,3*N+i+1,N+i+1),(i,N+i,N+i+1,i+1),(2*N+i,2*N+i+1,3*N+i+1,3*N+i)])
 fs.extend([(0,2*N,3*N,N),(n,N+n,3*N+n,2*N+n)])
 return solid(name,vs,fs,key)
def wall(name,u0,u1,z0,z1,f,holes=(),key='metal'):
 # Rectangular planar partition eliminates opaque faces behind windows/doors.
 us=sorted(set([u0,u1]+[a for h in holes for a in h[:2]]));zs=sorted(set([z0,z1]+[a for h in holes for a in h[2:]]))
 for a,c in zip(us,us[1:]):
  for d,e in zip(zs,zs[1:]):
   if any(h[0]<(a+c)/2<h[1]and h[2]<(d+e)/2<h[3]for h in holes):continue
   if c-a>1e-6 and e-d>1e-6:sheet(name,a,c,d,e,f,key)
def gable(name,x0,x1,y,eave,ridge,key):
 poly=[(x0,eave),(x1,eave),((x0+x1)/2,ridge)]
 return solid(name,[(x,y+off,z)for off in(-.032,.006)for x,z in poly],[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],key)
def roof(name,x0,x1,y0,y1,eave,ridge):
 cx=(x0+x1)/2;half=(x1-x0)/2;gradient=(ridge-eave)/half
 for side in(-1,1):
  f=lambda u,v,t,s=side:(cx+s*v,u,ridge-gradient*v+t)
  sheet(name+' corrugated roof',y0-.10,y1+.10,0,half+.10,f)
  beam(name+' eave',(cx+side*(half+.08),y0-.10,eave-gradient*.08-.060),(cx+side*(half+.08),y1+.10,eave-gradient*.08-.060),.08,.08)
 # Raised two-leaf cap contacts both slopes without a same-plane duplicate.
 for side in(-1,1):
  poly=[(cx,y0-.11,ridge+.040),(cx+side*.11,y0-.11,ridge-gradient*.11+.040),(cx+side*.11,y1+.11,ridge-gradient*.11+.040),(cx,y1+.11,ridge+.040)]
  solid(name+' ridge cap',[(x,y,z+off)for off in(-.029,0)for x,y,z in poly],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'metal')
def front_frame(name,c,y,z,w,h,door=False):
 # timber frame on a real opening. Pane centres and bars fit exactly.
 t=.055
 for x in(c-w/2,c+w/2):box(name+' jamb',(x,y,z+h/2),(t,.09,h+t))
 for zz in(z,z+h):box(name+' rail',(c,y,zz),(w-t,.09,t))
 if door:
  for side in(-1,1):
   ww=(w-t)/2;cx=c+side*ww/2
   for j in range(5):box(name+' door board',(cx-ww/2+ww*(j+.5)/5,y+.012,z+h/2),(ww/5-.003,.047,h-t),'wood')
   for zz in(z+.13,z+h-.13):box(name+' door strap',(cx,y-.018,zz),(ww-.05,.015,.035),'iron')
  box(name+' latch',(c+.06,y-.016,z+h*.50),(.12,.025,.035),'iron')
 else:
  box(name+' vertical bar',(c,y,z+h/2),(.020,.066,h-t))
  for row in range(1,3):
   for side in(-1,1):box(name+' crossbar',(c+side*w/4,y,z+h*row/3),(w/2-.022,.066,.020))
  for i in range(2):
   for j in range(3):box(name+' glazing',(c-w/2+w*(i+.5)/2,y,z+h*(j+.5)/3),(w/2-.017,.012,h/3-.017),'glass')
  box(name+' sill',(c,y-.025,z-.025),(w+.13,.17,.05))
# Main exterior spans a compact three-level silhouette; no process equipment.
cx=.74;x0=-.56;x1=2.04;front=-2.00;back=1.95;floor=.22
box('Works grounded sill',(cx,(front+back)/2,.11),(2.72,4.07,.22))
box('Works floor',(cx,(front+back)/2,.235),(2.64,4.00,.07))
levels=[(front,-.50,1.72,2.35),(-.50,.72,2.35,2.98),(.72,back,2.98,3.61)]
for k,(ya,yb,e,ridge)in enumerate(levels):
 for side,x in [(-1,x0),(1,x1)]:
  f=lambda u,v,t,x=x,side=side:(x+side*t,u,v)
  wall(f'Works tier{k+1} side cladding',ya,yb,floor,e,f)
  for y,ptop in ([(ya,e-.12)]if k==0 else [])+[(yb,(levels[k+1][2]if k<2 else e)-.12)]:
   box(f'Works tier{k+1} corner post',(x,y,(floor+ptop)/2),(.08,.08,ptop-floor))
  ba=ya-.04;bb=yb-.04 if k<2 else yb+.04
  box(f'Works tier{k+1} top beam',(x,(ba+bb)/2,e-.08),(.085,bb-ba,.08))
 roof(f'Works tier{k+1}',x0,x1,ya,yb,e,ridge)
 if k:
  oldridge=levels[k-1][3];oldeave=levels[k-1][2]
  # Closed upper transition wall on the step; overlapped by lower roof edges.
  wall(f'Works tier{k+1} upper step cladding',x0,x1,oldeave,e,lambda u,v,t,ya=ya:(u,ya-t,v))
 gable(f'Works tier{k+1} front gable',x0,x1,ya-.005,e,ridge,'metal')
# Door/window front; rear receives a single sash. All openings are real.
front_holes=[(-.36,.60,floor,1.48),(1.02,1.67,.78,1.47)]
wall('Works front cladding',x0,x1,floor,levels[0][2],lambda u,v,t:(u,front-t,v),front_holes)
front_frame('Works entrance',.12,front-.023,floor,.96,1.26,True)
front_frame('Works front sash',1.345,front-.023,.78,.65,.69)
wall('Works rear cladding',x0,x1,floor,levels[-1][2],lambda u,v,t:(u,back+t,v),[(.30,1.18,1.15,2.06)])
front_frame('Works rear sash',.74,back+.023,1.15,.88,.91)
gable('Works rear gable',x0,x1,back,levels[-1][2],levels[-1][3],'metal')
box('Works entrance step',(.12,front-.22,.10),(1.10,.38,.20))
# Separate yellow corrugated office: no fiction about plant layout or functions.
ox=-1.60;oa=-2.37;ob=-.83;oy0=-.62;oy1=1.35;oe=1.58;orr=2.13
box('Office grounded sill',(ox,(oy0+oy1)/2,.10),(1.66,2.09,.20))
box('Office floor',(ox,(oy0+oy1)/2,.215),(1.59,2.02,.07))
for side,x in[(-1,oa),(1,ob)]:
 wall('Office side yellow cladding',oy0,oy1,.22,oe,lambda u,v,t,x=x,side=side:(x+side*t,u,v),key='yellow')
 for y in(oy0,oy1):box('Office corner post',(x,y,(.22+oe-.12)/2),(.075,.075,oe-.12-.22))
 box('Office eave beam',(x,(oy0+oy1)/2,oe-.08),(.075,oy1-oy0+.075,.08))
wall('Office front yellow cladding',oa,ob,.22,oe,lambda u,v,t:(u,oy0-t,v),[(ox-.31,ox+.31,.22,1.39)],'yellow')
front_frame('Office door',ox,oy0-.023,.22,.62,1.17,True)
# Paired window group at rear, informed by documented paired sash, placement reconstructed.
wh=[(-2.22,-1.77,.67,1.31),(-1.43,-.98,.67,1.31)]
wall('Office rear yellow cladding',oa,ob,.22,oe,lambda u,v,t:(u,oy1+t,v),wh,'yellow')
for a,c,z,t in wh:front_frame('Office paired sash',(a+c)/2,oy1+.022,z,c-a,t-z)
gable('Office front yellow gable',oa,ob,oy0-.005,oe,orr,'yellow');gable('Office rear yellow gable',oa,ob,oy1,oe,orr,'yellow');roof('Office',oa,ob,oy0,oy1,oe,orr)
# Shallow entry porch: supported deck, four posts and metal shed roof.
box('Office porch footing',(ox,oy0-.36,.095),(1.14,.70,.19))
box('Office porch deck',(ox,oy0-.36,.212),(1.15,.72,.044))
for x in(ox-.49,ox+.49):
 for y in(oy0-.65,oy0-.02):
  top=1.42+(y-oy0)*.15-.024;box('Office porch post',(x,y,(.234+top)/2),(.055,.055,top-.234))
 beam('Office porch brace',(x,oy0-.65,1.15),(x,oy0-.43,1.315),.035)
sheet('Office porch metal roof',ox-.60,ox+.60,oy0-.75,oy0+.01,lambda u,v,t:(u,v,1.42+(v-oy0)*.15+t))
box('Office porch front beam',(ox,oy0-.65,1.277),(1.08,.075,.06))
box('Office porch front step',(ox,oy0-.80,.055),(.74,.28,.11))
# Capture the exact source, atlas and pin set before export; no overwrite of prior candidates.
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=O/'NitroWorks.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project));glb=O/'NitroWorks.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(O/'source-script.py').write_bytes(Path(__file__).read_bytes())
(O/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(B),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=b['reconstruction']),indent=2)+'\n');print('NITRO_AUTHORED',len(objects),flush=True)
