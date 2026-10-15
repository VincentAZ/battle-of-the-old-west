"""Stage only corrected Holster/Unholster FBXs; preserve props and live assets.

Uses the exact reviewed candidate pose samples. The reverse clip keeps the
existing 91-frame/3-second timing, rifle path, grip transition and endpoints.
No native importer or Content writer is invoked.
"""
import argparse,ast,copy,hashlib,json,os,sys,traceback
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/scientist_gesture'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def activate(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
def convert(matrix):
    p,q,s=matrix.decompose()
    return {'translation_cm':[100*p.x,-100*p.y,100*p.z],'rotation_xyzw':[-q.x,q.y,-q.z,q.w],'scale':list(s)}
def main():
    global arm,scene  # The retained authoring export helper uses these bindings.
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=a.source.resolve()
    review=json.loads((folder/'manual-review.json').read_text())
    assert review['accepted_for_native_candidate_validation']
    source=folder/'Scientist_Holster_Candidate.blend';original=BASE/'holster-v3/runtime-integration-contract.json'
    old=json.loads(original.read_text());forward=json.loads((folder/'pose-and-rifle-samples.json').read_text())
    baseline=json.loads((BASE/'holster-v3/pose-and-rifle-samples.json').read_text())
    assert len(forward)==len(baseline)==91
    protected={str(p):sha(p) for directory in (BASE/'holster-v3',ROOT/'game/OldWest/Content') for p in directory.rglob('*') if p.is_file()}
    protected[str(source)]=sha(source)
    modified={'mixamorig:LeftArm','mixamorig:LeftForeArm','mixamorig:LeftHand'}
    for i,(row,prev) in enumerate(zip(forward,baseline)):
        assert set(row['bones'])==set(prev['bones']) and len(row['bones'])==53
        assert row['frame']==prev['frame']==i+1 and row['rifle_held']==prev['rifle_held']
        assert max(abs(x-y) for a,b in zip(row['rifle_matrix_m'],prev['rifle_matrix_m']) for x,y in zip(a,b))<1e-6
        for name,data in row['bones'].items():
            if name in modified and i not in (0,90):continue
            ref=prev['bones'][name]
            assert max(abs(x-y) for field in ('location','scale') for x,y in zip(data[field],ref[field]))<1e-6
            aq=Quaternion((data['rotation_xyzw'][3],*data['rotation_xyzw'][:3])).normalized()
            bq=Quaternion((ref['rotation_xyzw'][3],*ref['rotation_xyzw'][:3])).normalized()
            assert abs(aq.dot(bq))>1-1e-6
    reverse=[]
    for i,row in enumerate(reversed(forward),1):
        row=copy.deepcopy(row);row['source_holster_frame']=row['frame'];row['frame']=i;row['seconds']=(i-1)/30;reverse.append(row)
    tree=ast.parse((ROOT/'scripts/author_scientist_decision_branches.py').read_text())
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_animation'],type_ignores=[]),'animation-export-helper','exec'),globals())
    exports=[];dense={}
    for name,rows in [('Holster',forward),('Unholster',reverse)]:
        assert not (folder/f'A_Scientist_{name}_Cm.fbx').exists()
        bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
        arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene;rifle=bpy.data.objects['ActualNativeRifle_CPUReference']
        for obj in bpy.data.objects:obj.animation_data_clear()
        for action in list(bpy.data.actions):bpy.data.actions.remove(action)
        expected=[]
        for row in rows:
            for bone_name,data in row['bones'].items():
                bone=arm.pose.bones[bone_name];bone.rotation_mode='QUATERNION';bone.location=data['location'];bone.scale=data['scale']
                x,y,z,w=data['rotation_xyzw'];bone.rotation_quaternion=Quaternion((w,x,y,z))
                for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=row['frame'])
            rifle.matrix_world=Matrix(row['rifle_matrix_m']);rifle.rotation_mode='QUATERNION'
            for channel in ('location','rotation_quaternion','scale'):rifle.keyframe_insert(channel,frame=row['frame'])
            scene.frame_set(row['frame']);bpy.context.view_layer.update()
            expected.append({'frame':row['frame'],'seconds':row['seconds'],'rifle_held':row['rifle_held'],
                'rifle_body_relative':convert(rifle.matrix_world),
                'bones':{b.name.removeprefix('mixamorig:'):convert(arm.matrix_world@b.matrix) for b in arm.pose.bones}})
        dense[name]=expected
        if name=='Unholster':
            scene.frame_start=1;scene.frame_end=91;scene.frame_set(1)
            bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Scientist_Unholster_Candidate.blend'))
        exports.append(export_animation(name,rows,folder))
    assert all(sha(p)==h for p,h in protected.items())
    contract=copy.deepcopy(old)
    contract.update({'status':'isolated two-animation replacement candidate; native import and visual review required',
        'source_blend':str(source),'source_blend_sha256':sha(source),
        'previous_contract':str(original),'previous_contract_sha256':sha(original),
        'clips':[dict(e,asset='/Game/Art/Survivors/ScientistAnalysis/Animations/'+Path(e['path']).stem) for e in exports],
        'dense_expected_native_samples':dense,
        'replacement_scope':{'assets':[e['asset'] for e in [dict(e,asset='/Game/Art/Survivors/ScientistAnalysis/Animations/'+Path(e['path']).stem) for e in exports]],
            'other_11_clips_unchanged':True,'all_11_props_unchanged':True,'rifle_dense_path_unchanged':True,
            'all_body_channels_except_left_arm_chain_unchanged':True,'endpoints_unchanged':True,
            'runtime_prop_data_requires_change':False,'protected_existing_files':len(protected),'protected_existing_files_unchanged':True},
        'review':review})
    (folder/'runtime-integration-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    (folder/'pose-and-rifle-samples-unholster.json').write_text(json.dumps(reverse,indent=2)+'\n')
    print('SCIENTIST_TWO_ANIMATION_REPLACEMENT_STAGED '+json.dumps({'clips':2,'props_exported':0,'originals_unchanged':True}),flush=True)
try:main();code=0
except BaseException:traceback.print_exc();code=1
sys.stdout.flush();sys.stderr.flush();os._exit(code)
