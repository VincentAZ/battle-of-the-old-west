"""CPU-only, read-only Blender extraction; never saves a blend or imports FBX.

Creates all-bone, all-frame expectations for the coordinated native importer.
Existing expectation files are immutable: pass a new --output for an iteration.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientist_import_contract import CONTRACT, EXPECTATIONS, difference, load_bundle, require, sha

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=EXPECTATIONS)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
require(not args.output.exists(), 'Preserve existing expectations:', args.output)
bundle = load_bundle(False)


def convert(matrix):
    p, q, s = matrix.decompose()
    return {'translation_cm':[p.x*100, -p.y*100, p.z*100],
            'rotation_xyzw':[-q.x, q.y, -q.z, q.w], 'scale':list(s)}


output = {'schema':'oldwest.scientist.all-bone-import-expectations.v1',
          'status':'CPU expectations only; not native import evidence',
          'complete_contract_sha256':sha(CONTRACT), 'provenance':bundle['provenance'],
          'extractor_sha256':sha(__file__), 'clips':{}, 'props':{}}
for blend in sorted({c['blend'] for c in bundle['clips']}):
    bpy.ops.wm.open_mainfile(filepath=blend, use_scripts=False)
    arm = bpy.data.objects['Survivor_Rig']
    names = [b.name.removeprefix('mixamorig:') for b in arm.data.bones]
    require(len(names) == len(set(names)) == 53, '53 unique authored bones required')
    reference = {b.name.removeprefix('mixamorig:'):{
        'parent':b.parent.name.removeprefix('mixamorig:') if b.parent else 'Survivor_Rig',
        'component_rest':convert(arm.matrix_world@b.matrix_local)} for b in arm.data.bones}
    if 'bone_names' not in output:
        output['bone_names'], output['reference'] = names, reference
    else:
        require(names == output['bone_names'], 'Authored bone identity/order changed')
        for name, row in reference.items():
            require(row['parent'] == output['reference'][name]['parent'], 'Authored bone parent changed',name)
            cm, degrees = difference(row['component_rest'], output['reference'][name]['component_rest'])
            require(cm < .001 and degrees < .001, 'Authored reference pose changed',name)
    for clip in [c for c in bundle['clips'] if c['blend'] == blend]:
        rows = []
        for frame in range(clip['frames'][0], clip['frames'][1]+1):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            bones = {b.name.removeprefix('mixamorig:'):convert(arm.matrix_world@b.matrix) for b in arm.pose.bones}
            for name, expected in clip['published'][frame]['bones'].items():
                cm, degrees = difference(bones[name], expected)
                require(cm < .01 and degrees < .1, 'Existing contract disagrees with source',clip['asset'],frame,name,cm,degrees)
            rows.append({'frame':frame,'seconds':(frame-clip['frames'][0])/30,'bones':bones})
        output['clips'][clip['asset']] = rows
    bpy.context.scene.frame_set(1)
    for prop in bundle['props']:
        if Path(prop['source_fbx']).parent != Path(blend).parent:
            continue
        # Holster and Unholster share the same receiver; inspect it once.
        if prop['asset'] in output['props']:
            continue
        name = prop.get('pivot_name','RifleHolster_Receiver')
        root = bpy.data.objects[name]
        points = [root.matrix_world.inverted()@child.matrix_world@v.co
                  for child in root.children if child.type == 'MESH' for v in child.data.vertices]
        require(points, 'Empty prop geometry',name)
        native = [[100*p.x,-100*p.y,100*p.z] for p in points]
        bounds = [[min(p[i] for p in native) for i in range(3)], [max(p[i] for p in native) for i in range(3)]]
        if 'local_mesh_bounds_cm' in prop:
            require(max(abs(a-b) for x,y in zip(bounds,prop['local_mesh_bounds_cm']) for a,b in zip(x,y)) < .01,'Prop pivot/bounds changed',name)
        output['props'][prop['asset']] = {'pivot':name,'local_mesh_bounds_cm':bounds,
                                        'body_relative_transform':convert(root.matrix_world)}
require(all(sha(p) == h for p,h in bundle['provenance'].items()), 'Source changed during extraction')
require(len(output['props']) == 11 and len(output['clips']) == 13, 'Incomplete extraction')
args.output.write_text(json.dumps(output,separators=(',',':'))+'\n')
print('SCIENTIST_COMPLETE_EXPECTATIONS '+json.dumps({'clips':13,'props':11,'bones':53,
      'frames':sum(len(x) for x in output['clips'].values()),'output':str(args.output)}),flush=True)
