"""Read-only connected-solid support audit: Mixar --python SCRIPT -- RUIN_DIR."""
import hashlib
import json
import os
import sys
from pathlib import Path

import bpy
import bmesh

out = Path(sys.argv[sys.argv.index('--')+1])
condition = os.environ.get('OLDWEST_HOLDING_CONDITION', 'Ruin')
assert condition in ('Ruin', 'Damaged')
source = next(out.glob(f'*-{condition}.blend'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()), use_scripts=False)
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == 1
obj = objects[0]
bm = bmesh.new(); bm.from_mesh(obj.data)
unseen = set(bm.verts); rows = []
while unseen:
    seed = unseen.pop(); connected = {seed}; pending = [seed]
    while pending:
        v = pending.pop()
        for edge in v.link_edges:
            other = edge.other_vert(v)
            if other in unseen:
                unseen.remove(other); connected.add(other); pending.append(other)
    faces = set(f for v in connected for f in v.link_faces)
    part = bmesh.new(); mapping = {v:part.verts.new(obj.matrix_world@v.co) for v in connected}
    for f in faces: part.faces.new([mapping[v] for v in f.verts])
    row = dict(vertices=len(part.verts), faces=len(part.faces),
        boundary_edges=sum(e.is_boundary for e in part.edges),
        nonmanifold_edges=sum(not e.is_manifold for e in part.edges),
        signed_volume_m3=part.calc_volume(signed=True),
        minimum_z_m=min(v.co.z for v in part.verts))
    assert row['boundary_edges'] == 0 and row['nonmanifold_edges'] == 0, row
    assert row['signed_volume_m3'] > 0 and abs(row['minimum_z_m']) < .0001, row
    rows.append(row); part.free()
bm.free()
assert sha(source) == before
report = dict(status='passed', source_sha256=before, connected_solids=len(rows),
    closed_outward_grounded=True, solids=rows,
    limitations=['Checks each connected solid against the source ground plane, not native terrain.',
                 'Separate solids may overlap; this is not a Boolean-union or collision audit.'])
(out/'closed-solids.json').write_text(json.dumps(report,indent=2)+'\n')
print('RUIN_CONNECTED_SOLIDS_VALIDATED',len(rows),flush=True)
