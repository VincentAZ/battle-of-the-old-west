"""Sample approved source component colours without changing mesh or texture."""
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/drifter/reveal-bandana-v001'
record = json.loads((BASE/'components.json').read_text())
source = ROOT/record['source']
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
body = bpy.data.objects[record['object']]
material = body.data.materials[0]
image = next(n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and 'BaseColor' in n.image.name)
width, height = image.size
pixels = np.empty(width*height*4, dtype=np.float32)
image.pixels.foreach_get(pixels)
pixels = pixels.reshape(height, width, 4)
colors = {v.index: [] for v in body.data.vertices}
for loop in body.data.loops:
    uv = body.data.uv_layers.active.data[loop.index].uv
    c = pixels[min(height-1, max(0, int(uv.y*height))), min(width-1, max(0, int(uv.x*width))), :3]
    colors[loop.vertex_index].append(c)
output = []
for index, component in enumerate(record['components']):
    values = np.array([c for v in component['indices'] for c in colors[v]])
    output.append(dict(component=index, vertices=component['vertices'], minimum=component['minimum'],
                       maximum=component['maximum'], median_rgb=np.median(values, axis=0).tolist()))
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
path = BASE/'component-colors.json'
assert not path.exists()
path.write_text(json.dumps(dict(source_sha256=record['source_sha256'], components=output), indent=2)+'\n')
print(json.dumps([c for c in output if c['maximum'][2] > 1.2 and c['minimum'][2] < 1.75], indent=2))
