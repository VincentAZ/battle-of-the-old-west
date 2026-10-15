"""Author a documented, unoccupied circular Revival Tent in local Mixar.
Static source only; material and architectural uncertainties are in the pinned brief.
Primitive helpers adapted from the existing Wagon Fort authoring script.
"""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
from mathutils import Vector,Matrix
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/revival-tent'
OUT=BASE/'local-source-v002'
BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists(),'Preserve previous candidates'
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(1872)
atlas=Image.new('RGB',(2048,2048));draw=ImageDraw.Draw(atlas);regions={}
for i,(key,c) in enumerate(brief['palette'].items()):
 x=(i%2)*1024;y=(i//2)*1024;regions[key]=(x+8,y+8,x+1016,y+1016)
 draw.rectangle(regions[key],fill=tuple(c))
 if key=='wood':
  for yy in range(y+12,y+1012,8):
   tint=random.randint(-7,7);draw.line((x+12,yy,x+1012,yy),fill=tuple(max(0,min(255,v+tint))for v in c))
 if key=='canvas':
  for yy in range(y+12,y+1012,4):draw.line((x+12,yy,x+1012,yy),fill=(241,234,214))
  for xx in range(x+12,x+1012,4):draw.line((xx,y+12,xx,y+1012),fill=(246,239,219))
texture=OUT/'RevivalTent_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_RevivalTent_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.8
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]

def solid(name,verts,faces,region,smooth=False):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    uv=mesh.uv_layers.new();x0,y0,x1,y1=regions[region]
    for face in mesh.polygons:
        axis=max(range(3),key=lambda k:abs(face.normal[k]));a,b=[k for k in range(3)if k!=axis]
        points=[mesh.vertices[i].co for i in face.vertices]
        low=[min(v[k]for v in points)for k in range(3)];high=[max(v[k]for v in points)for k in range(3)]
        for loop in face.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co
            u=(v[a]-low[a])/max(1e-6,high[a]-low[a]);w=(v[b]-low[b])/max(1e-6,high[b]-low[b])
            uv.data[loop].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-w*(y1-y0-10))/2048)
        face.use_smooth=smooth
    objects.append(o)
    return o


def box(name,centre,size,region='wood'):
    x,y,z=centre;a,b,c=[v/2 for v in size]
    return solid(name,[(x+u*a,y+v*b,z+w*c)for u,v,w in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)


def beam(name,a,b,width,depth,region='wood'):
    a,b=Vector(a),Vector(b);o=box(name,(0,0,0),(width,depth,(b-a).length),region)
    o.location=(a+b)/2;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return o


def tube(name,points,radius,region='iron',sides=8):
    points=[Vector(p)for p in points];verts=[]
    for i,p in enumerate(points):
        tangent=points[min(i+1,len(points)-1)]-points[max(0,i-1)]
        q=tangent.to_track_quat('Z','Y')
        verts += [p+q@Vector((radius*math.cos(j*math.tau/sides),radius*math.sin(j*math.tau/sides),0))for j in range(sides)]
    faces=[tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))]
    for i in range(len(points)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,b,b+sides,a+sides))
    return solid(name,verts,faces,region)


def cloth(name,vertices,faces):
    o=solid(name,vertices,faces,'canvas',True)
    bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Actual canvas thickness','SOLIDIFY');m.thickness=.012;m.offset=-1
    bpy.ops.object.modifier_apply(modifier=m.name)
    return o


# A single connected roof shell, with genuine open space beneath it.
R=4.2;N=64;NR=8;ZEDGE=2.1;ZTOP=4.8
def roof(r,a):
    t=r/R
    z=ZTOP+(ZEDGE-ZTOP)*t-.045*math.sin(math.pi*t)
    z-=.035*math.sin(math.pi*((a/math.tau*16)%1))*t
    return Vector((r*math.cos(a),r*math.sin(a),z))
verts=[(0,0,ZTOP)]
for j in range(1,NR+1):
    verts.extend(roof(R*j/NR,i*math.tau/N)for i in range(N))
faces=[(0,1+i,1+(i+1)%N)for i in range(N)]
for j in range(NR-1):
    a=1+j*N;b=a+N
    faces.extend((a+i,b+i,b+(i+1)%N,a+(i+1)%N)for i in range(N))
