"""Read-only source composition: reviewed work clip with actual parked rifle."""
import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--holster',type=Path,required=True)
parser.add_argument('--frames',nargs='+',type=int,default=[60,70,135,215])
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
SOURCE=ROOT/'art/characters/scientist_gesture/candidate-v11'
HOLSTER=args.holster.resolve();OUT=HOLSTER/'core-parked-rifle';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[SOURCE/'Scientist_Analysis_Candidate.blend',HOLSTER/'Scientist_Holster_Candidate.blend']
before={str(p):sha(p) for p in paths}
bpy.ops.wm.open_mainfile(filepath=str(paths[0]),use_scripts=False)
with bpy.data.libraries.load(str(paths[1]),link=False) as (available,loaded):
    loaded.objects=[name for name in available.objects if name=='ActualNativeRifle_CPUReference' or name.startswith(('RifleHolster_','Holster_'))]
for obj in loaded.objects:
    if obj is None:continue
    bpy.context.collection.objects.link(obj);obj.animation_data_clear()
gun=bpy.data.objects['ActualNativeRifle_CPUReference']
row=json.loads((HOLSTER/'pose-and-rifle-samples.json').read_text())[-1]
gun.matrix_world=Matrix(row['rifle_matrix_m'])
path=OUT/'Scientist_Holster_Candidate.blend';bpy.context.scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
source=(ROOT/'scripts/author_scientist_decision_branches.py').read_text().replace('(2.8,-2.4,2.25)','(-2.8,-2.4,2.25)').replace('(1.3,-1.8,2.4)','(-1.7,-1.8,2.0)')
tree=ast.parse(source);exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='studio'],type_ignores=[]),'studio','exec'),globals())
images=studio(path,OUT,args.frames)
assert all(sha(p)==value for p,value in before.items())
(OUT/'manifest.json').write_text(json.dumps({'status':'CPU_combined_clearance_study_requires_review',
    'sources_unchanged':before,'blend_sha256':sha(path),'images':images,
    'scope':'Same reviewed core animation with the actual rifle frozen at the holster endpoint. No native import.'},indent=2)+'\n')
print('SCIENTIST_PARKED_RIFLE_STUDY_COMPLETE',flush=True)
