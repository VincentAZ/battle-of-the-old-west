"""Temporary rendered torso/arm stress pose, never saved into approved project."""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Matrix,Euler
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug
record=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug]
bpy.ops.wm.open_mainfile(filepath=str(out/(record['asset_name']+'-Rigged.blend')),use_scripts=False)
a=bpy.data.objects['Armature'];frozen=set(json.loads((out/'rig-validation.json').read_text())['freeze_bones'])
changes={'Spine':(0,0,12),'Spine2':(10,0,-15),'RightArm':(0,0,40)}
if slug in ('trail-organizer','wild-bill-hickok'):changes.update(RightArm=(0,0,65),RightForeArm=(0,-30,0),RightHand=(0,0,-15))
if slug=='sharpshooter':changes.update(LeftArm=(0,0,-65),LeftForeArm=(0,30,0),LeftHand=(0,0,15))
if slug=='laudanum-doctor':changes.update(LeftArm=(0,0,-35),LeftForeArm=(0,20,0),LeftHand=(0,0,10))
for n,angles in changes.items():
 if n in frozen:continue
 a.pose.bones[n].rotation_quaternion=Euler([math.radians(v) for v in angles]).to_quaternion()
bpy.context.view_layer.update();scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100;scene.cycles.samples=24
for view in ('rear','three-quarter'):
 scene.camera=bpy.data.objects['Review_'+view];scene.render.filepath=str(out/'rig-mask-qa'/('stress-'+view+'.png'));bpy.ops.render.render(write_still=True)
