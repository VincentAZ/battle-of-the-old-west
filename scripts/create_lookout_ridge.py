"""Author the sourced, reconstructed Lookout Ridge as a static local mesh."""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from PIL import Image
from mathutils import Vector
from mathutils.noise import noise

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/holdings/expansion-review-v001/lookout-ridge'
OUT = BASE / 'local-source-v003'
BRIEF = BASE / 'local-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['status'] == 'prepared_before_local_modeling'
for name, digest in brief['source_records'].items():
    assert sha(BASE / name) == digest
for source in json.loads((BASE / 'reference-review-v001.json').read_text())['sources']:
    assert sha(BASE / source['file']) == source['sha256']
assert not OUT.exists(), 'Preserve previous modeling versions'
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)

# An angular/height atlas keeps geological layers level around every side.
# These exact hues and erosion marks are reconstruction, not a colour survey.
size = 2048
yy, xx = np.indices((size, size))
theta = xx / (size - 1) * math.tau
height = (1 - yy / (size - 1)) / .79 * 3.15
rng = np.random.default_rng(1866)
grain = rng.normal(0, 7, (size, size))
for field_size, strength in ((32, 12), (128, 8), (512, 5)):
    field = Image.fromarray(rng.integers(0, 256, (field_size, field_size), dtype=np.uint8))
    grain += (np.asarray(field.resize((size,size), Image.Resampling.BILINEAR)).astype(float)/255-.5)*strength*2
weather = (3.5*np.sin(theta*17 + height*4) +
           2.7*np.sin(theta*41 - height*7) +
           2*np.cos(theta*83 + height*13))
warp = .023*np.sin(theta*7) + .017*np.cos(theta*13)
strata = 5*np.sin((height+warp)*13) + 2.8*np.sin((height+warp)*31)
rock = np.zeros((size, size))
for level, width, phase in ((.72, .07, 0), (1.61, .105, 2), (2.38, .09, 4)):
    discontinuity = np.clip((np.sin(theta*3+phase) + .6*np.sin(theta*7-phase)+.5)*1.5, 0, 1)
    rock = np.maximum(rock, np.exp(-((height+warp-level)/width)**6)*discontinuity)
top = yy < size*.19
rock[top] = np.clip(.68+.22*np.sin(xx[top]*.029+yy[top]*.027)+.25*np.cos(xx[top]*.012-yy[top]*.049), .15, 1)
pixels = np.empty((size, size, 3), dtype=np.float32)
for channel, (sand, limestone) in enumerate(zip((185, 149, 104), (126, 124, 113))):
    pixels[:, :, channel] = sand*(1-rock)+limestone*rock+grain+weather+strata*(1-rock)
texture = OUT/'LookoutRidge_BaseColor.png'
Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_LookoutRidge_SedimentaryRock')
material.use_nodes = True
shader = material.node_tree.nodes['Principled BSDF']
shader.inputs['Roughness'].default_value = .93
tex = material.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(texture)); tex.image.pack()
material.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])

segments, rows = 128, 78
vertices, faces, uv_faces = [], [], []


def top_height(x,y):
    return 2.36-.19*x+.09*math.sin(x*1.9)*math.cos(y*2.3)+.045*noise(Vector((x*6,y*6,7)))


def crest(angle):
    # The western brow is higher; the east shoulder is worn down. No structure.
    return 2.30-.44*math.cos(angle)+.09*math.sin(angle*3)+.045*math.cos(angle*11)+.025*math.sin(angle*37)


