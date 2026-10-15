"""Author sourced Trouble miniatures locally in Mixar, with editable sources."""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'research/western-presentation/trouble-landscapes.json'
OUT = ROOT/'art/western/trouble/landscapes-v002'
PALETTE = {
    'Earth': (.19, .083, .025), 'Sand': (.55, .36, .16),
    'Sandstone': (.69, .51, .29), 'SandstoneLight': (.82, .67, .44),
    'SandstoneDark': (.51, .36, .18), 'Varnish': (.30, .20, .11),
    'Snow': (.86, .92, 1.0), 'SnowShadow': (.44, .62, .83),
    'Cloud': (.13, .18, .26), 'CloudLight': (.31, .40, .51),
    'Grass': (.44, .23, .055), 'GrassLight': (.64, .40, .11),
    'Char': (.012, .010, .008), 'FlameOrange': (1, .13, .003),
    'FlameGold': (1, .52, .009), 'FlameCore': (1, .88, .24),
}
MATS = {}
PARTS = []
RNG = random.Random(8317)


def mesh(name, vertices, faces, materials, indices=None, smooth=False):
    data=bpy.data.meshes.new(name);data.from_pydata(vertices, [], faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    for mat in materials:data.materials.append(MATS[mat])
    for i, polygon in enumerate(data.polygons):
        polygon.material_index=indices[i] if indices else 0;polygon.use_smooth=smooth
    PARTS.append(obj);return obj


def ellipsoid(name, location, scale, material, subdivisions=3):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,radius=1,location=location)
    obj=bpy.context.object;obj.name=name;obj.scale=scale;obj.data.materials.append(MATS[material])
    for p in obj.data.polygons:p.use_smooth=True
    PARTS.append(obj);return obj


def base(material='Earth',snow=False):
    # An irregular edged, gently rolling closed ground slice, not a plastic disc.
    n=72;nr=15;verts=[(0,0,.10)];faces=[]
    for r in range(1,nr+1):
        for i in range(n):
            a=i*math.tau/n;f=r/nr;edge=1+.023*math.sin(a*7)+.012*math.cos(a*13)
            x=.91*f*math.cos(a)*edge;y=.71*f*math.sin(a)*edge
            z=.10+.038*math.sin(x*6+y*3)*math.cos(y*7)+.025*math.cos(x*11-y*4)
            if snow:z+=.035*math.sin(x*4-y*5)
            verts.append((x,y,z))
    for i in range(n):faces.append((0,1+i,1+(i+1)%n))
    for r in range(nr-1):
        for i in range(n):
            a=1+r*n+i;b=1+r*n+(i+1)%n;faces.append((a,a+n,b+n,b))
    bottom=len(verts)
    for i in range(n):
        p=verts[1+(nr-1)*n+i];verts.append((p[0],p[1],0))
    for i in range(n):faces.append((1+(nr-1)*n+i,bottom+i,bottom+(i+1)%n,1+(nr-1)*n+(i+1)%n))
    faces.append(tuple(reversed(range(bottom,bottom+n))))
    return mesh('GroundSlice',verts,faces,[material],smooth=True)


def blade(x,y,z,height,width,material,angle,bend=.12):
    # Curved tapered ribbon with its own thickness-free double-sided material.
    dx=math.cos(angle);dy=math.sin(angle);verts=[]
    for i in range(5):
        t=i/4;w=width*(1-t);cx=x+dx*bend*t*t;cy=y+dy*bend*t*t
        verts.extend([(cx-dy*w,cy+dx*w,z+height*t),(cx+dy*w,cy-dx*w,z+height*t)])
    return mesh('Blade',verts,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(4)],[material])


