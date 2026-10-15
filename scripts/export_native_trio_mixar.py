"""Export approved Lozen and Sarah appearances for the Mixar rig service."""
import bpy, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/native/trio-animation-v001'
approvals=json.loads((OUT.parent/'review-v001/appearance-approval.json').read_text())['projects']
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
for slug,name in [('lozen','Lozen'),('sarah-winnemucca','Sarah')]:
    source=ROOT/approvals[slug]['path']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==approvals[slug]['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    bpy.ops.object.select_all(action='DESELECT')
    obj=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review']
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.gltf(filepath=str(OUT/slug/(name+'-Approved.glb')),use_selection=True,export_format='GLB')
