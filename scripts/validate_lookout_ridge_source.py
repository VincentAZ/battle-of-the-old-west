"""Read the saved ridge back; check its solid independently of authoring state."""
import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy

review = Path(sys.argv[sys.argv.index('--')+1]).resolve()
manifest = json.loads((review/'manifest.json').read_text())
project = review/manifest['project']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(project) == manifest['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
obj = bpy.data.objects[manifest['mesh_object']]
bm = bmesh.new(); bm.from_mesh(obj.data)
# GLB uses independent vertices along UV seams. Weld a validation-only copy.
before = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
assert all(edge.is_manifold for edge in bm.edges)
assert all(face.calc_area() > 1e-9 for face in bm.faces)
volume = bm.calc_volume(signed=True); assert volume > 0
remaining = set(bm.verts); components = 0
while remaining:
    components += 1
    frontier = [remaining.pop()]
    while frontier:
        vertex = frontier.pop()
        for edge in vertex.link_edges:
            other = edge.other_vert(vertex)
            if other in remaining:
                remaining.remove(other); frontier.append(other)
assert components == 1
report = dict(status='passed', project_sha256=sha(project),
    validation_script_sha256=sha(Path(__file__)), closed_manifold=True,
    connected_components=components, positive_volume_m3=volume,
    vertices_before_seam_weld=before,vertices_after_seam_weld=len(bm.verts),
    nonzero_face_areas=True,scope='Saved mesh topology and volume; not a visual or historical verdict.')
bm.free()
(review/'solid-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('LOOKOUT_SAVED_SOLID_VALIDATED',json.dumps(report),flush=True)
