"""Complete Prospector importer. Run only in the root-assigned editor lane.

CPU preflight: python scripts/scientist_import_contract.py.
Fresh editor readback: OLDWEST_SCIENTIST_VERIFY_ONLY=1.
OLDWEST_SCIENTIST_REPORT may select a NEW report within the authoring folder.
No editor launch or gameplay integration. The core-only importer is preserved
under art/characters/scientist_gesture/importer-provenance/.
"""
import json
import math
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
import unreal
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientist_import_contract import (BASE, CONTRACT, DEST, EXPECTATIONS, ROOT,
    check_transform, difference, endpoint_checks, load_bundle, read, require, sha)

CONTENT = ROOT/'game/OldWest/Content'
DEST_DISK = CONTENT/'Art/Survivors/ScientistAnalysis'
VERIFY = os.environ.get('OLDWEST_SCIENTIST_VERIFY_ONLY') == '1'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
MODE = 'readback' if VERIFY else 'import'
REPORT = Path(os.environ.get('OLDWEST_SCIENTIST_REPORT',str(BASE/'native-complete-audits'/f'{STAMP}-{MODE}.json'))).resolve()
require(REPORT.is_relative_to(BASE) and not REPORT.exists(), 'Report must be a new Prospector authoring file',REPORT)
require('OLDWEST_SCIENTIST_SOURCE' not in os.environ,'Core-only SOURCE override obsolete; complete bundle required')
LIB, MAT = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
report = {'ok':False,'mode':MODE,'status':'preflight','animations':[],'props':[],'materials':[],
    'importer_sha256':sha(__file__),'validator_sha256':sha(Path(__file__).with_name('scientist_import_contract.py')),
    'complete_contract_sha256':sha(CONTRACT),'dense_expectations_sha256':sha(EXPECTATIONS)}
before = None
allowed_outputs = set()


def snapshot():
    return {str(p.relative_to(CONTENT)):sha(p) for p in sorted(CONTENT.rglob('*'))
            if p.is_file() and (VERIFY or str(p.relative_to(CONTENT)) not in allowed_outputs)}


def as_transform(t):
    p,q,s = t.translation,t.rotation,t.scale3d
    value = dict(translation_cm=[p.x,p.y,p.z],rotation_xyzw=[q.x,q.y,q.z,q.w],scale=[s.x,s.y,s.z])
    check_transform(value,'native transform')
    return value


def strict_object(obj, path, cls):
    require(isinstance(obj,cls) and obj.get_path_name() == path+'.'+path.rsplit('/',1)[1], 'Unexpected native object',path,obj)
    return obj


def configure_coordinates(data):
    for key,value in dict(import_translation=unreal.Vector(0,0,0),import_rotation=unreal.Rotator(0,0,0),
        import_uniform_scale=1.,convert_scene=True,force_front_x_axis=False,convert_scene_unit=True).items():
        data.set_editor_property(key,value)


def import_fbx(path, asset, options, cls):
    task = unreal.AssetImportTask()
    for key,value in dict(filename=str(path),destination_name=asset.rsplit('/',1)[1],destination_path=asset.rsplit('/',1)[0],
        automated=True,replace_existing=True,save=False,options=options,factory=unreal.FbxFactory()).items():
        task.set_editor_property(key,value)
    TOOLS.import_asset_tasks([task])
    objects = list(task.get_objects())
    require(len(objects) == 1,'Import created unexpected additional objects',asset,[x.get_path_name() for x in objects])
    return strict_object(objects[0],asset,cls)


def material_constant(material, prop, value, create):
    vector = isinstance(value,list)
    cls = unreal.MaterialExpressionConstant3Vector if vector else unreal.MaterialExpressionConstant
    if create:
        node = MAT.create_material_expression(material,cls)
        node.set_editor_property('constant' if vector else 'r',unreal.LinearColor(*value,1.) if vector else float(value))
        require(MAT.connect_material_property(node,'',prop),'Material connection failed',material.get_path_name(),prop)
    node = MAT.get_material_property_input_node(material,prop)
    require(isinstance(node,cls),'Missing/wrong material input node',material.get_path_name(),prop)
    actual = node.get_editor_property('constant' if vector else 'r')
    error = max(abs(a-b) for a,b in zip((actual.r,actual.g,actual.b),value)) if vector else abs(actual-value)
    require(error < .00001,'Persisted material value mismatch',material.get_path_name(),prop,error)


