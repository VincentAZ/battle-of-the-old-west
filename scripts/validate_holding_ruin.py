"""Read back a separate static ruin: BASE RUIN_DIR BRIEF (Mixar --python)."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import bpy
from bpy_extras.object_utils import world_to_camera_view

base, out, brief_path = map(Path,sys.argv[sys.argv.index('--')+1:])
condition = os.environ.get('OLDWEST_HOLDING_CONDITION', 'Ruin')
assert condition in ('Ruin', 'Damaged')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(brief_path.read_text())
record=json.loads((out/'authoring.json').read_text())
assert sha(brief_path)==record['brief_sha256']
for path_key,hash_key in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:
    assert sha(base/brief['preservation'][path_key])==brief['preservation'][hash_key]
project=next(p for p in out.glob(f'*-{condition}.blend'))
fbx=next(out.glob(f'SM_Holding{condition}_*.fbx'))
assert sha(project)==record['project_sha256'] and sha(fbx)==record['fbx_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project.resolve()),use_scripts=False)
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
mesh.data.calc_loop_triangles()
assert len(mesh.data.loop_triangles)==record['triangles']<30000
assert len(mesh.data.materials)==1 and mesh.data.uv_layers
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
assert all(math.isfinite(c) for v in mesh.data.vertices for c in v.co)
assert all(math.isfinite(c) for uv in mesh.data.uv_layers.active.data for c in uv.uv)
coords=[mesh.matrix_world@v.co for v in mesh.data.vertices]
lo=[min(v[k] for v in coords)for k in range(3)]
hi=[max(v[k] for v in coords)for k in range(3)]
assert all(abs(a-b)<.0001 for a,b in zip(lo,record['bounds_m']['min']))
assert all(abs(a-b)<.0001 for a,b in zip(hi,record['bounds_m']['max']))
assert abs(lo[2])<.0001
manifest=json.loads((base/'review/manifest.json').read_text())
assert hi[2]<manifest['size_m'][2] if condition == 'Ruin' else hi[2]<=manifest['size_m'][2]+.0001
assert all(lo[k]>=manifest['bounds_m']['min'][k]-.001 and hi[k]<=manifest['bounds_m']['max'][k]+.001 for k in range(2))
signature=([tuple(v.co)for v in mesh.data.vertices],[tuple(uv.uv)for uv in mesh.data.uv_layers.active.data])
mesh_name=mesh.name
review=next(out.glob(f'*-{condition}-Review.blend'))
bpy.ops.wm.open_mainfile(filepath=str(review.resolve()),use_scripts=False)
mesh=bpy.data.objects[mesh_name]
assert signature==([tuple(v.co)for v in mesh.data.vertices],[tuple(uv.uv)for uv in mesh.data.uv_layers.active.data])
assert set(record['views'])=={'front','rear','right','overhead'}
for name,digest in record['views'].items():
    assert sha(out/(name+'.png'))==digest
    camera=bpy.data.objects['Review_'+name]
    projected=[world_to_camera_view(bpy.context.scene,camera,o.matrix_world@v.co)
               for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected)
report=dict(status='passed',scope='Saved mesh, unchanged sources, bounds, UVs and four-view framing; not historical or native approval',
    project_sha256=sha(project),review_project_sha256=sha(review),fbx_sha256=sha(fbx),triangles=record['triangles'],
    bounds_m={'min':lo,'max':hi},inside_healthy_footprint=True,healthy_source_and_base_unchanged=True,
    no_rigs_or_animation=True,views=record['views'])
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('HOLDING_RUIN_VALIDATED',json.dumps(report),flush=True)
