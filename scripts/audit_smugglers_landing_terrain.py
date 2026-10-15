"""Read-only source/terrain audit for the level-water landing at a native pose.

This measures source triangles, not GPU vertices. It deliberately does not
apply the dry-holding deformation to the boat, water or shoreline.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--proposal-split', action='store_true', help='Study a separated wet foundation and dry apron before authoring')
parser.add_argument('--pose-origin', type=float, nargs=3, help='Explicit source-only placement study; never changes the native capture')
parser.add_argument('--pose-yaw', type=float, default=0)
parser.add_argument('--early-apron-lift', action='store_true', help='Study/review v003 dry apron lift; requires matching native material when not a proposal')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
args.state = args.state.resolve()
base = ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing/base-v005/smugglers-landing-Base.blend'
terrain = ROOT/'art/world/ContinuousTerrain_Collision.blend'
height_texture = ROOT/'art/western/holdings/ground-fit-v001/T_ArenaGroundHeight.tga'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protected = {p: sha(p) for p in (base, terrain, args.state, height_texture)}
state = json.loads(args.state.read_text())
cinematic = state.get('before_request', state)['cinematic']
tp = cinematic['terrain_renderer']
assert tp['location'] == [0, 0, 0] and tp['scale'] == [1, 1, 1]
assert all(abs(v) < 1e-5 for v in tp['rotation_degrees'])
unit = next(u for u in cinematic['units'] if u.get('card_id') == 'smuggler_s_landing')
component = next(c for c in unit['holding_components'] if '/SM_HoldingBase_' in c['mesh'])
if args.pose_origin:
    assert args.proposal_split
    component = dict(component, location=args.pose_origin,
        quaternion_xyzw=[0,0,math.sin(math.radians(args.pose_yaw)/2),math.cos(math.radians(args.pose_yaw)/2)])
x, y, z, w = component['quaternion_xyzw']
pose = Matrix.LocRotScale(Vector(component['location']), Quaternion((w, x, y, z)), Vector(component['scale']))
bpy.ops.wm.open_mainfile(filepath=str(base), use_scripts=False)
objects = {}
for name in ('Holding_Base_Ground', 'Holding_Base_Water', 'Holding_Base_EarthCut', 'Holding_Base_WaterCut'):
    obj = bpy.data.objects[name]
    obj.data.calc_loop_triangles()
    vertices = []
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        vertices.append(pose @ Vector((-100*p.x, 100*p.y, 100*p.z)))
    objects[name] = (vertices, [tuple(t.vertices) for t in obj.data.loop_triangles])
bpy.ops.wm.open_mainfile(filepath=str(terrain), use_scripts=False)
obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
obj.data.calc_loop_triangles()
tree = BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
    [tuple(t.vertices) for t in obj.data.loop_triangles], all_triangles=True)
foundations = state.get('before_request', state)['hud']['region'].get('landing_foundations', [])
split_fit = args.proposal_split or bool(foundations and all(f.get('profile')=='split_wet_dry_v002' for f in foundations))
if split_fit and not args.proposal_split:
    assert len(foundations)==1
    assert (Vector(foundations[0]['origin'])-Vector(component['location'])).length < .001
    expected = pose.to_quaternion().to_euler().z
    assert abs(foundations[0]['frame'][0]-math.cos(expected)) < 1e-5
    assert abs(foundations[0]['frame'][1]-math.sin(expected)) < 1e-5
    assert abs(foundations[0]['frame'][2]-component['scale'][0]) < 1e-5
    if args.early_apron_lift:
        assert component['ground_fit']['material'].endswith('/M_LandingDryBankV003.M_LandingDryBankV003')
inverse = pose.inverted()
def smooth(a, b, value):
    t = max(0, min(1, (value-a)/(b-a)))
    return t*t*(3-2*t)

def split_weight(world):
    local = inverse @ world
    return (1-smooth(500,700,abs(local.x)))*(1-smooth(450,650,local.y))*(1-smooth(300,355,-local.y))

if args.proposal_split:
    foundations = [dict(origin=component['location'], scale=component['scale'],
        quaternion_xyzw=component['quaternion_xyzw'], profile='split_wet_dry_proposal')]
terrain_vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
fitted_vertices = []
sample_vertices = []
height_bytes = height_texture.read_bytes()
shifts = []
for p in terrain_vertices:
    # Terrain source metres map to native centimetres with Y reversed.
    world = Vector((p.x*100, -p.y*100, p.z*100))
    offset = 0
    for foundation in foundations:
        if split_fit:
            offset += (component['location'][2]-world.z)*split_weight(world)
            continue
        origin, extent = foundation['origin'], foundation['flat_extent']
        outside = math.hypot(max(abs(world.x-origin[0])-extent[0], 0), max(abs(world.y-origin[1])-extent[1], 0))
        t = min(1, outside/foundation['transition_cm'])
        weight = 1-t*t*(3-2*t)
        offset += max(-200, min(200, origin[2]-world.z))*weight
    offset = max(-200, min(200, offset))
    fitted_vertices.append(p+Vector((0, 0, offset/100)))
    ix, iy = round((world.x+6500)/50), round((world.y+6500)/50)
    blue, green, red = height_bytes[18+(iy*261+ix)*3:21+(iy*261+ix)*3]
    decoded_height = (red*256+green-32768)/16
    if split_fit:
        decoded_height += (component['location'][2]-decoded_height)*split_weight(world)
    sample_vertices.append(Vector((p.x,p.y,decoded_height/100)))
    shifts.append(offset)
fitted_tree = BVHTree.FromPolygons(fitted_vertices,
    [tuple(t.vertices) for t in obj.data.loop_triangles], all_triangles=True)
sample_tree = BVHTree.FromPolygons(sample_vertices,
    [tuple(t.vertices) for t in obj.data.loop_triangles], all_triangles=True)
rows = {}
for name, (vertices, triangles) in objects.items():
    if split_fit and name != 'Holding_Base_Water':
        adjusted = []
        for p in vertices:
            local = inverse @ p
            dry = smooth(270,280,-local.y)
            fitted_hit, _, _, _ = sample_tree.ray_cast(Vector((p.x/100,-p.y/100,100)),Vector((0,0,-1)),200)
            assert fitted_hit is not None
            lift_start, lift_end = (270,330) if args.early_apron_lift else (280,355)
            shift = (fitted_hit.z*100-component['location'][2])*dry + 1.5*smooth(lift_start,lift_end,-local.y)
            adjusted.append(p+Vector((0,0,shift)))
        vertices = adjusted
    samples = []
    for tri in triangles:
        for weights in ((1/3, 1/3, 1/3), (.5, .5, 0), (0, .5, .5), (.5, 0, .5)):
            p = sum((vertices[i]*weight for i, weight in zip(tri, weights)), Vector())
            hit, _, _, _ = tree.ray_cast(Vector((p.x/100, -p.y/100, 100)), Vector((0, 0, -1)), 200)
            assert hit is not None
            fitted_hit, _, _, _ = fitted_tree.ray_cast(Vector((p.x/100, -p.y/100, 100)), Vector((0, 0, -1)), 200)
            assert fitted_hit is not None
            samples.append(dict(world_cm=list(p), clearance_cm=p.z-hit.z*100,
                fitted_clearance_cm=p.z-fitted_hit.z*100))
    rows[name] = dict(triangles=len(triangles), samples=len(samples),
        minimum_clearance_cm=min(s['clearance_cm'] for s in samples),
        maximum_clearance_cm=max(s['clearance_cm'] for s in samples),
        buried_samples=sum(s['clearance_cm'] < 0 for s in samples),
        fitted_minimum_clearance_cm=min(s['fitted_clearance_cm'] for s in samples),
        fitted_maximum_clearance_cm=max(s['fitted_clearance_cm'] for s in samples),
        fitted_buried_samples=sum(s['fitted_clearance_cm'] < -.01 for s in samples),
        fitted_lowest=sorted(samples, key=lambda s: s['fitted_clearance_cm'])[:8],
        lowest=sorted(samples, key=lambda s: s['clearance_cm'])[:8],
        highest=sorted(samples, key=lambda s: s['clearance_cm'])[-8:])
assert all(sha(p) == h for p, h in protected.items())
crew = []
support_units = list(cinematic['units'])
for side in range(2):
    for column in range(3):
        for row in range(2):
            support_units.append(dict(id=f'formation-{side}-{column}-{row}',
                location=[(column-1)*1350,2500+(1 if side==0 else -1)*(500+row*480),0]))
for u in support_units:
    if u.get('camp') or u.get('hidden') or u.get('event_token'):
        continue
    if 'location' not in u:
        continue
    # Include the whole 300x180 cm frame plus its 2.5 cm board half-width.
    for dx, dy in ((dx,dy) for dx in range(-155,156,10) for dy in range(-95,96,10)):
        x, y = u['location'][0]+dx, u['location'][1]+dy
        start = Vector((x/100,-y/100,100))
        a, _, _, _ = tree.ray_cast(start,Vector((0,0,-1)),200)
        b, _, _, _ = fitted_tree.ray_cast(start,Vector((0,0,-1)),200)
        assert a is not None and b is not None
        crew.append(dict(id=u['id'],point=[x,y],visual_surface_change_cm=(b.z-a.z)*100))
checks = dict(single_foundation=len(foundations)==1,
    exposed_ground_and_water_clear=all(r['fitted_buried_samples']==0 for name,r in rows.items() if name != 'Holding_Base_EarthCut'),
    earth_cut_lower_edge_embed_under_one_cm=rows['Holding_Base_EarthCut']['fitted_minimum_clearance_cm'] > -1,
    crew_samples_present=bool(crew),
    crew_surface_unchanged=bool(crew) and max(abs(c['visual_surface_change_cm']) for c in crew)<.01)
report = dict(status=('fitted_samples_passed' if all(checks.values()) else 'fitted_candidate_rejected') if foundations else 'measured_unfitted_landing', native_component=component,
    objects=rows, source_sha256={str(p.relative_to(ROOT)): h for p, h in protected.items()},
    foundations=foundations, terrain_vertices_changed=sum(abs(d)>.0001 for d in shifts),
    maximum_terrain_displacement_cm=max(abs(d) for d in shifts), crew_footprints=crew,
    checks=checks,
    proposed_split_fit=args.proposal_split,
    early_apron_lift=args.early_apron_lift,
    proposed_pose_origin=args.pose_origin,
    proposed_pose_yaw=args.pose_yaw if args.pose_origin else None,
    all_twelve_formation_frames_sampled=True,
    native_split_fit=split_fit and not args.proposal_split,
    base_height_sampling='Decoded saved height texture; exact source triangle diagonals and per-vertex split deformation.',
    sources_unchanged=True, auditor_sha256=sha(Path(__file__)),
    limits='One native pose and sampled source triangles. No GPU readback, continuous proof, other placements or terrain modification.')
assert not args.output.exists()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print('LANDING_TERRAIN_AUDIT', json.dumps({n: {k: v for k, v in r.items() if k not in ('lowest', 'highest')} for n, r in rows.items()}), flush=True)
if foundations:
    assert all(checks.values()), checks
