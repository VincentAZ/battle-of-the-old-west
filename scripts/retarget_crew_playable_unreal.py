"""Crew retarget and fresh-process animation readback worker."""
import json, os, traceback
import math
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT/'scripts'))
from crew_unreal_contract import character, CLIPS
import crew_animation_constraints as constraints
CONFIG=character(os.environ['OLDWEST_CREW_SLUG'])
SLUG,NAME,OUT,DEST=(CONFIG[k] for k in ('slug','name','out','dest'))
VERIFY=os.environ.get('OLDWEST_CREW_VERIFY_ONLY')=='1'
report = {'ok': False, 'mode': 'fresh_readback' if VERIFY else 'retarget', 'visual_qa_passed': False}
REPORT_PATH = OUT/('unreal-retarget-readback.json' if VERIFY else 'unreal-retarget.json')
try:
    LIB = unreal.EditorAssetLibrary
    TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
    source = LIB.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
    target = LIB.load_asset(DEST + '/SK_'+NAME)
    assert source and target, 'Both skeletal meshes must already be imported'
    assert target.get_editor_property('skeleton'), 'Run the Native preview import helper to save its skeleton first'


    def bone_names(mesh):
        component = unreal.SkeletalMeshComponent()
        component.set_skeletal_mesh_asset(mesh)
        return [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]


    source_bones, target_bones = bone_names(source), bone_names(target)
    (OUT / 'unreal-bones.json').write_text(json.dumps({'source': source_bones, 'target': target_bones}, indent=2) + '\n')


    def resolve(name, bones):
        possibilities = [name, name.replace(':', '_'), name.split(':')[-1]]
        found = list(dict.fromkeys(n for n in possibilities if n in bones))
        assert len(found) == 1, f'No bone matching {name} in {bones}'
        return found[0]


    source_chains = {
        'Root': ['root', 'root'], 'Spine': ['spine_01', 'spine_05'],
        'Neck': ['neck_01', 'neck_02'], 'Head': ['head', 'head'],
    }
    for side, suffix in [('Left', 'l'), ('Right', 'r')]:
        source_chains.update({
            side+'Clavicle': ['clavicle_'+suffix]*2,
            side+'Arm': ['upperarm_'+suffix, 'hand_'+suffix],
            side+'Leg': ['thigh_'+suffix, 'foot_'+suffix],
            side+'Toe': ['ball_'+suffix]*2,
        })
        for finger in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
            source_chains[side+finger] = [f'{finger.lower()}_01_{suffix}', f'{finger.lower()}_03_{suffix}']
    spec = json.loads((ROOT/'art/characters/oldwest_survivor/manny-retarget-chains.json').read_text())
    target_chains = {name: [resolve(b, target_bones) for b in pair] for name, pair in spec['chains'].items()}


    def rig(name, mesh, root, chains):
        path = DEST + '/Rig/' + name
        asset = LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name, DEST+'/Rig', unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
        ctrl = unreal.IKRigController.get_controller(asset)
        assert ctrl.set_skeletal_mesh(mesh)
        assert ctrl.set_retarget_root(root)
        for old in ctrl.get_retarget_chains():
            ctrl.remove_retarget_chain(old.chain_name)
        for chain, (start, end) in chains.items():
            assert start in bone_names(mesh) and end in bone_names(mesh), chain
            assert str(ctrl.add_retarget_chain(chain, start, end, 'None')) == chain
        LIB.save_loaded_asset(asset)
        return asset


    if not VERIFY:
        source_rig = rig('IK_Manny_Source', source, 'pelvis', source_chains)
        target_rig = rig('IK_'+NAME, target, resolve(spec['target_retarget_root'], target_bones), target_chains)
        path = DEST + '/Rig/RTG_Manny_'+NAME
        retarget = LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset('RTG_Manny_'+NAME, DEST+'/Rig', unreal.IKRetargeter, unreal.IKRetargetFactory())
        ctrl = unreal.IKRetargeterController.get_controller(retarget)
        for role, ik, mesh in [(unreal.RetargetSourceOrTarget.SOURCE, source_rig, source), (unreal.RetargetSourceOrTarget.TARGET, target_rig, target)]:
            ctrl.set_ik_rig(role, ik)
            ctrl.set_preview_mesh(role, mesh)
        ctrl.remove_all_ops()
        ctrl.add_default_ops()
        ctrl.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
        ctrl.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.TARGET, target_rig)
        ctrl.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
        ctrl.auto_align_all_bones(unreal.RetargetSourceOrTarget.TARGET, unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
        LIB.save_loaded_asset(retarget)

        clips = CLIPS
        inputs = unreal.IKRetargetBatchOperationInputs()
        inputs.assets_to_retarget = [LIB.find_asset_data('/Game/Characters/Mannequins/Anims/'+p) for p in clips]
        assert all(a.is_valid() for a in inputs.assets_to_retarget), 'Missing source clip'
        inputs.source_mesh = source
        inputs.target_mesh = target
        inputs.ik_retarget_asset = retarget
        inputs.prefix = 'RA_'
        inputs.target_path = DEST + '/Animations'
        inputs.use_source_path = False
        inputs.include_referenced_assets = False
        inputs.overwrite_existing_files = True
        inputs.retain_additive_flags = False
        results = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
        assert len(results) == len(clips), f'Only {len(results)} clips baked'

    else:
        retarget = LIB.load_asset(DEST+'/Rig/RTG_Manny_'+NAME)
        assert isinstance(retarget, unreal.IKRetargeter), 'Missing saved retargeter'
        results = [LIB.find_asset_data(DEST+'/Animations/RA_'+Path(p).name) for p in CLIPS]
        assert all(data.is_valid() for data in results), 'Missing saved animation'

    expected_clip_paths = {DEST+'/Animations/RA_'+Path(p).name for p in CLIPS}
    assert {data.get_asset().get_path_name().split('.')[0] for data in results} == expected_clip_paths, 'Unexpected retarget output names'
    report = {'ok': False, 'mode': 'fresh_readback' if VERIFY else 'retarget',
              'approved_source_sha256': CONFIG['source_sha256'], 'rig_project_sha256': CONFIG['validation']['project_sha256'],
              'source_mesh': source.get_path_name(), 'target_mesh': target.get_path_name(),
              'retargeter': retarget.get_path_name(), 'target_bones': len(target_bones),
              'chains': target_chains, 'clips': [], 'visual_qa_passed': False}
    frozen = constraints.frozen_bones(CONFIG['validation'], target_bones)
    report['frozen_bind_bones'] = frozen
    inspect_bones = [resolve('mixamorig:'+b, target_bones) for b in ['Hips', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot']]
    for data in results:
        anim = data.get_asset()
        assert isinstance(anim, unreal.AnimSequence)
        assert anim.get_path_name().startswith(DEST+'/Animations/'), 'Animation escaped character destination'
        if not VERIFY:
            constraints.apply(anim, target.get_editor_property('skeleton'), frozen)
            assert LIB.save_loaded_asset(anim)
        constraint_report = constraints.audit(anim, target.get_editor_property('skeleton'), frozen)
        length = anim.get_play_length()
        assert length > 0
        assert anim.get_editor_property('skeleton') == target.get_editor_property('skeleton')
        assert anim.get_editor_property('additive_anim_type') == unreal.AdditiveAnimationType.AAT_NONE
        poses = []
        for fraction in [0, .25, .5, .75, .99]:
            pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, length*fraction, unreal.AnimPoseEvaluationOptions())
            assert unreal.AnimPoseExtensions.is_valid(pose)
            samples = {}
            for bone in inspect_bones:
                transform = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
                pos, rot = transform.translation, transform.rotation
                samples[bone] = tuple(round(v, 5) for v in (pos.x, pos.y, pos.z, rot.x, rot.y, rot.z, rot.w))
                assert all(math.isfinite(v) for v in samples[bone]), 'Invalid animated bone transform'
            poses.append(samples)
        # A meter-based FBX with a 100x armature-node scale can bake moving yet
        # collapsed poses. Enforce human-sized head-to-pelvis distances in cm.
        head = resolve('mixamorig:Head', target_bones)
        hips = resolve('mixamorig:Hips', target_bones)
        for sample in poses:
            distance = math.dist(sample[head][:3], sample[hips][:3])
            assert 20 < distance < 120, f'Collapsed or overstretched skeleton: head/pelvis {distance} cm'
        animated = [b for b in inspect_bones if len({p[b] for p in poses}) > 1]
        assert animated, f'Animation contains no measured movement: {anim.get_name()}'
        report['clips'].append({'asset': anim.get_path_name(), 'seconds': length,
                                'animated_sample_bones': animated, 'full_pose': True,
                                'sample_poses': poses, 'bind_constraints': constraint_report})
    report['ok'] = True
    (OUT/('unreal-retarget-readback.json' if VERIFY else 'unreal-retarget.json')).write_text(json.dumps(report, indent=2)+'\n')
    unreal.log('CREW_RETARGET_AUDIT ' + json.dumps(report))
except Exception as exc:
    report.update(ok=False, error=repr(exc), traceback=traceback.format_exc())
    REPORT_PATH.write_text(json.dumps(report, indent=2)+'\n')
    raise
