"""Check closed source geometry, display support and authored glass properties."""
import hashlib,json,sys
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
project=folder/'Apothecary.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
records=[]
for ob in objects:
 bm=bmesh.new();bm.from_mesh(ob.data)
 assert all(e.is_manifold for e in bm.edges),ob.name
 assert all(f.calc_area()>1e-10 for f in bm.faces),ob.name
 assert bm.calc_volume(signed=True)>1e-10,(ob.name,bm.calc_volume(signed=True))
 assert ob.data.uv_layers
 ob.data.calc_loop_triangles()
 records.append(dict(name=ob.name,triangles=len(ob.data.loop_triangles),volume_m3=bm.calc_volume(signed=True)))
 bm.free()
def bounds(ob):
 points=[ob.matrix_world@v.co for v in ob.data.vertices]
 return [[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]]
globes=[o for o in objects if o.name.startswith('Clear stoppered show globe')]
shelves=[o for o in objects if o.name.startswith('Interior display shelf')]
assert len(globes)==len(shelves)==2
support=[]
for globe in globes:
 lo,hi=bounds(globe)
 shelf=min(shelves,key=lambda o:abs(o.location.x-(lo[0]+hi[0])/2))
 sl,sh=bounds(shelf)
 assert abs(lo[2]-sh[2])<1e-6
 assert all(sl[i]<lo[i] and hi[i]<sh[i] for i in range(2))
 assert lo[1]>-1.796, 'Globe must be behind the window glazing'
 support.append(dict(globe=globe.name,shelf=shelf.name,gap_m=lo[2]-sh[2],entire_globe_behind_window=True))
mat=objects[0].data.materials[0];bsdf=mat.node_tree.nodes.get('Principled BSDF')
assert bsdf.inputs['Metallic'].default_value==0
assert bsdf.inputs['Transmission Weight'].is_linked and bsdf.inputs['Roughness'].is_linked
# Sample the actual authored images in each material region, not just constants.
from PIL import Image
rough=Image.open(folder/'Apothecary_Roughness.png');trans=Image.open(folder/'Apothecary_Transmission.png')
assert trans.getpixel((256,768))[0]==0
assert trans.getpixel((256,1280))[0]==255
assert rough.getpixel((256,1280))[0]<16
assert trans.getpixel((768,1280))[0]>120 and trans.getpixel((1280,1280))[0]>120
report=dict(status='passed',scope='Static source geometry and optical-map/support audit, not gameplay or user approval',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles'] for r in records),objects=records,display_support=support,glass_transmission_and_roughness_sampled=True,rigs=0,animations=0)
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('APOTHECARY_SOURCE_AUDIT',len(objects),report['triangles'],flush=True)
