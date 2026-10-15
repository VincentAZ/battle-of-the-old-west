"""CPU triangle crossings at quarter frames on the actual imported costume source.

Compares native baseline local-key interpolation with the isolated candidate.
Open coat surfaces make signed containment ambiguous; actual triangle crossing
counts and rendered views are retained instead of a fictional zero-overlap rule.
"""
import argparse,hashlib,json,math,os,sys,traceback
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit_scientist_native_contacts as audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.source.resolve()
    output=source/'cloth-subframe-audit.json';assert not output.exists()
    path=source/'Scientist_Holster_Candidate.blend';before=hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
    arm=bpy.data.objects['Survivor_Rig'];body=bpy.data.objects['Survivor_Body'];coat=bpy.data.objects['Scientist_Outfit_Assembly']
    hand_groups={g.index for g in body.vertex_groups if g.name.startswith('mixamorig:LeftHand')}
    hand_vertices={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in hand_groups)>.65}
    hand_faces=[list(p.vertices) for p in body.data.polygons if all(i in hand_vertices for i in p.vertices)]
    assert hand_vertices and hand_faces
    frames=sorted(set([float(f) for f in range(1,92)]+[1+i/4 for i in range(360)]))
    ref=audit.Reference();results={};max_baseline_position_error=0.;max_baseline_angle_error=0.
    for mode in ('candidate','native_baseline'):
        samples=[]
        for frame in frames:
            bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
            if mode=='native_baseline':
                expected=ref.pose('Holster',(frame-1)/30)
                for bone in arm.pose.bones:
                    xyz,q,s=expected[bone.name.removeprefix('mixamorig:')]
                    bone.matrix=Matrix.LocRotScale(Vector((xyz[0]/100,-xyz[1]/100,xyz[2]/100)),
                        Quaternion((q[3],-q[0],q[1],-q[2])),Vector(s))
                    # Matrix assignment converts through the evaluated parent.
                    # Update each parent before assigning its child's absolute
                    # matrix; a single final update leaves stale parent frames.
                    bpy.context.view_layer.update()
            bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
            if mode=='native_baseline':
                for name in audit.BONES:
                    bone=arm.pose.bones['root' if name=='root' else 'mixamorig:'+name]
                    p,q,s=bone.matrix.decompose()
                    cm,angle,_=audit.distance(([p.x*100,-p.y*100,p.z*100],audit.unit([-q.x,q.y,-q.z,q.w]),list(s)),expected[name])
                    max_baseline_position_error=max(max_baseline_position_error,cm)
                    max_baseline_angle_error=max(max_baseline_angle_error,angle)
                assert max_baseline_position_error<.01 and max_baseline_angle_error<.05,(max_baseline_position_error,max_baseline_angle_error)
            b=body.evaluated_get(deps);bm=b.to_mesh();points=[b.matrix_world@v.co for v in bm.vertices]
            c=coat.evaluated_get(deps);cm=c.to_mesh();cp=[c.matrix_world@v.co for v in cm.vertices]
            hand_tree=BVHTree.FromPolygons(points,hand_faces)
            coat_faces=[list(p.vertices) for p in cm.polygons]
            coat_tree=BVHTree.FromPolygons(cp,coat_faces);overlaps=hand_tree.overlap(coat_tree)
            affected={v for face,_ in overlaps for v in hand_faces[face]}
            distances=[]
            for i in affected:
                location,normal,_,distance=coat_tree.find_nearest(points[i])
                if location is not None:distances.append(distance*100)
            samples.append({'frame':frame,'seconds':(frame-1)/30,'hand_coat_triangle_crossings':len(overlaps),
                'affected_skin_vertices':len(affected),'maximum_crossing_vertex_nearest_surface_cm':max(distances,default=0.)})
            b.to_mesh_clear();c.to_mesh_clear()
        results[mode]={'samples':samples,'frames_with_crossing':sum(s['hand_coat_triangle_crossings']>0 for s in samples),
                       'maximum_crossing_pairs':max(s['hand_coat_triangle_crossings'] for s in samples)}
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    output.write_text(json.dumps({'status':'CPU triangle diagnostic; actual images required','source':str(path),
        'source_sha256':before,'source_unchanged':True,'sample_count_per_mode':len(frames),'body_object':body.name,
        'coat_object':coat.name,'hand_vertices':len(hand_vertices),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'maximum_baseline_bone_position_cm':max_baseline_position_error,'maximum_baseline_bone_angle_degrees':max_baseline_angle_error,
        'source_costume':str(audit.ROOT/'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend'),
        'results':results,'limitations':['Only left hand skin crossing coat triangles; adjacent cuffs may legitimately touch.',
            'Not native GPU skin, cloth simulation, whole-body collision or visual acceptance.']},indent=2)+'\n')
    print('SCIENTIST_CLOTH_SUBFRAME_AUDIT '+json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='samples'} for k,v in results.items()}),flush=True)
try:main();code=0
except BaseException:traceback.print_exc();code=1
sys.stdout.flush();sys.stderr.flush();os._exit(code)
