"""Export only the approved Quanah mesh for Mixar's biped rig service."""
import bpy, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/native/quanah-game-v001'
approval = json.loads((OUT.parent/'review-v001/appearance-approval.json').read_text())['projects']['quanah-parker']
source = ROOT/approval['path']
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert hashlib.sha256(source.read_bytes()).hexdigest() == approval['sha256']
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
bpy.ops.object.select_all(action='DESELECT')
obj = bpy.data.objects['quanah_parker_Appearance_Review']
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.gltf(filepath=str(OUT/'Quanah-Approved.glb'), use_selection=True, export_format='GLB')
