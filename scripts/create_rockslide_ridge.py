"""Author a static reconstructed granite cliff and grounded talus in local Mixar."""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
import bmesh
import numpy as np
from PIL import Image
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/rockslide-ridge'
OUT = BASE/'local-source-v004'
BRIEF = BASE/'local-authoring-brief-v004.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json') == brief['historical_brief_sha256']
assert all(sha(BASE/s['local_photo']) == s['sha256'] for s in brief['sources'])
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
rng = random.Random(18720326)
noise = np.random.default_rng(1872)
yy, xx = np.indices((2048, 2048))
fine = noise.normal(0, 8, (2048, 2048))
mineral = np.where(noise.random((2048, 2048)) < .065, -70, 0)
cloud = 13*np.sin(xx*.024+np.sin(yy*.006)) + 9*np.cos(xx*.009+yy*.013)
streak = np.zeros((2048, 2048))
for centre, width, strength in [(130, 30, .68), (370, 62, .52), (490, 15, .72),
                               (810, 95, .6), (1090, 36, .55), (1310, 75, .65)]:
    ribbon = np.exp(-((xx-centre-11*np.sin(yy*.004+centre)) / width)**2)
    streak = np.maximum(streak, ribbon*strength*(.55+.45*np.sin(yy*.002+centre)**2))
pixels = np.empty((2048, 2048, 3), dtype=np.float32)
for i, colour in enumerate([160, 157, 146]):
    pixels[:, :, i] = colour+fine+mineral+cloud
    pixels[:, :, i] = pixels[:, :, i]*(1-streak)+[82, 69, 48][i]*streak
    pixels[:, 1536:, i] = [195, 191, 178][i]+fine[:, 1536:]+mineral[:, 1536:]+cloud[:, 1536:]*.6
texture = OUT/'RockslideRidge_BaseColor.png'
Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).save(texture)
mat = bpy.data.materials.new('M_RockslideRidge_Granite'); mat.use_nodes = True
shader = mat.node_tree.nodes['Principled BSDF']; shader.inputs['Roughness'].default_value = .92
tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(str(texture)); tex.image.pack()
mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
objects = []


def finish(name, vertices, faces, fresh=False, smooth=False, axes=None):
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat); uv = mesh.uv_layers.new()
    for face in mesh.polygons:
        face.use_smooth = smooth
        axis = axes[face.index] if axes is not None else max(range(3), key=lambda i: abs(face.normal[i]))
        for loop in face.loop_indices:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co
            u = ((p.x if axis != 0 else p.y)+3)/6
            v = p.z/5.5 if axis != 2 else (p.y+3)/6
            uv.data[loop].uv = ((.76+.23*u) if fresh else (.01+.72*u), .01+.98*v)
    objects.append(obj)
    return obj


# One closed mass. Uneven front columns create vertical joint grooves;
# curved surface-parallel seams interrupt the face without masonry courses.
joints = [-1.69, -.83, .43, 1.53]
xs = sorted(set([-2.45+i*4.9/38 for i in range(39)] +
                [j+d for j in joints for d in (-.075, 0, .075)]))
rows = 36; verts = []
for back in (False, True):
    for j in range(rows+1):
        t = j/rows
        for x in xs:
            crest = 3.65+1.38*max(0, 1-(x/2.55)**2)**.6+.07*math.sin(x*6)
            z = t*crest*(.88 if back else 1.)
            joint = max(math.exp(-((x-q-.025*math.sin(z*1.4))/ .025)**2)*
                        (.5+.5*math.sin(z*1.1+q)**2) for q in joints)
            sheets = sum(.065*math.exp(-((z-(level+.14*x*x))/ .042)**2) for level in (1.45, 2.9))
            face = -.40-.26*math.cos(x*.8)+.10*math.sin(z*1.8+x*4)+.08*joint+sheets
            face += .07*math.sin(x*9+z*3)*math.sin(z*4.7+x*2)
            y = ((.35+2.2*max(0, 1-(x/2.5)**2)**.5)*(1-.55*t*t)+
                 .10*math.sin(z*2+x*3)) if back else face
            # Rounded upper shoulder, while retaining a steep lower face.
            y += (-.15 if back else .40)*max(0, (t-.80)/.20)**2
            verts.append((x*(1-.065*t*t)+.038*math.sin(z*2+x)*math.sin(math.pi*t), y, z))
