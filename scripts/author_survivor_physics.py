"""Build or freshly verify the separate anatomical asset; never edit the mesh/map.

Run Unreal Python commandlet after the shared native build. Add
-SurvivorPhysicsVerifyOnly for a read-only persisted-asset check.
Use -SurvivorRoundedPalms when authoring or verifying the isolated palm candidate;
the default remains the supported box-palm rig until native review accepts it.
The default knees permit -5..115 degrees of physical flexion. Use
-SurvivorLegacyKneeRange only to reproduce the old symmetric comparison rig.
The default elbows also permit -5..115 degrees, retaining forearm roll. Use
-SurvivorLegacyElbowRange only for the old symmetric elbow comparison rig.
"""
import hashlib
import json
import math
import shutil
import time
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/oldwest_survivor/physics'
OUT.mkdir(exist_ok=True)
BASE=ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA'
OLD=BASE/'SKM_Survivor_A_Cm_PhysicsAsset.uasset'
MESH=BASE/'SKM_Survivor_A_Cm.uasset'
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OLD,MESH)}
reference=OUT/'original-generated-physicsasset.uasset'
if not reference.exists():shutil.copy2(OLD,reference)
path='/Game/Art/Survivors/SurvivorA/PA_Survivor_Anatomical'
verify='-SurvivorPhysicsVerifyOnly' in unreal.SystemLibrary.get_command_line()
if verify:
    asset=unreal.load_asset(path)
