"""Run using Blender's Python; does not enable scripts stored in source assets."""
import bpy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/vitruvian'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE / 'blender_prep/vitruvian_rigged.blend'), use_scripts=False)
report = {'blender': bpy.app.version_string, 'objects': [], 'images': [], 'actions': []}
for obj in bpy.data.objects:
    item = {'name': obj.name, 'type': obj.type, 'dimensions': list(obj.dimensions),
            'location': list(obj.location), 'scale': list(obj.scale), 'hidden': obj.hide_render}
    if obj.type == 'MESH':
        item.update(vertices=len(obj.data.vertices), polygons=len(obj.data.polygons),
                    materials=[m.name for m in obj.data.materials if m],
                    modifiers=[{'name': m.name, 'type': m.type} for m in obj.modifiers],
                    uv_layers=[u.name for u in obj.data.uv_layers])
    if obj.type == 'ARMATURE':
        item['bones'] = [{'name': b.name, 'deform': b.use_deform,
                         'parent': b.parent.name if b.parent else None} for b in obj.data.bones]
    report['objects'].append(item)
for img in bpy.data.images:
    report['images'].append({'name': img.name, 'filepath': img.filepath, 'packed': bool(img.packed_file),
                             'size': list(img.size)})
report['actions'] = [{'name': a.name, 'frames': list(a.frame_range)} for a in bpy.data.actions]
(SOURCE / 'blend-inspection.json').write_text(json.dumps(report, indent=2) + '\n')
print('CHARACTER_INSPECTION', json.dumps({k: len(v) for k, v in report.items() if isinstance(v, list)}))
for o in report['objects']:
    if o['type'] in ['MESH', 'ARMATURE']:
        print(o['name'], o['type'], o.get('vertices'), len(o.get('bones', [])), o['dimensions'])
