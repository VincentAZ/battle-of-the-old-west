"""Author the sourced ox yokes/chains and review the assembled delivery team."""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import create_trouble_landscapes as geo
from create_trouble_objects import box,rod,curve
from create_delivery_wagon import join
OUT=ROOT/'art/western/delivery/hitch-v005'
WAGON=ROOT/'art/western/delivery/wagon-v004'
OX=ROOT/'art/western/delivery/oxen-v002'
EVIDENCE=ROOT/'research/western-presentation/delivery-oxen.json'
PAIR_Y=[-3.5,-6.8]
YOKE_Y=[y-.68*.9 for y in PAIR_Y]
OX_SCALE=.9
CHAIN_FROM=Vector((0,-1.865,.85))
CHAIN_YOKE=Vector((0,.045,1.30))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def yoke():
    # A lighter wagon neck beam with two saddles; dimensions reconstructed
    # around the reviewed animal rather than borrowed from a heavy plow yoke.
    verts=[];n=96
    def beam_top(x):return 1.44+.30*math.exp(-((abs(x)-.75)/.34)**2)
    for i in range(n+1):
        x=-1.25+2.50*i/n
        top=beam_top(x)
        verts += [(x,-.050,top-.11),(x,.050,top-.11),(x,.050,top),(x,-.050,top)]
    faces=[(0,3,2,1),(n*4,n*4+1,n*4+2,n*4+3)]
    faces += [(i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j) for i in range(n) for j in range(4)]
    geo.mesh('NeckBeam',verts,faces,['Wood'],smooth=False)
    for cx in [-.75,.75]:
        width=.40
        pts=[(cx+width,0,beam_top(cx+width)+.06),(cx+width,0,1.04)]
        pts += [(cx+width*math.cos(i*math.pi/32),0,1.04-.40*math.sin(i*math.pi/32)) for i in range(33)]
        pts += [(cx-width,0,beam_top(cx-width)+.06)]
        # Loose bows lean forward below their beam holes; a vertical lower
        # loop catches the advancing foreleg in the full-cycle fit check.
        top=beam_top(cx+width)
        pts=[(x,.18*(z-top)/(top-.64),z) for x,y,z in pts]
        curve('BentBow',pts,.022,'WoodLight')
        for x in [cx-width,cx+width]:
            rod('BowPin',(x,-.08,beam_top(x)+.035),(x,.08,beam_top(x)+.035),.012,'Wood')
    # The keyhole/calabash has a narrow upper slot retaining the draft link.
    points=[(-.027,.045,1.39),(.027,.045,1.39),(.027,.045,1.30)]
    points += [(.090*math.cos(math.pi/2-i*math.tau/40),.045,1.210+.090*math.sin(math.pi/2-i*math.tau/40)) for i in range(41)]
    points += [(-.027,.045,1.30),(-.027,.045,1.39)]
    curve('Calabash',points,.013,'Iron')
    rod('YokeStaple',(0,.045,1.39),(0,.045,1.445),.018,'Iron')
    # Separate front O-ring surrounds the tongue; the lower goose stops it.
    curve('TongueRing',[(.150*math.cos(i*math.tau/64),-.055,1.045+.150*math.sin(i*math.tau/64)) for i in range(65)],.012,'Iron')
    rod('TongueRingHanger',(0,-.055,1.195),(0,-.055,1.43),.014,'Iron')


def chain(name,length):
    start=len(geo.PARTS)
    count=max(2,round(length/.080));step=length/count
    # Long oval iron links alternate through one another. End points are at
    # z=0 and z=length; the moving assembly only adjusts the small end rise.
    half=(step+.020)/2
    for i in range(count):
        z=step*(i+.5);pts=[]
        for j in range(25):
            a=math.tau*j/24;u=.021*math.cos(a);v=half*math.sin(a)
            pts.append((u if i%2==0 else 0,0 if i%2==0 else u,z+v))
        curve('DraftLink',pts,.007,'Iron')
    obj=join(name,geo.PARTS[start:]);geo.PARTS.clear();return obj


def append_project(path,names):
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.objects=[n for n in src.objects if n in names]
    for o in dst.objects:bpy.context.scene.collection.objects.link(o)
    return dst.objects


