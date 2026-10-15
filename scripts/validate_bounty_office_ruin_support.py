"""Read back closed ruin components and their actual foundation support."""
import hashlib
import json
from pathlib import Path
import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/bounty-office'
OUT = BASE/'ruin-source-v003'
project = OUT/'BountyOffice-Ruin.blend'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = sha(project)
record = json.loads((OUT/'authoring.json').read_text())
scale = record['normalization']['scale']
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == 1
obj = objects[0]
bm = bmesh.new(); bm.from_mesh(obj.data)
unseen = set(bm.verts)
rows = []
while unseen:
    seed = unseen.pop(); connected = {seed}; pending = [seed]
    while pending:
        for edge in pending.pop().link_edges:
            for other in edge.verts:
                if other in unseen:
                    unseen.remove(other); connected.add(other); pending.append(other)
    faces = {f for v in connected for f in v.link_faces}
    part = bmesh.new()
    mapping = {v: part.verts.new(obj.matrix_world@v.co) for v in connected}
    for face in faces:
        part.faces.new([mapping[v] for v in face.verts])
    low = [min(v.co[k] for v in part.verts) for k in range(3)]
    high = [max(v.co[k] for v in part.verts) for k in range(3)]
    assert all(e.is_manifold for e in part.edges)
    assert part.calc_volume(signed=True) > 0
    assert min(f.calc_area() for f in part.faces) > 1e-12
    rows.append(dict(bounds_m=dict(min=low,max=high),
                     signed_volume_m3=part.calc_volume(signed=True)))
    part.free()
bm.free()
# Retained wall pieces also sit on lower wall courses and pier feet.
# Their original geometry consists of axis-aligned boxes; debris rests on
# the broad, flat foundation. Check support in ascending vertical order.
rows.sort(key=lambda r:r['bounds_m']['min'][2])
for index, row in enumerate(rows):
    low, high = row['bounds_m']['min'], row['bounds_m']['max']
    if abs(low[2]) < .0001:
        row['support'] = 'ground_plane'
        continue
    cx, cy = (low[0]+high[0])/2, (low[1]+high[1])/2
    supports = []
    for prior, candidate in enumerate(rows[:index]):
        a, b = candidate['bounds_m']['min'], candidate['bounds_m']['max']
        if (a[2] < low[2] and b[2] >= low[2]-.0001
            and a[0]-.0001 <= cx <= b[0]+.0001
            and a[1]-.0001 <= cy <= b[1]+.0001):
            supports.append(prior)
    assert supports, row
    row['support'] = 'lower_surviving_component'
    row['support_components'] = supports

assert len(rows) == record['component_count']
assert sha(project) == before
report = dict(status='passed', project_sha256=before, components=len(rows),
              closed_outward=True, supported=True, solids=rows,
              limitations=['Support checks use component bounds and bottom-centre contact; retained structural components are axis-aligned boxes. Small structural overlaps are allowed.',
                           'Not a Boolean intersection, physical collapse or native terrain audit.'])
(OUT/'support-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('BOUNTY_OFFICE_RUIN_SUPPORT_PASSED', len(rows), flush=True)
