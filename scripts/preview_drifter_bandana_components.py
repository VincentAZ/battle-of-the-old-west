"""Read-only labelled contact sheet of candidate cloth components (local Mixar)."""
import hashlib
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/drifter/reveal-bandana-v001'
record = json.loads((BASE/'components.json').read_text())
source = ROOT/record['source']
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
assert (ROOT/'research/western-presentation/drifter-reveal-bandana.json').exists()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
body = bpy.data.objects[record['object']]
for obj in bpy.context.scene.objects:
    obj.hide_render = True
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.render.resolution_x = 1200
scene.render.resolution_y = 1050
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.world.color = (.35, .35, .35)
panels = [None, 14, 19, 51, 36, 46, 49, 40, 50, 63, 28, 55]
labels = []
for index, component in enumerate(panels):
    obj = body.copy()
    obj.data = body.data.copy()
    scene.collection.objects.link(obj)
    obj.hide_render = False
    obj.parent = None
    obj.modifiers.clear()
    obj.matrix_world = body.matrix_world.copy()
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    mesh.verts.ensure_lookup_table()
    keep = set(record['components'][component]['indices']) if component is not None else {
        v.index for v in obj.data.vertices if (body.matrix_world @ v.co).z > 1.30}
    bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v.index not in keep], context='VERTS')
    mesh.to_mesh(obj.data)
    mesh.free()
    x = (index % 4 - 1.5)*.52
    z = (2-index//4)*.58
    obj.location += Vector((x, 0, z-1.52))
    label = 'source head' if component is None else 'component '+str(component)
    curve = bpy.data.curves.new(label, 'FONT')
    curve.body, curve.size, curve.align_x = label, .042, 'CENTER'
    text = bpy.data.objects.new(label, curve)
    scene.collection.objects.link(text)
    text.location = (x, -.3, z-.23)
    text.rotation_euler = (1.57079632679, 0, 0)
    labels.append(dict(panel=index, label=label, component=component))
focus = Vector((0, 0, .57))
for pos, energy in [((1, -3, 3), 300), ((-3, -2, 1), 200)]:
    data = bpy.data.lights.new('ComponentReviewLight', 'AREA')
    data.energy, data.size = energy, 3
    lamp = bpy.data.objects.new('ComponentReviewLight', data)
    scene.collection.objects.link(lamp)
    lamp.location = pos
    lamp.rotation_euler = (focus-lamp.location).to_track_quat('-Z', 'Y').to_euler()
data = bpy.data.cameras.new('ComponentReviewCamera')
camera = bpy.data.objects.new('ComponentReviewCamera', data)
scene.collection.objects.link(camera)
scene.camera = camera
data.type, data.ortho_scale = 'ORTHO', 2.15
camera.location = focus+Vector((0, -5, 0))
camera.rotation_euler = (focus-camera.location).to_track_quat('-Z', 'Y').to_euler()
destination = BASE/'components-front.png'
assert not destination.exists()
scene.render.filepath = str(destination)
bpy.ops.render.render(write_still=True)
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
(BASE/'components-front.json').write_text(json.dumps(dict(source_sha256=record['source_sha256'],
    source_unchanged=True, panels=labels, image_sha256=hashlib.sha256(destination.read_bytes()).hexdigest()), indent=2)+'\n')
