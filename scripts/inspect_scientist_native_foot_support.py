"""Read-only CPU source-mesh evaluation at a recorded imported native pose.

The result measures source shoe vertices in the real Body frame. It does not
invent terrain contact heights; those require native ground traces at the feet.
"""
import argparse
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scientist_import_contract import ROOT,require,sha

p=argparse.ArgumentParser();p.add_argument('--pose',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
require(not args.output.exists(),'Preserve previous support measurement')
source=ROOT/'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend';before=sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
arm=bpy.data.objects['Survivor_Rig'];arm.animation_data_clear()
poses=json.loads(args.pose.read_text())
for bone in arm.pose.bones:
    value=poses[bone.name.removeprefix('mixamorig:')];x,y,z=value['position'];qx,qy,qz,qw=value['quaternion_xyzw']
    bone.matrix=Matrix.LocRotScale(Vector((x/100,-y/100,z/100)),Quaternion((qw,-qx,qy,-qz)),Vector(value['scale']))
bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
rows=[]
for obj in bpy.data.objects:
    if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
    evaluated=obj.evaluated_get(dg);mesh=evaluated.to_mesh()
    for side in ('Left','Right'):
        allowed={f'mixamorig:{side}{n}' for n in ('Foot','ToeBase','Leg')}
        indices=[v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if obj.vertex_groups[g.group].name in allowed)>.9]
        if not indices:continue
        points=[evaluated.matrix_world@mesh.vertices[i].co for i in indices]
        point=min(points,key=lambda v:v.z)
        rows.append({'object':obj.name,'side':side,'vertices':len(indices),
                     'lowest_source_skinned_body_cm':[100*point.x,-100*point.y,100*point.z]})
    evaluated.to_mesh_clear()
require(rows and sha(source)==before,'Source changed or no foot geometry')
out={'status':'CPU native-pose source-geometry measurement; native terrain support unmeasured',
     'source':str(source),'source_sha256':before,'pose':str(args.pose),'pose_sha256':sha(args.pose),
     'script_sha256':sha(__file__),'original_unchanged':True,'foot_geometry':rows,
     'limits':['Uses original imported costume source mesh and accepted native interpolated bone pose.',
               'No GPU skin readback or native terrain line trace; world support must use actual Body transform and measured terrain heights.']}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
print('SCIENTIST_FOOT_SUPPORT '+json.dumps(rows),flush=True)
