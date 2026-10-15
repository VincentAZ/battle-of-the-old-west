"""Sourced redwood-woodland edge around the unchanged static works."""
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));import holdings_base as base
A=R/'art/western/holdings/expansion-review-v001/nitro-works';O=A/'base-v001';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();E=json.loads((A/'base-evidence-v001.json').read_text())
assert E['pre_modeling_review']['completed'];assert sha(A/'holding.json')==E['holding_sha256'];assert sha(A/'base-holding-v001.json')==E['base_configuration_sha256']
for s in E['sources']:assert sha(R/s['local'])==s['sha256']
assert not O.exists();oldground=base.ground_mesh
class Outline:
 def __init__(self,rng,half_x,half_y,margin,wobble):self.phase=rng.uniform(0,math.tau)
 def radius(self,a):
  hx=3.70 if math.cos(a)<0 else 3.52;hy=3.24 if math.sin(a)<0 else 3.62
  return (abs(math.cos(a)/hx)**4+abs(math.sin(a)/hy)**4)**(-.25)*(1+.035*math.sin(5*a+self.phase)+.025*math.cos(7*a))
def ground_mesh(*args,**kwargs):
 o=oldground(*args,**kwargs);p=args[3];col=o.data.color_attributes['Col']
 for v in o.data.vertices:v.co.z=0
 for loop in o.data.loops:
  v=o.data.vertices[loop.vertex_index].co;t=.5+.23*math.sin(v.x*4.6+v.y)*math.cos(v.y*5.4);rgb=base.lerp(p['ground'],p['ground_alt'],t)
  margin=max(abs(v.x)/3.14,v.y/3.09);leaf=max(0,min(.78,(margin-.84)*3))*(.6+.4*math.sin(v.y*3.1-v.x)**2)
  if v.y<0 and abs(v.x)<3.0:leaf=0
  rgb=base.lerp(rgb,base.lerp(p['grass'],p['grass_alt'],t),leaf);col.data[loop.index].color_srgb=(*rgb,col.data[loop.index].color[3])
 o.data.update();return o
plants=[]
def scatter(collection_name,rng,outline,kind,count,palette,keep_out,**kwargs):
 objects=[];centres=[]
 for attempt in range(25000):
  if len(centres)==count:break
  a=rng.uniform(0,math.tau);r=outline.radius(a)*math.sqrt(rng.uniform(.20,.85));x,y=r*math.cos(a),r*math.sin(a)
  if abs(x)<3.00 and y<2.94:continue
  if any(math.hypot(x-px,y-py)<(.055 if kind=='sorrel'else .07)for px,py in centres):continue
  centres.append((x,y))
  if kind=='litter':
   bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,.0015));o=bpy.context.object;o.dimensions=(rng.uniform(.05,.13),.004,.003);o.rotation_euler.z=rng.uniform(0,math.tau);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.name='Holding_Base_litter';o.color=(*base.srgb((rng.uniform(.35,.47),.22,.105)),1);objects.append(o);continue
  assert kind=='sorrel';h=rng.uniform(.055,.12);phi=rng.uniform(0,math.tau);tint=base.lerp(palette['grass'],palette['grass_alt'],rng.random())
  bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=.0016,depth=h,location=(x,y,h/2));stem=bpy.context.object;stem.name='Holding_Base_sorrel_stem';stem.color=(*base.srgb(tint),1);objects.append(stem)
  for k in range(3):
   ang=phi+k*math.tau/3;scale=rng.uniform(.78,1.0);poly=[(0,0),(.018,-.016),(.032,-.020),(.041,-.013),(.041,-.006),(.032,0),(.041,.006),(.041,.013),(.032,.020),(.018,.016)];vs=[]
   for dz in(-.0006,.0006):
    for u,v in poly:vs.append((x+scale*(u*math.cos(ang)-v*math.sin(ang)),y+scale*(u*math.sin(ang)+v*math.cos(ang)),h-.13*u+dz))
   n=len(poly);fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)];me=bpy.data.meshes.new('Sorrel leaflet');me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new('Holding_Base_sorrel_leaflet',me);bpy.context.collection.objects.link(o);o.color=(*base.srgb(tint),1);objects.append(o)
  plants.append(dict(x=x,y=y,height=h,leaflets=3))
 assert len(centres)==count,(kind,len(centres));return objects
base.Outline=Outline;base.ground_mesh=ground_mesh;base.scatter=scatter
sys.argv=[__file__,'--','--holding',str(A/'base-holding-v001.json'),'--review',str(A/'review-v003'),'--output',str(O),'--samples','24'];base.main()
(O/'source-script.py').write_bytes(Path(__file__).read_bytes());(O/'authoring.json').write_text(json.dumps(dict(project_sha256=sha(O/'nitro-works-Base.blend'),evidence_sha256=sha(A/'base-evidence-v001.json'),helper_script_sha256=sha(Path(base.__file__)),script_sha256=sha(Path(__file__)),sorrel_plants=plants,litter_fragments=54,game_imported=False),indent=2)+'\n')