cloth('Circular canvas roof',verts,faces)
tube('Central timber mast',[(0,0,.0),(0,0,4.730)],.09,'wood',12)
for i in range(16):
    a=i*math.tau/16;x,y=R*math.cos(a),R*math.sin(a)
    tube(f'Perimeter pole {i:02}',[(x,y,0),(x,y,2.095)],.053,'wood',8)
    gx,gy=5.35*math.cos(a),5.35*math.sin(a)
    tube(f'Wooden stake {i:02}',[(gx,gy,0),(gx,gy,.27)],.04,'wood',6)
    tube(f'Guy rope {i:02}',[(x,y,2.088),(gx,gy,.19)],.015,'rope',6)
    # Cloth seams follow the actual roof shape, without detached strip geometry.
    # Small hem around each sector is physically joined to the roof shell.
    aa=[a+k*math.tau/64 for k in range(5)]
    vv=[roof(R,t) for t in aa]+[roof(R,t)-Vector((0,0,.12)) for t in aa]
    cloth(f'Canvas valance {i:02}',vv,[(k,k+5,k+6,k+1)for k in range(4)])
    # Rear wall follows the octagonal bay chord with a restrained cloth billow.
    if i<8:
        b=a+math.tau/16
        p=Vector((x,y,0));q=Vector((R*math.cos(b),R*math.sin(b),0))
        vertices=[]
        for zz in (.10,.55,1.10,1.60,2.065):
            for k in range(5):
                t=k/4;v=p.lerp(q,t);v.z=zz
                v+=Vector((math.cos((a+b)/2),math.sin((a+b)/2),0))*.025*math.sin(math.pi*t)*math.sin(math.pi*zz/2.065)
                vertices.append(v)
        cloth(f'Rear canvas wall {i:02}',vertices,[(j*5+k,j*5+k+1,(j+1)*5+k+1,(j+1)*5+k)for j in range(4)for k in range(4)])
        for end in (p,q):
            for zz in (.18,1.1,2.035):
                v=end.copy();v.z=zz
                # One loop encircles the timber and touches the wall edge.
                loop=[v+Vector((.062*math.cos(k*math.tau/8),.062*math.sin(k*math.tau/8),0))for k in range(9)]
                tube(f'Wall tie {i:02}',loop,.012,'rope',4)

# Rotate only the tent envelope half a bay: two front guys flank an actual entrance.
rotation=Matrix.Rotation(math.pi/16,4,'Z')
bpy.context.view_layer.update()
for o in objects:o.matrix_world=rotation@o.matrix_world

# Twelve plain backless benches, with seated height and support expressed in geometry.
for side in (-1,1):
    for row in range(6):
        prefix=f'Bench {side:+d} {row:02}'
        x=side*1.35;y=-2.05+row*.65
        box(prefix+' seat',(x,y,.44),(1.65,.32,.08))
        for dx in (-.63,.63):
            for dy in (-.10,.10):box(prefix+' leg',(x+dx,y+dy,.20),(.065,.065,.40))
        box(prefix+' stretcher',(x,y,.17),(1.30,.06,.07))
        for dx in (-.63,.63):box(prefix+' end stretcher',(x+dx,y,.17),(.065,.23,.07))

# Low speaker platform: visible pier blocks, joists, planks, step and a plain lectern.
for x in (-.90,.90):
    for y in (2.35,3.05):box('Platform timber foot',(x,y,.055),(.22,.20,.11))
    box('Platform longitudinal joist',(x,2.70,.145),(.12,.90,.07))
for i in range(10):box('Platform floor plank',(-.99+i*.22,2.7,.21),(.22,1.05,.06))
box('Platform front step',(0,1.99,.09),(.95,.35,.18))
box('Lectern foot',(0,2.72,.28),(.65,.40,.08))
for x in (-.24,.24):box('Lectern upright',(x,2.72,.65),(.065,.065,.68))
box('Lectern front panel',(0,2.51,.68),(.59,.04,.54))
for x in (-.24,.24):box('Lectern panel support',(x,2.63,.60),(.065,.24,.08))
box('Lectern desk',(0,2.65,1.025),(.72,.52,.07))

bpy.context.view_layer.update()
audit=[];triangles=0
for o in objects:
    # World vertices are baked once; every saved component remains independent.
    points=[o.matrix_world@v.co for v in o.data.vertices]
    o.matrix_world.identity()
    for v,p in zip(o.data.vertices,points):v.co=p
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data)
    closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    area=min(f.calc_area() for f in bm.faces);bm.free()
    assert closed and volume>1e-10 and area>1e-12,(o.name,closed,volume,area)
    o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
    audit.append(dict(name=o.name,closed=closed,volume=volume))
assert triangles<=30000,triangles
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'RevivalTent.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'RevivalTent.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('REVIVAL_TENT_AUTHORED',len(objects),triangles,flush=True)

