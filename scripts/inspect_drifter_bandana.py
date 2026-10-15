"""Read-only component evidence for a separate public-reveal bandana prop."""
import hashlib
import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/drifter/reveal-bandana-v001'
SOURCE = ROOT/'art/western/drifter/animation-v001/Drifter-Rigged.blend'
before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert json.loads((SOURCE.parent/'rig-validation.json').read_text())['project_sha256'] == before
assert (ROOT/'research/western-presentation/drifter-reveal-bandana.json').exists()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
body = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and
            any(m.type == 'ARMATURE' for m in o.modifiers))
parent = list(range(len(body.data.vertices)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


for edge in body.data.edges:
    a, b = map(find, edge.vertices)
    parent[a] = b
parts = {}
for vertex in body.data.vertices:
    parts.setdefault(find(vertex.index), []).append(vertex.index)
report = []
for ids in parts.values():
    points = [body.matrix_world @ body.data.vertices[i].co for i in ids]
    report.append(dict(vertices=len(ids), indices=ids,
                       minimum=[min(p[k] for p in points) for k in range(3)],
                       maximum=[max(p[k] for p in points) for k in range(3)]))
report.sort(key=lambda p: p['vertices'], reverse=True)
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == before
BASE.mkdir(parents=True, exist_ok=True)
out = BASE/'components.json'
assert not out.exists(), 'Preserve previous diagnostics'
out.write_text(json.dumps(dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=before,
    object=body.name, materials=[m.name for m in body.data.materials], components=report), indent=2)+'\n')
print(json.dumps([{k:v for k,v in p.items() if k != 'indices'} for p in report[:20]], indent=2))
