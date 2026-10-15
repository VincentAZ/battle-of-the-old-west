"""Author the sourced fictional 1890s Portland Crimp House, static and local."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];A=R/'art/western/holdings/expansion-review-v001/crimp-house';O=A/'local-source-v004';B=A/'local-authoring-brief-v004.json'
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
 elif key!='glass':
  for j in range(7000):
   v=rng.randint(-7,7);d.point((rng.randint(x+8,x+504),rng.randint(y+8,y+504)),fill=tuple(max(0,min(255,a+v))for a in c))
m=bpy.data.materials.new('M_CrimpHouse_Atlas');m.use_nodes=True;nt=m.node_tree;bs=nt.nodes['Principled BSDF'];bs.inputs['IOR'].default_value=1.46
for name,img in imgs.items():
 p=O/f'CrimpHouse_{name}.png';img.save(p);n=nt.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(p));n.image.pack()
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
 vs=[(x*dim[0]/2,y*dim[1]/2,z*dim[2]/2)for z in(-1,1)for y in(-1,1)for x in(-1,1)]
 fs=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
 o=solid(name,vs,fs,key);o.location=loc;return o
def beam(name,p,q,w,d=None,key='wood'):
 from mathutils import Vector
 p=Vector(p);q=Vector(q);o=box(name,(p+q)/2,(w,d or w,(q-p).length),key);o.rotation_euler=(q-p).to_track_quat('Z','Y').to_euler();return o
def panel(name,poly,y0,y1,key='paint'):
 n=len(poly);return solid(name,[(x,y,z)for y in(y0,y1)for x,z in poly],[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)],key)
def arch(name,c,y,spring,r,t,depth,key='paint'):
 n=18;poly=[(c+(r+t)*math.cos(j*math.pi/n),spring+(r+t)*math.sin(j*math.pi/n))for j in range(n+1)]
 poly += [(c+r*math.cos(j*math.pi/n),spring+r*math.sin(j*math.pi/n))for j in range(n,-1,-1)]
 return panel(name,poly,y-depth/2,y+depth/2,key)
def flatwall(name,u0,u1,z0,z1,plane,side,holes=()):
 # Plane X for sides, Y for front/rear. Rectangular apertures are cut through
 # both the backing and individual brick faces before any framing is added.
 cutsu=sorted(set([u0,u1]+[q for h in holes for q in h[:2]]));cutsz=sorted(set([z0,z1]+[q for h in holes for q in h[2:]]))
 def blocked(a,c,d,e):return any(h[0]<(a+c)/2<h[1]and h[2]<(d+e)/2<h[3]for h in holes)
 def part(label,a,c,d,e,thickness,offset,key):
  if c-a<1e-7 or e-d<1e-7:return
  loc=(plane+side*offset,(a+c)/2,(d+e)/2)if name.startswith('Side')else((a+c)/2,plane+side*offset,(d+e)/2)
  dim=(thickness,c-a,e-d)if name.startswith('Side')else(c-a,thickness,e-d)
  box(name+' '+label,loc,dim,key)
 for a,c in zip(cutsu,cutsu[1:]):
  for d,e in zip(cutsz,cutsz[1:]):
   if not blocked(a,c,d,e):part('mortar core',a,c,d,e,.18,0,'mortar')
 row=0;d=z0
 while d<z1-1e-6:
  e=min(z1,d+.125);a=u0-.22*(row%2)
  while a<u1-1e-6:
   c=min(u1,a+.44);aa=max(u0,a)
   # Clip brick cells against every aperture boundary before selection.
   us=sorted(set([aa,c]+[u for h in holes if d<h[3] and e>h[2] for u in h[:2] if aa<u<c]));zs=sorted(set([d,e]+[z for z in cutsz if d<z<e]))
   for l,r in zip(us,us[1:]):
    for bot,top in zip(zs,zs[1:]):
     if not blocked(l,r,bot,top) and r-l>.018 and top-bot>.018:
      part('brick',l+.003,r-.003,bot+.003,top-.003,.05,.10,rng.choice(['brick','brick','brick_light','brick_dark']))
   a+=.44
  d=e;row+=1
def sash(name,c,y,bottom,w,h,rows=4):
 t=.04
 for x in(c-w/2,c+w/2):box(name+' jamb',(x,y,bottom+h/2),(t,.105,h+t),'paint')
 for z in(bottom,bottom+h):box(name+' rail',(c,y,z),(w-t,.105,t),'paint')
 box(name+' mullion',(c,y,bottom+h/2),(.022,.065,h-t),'paint')
 for j in range(1,rows):
  for side in(-1,1):box(name+' crossbar',(c+side*w/4,y,bottom+h*j/rows),(w/2-.022,.07,.025 if j==rows//2 else .018),'paint')
 for i in range(2):
  for j in range(rows):box(name+' glazing',(c-w/2+w*(i+.5)/2,y,bottom+h*(j+.5)/rows),(w/2-.018,.012,h/rows-.017),'glass')
 box(name+' sill',(c,y-.015,bottom-.035),(w+.12,.23,.07),'paint')
 # Hood on a supporting wall above the clear opening.
 if name not in ('Storefront display','Entrance door'):box(name+' hood',(c,y-.018,bottom+h+.055),(w+.16,.20,.07),'paint')

# Foundation and enclosed floors. Dimensions are presentation reconstruction.
x0,x1=-1.85,1.85;y0,y1=-2.20,2.20
box('Stone foundation',(0,0,.10),(3.88,4.60,.20),'stone')
box('Ground timber floor',(0,0,.235),(3.72,4.42,.07),'wood')
box('Upper timber floor',(0,0,2.13),(3.72,4.42,.10),'wood')
box('Entrance step',(1.233,y0-.28,.08),(1.02,.46,.16),'stone')
box('Entrance threshold',(1.233,y0-.055,.22),(.99,.28,.10),'stone')
# Side and rear apertures are smaller service/lodging sash, all reconstructed.
for side,x in[(-1,x0),(1,x1)]:
 holes=[(u-.35,u+.35,z,z+1.00)for u in(-.70,.90)for z in(.70,2.55)]
 flatwall('Side',y0+.075,y1-.09,.20,4.20,x,side,holes)
 for u in(-.70,.90):
  for z in(.70,2.55):
   before=len(objects);sash('Side sash',u,0,z,.70,1.00)
   # Sash local X becomes Y; its outward -Y becomes the chosen side normal.
   for o in objects[before:]:
    xx,yy,zz=o.location;o.location=(x+side*(.10-yy),u+(xx-u),zz)
    o.rotation_euler.z=side*math.pi/2
 # Solid low parapets continue the masonry above the roof membrane.
holes=[(c-.36,c+.36,z,z+1.00)for c in(-.84,.84)for z in(.70,2.55)]
flatwall('Rear',x0-.125,x1+.125,.20,4.04,y1,1,holes)
for c in(-.84,.84):
 for z in(.70,2.55):sash('Rear sash',c,y1+.095,z,.72,1.00)

# Three upper sash openings in red masonry; rectangular four-over-four type.
centres=(-1.233,0,1.233)
holes=[(c-.38,c+.38,2.59,3.70)for c in centres]
flatwall('Front upper',x0-.125,x1+.125,2.18,4.20,y0,-1,holes)
for c in centres:sash('Upper front sash',c,y0-.095,2.59,.76,1.11)

# Ground-floor cast iron: repeated pillars and arched transoms with real voids.
for x in(-1.85,-.617,.617,1.85):
 box('Cast pillar base',(x,y0-.055,.355),(.24,.27,.31),'paint')
 box('Cast pillar shaft',(x,y0-.055,1.235),(.15,.19,1.45),'paint')
 box('Cast pillar capital',(x,y0-.055,2.0125),(.26,.28,.115),'paint')
 for side in(-1,1):box('Cast pillar flute',(x+side*.048,y0-.156,1.24),(.012,.014,1.31),'paint')
for j,c in enumerate(centres):
 r=.47;spring=1.50;outer=.55
 arch('Storefront arch',c,y0-.04,spring,r,.08,.18)
 # Above the arch, closed infill to the horizontal floor beam.
 poly=[(c-outer,2.07),(c+outer,2.07)]+[(c+outer*math.cos(k*math.pi/18),spring+outer*math.sin(k*math.pi/18))for k in range(19)]
 panel('Storefront arch spandrel',poly,y0-.04,y0+.05)
 for x in(c-.50625,c+.50625):box('Storefront frame jamb',(x,y0-.045,.875),(.0725,.11,1.25),'paint')
 box('Storefront transom rail',(c,y0-.045,spring),(2*r,.11,.045),'paint')
 poly=[(c+r-.022,spring+.017)]+[(c+(r-.022)*math.cos(k*math.pi/18),spring+.017+(r-.022)*math.sin(k*math.pi/18))for k in range(1,19)]
 panel('Storefront transom glazing',poly,y0-.051,y0-.039,'glass')
 if j<2:
  box('Storefront lower panel',(c,y0-.045,.405),(.94,.11,.31),'paint')
  sash('Storefront display',c,y0-.045,.58,.90,.8775,2)
 else:
  box('Door lower timber panel',(c,y0-.025,.4725),(.90,.08,.415),'wood')
  sash('Entrance door',c,y0-.045,.70,.90,.7575,2)
  box('Door latch',(c+.45,y0-.105,.85),(.06,.025,.03),'iron')
box('Cast floor beam',(0,y0-.03,2.125),(3.94,.25,.11),'paint')
# Bracketed cornice and pale parapet caps. Separate joined levels avoid coplanar
# exposed faces. The low-pitch roof is framed on the complete masonry walls.
box('Cornice fascia',(0,y0-.075,4.19),(3.97,.31,.18),'paint')
box('Cornice crown',(0,y0-.11,4.315),(4.13,.44,.07),'paint')
for x in[-1.80+i*.40 for i in range(10)]:
 panel('Cornice bracket',[(x-.055,4.05),(x+.055,4.05),(x+.055,4.25),(x-.055,4.25)],y0-.245,y0+.02,'paint')
for side in(-1,1):box('Side parapet cap',(side*1.85,.02,4.225),(.27,4.36,.07),'paint')
box('Rear parapet cap',(0,y1,4.065),(3.58,.27,.07),'paint')
def rz(y):return 4.13-(y-y0)*.050
# Closed sloped timber roof decking plus metal membrane touching its upper face.
poly=[(-1.76,y0+.11,rz(y0+.11)),(1.76,y0+.11,rz(y0+.11)),(1.76,y1-.04,rz(y1-.04)),(-1.76,y1-.04,rz(y1-.04))]
fs=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
solid('Roof timber deck',[(x,y,z+dz)for dz in(-.08,0)for x,y,z in poly],fs,'wood')
solid('Roof sheet metal',[(x,y,z+dz)for dz in(0,.012)for x,y,z in poly],fs,'metal')
for i in range(7):
 x=-1.5+i*.50
 beam('Roof standing seam',(x,y0+.11,rz(y0+.11)+.017),(x,y1-.04,rz(y1-.04)+.017),.014,.022,'metal')
# Interior roof perimeter support connected to the side walls.
for side in(-1,1):
 beam('Roof bearing beam',(side*1.72,y0+.11,rz(y0+.11)-.07),(side*1.72,y1-.04,rz(y1-.04)-.07),.15,.12,'wood')
bpy.context.view_layer.update()
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
assert triangles<30000,triangles
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=O/'CrimpHouse.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project));glb=O/'CrimpHouse.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(O/'source-script.py').write_bytes(Path(__file__).read_bytes())
(O/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(B),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=b['reconstruction']),indent=2)+'\n')
print('CRIMP_AUTHORED',len(objects),triangles,flush=True)
