"""Stress-check locally weighted Doctor feet without editing the saved rig."""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/crew/playable-v001/laudanum-doctor'
project=OUT/'LaudanumDoctor-Rigged.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
obj=bpy.data.objects['laudanum_doctor_Appearance_Review'];arm=bpy.data.objects['Armature']
positions=[obj.matrix_world@v.co for v in obj.data.vertices]
shoe={side:[i for i,p in enumerate(positions) if p.x*sign>0 and p.z<.10] for side,sign in [('Left',1),('Right',-1)]}
results=[]
for angle in [-25,0,25]:
    for side in shoe:
        bone=arm.pose.bones[side+'Foot'];bone.rotation_mode='XYZ';bone.rotation_euler.x=math.radians(angle)
    bpy.context.view_layer.update()
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    max_error=0
    for side,indices in shoe.items():
        transform=arm.matrix_world@arm.pose.bones[side+'Foot'].matrix@arm.data.bones[side+'Foot'].matrix_local.inverted()@arm.matrix_world.inverted()
        for i in indices:
            expected=transform@positions[i];actual=obj.matrix_world@mesh.vertices[i].co
            max_error=max(max_error,(actual-expected).length)
    assert max_error<1e-5,max_error
    ev.to_mesh_clear();results.append({'foot_pitch_degrees':angle,'rigid_boot_max_error_m':max_error})
    if angle:
        cam_data=bpy.data.cameras.new('DoctorFootDiagnostic');cam=bpy.data.objects.new('DoctorFootDiagnostic',cam_data);bpy.context.scene.collection.objects.link(cam)
        cam.location=(-.85,-1.6,.45);target=Vector((0,0,.16));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam_data.type='ORTHO';cam_data.ortho_scale=.8
        scene=bpy.context.scene;scene.camera=cam;scene.render.resolution_x=800;scene.render.resolution_y=600;scene.render.resolution_percentage=100
        scene.render.filepath=str(OUT/f'foot-stress-{angle}.png');bpy.ops.render.render(write_still=True)
report={'status':'passed','project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),'rigid_boot_vertices':{k:len(v) for k,v in shoe.items()},'poses':results,'note':'Static boot rigidity and ankle deformation stress; Unreal gait/floor-contact review remains required.'}
(OUT/'foot-stress-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
