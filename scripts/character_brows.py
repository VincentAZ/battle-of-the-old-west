"""Surface-fitted eyebrow strands that follow the existing facial shape keys.

Creates native mesh geometry, with barycentric skin/morph binding to the face.
No face texture, original skin vertex, or reference bone is changed.
"""
import math
import random

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from character_face import PROFILES, sculpt_point


STYLES = {
    'bartender': dict(arch=.0065, thickness=.004, height=1.650,
                 color=(.026, .011, .024)),
    'quanah_parker': dict(arch=.0035, thickness=.0048, height=1.6485,
                        color=(.055, .032, .018)),
    'charles_goodnight': dict(arch=.008, thickness=.0038, height=1.650,
                      color=(.027, .017, .015)),
}


def author_brows(card):
    face = bpy.data.objects['Survivor_Face_27Shapes']
    assert not face.get('surface_bound_brows'), 'Brows are already present'
    style = STYLES[card]
    mesh = face.data
    keys = mesh.shape_keys.key_blocks
    key_names = [key.name for key in keys]
    assert len(key_names) == 27 and key_names[0] == 'Basis'
    original_count = len(mesh.vertices)
    original = [vertex.co.copy() for vertex in mesh.vertices]
    world = face.matrix_world.copy()
    inverse = world.inverted()
    points = [world @ point.co for point in keys[0].data]
    mesh.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    surface = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    bindings, vertices, polygons = [], [], []
    rng = random.Random(713)

    def bind(x, z, lift=.0003):
        position = sculpt_point(Vector((x, -.07, z)), PROFILES[card])
        hit, normal, index, distance = surface.ray_cast(
            Vector((position.x, -.3, position.z)), Vector((0, 1, 0)), .35)
        assert hit is not None and normal.y < -.1, (card, x, z, 'Missing outward brow surface')
        indices = triangles[index]
        a, b, c = [points[i] for i in indices]
        u, v, delta = b-a, c-a, hit-a
        uu, uv, vv = u.dot(u), u.dot(v), v.dot(v)
        determinant = uu*vv-uv*uv
        assert determinant > 1e-20
        wb = (vv*delta.dot(u)-uv*delta.dot(v))/determinant
        wc = (uu*delta.dot(v)-uv*delta.dot(u))/determinant
        weights = (1-wb-wc, wb, wc)
        assert min(weights) > -1e-4 and max(weights) < 1.0001
        offset = normal * lift
        bindings.append((indices, weights, offset))
        vertices.append(inverse @ (hit+offset))
        return len(vertices)-1

    for side in (-1, 1):
        # The individual hairs become subpixel in a card portrait. A narrow
        # fitted base keeps the brow continuous there, while the strands keep
        # its edge detail in close shots. Taper both ends into the skin.
        base_pairs = []
        for step in range(37):
            t = step/36
            x = .016+.044*t
            center_z = style['height']+style['arch']*math.sin(math.pi*.9*t)-.003*t
            width = style['thickness']*(1-.70*t)*.66
            width *= min(1., .18+8*t, .12+10*(1-t))
            base_pairs.append([bind(side*x, center_z+width*.5*edge, .0001) for edge in (-1, 1)])
        for a, b in zip(base_pairs, base_pairs[1:]):
            polygons.extend(((a[0], a[1], b[1]), (a[0], b[1], b[0])))
        for strand in range(150):
            t = (strand + rng.uniform(-.22, .22))/149
            t = max(0., min(1., t))
            x = .016 + .044*t
            center_z = style['height'] + style['arch']*math.sin(math.pi*.9*t) - .003*t
            thickness = style['thickness'] * (1-.70*t)
            root_z = center_z - thickness*.5 + rng.uniform(-.00025, .0003)
            dx = .00065 + .0019*t
            dz = thickness * rng.uniform(.80, 1.13)
            width = rng.uniform(.00027, .00040) * (1-.35*t)
            cross = Vector((-dz, dx)).normalized()
            pairs = []
            for along in (0., .4, .8):
                half = width*.5*(1-.75*along)
                pair = [bind(side*(x+dx*along+cross.x*half*edge),
                             root_z+dz*along+cross.y*half*edge) for edge in (-1, 1)]
                pairs.append(pair)
            tip = bind(side*(x+dx), root_z+dz)
            for a, b in zip(pairs, pairs[1:]):
                polygons.extend(((a[0], a[1], b[1]), (a[0], b[1], b[0])))
            polygons.append((pairs[-1][0], pairs[-1][1], tip))

    # Orient each surface triangle outward for correct lighting from either side.
    for i, tri in enumerate(polygons):
        a, b, c = [world @ vertices[j] for j in tri]
        if (b-a).cross(c-a).dot(bindings[tri[0]][2]) < 0:
            polygons[i] = tuple(reversed(tri))
    data = bpy.data.meshes.new(card+'_SurfaceBrows')
    data.from_pydata(vertices, [], polygons)
    data.update()
    brows = bpy.data.objects.new(card+'_SurfaceBrows', data)
    bpy.context.collection.objects.link(brows)
    brows.matrix_world = world
    for name in key_names:
        key = brows.shape_key_add(name=name)
        source = keys[name]
        for point, (indices, weights, offset) in zip(key.data, bindings):
            position = sum(((world @ source.data[index].co)*weight
                            for index, weight in zip(indices, weights)), Vector()) + offset
            point.co = inverse @ position
    for group in face.vertex_groups:
        brows.vertex_groups.new(name=group.name)
    for index, (indices, weights, _) in enumerate(bindings):
        groups = {}
        for source, weight in zip(indices, weights):
            for item in mesh.vertices[source].groups:
                groups[item.group] = groups.get(item.group, 0.) + max(weight, 0.)*item.weight
        total = sum(groups.values())
        assert total > .99
        for group, weight in groups.items():
            if weight > 0:
                brows.vertex_groups[group].add([index], weight/total, 'REPLACE')
    name = 'M_'+''.join(word.title() for word in card.split('_'))+'_Brows'
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*style['color'], 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*style['color'], 1)
    shader.inputs['Roughness'].default_value = .86
    shader.inputs['Specular IOR Level'].default_value = .12
    data.materials.append(material)
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    face.select_set(True)
    brows.select_set(True)
    bpy.context.view_layer.objects.active = face
    bpy.ops.object.join()
    assert len(face.data.vertices) == original_count+len(vertices)
    assert key_names == [key.name for key in face.data.shape_keys.key_blocks]
    assert all((face.data.vertices[i].co-point).length < 1e-7 for i, point in enumerate(original))
    face['surface_bound_brows'] = card
    return {'material': name, 'material_spec': {'kind': 'solid_detail', 'base': style['color'],
             'roughness': .86, 'specular': .12, 'two_sided': True},
            'strands': 300, 'added_vertices': len(vertices), 'added_triangles': len(polygons),
            'original_face_vertices': original_count, 'original_face_vertices_unchanged': True,
            'shape_keys': key_names, 'binding': 'barycentric face triangles for all shape keys and skin weights',
            'strand_surface_offset_m': .0003, 'base_surface_offset_m': .0001,
            'fitted_base_for_card_resolution': True, 'visual_expression_review_required': True}
