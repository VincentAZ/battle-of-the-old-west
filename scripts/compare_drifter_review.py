"""Compose labeled, unretouched before/after model renders inside Mixar."""
import sys
from pathlib import Path
import bpy


root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[sys.argv.index('--')+1]).resolve()
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 4
scene.render.threads_mode = 'FIXED'
scene.render.threads = 8
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_x = 2560
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'


def emission(name, color=None, image=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    emit = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(emit.outputs[0], output.inputs['Surface'])
    if image:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(image))
        tex.interpolation = 'Closest'
        mat.node_tree.links.new(tex.outputs['Color'],emit.inputs['Color'])
    else:
        emit.inputs['Color'].default_value = color
    return mat


white = emission('Header lettering',(.85,.87,.89,1))
for x, label, path in (
    (-640,'BEFORE | Original',root/'art/western/drifter/review-v001/review/previews/three-quarter.png'),
    (640,'AFTER | Worn clothes',out/'review/previews/three-quarter.png'),
):
    bpy.ops.mesh.primitive_plane_add(size=2,location=(x,-32,0))
    plane = bpy.context.object
    plane.scale = (640,480,1)
    plane.data.materials.append(emission(label,image=path))
    bpy.ops.object.text_add(location=(x-602,469,1))
    text = bpy.context.object
    text.data.body = label
    text.data.size = 32
    text.data.materials.append(white)
bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-1))
bpy.context.object.scale = (1280,512,1)
bpy.context.object.data.materials.append(emission('Header background',(.018,.022,.027,1)))
bpy.ops.object.camera_add(location=(0,0,10))
camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2560
camera.data.clip_end = 100
scene.camera = camera
scene.render.filepath = str(out/'Drifter-Before-After.png')
bpy.ops.render.render(write_still=True)
print('DRIFTER_COMPARISON_READY',scene.render.filepath,flush=True)