else:
    existing=BASE/'PA_Survivor_Anatomical.uasset'
    if existing.exists():
        backup=OUT/('before-revision-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
        backup.mkdir()
        shutil.copy2(existing,backup/existing.name)
        for filename in ('authoring-report.json','fresh-validation.json'):
            if (OUT/filename).exists():shutil.copy2(OUT/filename,backup/filename)
    legacy_wrist_frames='-SurvivorUseLegacyWristFrames' in unreal.SystemLibrary.get_command_line()
    asset=unreal.OldWestAssetAuthoring.create_survivor_physics_asset(True,not legacy_wrist_frames)
    assert asset,'Anatomical asset authoring failed'
assert asset
report=json.loads(unreal.OldWestAssetAuthoring.describe_survivor_physics_asset(asset))
assert report['body_count']==16 and report['constraint_count']==15
assert abs(report['total_mass_kg']-73.3)<.01
bodies={b['bone']:b for b in report['bodies']}
rounded='-SurvivorRoundedPalms' in unreal.SystemLibrary.get_command_line()
for side in ('Left','Right'):
    hand=bodies[side+'Hand']
    assert abs(hand['mass_kg']-.5)<1e-6
    assert not hand['capsules']
    if rounded:
        assert not hand['boxes'] and len(hand['convexes'])==1
        shape=hand['convexes'][0]
        assert len(shape['vertices_cm'])==56 and len(shape['indices'])>=36
        assert all(abs(a-b)<1e-4 for a,b in zip(shape['size_cm'],(14,7.5,4)))
        assert 350<shape['volume_cm3']<420
        # A symmetric hull preserves the palm center rather than shifting it
        # toward a particular contact or pose used by the replay.
        vertices={tuple(round(v,5) for v in p) for p in shape['vertices_cm']}
        assert all(tuple(-v for v in p) in vertices for p in vertices)
    else:
        assert len(hand['boxes'])==1 and not hand['convexes']
assert {'LeftForeArm','RightForeArm'}<=bodies.keys()
assert all(.4<=b['mass_kg']<=18 for b in bodies.values())
assert all(b['iteration_overrides_enabled'] and b['position_solver_iterations']==12
           and b['velocity_solver_iterations']==4 and b['projection_solver_iterations']==1
           for b in bodies.values()), \
    'Stored solver counts are insufficient: every body must enable its 12/4/1 iteration override'
assert max(bodies['Hips']['bounds_size_cm'])<=30.1
assert max(bodies['Head']['bounds_size_cm'])<=26.1
assert all(bodies[side+'Foot']['mass_kg']<1.5 for side in ('Left','Right'))
assert all(c['adjacent_collision_disabled'] for c in report['constraints'])
assert report['disabled_collision_pairs']==30
assert report['thigh_collision_enabled'], 'Left and right thighs must not pass through one another'
assert report['forearm_chest_collision_enabled']=={'LeftForeArm':True,'RightForeArm':True}, \
    'Forearms must meet the chest instead of threading through it during a fall'
def verify_twist_range(joint, expected):
    child=joint['child_frame_reference_world_quaternion_xyzw']
    parent=joint['parent_frame_reference_world_quaternion_xyzw']
    # Independently reconstruct X twist of inverse(parent) * child. In this
    # reference pose the frames differ only in their deliberate hinge offset.
    x=parent[3]*child[0]-parent[0]*child[3]-parent[1]*child[2]+parent[2]*child[1]
    w=sum(a*b for a,b in zip(parent,child))
    neutral=(math.degrees(2*math.atan2(x,w))+180)%360-180
    assert abs(neutral-joint['neutral_twist_degrees'])<1e-4
    limits=[-joint['twist_degrees']-neutral,joint['twist_degrees']-neutral]
    assert all(abs(a-b)<1e-4 for a,b in zip(limits,expected)),(joint['child'],limits,expected)

one_way_knees='-SurvivorLegacyKneeRange' not in unreal.SystemLibrary.get_command_line()
one_way_elbows='-SurvivorLegacyElbowRange' not in unreal.SystemLibrary.get_command_line()
for side in ('Left','Right'):
    knee=next(c for c in report['constraints'] if c['child']==side+'Leg')
    verify_twist_range(knee,(-5,115) if one_way_knees else (-115,115))
    assert knee['swing1_degrees']==5 and knee['swing2_degrees']==5
    lower=[b-a for a,b in zip(bodies[side+'Leg']['reference_position_cm'],bodies[side+'Foot']['reference_position_cm'])]
    axis=knee['reference_twist_axis']
    derivative=[axis[1]*lower[2]-axis[2]*lower[1],axis[2]*lower[0]-axis[0]*lower[2],axis[0]*lower[1]-axis[1]*lower[0]]
    assert sum(a*b for a,b in zip(derivative,report['reference_forward'])) < -20, \
        'Positive knee twist must flex the lower leg toward the back of the character'
    elbow=next(c for c in report['constraints'] if c['child']==side+'ForeArm')
    verify_twist_range(elbow,(-5,115) if one_way_elbows else (-115,115))
    assert elbow['swing1_degrees']==80 and elbow['swing2_degrees']==5
    lower=[b-a for a,b in zip(bodies[side+'ForeArm']['reference_position_cm'],bodies[side+'Hand']['reference_position_cm'])]
    axis=elbow['reference_twist_axis']
    derivative=[axis[1]*lower[2]-axis[2]*lower[1],axis[2]*lower[0]-axis[0]*lower[2],axis[0]*lower[1]-axis[1]*lower[0]]
    assert sum(a*b for a,b in zip(derivative,report['reference_forward'])) > 20, \
        'Positive elbow twist must flex the forearm toward the front of the character'
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
if not verify:
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False)
    unreal.AssetRegistryHelpers.get_asset_registry().scan_modified_asset_files([str(BASE/'PA_Survivor_Anatomical.uasset')])
report.update({'fresh_reload':verify,'original_generated_asset_and_mesh_unchanged':True,
               'rounded_palms_candidate':rounded,
               'one_way_knees':one_way_knees,
               'one_way_elbows':one_way_elbows,
               'asset_sha256':hashlib.sha256((BASE/'PA_Survivor_Anatomical.uasset').read_bytes()).hexdigest(),
               'protected_sha256':protected,'reference_copy':str(reference),
               'runtime_fall_validation_required':True,'visual_body_fit_validation_required':True})
(OUT/('fresh-validation.json' if verify else 'authoring-report.json')).write_text(json.dumps(report,indent=2)+'\n')
unreal.log('SURVIVOR_ANATOMICAL_PHYSICS_VERIFIED '+json.dumps({k:v for k,v in report.items() if k not in ('bodies','constraints')}))
