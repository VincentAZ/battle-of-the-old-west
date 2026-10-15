"""Author an isolated, sourced Fort Smith-type static scaffold in local Mixar."""
import hashlib
import json
import math
from pathlib import Path
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/gallows'
OUT = BASE/'local-source-v004'
EVIDENCE = BASE/'historical-evidence.json'
BRIEF = BASE/'local-brief-v004.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['evidence_sha256'] == sha(EVIDENCE)
for path, digest in brief['reference_hashes'].items():
    assert sha(ROOT/path) == digest
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists(), 'Preserve previous sources'
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1889)
rng = np.random.default_rng(1889)

# A single original procedural atlas; the photographs remain evidence only.
size = 2048
pixels = np.ones((size, size, 4), dtype=np.float32)
yy, xx = np.mgrid[0:size, 0:512]
grain = np.sin(xx*.19 + np.sin(yy*.004)*1.7) + .4*np.sin(xx*.61 + yy*.001)
fine = rng.normal(0, 1, (size, 512))
for tile, colour, strength in [(0, (239, 236, 224), 2.8), (1, (117, 73, 36), 9),
                               (2, (40, 37, 33), .6), (3, (184, 142, 84), 4)]:
    variation = grain*strength + fine*(.55 if tile == 0 else 1.3)
    if tile == 3:
        variation += 9*np.sin(xx*.08 + yy*.14)
    rgb = np.clip(np.array(colour)[None, None, :] + variation[:, :, None], 0, 255)/255
    pixels[:, tile*512:(tile+1)*512, :3] = rgb
image = bpy.data.images.new('Gallows_BaseColor', size, size, alpha=False)
image.pixels.foreach_set(pixels.ravel())
image.filepath_raw = str(OUT/'Gallows_BaseColor.png')
image.file_format = 'PNG'
image.save()
image.pack()
material = bpy.data.materials.new('M_Gallows')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .82
texture = material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = image
material.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
objects = []


def finish(obj, tile=0, axis=2):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new()
    values = [v.co for v in obj.data.vertices]
    lo = [min(v[i] for v in values) for i in range(3)]
    hi = [max(v[i] for v in values) for i in range(3)]
    widths = [max(hi[i]-lo[i], .001) for i in range(3)]
    for poly in obj.data.polygons:
        across = max((i for i in range(3) if i != axis), key=lambda i: widths[i]*(1-abs(poly.normal[i])))
        for loop in poly.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv = ((tile+.025+.95*(point[across]-lo[across])/widths[across])/4,
                                .015+.97*(point[axis]-lo[axis])/widths[axis])
    objects.append(obj)
    return obj


