"""Local static fictional meeting hall; sources and reconstruction pinned first."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/vigilance-committee'
OUT=BASE/'local-source-v006';BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert not OUT.exists();OUT.mkdir();bpy.ops.wm.read_factory_settings(use_empty=True)
rng=random.Random(1863);regions={};maps={k:Image.new('RGB',(2048,2048),v)for k,v in [('BaseColor',(0,0,0)),('Roughness',(210,)*3),('Transmission',(0,)*3)]}
for i,(key,col)in enumerate(brief['palette'].items()):
 x,y=i%4*512,i//4*512;regions[key]=(x+8,y+8,x+504,y+504)
 for name,img in maps.items():
  d=ImageDraw.Draw(img);c=tuple(col)if name=='BaseColor'else((255,)*3 if key=='glass'and name=='Transmission'else(8,)*3 if key=='glass'and name=='Roughness'else(210,)*3 if name=='Roughness'else(0,)*3);d.rectangle(regions[key],fill=c)
 d=ImageDraw.Draw(maps['BaseColor'])
 if key in ('wood','roof','inside'):
  for yy in range(y+12,y+498,4):
   tone=rng.randint(-17,17);d.line([(x+xx,yy+math.sin(xx*.04+yy)*1.3)for xx in range(10,502,8)],fill=tuple(max(0,min(255,v+tone))for v in col),width=1)
 elif key!='glass':
  for j in range(6500):
   tone=rng.randint(-15,15);d.point((rng.randint(x+10,x+500),rng.randint(y+10,y+500)),fill=tuple(max(0,min(255,v+tone))for v in col))
material=bpy.data.materials.new('M_VigilanceCommittee_Atlas');material.use_nodes=True
bs=material.node_tree.nodes['Principled BSDF'];bs.inputs['IOR'].default_value=1.46
for name,img in maps.items():
 p=OUT/f'VigilanceCommittee_{name}.png';img.save(p);n=material.node_tree.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(p));n.image.pack()
 if name!='BaseColor':n.image.colorspace_settings.name='Non-Color'
 material.node_tree.links.new(n.outputs['Color'],bs.inputs[{'BaseColor':'Base Color','Roughness':'Roughness','Transmission':'Transmission Weight'}[name]])
objects=[]
def uv(o,key):
 m=o.data;m.update();layer=m.uv_layers.active or m.uv_layers.new();x0,y0,x1,y1=regions[key]
 for f in m.polygons:
  axis=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3)if k!=axis];pts=[m.vertices[v].co for v in f.vertices];lo=[min(p[k]for p in pts)for k in range(3)];hi=[max(p[k]for p in pts)for k in range(3)];a=max(axes,key=lambda k:hi[k]-lo[k]);b=next(k for k in axes if k!=a)
  for i in f.loop_indices:
   p=m.vertices[m.loops[i].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-8);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-8);layer.data[i].uv=((x0+4+u*(x1-x0-8))/2048,1-(y1-4-v*(y1-y0-8))/2048)
def box(name,loc,dim,key='wood'):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);uv(o,key);objects.append(o)
 if 'rubble block' in name or 'horizontal board' in name:
  
  if 'rubble' in name:
   axis=0 if 'Side' in name else 1;sgn=1 if loc[axis]>0 else -1
   for v in o.data.vertices:
    if v.co[axis]*sgn>0:
     v.co[axis]+=sgn*rng.uniform(-.009,.009)
     for k in range(3):
      if k!=axis:v.co[k]+=rng.uniform(-.018,.018)
   o.data.update()
  mod=o.modifiers.new('Material edge relief','BEVEL');mod.width=.015 if 'rubble' in name else .002;mod.segments=1;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name);uv(o,key)
 return o
def solid(name,verts,faces,key='wood'):
 m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update();bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free();o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);m.materials.append(material);uv(o,key);objects.append(o);return o
def panel(name,poly,y0,y1,key='wood'):
 n=len(poly);return solid(name,[(x,y,z)for y in(y0,y1)for x,z in poly],[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)],key)
# Floor and plinth are continuous grounded supports; upper floor is enclosed.
box('Stone foundation',(0,0,.09),(4.96,3.32,.18),'stone')
box('Ground timber floor',(0,0,.205),(4.72,3.12,.05))
box('Upper timber floor',(0,0,2.04),(4.72,3.12,.12))
for x in(-2.30,2.30):box('Side lime mortar core',(x,.06,1.61),(.23,3.00,2.86),'mortar')
box('Rear lime mortar core',(0,1.52,1.61),(4.44,.23,2.86),'mortar')
# Rear and side masonry: individually staggered rectangular rubble blocks.
# Flat joint backs keep contacts definite; front scored plaster conceals its core.
for side in(-1,1):
 for row in range(13):
  z=.18+row*.22
  # side walls run between the front and rear masonry faces
  cuts=[-1.44]+[v for v in[-1.44+.46*(j+.5*(row%2))+rng.uniform(-.045,.045)for j in range(1,8)]if v<1.63]+[1.68]
  for a,b in zip(cuts,cuts[1:]):box('Side rubble block',(side*2.34,(a+b)/2,z+.11),(.24,b-a,.22),'stone')
for row in range(13):
 cuts=[-2.22]+[v for v in[-2.22+.48*(j+.5*(row%2))+rng.uniform(-.045,.045)for j in range(1,11)]if v<2.22]+[2.22]
 for a,b in zip(cuts,cuts[1:]):box('Rear rubble block',((a+b)/2,1.56,.18+row*.22+.11),(b-a,.24,.22),'stone')
# Six French-door leaves form three openings. Original merchant names omitted.
centres=(-1.52,0,1.52);half=.56;front=-1.56
cuts=[-2.46]+[v for c in centres for v in(c-half,c+half)]+[2.46]
for i,(a,b)in enumerate(zip(cuts,cuts[1:])):
 if i%2==0:
  box('Front masonry pier',((a+b)/2,front,1.065),(b-a,.24,1.77),'mortar')
  # Discrete ashlar-score tiles create shallow recessed lines, backed by core.
  for row in range(7):
   z=.20+row*.255;top=min(z+.248,1.949);box('Scored lime plaster',((a+b)/2,front-.133,(z+top)/2),(b-a-.004,.026,top-z),'plaster')
box('Front masonry lintel',(0,front,2.015),(4.92,.24,.13),'mortar')
box('Front plaster lintel',(0,front-.133,2.015),(4.92,.026,.13),'plaster')
def glazed_frame(name,c,y,bottom,w,h,cols,rows):
 # Outer frame, rails and individual panes. No opaque backing in glazed area.
 t=.042;top=bottom+h;left=c-w/2;right=c+w/2
 for x in(left,right):box(name+' stile',(x,y,(bottom+top)/2),(t,.08,h-t))
 for z in(bottom,top):box(name+' rail',(c,y,z),(w+t,.08,t))
 for j in range(1,cols):box(name+' mullion',(left+w*j/cols,y,(bottom+top)/2),(.020,.06,h-t))
 for j in range(1,rows):
  for i in range(cols):
   a=left+w*i/cols+(t/2 if i==0 else .010);b=left+w*(i+1)/cols-(t/2 if i==cols-1 else .010)
   box(name+' glazing bar',((a+b)/2,y,bottom+h*j/rows),(b-a,.06,.020))
 for i in range(cols):
  for j in range(rows):box(name+' glazing',(left+w*(i+.5)/cols,y,bottom+h*(j+.5)/rows),(w/cols-.01,.012,h/rows-.01),'glass')
for c in centres:
 box('Door threshold',(c,front-.035,.22),(1.16,.40,.08),'stone')
 for x in(c-half+.035,c+half-.035):box('Door jamb',(x,front-.055,1.07),(.07,.15,1.70))
 box('Door head',(c,front-.055,1.955),(1.12,.15,.07))
 for side in(-1,1):
  cx=c+side*.267
  box('French door lower panel',(cx,front-.05,.53),(.53,.07,.54))
  glazed_frame('French door',cx,front-.05,.82,.49,1.08,2,3)
# Early false front: two sash windows; lower boards run continuously.
wincentres=(-.66,.66);w=.64;zb=2.53;zt=3.56
for row in range(19):
 lo=2.08+row*.113;hi=lo+.113;spans=[(-2.52,2.52)]
 if hi>zb and lo<zt:
  spans=[(-2.52,wincentres[0]-w/2),(wincentres[0]+w/2,wincentres[1]-w/2),(wincentres[1]+w/2,2.52)]
 for a,b in spans:box('False front horizontal board',((a+b)/2,-1.59,(lo+hi)/2),(b-a,.14,hi-lo))
 # Window-strip infill where a board crosses top/bottom of the aperture.
 for c in wincentres:
  if lo<zb<hi:box('Sash below infill',(c,-1.59,(lo+zb)/2),(w,.14,zb-lo))
  if lo<zt<hi:box('Sash above infill',(c,-1.59,(zt+hi)/2),(w,.14,hi-zt))
for c in wincentres:
 glazed_frame('Upper sash',c,-1.615,zb,w,zt-zb,2,3)
 box('Upper window sill',(c,-1.655,zb-.025),(w+.12,.23,.05))
for z,wid,dep in[(4.23,5.12,.20),(4.29,5.28,.30)]:box('False front cornice',(0,-1.59,z),(wid,dep,.08))
# Roof slopes across X, ridge running front to back; rear gable is timber.
eave=3.04;ridge=4.04;slope=(ridge-eave)/2.46
panel('Rear timber gable',[(-2.46,eave),(2.46,eave),(0,ridge)],1.46,1.64)
for side in(-1,1):
 for row in range(12):
  # Exposed shingle courses with staggered joints; continuous deck below.
  xout=2.60-row*.218;xin=max(0,xout-.26)
  cuts=[-1.59]+[v for v in[-1.59+.25*(j+.5*(row%2))for j in range(1,15)]if v<1.77]+[1.77]
  for a,b in zip(cuts,cuts[1:]):
   a=a-row*.001 if abs(a+1.59)<1e-6 else a;b=b+row*.001 if abs(b-1.77)<1e-6 else b
   x0,x1=sorted((side*xin,side*xout));poly=[(x0,a),(x1,a),(x1,b-.004),(x0,b-.004)]
   solid('Dressed roof shingle',[(x,y,ridge-slope*abs(x)+off+row*.006)for off in(-.018,.013)for x,y in poly],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'roof')
 x0,x1=sorted((0,side*2.60));poly=[(x0,-1.59),(x1,-1.59),(x1,1.77),(x0,1.77)]
 solid('Roof timber deck',[(x,y,ridge-slope*abs(x)+off+(max(0,2.60-abs(x))*.006/.218 if off==-.018 else 0))for off in(-.09,-.018)for x,y in poly],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
box('Roof ridge cap',(0,.09,4.13),(.14,3.36,.10),'roof')
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'VigilanceCommittee.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'VigilanceCommittee.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('VIGILANCE_AUTHORED',len(objects),flush=True)