def winter():
    base('SnowShadow',True)
    for x,y,s in [(-.34,.19,.45),(.35,.05,.40),(-.05,-.38,.37),(.3,.4,.27)]:
        ellipsoid('SnowDrift',(x,y,.13),(s,s*.7,.085),'Snow')
    for i in range(8):
        x=RNG.uniform(-.7,.7);y=RNG.uniform(-.47,.47)
        ellipsoid('ExposedRidge',(x,y,.12),(.11,.07,.032),'Earth',2)
    for i in range(28):
        x=RNG.uniform(-.69,.69);y=RNG.uniform(-.5,.5)
        blade(x,y,.13,RNG.uniform(.08,.19),.007,'Grass',RNG.random()*math.tau,.03)
    # A storm bank: overlapping soft forms, flattened below and rising at the back.
    for i in range(13):
        x=RNG.uniform(-.61,.61);y=RNG.uniform(-.24,.27);z=1.16+RNG.uniform(-.04,.17)
        ellipsoid('StormCloud',(x,y,z),(RNG.uniform(.24,.34),.25,RNG.uniform(.16,.26)),
                  'CloudLight' if z>1.23 else 'Cloud')
    for i in range(55):
        x=RNG.uniform(-.65,.64);y=RNG.uniform(-.35,.32);z=RNG.uniform(.30,1.0)
        a=Vector((x,y,z));b=a+Vector((-.07,0,-.105));d=b-a
        bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=.006,depth=d.length,location=(a+b)/2)
        obj=bpy.context.object;obj.rotation_euler=d.to_track_quat('Z','Y').to_euler()
        obj.data.materials.append(MATS['Snow']);PARTS.append(obj)


def canyon():
    base('Sand')
    # One continuous U-shaped cliff; visible inner wall encloses a real dead end.
    ns=112;nz=22;verts=[];faces=[];indices=[]
    for side in (0,1):
        for j in range(nz+1):
            t=j/nz
            for i in range(ns+1):
                a=math.radians(-28)+math.radians(236)*i/ns
                h=.79+.12*math.sin(a*3.3)+.04*math.sin(a*13)
                r=(.47 if side==0 else .84)+.037*math.sin(a*29)+.014*math.sin(a*53+t*3)
                r+=.007*math.sin(t*49+a*5)+.004*math.sin(t*73+a*3)
                r+=.023*math.cos(a*13+t*4)+.006*math.cos(a*79-t*9)
                if t>.93:r+=(.02 if side==0 else -.02)*(t-.93)/.07
                verts.append((r*math.cos(a),r*.78*math.sin(a),.09+h*t))
    stride=ns+1;layer=(nz+1)*stride
    for side in (0,1):
        for j in range(nz):
            for i in range(ns):
                a=side*layer+j*stride+i;face=(a,a+1,a+1+stride,a+stride)
                faces.append(tuple(reversed(face)) if side==0 else face)
                band=(j+int(3*math.sin(i*.045)))%17
                stain=(i%37 in (2,3)) and j<19 and j>4
                indices.append(3 if stain else (2 if band==3 else 1 if band in (7,8,9,10) else 0))
    for i in range(ns):
        a=nz*stride+i;faces.append((a,a+1,a+1+layer,a+layer));indices.append(1)
    for i in (0,ns):
        for j in range(nz):
            a=j*stride+i;faces.append((a,a+stride,a+stride+layer,a+layer));indices.append(0)
    mesh('JointedSandstone',verts,faces,['Sandstone','SandstoneLight','SandstoneDark','Varnish'],indices)
    for i in range(35):
        a=RNG.uniform(-.3,3.5);r=RNG.uniform(.32,.47)
        obj=ellipsoid('Rockfall',(r*math.cos(a),r*.78*math.sin(a),.13),
                      (RNG.uniform(.018,.055),RNG.uniform(.024,.059),RNG.uniform(.026,.06)),'SandstoneDark',1)
        for p in obj.data.polygons:p.use_smooth=False


def flame(x,y,height,width,angle,material,phase):
    dx=math.cos(angle);dy=math.sin(angle);verts=[];steps=15
    for i in range(steps+1):
        t=i/steps
        w=width*(.32+.92*math.sin(t*math.pi)**.75)*(1-t)**.35
        curl=.075*math.sin(t*6+phase)*t+.21*t*t
        cx=x+dx*curl;cy=y+dy*curl
        verts.extend([(cx-dy*w,cy+dx*w,height*t+.13),(cx+dy*w,cy-dx*w,height*t+.13)])
    mesh('FlameTongue',verts,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(steps)],[material])


