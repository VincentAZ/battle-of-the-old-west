"""Render existing Blender character sources for close material/anatomy review.

Run with Blender --background -noaudio --disable-autoexec --python this_file --
    --cards karli_blaze muse vera_vosh mutant --output <new review directory>
These are source lookdev renders, not evidence of the native game appearance.
No source model is edited or saved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cards', nargs='+', required=True)
    parser.add_argument('--source-root', type=Path, default=ROOT / 'art/characters/identities')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--poses', nargs='+', default=['rest'],
                        choices=['rest', 'turn-left', 'look-up', 'look-down', 'idle', 'rifle-idle', 'hit', 'walk'])
    parser.add_argument('--native-pose-export', type=Path,
                        help='Read-only native animation transform export for idle/rifle-idle/hit/walk source studies')
    parser.add_argument('--expressions', nargs='+', default=['neutral'],
                        choices=['neutral', 'blink', 'jaw-open', 'smile', 'happy', 'squint', 'brows-raised', 'brows-frown'])
    parser.add_argument('--views', nargs='+', default=['front', 'three-quarter'],
                        choices=['front', 'three-quarter', 'profile', 'back'])
    parser.add_argument('--hide-meshes', nargs='+', default=[],
                        help='Hide explicitly named meshes in this diagnostic render only')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    native_names = {'idle', 'rifle-idle', 'hit', 'walk'}
    if native_names.intersection(args.poses) and not args.native_pose_export:
        parser.error('Native poses require --native-pose-export')
    native = json.loads(args.native_pose_export.read_text()) if args.native_pose_export else None
    if native:
        sys.path.insert(0, str(ROOT / 'scripts'))
        from character_native_pose import apply_pose
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'scope': 'Blender source lookdev only; native review is still required.', 'cards': []}
    for card in args.cards:
        folder = args.source_root.resolve() / card
        manifest = json.loads((folder / 'manifest.json').read_text())
        # Resolve aliases before opening so Blender's //textures paths stay
        # relative to the original asset, not a review-directory symlink.
        source = (folder / (manifest['name'] + '.blend')).resolve()
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
        for name in args.hide_meshes:
            obj = bpy.data.objects.get(name)
            assert obj and obj.type == 'MESH', f'Missing diagnostic mesh: {name}'
            obj.hide_render = True
        missing_images = [bpy.path.abspath(image.filepath) for image in bpy.data.images
                          if image.source == 'FILE' and image.filepath
                          and not image.packed_file
                          and not Path(bpy.path.abspath(image.filepath)).is_file()]
        if missing_images:
            raise FileNotFoundError(f'Missing source textures: {missing_images}')
        scene = bpy.context.scene
        for obj in list(bpy.data.objects):
            if obj.type in {'LIGHT', 'CAMERA'}:
                bpy.data.objects.remove(obj, do_unlink=True)
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 4
        scene.render.resolution_x = scene.render.resolution_y = 1024
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.view_settings.view_transform = 'AgX'
        world = bpy.data.worlds.new('CharacterReviewWorld')
        world.use_nodes = True
        world.node_tree.nodes['Background'].inputs['Color'].default_value = (.18, .20, .22, 1)
        world.node_tree.nodes['Background'].inputs['Strength'].default_value = .35
        scene.world = world
        focus = Vector((0, -.02, 1.59))
        for name, location, energy, size in (
                ('Key', (-1.2, -1.8, 2.8), 110, 1.5),
                ('Fill', (1.3, -.8, 1.8), 45, 1.3),
                ('Rim', (.3, 1.2, 2.4), 85, 1.)):
            data = bpy.data.lights.new('Review' + name, 'AREA')
            data.energy, data.shape, data.size = energy, 'DISK', size
            light = bpy.data.objects.new(data.name, data)
            scene.collection.objects.link(light)
            light.location = location
            light.rotation_euler = (focus - light.location).to_track_quat('-Z', 'Y').to_euler()
        data = bpy.data.cameras.new('CharacterDetailReview')
        data.lens = 85
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        captures = []
        native_pose_checks = []
        arm = bpy.data.objects['Survivor_Rig']
        for pose in args.poses:
            arm.animation_data_clear()
            for bone in arm.pose.bones:
                bone.matrix_basis.identity()
            bpy.context.view_layer.update()
            focus = Vector((0, -.02, 1.59))
            if pose in native_names:
                native_pose_checks.append(apply_pose(arm, native, pose))
                focus = arm.matrix_world @ arm.pose.bones['mixamorig:Head'].head + Vector((0, 0, .04))
            elif pose != 'rest':
                axis, angle = {'turn-left': ('Z', 42), 'look-up': ('X', -22),
                               'look-down': ('X', 28)}[pose]
                for name, fraction in [('mixamorig:Neck', .35), ('mixamorig:Head', .65)]:
                    bone = arm.pose.bones[name]
                    pivot = bone.head.copy()
                    bone.matrix = (Matrix.Translation(pivot)
                                   @ Matrix.Rotation(math.radians(angle * fraction), 4, axis)
                                   @ Matrix.Translation(-pivot) @ bone.matrix)
                    bpy.context.view_layer.update()
            for expression in args.expressions:
                keys = bpy.data.objects['Survivor_Face_27Shapes'].data.shape_keys.key_blocks
                for key in list(keys)[1:]:
                    key.value = 0
                for key, value in {'neutral': {}, 'blink': {'Eyes_Closed_Max': 1.},
                                   'jaw-open': {'Jaw_Lower': .6, 'Mouth_Large_Opened': .35},
                                   'smile': {'Smile_Lips_Closed': .8},
                                   'happy': {'Happy': 1.}, 'squint': {'Eyes_Squint': 1.},
                                   'brows-raised': {'Eyebrows_Raised_Left': .85, 'Eyebrows_Raised_Right': .85},
                                   'brows-frown': {'Eyebrows_Frown_Left': .85, 'Eyebrows_Frown_Right': .85}}[expression].items():
                    assert key in keys, f'Missing facial expression {key}'
                    keys[key].value = value
                # Separate skinned facial hair exports matching morph names.
                # Drive the same expression on each mesh, as the combined
                # native skeletal mesh does, without changing the source file.
                for obj in bpy.data.objects:
                    if obj.type != 'MESH' or obj.find_armature() != arm or not obj.data.shape_keys:
                        continue
                    for key in list(obj.data.shape_keys.key_blocks)[1:]:
                        if key.name in keys:
                            key.value = keys[key.name].value
                bpy.context.view_layer.update()
                for name in args.views:
                    location = {'front': (0, -1.35, 1.64), 'three-quarter': (.72, -1.15, 1.66),
                                'profile': (1.35, -.10, 1.64), 'back': (0,1.35,1.64)}[name]
                    if pose in native_names:
                        offset = {'front': (0, -1.60, .14), 'three-quarter': (-1.48, -1.20, .15),
                                  'profile': (-1.8, -.15, .12), 'back': (0,1.6,.14)}[name]
                        location = focus + Vector(offset)
                    camera.location = location
                    camera.rotation_euler = (focus - camera.location).to_track_quat('-Z', 'Y').to_euler()
                    label = '-'.join(part for part in (pose, expression, name) if part not in ('rest', 'neutral'))
                    image = args.output / f'{card}-{label}.png'
                    scene.render.filepath = str(image)
                    bpy.ops.render.render(write_still=True)
                    captures.append(str(image))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == checksum
        report['cards'].append({'card': card, 'source': str(source), 'source_sha256': checksum,
                                'poses': args.poses, 'manual_poses_not_native_animation': any(p not in native_names for p in args.poses),
                                'native_pose_checks': native_pose_checks,
                                'native_pose_export_sha256': hashlib.sha256(args.native_pose_export.read_bytes()).hexdigest() if native else None,
                                'expressions': args.expressions,
                                'views': args.views,
                                'diagnostic_hidden_meshes': args.hide_meshes,
                                'captures': captures})
        (args.output / 'sources.json').write_text(json.dumps(report, indent=2) + '\n')
        print('CHARACTER_DETAIL_RENDERED', card, flush=True)


if __name__ == '__main__':
    main()