def side_point(angle, t):
    z = t*crest(angle)
    rear = .5+.5*math.sin(angle)
    taper = 1-(.23+.18*rear)*t**1.6
    ribs = .037*math.sin(angle*17+.3*math.sin(z*2)) + .019*math.cos(angle*31-z*.8)
    wave = .023*math.sin(angle*7)+.017*math.cos(angle*13)
    ledges = 0
    for level, width, phase in ((.72,.07,0),(1.61,.105,2),(2.38,.09,4)):
        patch = max(0,min(1,(math.sin(angle*3+phase)+.6*math.sin(angle*7-phase)+.5)*1.5))
        ledges += .047*math.exp(-((z+wave-level)/width)**6)*patch
    erosion = .024*math.sin(angle*9+z*3)*math.sin(z*5+angle*2)
    point=Vector((3*math.cos(angle),1.94*math.sin(angle),z))
    grain_relief = .030*noise(point*5.7)+.015*noise(point*13.1)+.007*noise(point*27.3)
    # Short exposed shelves have chipped edges; discontinuous ledges do not
    # become a stack of complete uniform strata rings.
    ledges *= max(.08, .85+noise(point*9)*1.8)
    radius = taper+ribs*(.45+.55*t)+ledges+erosion*math.sin(math.pi*t)+grain_relief
    z += .033*noise(point*8.5)*math.sin(math.pi*t)
    x,y=3*math.cos(angle)*radius, 1.94*math.sin(angle)*radius
    z=t*top_height(x,y)+.025*noise(point*8.5)*math.sin(math.pi*t)
    return (x,y,z)


for row in range(rows+1):
    for col in range(segments):
        vertices.append(side_point(col/segments*math.tau, row/rows))
for row in range(rows):
    for col in range(segments):
        nxt = (col+1)%segments
        ids = (row*segments+col, row*segments+nxt, (row+1)*segments+nxt, (row+1)*segments+col)
        faces.append(ids)
        uv_faces.append([(u, .79*vertices[k][2]/3.15) for k,u in zip(ids,(col/segments,(col+1)/segments,(col+1)/segments,col/segments))])

# The summit is a broad, uneven surface with a slight rear rise. Concentric
# rings close it without a single large, stretched triangle fan across the top.
previous = rows*segments
for ring in range(1, 21):
    radius = 1-ring/21
    start = len(vertices)
    for col in range(segments):
        angle = col/segments*math.tau
        x,y,z = side_point(angle,1)
        x*=radius; y*=radius
        vertices.append((x,y,top_height(x,y)))
    for col in range(segments):
        nxt=(col+1)%segments
        ids=(previous+col,previous+nxt,start+nxt,start+col)
        faces.append(ids)
        uv_faces.append([((vertices[k][0]+3.4)/6.8,.815+.17*(vertices[k][1]+2.2)/4.4) for k in ids])
    previous=start
center=len(vertices); vertices.append((0,0,top_height(0,0)))
for col in range(segments):
    ids=(previous+col,previous+(col+1)%segments,center)
    faces.append(ids)
    uv_faces.append([((vertices[k][0]+3.4)/6.8,.815+.17*(vertices[k][1]+2.2)/4.4) for k in ids])
bottom=len(vertices); vertices.append((0,0,0))
for col in range(segments):
    ids=((col+1)%segments,col,bottom)
    faces.append(ids)
    uv_faces.append([((vertices[k][0]+3.4)/6.8,.01+.04*(vertices[k][1]+2.2)/4.4) for k in ids])
mesh=bpy.data.meshes.new('Continuous eroded sedimentary bluff')
mesh.from_pydata(vertices,[],faces); mesh.update()
obj=bpy.data.objects.new('LookoutRidge',mesh); bpy.context.collection.objects.link(obj)
mesh.materials.append(material)
uv=mesh.uv_layers.new()
for poly, coords in zip(mesh.polygons,uv_faces):
    poly.use_smooth=True
    for loop,coord in zip(poly.loop_indices,coords): uv.data[loop].uv=coord
bm=bmesh.new(); bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY')
assert all(edge.is_manifold for edge in bm.edges)
volume=bm.calc_volume(signed=True); assert volume>0
bm.to_mesh(mesh); bm.free()
mesh.calc_loop_triangles(); assert len(mesh.loop_triangles)<30000
bpy.context.view_layer.objects.active=obj; obj.select_set(True)
project=OUT/'LookoutRidge.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'LookoutRidge.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
    export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),
    objects=1,triangles=len(mesh.loop_triangles),closed_manifold=True,volume_m3=volume,
    rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('LOOKOUT_RIDGE_AUTHORED',glb,flush=True)
