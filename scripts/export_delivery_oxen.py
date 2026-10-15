"""Export the separate draft-ox study; source, approved longhorn and prior clips stay intact."""
import hashlib,json
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/delivery/oxen-v002'
SOURCE=OUT/'Draft-Ox.blend'
before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
review=json.loads((OUT/'visual-review.json').read_text())
assert review['status']=='accepted_for_hitch_and_native_study' and review['project_sha256']==before
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
arm=next(o for o in scene.objects if o.type=='ARMATURE')
arm.name='Armature'
mesh=bpy.data.objects['DraftOx']
assert len(mesh.data.materials)==1
def native_transform(matrix):
    p,q,s=matrix.decompose()
    return {'position':[p.x*100,-p.y*100,p.z*100], 'quaternion':[-q.x,q.y,-q.z,q.w], 'scale':list(s)}
expected={'source_sha256':before,'bones':[b.name for b in arm.data.bones],'clips':{}}
for clip,end in [('Idle',90),('Walk',36)]:
    arm.animation_data.action=bpy.data.actions['DraftOx_'+clip]
    rows=[]
    for frame in range(end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        rows.append({'frame':frame,'seconds':frame/30,'bones':{b.name:native_transform(b.matrix) for b in arm.pose.bones}})
    expected['clips'][clip]=rows
(OUT/'expected-native-poses.json').write_text(json.dumps(expected,separators=(',',':'))+'\n')
arm.animation_data.action=None
for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
for obj in [arm,mesh]:
    assert all(abs(v-1)<1e-6 for v in obj.scale)
    obj.data.transform(Matrix.Scale(100,4))
    obj.location*=100
    matrix=obj.matrix_parent_inverse.copy();matrix.translation*=100;obj.matrix_parent_inverse=matrix
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path.endswith('.location'):
                        for key in curve.keyframe_points:
                            key.co.y*=100;key.handle_left.y*=100;key.handle_right.y*=100
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
scene.render.fps=30
bpy.context.view_layer.update()
dest=OUT/'exports';dest.mkdir(exist_ok=True)
common=dict(use_selection=True,add_leaf_bones=False,use_armature_deform_only=True,
            use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
            path_mode='RELATIVE')
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(dest/'SK_DraftOx.fbx'),object_types={'ARMATURE','MESH'},bake_anim=False,**common)
mesh.select_set(False)
for name,end in [('Idle',90),('Walk',36)]:
    arm.animation_data.action=bpy.data.actions['DraftOx_'+name]
    scene.frame_start=0;scene.frame_end=end;scene.frame_set(0)
    bpy.ops.export_scene.fbx(filepath=str(dest/('A_DraftOx_'+name+'.fbx')),object_types={'ARMATURE'},
        bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_use_all_bones=True,bake_anim_force_startend_keying=True,bake_anim_simplify_factor=0,
        bake_anim_step=1,**common)
textures=ROOT/'art/western/stampede/review-v001/review/textures'
import shutil
for path in textures.glob('*.png'):shutil.copy2(path,dest/path.name.replace('Longhorn','DraftOx'))
report={'source_project_sha256':before,'units':'centimeters','object_scale':list(arm.scale),
        'fbx_axes':{'forward':'-Y','up':'Z'},'sample_rate':30,'root_motion':False,
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.iterdir()) if p.is_file()}}
assert before==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
(OUT/'export-settings.json').write_text(json.dumps(report,indent=2)+'\n')
print('DELIVERY_OXEN_EXPORTED',json.dumps(report),flush=True)
