"""Export the exact central terrain as collision geometry, using Blender.

The visible terrain and its authored triangulation are never regenerated. This
copies the existing 130m square around the fixed arena into a separate FBX.
"""
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/world'
SOURCE = OUT/'ContinuousTerrain.blend'
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
assert len(objects) == 1
source = objects[0]
assert all(abs(source.matrix_world[row][col] - (row == col)) < 1e-6
           for row in range(4) for col in range(4)), 'Source has an unexpected transform'
mesh = source.data
xyz = np.empty((len(mesh.vertices), 3), dtype=np.float32)
mesh.vertices.foreach_get('co', xyz.ravel())
inside = np.all(np.abs(xyz[:, :2]) <= 65.0, axis=1)
indices = np.flatnonzero(inside)
mapping = np.full(len(xyz), -1, dtype=np.int32)
mapping[indices] = np.arange(len(indices))
positions = xyz[indices].copy()
faces = [tuple(int(mapping[i]) for i in poly.vertices) for poly in mesh.polygons
         if all(inside[i] for i in poly.vertices)]
assert len(positions) == 261*261 and len(faces) == 260*260
assert all(len(face) == 4 for face in faces)
assert {float(value) for value in positions[:, 0]} == {i*.5 for i in range(-130, 131)}
assert {float(value) for value in positions[:, 1]} == {i*.5 for i in range(-130, 131)}
source_triangles = sum(len(poly.vertices)-2 for poly in mesh.polygons)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
collision = bpy.data.meshes.new('ContinuousTerrain_Collision')
collision.from_pydata(positions.tolist(), [], faces)
collision.update()
obj = bpy.data.objects.new('SM_ContinuousTerrain_Collision', collision)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ContinuousTerrain_Collision.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'ContinuousTerrain_Collision.fbx'),
    use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
    add_leaf_bones=False, bake_anim=False, axis_forward='-Y', axis_up='Z',
    mesh_smooth_type='FACE')

# Independently reload the exported file to catch unit or axis mistakes before
# Unreal imports it. The source .blend remains byte-for-byte unchanged.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(OUT/'ContinuousTerrain_Collision.fbx'), use_anim=False)
objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
assert len(objects) == 1
obj = objects[0]
actual = np.array([tuple(obj.matrix_world @ vertex.co) for vertex in obj.data.vertices])
assert len(actual) == len(positions)
order = lambda points: np.lexsort((np.round(points[:, 1], 3), np.round(points[:, 0], 3)))
error = float(np.max(np.abs(actual[order(actual)]-positions[order(positions)])))
assert error < .00001, 'FBX units or positions changed'
actual_faces = []
for poly in obj.data.polygons:
    points = [tuple(np.round(actual[index], 4)) for index in poly.vertices]
    first = min(range(len(points)), key=lambda index: points[index])
    actual_faces.append(tuple(points[first:]+points[:first]))
source_faces = []
for face in faces:
    points = [tuple(np.round(positions[index].astype(float), 4)) for index in face]
    first = min(range(len(points)), key=lambda index: points[index])
    source_faces.append(tuple(points[first:]+points[:first]))
assert set(actual_faces) == set(source_faces), 'FBX changed face topology or winding'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
report = dict(ok=True, source=str(SOURCE.relative_to(ROOT)), source_sha256=source_hash,
    visible_source_unchanged=True, extent_m=[-65, 65], vertices=len(positions),
    quads=len(faces), triangles=len(faces)*2, previous_collision_triangles=source_triangles,
    collision_triangle_reduction_percent=round(100*(1-len(faces)*2/source_triangles), 2),
    exact_source_vertices_and_faces=True, fbx_maximum_coordinate_error_m=error,
    fbx_face_topology_and_winding_preserved=True,
    limitation='Collision covers the fixed arena and its cameras; the distant scenic terrain remains visual only.')
(OUT/'terrain-collision-geometry.json').write_text(json.dumps(report, indent=2)+'\n')
print('TERRAIN_COLLISION_EXPORTED '+json.dumps(report), flush=True)
