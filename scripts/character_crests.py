"""Build a scalp-fitted, skinned crest from closed tapered strand geometry."""
import math
import random

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def fitted_crest(face, arm, material, name, *, long=False, atlas_uv=None):
    face.data.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in face.data.loop_triangles]
    points = [face.matrix_world @ v.co for v in face.data.vertices]
    tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    vertices, faces, strands = [], [], []
    randomizer = random.Random(12019 if long else 12011)
    levels = [0., .05, .15, .30, .50, .70, .86, .96]
    sides = 5
    for row in range(33):
        u = row / 32
        for column in range(9):
            x = (column-4)*.003 + randomizer.uniform(-.00045, .00045)
            y = -.027 + u*.141 + randomizer.uniform(-.0005, .0005)
            hit, normal, triangle, _ = tree.ray_cast(Vector((x, y, 2.2)), Vector((0, 0, -1)), .6)
            assert hit is not None and normal.z > .30, ('Crest root is outside the crown', x, y)
            ids = triangles[triangle]
            assert all(sum(g.weight for g in face.data.vertices[i].groups
                           if face.vertex_groups[g.group].name == 'mixamorig:Head') > .999 for i in ids)
            a, b, c = [points[i] for i in ids]
            edge_b, edge_c, relative = b-a, c-a, hit-a
            denominator = edge_b.length_squared*edge_c.length_squared-edge_b.dot(edge_c)**2
            s = (relative.dot(edge_b)*edge_c.length_squared-relative.dot(edge_c)*edge_b.dot(edge_c))/denominator
            t = (relative.dot(edge_c)*edge_b.length_squared-relative.dot(edge_b)*edge_b.dot(edge_c))/denominator
            bary = (1-s-t, s, t)
            root = hit-normal*.0012
            height = (.145 if long else .076) * (.70+.30*math.sin(math.pi*u)) * randomizer.uniform(.90, 1.08)
            # Dense roots open into a thin swept fan, with irregular fine tips.
            drift = Vector((x*.30+randomizer.uniform(-.003, .003), (.033 if long else .017)+u*.01, 0.))
            direction = (normal*.28+Vector((0, 0, .72))).normalized()
            radius = randomizer.uniform(.0016, .0022)
            start = len(vertices)
            for level in levels:
                center = root + direction*(height*level) + drift*(level*level)
                tangent = (direction*height + drift*(2*level)).normalized()
                side = Vector((1, 0, 0))
                side = (side-tangent*side.dot(tangent)).normalized()
                across = tangent.cross(side).normalized()
                width = radius*(1-level)**.72
                for side_index in range(sides):
                    angle = math.tau*side_index/sides
                    vertices.append(center+width*(side*math.cos(angle)+across*math.sin(angle)))
            tip = len(vertices)
            vertices.append(root+direction*height+drift)
            faces.append(tuple(start+i for i in reversed(range(sides))))
            for ring in range(len(levels)-1):
                for i in range(sides):
                    faces.append((start+ring*sides+i, start+ring*sides+(i+1)%sides,
                                  start+(ring+1)*sides+(i+1)%sides, start+(ring+1)*sides+i))
            for i in range(sides):
                faces.append((start+(len(levels)-1)*sides+i, start+(len(levels)-1)*sides+(i+1)%sides, tip))
            strands.append(dict(start=start, end=len(vertices), root=list(root), hit=list(hit),
                                normal=list(normal), triangle=ids, bary=bary, height_m=height))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name='UVMap')
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        for corner, loop in enumerate(polygon.loop_indices):
            angle = math.tau*corner/len(polygon.vertices)
            # Reuse a verified dyed-hair patch of the existing outfit atlas.
            uv.data[loop].uv = ((atlas_uv[0]+.0001*math.cos(angle), atlas_uv[1]+.0001*math.sin(angle))
                                if atlas_uv else (.5+.48*math.cos(angle), .5+.48*math.sin(angle)))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = arm
    obj.matrix_world = Matrix.Identity(4)
    obj.vertex_groups.new(name='mixamorig:Head').add(list(range(len(vertices))), 1., 'REPLACE')
    modifier = obj.modifiers.new('Preserved_survivor_skin', 'ARMATURE')
    modifier.object = arm
    obj.shape_key_add(name='Basis')
    maximum_delta = 0.
    for source_key in list(face.data.shape_keys.key_blocks)[1:]:
        target = obj.shape_key_add(name=source_key.name)
        moved = [face.matrix_world @ p.co for p in source_key.data]
        for strand in strands:
            ids, bary = strand['triangle'], strand['bary']
            a, b, c = [moved[i] for i in ids]
            normal = (b-a).cross(c-a).normalized()
            rotation = Vector(strand['normal']).rotation_difference(normal)
            hit = sum((moved[i]*w for i, w in zip(ids, bary)), Vector())
            for i in range(strand['start'], strand['end']):
                target.data[i].co = hit + rotation @ (vertices[i]-Vector(strand['hit']))
                maximum_delta = max(maximum_delta, (target.data[i].co-vertices[i]).length)
    mesh.calc_loop_triangles()
    return obj, dict(strands=len(strands), vertices=len(vertices), triangles=len(mesh.loop_triangles),
                     style='long swept crest' if long else 'short swept crest', roots=strands,
                     root_embed_mm=1.2, expression_count=len(obj.data.shape_keys.key_blocks)-1,
                     maximum_expression_displacement_mm=maximum_delta*1000,
                     material_preserved=material.name, atlas_uv=atlas_uv)
