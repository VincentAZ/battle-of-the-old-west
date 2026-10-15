"""Fit goggles and a cloth neck wrap to the existing skinned character surfaces."""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from author_vigilante_headgear_candidate import (Geometry, face_surface, goggles,
    bind_pad_compression, bind_soft_expressions)
from author_vigilante_collar_candidate import interpolated_weights
from author_vigilante_neck_candidate import coordinates, weights


def fit_collar_weights(outfit, body, components=None):
    if components is None:
        adjacency = [set() for _ in outfit.data.vertices]
        for edge in outfit.data.edges:
            a, b = edge.vertices
            adjacency[a].add(b); adjacency[b].add(a)
        remaining = set(range(len(adjacency)))
        components = []
        while remaining:
            pending = [remaining.pop()]
            island = set(pending)
            while pending:
                adjacent = adjacency[pending.pop()] & remaining
                remaining.difference_update(adjacent)
                island.update(adjacent); pending.extend(adjacent)
            components.append(dict(count=len(island), indices=sorted(island)))
    bands = [c for c in components if c['count'] == 85]
    panels = [c for c in components if c['count'] == 3201]
    assert len(bands) == len(panels) == 4
    collar = {i for c in bands for i in c['indices']}
    garment = {i for c in bands+panels for i in c['indices']}
    before = coordinates(outfit)
    old_weights = weights(outfit)
    normals = [tuple(n.vector) for n in outfit.data.corner_normals]
    points = [outfit.matrix_world@v.co for v in outfit.data.vertices]
    band = BVHTree.FromPolygons(points, [list(p.vertices) for p in outfit.data.polygons
                                       if all(i in collar for i in p.vertices)])
    skin = surface_info(body)
    changed = []
    for i in sorted(garment):
        distance = band.find_nearest(points[i])[3]
        if distance >= .055:
            continue
        t = max(0., min(1., (distance-.004)/.051))
        blend = 1-t*t*(3-2*t)
        target = interpolated_weights(body, skin['points'], skin['triangles'], skin['tree'], points[i])
        current = dict(old_weights[i])
        for name in current.keys() | target.keys():
            amount = current.get(name, 0.)*(1-blend)+target.get(name, 0.)*blend
            group = outfit.vertex_groups.get(name) or outfit.vertex_groups.new(name=name)
            if amount > 1e-7:
                group.add([i], amount, 'REPLACE')
            else:
                group.remove([i])
        assert abs(sum(g.weight for g in outfit.data.vertices[i].groups)-1) < .001
        changed.append(i)
    after = weights(outfit)
    assert changed and coordinates(outfit) == before
    assert normals == [tuple(n.vector) for n in outfit.data.corner_normals]
    assert all(after[i] == old_weights[i] for i in range(len(after)) if i not in changed)
    return dict(collar_vertices=len(collar), reweighted_vertices=len(changed),
                geometry_uvs_normals_preserved=True, other_weights_preserved=True,
                method='Body-interpolated collar weights, fading into the shirt over 5.5 cm')


def atlas_patch(obj, uv):
    layer = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    for polygon in obj.data.polygons:
        for corner, index in enumerate(polygon.loop_indices):
            angle = math.tau*corner/len(polygon.vertices)
            layer.data[index].uv = (uv[0]+.0001*math.cos(angle), uv[1]+.0001*math.sin(angle))


