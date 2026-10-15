"""Simple sourced first-pass expansion models; cosmetic refinements are deferred."""
import json,hashlib,math,sys,random
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];O=R/'art/western/holdings/expansion-review-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for slug in ['rustlers-corral','quaker-settlement','dance-hall']:
 A=O/slug;E=json.loads((A/'historical-evidence.json').read_text());assert E['pre_modeling_review']['completed'];D=A/'local-source-v001';assert not D.exists();D.mkdir();bpy.ops.wm.read_factory_settings(use_empty=True)
 name=''.join(x.title()for x in slug.split('-'));rng=random.Random(slug)
 colors={'wood':(158,115,68),'paint':(239,231,203)if slug=='dance-hall'else(241,238,218),'roof':(120,107,88),'iron':(42,38,31),'stone':(162,150,126),'glass':(224,238,240),'brick':(159,68,40),'sign':(26,24,20)}
 regions={};maps={k:Image.new('RGB',(2048,2048))for k in ['BaseColor','ORM','Transmission']}
 for i,(key,color)in enumerate(colors.items()):
  x=i%4*512;y=i//4*512;regions[key]=(x+12,y+12,x+500,y+500)
  for channel,img in maps.items():
   c=color if channel=='BaseColor'else(255,30 if key=='glass'else 195,0)if channel=='ORM'else(255,)*3 if key=='glass'else(0,)*3
   ImageDraw.Draw(img).rectangle((x,y,x+511,y+511),fill=c)
  if key in ['wood','roof']:
   dr=ImageDraw.Draw(maps['BaseColor'])
   for yy in range(y+10,y+501,6):
    delta=rng.randint(-16,16);dr.line((x+8,yy,x+503,yy),fill=tuple(max(0,v+delta)for v in color),width=2)
   if key=='roof':
    for yy in range(y+16,y+500,64):dr.line((x+8,yy,x+503,yy),fill=(78,66,52),width=3)
 if slug=='dance-hall':
  x,y,_,_=regions['sign'];dr=ImageDraw.Draw(maps['BaseColor']);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',53);dr.text((x+244,y+244),'DANCE HALL',font=font,anchor='mm',fill=(219,179,81))
 m=bpy.data.materials.new('M_'+name);m.use_nodes=True;nt=m.node_tree;bs=nt.nodes['Principled BSDF']
 for channel,img in maps.items():
  p=D/(name+'_'+channel+'.png');img.save(p);n=nt.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(p));n.image.pack()
  if channel!='BaseColor':n.image.colorspace_settings.name='Non-Color'
  if channel=='ORM':
   sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(n.outputs['Color'],sep.inputs['Color']);nt.links.new(sep.outputs['Green'],bs.inputs['Roughness'])
  else:nt.links.new(n.outputs['Color'],bs.inputs['Base Color'if channel=='BaseColor'else'Transmission Weight'])
 objects=[]
 def solid(label,verts,faces,key):
  me=bpy.data.meshes.new(label);me.from_pydata(verts,[],faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();obj=bpy.data.objects.new(label,me);bpy.context.collection.objects.link(obj);me.materials.append(m);uv=me.uv_layers.new();x0,y0,x1,y1=regions[key]
  for f in me.polygons:
   axes=[i for i in range(3)if i!=max(range(3),key=lambda j:abs(f.normal[j]))];a,b=axes;pts=[me.vertices[i].co for i in f.vertices];lo=[min(p[j]for p in pts)for j in range(3)];hi=[max(p[j]for p in pts)for j in range(3)]
   for li in f.loop_indices:
    p=me.vertices[me.loops[li].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-6);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-6);uv.data[li].uv=((x0+u*(x1-x0))/2048,1-(y1-v*(y1-y0))/2048)
  objects.append(obj);return obj
 def box(label,loc,dim,key='wood'):
  o=solid(label,[(x*dim[0]/2,y*dim[1]/2,z*dim[2]/2)for z in(-1,1)for y in(-1,1)for x in(-1,1)],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],key);o.location=loc;return o
 def pole(label,a,b,r=.05):
  a,b=Vector(a),Vector(b);L=(b-a).length;n=10;v=[(r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z)for z in(-L/2,L/2)for i in range(n)];f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)];o=solid(label,v,f,'wood');o.location=(a+b)/2;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
 def beam(label,a,b,w=.08,key='wood'):
  a,b=Vector(a),Vector(b);o=box(label,(a+b)/2,(w,w,(b-a).length),key);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
 def wall(label,width,height,origin,angle,holes,paint=True):
  start=len(objects);thick=.12;bottom=.2;step=.15
  # Clip horizontal clapboard courses around each actual opening.
  z=bottom
  while z<height-.001:
   top=min(height,z+step);cuts=[(-width/2,width/2)]
   for l,r,b,t,kind in holes:
    if z<t and top>b:
     cuts=[q for a,c in cuts for q in ([(a,min(c,l))]if a<l else[])+([(max(a,r),c)]if c>r else[])if q[1]-q[0]>.001]
   for l,r in cuts:box(label+' clapboard',((l+r)/2,0,(z+top)/2),(r-l,thick,top-z+.006),'paint'if paint else'wood')
   z=top
  for l,r,b,t,kind in holes:
   u=(l+r)/2;w=r-l;h=t-b
   if kind=='door':
    box('Timber entry door',(u,-.015,(b+t)/2),(w,.08,h),'wood')
    for uu in [u-w*.25,u+w*.25]:box('Door panel',(uu,-.064,(b+t)/2),(w*.39,.025,h*.84),'paint')
    box('Iron latch',(r-.09,-.09,(b+t)/2),(.025,.035,.10),'iron')
   else:
    box('Glazing',(u,-.02,(b+t)/2),(w,.015,h),'glass')
    for zz in [b,(b+t)/2,t]:box('Sash rail',(u,-.05,zz),(w+.04,.075,.04),'iron'if slug=='dance-hall'else'paint')
    box('Sash muntin',(u,-.05,(b+t)/2),(.027,.075,h),'iron'if slug=='dance-hall'else'paint')
   for uu in[l,r]:box('Opening jamb',(uu,-.045,(b+t)/2),(.075,.12,h+.06),'paint')
   box('Opening lintel',(u,-.045,t),(w+.12,.13,.075),'paint');box('Opening sill',(u,-.065,b),(w+.12,.18,.055),'paint')
  for o in objects[start:]:
   p=o.location.copy();o.location=Vector(origin)+Vector((math.cos(angle)*p.x-math.sin(angle)*p.y,math.sin(angle)*p.x+math.cos(angle)*p.y,p.z));o.rotation_euler.z+=angle
 if slug=='rustlers-corral':
  pts=[(2.45*math.cos(i*math.tau/16),2.1*math.sin(i*math.tau/16))for i in range(16)]
  for x,y in pts:pole('Grounded corral post',(x,y,0),(x,y,1.45),.085)
  for i,(x,y)in enumerate(pts):
   xx,yy=pts[(i+1)%16]
   if i in[11,12]:continue
   for z in[.38,.78,1.17]:pole('Corral rail',(x,y,z),(xx,yy,z),.052)
  a,b=pts[11],pts[13]
  for z in[.38,.78,1.17]:pole('Closed timber gate',(*a,z),(*b,z),.045)
  pole('Gate brace',(*a,.3),(*b,1.26),.045)
  for x in[-2.45,0,2.45]:pole('Divider post',(x,0,0),(x,0,1.4),.075)
  for z in[.38,.78,1.17]:pole('Dividing rail',(-2.45,0,z),(2.45,0,z),.05)
  pole('Gate wing post',(-1.2,-2.5,0),(-1.2,-2.5,1.4),.085)
  for z in[.38,.78,1.17]:pole('Gate wing',(*a,z),(-1.2,-2.5,z),.05)
 else:
  q=slug=='quaker-settlement';w=5.0 if q else 4.1;dep=2.9 if q else 4.3;h=2.65;ridge=3.42
  box('Stone foundation',(0,0,.09),(w+.10,dep+.10,.18),'stone');box('Timber floor',(0,0,.205),(w,dep,.07),'wood')
  front=[(-1.62,-1.04,.2,1.85,'door'),(.80,1.38,.2,1.85,'door'),(-2.20,-1.85,.85,2.20,'window'),(-.55,-.13,.85,2.20,'window'),(1.75,2.12,.85,2.20,'window')]if q else[(-.7,.7,.2,2.1,'door'),(-1.78,-.98,.65,2.10,'window'),(.98,1.78,.65,2.10,'window')]
  wall('Front',w,h,(0,-dep/2,0),0,front,q or True)
  wall('Rear',w,h,(0,dep/2,0),math.pi,[(-1.5,-.95,.85,2.2,'window'),(.95,1.5,.85,2.2,'window')],q)
  for s in[-1,1]:wall('Side',dep,h,(s*w/2,0,0),-s*math.pi/2,[(-.6,-.10,.85,2.20,'window'),(.45,.95,.85,2.20,'window')]if not q else[(-.27,.27,.85,2.2,'window')],q)
  # Quaker ridge runs across the long facade; dance hall ridge runs rearward.
  rw,rd=(w,dep)if q else(dep,w)
  for side in[-1,1]:
   poly=[(-rw/2-.16,0,ridge),(rw/2+.16,0,ridge),(rw/2+.16,side*(rd/2+.18),h),(-rw/2-.16,side*(rd/2+.18),h)];o=solid('Wood shingle roof',[(x,y,z+d)for d in[-.08,0]for x,y,z in poly],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'roof')
   if not q:o.rotation_euler.z=math.pi/2
  for side in[-1,1]:
   poly=[(-rd/2,h),(rd/2,h),(0,ridge-.06)];vs=[(x,y,z)for x in[side*rw/2-.04,side*rw/2+.04]for y,z in poly];o=solid('Closed gable',vs,[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],'paint'if q else'wood')
   if not q:o.rotation_euler.z=math.pi/2
  if q:
   for x in[-1.7,1.7]:box('Brick chimney',(x,0,3.40),(.20,.23,.7),'brick')
   for x in[-1.33,1.09]:box('Stone entry step',(x,-dep/2-.25,.09),(.88,.50,.18),'stone')
  else:
   box('False front',(0,-dep/2-.02,2.94),(w+.08,.14,.64),'paint');box('Sign fascia',(0,-dep/2-.115,2.97),(3.8,.08,.51),'sign')
   for x in[-w/2,w/2]:box('Front corner trim',(x,-dep/2-.08,1.7),(.12,.14,3.0),'paint')
   for i in range(24):box('Boardwalk plank',(-2.15+i*.187,-dep/2-.38,.10),(.18,.9,.2),'wood')
 bpy.context.view_layer.update();tris=0
 for o in objects:o.data.calc_loop_triangles();tris+=len(o.data.loop_triangles)
 assert tris<30000
 bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=objects[0]
 p=D/(name+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(p));g=D/(name+'.glb');bpy.ops.export_scene.gltf(filepath=str(g),export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
 (D/'authoring.json').write_text(json.dumps(dict(triangles=tris,objects=len(objects),project_sha256=sha(p),source_sha256=sha(g),historical_evidence_sha256=sha(A/'historical-evidence.json'),status='first_pass_pending_visual_review'),indent=2)+'\n');print('AUTHORED',slug,tris,flush=True)
