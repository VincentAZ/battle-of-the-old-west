"""Read-only Blender extraction of a Prospector candidate's native contract.

The generated transforms are expected import results, not evidence that an
Unreal importer or the game actually reproduced them.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source = args.source.resolve()
blend = source/'Scientist_Analysis_Candidate.blend'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
before = sha(blend)
spec = json.loads((source/'manifest.json').read_text())
samples = json.loads((source/'pose-and-prop-samples.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(blend), use_scripts=False)
arm = bpy.data.objects['Survivor_Rig']
base = '/Game/Art/Survivors/ScientistAnalysis'


def position(v):
    return [100*v[0], -100*v[1], 100*v[2]]


def rotation(q):
    # Equivalent to FFbxDataConverter::ConvertRotToQuat; sign is immaterial.
    return [-q.x, q.y, -q.z, q.w]


def transform(matrix):
    p, q, s = matrix.decompose()
    return {'translation_cm': position(p), 'rotation_xyzw': rotation(q), 'scale': list(s)}


frames = []
names = ['root','Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot',
         'LeftHandIndex1','LeftHandPinky1','RightHandIndex1','RightHandPinky1']
for frame in range(1,272):
    bpy.context.scene.frame_set(frame)
    bones = {name: transform(arm.matrix_world @ arm.pose.bones['root' if name=='root' else 'mixamorig:'+name].matrix) for name in names}
    props = {name: transform(bpy.data.objects[name].matrix_world) for name in samples[frame-1]['props']}
    frames.append({'source_frame':frame, 'full_clip_seconds':(frame-1)/30, 'bones':bones, 'props':props,
                   'palm_contacts_cm':{side:position(data['palm_world_m'])
                                       for side,data in samples[frame-1]['contacts'].items()}})
bpy.context.scene.frame_set(1)
props = []
for exported in spec['prop_exports']:
    root = bpy.data.objects[exported['pivot']]
    points = [root.matrix_world.inverted() @ child.matrix_world @ v.co
              for child in root.children if child.type == 'MESH' for v in child.data.vertices]
    native = [position(p) for p in points]
    props.append({'asset':base+'/Props/'+Path(exported['path']).stem, 'source_fbx_sha256':exported['sha256'],
                  'pivot_name':root.name, 'initial_body_relative_transform':transform(root.matrix_world),
                  'local_mesh_bounds_cm':[[min(p[i] for p in native) for i in range(3)],
                                          [max(p[i] for p in native) for i in range(3)]],
                  'material_slots':exported['material_slots']})
clips = []
for item in spec['animation_exports']:
    first,last = item['frames']
    clips.append({'asset':base+'/Animations/'+Path(item['path']).stem,
                  'source_fbx_sha256':item['sha256'], 'source_frames':[first,last],
                  'duration_seconds':(last-first)/30,
                  'full_clip_time_offset_seconds':(first-1)/30,
                  'integer_sample_rule':'source_frame=first+30*local_clip_seconds',
                  'loop':False})
contract = {
    'schema':'oldwest.scientist.cpu-import-contract.v1',
    'status':'expected_native_contract; import and rendered gameplay validation pending',
    'source':str(source), 'source_blend_sha256':before, 'source_manifest_sha256':sha(source/'manifest.json'),
    'coordinate_system':{
        'authoring':'meters; actor feet at origin; character faces -Y; +Z up',
        'native':'centimeters in the skeletal Body component frame; model faces +Y; +Z up',
        'position':'(x,y,z) -> (100*x,-100*y,100*z)',
        'quaternion_xyzw':'(x,y,z,w) -> (-x,y,-z,w), equivalent to engine (x,-y,z,-w)',
        'fbx_export':'physical centimeter vertices/translations; object scale1; axes forward=-Y/up=Z; no leaf bones',
        'fbx_import':'legacy FBX importer; match up axis; force front X false; no extra import rotation/translation/scale',
        'native_source':'UE5.8.2 UnrealEd/Private/Fbx/FbxUtilsImport.cpp ConvertPos/ConvertRotToQuat and FbxMainImport.cpp ConvertScene',
        'world_composition':'Transform all props by Body->GetComponentTransform(), including existing Facing; never add a second yaw or attach to actor forward.',
        'ground':'Case feet are authored at the same local ground as the fixed character feet. Use one common scene placement; do not independently resnap the case after aligning hands.'},
    'rig':{'skeleton':'/Game/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm_Skeleton',
           'review_mesh':'/Game/Art/Survivors/Variants/SKM_Prospector_Cm',
           'blender_bones':53,'expected_native_bones':54,'root_motion':'none; root and both feet fixed',
           'bone_names':'Native names omit mixamorig:; extra imported container bone is Survivor_Rig.',
           'body_pose':'work lean is entered during1..30 and removed250..271; do not add procedural work pitch on top.'},
    'clips':clips,'props':props,
    'clock':{'fps':30,'full_duration_seconds':9,
             'rule':'Drive bone clip and prop table from one elapsed animation clock. Interpolate translations linearly and quaternions by shortest-arc slerp between integer samples.',
             'boundaries':'Six phase FBXs contain inclusive source endpoints; their durations sum to8.833333s, because five 1/30s inter-phase intervals are absent. The9s Full clip is canonical. Preserve the source clock or supply those bridge intervals; do not simply concatenate phase durations and use full-clip prop time.',
             'policy':'9s is source material, not an unconditional gameplay delay or authorization to change global cinematic timing.'},
    'events':[
        {'frames':[1,30],'event':'Approach closed case; rifle must already be holstered; real case deployment is a separate entry action.'},
        {'frames':[31,60],'event':'Right palm follows hinged handle; lid opens0..70 degrees about Blender local-Y (native negative-Y equivalent). Left hand braces outside handle.'},
        {'frames':[61,80],'event':'Release handle and move around rear lid edge outside the coat; right hand reaches dock. Keep scanner on dock through frame80.'},
        {'frames':[81,135],'event':'Scanner follows right palm anchor, with authored fixed component orientation; scan actual populated trays. Source inspection stops at frame135 before selection.'},
        {'frames':[136,145],'event':'Left hand reaches the middle sample; this authored selection index is1, not an arbitrary runtime choice.'},
        {'frames':[146,176],'event':'Selected sample follows left palm plus Blender(0,-.055,-.035)m; reaches receiver at frame176.'},
        {'frames':[177,185],'event':'Detach selected sample to the exact receiver-relative world position in the dense prop samples; fingers release while the sample stays supported.'},
        {'frames':[186,205],'event':'Left hand leaves receiver; scanner returns to dock, still hand-driven through205.'},
        {'frames':[206,225],'event':'Detach scanner to dock; hand travels around lid edge and grasps handle.'},
        {'frames':[226,250],'event':'Close lid70..0 degrees, following the actual hinge and handle.'},
        {'frames':[251,271],'event':'Release handle; hands leave closed case; torso returns upright. Restore weapon/idle only after hands clear.'}],
    'attachment_policy':{
        'preferred':'Use the dense body-relative prop transforms synchronized to the animation. They already contain grip offsets and release positions.',
        'socket_alternative':'At a reviewed contact frame compute RelativeProp=PropBody.GetRelativeTransform(HandBody). Attach with KeepWorldTransform and retain this offset, never SnapToTarget. Scanner grip orientation is component-fixed in this candidate; verify every held frame if using a bone-relative socket.',
        'sample_alternative':'Sample held center is native palm+(0,+5.5,-3.5)cm; once released, detach KeepWorldTransform and keep receiver position. Never recenter sample at hand bone origin.',
        'lid':'Local pivot is the hinge; asset is not centered. Apply authored quaternion and hinge position together.'},
    'public_outcome_gate':{
        'dispatch':'public scientist ability_index0, or exact public copied-source Prospector ability; do not infer from a hidden person ID.',
        'reveals':'Use ordered public reveal_discard records for this source/sequence and actual count0..3. Never inspect private deck state or fabricate a third card after depletion.',
        'selection':'Only legally selected choice may feed output. This candidate authors middle index1. Left/right selected-tray clips or validated equivalent hand IK remain required before general gameplay use; silently selecting the middle sample is prohibited.',
        'skip':'Do not play Sort or an output reaction on Skip. A validated transition from frame135 to the scanner-return/recovery phase is required; this candidate does not claim that branch is authored.',
        'depletion':'Cancel unfinished optional work on match finish; retain only already public reveals and the actual game result.',
        'target_reaction':'Chosen water/draw/raid/injury/punk/restore beats must follow authoritative public effects. Unused sample discard and target modules are separate remaining scene work.'},
    'weapon_and_lifecycle':{
        'weapon':'Stockyards firearm visibility/attachment and current animation state. Holster at a reviewed back/hip location or conceal during a separately authored holster transition before work; never leave rifle attached to the scanner hand. This candidate contains no holster animation.',
        'collision':'Decorative work props have no physics, pawn or camera query collision; no change to authoritative unit, ragdoll bodies or gameplay targeting.',
        'ownership':'One transient scene owner per active beat owns all10 prop components; do not register preview copies as gameplay units.',
        'interrupt':'On travel, source removal/death, cancellation, match finish or beat teardown: stop the work clock, detach/destroy props, clear grip bindings and restore weapon only for a still-live armed unit. Do not revive or resume idle over an active ragdoll.',
        'choice_wait':'Do not repeatedly advance/replay Sort while awaiting public choice. A separate relaxed work-hold loop is future animation work; do not assert it exists.'},
    'native_acceptance':[
        'Fresh process: all7clips/10props/materialslots,54bone skeleton, finite unit scales and unchanged original asset hashes.',
        'Imported hand/root/foot positions and orientations match dense expected samples, including open, handoff, grip, sample placement and recovery.',
        'Actual rendered performer+props from both player orientations; both hands and device housings visible; inspect lid/coat clearance and firearm holster.',
        'Legal public action captures for three revealed choices, Skip and depletion; no invented outcome or duplicate activation.',
        'Interrupt/teardown leaves no props or hidden weapon on living unit and does not alter the strict natural ragdoll guard.',
        'Studio material micro-bump is not baked into native materials; inspect actual material quality before claiming parity.'],
    'dense_expected_native_samples':frames}
assert sha(blend)==before
(source/'runtime-integration-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print('SCIENTIST_INTEGRATION_CONTRACT_COMPLETE',str(source),flush=True)
