"""Render bounded CPU views from an unchanged saved Prospector gesture study."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--blend', type=Path, help='Explicit branch filename for read-only transition studies.')
parser.add_argument('--frames', nargs='+', type=int, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source = args.source.resolve()
path = args.blend.resolve() if args.blend else source / 'Scientist_Analysis_Candidate.blend'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
before = sha(path)
bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
scene = bpy.context.scene
scene.unit_settings.scale_length = 1
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
if hasattr(scene.cycles, 'denoising_use_gpu'):
    scene.cycles.denoising_use_gpu = False
scene.render.resolution_x = 1280
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
world = bpy.data.worlds.new('CPU_Transition_Review')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.1,.13,.15,1)
world.node_tree.nodes['Background'].inputs[1].default_value = .3
scene.world = world
for name, pos, power, size, color in [('Key',(-3,-4,5),700,3.5,(1,.88,.72)),
                                    ('Fill',(3,-2,3),450,3,(.65,.8,1)),
                                    ('Rim',(0,3,4),850,3,(.8,.93,1))]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = power
    data.shape = 'DISK'
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector((0,-.15,1))-obj.location).to_track_quat('-Z','Y').to_euler()
data = bpy.data.cameras.new('CPU_Transition_Camera')
camera = bpy.data.objects.new('CPU_Transition_Camera', data)
bpy.context.collection.objects.link(camera)
scene.camera = camera
data.lens = 60
records = []
for frame in args.frames:
    scene.frame_set(frame)
    for side, pos, target in [('outer',(-1.6,-1.3,2.05),(-.28,-.19,1.3)),
                              ('inner',(.75,-1.35,2.1),(-.21,-.19,1.25))]:
        camera.location = pos
        camera.rotation_euler = (Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        out = source / f'transition-{frame:03d}-{side}.png'
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        records.append({'frame': frame, 'view': side, 'path': str(out), 'sha256': sha(out)})
assert sha(path) == before, 'Saved study changed during read-only render'
(source / 'transition-render-review.json').write_text(json.dumps({
    'source_blend_sha256': before, 'source_unchanged': True,
    'kind': 'CPU posed transition studies; not native gameplay', 'renders': records}, indent=2)+'\n')
print('SCIENTIST_TRANSITION_REVIEW_RENDER_COMPLETE', flush=True)
