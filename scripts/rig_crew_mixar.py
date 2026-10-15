"""Rig an approved Crew source without changing its geometry, UVs or materials.

Run with Mixar --background --factory-startup --python-exit-code 1 --python
scripts/rig_crew_mixar.py -- SLUG [--settings JSON] [--mapping JSON]. Root owns
remote rig jobs. This script reads the downloaded guide and never submits jobs.
Settings may define rigid_regions with name,parent, vertex_indices or axis/min/max,
plus motion_constraints. A region must select complete polygons. Held weapons need
reviewed masks and separate hand-contact animation QA; successful binding is not
animation approval. New files only under --output (default playable-v001/SLUG).
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from mixar.modules.hunyuan.constants import ANIMATE_IMPORT_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from crew_rig_mapping import infer_mapping, canonical_parents, FINGERS
from weather_drifter_review import geometry_hash


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def appearance(obj):
    """Exact coordinates/topology/UV, material assignment/nodes, and texture bytes."""
    materials = []
    for material in obj.data.materials:
        nodes = []
        for node in material.node_tree.nodes:
            defaults = []
            for socket in node.inputs:
                if hasattr(socket, 'default_value'):
                    value = socket.default_value
                    if not isinstance(value, (int, float, str, bool)):
                        try: value = list(value)
                        except TypeError: value = str(value)
                    defaults.append((socket.name, value))
            image = getattr(node, 'image', None)
            image_hash = None
            if image:
                if image.packed_file: image_hash = hashlib.sha256(image.packed_file.data).hexdigest()
                else: image_hash = sha(bpy.path.abspath(image.filepath))
            nodes.append((node.name, node.bl_idname, defaults, image_hash))
        links = sorted((l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in material.node_tree.links)
        materials.append((material.name, nodes, links))
    result = dict(geometry_uv=geometry_hash(obj), materials=materials,
                  material_indices=[p.material_index for p in obj.data.polygons],
                  vertex_normals=[list(v.normal) for v in obj.data.vertices])
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def bounds(points):
    return Vector([min(v[i] for v in points) for i in range(3)]), Vector([max(v[i] for v in points) for i in range(3)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('slug')
    parser.add_argument('--approval', type=Path, default=ROOT/'art/western/crew/review-v003/appearance-approval.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--guide', type=Path)
    parser.add_argument('--settings', type=Path)
    parser.add_argument('--mapping', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use installed authenticated Mixar application'
    record = json.loads(args.approval.read_text())['projects'][args.slug]
    source = ROOT/record['path']
    assert sha(source) == record['sha256'], 'Approved source hash mismatch'
    name = record.get('asset_name', ''.join(p.capitalize() for p in args.slug.split('-')))
    output = (args.output or ROOT/'art/western/crew/playable-v001'/args.slug).resolve()
    assert output != source.parent and source.parent not in output.parents, 'Never write inside approved review'
    output.mkdir(parents=True, exist_ok=True)
    write(output/'rig-validation.json', dict(status='in_progress', slug=args.slug, source_project_sha256=sha(source)))
    guide_path = args.guide or output/'rigged-original.glb'
    settings = json.loads(args.settings.read_text()) if args.settings else {}
    if args.slug in ('coach-guard', 'gatling-gunner'):
        assert settings.get('rigid_regions') and settings.get('motion_constraints'), 'Prop pilot requires explicit rigid mask and motion constraints'
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    obj = bpy.data.objects[args.slug.replace('-', '_')+'_Appearance_Review']
    original_hash = appearance(obj)
    geometry = geometry_hash(obj)
    original_world = obj.matrix_world.copy()
    target_positions = [obj.matrix_world@v.co for v in obj.data.vertices]
    assert not obj.vertex_groups and not any(m.type == 'ARMATURE' for m in obj.modifiers)
    assert not bpy.data.actions and not bpy.data.armatures, 'Approved source must be static'
    assert len(obj.data.materials) == 1, 'Expected one approved atlas material'
    tmin, tmax = bounds(target_positions)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(guide_path), **ANIMATE_IMPORT_OPTIONS)
    arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(arms) == 1 and meshes, 'Expected one guide armature and mesh'
    raw_arm = arms[0]
    raw_positions = [o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    rmin, rmax = bounds(raw_positions)
    scale = (tmax.z-tmin.z)/(rmax.z-rmin.z)
    translation = (tmin+tmax)/2-scale*(rmin+rmax)/2
    alignment = Matrix.Translation(translation)@Matrix.Scale(scale, 4)
    world = alignment@raw_arm.matrix_world
    guide = {b.name: dict(head=world@b.head_local, tail=world@b.tail_local,
             matrix=world@b.matrix_local, parent=b.parent.name if b.parent else None) for b in raw_arm.data.bones}
    diagnostic = [dict(name=n, parent=g['parent'], head=list(g['head']), tail=list(g['tail'])) for n, g in guide.items()]
    write(output/'guide-bones.json', diagnostic)
    mapping = json.loads(args.mapping.read_text()) if args.mapping else infer_mapping(diagnostic)
    assert set(mapping) == set(guide), 'Explicit mapping must cover every guide bone'
    write(output/'bone-mapping.json', mapping)
    tree = KDTree(len(raw_positions))
    weights = []
    for raw in meshes:
        for v in raw.data.vertices:
            tree.insert(alignment@(raw.matrix_world@v.co), len(weights))
            values = {}
            for group in v.groups:
                bone = mapping[raw.vertex_groups[group.group].name]
                values[bone] = values.get(bone, 0)+group.weight
            weights.append(values)
    tree.balance()
    rest = {}
    for original, g in guide.items():
        rest.setdefault(mapping[original], g.copy())
    rest['Hips']['head'] = (rest['LeftUpLeg']['head']+rest['RightUpLeg']['head'])/2
    rest['Hips']['tail'] = rest['Spine']['head']
    if 'Spine2' not in rest:
        rest['Spine2'] = dict(head=rest['Spine1']['head'].lerp(rest['Neck']['head'], .55), tail=rest['Neck']['head'], matrix=rest['Spine1']['matrix'])
    parents = canonical_parents()
    for n, g in settings.get('additional_rest_bones', {}).items():
        assert n in parents and (n not in rest or settings.get('override_existing_rest_bones')), 'Existing rest bone override requires explicit setting: '+n
        rest[n] = dict(head=Vector(g['head']), tail=Vector(g['tail']), matrix=Matrix.Identity(4))
    synthesized = []
    if settings.get('synthesize_missing_bones'):
        for n, parent in parents.items():
            if n in rest: continue
            if n.endswith('ToeBase'):
                ankle = rest[parent]['head']
                head = Vector((ankle.x, ankle.y-.12, tmin.z+.01))
                rest[n] = dict(head=head, tail=head+Vector((0,-.06,0)), matrix=rest[parent]['matrix'])
                synthesized.append(n)
                continue
            assert 'Hand' in n and n[-1].isdigit() or n.endswith('ToeBase'), 'Cannot synthesize missing major anatomy: '+n
            previous = rest[parent]
            direction = (previous['tail']-previous['head']).normalized()
            head = previous['tail'].copy()
            rest[n] = dict(head=head, tail=head+direction*.015, matrix=previous['matrix'])
            synthesized.append(n)
    assert set(rest) == set(parents), 'Unknown/missing anatomical mapping'
    for side in ('Left','Right'): rest[side+'Foot']['tail'] = rest[side+'ToeBase']['head'].copy()
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    obj = bpy.data.objects[args.slug.replace('-', '_')+'_Appearance_Review']
    region_indices = {}
    claimed = set()
    for region in settings.get('rigid_regions', []):
        if 'vertex_indices' in region:
            assert settings.get('source_geometry_uv_sha256') == geometry, 'Explicit vertex masks require source geometry fingerprint'
            indices = set(region['vertex_indices'])
        else:
            axis = 'xyz'.index(region['axis'])
            indices = {i for i, p in enumerate(target_positions) if region.get('min', -float('inf')) <= p[axis] <= region.get('max', float('inf'))}
        assert indices and min(indices) >= 0 and max(indices) < len(target_positions)
        assert not indices & claimed, 'Rigid regions overlap'
        cut_polygons = sum(bool(set(p.vertices)&indices) and not set(p.vertices)<=indices for p in obj.data.polygons)
        assert not cut_polygons or (region.get('allow_polygon_boundary') and region.get('boundary_note')), 'Mask cuts through a polygon; require documented boundary paint and stress validation'
        claimed |= indices
        region_indices[region['name']] = indices
        assert region['name'] not in parents and region['parent'] in {'root', *parents}
        parents[region['name']] = region['parent']
        center = sum((target_positions[i] for i in indices), Vector())/len(indices)
        rest[region['name']] = dict(head=center, tail=center+Vector((0, 0, .1)), matrix=Matrix.Identity(4))
    arm_data = bpy.data.armatures.new(name+'_Skeleton')
    arm = bpy.data.objects.new('Armature', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    root = arm_data.edit_bones.new('root')
    root.head, root.tail = (0, 0, 0), (0, 0, .15)
    for n in parents:
        g = rest[n]
        bone = arm_data.edit_bones.new(n)
        bone.head, bone.tail = g['head'], g['tail']
        if n == 'Head': bone.tail = bone.head+Vector((0, 0, .17))
        if n.endswith('ToeBase'): bone.tail = bone.head+Vector((0, -.06, 0))
        if (bone.tail-bone.head).length < .0001: bone.tail = bone.head+Vector((0, 0, .01))
        bone.align_roll(g['matrix'].to_3x3()@Vector((0, 0, 1)))
    for n, parent in parents.items(): arm_data.edit_bones[n].parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for n in ['root', *parents]: obj.vertex_groups.new(name=n)
    rigid_lookup = {i: n for n, ids in region_indices.items() for i in ids}
    overrides = {}
    for override in settings.get('weight_overrides', []):
        assert settings.get('source_geometry_uv_sha256') == geometry, 'Weight overrides require exact source geometry fingerprint'
        assert set(override['weights']) <= set(parents), 'Unknown override bone'
        for i in override['vertex_indices']:
            assert 0 <= i < len(target_positions) and i not in overrides and i not in rigid_lookup, 'Invalid or overlapping weight override'
            overrides[i] = override['weights']
    distances = []
    influences = []
    for v, co in zip(obj.data.vertices, target_positions):
        _, i, distance = tree.find(co)
        distances.append(distance)
        w = {rigid_lookup[v.index]: 1} if v.index in rigid_lookup else overrides.get(v.index, weights[i])
        w = dict(sorted(((n, a) for n, a in w.items() if a > .001), key=lambda pair: pair[1], reverse=True)[:4])
        total = sum(w.values())
        assert total > 0, 'Unweighted vertex '+str(v.index)
        influences.append(len(w))
        for n, weight in w.items(): obj.vertex_groups[n].add([v.index], weight/total, 'REPLACE')
    assert max(distances) < .00002, f'Guide does not match approved mesh: {max(distances):.9f}m'
    obj.parent = arm
    obj.matrix_world = original_world
    modifier = obj.modifiers.new(name+' skin', 'ARMATURE')
    modifier.object = arm
    modifier.use_deform_preserve_volume = False
    for bone in arm.pose.bones: bone.rotation_mode = 'QUATERNION'
    arm.show_in_front = True
    assert appearance(obj) == original_hash, 'Approved appearance changed'
    bpy.context.view_layer.update()
    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = evaluated_obj.to_mesh()
    assert len(evaluated.vertices) == len(obj.data.vertices)
    error = max((a.co-b.co).length for a, b in zip(obj.data.vertices, evaluated.vertices))
    evaluated_obj.to_mesh_clear()
    assert error < .00001, f'Bind pose changed: {error}m'
    obj.data.calc_loop_triangles()
    triangles = len(obj.data.loop_triangles)
    project = output/(name+'-Rigged.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    # Verify the saved editable source before any disposable export transform.
    bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
    obj = bpy.data.objects[args.slug.replace('-', '_')+'_Appearance_Review']
    arm = bpy.data.objects['Armature']
    assert appearance(obj) == original_hash and not bpy.data.actions
    assert len(arm.data.bones) == len(parents)+1
    assert all(abs(sum(g.weight for g in v.groups)-1) < 1e-5 for v in obj.data.vertices)
    exports = output/'exports'
    exports.mkdir(exist_ok=True)
    textures = list((source.parent/'textures').glob('*.png'))
    assert len(textures) == 3, 'Expected three approved atlas textures'
    for path in textures:
        suffix = next((s for s in ('BaseColor', 'ORM', 'Normal') if path.stem.lower().endswith('_'+s.lower())), None)
        assert suffix, 'Unrecognized texture '+path.name
        destination = exports/('T_'+name+'_'+suffix+'.png')
        shutil.copy2(path, destination)
        assert sha(destination) == sha(path), 'Texture bytes changed during export'
    unit = Matrix.Scale(100, 4)
    for item in (obj, arm):
        item.data.transform(unit)
        item.location *= 100
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fbx = exports/('SK_'+name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False, use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
    report = dict(status='passed', stage='rig_binding_only', slug=args.slug,
        source_project_sha256=sha(source), source_sha256=sha(source), project_sha256=sha(project),
        guide_sha256=sha(guide_path), source_geometry_uv_sha256=geometry,
        source_appearance_sha256=original_hash, rig_bones=len(parents)+1,
        bone_mapping=mapping, bind_pose_max_error_m=error,
        nearest_guide_max_error_m=max(distances), maximum_vertex_influences=max(influences),
        triangles=triangles, saved_source_reopened=True,
        alignment=dict(scale=scale, translation=list(translation)),
        rigid_regions={n: len(v) for n, v in region_indices.items()},
        motion_constraints=settings.get('motion_constraints', []),
        freeze_bones=sorted(set(settings.get('freeze_bones', [])) | {side+'Hand'+finger+str(digit) for side in ('Left', 'Right') for finger in FINGERS for digit in range(1,4)}),
        synthesized_unweighted_bones=synthesized,
        locally_placed_rest_bones=settings.get('additional_rest_bones', {}),
        weight_override_vertices=len(overrides),
        finger_animation_policy='All finger local bind transforms preserved; body clips do not require finger gestures.',
        settings_sha256=sha(args.settings) if args.settings else None,
        mapping_method='inspected_explicit' if args.mapping else 'topology_and_anatomical_positions',
        guide_mapping_notes=settings.get('guide_mapping_notes', []),
        animation_qa_status='pending',
        files={p.name: sha(p) for p in exports.iterdir() if p.is_file()})
    write(output/'rig-validation.json', report)
    print('CREW_RIGGED', json.dumps({k: v for k, v in report.items() if k not in ('files', 'bone_mapping')}), flush=True)


if __name__ == '__main__':
    main()
