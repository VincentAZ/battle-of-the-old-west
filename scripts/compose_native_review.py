"""Compose the three unretouched Mixar mesh renders for appearance review."""
import argparse
import sys
from pathlib import Path
import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path)
parser.add_argument('--view', default='three-quarter')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = args.directory.resolve()
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 4
scene.render.threads_mode = 'FIXED'
scene.render.threads = 8
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_x = 3840
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'


def emission(name, color=None, path=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(emit.outputs[0], output.inputs['Surface'])
    if path:
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(path))
        tex.interpolation = 'Closest'
        mat.node_tree.links.new(tex.outputs['Color'], emit.inputs['Color'])
    else:
        emit.inputs['Color'].default_value = color
    return mat


white = emission('Review lettering', (.85, .87, .89, 1))
for x, slug, label, subtitle in (
    (-1280, 'quanah-parker', 'Quanah Parker', 'Comanche | 1870s'),
    (0, 'lozen', 'Lozen', 'Chihenne Chiricahua Apache | 1880s'),
    (1280, 'sarah-winnemucca', 'Sarah Winnemucca', 'Northern Paiute | 1870s'),
):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(x, -45, 0))
    plane = bpy.context.object
    plane.scale = (640, 480, 1)
    plane.data.materials.append(emission(label, path=out / slug / 'review/previews' / (args.view + '.png')))
    for y, body, size in ((508, label, 35), (471, subtitle, 25)):
        bpy.ops.object.text_add(location=(x - 602, y, 1))
        text = bpy.context.object
        text.data.body, text.data.size = body, size
        text.data.materials.append(white)
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -1))
bpy.context.object.scale = (1920, 550, 1)
bpy.context.object.data.materials.append(emission('Background', (.018, .022, .027, 1)))
bpy.ops.object.camera_add(location=(0, 0, 10))
camera = bpy.context.object
camera.data.type, camera.data.ortho_scale, camera.data.clip_end = 'ORTHO', 3840, 100
scene.camera = camera
scene.render.filepath = str(out / ('Native-Appearance-' + args.view + '.png'))
assert not Path(scene.render.filepath).exists(), 'Preserve existing review images'
bpy.ops.render.render(write_still=True)
print('NATIVE_COMPARISON_READY', scene.render.filepath, flush=True)
