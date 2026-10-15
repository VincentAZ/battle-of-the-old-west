"""Read-only front/rear close views of every saved dressing fit in local Mixar."""
import hashlib
import json
import os
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get('OLDWEST_BANDAGE_SOURCE', str(ROOT / 'art/western/bandages/review-v002')))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


results = []
for path in sorted(BASE.glob('*/authoring.json')):
    data = json.loads(path.read_text())
    source = path.parent / ('Bandage_' + data['name'] + '.blend')
    assert sha(source) == data['project_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    wrap = bpy.data.objects['Bandage_' + data['name']]
    points = [wrap.matrix_world @ v.co for v in wrap.data.vertices]
    center = sum(points, Vector()) / len(points)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.render.resolution_x = scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.world.color = (.3, .3, .3)
    for obj in list(scene.objects):
        if obj.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(obj, do_unlink=True)
    for position, energy, size in [((2, -3, 4), 240, 3), ((-2, 2, 3), 240, 3)]:
        light_data = bpy.data.lights.new('ReviewLight', 'AREA')
        light_data.energy, light_data.shape, light_data.size = energy, 'DISK', size
        light = bpy.data.objects.new('ReviewLight', light_data)
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (center-light.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data = bpy.data.cameras.new('ReviewCamera')
    camera = bpy.data.objects.new('ReviewCamera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type, camera_data.ortho_scale = 'ORTHO', .35
    views = []
    sign = 1 if data['arm'] == 'Left' else -1
    for view, offset in [('front', Vector((sign, -3, .6))), ('rear', Vector((sign, 3, .6)))]:
        destination = path.parent / ('fit-' + view + '.png')
        camera.location = center + offset
        camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        views.append(dict(view=view, path=str(destination.relative_to(ROOT)), sha256=sha(destination)))
    assert sha(source) == data['project_sha256']
    assert sha(ROOT/data['source']) == data['source_sha256']
    results.append(dict(slug=data['slug'], views=views, source_unchanged=True))
    (BASE/'source-fit-captures.json').write_text(json.dumps(results, indent=2)+'\n')
    print('BANDAGE_FIT_CAPTURED', data['slug'], flush=True)
