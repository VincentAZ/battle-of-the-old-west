"""Fit the overlapping body neck beneath the preserved facial mesh."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def fit_neck_seam():
    face = bpy.data.objects['Survivor_Face_27Shapes']
    body = bpy.data.objects['Survivor_Body']
    body_weights = [tuple((g.group, g.weight) for g in v.groups) for v in body.data.vertices]
    points = [face.matrix_world @ v.co for v in face.data.vertices]
    surface = BVHTree.FromPolygons(points, [list(p.vertices) for p in face.data.polygons])
    bottom = min(p.z for p in points)
    ring = [p for p in points if bottom <= p.z <= bottom + .025]
    center_y = (min(p.y for p in ring) + max(p.y for p in ring)) / 2
    inverse = body.matrix_world.inverted().to_3x3()
    changed = 0
    for vertex in body.data.vertices:
        p = body.matrix_world @ vertex.co
        if p.z < bottom - .016 or p.z > bottom + .060:
            continue
        radial = Vector((p.x, p.y - center_y, 0))
        if radial.length < .005 or radial.length > .09:
            continue
        direction = radial.normalized()
        # Below the face's boundary, sample its lowest complete neck ring and
        # blend toward that radius. Within the overlap, keep the body 0.1 mm
        # inside the face so two differently textured skins cannot z-fight.
        probe_z = max(p.z, bottom)
        hit, _, _, _ = surface.ray_cast(Vector((0, center_y, probe_z)), direction)
        if hit is None:
            probe_z = max(p.z, bottom + .007)
            hit, _, _, _ = surface.ray_cast(Vector((0, center_y, probe_z)), direction)
        if hit is None or (hit - Vector((0, center_y, probe_z))).length > .10:
            continue
        target = hit - direction * .0001
        target.z = p.z
        alpha = max(0., min(1., (p.z - (bottom - .016)) / .016))
        alpha = alpha * alpha * (3 - 2 * alpha)
        delta = inverse @ ((target - p) * alpha)
        if delta.length < 1e-7:
            continue
        if body.data.shape_keys:
            for key in body.data.shape_keys.key_blocks:
                key.data[vertex.index].co += delta
        else:
            vertex.co += delta
        changed += 1
    assert changed > 0, 'No shared neck overlap found'
    body.data.update()
    # Preserve body/garment motion. Transfer the body's interpolated weights to
    # the face overlap, which originally moved rigidly with Head. Changing body
    # weights independently of the shirt opens the collar during a head turn.
    body.data.calc_loop_triangles()
    body_points = [body.matrix_world @ v.co for v in body.data.vertices]
    triangles = [tuple(t.vertices) for t in body.data.loop_triangles]
    body_surface = BVHTree.FromPolygons(body_points, triangles, all_triangles=True)
    body_top = max(p.z for p in body_points)
    count = 0
    for vertex in face.data.vertices:
        p = face.matrix_world @ vertex.co
        if p.z >= body_top + .035:
            continue
        hit, _, triangle_index, distance = body_surface.find_nearest(p)
        if hit is None or distance > .08:
            continue
        ids = triangles[triangle_index]
        p0, p1, p2 = (body_points[index] for index in ids)
        edge0, edge1, relative = p1 - p0, p2 - p0, hit - p0
        d00, d01, d11 = edge0.dot(edge0), edge0.dot(edge1), edge1.dot(edge1)
        denominator = d00 * d11 - d01 * d01
        if abs(denominator) < 1e-18:
            continue
        w1 = (d11 * relative.dot(edge0) - d01 * relative.dot(edge1)) / denominator
        w2 = (d00 * relative.dot(edge1) - d01 * relative.dot(edge0)) / denominator
        interpolated = {}
        for index, amount in zip(ids, (1 - w1 - w2, w1, w2)):
            for group in body.data.vertices[index].groups:
                name = body.vertex_groups[group.group].name
                interpolated[name] = interpolated.get(name, 0) + group.weight * max(0., amount)
        total = sum(interpolated.values())
        assert total > .99
        fade = max(0., min(1., (p.z - body_top) / .035))
        fade = fade * fade * (3 - 2 * fade)
        previous = {face.vertex_groups[g.group].name: g.weight for g in vertex.groups}
        for name in previous.keys() | interpolated.keys():
            weight = previous.get(name, 0) * fade + interpolated.get(name, 0) / total * (1 - fade)
            group = face.vertex_groups.get(name) or face.vertex_groups.new(name=name)
            if weight > 1e-7:
                group.add([vertex.index], weight, 'REPLACE')
            else:
                group.remove([vertex.index])
        assert abs(sum(g.weight for g in vertex.groups) - 1) < .001
        count += 1
    face['neck_body_weight_transfer_vertices'] = count
    assert body_weights == [tuple((g.group, g.weight) for g in v.groups) for v in body.data.vertices]
    body['neck_body_weights_preserved'] = True
    body['neck_seam_vertices_fitted'] = changed
    body['neck_face_boundary_world_m'] = bottom
    return changed
