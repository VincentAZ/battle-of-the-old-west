"""CPU-only original source outsole vertices for a staged native ground probe."""
import argparse
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scientist_import_contract import ROOT,require,sha

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);require(not args.output.exists(),'Preserve previous sole landmarks')
source=ROOT/'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend'
mesh=ROOT/'game/OldWest/Content/Art/Survivors/Variants/SKM_Prospector_Cm.uasset'
protected={str(x):sha(x) for x in (source,mesh)}
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False);arm=bpy.data.objects['Survivor_Rig']
rows=[]
for side in ('Left','Right'):
    candidates=[]
    for obj in bpy.data.objects:
        if obj.type!='MESH' or not (obj.name.startswith(side+'_Tread') or obj.name=='Survivor_'+side+'_Outsole'):continue
        for vertex in obj.data.vertices:
            world=obj.matrix_world@vertex.co
            if world.z>-.011:continue
            weights=[]
            for g in vertex.groups:
                name=obj.vertex_groups[g.group].name
                if name not in arm.data.bones or g.weight<=0:continue
                local=(arm.matrix_world@arm.data.bones[name].matrix_local).inverted()@world
                weights.append({'bone':name.removeprefix('mixamorig:'),'weight':g.weight,
                                'bone_local_cm':[100*local.x,-100*local.y,100*local.z]})
            require(weights and abs(sum(w['weight'] for w in weights)-1)<.0001,'Incomplete sole weights')
            candidates.append({'side':side,'object':obj.name,'vertex':vertex.index,
                               'rest_body_cm':[100*world.x,-100*world.y,100*world.z],'weights':weights})
    require(len(candidates)>6,'Missing real sole geometry')
    # Corners near front/back and both edges, followed by farthest remaining
    # sole surface points, independent of the eventual terrain height.
    selected=[min(candidates,key=lambda r:r['rest_body_cm'][2])]
    while len(selected)<6:
        selected.append(max((r for r in candidates if r not in selected),key=lambda r:min(
            sum((a-b)**2 for a,b in zip(r['rest_body_cm'],s['rest_body_cm'])) for s in selected)))
    rows.extend(selected)
require(all(sha(x)==h for x,h in protected.items()),'Protected originals changed')
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'schema':'oldwest.scientist.sole-landmarks.v1','source_provenance':protected,
    'extractor_sha256':sha(__file__),'status':'staged source landmarks; native terrain unmeasured','points':rows},indent=2)+'\n')
print('SCIENTIST_SOLE_LANDMARKS '+json.dumps({'count':len(rows),'output':str(args.output)}),flush=True)
