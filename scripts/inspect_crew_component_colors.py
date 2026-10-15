"""Read-only texture-color diagnostics for component mask selection."""
import bpy,json,sys
import numpy as np
from pathlib import Path
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug
r=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug]
bpy.ops.wm.open_mainfile(filepath=str(root/r['path']),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review']
components=json.loads((out/'components.json').read_text())['components'];image=next(n.image for n in o.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and 'BaseColor' in n.image.name)
w,h=image.size;pixels=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(pixels);pixels=pixels.reshape(h,w,4)
colors={i:[] for i in range(len(o.data.vertices))}
for loop in o.data.loops:
 uv=o.data.uv_layers.active.data[loop.index].uv;c=pixels[min(h-1,max(0,int(uv.y*h))),min(w-1,max(0,int(uv.x*w))),:3];colors[loop.vertex_index].append(c)
for i,c in enumerate(components):
 a=np.array([col for v in c['indices'] for col in colors[v]]);c['component_id']=i;c['mean_color']=np.mean(a,axis=0).tolist();c['median_color']=np.median(a,axis=0).tolist()
(out/'component-colors.json').write_text(json.dumps(components,indent=2)+'\n')