def bvh(obj,exclude_iron=False):
    deps=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
    verts=[evaluated.matrix_world@v.co for v in mesh.vertices]
    polys=[list(p.vertices) for p in mesh.polygons
           if not exclude_iron or not mesh.materials[p.material_index].name.startswith('M_Delivery_Iron')]
    tree=BVHTree.FromPolygons(verts,polys);evaluated.to_mesh_clear();return tree


def main():
    evidence=json.loads(EVIDENCE.read_text());assert evidence['render_brief']['hitch']
    assert (WAGON/'manifest.json').exists()
    sources={str(p.relative_to(ROOT)):sha(p) for p in [WAGON/'Delivery-Wagon.blend',OX/'Draft-Ox.blend']}
    OUT.mkdir(parents=True,exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
    for name,rgb in {'Wood':(.30,.115,.025),'WoodLight':(.56,.30,.075),'Iron':(.025,.03,.034)}.items():
        m=bpy.data.materials.new('M_Delivery_'+name);m.use_nodes=True
        bsdf=m.node_tree.nodes['Principled BSDF'];bsdf.inputs['Base Color'].default_value=(*rgb,1)
        bsdf.inputs['Roughness'].default_value=.38 if name=='Iron' else .78
        bsdf.inputs['Metallic'].default_value=.8 if name=='Iron' else 0
        geo.MATS[name]=m
    yoke();rear=join('SM_Delivery_OxYoke',list(geo.PARTS));geo.PARTS.clear()
    bob=-.065*OX_SCALE
    back_end=Vector((0,YOKE_Y[0],bob))+CHAIN_YOKE
    front_end=Vector((0,YOKE_Y[1],bob))+CHAIN_YOKE
    chain_lengths={'SM_Delivery_DraftChain':(back_end-CHAIN_FROM).length,
                   'SM_Delivery_TeamChain':(front_end-back_end).length}
    main_chain=chain('SM_Delivery_DraftChain',chain_lengths['SM_Delivery_DraftChain'])
    team_chain=chain('SM_Delivery_TeamChain',chain_lengths['SM_Delivery_TeamChain'])
    records=[]
    for obj in [rear,main_chain,team_chain]:
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        fbx=OUT/(obj.name+'.fbx')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
        records.append(dict(name=obj.name,fbx=fbx.name,sha256=sha(fbx),size_m=list(obj.dimensions),
            materials=[m.name for m in obj.data.materials]))
        if obj.name in chain_lengths:records[-1]['rest_length_m']=chain_lengths[obj.name]
    front=rear.copy();front.data=rear.data;front.name='FrontYoke';bpy.context.scene.collection.objects.link(front)
    for obj,y in zip([rear,front],YOKE_Y):obj.location=(0,y,bob)
    wagon=append_project(WAGON/'Delivery-Wagon.blend',[x['name'] for x in json.loads((WAGON/'manifest.json').read_text())['assets']])
    appended=append_project(OX/'Draft-Ox.blend',['DraftOx','DraftOxArmature'])
    arm=next(x for x in appended if x.type=='ARMATURE');animal=next(x for x in appended if x.type=='MESH')
    arm.animation_data_clear();animals=[];arms=[]
    for pair,y in enumerate(PAIR_Y):
        for side,x in enumerate([-.75,.75]):
            a=arm.copy();a.data=arm.data.copy();a.animation_data_clear();a.name=f'DraftTeam_{pair}_{side}'
            bpy.context.scene.collection.objects.link(a)
            m=animal.copy();m.data=animal.data;m.name=f'Ox_{pair}_{side}';bpy.context.scene.collection.objects.link(m)
            m.parent=a;m.matrix_parent_inverse=Matrix.Identity(4)
            for mod in m.modifiers:
                if mod.type=='ARMATURE':mod.object=a
            a.location=(x-.052734*OX_SCALE,y,0);a.scale=(OX_SCALE,)*3
            arms.append(a);animals.append(m)
    bpy.data.objects.remove(animal,do_unlink=True);bpy.data.objects.remove(arm,do_unlink=True)
    clips=json.loads((OX/'expected-native-poses.json').read_text())['clips']
    def pose(frame,clip='Walk'):
        poses=clips[clip];count=len(poses)-1
        for i,a in enumerate(arms):
            row=poses[(frame+(i%2)*18 if clip=='Walk' else frame)%count]
            for pb in a.pose.bones:
                t=row['bones'][pb.name];x,y,z=t['position'];qx,qy,qz,qw=t['quaternion']
                pb.matrix=Matrix.LocRotScale(Vector((x/100,-y/100,z/100)),Quaternion((qw,-qx,qy,-qz)),Vector(t['scale']))
                bpy.context.view_layer.update()
        z=(poses[frame%count]['bones']['Body']['position'][2]/100-1.5)*OX_SCALE
        rear.location.z=front.location.z=z
        end=Vector((0,YOKE_Y[0],z))+CHAIN_YOKE;lead=Vector((0,YOKE_Y[1],z))+CHAIN_YOKE
        for obj,start,finish in [(main_chain,CHAIN_FROM,end),(team_chain,end,lead)]:
            direction=finish-start;obj.location=start;obj.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
            base_length=chain_lengths[obj.name]
            obj.scale=(1,1,direction.length/base_length)
        bpy.context.view_layer.update()
    checks=[]
    wagon_trees=[bvh(o) for o in wagon]
    wagon_noniron_trees=[bvh(o,exclude_iron=True) for o in wagon]
    for clip in ['Walk','Idle']:
        for frame in range(len(clips[clip])-1):
            pose(frame,clip)
            animal_trees=[bvh(o) for o in animals]
            yoke_trees=[bvh(rear),bvh(front)]
            chain_trees=[bvh(main_chain),bvh(team_chain)]
            checks.append(dict(clip=clip,frame=frame,
                yoke_animal_triangle_overlaps=[len(t.overlap(yoke_trees[i//2])) for i,t in enumerate(animal_trees)],
                animal_wagon_triangle_overlaps=[sum(len(t.overlap(w)) for w in wagon_trees) for t in animal_trees],
                chain_animal_triangle_overlaps=[sum(len(t.overlap(c)) for c in chain_trees) for t in animal_trees],
                chain_noniron_wagon_triangle_overlaps=[sum(len(t.overlap(w)) for w in wagon_noniron_trees) for t in chain_trees],
                animal_pair_triangle_overlaps=[len(animal_trees[i].overlap(animal_trees[j])) for i in range(4) for j in range(i+1,4)],
                rear_yoke_wagon_triangle_overlaps=sum(len(yoke_trees[0].overlap(w)) for w in wagon_trees)))
    (OUT/'clearance-study.json').write_text(json.dumps(checks,indent=2)+'\n')
    print('DELIVERY_HITCH_CLEARANCES '+json.dumps({key:max(max(row[key]) if isinstance(row[key],list) else row[key] for row in checks)
          for key in checks[0] if key not in ['clip','frame']}),flush=True)
    pose(0)
    project=OUT/'Delivery-Team.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    scene.world=bpy.data.worlds.new('TeamReview');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.72,1,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.01));floor=bpy.context.object
    mat=bpy.data.materials.new('TeamReviewGround');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.18,.22,.28,1)
    floor.data.materials.append(mat)
    for pos,power,size in [((5,-5,7),2000,6),((-5,-2,6),1200,5),((2,5,6),1600,5)]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size
        o.rotation_euler=(Vector((0,-3,1))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
    shots=[('team-quarter',(8,-11,7),(0,-3,1),12,0),('team-side',(12,-3,4),(0,-3,1),12,9),
        ('hitch-front',(4,-7,3),(0,-4,1.1),4.6,0),('hitch-rear',(4,-1,2.8),(0,-3.3,1),5.5,18)]
    for name,pos,target,scale,frame in shots:
        pose(frame);camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    assert all(sha(ROOT/p)==h for p,h in sources.items())
    (OUT/'clearance-study.json').write_text(json.dumps(checks,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(dict(assets=records,sources=sources,project_sha256=sha(project),evidence_sha256=sha(EVIDENCE),
        author_sha256=sha(Path(__file__)),animal_scale=OX_SCALE,pair_body_y=PAIR_Y,yoke_y=YOKE_Y,
        material_linear_rgb={m.name:list(m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3]) for m in geo.MATS.values()},
        chain_from=list(CHAIN_FROM),chain_yoke_local=list(CHAIN_YOKE),visual_review='pending'),indent=2)+'\n')
    print('DELIVERY_HITCH_AUTHORED',flush=True)


if __name__=='__main__':main()