def fitted_goggles(face, arm, material, frame_uv, lens_uv, name, lens_material=None):
    parts = goggles(face_surface(face), arm, material, frame_uv)
    bindings = {}
    for obj in parts:
        obj.name = obj.name.replace('Vigilante', name)
        if obj.name.endswith('Convex_Lenses'):
            old = obj.data.materials[0]
            obj.data.materials.clear(); obj.data.materials.append(lens_material or material)
            atlas_patch(obj, lens_uv)
            if old.users == 0:
                bpy.data.materials.remove(old)
        elif obj.name.endswith('Goggle_Cups'):
            selected = [v.index for v in obj.data.vertices if (v.index%256)//64 >= 2]
            bindings[obj.name] = bind_pad_compression(obj, face, selected)
        elif obj.name.endswith('Continuous_Strap'):
            bindings[obj.name] = bind_soft_expressions(obj, face, range(len(obj.data.vertices)))
    return parts, bindings


def surface_info(obj):
    obj.data.calc_loop_triangles()
    points = [obj.matrix_world@v.co for v in obj.data.vertices]
    triangles = [tuple(t.vertices) for t in obj.data.loop_triangles]
    return dict(obj=obj, points=points, triangles=triangles,
                tree=BVHTree.FromPolygons(points, triangles, all_triangles=True))


def binding(surface, point, triangle):
    ids = surface['triangles'][triangle]
    a, b, c = [surface['points'][i] for i in ids]
    u, v, q = b-a, c-a, point-a
    d = u.length_squared*v.length_squared-u.dot(v)**2
    assert d > 1e-16
    s = (q.dot(u)*v.length_squared-q.dot(v)*u.dot(v))/d
    t = (q.dot(v)*u.length_squared-q.dot(u)*u.dot(v))/d
    return ids, (1-s-t, s, t)


def scarf(face, body, arm, material, uv, name, garment=None):
    surfaces = [surface_info(body), surface_info(face)]
    if garment is not None:
        surfaces.append(surface_info(garment))
    geometry, bindings = Geometry(), []
    columns, rows = 192, 21
    center_y = .033
    supports = []
    for row in range(rows):
        v = row/(rows-1)
        ring = []
        for column in range(columns):
            angle = math.tau*column/columns
            direction = Vector((math.cos(angle), math.sin(angle), 0))
            front = max(0., -math.sin(angle))
            # The front drapes down from the nape, below the moving jaw.
            z = 1.495 + v*.023 - front*(.041-.002*v)
            origin = Vector((0, center_y, z))
            hits = []
            for surface in surfaces:
                # Start outside: the joined shirt includes an inner collar,
                # which an outward ray would hit before the visible fabric.
                p, normal, triangle, distance = surface['tree'].ray_cast(origin+direction*.17, -direction, .17)
                if p is not None:
                    hits.append(((p-origin).dot(direction), surface, p, normal, triangle))
            if not hits:
                # Skin below the face boundary is open beneath the shirt.
                # Bridge that opening from its complete upper neck ring.
                probe = Vector((0, center_y, 1.480))
                for surface in surfaces[:2]:
                    p, normal, triangle, distance = surface['tree'].ray_cast(probe+direction*.17, -direction, .17)
                    if p is not None:
                        hits.append(((p-probe).dot(direction), surface, p, normal, triangle))
            assert hits, ('No neck support', column, row)
            radius, surface, hit, normal, triangle = max(hits, key=lambda item:item[0])
            ring.append(dict(origin=origin, direction=direction, radius=radius,
                             surface=surface, hit=hit, normal=normal, triangle=triangle))
        supports.append(ring)
    # Cloth bridges small surface hollows instead of reproducing each triangle.
    radii = [[s['radius'] for s in ring] for ring in supports]
    for _ in range(12):
        radii = [[max(supports[r][c]['radius'],
                      (radii[r][(c-1)%columns]+radii[r][(c+1)%columns]+
                       radii[max(0,r-1)][c]+radii[min(rows-1,r+1)][c])/4)
                  for c in range(columns)] for r in range(rows)]
    for layer in range(2):
        for row in range(rows):
            v = row/(rows-1)
            for column in range(columns):
                angle = math.tau*column/columns
                support = supports[row][column]
                surface, hit, normal, triangle = (support[k] for k in ('surface','hit','normal','triangle'))
                direction = support['direction']
                folds = .0012*math.sin(v*math.pi*4 + .3*math.sin(angle*3))**2
                offset = .008 + folds + (.0015 if layer == 0 else 0.)
                p = support['origin'] + direction*(radii[row][column]+offset)
                index = geometry.vertex(p)
                # Share the neck's skinning across the cloth instead of
                # switching between unrelated shirt and face weight fields.
                surface = surfaces[0]
                hit, normal, triangle, _ = surface['tree'].find_nearest(p)
                ids, bary = binding(surface, hit, triangle)
                bindings.append((index, surface, ids, bary, normal, p-hit))
    section = columns*rows
    for layer in range(2):
        for row in range(rows-1):
            for column in range(columns):
                a = layer*section+row*columns+column
                b = layer*section+row*columns+(column+1)%columns
                geometry.face((a,b,b+columns,a+columns), [uv]*4)
    for row in (0, rows-1):
        for column in range(columns):
            a = row*columns+column; b = row*columns+(column+1)%columns
            geometry.face((a,b,b+section,a+section), [uv]*4)
    obj = geometry.object(name, material, arm)
    obj.vertex_groups.clear()
    inverse = obj.matrix_world.inverted()
    for index, surface, ids, bary, normal, offset in bindings:
        weights = {}
        parent = surface['obj']
        for i, fraction in zip(ids, bary):
            for group in parent.data.vertices[i].groups:
                key = parent.vertex_groups[group.group].name
                weights[key] = weights.get(key, 0.)+max(0., fraction)*group.weight
        total = sum(weights.values()); assert total > .99
        for key, amount in weights.items():
            if amount > 1e-7:
                group = obj.vertex_groups.get(key) or obj.vertex_groups.new(name=key)
                group.add([index], amount/total, 'REPLACE')
    obj.shape_key_add(name='Basis')
    maximum = 0.
    for source_key in list(face.data.shape_keys.key_blocks)[1:]:
        key = obj.shape_key_add(name=source_key.name)
        positions = {s['obj'].name: [s['obj'].matrix_world@p.co for p in
                     (s['obj'].data.shape_keys.key_blocks[source_key.name].data if s['obj'].data.shape_keys else s['obj'].data.vertices)]
                     for s in surfaces}
        for index, surface, ids, bary, normal, offset in bindings:
            moved = positions[surface['obj'].name]
            a,b,c = [moved[i] for i in ids]
            new_normal = (b-a).cross(c-a).normalized()
            point = sum((moved[i]*weight for i,weight in zip(ids,bary)), Vector())
            point += normal.rotation_difference(new_normal)@offset
            key.data[index].co = inverse@point
            maximum = max(maximum, (key.data[index].co-obj.data.vertices[index].co).length)
    atlas_patch(obj, uv)
    return obj, dict(vertices=len(obj.data.vertices), triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
                     maximum_expression_displacement_mm=maximum*1000,
                     method='Closed folded cloth band, barycentric skin weights and 26 surface-driven expressions',
                     bindings=[dict(vertex=i,source=s['obj'].name,triangle=ids,bary=bary,offset_m=list(offset))
                               for i,s,ids,bary,normal,offset in bindings])
