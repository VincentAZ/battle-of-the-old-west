"""Author the documented, fictional 1880s Coal Yard composite in Mixar.

Static source only. All construction analogues and uncertainties are pinned
before authoring; this is not a replica of a surveyed Denver installation.
"""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from PIL import Image, ImageDraw
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/holdings/expansion-review-v001/coal-yard'
OUT = BASE / 'local-source-v003'
BRIEF = BASE / 'local-authoring-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
for path, digest in brief['source_records'].items():
    assert sha(ROOT / path) == digest, path
assert not OUT.exists(), 'Preserve authored versions'
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1887)
rng = np.random.default_rng(1887)

regions = {'wood': (8, 8, 1008, 1016), 'shingle': (1040, 8, 2040, 1016),
           'coal': (8, 1040, 1008, 2040), 'iron': (1040, 1040, 1512, 1512),
           'tie': (1540, 1040, 2040, 2040), 'end': (1040, 1540, 1512, 2040)}
colours = {'wood': (146, 92, 43), 'shingle': (115, 70, 33),
           'coal': (26, 29, 33), 'iron': (59, 49, 39),
           'tie': (96, 60, 31), 'end': (154, 105, 57)}
atlas = Image.new('RGB', (2048, 2048), (88, 61, 39))
draw = ImageDraw.Draw(atlas)
for key, rect in regions.items():
    draw.rectangle(rect, fill=colours[key])
    x0, y0, x1, y1 = rect
    if key in ('wood', 'shingle', 'tie'):
        for x in range(x0 + 4, x1 - 3, 3):
            delta = random.randint(-19, 19)
            col = tuple(max(0, v + delta) for v in colours[key])
            draw.line((x, y0 + 3, x + random.randint(-2, 2), y1 - 3), fill=col)
    if key == 'coal':
        for _ in range(750):
            x, y = random.randint(x0 + 2, x1 - 20), random.randint(y0 + 2, y1 - 20)
            t = random.randint(21, 43)
            draw.line((x, y, x + random.randint(2, 18), y + random.randint(1, 7)), fill=(t, t+1, t+3), width=2)
pixels = np.asarray(atlas).astype(np.int16)
pixels += rng.integers(-3, 4, (2048, 2048, 1), dtype=np.int16)
texture = OUT / 'CoalYard_BaseColor.png'
Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_CoalYard_Atlas')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .77
node = material.node_tree.nodes.new('ShaderNodeTexImage')
node.image = bpy.data.images.load(str(texture)); node.image.pack()
material.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
objects = []


def finish(obj, region):
    obj.data.materials.append(material)
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new()
    x0, y0, x1, y1 = regions[region]
    for face in obj.data.polygons:
        axis = max(range(3), key=lambda k: abs(face.normal[k]))
        a, b = [k for k in range(3) if k != axis]
        coords = [obj.data.vertices[obj.data.loops[i].vertex_index].co for i in face.loop_indices]
        low = [min(p[k] for p in coords) for k in range(3)]
        high = [max(p[k] for p in coords) for k in range(3)]
        # Keep the long grain running along the longer dimension of each face.
        if high[a]-low[a] > high[b]-low[b]:
            a, b = b, a
        for loop in face.loop_indices:
            v = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u = (v[a]-low[a]) / max(high[a]-low[a], .00001)
            w = (v[b]-low[b]) / max(high[b]-low[b], .00001)
            uv.data[loop].uv = ((x0+5+u*(x1-x0-10))/2048,
                                1-(y1-5-w*(y1-y0-10))/2048)
    objects.append(obj)
    return obj


