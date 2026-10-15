"""Prepare the single Drifter's appearance review inside Mixar.

Run with Mixar --background --factory-startup --python-exit-code 1
    --python scripts/prepare_drifter_review.py -- --source MODEL.glb --output DIR

This creates an unrigged review source and eight honest renders of that mesh.
It does not import into Unreal, animate, or alter any existing game asset.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(meshes):
    points = [ob.matrix_world @ Vector(p) for ob in meshes for p in ob.bound_box]
    return (Vector([min(p[i] for p in points) for i in range(3)]),
            Vector([max(p[i] for p in points) for i in range(3)]))


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--heading-degrees', type=float, default=270,
                        help='Inspected Drifter result faces +X after glTF import; turn it toward -Y')
    parser.add_argument('--samples', type=int, default=32)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use the installed Mixar executable'
    source = args.source.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    textures = out / 'textures'
    textures.mkdir()
    previews = out / 'previews'
    previews.mkdir()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH']
    assert meshes, 'No generated mesh was imported'
    assert not any(ob.type == 'ARMATURE' for ob in bpy.context.scene.objects), 'Appearance checkpoint precedes rigging'
    rotation = Matrix.Rotation(math.radians(args.heading_degrees), 4, 'Z')
    for ob in meshes:
        transform = ob.matrix_world.copy()
        ob.parent = None
        ob.matrix_world = rotation @ transform
    bpy.context.view_layer.update()
    lo, hi = bounds(meshes)
    # Height includes the hat; uniform scaling preserves the approved proportions.
    factor = 1.85 / (hi.z - lo.z)
    shift = Vector((-(hi.x + lo.x) / 2, -(hi.y + lo.y) / 2, -lo.z))
    for ob in meshes:
        ob.matrix_world = Matrix.Scale(factor, 4) @ Matrix.Translation(shift) @ ob.matrix_world
    bpy.ops.object.select_all(action='DESELECT')
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    character = bpy.context.object
    character.name = 'Drifter_Appearance_Review'
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    character.data.calc_loop_triangles()
    original_triangles = len(character.data.loop_triangles)
    if original_triangles > 30000:
        modifier = character.modifiers.new('Review budget: preserve original GLB separately', 'DECIMATE')
        modifier.ratio = 29500 / original_triangles
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    character.data.calc_loop_triangles()
    triangle_count = len(character.data.loop_triangles)
    assert triangle_count <= 30000, f'Triangle budget exceeded: {triangle_count}'
    assert len(character.data.materials) == 1, 'Review requires a single shared material atlas'
    assert character.data.uv_layers, 'Generated mesh has no UV map'
    material = character.data.materials[0]
    material.name = 'M_Drifter_Review'
    for node in material.node_tree.nodes:
        if node.type == 'NORMAL_MAP':
            node.inputs['Strength'].default_value = .3
        if node.type == 'BSDF_PRINCIPLED':
            # Cloth, leather and felt stay matte; retain supplied roughness variation.
            # The small dull buckle does not need its own material.
            for link in list(node.inputs['Metallic'].links):
                material.node_tree.links.remove(link)
            node.inputs['Metallic'].default_value = 0
            # Generated gloves/boots are too glossy in the studio. Retain the
            # atlas variation but enforce the worn natural-material finish.
            roughness = node.inputs['Roughness']
            if roughness.is_linked:
                source_socket = roughness.links[0].from_socket
                clamp = material.node_tree.nodes.new('ShaderNodeMath')
                clamp.name = 'Worn_material_roughness_floor'
                clamp.operation = 'MAXIMUM'
                clamp.inputs[1].default_value = .6
                material.node_tree.links.new(source_socket, clamp.inputs[0])
                material.node_tree.links.new(clamp.outputs[0], roughness)
            else:
                roughness.default_value = max(.6, roughness.default_value)
    image_records = []
    seen = set()
    for node in material.node_tree.nodes:
        if node.type != 'TEX_IMAGE' or not node.image or node.image.as_pointer() in seen:
            continue
        image = node.image
        seen.add(image.as_pointer())
        original_size = list(image.size)
        channel = 'Texture_' + str(len(image_records) + 1)
        for link in material.node_tree.links:
            if link.from_node == node:
                if link.to_socket.name == 'Base Color':
                    channel = 'BaseColor'
                elif link.to_node.type == 'NORMAL_MAP':
                    channel = 'Normal'
                elif link.to_node.type in {'SEPARATE_COLOR', 'SEPRGB'}:
                    channel = 'ORM'
        image.name = 'T_Drifter_' + channel
        if tuple(image.size) != (2048, 2048):
            image.scale(2048, 2048)
        path = textures / (image.name + '.png')
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()
        # glTF imports carry the original packed bytes. Repacking without
        # removing them leaves the 4K source embedded after reopening.
        if image.packed_file:
            image.unpack(method='REMOVE')
        image.filepath_raw = str(path)
        image.reload()
        assert tuple(image.size) == (2048, 2048)
        image.pack()
        image_records.append({'channel': channel, 'source_size': original_size,
                              'size': list(image.size), 'file': str(path.relative_to(out)),
                              'sha256': digest(path)})
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 12
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('Drifter neutral studio')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.28, .31, .35, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .45
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=2000)
    floor = bpy.context.object
    floor.name = 'Review_only_ground'
    ground_material = bpy.data.materials.new('Review_only_matte_ground')
    ground_material.use_nodes = True
    bsdf = ground_material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (.20, .23, .25, 1)
    bsdf.inputs['Roughness'].default_value = .9
    floor.data.materials.append(ground_material)
    for name, location, energy, size in (
        ('Key', (-3.5, -4, 6), 650, 4.0),
        ('Fill', (4, -2, 3.5), 300, 3.5),
        ('Rim', (0, 4, 5.5), 750, 3.0),
    ):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.shape, data.size = energy, 'DISK', size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        aim(light, (0, 0, 1))
    lo, hi = bounds([character])
    focus = (0, 0, (hi.z + lo.z) * .5)
    views = {
        'front': ((0, -12, 1.1), 2.65, focus),
        'side': ((-12, 0, 1.1), 2.65, focus),
        'rear': ((0, 12, 1.1), 2.65, focus),
        'three-quarter': ((-4, -7, 2.9), 2.65, focus),
        'game-camera': ((-5.2, -7, 7.0), 5.3, focus),
        'face-detail': ((-.35, -5, 1.95), .95, (0, 0, 1.60)),
        'hands-detail': ((0, -5, .85), 1.6, (0, 0, .82)),
        'underside-diagnostic': ((0, -4, -2), 2.9, focus),
    }
    cameras = {}
    for name, (location, ortho_scale, target) in views.items():
        data = bpy.data.cameras.new('Review_' + name)
        data.type = 'ORTHO'
        data.ortho_scale = ortho_scale
        data.clip_end = 1000
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
        camera.location = location
        aim(camera, target)
        cameras[name] = camera
    scene.camera = cameras['three-quarter']
    bpy.ops.object.select_all(action='DESELECT')
    character.select_set(True)
    bpy.context.view_layer.objects.active = character
    # Only the review character is selected for subsequent export; stage is distinct.
    character['review_status'] = 'Awaiting appearance approval; not rigged or game-integrated'
    character['source_generator'] = 'Mixar / Tripo Pro'
    for area in (bpy.context.screen.areas if bpy.context.screen else []):
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.shading.type = 'MATERIAL'
    project = out / 'Drifter-Review.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    manifest = {
        'stage': 'A: appearance review', 'status': 'awaiting_user_review',
        'source_glb': str(source), 'source_sha256': digest(source),
        'authoring_application': bpy.app.binary_path, 'application_version': bpy.app.version_string,
        'project': project.name, 'project_sha256': digest(project),
        'original_triangles': original_triangles, 'triangles': triangle_count,
        'heading_degrees': args.heading_degrees, 'height_including_hat_m': 1.85,
        'normal_strength': .3, 'metallic': 0, 'minimum_roughness': .6,
        'material_count': len(character.data.materials), 'textures': image_records,
        'bounds_m': {'min': list(lo), 'max': list(hi)},
        'rigged': False, 'animations': [], 'unreal_imported': False,
        'preview_scope': 'Mixar mesh renders; game-camera is approximate, not an Unreal capture',
        'previews': [],
    }
    for name, camera in cameras.items():
        scene.camera = camera
        floor.hide_render = name == 'underside-diagnostic'
        destination = previews / (name + '.png')
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        manifest['previews'].append({'view': name, 'file': str(destination.relative_to(out)),
                                     'sha256': digest(destination)})
        print('DRIFTER_PREVIEW', name, flush=True)
    floor.hide_render = False
    scene.camera = cameras['three-quarter']
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('DRIFTER_REVIEW_READY', json.dumps({'triangles': triangle_count, 'project': str(project)}), flush=True)


if __name__ == '__main__':
    main()
