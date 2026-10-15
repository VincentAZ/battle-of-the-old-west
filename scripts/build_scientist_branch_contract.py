"""Read-only extraction of exact decision-branch native import expectations."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Quaternion, Vector

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/scientist_gesture'
CORE=BASE/'candidate-v11'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
core=json.loads((CORE/'runtime-integration-contract.json').read_text())
sources={'SortLeft':BASE/'decision-branches-v3/SortLeft',
         'SortRight':BASE/'decision-branches-v2/SortRight',
         'SkipRecover':BASE/'decision-branches-v2/SkipRecover',
         'WorkHold':BASE/'decision-branches-v2/WorkHold'}
names=list(core['dense_expected_native_samples'][0]['bones'])

def convert(matrix):
    p,q,s=matrix.decompose()
    return {'translation_cm':[p.x*100,-p.y*100,p.z*100],
            'rotation_xyzw':[-q.x,q.y,-q.z,q.w],'scale':list(s)}
def difference(a,b):
    pa,pb=Vector(a['translation_cm']),Vector(b['translation_cm'])
    qa,qb=[Quaternion((x['rotation_xyzw'][3],*x['rotation_xyzw'][:3])).normalized() for x in (a,b)]
    return (pa-pb).length,math.degrees(2*math.acos(min(1,abs(qa.dot(qb)))))

reports=[]
for name,directory in sources.items():
    manifest=json.loads((directory/'manifest.json').read_text());path=Path(manifest['blend']);before=sha(path)
    audit=json.loads((directory/'skin-contact-audit.json').read_text())
    assert audit['source_sha256']==before and audit['all_authored_30hz_frames'] and audit['source_unchanged']
    samples=json.loads((directory/'pose-and-prop-samples.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
    arm=bpy.data.objects['Survivor_Rig'];frames=[]
    for row in samples:
        bpy.context.scene.frame_set(row['frame'])
        frames.append({'frame':row['frame'],'seconds':row['seconds'],
            'bones':{n:convert(arm.matrix_world@arm.pose.bones['root' if n=='root' else 'mixamorig:'+n].matrix) for n in names},
            'props':{n:convert(bpy.data.objects[n].matrix_world) for n in row['props']}})
    endpoints=[]
    for label,frame,target in [('entry',frames[0],135),('exit',frames[-1],manifest['final_pose_source_frame'])]:
        expected=core['dense_expected_native_samples'][target-1]['bones']
        values=[difference(frame['bones'][n],expected[n]) for n in names]
        maximum_cm=max(v[0] for v in values);maximum_degrees=max(v[1] for v in values)
        assert maximum_cm<.01 and maximum_degrees<.1,(name,label,maximum_cm,maximum_degrees)
        endpoints.append({'boundary':label,'source_core_frame':target,'maximum_position_difference_cm':maximum_cm,
                          'maximum_rotation_difference_degrees':maximum_degrees,'bones_checked':len(names)})
    assert sha(path)==before
    exported=manifest['animation_export']
    assert sha(exported['path'])==exported['sha256']
    reports.append({'name':name,'source_manifest':str(directory/'manifest.json'),'source_manifest_sha256':sha(directory/'manifest.json'),
        'blend_sha256':before,'animation_asset':'/Game/Art/Survivors/ScientistAnalysis/Animations/'+Path(exported['path']).stem,
        'source_fbx_sha256':exported['sha256'],'seconds':exported['duration_seconds'],'frames':exported['frames'],
        'loop':name=='WorkHold','selected_index':manifest['selected_index'],'endpoint_comparison':endpoints,
        'dense_expected_native_samples':frames})
contract={'schema':'oldwest.scientist.decision-branches.v1',
    'status':'CPU_import_expectations; native import and rendered gameplay remain unverified',
    'review':'Representative CPU branch views and all-frame contact audits; existing concealed handle/tray overlaps remain documented.',
    'core_contract':str(CORE/'runtime-integration-contract.json'),'core_contract_sha256':sha(CORE/'runtime-integration-contract.json'),
    'branch_sources':reports,
    'clock':'Each branch owns a30Hz local clock. Inclusive frames1..61 mean2seconds; Skip1..87 means2.8666667seconds. Use exact imported durations and verify them.',
    'choice_wait':'Enter WorkHold from core135. Keep response UI accessible and presentation nonbusy while waiting. Complete a loop or blend from its current small breathing phase; never reset the current hand/prop transforms by changing game state.',
    'public_gate':'Select0→SortLeft; select1→reviewed coreSort136..185; select2→SortRight. Skip→SkipRecover. Use only accepted public analysis_choice metadata matched to source/ability sequence and actual ordered reveals. Do not fabricate unavailable samples.',
    'recover_selected_sample_invariant':{
        'rule':'Capture all three actual sample identities and body-relative transforms at the accepted Sort branch endpoint. Keep those transforms throughout shared Recover. Drive only body, scanner and lid from coreRecover timing.',
        'reason':'CoreRecover was authored with middle sample at output. Replaying that sample table for left/right choices would visibly swap identities and move the wrong sample.',
        'position':'The selected branch sample stays supported on the output receiver; unselected samples remain in their real trays. Public effect/discard presentation may consume them only at the corresponding authorized beat.',
        'skip':'SkipRecover retains each visible sample in its original tray and keeps the output empty.'},
    'lifecycle':'Retain source match/ability sequence across response wait; cancel and clear scene props on interruption, match change or authoritative actor removal. Do not replay an old choice into a new scene.',
    'remaining':['Holster/return acceptance and FBX export','Native bone/material/prop audit','Actual gameplay branch/Skip/depletion/interrupt validation','Actual public junk-effect and unused-sample reaction choreography']}
(BASE/'decision-branch-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print('SCIENTIST_DECISION_BRANCH_CONTRACT_COMPLETE',flush=True)
