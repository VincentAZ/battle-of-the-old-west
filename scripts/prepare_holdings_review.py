"""Prepare one Western Holding static appearance candidate inside Mixar.

Run with Mixar --background --factory-startup --python-exit-code 1
    --python scripts/prepare_holdings_review.py -- --source MODEL.glb --output DIR --holding HOLDING.json

This creates an unrigged, unanimated review source and eight honest renders of
that mesh. It does not import into Unreal, animate, or alter any game asset.
The footprint scale is game presentation, not a historical dimension claim.
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
    # Exact world-space extents from the vertices: a rotated local bound box
    # over-estimates the footprint for non-axis-aligned headings.
    points = [ob.matrix_world @ v.co for ob in meshes for v in ob.data.vertices]
    return (Vector([min(p[i] for p in points) for i in range(3)]),
            Vector([max(p[i] for p in points) for i in range(3)]))


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--holding', type=Path, required=True)
    parser.add_argument('--heading-degrees', type=float, default=180,
                        help='Rotate the imported result about Z so its front facade faces -Y')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--source-method', choices=['generated','local-modeling'], default='generated')
    parser.add_argument('--preserve-authored-material', action='store_true',
                        help='Keep local-modeling material values, including glass roughness and transmission')
    parser.add_argument('--detail-height', type=float, default=.3,
                        help='Facade-detail target as a fraction of model height')
    parser.add_argument('--views', nargs='+', help='Subset for orientation diagnostics')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert 0 <= args.detail_height <= 1
    assert not args.preserve_authored_material or args.source_method == 'local-modeling'
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use the installed Mixar executable'
    info = json.loads(args.holding.read_text())
    label = info['slug'].replace('-', '_')
    footprint = float(info['footprint_m'])
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
    assert not bpy.data.actions, 'Appearance checkpoint prohibits animations'
    assert not any(ob.type == 'ARMATURE' for ob in bpy.context.scene.objects), 'Appearance checkpoint precedes rigging'
    rotation = Matrix.Rotation(math.radians(args.heading_degrees), 4, 'Z')
    for ob in meshes:
        transform = ob.matrix_world.copy()
        ob.parent = None
        ob.matrix_world = rotation @ transform
    bpy.context.view_layer.update()
    lo, hi = bounds(meshes)
    # Longest horizontal extent becomes the presentation footprint; ground at Z=0.
    factor = footprint / max(hi.x - lo.x, hi.y - lo.y)
    shift = Vector((-(hi.x + lo.x) / 2, -(hi.y + lo.y) / 2, -lo.z))
    for ob in meshes:
        ob.matrix_world = Matrix.Scale(factor, 4) @ Matrix.Translation(shift) @ ob.matrix_world
    bpy.ops.object.select_all(action='DESELECT')
    for ob in meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    holding = bpy.context.object
    holding.name = label + '_Holding_Review'
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    holding.data.calc_loop_triangles()
    original_triangles = len(holding.data.loop_triangles)
    if original_triangles > 30000:
        modifier = holding.modifiers.new('Review budget: preserve original GLB separately', 'DECIMATE')
        modifier.ratio = 29500 / original_triangles
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    holding.data.calc_loop_triangles()
    triangle_count = len(holding.data.loop_triangles)
    assert triangle_count <= 30000, f'Triangle budget exceeded: {triangle_count}'
    assert len(holding.data.materials) == 1, 'Review requires a single shared material atlas'
    assert holding.data.uv_layers, 'Generated mesh has no UV map'
    material = holding.data.materials[0]
    material.name = 'M_' + label + '_Review'
    for node in material.node_tree.nodes:
        if args.preserve_authored_material:
            continue
        if node.type == 'NORMAL_MAP':
            node.inputs['Strength'].default_value = .3
        if node.type == 'BSDF_PRINCIPLED':
            # Weathered wood, stone, adobe and canvas are dielectric. Small iron
            # fittings do not justify the generated metallic noise at game scale.
            for link in list(node.inputs['Metallic'].links):
                material.node_tree.links.remove(link)
            node.inputs['Metallic'].default_value = 0
            roughness = node.inputs['Roughness']
            if roughness.is_linked:
                source_socket = roughness.links[0].from_socket
                clamp = material.node_tree.nodes.new('ShaderNodeMath')
                clamp.name = 'Weathered_material_roughness_floor'
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
        image.name = 'T_' + label + '_' + channel
        if tuple(image.size) != (2048, 2048):
            image.scale(2048, 2048)
        path = textures / (image.name + '.png')
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()
        if image.packed_file:
            image.unpack(method='REMOVE')
        image.filepath_raw = str(path)
        image.reload()
        assert tuple(image.size) == (2048, 2048)
        image.pack()
        image_records.append({'channel': channel, 'source_size': original_size,
                              'size': list(image.size), 'file': str(path.relative_to(out)),
                              'sha256': digest(path)})
    assert any(r['channel'] == 'BaseColor' for r in image_records), 'Generated material has no base color texture'
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 8
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new(info['display_name'] + ' neutral studio')
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
    lo, hi = bounds([holding])
    size = hi - lo
    extent = max(size)
    s = extent / 1.8  # the crew studio was laid out around a 1.8 m figure
    for name, location, energy, radius in (
        ('Key', (-3.5, -4, 6), 650, 4.0),
        ('Fill', (4, -2, 3.5), 300, 3.5),
        ('Rim', (0, 4, 5.5), 750, 3.0),
    ):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.shape, data.size = energy * s * s, 'DISK', radius * s
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = Vector(location) * s
        aim(light, (0, 0, size.z * .5))
    focus = (0, 0, size.z * .5)
    D = extent * 4
    # Orthographic width; the 4:3 frame shows only three quarters of it vertically.
    aspect = scene.render.resolution_y / scene.render.resolution_x
    frame = 1.2 * max(math.hypot(size.x, size.y), size.z / aspect)
    views = {
        'front': ((0, -D, size.z * .5), 1.15 * max(size.x, size.z / aspect), focus),
        'side': ((-D, 0, size.z * .5), 1.15 * max(size.y, size.z / aspect), focus),
        'rear': ((0, D, size.z * .5), 1.15 * max(size.x, size.z / aspect), focus),
        'three-quarter': ((-.6 * D, -.8 * D, .45 * D), frame, focus),
        'game-camera': ((-.55 * D, -.75 * D, .75 * D), 1.3 * frame, focus),
        'overhead': ((0, -.25 * D, D), 1.15 * max(size.x, size.y / aspect), (0, 0, 0)),
        'facade-detail': ((0, -D, size.z * args.detail_height), .55 * frame, (0, 0, size.z * args.detail_height)),
        'underside-diagnostic': ((0, -.5 * D, -D), frame, focus),
    }
    cameras = {}
    for name, (location, ortho_scale, target) in views.items():
        data = bpy.data.cameras.new('Review_' + name)
        data.type = 'ORTHO'
        data.ortho_scale = ortho_scale
        data.clip_end = 10000
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
        camera.location = location
        aim(camera, target)
        if name != 'facade-detail':
            # Tall false fronts project beyond a ground-centred overhead frame.
            # Fit actual projected geometry for every full-asset review view.
            right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
            up = camera.rotation_euler.to_quaternion() @ Vector((0, 1, 0))
            points = [holding.matrix_world @ vertex.co for vertex in holding.data.vertices]
            xs = [(p-camera.location).dot(right) for p in points]
            ys = [(p-camera.location).dot(up) for p in points]
            camera.location += right*((max(xs)+min(xs))/2) + up*((max(ys)+min(ys))/2)
            camera.data.ortho_scale = 1.15 * max(max(xs)-min(xs), (max(ys)-min(ys))/aspect)
        cameras[name] = camera
    scene.camera = cameras['three-quarter']
    bpy.ops.object.select_all(action='DESELECT')
    holding.select_set(True)
    bpy.context.view_layer.objects.active = holding
    holding['review_status'] = 'Provisional: awaiting user appearance approval; static, unrigged, not game-integrated'
    holding['source_generator'] = 'Local modeling in Mixar' if args.source_method == 'local-modeling' else 'Mixar / Tripo Pro'
    for area in (bpy.context.screen.areas if bpy.context.screen else []):
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.shading.type = 'MATERIAL'
    project = out / (info['slug'] + '-Review.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    manifest = {
        'stage': 'A: static appearance review', 'status': 'awaiting_user_review',
        'source_glb': str(source), 'source_sha256': digest(source),
        'source_method': args.source_method, 'detail_height': args.detail_height,
        'authoring_application': bpy.app.binary_path, 'application_version': bpy.app.version_string,
        'project': project.name, 'project_sha256': digest(project),
        'original_triangles': original_triangles, 'triangles': triangle_count,
        'heading_degrees': args.heading_degrees, 'footprint_m': footprint,
        'footprint_scope': 'Longest horizontal extent at game presentation scale; not a historical dimension',
        'holding': info, 'mesh_object': holding.name,
        'material_policy': 'preserve-authored' if args.preserve_authored_material else 'weathered-dielectric',
        'normal_strength': None if args.preserve_authored_material else .3,
        'metallic': None if args.preserve_authored_material else 0,
        'minimum_roughness': None if args.preserve_authored_material else .6,
        'material_count': len(holding.data.materials), 'textures': image_records,
        'bounds_m': {'min': list(lo), 'max': list(hi)}, 'size_m': list(size),
        'rigged': False, 'animations': [], 'unreal_imported': False,
        'preview_scope': 'Mixar mesh renders; game-camera is approximate, not an Unreal capture',
        'previews': [],
    }
    for name, camera in cameras.items():
        if args.views and name not in args.views:
            continue
        scene.camera = camera
        floor.hide_render = name == 'underside-diagnostic'
        destination = previews / (name + '.png')
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        manifest['previews'].append({'view': name, 'file': str(destination.relative_to(out)),
                                     'sha256': digest(destination)})
        print('HOLDING_PREVIEW', name, flush=True)
    floor.hide_render = False
    scene.camera = cameras['three-quarter']
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('HOLDING_REVIEW_READY', json.dumps({'triangles': triangle_count, 'project': str(project)}), flush=True)


if __name__ == '__main__':
    main()
