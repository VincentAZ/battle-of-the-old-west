"""Encode the unchanged arena terrain for render-only holding-ground fitting.

Run in local Mixar background Python. No source project is saved.
"""
import hashlib
import json
from pathlib import Path
import struct

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/ground-fit-v001'
SOURCE = ROOT/'art/world/ContinuousTerrain_Collision.blend'
OUT.mkdir(parents=True, exist_ok=True)
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
obj.data.calc_loop_triangles()
points = [obj.matrix_world @ v.co for v in obj.data.vertices]
grid = {(round(p.x*2)+130, round(-p.y*2)+130): p.z*100 for p in points}
assert len(grid) == 261*261
diagonals = {}
for t in obj.data.loop_triangles:
    keys = [(round(points[i].x*2)+130, round(-points[i].y*2)+130) for i in t.vertices]
    x, y = min(k[0] for k in keys), min(k[1] for k in keys)
    # Which of the two possible diagonals does the source triangulation use?
    rising = (x, y) in keys and (x+1, y+1) in keys
    if (x, y) in diagonals:
        assert diagonals[x, y] == rising
    diagonals[x, y] = rising
pixels = bytearray()
max_error = 0
for y in range(261):
    for x in range(261):
        height = grid[x, y]
        code = round(height*16)+32768
        assert 0 <= code <= 65535
        max_error = max(max_error, abs((code-32768)/16-height))
        # TGA BGR, top origin. RG store 1/16 cm height; B stores the diagonal.
        pixels.extend((255 if diagonals.get((x, y), False) else 0, code % 256, code//256))
header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, 261, 261, 24, 0x20)
texture = OUT/'T_ArenaGroundHeight.tga'
texture.write_bytes(header+pixels)
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
report = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=source_hash,
    texture_sha256=hashlib.sha256(texture.read_bytes()).hexdigest(), source_unchanged=True,
    dimensions=[261, 261], world_min_cm=[-6500, -6500], grid_cm=50,
    height_decode_cm='(round(R*255)*256+round(G*255)-32768)/16',
    blue_channel='1 = diagonal (0,0) to (1,1); 0 = diagonal (1,0) to (0,1)',
    maximum_vertex_quantization_error_cm=max_error,
    scope='Render-only sampling of existing arena geometry; does not alter terrain, collision or gameplay.')
(OUT/'heightmap.json').write_text(json.dumps(report, indent=2)+'\n')
print('HOLDING_HEIGHTMAP_CREATED', max_error, flush=True)
