"""Paint the fused hip-tool surface and immediate cloth attachment without topology edits."""
import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/barn-burner'
s=json.loads((out/'rig-settings.json').read_text());a=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects']['barn-burner']
bpy.ops.wm.open_mainfile(filepath=str(root/a['path']),use_scripts=False);o=bpy.data.objects['barn_burner_Appearance_Review']
ids=[]
for v in o.data.vertices:
 x,y,z=o.matrix_world@v.co
 if .225<x<.30 and -.06<y<.09 and .677<z<1.002:ids.append(v.index)
s['rigid_regions'][1].update(vertex_indices=ids,allow_polygon_boundary=True,boundary_note='The narrow belt tool is fused with pants and coat islands; spatial surface painting includes immediate attachment cloth, with surrounding skin faded to Hips. Exact original mesh geometry and UVs remain unchanged.')
(out/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print('tool',len(ids))