def box(name, location, dimensions, region='wood', rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object; obj.name = name; obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if rotation: obj.rotation_euler = rotation
    bpy.context.view_layer.update()
    return finish(obj, region)


def solid(name, vertices, faces, region):
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    return finish(obj, region)


def beam(name, start, end, width, depth, region='wood'):
    start, end = Vector(start), Vector(end)
    obj = box(name, (start+end)/2, (width, depth, (end-start).length), region)
    obj.rotation_euler = (end-start).to_track_quat('Z', 'Y').to_euler()
    return obj


# Complete timber shell, with three accessible bays and continuous sill support.
front, rear, centre = -.30, 1.60, .65
posts = [-2.25, -.75, .75, 2.25]
for y in (front, rear):
    box('Continuous sill', (0, y, .075), (4.70, .18, .15), 'tie')
    box('Eave wall plate', (0, y, 2.07), (4.66, .17, .16))
    for x in posts:
        box('Grounded frame post', (x, y, 1.045), (.17, .17, 1.89))
        for direction in (-1, 1):
            if abs(x + direction*.37) < 2.25:
                beam('Timber knee brace', (x, y, 1.65), (x+direction*.37, y, 2.03), .085, .085)
for i in range(30):
    x = -2.25 + (i+.5)*.15
    box('Rear vertical rough board', (x, rear+.065, 1.08), (.149, .06, 2.12))
    if i < 29:
        box('Rear seam batten', (x+.075, rear+.11, 1.08), (.040, .04, 2.12))
for side in (-1, 1):
    x = side*2.315
    def end_board(name, x, low, high, thickness):
        z0 = 2.785 - abs(low-centre)*.60
        z1 = 2.785 - abs(high-centre)*.60
        # Split at the ridge so a board crossing it follows both roof slopes.
        if low < centre < high:
            end_board(name, x, low, centre, thickness)
            end_board(name, x, centre, high, thickness)
            return
        vertices = [(xx, yy, zz) for xx in (x-thickness/2, x+thickness/2)
                    for yy, zz in [(low, .02), (high, .02), (high, z1), (low, z0)]]
        solid(name, vertices, [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),
                               (2,3,7,6),(3,0,4,7)], 'wood')
    for i in range(13):
        y = front + (i+.5)*(rear-front)/13
        half = (rear-front)/26
        end_board('Slope-cut end board', x, y-half, y+half, .06)
        if i < 12:
            yy = y+(rear-front)/26
            end_board('Slope-cut end batten', x+side*.045, yy-.019, yy+.019, .035)

# Internal retaining partitions are closed horizontal planks; geometry is a
# disclosed functional reconstruction, not a measured historical bin plan.
for x in posts:
    for row in range(6):
        box('Coal partition retaining plank', (x, centre, .095+row*.16), (.09, 1.77, .155))
for bay in (-1, 0, 1):
    for row in range(2):
        box('Low removable front retaining plank', (bay*1.5, front+.035, .095+row*.16), (1.32, .08, .155))
    box('Bay timber threshold', (bay*1.5, centre, .05), (1.41, 1.72, .08), 'tie')

# Simple gabled roof. Solid boarding and tilted individual courses keep roof
# overlaps distinct while every framing member meets a supported roof face.
rise, run = .69, 1.15
angle, slope = math.atan2(rise, run), math.hypot(rise, run)
ridge = 2.82
for side in (-1, 1):
    box('Continuous roof boarding', (0, centre+side*run/2, ridge-rise/2), (4.93, slope, .065), 'wood', (-side*angle, 0, 0))
    for row in range(8):
        d = (row+.5)*slope/8
        shift = .105 if row%2 else 0
        for col in range(25):
            a = max(-2.47, -2.47+col*.21-shift)
            b = min(2.47, -2.47+(col+1)*.21-shift)
            if b-a < .01: continue
            box('Lapped wood shingle', ((a+b)/2, centre+side*d*math.cos(angle), ridge-d*math.sin(angle)+.047),
                (b-a-.002, slope/8+.025, .018), 'shingle', (-side*(angle-.022), 0, 0))
    box('Eave fascia', (0, centre+side*1.132, 2.13), (4.98, .055, .13))
for side in (-1, 1):
    box('Ridge weather board', (0, centre+side*.038, ridge+.06), (4.95, .105, .034), 'shingle', (-side*angle, 0, 0))
for x in posts:
    box('Roof tie beam', (x, centre, 2.13), (.11, 2.11, .10))
    for side in (-1, 1):
        beam('Common roof rafter', (x, centre+side*1.10, 2.13), (x, centre, 2.76), .09, .09)


