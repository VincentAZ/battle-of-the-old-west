"""Add brows to derived identity copies without rebaking or changing their sources.

Blender --background --python-exit-code 1 --python this_file --
    --source-root <existing identities> --output <new folder> --cards muse
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_brows import STYLES, author_brows


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cards', nargs='+', choices=sorted(STYLES), required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True, exist_ok=False)
    reports = []
    for card in args.cards:
        folder = args.source_root.resolve()/card
        spec = json.loads((folder/'manifest.json').read_text())
        source = folder/(spec['name']+'.blend')
        source_hash = sha(source)
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
        for image in bpy.data.images:
            if image.filepath:
                image.filepath = bpy.path.abspath(image.filepath)
        arm = bpy.data.objects['Survivor_Rig']
        reference = [(bone.name, bone.parent.name if bone.parent else None,
                      tuple(tuple(row) for row in bone.matrix_local)) for bone in arm.data.bones]
        details = author_brows(card)
        assert reference == [(bone.name, bone.parent.name if bone.parent else None,
                              tuple(tuple(row) for row in bone.matrix_local)) for bone in arm.data.bones]
        out = args.output/card
        out.mkdir()
        blend = out/(spec['name']+'.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        spec['brows'] = details
        spec['materials'][details['material']] = details['material_spec']
        spec['material_names'].append(details['material'])
        spec['material_names'].sort()
        spec['total_triangles'] += details['added_triangles']
        spec['brow_source_blend'] = str(source)
        spec['brow_source_sha256'] = source_hash
        spec['status'] = 'surface-bound brow candidate; source and native expression review required'
        meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.find_armature() == arm]
        assert bpy.data.objects['Survivor_Face_27Shapes'] in meshes
        scale = Matrix.Scale(100, 4)
        for obj in [arm]+meshes:
            if obj.type == 'MESH':
                obj.data.transform(scale, shape_keys=True)
            else:
                obj.data.transform(scale)
            obj.location *= 100
            inverse = obj.matrix_parent_inverse.copy()
            inverse.translation *= 100
            obj.matrix_parent_inverse = inverse
        bpy.context.scene.unit_settings.scale_length = .01
        bpy.context.view_layer.update()
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in [arm]+meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = arm
        fbx = out/(spec['name']+'_Cm.fbx')
        bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True,
            object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False,
            use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE',
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
        spec['fbx_sha256'] = sha(fbx)
        assert sha(source) == source_hash
        (out/'manifest.json').write_text(json.dumps(spec, indent=2)+'\n')
        reports.append({'card_id': card, 'source_sha256': source_hash,
                        'blend_sha256': sha(blend), 'fbx_sha256': spec['fbx_sha256'], 'brows': details})
    (args.output/'authoring-report.json').write_text(json.dumps(reports, indent=2)+'\n')


if __name__ == '__main__':
    main()
