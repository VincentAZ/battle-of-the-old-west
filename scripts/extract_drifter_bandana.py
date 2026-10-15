"""Derive a separate cloth candidate; never save over the approved Drifter."""
import colorsys
import hashlib
import json
import os
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/drifter/reveal-bandana-v001'
OUT = BASE/os.environ.get('OLDWEST_BANDANA_EXTRACTION', 'extraction-v004')
record = json.loads((BASE/'components.json').read_text())
source = ROOT/record['source']
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
brief = ROOT/'research/western-presentation/drifter-reveal-bandana.json'
assert brief.exists()
assert not OUT.exists(), 'Preserve previous extractions'
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
body = bpy.data.objects[record['object']]
material = body.data.materials[0]
texture = next(n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and 'BaseColor' in n.image.name)
width, height = texture.size
pixels = np.empty(width*height*4, dtype=np.float32)
texture.pixels.foreach_get(pixels)
pixels = pixels.reshape(height, width, 4)
mesh = bmesh.new()
mesh.from_mesh(body.data)
# This ROI excludes the coat torso, hat, ears and rear hair. Subdivision only
# interpolates the copied source surface and UVs; it never changes the source.
def in_region(point):
    p = body.matrix_world @ point
    # Below the jaw the folded cloth tapers to a chest point. Trim the
    # adjoining brown lapel lip which the colour-only mask also selected.
    half_width = min(.113, .002+max(0., p.z-1.40)*.46)
    return abs(p.x) < half_width and -.16 < p.y < -.016 and 1.380 < p.z < 1.676
bmesh.ops.delete(mesh, geom=[f for f in mesh.faces if not any(in_region(v.co) for v in f.verts)], context='FACES')
bmesh.ops.subdivide_edges(mesh, edges=list(mesh.edges), cuts=3, use_grid_fill=True)
uv_layer = mesh.loops.layers.uv.active
def cloth(face):
    if not in_region(face.calc_center_median()):
        return False
    uv = sum((loop[uv_layer].uv for loop in face.loops), Vector((0, 0)))/len(face.loops)
    rgb = pixels[min(height-1, max(0, int(uv.y*height))), min(width-1, max(0, int(uv.x*width))), :3]
    hue, saturation, value = colorsys.rgb_to_hsv(*map(float, rgb))
    return hue < .048 and saturation > .25 and value > .15 and rgb[0] > rgb[1]*1.32
bmesh.ops.delete(mesh, geom=[f for f in mesh.faces if not cloth(f)], context='FACES')
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if not v.link_faces], context='VERTS')
# Rejoin the copied UV seams and remove detached texture-mask specks. The
# separate cloth prop has a sewn outline, not a ragged triangle-mask edge.
bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=.00001)
unvisited = set(mesh.verts)
islands = []
while unvisited:
    pending = [unvisited.pop()]
    island = set(pending)
    while pending:
        vertex = pending.pop()
        for edge in vertex.link_edges:
            neighbor = edge.other_vert(vertex)
            if neighbor in unvisited:
                unvisited.remove(neighbor)
                island.add(neighbor)
                pending.append(neighbor)
    islands.append(island)
main_island = max(islands, key=len)
bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v not in main_island], context='VERTS')
boundary_edges = {edge for edge in mesh.edges if edge.is_boundary}
loops = []
while boundary_edges:
    pending = [boundary_edges.pop()]
    connected = set(pending)
    while pending:
        for vertex in pending.pop().verts:
            for edge in vertex.link_edges:
                if edge in boundary_edges:
                    boundary_edges.remove(edge)
                    connected.add(edge)
                    pending.append(edge)
    loops.append(connected)
outer = max(loops, key=lambda edges: sum(e.calc_length() for e in edges))
initial_boundary_perimeters = [sum(e.calc_length() for e in edges) for edges in loops]
holes_filled = 0
for edges in loops:
    if edges != outer and sum(e.calc_length() for e in edges) < .08:
        # Hole fill does not infer texture coordinates. Carry each boundary
        # vertex's existing cloth UV across the new face, rather than sample
        # the atlas origin (which painted a dark slit on the previous attempt).
        existing_uv = {v: next(loop[uv_layer].uv.copy() for loop in v.link_loops)
                       for edge in edges for v in edge.verts}
        filled = bmesh.ops.holes_fill(mesh, edges=list(edges), sides=0)
        for face in filled['faces']:
            for loop in face.loops:
                loop[uv_layer].uv = existing_uv[loop.vert]
        holes_filled += 1
boundary = {v for e in mesh.edges if e.is_boundary for v in e.verts}
for _ in range(8):
    next_positions = {}
    for vertex in boundary:
        neighbors = [e.other_vert(vertex).co for e in vertex.link_edges if e.is_boundary]
        if len(neighbors) == 2:
            next_positions[vertex] = vertex.co.lerp((neighbors[0]+neighbors[1])*.5, .5)
    for vertex, position in next_positions.items():
        vertex.co = position
data = bpy.data.meshes.new('Bandana_Drop_Candidate')
mesh.to_mesh(data)
mesh.free()
prop = bpy.data.objects.new('Bandana_Drop_Candidate', data)
bpy.context.scene.collection.objects.link(prop)
prop.matrix_world = body.matrix_world.copy()
data.materials.append(material)
for poly in data.polygons:
    poly.use_smooth = True
for obj in list(bpy.context.scene.objects):
    if obj != prop:
        bpy.data.objects.remove(obj, do_unlink=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.render.resolution_x = scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.world.color = (.35, .35, .35)
center = Vector((0, -.08, 1.56))
for pos, energy in [((1, -3, 4), 300), ((-2, -1, 2), 180)]:
    light_data = bpy.data.lights.new('ClothReviewLight', 'AREA')
    light_data.energy, light_data.size = energy, 2
    lamp = bpy.data.objects.new('ClothReviewLight', light_data)
    scene.collection.objects.link(lamp)
    lamp.location = pos
    lamp.rotation_euler = (center-lamp.location).to_track_quat('-Z', 'Y').to_euler()
camera_data = bpy.data.cameras.new('ClothReviewCamera')
camera = bpy.data.objects.new('ClothReviewCamera', camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type, camera_data.ortho_scale = 'ORTHO', .32
captures = []
for name, offset in [('front', (0, -2, 0)), ('quarter', (.8, -2, .1)), ('rear', (0, 2, 0))]:
    camera.location = center+Vector(offset)
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    target = OUT/(name+'.png')
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
    captures.append(dict(path=str(target.relative_to(ROOT)), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
project = OUT/'Bandana_Drop_Candidate.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
(OUT/'authoring.json').write_text(json.dumps(dict(status='candidate_requires_visual_review',
    source=record['source'], source_sha256=record['source_sha256'], source_unchanged=True,
    brief_sha256=hashlib.sha256(brief.read_bytes()).hexdigest(), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(), vertices=len(data.vertices),
    polygons=len(data.polygons), holes_filled=holes_filled, detached_islands_removed=len(islands)-1,
    initial_boundary_perimeters_m=initial_boundary_perimeters,
    method='Copied source face region, interpolated UV subdivision, red-cloth centroid mask, joined UV seams, removed detached specks, filled tiny interior holes, smoothed outer edge; no body edits. No claim of accepted isolation until rendered views are inspected.',
    captures=captures), indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
