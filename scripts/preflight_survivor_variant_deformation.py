"""CPU manually posed garment studies, explicitly not native motion proof.

Only creates PNG/JSON evidence. It never saves .blend, FBX or Unreal assets.
"""
import argparse
import hashlib
import sys
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--base',type=Path,default=ROOT/'art/characters/survivor_variants')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
BASE=args.base.resolve()
OUT=BASE/'deformation-preflight';OUT.mkdir(exist_ok=True)
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*/*.blend')}
protected.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*/*.fbx')})
records=[]


def aim(arm,name,direction):
    bone=arm.pose.bones['mixamorig:'+name]
    location=bone.head.copy()
    rest=bone.bone.matrix_local
    q=(bone.bone.tail_local-bone.bone.head_local).normalized().rotation_difference(Vector(direction).normalized())
    bone.matrix=Matrix.Translation(location)@q.to_matrix().to_4x4()@rest.to_3x3().to_4x4()
    bpy.context.view_layer.update()


for card,name in [('prospector','Prospector'),('gatling_gunner','Gatling Gunner'),('bounty_hunter','Bounty Hunter')]:
    bpy.ops.wm.open_mainfile(filepath=str(BASE/card/(name+'.blend')),use_scripts=False)
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=40;scene.cycles.use_denoising=True
    if hasattr(scene.cycles,'denoising_use_gpu'):scene.cycles.denoising_use_gpu=False
    scene.render.resolution_x=1100;scene.render.resolution_y=1250;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('CPU_Deformation_Study');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.16,.18,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.32));floor=bpy.context.object
    mat=bpy.data.materials.new('Study_ground');mat.use_nodes=True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.025,.034,.038,1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;floor.data.materials.append(mat)
    for label,p,energy,size,color in [('Key',(-3,-4,5),650,4,(1,.86,.69)),('Fill',(3,-2,3),350,3,(.58,.79,1)),('Rim',(1,3,4),850,3,(.81,.93,1))]:
        data=bpy.data.lights.new(label,'AREA');data.energy=energy;data.shape='DISK';data.size=size;data.color=color
        obj=bpy.data.objects.new(label,data);bpy.context.collection.objects.link(obj);obj.location=p
        obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('CPU_Study_Camera');camera=bpy.data.objects.new('CPU_Study_Camera',data);bpy.context.collection.objects.link(camera)
    scene.camera=camera;data.lens=68
    for pose in ['raised-rifle-arms','split-stride-deep-knee']:
        for bone in arm.pose.bones:bone.matrix_basis.identity()
        bpy.context.view_layer.update()
        if pose=='split-stride-deep-knee':
            hips=arm.pose.bones['mixamorig:Hips'];matrix=hips.matrix.copy();matrix.translation+=Vector((0,-.03,-.24));hips.matrix=matrix
            bpy.context.view_layer.update()
            aim(arm,'Spine2',(0,-.24,1))
            aim(arm,'LeftUpLeg',(.05,-.76,-.68));aim(arm,'LeftLeg',(.08,.62,-.79))
            aim(arm,'RightUpLeg',(-.04,.39,-.92));aim(arm,'RightLeg',(-.05,-.66,-.75))
        aim(arm,'LeftArm',(.15,-.12,-.06));aim(arm,'LeftForeArm',(-.12,-.16,.04))
        aim(arm,'RightArm',(-.13,-.13,-.08));aim(arm,'RightForeArm',(.10,-.19,.04))
        bpy.context.view_layer.update()
        record={'card_id':card,'study_pose':pose,'kind':'manual CPU posed study, not a native animation capture',
                'source_blend_sha256':protected[str(BASE/card/(name+'.blend'))],
                'bone_matrices':{b.name:[[float(v) for v in row] for row in b.matrix] for b in arm.pose.bones},'renders':[]}
        for view,position in [('three-quarter',(-3,-4,2.1)),('back',(2.7,4.0,2.05))]:
            camera.location=position;camera.rotation_euler=(Vector((0,0,.83))-camera.location).to_track_quat('-Z','Y').to_euler()
            path=OUT/(card+'-'+pose+'-'+view+'.png');scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            record['renders'].append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        records.append(record)
        (OUT/'evidence.json').write_text(json.dumps({'status':'rendering','studies':records},indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
(OUT/'evidence.json').write_text(json.dumps({'status':'rendered_manual_review_pending','studies':records,
    'source_blend_fbx_unchanged':True,'protected_sha256':protected,
    'limitations':['These are authored approximate joint poses, not imported game animation clips.','Ground contact and hand-to-weapon alignment are not under test.','No asset or runtime source changes were applied.']},indent=2)+'\n')
print('CPU_VARIANT_DEFORMATION_STUDIES_COMPLETE',len(records),flush=True)