for bay, height in [(-1, .70), (0, .58), (1, .83)]:
    cx = bay*1.5
    nx, ny = 11, 14
    vertices = []
    for j in range(ny+1):
        y = -.19+j*1.69/ny
        for i in range(nx+1):
            x = -.695+i*1.39/nx
            z = .21+(height-.21)*(j/ny) + random.uniform(-.025,.025)
            vertices.append((cx+x, y, z))
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j*(nx+1)+i; b = a+nx+1
            faces.extend([(a,a+1,b+1),(a,b+1,b)])
    edge = list(range(nx+1))
    edge += [j*(nx+1)+nx for j in range(1,ny+1)]
    edge += [ny*(nx+1)+i for i in range(nx-1,-1,-1)]
    edge += [j*(nx+1) for j in range(ny-1,0,-1)]
    bottom = len(vertices)
    vertices += [(vertices[k][0],vertices[k][1],.04) for k in edge]
    faces.append(tuple(bottom+i for i in range(len(edge)-1,-1,-1)))
    for i, a in enumerate(edge):
        ni = (i+1)%len(edge)
        faces.append((a,bottom+i,bottom+ni,edge[ni]))
    heap = solid('Wall-restrained shallow coal heap', vertices, faces, 'coal')
    surface = BVHTree.FromPolygons([v.co for v in heap.data.vertices], [p.vertices for p in heap.data.polygons])
    for i in range(190):
        x, y = random.uniform(-.605,.605), random.uniform(-.10,1.42)
        hit, _, _, _ = surface.ray_cast(Vector((cx+x,y,2)),Vector((0,0,-1)))
        assert hit is not None
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=(cx+x,y,hit.z-.023))
        obj = bpy.context.object; obj.name = 'Angular coal fragment embedded in heap'
        for v in obj.data.vertices:
            v.co *= random.uniform(.83, 1.13)
        obj.scale = (random.uniform(.045, .095), random.uniform(.045, .095), random.uniform(.045, .075))
        obj.rotation_euler = (random.random(), random.random(), random.random()*math.tau)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        finish(obj, 'coal')

# Short generic standard-gauge display siding. No modern clips or concrete ties.
track_y, gauge, rail_head = -2.0, 1.435, .065
for i in range(11):
    x = -2.5+i*.5
    box('Sawn timber rail tie', (x, track_y, .065), (.21, 2.50, .13), 'tie')
    for side in (-1, 1):
        ry = track_y+side*(gauge/2+rail_head/2)
        for offset in (-.085, .085):
            box('Plain rail spike head', (x, ry+offset, .157), (.035, .045, .028), 'iron')
for side in (-1, 1):
    ry = track_y+side*(gauge/2+rail_head/2)
    # Cross section follows a generic flat-bottom T rail, not an exact rail weight.
    profile = [(-.065, .13), (.065, .13), (.065, .15), (.013, .163), (.013, .225),
               (.0325, .231), (.0325, .262), (-.0325, .262), (-.0325, .231),
               (-.013, .225), (-.013, .163), (-.065, .15)]
    vertices = [(x, ry+y, z) for x in (-2.75, 2.75) for y, z in profile]
    n = len(profile)
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    solid('Closed flat-bottom iron rail', vertices, faces, 'iron')

# Validate each source component before export: closed outward solids, finite
# nonzero faces, no rigs/actions. Contacts remain a separate visual review.
solid_records = []
for obj in objects:
    bm = bmesh.new(); bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges), obj.name
    assert all(f.calc_area() > 1e-10 for f in bm.faces), obj.name
    volume = bm.calc_volume(signed=True)
    assert volume > 0, (obj.name, volume)
    solid_records.append(dict(name=obj.name, volume=volume, closed=True))
    bm.free()
bpy.ops.object.select_all(action='DESELECT')
for obj in objects: obj.select_set(True)
bpy.context.view_layer.objects.active = objects[0]
project = OUT / 'CoalYard.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb = OUT / 'CoalYard.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                          export_apply=True, export_animations=False, export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'solid-validation.json').write_text(json.dumps(dict(status='passed', scope='component closure, positive signed volume and nonzero face area; not contact or Boolean intersection validation', components=solid_records), indent=2)+'\n')
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed', brief_sha256=sha(BRIEF),
    project_sha256=sha(project), glb_sha256=sha(glb), atlas_sha256=sha(texture), objects=len(objects),
    materials=1, rigged=False, animations=0, paid_service_jobs=0, limitations=brief['reconstruction']), indent=2)+'\n')
print('COAL_YARD_AUTHORED', str(glb), flush=True)