stride = len(xs); layer = stride*(rows+1); faces = []
for side in (0, 1):
    for j in range(rows):
        for i in range(stride-1):
            a = side*layer+j*stride+i
            face = (a, a+1, a+1+stride, a+stride)
            faces.append(tuple(reversed(face)) if side else face)
for i in range(stride-1):
    faces.append((i+1, i, i+layer, i+1+layer))
    a = rows*stride+i; faces.append((a, a+1, a+1+layer, a+layer))
for i in (0, stride-1):
    for j in range(rows):
        a = j*stride+i; f = (a, a+stride, a+stride+layer, a+layer)
        faces.append(f if i == 0 else tuple(reversed(f)))
axes = [1]*(2*rows*(stride-1)) + [2]*(2*(stride-1)) + [0]*(2*rows)
assert len(axes) == len(faces)
finish('Continuous jointed granite ridge', verts, faces, smooth=True, axes=axes)

# A partially detached sheet stands on its own broad foot. Its heel meets
# the ridge, while its narrower upper portion exposes a real separation.
outline = [(-1.30, 0), (.82, 0), (1.08, .49), (.89, 1.05), (1.02, 1.75),
           (.59, 2.49), (.20, 2.59), (-.18, 2.78), (-1.04, 2.32), (-.99, 1.55), (-1.31, .76)]
slab = []
for rear in (False, True):
    for x, z in outline:
        y = (-.23 if z < .8 else -.84+.06*z) if rear else -1.17+.09*z+.06*math.sin(z*1.7+x*3)
        slab.append((x+.52, y, z))
n = len(outline)
centre = len(slab); slab.append((.47, -1.17+.09*1.35-.10, 1.35))
faces = [(i, (i+1)%n, centre) for i in range(n)]
faces += [tuple(reversed(range(n, 2*n)))]
faces += [(i+n, (i+1)%n+n, (i+1)%n, i) for i in range(n)]
finish('Supported exfoliation slab', slab, faces, fresh=True)


def block(index, x, y, size):
    # Convex angular fracture blocks with unequal cut planes, not repeated cubes.
    bm = bmesh.new()
    for _ in range(15):
        p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized()
        bm.verts.new((p.x*size, p.y*size*rng.uniform(.6, 1.), p.z*size*rng.uniform(.65, 1.25)))
    bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    unused = [v for v in bm.verts if not v.link_faces]
    if unused: bmesh.ops.delete(bm, geom=unused, context='VERTS')
    bm.verts.ensure_lookup_table(); bm.verts.index_update()
    low = min(v.co.z for v in bm.verts)
    vertices = [(v.co.x+x, v.co.y+y, v.co.z-low) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    finish(f'Angular talus block {index:02d}', vertices, faces, fresh=index%4 != 0)


for i in range(58):
    x = rng.uniform(-2.8, 2.8); y = rng.uniform(-2.5, -.25)
    # Larger rooted blocks by the cliff, smaller fragments at the outer toe.
    size = rng.uniform(.12, .26)+.44*((y+2.5)/2.25)**1.5
    block(i, x, y, size)
for i in range(15):
    block(58+i, rng.uniform(-2.8, 2.8), rng.uniform(-2.6, -.7), rng.uniform(.045, .10))
bpy.ops.object.select_all(action='DESELECT')
for obj in objects: obj.select_set(True)
bpy.context.view_layer.objects.active = objects[0]
assert not bpy.data.actions and not any(o.type == 'ARMATURE' for o in objects)
project = OUT/'RockslideRidge.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb = OUT/'RockslideRidge.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
    export_apply=True, export_animations=False, export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed', brief_sha256=sha(BRIEF),
    project_sha256=sha(project), glb_sha256=sha(glb), atlas_sha256=sha(texture), objects=len(objects),
    rigged=False, animations=0, paid_service_jobs=0, limitations=brief['reconstruction']), indent=2)+'\n')
print('ROCKSLIDE_RIDGE_AUTHORED', glb, flush=True)
