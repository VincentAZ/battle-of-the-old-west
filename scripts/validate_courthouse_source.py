"""Read-only audit of closed component solids in an authored courthouse source."""
import bpy,bmesh,json,hashlib,sys
from pathlib import Path
from math import isfinite
root=Path(__file__).resolve().parents[1];out=Path(sys.argv[sys.argv.index('--')+1]).resolve();source=out/'Courthouse.blend';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
rows=[];bad=[]
for obj in bpy.context.scene.objects:
 if obj.type!='MESH':continue
 bm=bmesh.new();bm.from_mesh(obj.data)
 row=dict(name=obj.name,vertices=len(bm.verts),faces=len(bm.faces),nonmanifold=sum(not e.is_manifold for e in bm.edges),volume=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area() for f in bm.faces),uv_in_unit_square=all(isfinite(x) and -1e-6<=x<=1.000001 for item in obj.data.uv_layers.active.data for x in item.uv))
 if row['nonmanifold'] or row['volume']<=1e-12 or row['minimum_face_area']<=1e-12 or not row['uv_in_unit_square']:bad.append(row)
 rows.append(row);bm.free()
assert sha(source)==before
(out/'mesh-audit.json').write_text(json.dumps(dict(ok=not bad,objects=len(rows),auditor_sha256=sha(Path(__file__)),source_sha256=before,bad=bad,solids=rows,limitations='Per-piece closed positive-volume solids, nonzero faces and finite UVs. Pieces intentionally overlap; not Boolean-union, support/contact, collision or historical approval.'),indent=2)+'\n')
print('COURTHOUSE_MESH_AUDIT',len(rows),'bad',len(bad),bad[:3],flush=True)
assert not bad
