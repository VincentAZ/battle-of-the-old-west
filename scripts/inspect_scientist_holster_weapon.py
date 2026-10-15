"""CPU-only actual rifle versus forearm/garment surface intersection audit."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils.bvhtree import BVHTree

parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--include-hands',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);source=args.source.resolve()
path=source/'Scientist_Holster_Candidate.blend';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=sha(path)
bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
rifle=bpy.data.objects['ActualNativeRifle_CPUReference'];objects=[]
for name in ('Survivor_Body','Scientist_Outfit_Assembly'):
    obj=bpy.data.objects[name]
    for side in ('Right','Left'):
        groups={g.index for g in obj.vertex_groups if g.name in ('mixamorig:'+side+'Arm','mixamorig:'+side+'ForeArm')}
        indices={v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>.65}
        faces=[list(p.vertices) for p in obj.data.polygons if all(i in indices for i in p.vertices)]
        assert indices and faces
        objects.append((obj,side,indices,faces))
    if args.include_hands and name=='Survivor_Body':
        for side in ('Right','Left'):
            groups={g.index for g in obj.vertex_groups if g.name.startswith('mixamorig:'+side+'Hand')}
            indices={v.index for v in obj.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>.65}
            faces=[list(p.vertices) for p in obj.data.polygons if all(i in indices for i in p.vertices)]
            assert indices and faces
            objects.append((obj,side+'Hand',indices,faces))
rows=[]
for frame in range(1,bpy.context.scene.frame_end+1):
    bpy.context.scene.frame_set(frame);deps=bpy.context.evaluated_depsgraph_get()
    gun_vertices=[rifle.matrix_world@v.co for v in rifle.data.vertices]
    gun_tree=BVHTree.FromPolygons(gun_vertices,[list(p.vertices) for p in rifle.data.polygons])
    row={'frame':frame,'seconds':(frame-1)/30,'parts':[]}
    for obj,side,indices,faces in objects:
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
        points=[evaluated.matrix_world@v.co for v in mesh.vertices];evaluated.to_mesh_clear()
        tree=BVHTree.FromPolygons(points,faces);overlaps=tree.overlap(gun_tree)
        depths=[]
        if overlaps:
            # Inspect only vertices of actual intersecting triangles. Distant
            # points can lie behind an open rifle surface normal and are not
            # penetration evidence for this non-convex, open mesh.
            affected={index for own,_ in overlaps for index in faces[own]}
            for i in affected:
                location,normal,_,distance=gun_tree.find_nearest(points[i])
                if location is not None and distance<.05 and (points[i]-location).dot(normal)<-.0001:depths.append(distance*100)
        row['parts'].append({'mesh':obj.name,'side':side,'triangle_overlap_count':len(overlaps),
                             'inside_signed_nearest_count':len(depths),'maximum_signed_nearest_depth_cm':max(depths,default=0)})
    rows.append(row)
assert sha(path)==before
(source/'rifle-forearm-surface-audit.json').write_text(json.dumps({'status':'CPU_surface_diagnostic_requires_actual_view',
    'source_blend_sha256':before,'source_unchanged':True,'frames':len(rows),
    'method':'Actual deformed vertices, weight>0.65 in arm/forearm groups; triangle-surface BVH overlaps against actual imported rifle. Hands excluded. Signed closest-surface values are diagnostic on this non-convex rifle.',
    'samples':rows},indent=2)+'\n')
print('SCIENTIST_RIFLE_FOREARM_AUDIT_COMPLETE',flush=True)
