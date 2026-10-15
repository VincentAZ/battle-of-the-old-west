"""Render in-memory rigid mask diagnostic without editing the approved source."""
import bpy,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug
s=json.loads((out/'rig-settings.json').read_text());r=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug]
bpy.ops.wm.open_mainfile(filepath=str(root/r['path']),use_scripts=False)
o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];indices={i for region in s['rigid_regions'] for i in region['vertex_indices']}
m=bpy.data.materials.new('Diagnostic_RigidMask');m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(1,.015,.005,1);bs.inputs['Roughness'].default_value=.6;o.data.materials.append(m)
for p in o.data.polygons:
 if set(p.vertices)<=indices:p.material_index=len(o.data.materials)-1
scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.cycles.samples=24
qa=out/'rig-mask-qa';qa.mkdir(exist_ok=True)
views=sys.argv[sys.argv.index('--')+2:] or ('front','side','rear','three-quarter')
for view in views:
 scene.camera=bpy.data.objects['Review_'+view];scene.render.filepath=str(qa/('mask-'+view+'.png'));bpy.ops.render.render(write_still=True)
