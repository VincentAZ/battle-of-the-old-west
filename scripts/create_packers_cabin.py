"""Author a fictional cabin using the pinned, unrelated 1874 Mancos reference."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'art/western/holdings/expansion-review-v001/packers-cabin';OUT=BASE/'local-source-v009';BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed'];assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert not OUT.exists();OUT.mkdir();bpy.ops.wm.read_factory_settings(use_empty=True)
rng=random.Random(1874);atlas=Image.new('RGB',(2048,2048));draw=ImageDraw.Draw(atlas);regions={}
for i,(key,color)in enumerate(brief['palette'].items()):
    x,y=(i%4)*512,(i//4)*512;regions[key]=(x+8,y+8,x+504,y+504);draw.rectangle(regions[key],fill=tuple(color))
    if key in ('wood','roof','door','inside'):
        for row in range(12,500,3):
            tone=rng.randint(-18,18);line=[(x+u,y+row+math.sin(u*.035+row)*1.8)for u in range(10,503,12)]
            draw.line(line,fill=tuple(max(0,min(255,c+tone))for c in color),width=1)
    elif key=='endgrain':
        for r in range(10,246,13):draw.ellipse((x+256-r,y+256-r,x+256+r,y+256+r),outline=tuple(c-24 for c in color),width=2)
    else:
        for j in range(8000):
            tone=rng.randint(-17,17);draw.point((rng.randint(x+8,x+503),rng.randint(y+8,y+503)),fill=tuple(max(0,min(255,c+tone))for c in color))
texture=OUT/'PackersCabin_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_PackersCabin_Atlas');material.use_nodes=True;bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.86
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color']);objects=[]
def uvmap(o,region):
    m=o.data;m.update();uv=m.uv_layers.active or m.uv_layers.new();x0,y0,x1,y1=regions[region]
    for f in m.polygons:
        x0,y0,x1,y1=regions['endgrain' if o.get('is_timber') and abs(f.normal.z)>.999 else region]
        normal=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3)if k!=normal];pts=[m.vertices[i].co for i in f.vertices]
        lo=[min(p[k]for p in pts)for k in range(3)];hi=[max(p[k]for p in pts)for k in range(3)];a=max(axes,key=lambda k:hi[k]-lo[k]);b=next(k for k in axes if k!=a)
        for i in f.loop_indices:
            p=m.vertices[m.loops[i].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-8);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-8)
            uv.data[i].uv=((x0+6+u*(x1-x0-12))/2048,1-(y1-6-v*(y1-y0-12))/2048)
def solid(name,verts,faces,region):
    m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update();bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
    o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);m.materials.append(material);uvmap(o,region);objects.append(o);return o
def box(name,loc,dim,region='wood'):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);uvmap(o,region);objects.append(o);return o
def beam(name,a,b,width=.26,depth=.22,region='wood'):
    a,b=Vector(a),Vector(b);length=(b-a).length;w,h=width/2,depth/2;c=min(w,h)*.38
    cross=[(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]
    verts=[(x,y,z)for z in (-length/2,length/2)for x,y in cross]
    o=solid(name,verts,[tuple(range(7,-1,-1)),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8)for i in range(8)],region)
    direction=(b-a).normalized();up=Vector((0,0,1))if abs(direction.z)<.99 else Vector((0,1,0));u=up.cross(direction).normalized();v=direction.cross(u)
    o['is_timber']=True;uvmap(o,region)
    o.location=(a+b)/2;o.rotation_euler=Matrix((u,v,direction)).transposed().to_euler();bpy.context.view_layer.update();return o
def notch(o,axis,locations,z):
    # Matched upper-half seats at crossing logs. Hidden exact joinery is a
    # reconstruction, without attributing a craft tradition to the photograph.
    for q in locations:
        if axis==0:a,b=(q,o.location.y-.35,z+.11),(q,o.location.y+.35,z+.11)
        else:a,b=(o.location.x-.35,q,z+.11),(o.location.x+.35,q,z+.11)
        cut=beam('Temporary matched log seat',a,b);objects.remove(cut)
        bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Reconstructed crossing seat','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
    uvmap(o,'wood')
def roof_board(name,x0,x1,y0,y1):
    z=lambda y:3.02-.45*abs(y)
    poly=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)];verts=[(x,y,z(y)-.045)for x,y in poly]+[(x,y,z(y))for x,y in poly]
    return solid(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'roof')
# Small exposed foundation is reconstruction; floor stays internal to the pen.
box('Interior earth floor',(0,0,.035),(3.40,2.60,.07),'chink')
for axis in (0,1):
    for side in (-1,1):
        if axis==0:
            spans=[(-1.30,-.4725),(.4725,1.30)]if side<0 else[(-1.30,1.30)]
            for lo,hi in spans:box('Stone wall footing',(side*1.85,(lo+hi)/2,.135),(.30,hi-lo,.27),'stone')
        else:box('Stone wall footing',(0,side*1.45,.08),(4.0,.30,.16),'stone')
for row in range(10):
    z=.27+row*.22
    for y in (-1.45,1.45):
        spans=[(-2.03,2.03)]if y>0 or row>=8 else[(-2.03,-.52),(.52,2.03)]
        for l,r in spans:
            o=beam(f'Wall X log {row}',(l,y,z),(r,y,z));notch(o,0,[q for q in (-1.85,1.85)if l<q<r],z)
            if row<9:
                dl,dr=max(l,-1.70),min(r,1.70)
                box('Recessed wall daubing',((dl+dr)/2,y,z+.11),(dr-dl,.15,.06),'chink')
    for x in (-1.85,1.85):
        if row==9:
            bottom,top=2.25,2.47;lower=(2.975-bottom)/.45;upper=(2.975-top)/.45
            cross=[(-lower,bottom),(lower,bottom),(upper,top),(-upper,top)]
            verts=[(xx,y,zz)for xx in (x-.13,x+.13)for y,zz in cross]
            solid(f'Wall Y log {row}',verts,[(3,2,1,0),(4,5,6,7)]+[(i,(i+1)%4,(i+1)%4+4,i+4)for i in range(4)],'wood')
            continue
        half=1.122 if row==9 else 1.60 if row==8 else 1.63
        o=beam(f'Wall Y log {row}',(x,-half,z+.11),(x,half,z+.11));notch(o,1,[]if row==9 else[-1.45,1.45],z+.11)
        if row<9:box('Recessed side daubing',(x,0,z+.22),(.15,3.0,.06),'chink')
# Shorter gable courses provide actual support for the roof framing.
for x in (-1.85,1.85):
    for row in range(3):
        bottom=2.47+row*.20;top=min(bottom+.20,2.970)
        lower=(2.975-bottom)/.45;upper=(2.975-top)/.45
        cross=[(-lower,bottom),(lower,bottom),(upper,top),(-upper,top)]
        verts=[(xx,y,z)for xx in (x-.13,x+.13)for y,z in cross]
        solid('Sloped gable log',verts,[(3,2,1,0),(4,5,6,7)]+[(i,(i+1)%4,(i+1)%4+4,i+4)for i in range(4)],'wood')
box('Door threshold',(0,-1.45,.16),(1.10,.35,.14),'wood')
for x in (-.53,.53):box('Door jamb',(x,-1.48,1.01),(.13,.27,1.84),'door')
box('Door lintel',(0,-1.48,2.00),(1.19,.27,.14),'door')
for i in range(6):box('Closed vertical door plank',(-.435+i*.174,-1.48,1.08),(.173,.06,1.78),'door')
# Purlins touch gable timber and the roof undersides; transverse upper poles
# reflect the visible period roof, without a claim about hidden fasteners.
for y in [-1.55,-1.12,-.66,0,.66,1.12,1.55]:
    z=3.02-.45*abs(y)-.045-.082
    beam('Roof supporting purlin',(-1.92,y,z),(2.13,y,z),.18,.18,'wood')
for side in (-1,1):
    for i in range(24):
        x0=-2.10+i*.175;x1=x0+.177
        y0,y1=(0,1.73)if side>0 else(-1.73,0)
        # Omit the tiny gable-edge strip occupied by the masonry flue.
        if x0< -1.90:
            if side>0:y0=.43
            else:y1=-.43
        roof_board('Roof board',x0,x1,y0,y1)
    for j,yabs in enumerate([.20,.58,.96,1.34,1.69]):
        y=side*yabs;z=3.02-.45*yabs+.062
        beam('Transverse roof retaining pole',(-1.88 if yabs<.43 else-2.16,y,z),(2.16,y,z),.13,.13)
# Rubble masonry is reconstructed in tan/buff regional sandstone. Each course
# is closed and supported; four-sided upper courses leave an actual open flue.
for row in range(19):
    z=.0975+row*.19;upper=row>=11;cx=-2.29 if upper else-2.20;wx=.76 if upper else.98;wy=.80 if upper else.94
    h=.195
    if upper:
        thick=.19
        for side in (-1,1):
            split=rng.uniform(-.13,.13)
            for lo,hi in [(-wy/2,split),(split,wy/2)]:
                box('Flue side masonry',(cx+side*(wx-thick)/2,(lo+hi)/2,z),(thick+rng.uniform(0,.025),hi-lo+.004,h),'stone')
            box('Flue end masonry',(cx,side*(wy-thick)/2,z),(wx-2*thick+.025,thick+rng.uniform(0,.025),h),'stone')
    else:
        splits=[-wx/2,-wx/6+rng.uniform(-.08,.08),wx/6+rng.uniform(-.08,.08),wx/2]
        for lo,hi in zip(splits,splits[1:]):
            middle=rng.uniform(-.13,.13)
            for ya,yb in [(-wy/2,middle),(middle,wy/2)]:
                box('Chimney rubble',(cx+(lo+hi)/2,(ya+yb)/2,z),(hi-lo+.005,yb-ya+.005,h),'stone')
# Closed low-poly bevels soften individual stones without changing support.
for o in objects:
    if 'masonry'in o.name or 'rubble'in o.name:
        bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Rough masonry arris','BEVEL');mod.width=rng.uniform(.012,.030);mod.segments=1;bpy.ops.object.modifier_apply(modifier=mod.name);uvmap(o,'stone')
    o.data.materials.clear();o.data.materials.append(material)
    for face in o.data.polygons:face.material_index=0
# Cut upper wall arrises beneath the sloped board undersides. Preserve every
# lower course and map the altered top faces back into the existing atlas.
for o in objects:
    if not o.name.startswith(('Wall ','Sloped gable','Recessed ')):continue
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);changed=False
    for v in bm.verts:
        ceiling=2.975-.45*abs(v.co.y)
        if v.co.z>ceiling:v.co.z=ceiling;changed=True
    if changed:
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.transform(o.matrix_world.inverted());bm.to_mesh(o.data);uvmap(o,'chink'if o.name.startswith('Recessed ')else'wood')
    bm.free()
bpy.context.view_layer.update();solids=[]
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update()
    assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0,o.name
    assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
    solids.append(dict(name=o.name,volume_m3=bm.calc_volume(signed=True)));bm.free()
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
assert triangles<=30000,triangles
project=OUT/'PackersCabin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project));bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
glb=OUT/'PackersCabin.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes());(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),triangles=triangles,objects=len(objects),solids=solids,materials=1,rigged=False,animations=0,limitations=brief['reconstruction']),indent=2)+'\n');print('PACKERS_CABIN_AUTHORED',triangles,len(objects),flush=True)
