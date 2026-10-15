"""Derive Scout/Punk crest candidates from their current reviewed hand sources."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates, weights
from author_vigilante_headgear_candidate import remove_components
from character_crests import fitted_crest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def author(item, inspected, output):
    source = Path(item['source_blend'])
    assert sha(source) == item['source_blend_sha256'] == inspected['source_sha256']
    assert sha(item['source_fbx']) == item['source_fbx_sha256'] and sha(item['native_path']) == item['native_sha256']
    folder = output/item['card_id']
    folder.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:
            image.filepath = bpy.path.abspath(image.filepath)
    arm = bpy.data.objects['Survivor_Rig']
    outfit = bpy.data.objects[inspected['outfit']]
    face = bpy.data.objects['Survivor_Face_27Shapes']
    protected = {o.name: (coordinates(o), weights(o), [tuple(n.vector) for n in o.data.corner_normals])
                 for o in bpy.data.objects if o.type == 'MESH' and o != outfit}
    rig = [(b.name, b.parent.name if b.parent else None, tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    old = inspected['mesh_components_above_1_7m']
    assert len(old) == 9 and all(len(c['vertices']) == 1106 and c['groups'] == ['mixamorig:Head'] for c in old)
    blocks = [dict(indices=c['vertices'], bounds_m=list(zip(c['bounds_min'], c['bounds_max']))) for c in old]
    selected = set(old[4]['vertices'])
    polygon = max((p for p in outfit.data.polygons if all(i in selected for i in p.vertices)), key=lambda p: p.area)
    uv_layer = outfit.data.uv_layers.active
    atlas_uv = [sum(uv_layer.data[i].uv[k] for i in polygon.loop_indices)/len(polygon.loop_indices) for k in (0, 1)]
    added, fitting = fitted_crest(face, arm, outfit.data.materials[0], item['name']+'_Fitted_Crest',
                                  long=item['card_id'] == 'punk', atlas_uv=atlas_uv)
    removal = remove_components(outfit, blocks)
    assert protected == {name: (coordinates(bpy.data.objects[name]), weights(bpy.data.objects[name]),
                               [tuple(n.vector) for n in bpy.data.objects[name].data.corner_normals]) for name in protected}
    assert rig == [(b.name, b.parent.name if b.parent else None, tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    spec = json.loads((source.parent/'manifest.json').read_text())
    spec['parts'] = [p for p in spec['parts'] if not p['name'].startswith('Mohawk_Lock')]
    spec['parts'].append(dict(name=added.name, vertices=len(added.data.vertices), bones=['mixamorig:Head']))
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
    spec['total_triangles'] = sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
    spec['outfit_triangles'] = sum(len(p.vertices)-2 for o in (outfit, added) for p in o.data.polygons)
    spec['crest_correction'] = dict(removal=removal, fitting={k:v for k,v in fitting.items() if k != 'roots'})
    spec['status'] = 'Scalp-fitted strand crest candidate; source, expression and native review required'
    blend = folder/(item['name']+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale = Matrix.Scale(100, 4)
    for obj in [arm]+meshes:
        obj.data.transform(scale, shape_keys=True) if obj.type == 'MESH' else obj.data.transform(scale)
        obj.location *= 100
        inverse = obj.matrix_parent_inverse.copy(); inverse.translation *= 100; obj.matrix_parent_inverse = inverse
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fbx = folder/(item['name']+'_Cm.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE','MESH'},
        add_leaf_bones=False, bake_anim=False, use_armature_deform_only=True, use_mesh_modifiers=False,
        mesh_smooth_type='FACE', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
    assert sha(source) == item['source_blend_sha256'] and sha(item['source_fbx']) == item['source_fbx_sha256']
    assert sha(item['native_path']) == item['native_sha256']
    spec['fbx_sha256'] = sha(fbx)
    (folder/'manifest.json').write_text(json.dumps(spec, indent=2)+'\n')
    report = dict(**item, blend=str(blend), blend_sha256=sha(blend), fbx=str(fbx), fbx_sha256=sha(fbx),
                  removal=removal, fitting=fitting, other_meshes_preserved=True, rig_preserved=True,
                  hand_correction_preserved=True, source_files_unchanged=True, native_imported=False)
    (folder/'authoring-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('CREST_CANDIDATE', item['card_id'], fitting['strands'], fitting['triangles'], flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inspection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output = args.output.resolve(); args.output.mkdir(parents=True, exist_ok=False)
    inspection = json.loads(args.inspection.read_text())['cards']
    cards = [author(item, next(c for c in inspection if c['card_id'] == item['card_id']), args.output)
             for item in json.loads(args.inputs.read_text())['cards']]
    (args.output/'authoring-report.json').write_text(json.dumps(dict(cards=cards), indent=2)+'\n')
