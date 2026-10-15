"""Read-only Blender extraction of real hand-skin vertices for a native observer.

No render, save, FBX import, or Content change. Only vertices whose complete
deforming weight support is present in the native 11-bone observation qualify.
The resulting LBS landmarks are not a GPU-skinned-vertex readback.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientist_import_contract import ROOT, require, sha

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
require(not args.output.exists(), 'Refusing to replace landmark evidence', args.output)
source = ROOT/'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend'
mesh = ROOT/'game/OldWest/Content/Art/Survivors/Variants/Scientist/SKM_Prospector_Cm.uasset'
if not mesh.exists():
    matches = list((ROOT/'game/OldWest/Content/Art/Survivors').rglob('SKM_Prospector_Cm.uasset'))
    require(len(matches) == 1, 'Cannot identify installed Prospector mesh')
    mesh = matches[0]
protected = {str(p):sha(p) for p in (source,mesh)}
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
arm, body = bpy.data.objects['Survivor_Rig'], bpy.data.objects['Survivor_Body']
require(len(arm.data.bones) == 53, 'Unexpected source rig')
points = []
for side in ('Left','Right'):
    allowed = {side+'Hand', side+'HandIndex1', side+'HandPinky1'}
    candidates = []
    for vertex in body.data.vertices:
        influences = []
        for group in vertex.groups:
            name = body.vertex_groups[group.group].name
            if name in arm.data.bones and group.weight > 0:
                influences.append((name, group.weight))
        total = sum(w for _,w in influences)
        if total < .999 or not influences or any(n.removeprefix('mixamorig:') not in allowed for n,_ in influences):
            continue
        world = body.matrix_world@vertex.co
        weights = []
        for name, weight in influences:
            local = (arm.matrix_world@arm.data.bones[name].matrix_local).inverted()@world
            weights.append({'bone':name.removeprefix('mixamorig:'), 'weight':weight/total,
                            'bone_local_cm':[100*local.x,-100*local.y,100*local.z]})
        candidates.append({'vertex':vertex.index,'side':side,'weights':weights,
                           'rest_body_cm':[100*world.x,-100*world.y,100*world.z]})
    require(len(candidates) >= 16, 'Insufficient completely observed skin vertices', side,len(candidates))
    # Deterministic surface spread, avoiding a cluster of effectively duplicate
    # vertices. The first point and all following ties use source vertex order.
    selected = [candidates.pop(0)]
    while len(selected) < 16:
        index = max(range(len(candidates)), key=lambda i:min(
            sum((a-b)**2 for a,b in zip(candidates[i]['rest_body_cm'],s['rest_body_cm'])) for s in selected))
        selected.append(candidates.pop(index))
    points.extend(selected)
require(all(sha(p) == h for p,h in protected.items()), 'Protected source changed during read-only extraction')
output = {'schema':'oldwest.scientist.skin-landmarks.v1','extractor_sha256':sha(__file__),
          'provenance':protected,'body_object':body.name,'landmark_count':len(points),'points':points,
          'method':'Actual source skin vertices with complete weight support in observed bones; 16 spread points per hand.',
          'limits':['Reconstructs linear blend skinning from the observed bone poses and source weights.',
                    'Does not read native GPU vertices, finger-tip bones, cloth deformation or collision surfaces.']}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(output,indent=2)+'\n')
print('SCIENTIST_CONTACT_LANDMARKS '+json.dumps({'points':len(points),'source_unchanged':True,'output':str(args.output)}),flush=True)