def evaluate(anim, seconds, scientist, names):
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property('optional_skeletal_mesh',scientist)
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,seconds,options)
    require(unreal.AnimPoseExtensions.is_valid(pose),'Invalid native pose',anim.get_path_name(),seconds)
    actual_names = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)]
    require(len(actual_names) == 54 and set(actual_names) == set(names),'Imported 53-to54 bone identity mismatch')
    return {name:as_transform(unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)) for name in names}


try:
    bundle = load_bundle()
    dense = bundle['dense']
    expected_assets = [c['asset'] for c in bundle['clips']]+[p['asset'] for p in bundle['props']]+[
        DEST+'/Materials/'+name for name in bundle['materials']]
    allowed_outputs = {asset.removeprefix('/Game/')+suffix for asset in expected_assets
                       for suffix in ('.uasset','.uexp','.ubulk')}
    report['source_provenance'],report['cpu_endpoint_checks'] = bundle['provenance'],bundle['endpoints']
    before = snapshot()
    require(before,'No existing Content assets found')
    report['protected_content_sha256'] = before
    if not VERIFY:
        backup = BASE/'native-import-backups'/STAMP
        backup.mkdir(parents=True,exist_ok=False)
        if DEST_DISK.exists(): shutil.copytree(DEST_DISK,backup/'ScientistAnalysis')
        (backup/'protected-content-sha256.json').write_text(json.dumps(before,indent=2)+'\n')
        shutil.copy2(__file__,backup/'importer.py'); shutil.copy2(CONTRACT,backup/CONTRACT.name)
        report['backup'] = str(backup)
    skeleton = strict_object(LIB.load_asset(bundle['core']['rig']['skeleton']),bundle['core']['rig']['skeleton'],unreal.Skeleton)
    scientist = strict_object(LIB.load_asset(bundle['core']['rig']['review_mesh']),bundle['core']['rig']['review_mesh'],unreal.SkeletalMesh)
    require(scientist.get_editor_property('skeleton') == skeleton,'Review mesh uses another skeleton')
    reference_path = ROOT/'art/characters/survivor_variants/deformation-v3/native-reference-audit.json'
    reference = read(reference_path)['reference']
    report['native_reference_audit_sha256'] = sha(reference_path)
    component = unreal.SkeletalMeshComponent(); component.set_skinned_asset_and_update(scientist)
    names = [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    require(len(names) == 54 and set(names) == set(dense['bone_names'])|{'Survivor_Rig'},'Reference bone identities')
    for index,row in enumerate(reference['bones']):
        require(names[index] == row['name'] and str(component.get_parent_bone(names[index])) == row['parent'],'Reference hierarchy changed',row['name'])
        actual = as_transform(component.get_ref_pose_transform(index))
        expected = dict(translation_cm=row['translation'],rotation_xyzw=row['rotation'],scale=row['scale'])
        cm,degrees = difference(actual,expected)
        require(cm < .001 and degrees < .001 and max(abs(a-b) for a,b in zip(actual['scale'],expected['scale'])) < .000001,'Reference pose changed',row['name'])
    report['reference_bone_count'] = len(names)
    if not VERIFY:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    materials = {}
    for name,spec in bundle['materials'].items():
        path = DEST+'/Materials/'+name
        material = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
        if not VERIFY: material = material or TOOLS.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        strict_object(material,path,unreal.Material)
        if not VERIFY:
            MAT.delete_all_material_expressions(material)
            material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
            material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
        require(material.get_editor_property('shading_model') == unreal.MaterialShadingModel.MSM_DEFAULT_LIT
            and material.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE,'Persisted material model mismatch')
        for prop,value in [(unreal.MaterialProperty.MP_BASE_COLOR,spec['base_color']),
                           (unreal.MaterialProperty.MP_ROUGHNESS,spec['roughness']),
                           (unreal.MaterialProperty.MP_METALLIC,spec['metallic'])]:
            material_constant(material,prop,value,not VERIFY)
        if spec['emission']:
            material_constant(material,unreal.MaterialProperty.MP_EMISSIVE_COLOR,[x*spec['emission'] for x in spec['base_color']],not VERIFY)
        else:
            require(MAT.get_material_property_input_node(material,unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None,'Unexpected emissive connection')
        if not VERIFY:
            MAT.recompile_material(material)
            require(LIB.save_loaded_asset(material,only_if_is_dirty=False),'Material save failed',path)
        materials[name] = material
        report['materials'].append(dict(asset=path,verified_values=spec))
    report['status'] = 'validating_props'
    for spec in bundle['props']:
        path = spec['asset']
        if not VERIFY:
            options = unreal.FbxImportUI()
            for key,value in dict(import_mesh=True,import_as_skeletal=False,import_animations=False,
                import_materials=False,import_textures=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH,
                automated_import_should_detect_type=False).items(): options.set_editor_property(key,value)
            data = options.static_mesh_import_data; configure_coordinates(data)
            for key,value in dict(combine_meshes=True,auto_generate_collision=False,
                normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items(): data.set_editor_property(key,value)
            mesh = import_fbx(spec['source_fbx'],path,options,unreal.StaticMesh); mesh.modify()
            slots = mesh.get_editor_property('static_materials')
            for index,slot in enumerate(slots):
                name = str(slot.get_editor_property('material_slot_name'))
                require(name in spec['material_slots'],'Unexpected imported prop material',name)
                slot.set_editor_property('material_interface',materials[name]); slots[index] = slot
            mesh.set_editor_property('static_materials',slots)
            require(LIB.save_loaded_asset(mesh,only_if_is_dirty=False),'Prop save failed',path)
        mesh = strict_object(LIB.load_asset(path),path,unreal.StaticMesh)
        slots = mesh.get_editor_property('static_materials')
        actual_names = [str(s.get_editor_property('material_slot_name')) for s in slots]
        require(len(actual_names) == len(spec['material_slots']) and set(actual_names) == set(spec['material_slots']),'Prop material slot set/count mismatch',path)
        require(all(s.get_editor_property('material_interface') == materials[str(s.get_editor_property('material_slot_name'))] for s in slots),'Persisted material mapping mismatch',path)
        box = mesh.get_bounding_box()
        bounds = [[getattr(v,c) for c in ('x','y','z')] for v in (box.min,box.max)]
        expected = dense['props'][path]['local_mesh_bounds_cm']
        error = max(abs(a-b) for x,y in zip(bounds,expected) for a,b in zip(x,y))
        require(error < .1,'Prop local bounds/pivot/unit mismatch',path,bounds,expected,error)
        report['props'].append(dict(asset=path,slots=actual_names,local_bounds_cm=bounds,maximum_bounds_error_cm=error,
            expected_body_relative_transform=dense['props'][path]['body_relative_transform']))
    report['status'] = 'validating_all_animation_frames'
    native_clips = {}
    for spec in bundle['clips']:
        path = spec['asset']
        if not VERIFY:
            options = unreal.FbxImportUI()
            for key,value in dict(import_mesh=False,import_as_skeletal=True,import_animations=True,import_materials=False,
                import_textures=False,skeleton=skeleton,mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION,
                automated_import_should_detect_type=False).items(): options.set_editor_property(key,value)
            data = options.anim_sequence_import_data; configure_coordinates(data)
            for key,value in dict(animation_length=unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME,
                use_default_sample_rate=True,import_bone_tracks=True,import_custom_attribute=False,
                add_curve_metadata_to_skeleton=False,preserve_local_transform=True).items(): data.set_editor_property(key,value)
            anim = import_fbx(spec['source_fbx'],path,options,unreal.AnimSequence)
            require(LIB.save_loaded_asset(anim,only_if_is_dirty=False),'Animation save failed',path)
        anim = strict_object(LIB.load_asset(path),path,unreal.AnimSequence)
        require(anim.get_editor_property('skeleton') == skeleton,'Animation skeleton mismatch')
        require(anim.get_editor_property('additive_anim_type') == unreal.AdditiveAnimationType.AAT_NONE,'Unexpected additive clip')
        length = anim.get_play_length()
        require(abs(length-spec['seconds']) < .002,'Imported duration mismatch',path,length,spec['seconds'])
        rows = []; maximum = {'position_cm':0.,'rotation_degrees':0.}
        for expected in dense['clips'][path]:
            bones = evaluate(anim,expected['seconds'],scientist,names)
            for name,transform in expected['bones'].items():
                cm,degrees = difference(bones[name],transform)
                require(cm < .2 and degrees < .5,'Dense native pose mismatch',path,expected['frame'],name,cm,degrees)
                maximum['position_cm'] = max(maximum['position_cm'],cm)
                maximum['rotation_degrees'] = max(maximum['rotation_degrees'],degrees)
            container = bones['Survivor_Rig']
            require(math.dist(container['translation_cm'],[0,0,0]) < .001 and abs(container['rotation_xyzw'][3]) > .999999,'Container transform changed')
            rows.append(dict(frame=expected['frame'],seconds=expected['seconds'],bones=bones))
        for name in ('root','LeftFoot','RightFoot') if spec['fixed_feet'] else ('root',):
            require(max(math.dist(r['bones'][name]['translation_cm'],rows[0]['bones'][name]['translation_cm']) for r in rows) < .15,'Unexpected root/fixed-foot motion',path,name)
        native_clips[path] = rows
        report['animations'].append(dict(asset=path,duration_seconds=length,source_frames=spec['frames'],sample_count=len(rows),
            checked_bones_per_frame=len(names),maximum_pose_errors=maximum,fixed_feet_required=spec['fixed_feet']))
        unreal.log('SCIENTIST_CLIP_AUDITED '+json.dumps(report['animations'][-1]))
    report['native_endpoint_checks'] = endpoint_checks(native_clips,position_limit=.02,angle_limit=.1)
    idle_path = read(BASE/'holster-reference/native-reference.json')['idle_clip'].split('.')[0]
    idle = strict_object(LIB.load_asset(idle_path),idle_path,unreal.AnimSequence)
    idle_pose = evaluate(idle,0.,scientist,names)
    for clip,index in [('Holster',0),('Unholster',-1)]:
        pose = native_clips[DEST+'/Animations/A_Scientist_'+clip+'_Cm'][index]['bones']
        for name in names:
            cm,degrees = difference(pose[name],idle_pose[name])
            require(cm < .2 and degrees < .5,'Native weapon-idle endpoint mismatch',clip,name,cm,degrees)
    require(all(sha(p) == h for p,h in bundle['provenance'].items()),'Authoring source changed during import')
    report['saved_bundle_sha256'] = {str(p.relative_to(CONTENT)):sha(p) for p in DEST_DISK.rglob('*') if p.is_file()}
    require(all(asset.removeprefix('/Game/')+'.uasset' in report['saved_bundle_sha256'] for asset in expected_assets),
            'A required output package was not saved')
    dense_report = REPORT.with_name(REPORT.stem+'-poses.json')
    require(not dense_report.exists(),'Preserve prior dense report')
    dense_report.parent.mkdir(parents=True,exist_ok=True)
    dense_report.write_text(json.dumps(native_clips,separators=(',',':'))+'\n')
    report['dense_native_pose_report'] = {'path':str(dense_report),'sha256':sha(dense_report)}
    report['ok'] = True
    report['status'] = 'fresh_readback_numeric_pass_native_render_required' if VERIFY else 'saved_fresh_process_readback_required'
    report['limitations'] = ['No gameplay, attachment, prop lifecycle or visual acceptance is performed.',
        'Native PBR constants are verified; CPU procedural micro-bump is not baked into these materials.',
        'Native rendered all-choice/Skip/hold/holster/contact and interruption checks remain required.']
except Exception as error:
    report['error'] = repr(error); report['traceback'] = traceback.format_exc()
    raise
finally:
    if before is not None:
        after = snapshot()
        changed = sorted(p for p in set(before)|set(after) if before.get(p) != after.get(p))
        report['original_assets_unchanged'],report['unexpected_content_changes'] = not changed,changed
        if changed:
            report['ok'] = False; report['status'] = 'FAILED_PROTECTED_CONTENT_CHANGED'
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('SCIENTIST_GESTURE_IMPORT_AUDIT '+json.dumps({'ok':report['ok'],'status':report['status'],
        'clips':len(report['animations']),'props':len(report['props']),'report':str(REPORT)}))
    require(report['ok'],'Prospector complete audit failed; see',REPORT)
