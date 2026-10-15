"""Build the sourced, static Wagon Fort reconstruction in local Mixar.
Shared primitive construction adapted from create_chuckwagon_holding.py;
no prior wagon meshes, rigs, or game assets are loaded or modified.
"""
import hashlib, json, math, random
from pathlib import Path
import bpy, bmesh
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/wagon-fort'
OUT=BASE/'local-source-v004'
BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists(), 'Preserve previous candidates'
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(1863)
atlas=Image.new('RGB',(2048,2048));draw=ImageDraw.Draw(atlas);regions={}
for i,(key,c) in enumerate(brief['palette'].items()):
 x=(i%3)*682;y=(i//3)*1024;rect=(x+8,y+8,x+674,y+1016);regions[key]=rect
 draw.rectangle(rect,fill=tuple(c))
 if key in ('wood','blue','red'):
  for yy in range(y+14,y+1011,7):
   tint=random.randint(-8,8);draw.line((x+12,yy,x+670,yy),fill=tuple(max(0,min(255,v+tint)) for v in c))
 if key=='canvas':
  for yy in range(y+12,y+1012,4):draw.line((x+12,yy,x+670,yy),fill=(234,224,199))
  for xx in range(x+12,x+670,4):draw.line((xx,y+12,xx,y+1012),fill=(239,229,204))
texture=OUT/'WagonFort_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_WagonFort_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.76
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


def annulus(name,radius,width,thickness,centre,region,segments=40):
    # Four circular loops around X; no doubled seam vertices or open end rings.
    x,y,z=centre;verts=[]
    for xx,rr in [(-width/2,radius-thickness),(-width/2,radius),(width/2,radius),(width/2,radius-thickness)]:
        verts += [(x+xx,y+rr*math.cos(i*math.tau/segments),z+rr*math.sin(i*math.tau/segments))for i in range(segments)]
    faces=[]
    for j in range(4):
        for i in range(segments):faces.append((j*segments+i,j*segments+(i+1)%segments,((j+1)%4)*segments+(i+1)%segments,((j+1)%4)*segments+i))
    return solid(name,verts,faces,region)


def thick_cloth(name,verts,faces):
    o=solid(name,verts,faces,'canvas',True)
    bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Physical canvas thickness','SOLIDIFY');mod.thickness=.008
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def bow(y,a,offset=0):
    normal=Vector((math.cos(a)/.64,0,math.sin(a)/1.04)).normalized()
    return Vector((.64*math.cos(a),y,1.55+1.04*math.sin(a)))+normal*offset


def wagon(index,partial=False):
    start=len(objects)
    for i in range(6):box('Floor plank',(-.5+i*.20,0,1.0),(.20,3.0,.08),'wood')
    for x in (-.635,.635):
        for j in range(3):box('Blue side plank',(x,0,1.11+j*.15),(.065,3.04,.147),'blue')
        box('Blue top rail',(x,0,1.535),(.085,3.07,.065),'blue')
        box('Red bed runner',(x*.69,0,.9),(.14,2.97,.16),'red')
        for y in (-1.4,0,1.4):box('Iron side strap',(x*1.061,y,1.30),(.018,.07,.50),'iron')
    for y in (-1.50,1.50):
        for j in range(3):box('Blue end plank',(0,y,1.11+j*.15),(1.22,.065,.147),'blue')
        for x in (-.48,.48):box('Iron end strap',(x,y*1.026,1.30),(.07,.018,.50),'iron')
    for y,r in ((-1.08,.54),(1.08,.67)):
        box('Red wood axle',(0,y,r),(1.77,.14,.14),'red')
        tube('Iron axle',[(-1.035,y,r),(1.035,y,r)],.032,'iron',8)
        box('Red bolster',(0,y,(r+.91)/2),(1.1,.18,.91-r),'red')
    beam('Red coupling reach',(0,-1.08,.59),(0,1.08,.72),.13,.13,'red')
    for x in (-.39,.39):
        beam('Front hound',(x,-1.08,.67),(x*.20,-1.86,.61),.075,.095,'red')
        beam('Rear hound',(x,1.08,.76),(0,.15,.67),.065,.085,'red')
    tube('Front kingpin',[(0,-1.08,.44),(0,-1.08,.97)],.027,'iron',6)
    # Tongue rests on the ground at the entrance, otherwise connects to
    # the neighbouring rear axle through a short suspended iron chain.
    endz=.055 if index==0 else .60
    beam('Red tongue',(0,-1.20,.65),(0,-3.12,endz),.10,.10,'red')
    for x in (-.88,.88):
        for y,r in ((-1.08,.54),(1.08,.67)):
            annulus('Red wheel felloe',r-.008,.105,.07,(x,y,r),'red',12)
            annulus('Iron wheel tire',r,.112,.015,(x,y,r),'iron',12)
            tube('Red wheel hub',[(x-.13,y,r),(x+.13,y,r)],.088,'red',6)
            for i in range(12):
                a=i*math.tau/12
                beam('Red dished spoke',(x-math.copysign(.025,x),y+.065*math.cos(a),r+.065*math.sin(a)),
                     (x,y+(r-.045)*math.cos(a),r+(r-.045)*math.sin(a)),.039,.046,'red')
            tube('Retaining linchpin',[(x+math.copysign(.141,x),y,r-.055),(x+math.copysign(.141,x),y,r+.055)],.012,'iron',3)
    for y in (-1.44,-.864,-.288,.288,.864,1.44):
        tube('Wood canvas bow',[bow(y,i*math.pi/10) for i in range(11)],.032,'wood',4)
        for x in (-.642,.642):box('Iron bow staple',(x,y,1.50),(.060,.048,.16),'iron')
    ymin=-1.47;ymax=.32 if partial else 1.47;ny=3;na=10
    def cloth(y,a):
        # Shallow cloth sag between the six supported bows, no bulging
        # closed solid in the bed or across the canopy openings.
        off=.034+.001*math.cos((y+1.44)*math.tau/.576)
        return bow(y,a,off)
    verts=[cloth(ymin+(ymax-ymin)*j/ny,i*math.pi/na) for j in range(ny+1) for i in range(na+1)]
    faces=[(j*(na+1)+i,j*(na+1)+i+1,(j+1)*(na+1)+i+1,(j+1)*(na+1)+i) for j in range(ny) for i in range(na)]
    thick_cloth('Partly folded canopy' if partial else 'Full canvas canopy',verts,faces)
    for y in ((ymin,) if partial else (ymin,ymax)):
        # Annular end drape creates a real arched opening; no dark-painted cap.
        verts=[cloth(y,i*math.pi/na) for i in range(na+1)]
        verts += [Vector((.36*math.cos(i*math.pi/na),y,1.65+.66*math.sin(i*math.pi/na))) for i in range(na+1)]
        thick_cloth('Gathered canvas end',verts,[(i,i+1,i+na+2,i+na+1) for i in range(na)])
        tube('Drawn opening hem',verts[na+1:],.010,'canvas',3)
    for x in (-.66,.66):
        for y in (-1.41,-.85,-.28,.28,.85,1.41):
            if y>ymax:continue
            tube('Canvas cord tie',[(x,y,1.56),(x*1.035,y,1.39),(x,y+.035,1.54)],.009,'rope',3)
    bpy.context.view_layer.update()
    theta=index*math.tau/9
    matrix=Matrix.Translation((6.7*math.cos(theta),6.7*math.sin(theta),0))@Matrix.Rotation(theta,4,'Z')
    for o in objects[start:]:
        o.name=f'W{index+1:02d} '+o.name
        o['wagon_index']=index
        o.matrix_world=matrix@o.matrix_world
    return matrix


matrices=[wagon(i,i in (2,6)) for i in range(8)]


def chain_link(name,centre,direction,roll=0):
    # Closed octagonal oval iron link. Adjacent alternating links interlock.
    direction=Vector(direction).normalized()
    q=direction.to_track_quat('X','Z').to_matrix().to_4x4()@Matrix.Rotation(roll,4,'X')
    pts=[Vector((.10*math.cos(i*math.tau/8),.045*math.sin(i*math.tau/8),0)) for i in range(8)]
    verts=[]
    for i,p in enumerate(pts):
        tangent=pts[(i+1)%8]-pts[(i-1)%8];cross=Vector((-tangent.y,tangent.x,0)).normalized()
        for j in range(4):verts.append(Vector(centre)+q.to_3x3()@(p+.014*(cross*math.cos(j*math.tau/4)+Vector((0,0,math.sin(j*math.tau/4))))))
    return solid(name,verts,[(i*4+j,i*4+(j+1)%4,((i+1)%8)*4+(j+1)%4,((i+1)%8)*4+j) for i in range(8) for j in range(4)],'iron')


for i in range(1,8):
    a=matrices[i]@Vector((0,-3.12,.60))
    b=matrices[i-1]@Vector((0,1.08,.67))
    # Rear hitch reaches the cross-axle from the chain endpoint.
    n=max(3,round((b-a).length/.175));points=[]
    for j in range(n+1):
        t=j/n;p=a.lerp(b,t);p.z-=.10*math.sin(t*math.pi);points.append(p)
    for j,p in enumerate(points):
        direction=points[min(j+1,n)]-points[max(j-1,0)]
        o=chain_link(f'Connecting chain {i} link {j}',p,direction,(j%2)*math.pi/2)
        o['chain_index']=i;o['link_index']=j
# Disconnected end at the entrance rests on earth rather than closing the gap.
a=matrices[0]@Vector((0,-3.12,.055))
for j in range(5):
    o=chain_link(f'Entrance slack chain link {j}',a+Vector((-.04*j,-.17*j,.004 if j%2 else -.041)),(0,-1,0),(j%2)*math.pi/2)
    o['chain_index']=0;o['link_index']=j

audit=[];triangles=0
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data)
    closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);area=min(f.calc_area() for f in bm.faces);bm.free()
    assert closed and volume>1e-10 and area>1e-12,(o.name,closed,volume,area)
    o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
    audit.append(dict(name=o.name,closed=closed,volume=volume))
(OUT/'triangle-counts.json').write_text(json.dumps({o.name:len(o.data.loop_triangles) for o in objects},indent=2)+'\n')
assert triangles<=30000,triangles
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'WagonFort.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'WagonFort.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('WAGON_FORT_AUTHORED',len(objects),triangles,flush=True)

