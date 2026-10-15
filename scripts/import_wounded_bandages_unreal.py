"""Import separate dressings using existing skeletons; never save source assets.

UnrealEditor-Cmd -run=pythonscript -script=<this>. Optional
OLDWEST_BANDAGE_SLUGS selects a comma-separated prototype subset.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get('OLDWEST_BANDAGE_SOURCE', str(ROOT / 'art/western/bandages/review-v002')))
CONTENT = ROOT / 'game/OldWest/Content'
DEST = '/Game/Art/Western/Bandages'
DISK = CONTENT / 'Art/Western/Bandages'
LIB = unreal.EditorAssetLibrary
MAT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot():
    return {str(p.relative_to(CONTENT)): sha(p) for p in CONTENT.rglob('*')
            if p.is_file() and not p.is_relative_to(DISK)}


def props(obj, **values):
    for key, value in values.items():
        obj.set_editor_property(key, value)


def save(obj):
    assert obj.get_path_name().startswith(DEST + '/'), 'Only new dressing assets may be saved'
    assert LIB.save_loaded_asset(obj, only_if_is_dirty=False)


before = snapshot()
report = dict(ok=False, preserved_content=before, imported=[])
selected = os.environ.get('OLDWEST_BANDAGE_SLUGS')
suffix = '-' + hashlib.sha256(selected.encode()).hexdigest()[:12] if selected else ''
(BASE / ('content-before' + suffix + '.json')).write_text(json.dumps(before, indent=2) + '\n')
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    material = LIB.load_asset(DEST + '/M_Muslin') if LIB.does_asset_exist(DEST + '/M_Muslin') else TOOLS.create_asset('M_Muslin', DEST, unreal.Material, unreal.MaterialFactoryNew())
    MAT.delete_all_material_expressions(material)
    props(material, two_sided=True, blend_mode=unreal.BlendMode.BLEND_OPAQUE)
    colour = MAT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    props(colour, constant=unreal.LinearColor(.72, .69, .61, 1))
    assert MAT.connect_material_property(colour, '', unreal.MaterialProperty.MP_BASE_COLOR)
    for value, property_name in [(.88, unreal.MaterialProperty.MP_ROUGHNESS), (.25, unreal.MaterialProperty.MP_SPECULAR)]:
        node = MAT.create_material_expression(material, unreal.MaterialExpressionConstant)
        props(node, r=value)
        assert MAT.connect_material_property(node, '', property_name)
    MAT.set_base_material_usage(material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH, True)
    MAT.recompile_material(material)
    save(material)
    manifest = os.environ.get('OLDWEST_BANDAGE_MANIFEST')
    records = [ROOT/p for p in json.loads(Path(manifest).read_text())['characters'].values()] if manifest else sorted(BASE.glob('*/authoring.json'))
    if selected:
        wanted = set(selected.split(','))
        records = [p for p in records if p.parent.name in wanted]
        assert {p.parent.name for p in records} == wanted
    else:
        assert len(records) == 47, 'All 46 people and generic Drifter are required'
    for path in records:
        data = json.loads(path.read_text())
        name = data['name']
        project = path.parent / ('Bandage_' + name + '.blend')
        fbx = path.parent / 'exports' / ('SK_Bandage_' + name + '.fbx')
        assert sha(project) == data['project_sha256'] and sha(fbx) == data['fbx_sha256']
        assert sha(ROOT / data['source']) == data['source_sha256']
        body_folder = '/Game/Art/Western/' + (name if name in ('Quanah', 'Lozen', 'Sarah', 'Drifter') else 'Crew/' + name)
        body = LIB.load_asset(body_folder + '/SK_' + name)
        assert isinstance(body, unreal.SkeletalMesh)
        skeleton = body.get_editor_property('skeleton')
        options = unreal.FbxImportUI()
        props(options, import_mesh=True, import_as_skeletal=True,
              mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,
              import_materials=False, import_textures=False, import_animations=False,
              automated_import_should_detect_type=False, create_physics_asset=False,
              skeleton=skeleton)
        props(options.skeletal_mesh_import_data,
              update_skeleton_reference_pose=False, use_t0_as_ref_pose=False,
              import_translation=unreal.Vector(0, 0, 0), import_rotation=unreal.Rotator(0, 0, 0),
              import_uniform_scale=1., convert_scene=True, force_front_x_axis=False,
              convert_scene_unit=True, preserve_smoothing_groups=True,
              normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        task = unreal.AssetImportTask()
        props(task, filename=str(fbx), destination_path=DEST,
              destination_name=fbx.stem, automated=True, replace_existing=False,
              save=False, options=options, factory=unreal.FbxFactory())
        existing = LIB.does_asset_exist(DEST + '/' + fbx.stem)
        if existing:
            mesh = LIB.load_asset(DEST + '/' + fbx.stem)
            filenames = mesh.get_editor_property('asset_import_data').extract_filenames()
            assert len(filenames) == 1 and Path(filenames[0]).resolve().is_relative_to(ROOT/'art/western/bandages'), 'Only this task-owned accessory may be revised'
            reimport = Path(filenames[0]).resolve() != fbx.resolve()
            if reimport:
                assert os.environ.get('OLDWEST_BANDAGE_REIMPORT') == '1', 'Versioned accessory reimport must be explicit'
                archive = BASE/'unreal-before'
                archive.mkdir(exist_ok=True)
                for prior in DISK.glob(fbx.stem+'.*'):
                    assert not (archive/prior.name).exists(), 'Preserve the previous imported accessory bytes'
                    shutil.copy2(prior, archive/prior.name)
                props(task, replace_existing=True)
        else:
            reimport = False
        if not existing or reimport:
            TOOLS.import_asset_tasks([task])
            mesh = next(o for o in task.get_objects() if isinstance(o, unreal.SkeletalMesh))
        assert mesh.get_editor_property('skeleton') == skeleton
        slots = mesh.get_editor_property('materials')
        assert len(slots) == 1
        props(slots[0], material_interface=material)
        props(mesh, materials=slots, physics_asset=None)
        save(mesh)
        body_component, bandage_component = unreal.SkeletalMeshComponent(), unreal.SkeletalMeshComponent()
        body_component.set_skeletal_mesh_asset(body)
        bandage_component.set_skeletal_mesh_asset(mesh)
        names = lambda c: [str(c.get_bone_name(i)) for i in range(c.get_num_bones())]
        assert names(body_component) == names(bandage_component), 'Leader-pose bone mapping mismatch'
        errors = dict(translation_cm=0., quaternion=0., scale=0.)
        for i in range(body_component.get_num_bones()):
            a, b = body_component.get_ref_pose_transform(i), bandage_component.get_ref_pose_transform(i)
            xyz = lambda p: [p.x, p.y, p.z]
            qa, qb = [a.rotation.x,a.rotation.y,a.rotation.z,a.rotation.w], [b.rotation.x,b.rotation.y,b.rotation.z,b.rotation.w]
            errors['translation_cm'] = max(errors['translation_cm'], math.dist(xyz(a.translation), xyz(b.translation)))
            errors['quaternion'] = max(errors['quaternion'], min(math.dist(qa,qb), math.dist(qa,[-v for v in qb])))
            errors['scale'] = max(errors['scale'], math.dist(xyz(a.scale3d),xyz(b.scale3d)))
        assert errors['translation_cm'] < .001 and errors['quaternion'] < .0001 and errors['scale'] < .00001, ('Bind pose mismatch', data['slug'], errors)
        report['imported'].append(dict(slug=data['slug'], mesh=mesh.get_path_name(),
            body=body.get_path_name(), skeleton=skeleton.get_path_name(), bones=names(bandage_component),
            source_project_sha256=data['project_sha256'], reference_pose_errors=errors))
    assert snapshot() == before, 'Pre-existing Content changed'
    report['ok'] = True
except Exception:
    report['error'] = traceback.format_exc()
    raise
finally:
    report['preserved_content_unchanged'] = snapshot() == before
    (BASE / ('unreal-import' + suffix + '.json')).write_text(json.dumps(report, indent=2) + '\n')
