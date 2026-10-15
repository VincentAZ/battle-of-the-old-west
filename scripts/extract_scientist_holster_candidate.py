"""Read an isolated CPU candidate without saving it; retain exact pose channels."""
import argparse,hashlib,json,math,os,sys,traceback
from pathlib import Path
import bpy

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=a.source.resolve()
    path=folder/'Scientist_Holster_Candidate.blend';output=folder/'pose-and-rifle-samples.json'
    assert not output.exists();sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
    before=sha(path);bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
    arm=bpy.data.objects['Survivor_Rig'];rifle=bpy.data.objects['ActualNativeRifle_CPUReference'];scene=bpy.context.scene
    rows=[];steps=[];previous={}
    for frame in range(1,92):
        scene.frame_set(frame);bpy.context.view_layer.update()
        for bone in arm.pose.bones:
            q=bone.rotation_quaternion.normalized()
            if bone.name in previous:
                dot=max(-1.,min(1.,abs(float(q.dot(previous[bone.name])))))
                steps.append({'frame_from':frame-1,'frame_to':frame,'bone':bone.name,'degrees':math.degrees(2*math.acos(dot))})
            previous[bone.name]=q.copy()
        rows.append({'frame':frame,'seconds':(frame-1)/30,'rifle_held':frame<=65,
            'rifle_matrix_m':[list(row) for row in rifle.matrix_world],
            'bones':{b.name:{'location':list(b.location),'rotation_xyzw':[b.rotation_quaternion.x,b.rotation_quaternion.y,b.rotation_quaternion.z,b.rotation_quaternion.w],'scale':list(b.scale)} for b in arm.pose.bones}})
    assert sha(path)==before
    output.write_text(json.dumps(rows,indent=2)+'\n')
    (folder/'pose-extraction.json').write_text(json.dumps({'source':str(path),'source_sha256':before,'source_unchanged':True,
        'rows':len(rows),'bones_per_row':len(rows[0]['bones']),'extractor_sha256':sha(__file__),
        'largest_adjacent_local_rotations':sorted(steps,key=lambda r:r['degrees'],reverse=True)[:30]},indent=2)+'\n')
    print('SCIENTIST_CANDIDATE_EXTRACTED',flush=True)
try:main();code=0
except BaseException:traceback.print_exc();code=1
sys.stdout.flush();sys.stderr.flush();os._exit(code)
