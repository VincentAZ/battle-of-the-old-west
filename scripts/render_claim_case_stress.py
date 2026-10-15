"""Render corrected rigid map case and blended coat boundary under torso twist."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Euler
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/crew/playable-v001/claim-jumper'
project=OUT/'ClaimJumper-Rigged.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
arm=bpy.data.objects['Armature']
arm.pose.bones['Spine'].rotation_quaternion=Euler((0,0,math.radians(12))).to_quaternion()
arm.pose.bones['Spine2'].rotation_quaternion=Euler((math.radians(10),0,math.radians(-25))).to_quaternion()
scene=bpy.context.scene;scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100;scene.cycles.samples=24
for view in ('rear','side'):
    scene.camera=bpy.data.objects['Review_'+view];scene.render.filepath=str(OUT/'rig-mask-qa'/('case-stress-'+view+'.png'));bpy.ops.render.render(write_still=True)
print('Stress renders complete; source unchanged',hashlib.sha256(project.read_bytes()).hexdigest())