def box(name, location, dimensions, tile=0, axis=None, bevel=.004):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new('Dressed timber edge', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return finish(obj, tile, axis if axis is not None else max(range(3), key=lambda i: dimensions[i]))


def beam(name, a, b, width, depth=None, tile=0):
    a, b = Vector(a), Vector(b)
    obj = box(name, (a+b)/2, (width, depth or width, (b-a).length), tile, 2)
    obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    return obj


def tube(name, points, radius=.020, cyclic=False):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    curve.use_fill_caps = True
    spline = curve.splines.new('POLY')
    spline.points.add(len(points)-1)
    for point, value in zip(spline.points, points):
        point.co = (*value, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    return finish(obj, 3, 2)


deck_z = 2.4384
width, depth = 6.096, 4.8768
front, rear = -depth/2, depth/2
trap_front, trap_rear = -2.13, -1.2156
# Raised stage, complete on every side; the trap remains closed and static.
for x in (-2.88, 0, 2.88):
    for y in (-2.25, 2.25):
        box('Platform_oak_leg', (x, y, (deck_z-.23)/2), (.3048, .3048, deck_z-.23))
for y in (-2.25, 2.25):
    box('Platform_main_girder', (0, y, deck_z-.18), (width, .23, .30))
for x in (-2.75, -1.4, 0, 1.4, 2.75):
    box('Platform_joist', (x, 0, deck_z-.13), (.16, depth-.06, .20))
for y in (-2.25, 2.25):
    for side in (-1, 1):
        beam('Under_stage_diagonal', (side*2.88, y, .55), (side*1.10, y, deck_z-.20), .15)
for x in (-2.88, 2.88):
    for side in (-1, 1):
        beam('Side_stage_diagonal', (x, side*2.25, .60), (x, side*.8, deck_z-.20), .15)

for i in range(30):
    x = -width/2 + (i+.5)*width/30
    spans = [(front, trap_front-.009), (trap_rear+.009, rear)] if abs(x) < 2.4384 else [(front, rear)]
    for a, b in spans:
        box('Platform_floor_plank', (x, (a+b)/2, deck_z-.035), (width/30-.006, b-a, .07), axis=1, bevel=.002)
for i in range(24):
    x = -2.4384+(i+.5)*4.8768/24
    box('Closed_trap_plank', (x, (trap_front+trap_rear)/2, deck_z-.035), (4.8768/24-.006, trap_rear-trap_front-.016, .07), axis=1, bevel=.002)
for x in (-1.9, -.65, .65, 1.9):
    box('Reconstructed_iron_hinge', (x, trap_rear, deck_z+.008), (.09, .24, .014), tile=2, bevel=.001)

# Sixteen-foot clear span and photographed upper triangular bracing.
post_x = (4.8768+.3048)/2
beam_y, top = -1.72, 4.8768
for side in (-1, 1):
    box('Tall_oak_upright', (side*post_x, beam_y, top/2), (.3048, .3048, top))
    beam('Upright_rear_stay', (side*post_x, beam_y, 3.67), (side*post_x, .15, deck_z+.03), .18)
box('Heavy_oak_crossbeam', (0, beam_y, top+.2794/2), (2*post_x+.56, .2286, .2794))
for side in (-1, 1):
    beam('Upper_triangular_brace', (side*post_x, beam_y, top+.30), (0, beam_y, top+.69), .18, .16)
beam('Upper_centre_block', (0, beam_y, top+.25), (0, beam_y, top+.69), .16)

# Simple rails informed by the modern replica; omitted compound is explicit.
for x in (-2.95, 2.95):
    for y in (-2.25, 0, 2.25):
        box('Side_rail_post', (x, y, deck_z+.46), (.12, .12, .92))
    for z in (deck_z+.48, deck_z+.94):
        box('Side_rail', (x, 0, z), (.095, 4.65, .115))
for x in (-1.48, 0, 1.48):
    box('Rear_rail_post', (x, 2.25, deck_z+.46), (.12, .12, .92))
for z in (deck_z+.48, deck_z+.94):
    box('Rear_rail', (0, 2.25, z), (5.94, .095, .115))

# Twelve separate treads; no modern gate or sign.
stair_x, stair_width, run = 2.32, 1.0668, .24
start = front-12*run
for i in range(12):
    z = (i+1)*deck_z/12
    box('Stair_tread_%02d'%(i+1), (stair_x, start+(i+.5)*run, z-.035), (stair_width, run+.012, .07), axis=0)
for side in (-1, 1):
    x = stair_x+side*(stair_width/2-.07)
    beam('Stair_stringer', (x, start-.025, .06), (x, front+.05, deck_z-.12), .12, .23)
    x = stair_x+side*(stair_width/2+.015)
    beam('Stair_handrail', (x, start+.055, deck_z/12+.830), (x, front-.055, deck_z+.940), .085, .10)
    for i in (0, 5, 11):
        z = (i+1)*deck_z/12
        box('Stair_rail_post', (x, start+(i+.5)*run, z+.43), (.085, .085, .86))

# Roof documented by 1889. Surface-board layout is restrained reconstruction.
roof_front, roof_rear = -2.30, 2.80
high, low = 6.00, 3.96
def roof_z(y):
    return high+(low-high)*(y-roof_front)/(roof_rear-roof_front)
for x in (-2.86, 2.86):
    box('Rear_roof_support', (x, 2.24, (roof_z(2.24)-.17)/2), (.18, .18, roof_z(2.24)-.17))
    box('Front_roof_extension', (x, beam_y, (roof_z(beam_y)+top)/2), (.14, .14, roof_z(beam_y)-top))
for i in range(13):
    x = -3.04+i*6.08/12
    beam('Whitewashed_roof_rafter', (x, roof_front, high-.11), (x, roof_rear, low-.11), .13, .17)
roof_length = math.hypot(roof_rear-roof_front, high-low)
for i in range(32):
    x = -3.2+(i+.5)*6.4/32
    obj = box('Roof_surface_board', (x, (roof_front+roof_rear)/2, (high+low)/2), (.198, roof_length, .055), tile=1, axis=1, bevel=.002)
    # Whitewashed underside follows the archived NPS reconstruction photograph.
    uv = obj.data.uv_layers.active
    for face in obj.data.polygons:
        if face.normal.z < -.5:
            for loop in face.loop_indices:
                uv.data[loop].uv.x -= .25
    obj.rotation_euler.x = math.atan2(low-high, roof_rear-roof_front)
for y in (roof_front, roof_rear):
    box('White_roof_fascia', (0, y, roof_z(y)-.10), (6.48, .11, .20), axis=0)

# Decorative static rope geometry: generic natural fibre, no mechanism/rig.
for index, x in enumerate((-.90, .35)):
    wrap = [(x, beam_y-.16*math.cos(t), top+.14+.21*math.sin(t)) for t in np.linspace(0, math.tau, 36, endpoint=False)]
    tube('Beam_rope_wrap_%d'%index, wrap, .021, True)
    tube('Suspended_rope_%d'%index, [(x, beam_y-.16, top+.14), (x+.015, beam_y-.17, 3.72), (x, beam_y-.17, 3.43)], .021)
    loop = [(x+.12*math.sin(t), beam_y-.17, 3.22+.23*math.cos(t)) for t in np.linspace(0, math.tau, 48, endpoint=False)]
    tube('Empty_rope_loop_%d'%index, loop, .020, True)
    coil = [(x+.031*math.cos(t), beam_y-.17+.031*math.sin(t), 3.40+t/(math.tau*6)*.20) for t in np.linspace(0, math.tau*6, 100)]
    tube('Reconstructed_rope_collar_%d'%index, coil, .013)

bpy.ops.object.select_all(action='DESELECT')
for obj in objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active = objects[0]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Gallows.blend'))
glb = OUT/'Gallows.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                           export_apply=True, export_animations=False, export_materials='EXPORT')
triangles = 0
for obj in objects:
    obj.data.calc_loop_triangles()
    triangles += len(obj.data.loop_triangles)
assert triangles < 30000 and not bpy.data.actions
(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    method='Local static mesh and original procedural atlas in Mixar',
    research_sha256=sha(EVIDENCE), brief_sha256=sha(BRIEF), script_sha256=sha(Path(__file__)),
    project_sha256=sha(OUT/'Gallows.blend'), glb_sha256=sha(glb), atlas_sha256=sha(OUT/'Gallows_BaseColor.png'),
    objects=len(objects), triangles=triangles, stair_treads=12, empty_rope_loops=2,
    unrigged=True, animations=0, unreal_imported=False,
    documented=['Whitewash', 'Oak framing and upper brace', 'Twelve steps', 'Roof by 1889'],
    reconstructed=['Isolated scaffold without its enclosure/masonry surroundings', 'Joinery, rails and stair placement',
                   'Plain wooden roof surfacing', 'Exact colour, rope arrangement and closed trap detail'],
    final_user_approval=False), indent=2)+'\n')
print('GALLOWS_AUTHORED', triangles, str(glb), flush=True)
