"""Read back static shoreline contact; does not claim native terrain coverage."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing'
B=P/'base-v005'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((B/'base.json').read_text())
project=B/'smugglers-landing-Base.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
def tree(name):
    ob=bpy.data.objects[name]
    return BVHTree.FromPolygons([ob.matrix_world@v.co for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons])
ground=tree('Holding_Base_Ground');water=tree('Holding_Base_Water')
def height(surface,x,y):
    hit=surface.ray_cast(Vector((x,y,5)),Vector((0,0,-1)),10)[0]
    return hit.z if hit else None
depths=[]
for x,y,z in record['willow_roots']:
    h=height(ground,x,y);assert h is not None and .005<h-z<.025,(x,y,z,h)
    assert height(water,x,y) is None
    depths.append(h-z)
# Coordinates are review-space positions of the unchanged post and approach.
post=(-1.85,-2.23);ramp=(-.70,-2.53)
assert height(water,*post) is None and height(water,*ramp) is None
assert .13<height(ground,*post)<.16 and .13<height(ground,*ramp)<.16
levels=[v.co.z for v in bpy.data.objects['Holding_Base_Water'].data.vertices]
assert max(levels)-min(levels)<1e-6 and abs(levels[0]-.105)<1e-6
boat_water=height(water,0,1.55)
assert abs(boat_water-.105)<1e-6
holding=tree('smugglers_landing_Holding_Review')
floor=height(holding,0,1.55)
assert floor is not None and floor>boat_water+.05,(floor,boat_water)
report=dict(status='passed',scope='Static saved source contact only; native regions and condition lifecycles untested',project_sha256=sha(project),willow_root_samples=len(depths),root_embed_m=[min(depths),max(depths)],post_and_approach_dry=True,water_level_m=levels[0],floor_above_water_m=floor-boat_water,source_script_sha256=sha(Path(__file__)))
(B/'contact-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('SMUGGLERS_CONTACT_PASS',json.dumps(report),flush=True)
