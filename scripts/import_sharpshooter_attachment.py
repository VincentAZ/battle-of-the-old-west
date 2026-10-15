"""Additive Sharpshooter attachment import; preserve original Content and motion."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from crew_unreal_contract import CLIPS
import crew_animation_constraints

OUT = ROOT/'art/western/crew/attachments-v001/sharpshooter'
OLD = '/Game/Art/Western/Crew/Sharpshooter'
VERSION = os.environ.get('OLDWEST_ATTACHMENT_VERSION', 'V002')
assert VERSION in ('V001', 'V002')
DEST = OLD+'/Attachments'+VERSION
REPORTS = OUT/('unreal-'+VERSION.lower())
REPORTS.mkdir(exist_ok=True)
CONTENT = ROOT/'game/OldWest/Content'
DISK = CONTENT/DEST.removeprefix('/Game/')
VERIFY = os.environ.get('OLDWEST_ATTACHMENT_VERIFY_ONLY') == '1'
LIB = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot():
    return {str(p.relative_to(ROOT)): sha(p) for p in CONTENT.rglob('*')
            if p.is_file() and not p.is_relative_to(DISK)}


def values(t):
    return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,
            t.rotation.z,t.rotation.w,t.scale3d.x,t.scale3d.y,t.scale3d.z]


def difference(a, b):
    a, b = values(a), values(b)
    return max(math.dist(a[:3],b[:3]), math.dist(a[7:],b[7:]),
               min(math.dist(a[3:7],b[3:7]),math.dist(a[3:7],[-v for v in b[3:7]])))


before = snapshot()
report = dict(ok=False, mode='fresh_readback' if VERIFY else 'import', destination=DEST,
              source_validation_sha256=sha(OUT/'source-validation.json'))
try:
    v = json.loads((OUT/'source-validation.json').read_text())
    assert v['ok'] and sha(OUT/'exports/SK_Sharpshooter.fbx') == v['fbx_sha256']
    old_mesh = LIB.load_asset(OLD+'/SK_Sharpshooter')
    old_skeleton = old_mesh.get_editor_property('skeleton')
    physics = LIB.load_asset(OLD+'/PA_Sharpshooter')
    material = LIB.load_asset(OLD+'/M_Sharpshooter')
    if not VERIFY:
        assert not LIB.does_asset_exist(DEST+'/SK_Sharpshooter'), 'Preserve prior candidate'
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
        opt = unreal.FbxImportUI()
        for k,x in dict(import_mesh=True,import_as_skeletal=True,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,
                        import_materials=False,import_textures=False,import_animations=False,
                        automated_import_should_detect_type=False,create_physics_asset=False).items():
            opt.set_editor_property(k,x)
        for k,x in dict(import_translation=unreal.Vector(0,0,0),import_rotation=unreal.Rotator(0,0,0),
                        import_uniform_scale=1.,convert_scene=True,force_front_x_axis=False,convert_scene_unit=True,
                        update_skeleton_reference_pose=True,use_t0_as_ref_pose=False,preserve_smoothing_groups=True,
                        normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():
            opt.skeletal_mesh_import_data.set_editor_property(k,x)
        task = unreal.AssetImportTask()
        for k,x in dict(filename=str(OUT/'exports/SK_Sharpshooter.fbx'),destination_path=DEST,
                        destination_name='SK_Sharpshooter',automated=True,replace_existing=False,save=False,
                        options=opt,factory=unreal.FbxFactory()).items():
            task.set_editor_property(k,x)
        TOOLS.import_asset_tasks([task])
        mesh = next(x for x in task.get_objects() if isinstance(x,unreal.SkeletalMesh))
        skeleton = mesh.get_editor_property('skeleton')
        slots = mesh.get_editor_property('materials'); assert len(slots)==1
        slot=slots[0];slot.set_editor_property('material_interface',material);slots[0]=slot
        mesh.set_editor_property('materials',slots)
        mesh.set_editor_property('physics_asset',physics)
        assert LIB.save_loaded_asset(mesh,False) and LIB.save_loaded_asset(skeleton,False)
    mesh = LIB.load_asset(DEST+'/SK_Sharpshooter')
    skeleton = mesh.get_editor_property('skeleton')
    assert skeleton.get_path_name().startswith(DEST+'/') and skeleton != old_skeleton
    assert mesh.get_editor_property('physics_asset') == physics
    assert mesh.get_editor_property('materials')[0].get_editor_property('material_interface') == material
    comp = unreal.SkeletalMeshComponent(); comp.set_skeletal_mesh_asset(mesh)
    old_comp = unreal.SkeletalMeshComponent(); old_comp.set_skeletal_mesh_asset(old_mesh)
    bones = [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
    old_bones = [str(old_comp.get_bone_name(i)) for i in range(old_comp.get_num_bones())]
    assert set(bones)==set(old_bones)
    assert str(comp.get_parent_bone('Rifle')) == 'RightHand'
    for bone in bones:
        if bone!='Rifle': assert comp.get_parent_bone(bone)==old_comp.get_parent_bone(bone),bone
    ref = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    old_ref = unreal.AnimPoseExtensions.get_reference_pose(old_skeleton)
    ref_error = max(difference(unreal.AnimPoseExtensions.get_bone_pose(ref,b,unreal.AnimPoseSpaces.WORLD),
                               unreal.AnimPoseExtensions.get_bone_pose(old_ref,b,unreal.AnimPoseSpaces.WORLD)) for b in bones)
    assert ref_error < .001,ref_error
    report.update(mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),physics_reused=physics.get_path_name(),
                  material_reused=material.get_path_name(),rest_world_max_error=ref_error,bone_count=len(bones),clips=[])
    for clip in CLIPS:
        name='RA_'+Path(clip).name
        old_anim = LIB.load_asset(OLD+'/Animations/'+name)
        old_model = old_anim.get_editor_property('data_model_interface')
        count = old_model.get_number_of_keys()
        if not VERIFY:
            factory = unreal.AnimSequenceFactory();factory.set_editor_property('target_skeleton',skeleton)
            factory.set_editor_property('preview_skeletal_mesh',mesh)
            anim = TOOLS.create_asset(name,DEST+'/Animations',unreal.AnimSequence,factory)
            for prop in ('bone_compression_settings','curve_compression_settings','interpolation','rate_scale'):
                anim.set_editor_property(prop,old_anim.get_editor_property(prop))
            anim.set_editor_property('retarget_source_asset',mesh)
            anim.update_retarget_source_asset_data()
            ctrl = anim.get_editor_property('controller')
            ctrl.open_bracket('Copy approved motion with corrected rifle parent',False)
            try:
                ctrl.set_frame_rate(old_model.get_frame_rate(),False)
                ctrl.set_number_of_frames(unreal.FrameNumber(old_model.get_number_of_frames()),False)
                keys={bone:[] for bone in bones}
                for i in range(count):
                    t=old_anim.get_play_length()*i/max(1,count-1)
                    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(old_anim,t,unreal.AnimPoseEvaluationOptions())
                    assert unreal.AnimPoseExtensions.is_valid(pose)
                    for bone in bones:
                        keys[bone].append(unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.LOCAL))
                for bone,transforms in keys.items():
                    pos=[t.translation for t in transforms]
                    rot=[t.rotation for t in transforms]
                    scale=[t.scale3d for t in transforms]
                    if not anim.get_editor_property('data_model_interface').is_valid_bone_track_name(bone):
                        assert ctrl.add_bone_curve(bone,False)
                    assert ctrl.set_bone_track_keys(bone,pos,rot,scale,False)
            finally:
                ctrl.close_bracket(False)
            crew_animation_constraints.apply(anim,skeleton,['Rifle'])
            assert LIB.save_loaded_asset(anim,False)
        anim=LIB.load_asset(DEST+'/Animations/'+name)
        assert anim.get_editor_property('skeleton')==skeleton
        assert abs(anim.get_play_length()-old_anim.get_play_length())<1e-6
        maxima={b:0. for b in bones}
        # Compare every native key, including the prop, in component space.
        # Existing clips freeze the grip chain, so reparenting must preserve
        # the full approved standing/walk/reaction/ability pose, not only rest.
        for i in range(count):
            t=old_anim.get_play_length()*i/max(1,count-1)
            a=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,t,unreal.AnimPoseEvaluationOptions())
            b=unreal.AnimPoseExtensions.get_anim_pose_at_time(old_anim,t,unreal.AnimPoseEvaluationOptions())
            assert unreal.AnimPoseExtensions.is_valid(a) and unreal.AnimPoseExtensions.is_valid(b)
            for bone in bones:
                delta=difference(unreal.AnimPoseExtensions.get_bone_pose(a,bone,unreal.AnimPoseSpaces.WORLD),
                                 unreal.AnimPoseExtensions.get_bone_pose(b,bone,unreal.AnimPoseSpaces.WORLD))
                maxima[bone]=max(maxima[bone],delta)
        assert max(maxima.values())<.02,(name,maxima)
        report['clips'].append(dict(asset=anim.get_path_name(),keys=count,max_world_error=max(maxima.values()),
                                   bone_errors=maxima,seconds=anim.get_play_length()))
    report['ok']=True
except Exception as error:
    report.update(error=repr(error),traceback=traceback.format_exc())
    raise
finally:
    after=snapshot();report['existing_content_unchanged']=before==after
    report['protected_content_count']=len(before)
    report['content_sha256']={str(p.relative_to(ROOT)):sha(p) for p in DISK.rglob('*') if p.is_file()}
    report['script_sha256']=sha(Path(__file__))
    report['ok']=report['ok'] and before==after
    (REPORTS/('unreal-readback.json' if VERIFY else 'unreal-import.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert before==after,'Existing Content changed'
    unreal.log('SHARPSHOOTER_ATTACHMENT_IMPORT '+str(report['ok']))
