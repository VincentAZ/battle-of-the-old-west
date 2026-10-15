"""Repair the inherited isolated ring-finger weight by connectivity, not vertex ID.

Only matches a rigid RightHandPinky1 vertex surrounded by eight neighbours
weighted exclusively to RightHandRing2/3. Does not smooth unrelated hand skin.
"""


def correct_isolated_ring_vertex(body):
    bad = 'mixamorig:RightHandPinky1'
    ring = {'mixamorig:RightHandRing2', 'mixamorig:RightHandRing3'}
    vertices = body.data.vertices
    weights = [{body.vertex_groups[g.group].name: g.weight for g in v.groups if g.weight > 1e-7}
               for v in vertices]
    adjacent = [set() for v in vertices]
    for edge in body.data.edges:
        a, b = edge.vertices
        adjacent[a].add(b)
        adjacent[b].add(a)
    candidates = [i for i, w in enumerate(weights) if w == {bad: 1.0}
                  and len(adjacent[i]) == 8
                  and all(set(weights[j]) == ring for j in adjacent[i])]
    assert len(candidates) <= 1, 'Unexpected multiple isolated ring-finger candidates'
    repairs = []
    for i in candidates:
        neighbors = sorted(adjacent[i])
        blended = {name: 0. for name in sorted(ring)}
        total = 0.
        for j in neighbors:
            length = (vertices[i].co - vertices[j].co).length
            assert length > 1e-8, 'Coincident hand edge requires a separate review'
            influence = 1. / length
            total += influence
            for name, value in weights[j].items():
                blended[name] += value * influence
        for group in list(vertices[i].groups):
            body.vertex_groups[group.group].remove([i])
        for name, value in blended.items():
            body.vertex_groups[name].add([i], value / total, 'REPLACE')
        after = {body.vertex_groups[g.group].name: g.weight for g in vertices[i].groups}
        assert abs(sum(after.values()) - 1.) < 1e-6
        repairs.append({'vertex': i, 'neighbors': neighbors, 'before': weights[i], 'after': after,
                        'method': 'Inverse-edge-length interpolation from eight connected ring-finger neighbours'})
    return repairs