def fire():
    base()
    for i in range(310):
        x=RNG.uniform(-.8,.8);y=RNG.uniform(-.58,.58)
        if (x/.86)**2+(y/.66)**2>1:continue
        for j in range(3):
            blade(x+RNG.uniform(-.03,.03),y+RNG.uniform(-.03,.03),.12,
                  RNG.uniform(.12,.32) if y<.16 else RNG.uniform(.06,.14),.006,
                  RNG.choice(['Grass','GrassLight']) if y<.16 else 'Char',RNG.random()*math.tau,.08)
    for i in range(19):
        x=-.77+i*.085;y=.03+.1*math.sin(i*1.7);height=RNG.uniform(.47,.96)
        for angle in (0,math.pi/2):
            phase=RNG.uniform(-1,1)
            flame(x,y,height,RNG.uniform(.05,.09),angle,'FlameOrange',phase)
            flame(x,y-.018,height*.72,.043,angle,'FlameGold',phase)
            flame(x,y-.036,height*.38,.021,angle,'FlameCore',phase)


def render(obj,path,focus=(0,0,.65),ortho_scale=2.5):
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.render.resolution_x=1000;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.65
    world=bpy.data.worlds.new('Studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.42,.52,.7,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.45;scene.world=world
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.006))
    floor=bpy.context.object;floor.data.materials.append(MATS['Cloud'])
    for location,power,size in [((2,-3,5),550,4),((-3,1,3),270,3)]:
        light=bpy.data.objects.new('StudioLight',bpy.data.lights.new('StudioLight','AREA'))
        scene.collection.objects.link(light);light.location=location;light.data.energy=power;light.data.size=size
        light.rotation_euler=(Vector((0,0,.5))-light.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera)
    scene.camera=camera;camera.location=(2.2,-3.9,3.0)
    camera.rotation_euler=(Vector(focus)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=ortho_scale
    scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)


def main():
    evidence=json.loads(EVIDENCE.read_text());assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for entry,author in zip(evidence['assets'],(winter,canyon,fire)):
        assert entry['sources'] and entry['render_brief']
        bpy.ops.wm.read_factory_settings(use_empty=True);MATS.clear();PARTS.clear();RNG.seed(8317)
        for name,rgb in PALETTE.items():
            mat=bpy.data.materials.new('M_Trouble_'+name);mat.use_nodes=True
            shader=mat.node_tree.nodes['Principled BSDF'];shader.inputs['Base Color'].default_value=(*rgb,1)
            shader.inputs['Roughness'].default_value=.87
            if name.startswith('Flame'):
                shader.inputs['Emission Color'].default_value=(*rgb,1);shader.inputs['Emission Strength'].default_value=.7
            MATS[name]=mat
        author();bpy.ops.object.select_all(action='DESELECT')
        for part in PARTS:part.select_set(True)
        bpy.context.view_layer.objects.active=PARTS[0];bpy.ops.object.join();obj=bpy.context.object
        obj.name=entry['name'];bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        obj.data.calc_loop_triangles();fbx=OUT/(obj.name+'.fbx');project=OUT/(obj.name+'.blend')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
        bpy.ops.wm.save_as_mainfile(filepath=str(project))
        records.append(dict(name=obj.name,card_id=entry['card_id'],fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
            project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),
            materials=[m.name for m in obj.data.materials]))
        render(obj,OUT/(entry['card_id']+'.png'))
    (OUT/'manifest.json').write_text(json.dumps(dict(evidence_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
        assets=records,material_linear_rgb={'M_Trouble_'+k:v for k,v in PALETTE.items()},visual_review='pending'),indent=2)+'\n')
    print('TROUBLE_LANDSCAPES_AUTHORED',[(r['card_id'],r['triangles']) for r in records],flush=True)


if __name__=='__main__':main()
