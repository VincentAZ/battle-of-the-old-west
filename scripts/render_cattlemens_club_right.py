"""Supplement the standard eight-view review with the clubhouse's right veranda."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
manifest=json.loads((folder/'manifest.json').read_text())
project=folder/manifest['project']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(project)==manifest['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
scene=bpy.context.scene
holding=bpy.data.objects[manifest['mesh_object']]
size=holding.dimensions;extent=max(size);d=extent*4
data=bpy.data.cameras.new('Right_veranda_diagnostic');data.type='ORTHO'
data.ortho_scale=1.25*max((size.x**2+size.y**2)**.5,size.z/.75)
camera=bpy.data.objects.new('Right_veranda_diagnostic',data);scene.collection.objects.link(camera)
camera.location=(.8*d,-.6*d,.4*d)
camera.rotation_euler=(Vector((0,0,size.z*.5))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.camera=camera
image=folder/'previews/right-veranda.png';assert not image.exists()
scene.render.filepath=str(image);bpy.ops.render.render(write_still=True)
assert sha(project)==manifest['project_sha256']
(folder/'right-veranda-render.json').write_text(json.dumps(dict(project_sha256=sha(project),image_sha256=sha(image),script_sha256=sha(Path(__file__)),scope='Additional view only; source and saved review project unchanged.'),indent=2)+'\n')
