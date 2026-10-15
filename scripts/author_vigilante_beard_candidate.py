"""Replace the isolated placeholder beard with a face-attached strand mesh.

Run in Blender background mode with -- --output <new source directory>.
Keeps the reviewed collar/patch and the existing atlas, rig and expressions.
Source and native visual review are required before accepting a candidate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from author_vigilante_neck_candidate import coordinates, weights
from fit_vigilante_patch import restore_outfit_normals


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_blocks(obj, components):
    mesh = obj.data
    blocks = [c for c in components if c['count'] == 1106]
    assert len(blocks) == 11
    discard = {i for c in blocks for i in c['indices']}
    assert len(discard) == 12166 and not mesh.shape_keys
    for component in blocks:
        for axis, expected in enumerate(component['bounds_m']):
            values = [mesh.vertices[i].co[axis] for i in component['indices']]
            assert max(abs(a-b) for a,b in zip((min(values), max(values)), expected)) < 1e-7
    assert all([(obj.vertex_groups[g.group].name, g.weight) for g in mesh.vertices[i].groups]
               == [('mixamorig:Head', 1.)] for i in discard)
    assert all(all(i in discard for i in p.vertices) or all(i not in discard for i in p.vertices)
               for p in mesh.polygons)
    old_normals = [tuple(n.vector) for n in mesh.corner_normals]
    old_weights = weights(obj)
    protected_vertices = {v.index: (tuple(v.co), old_weights[v.index])
                          for v in mesh.vertices if v.index not in discard}
    protected_faces = {p.index: {
        'uvs': [[tuple(layer.data[i].uv) for i in p.loop_indices] for layer in mesh.uv_layers],
        'normals': [old_normals[i] for i in p.loop_indices], 'vertices': list(p.vertices),
        'material': p.material_index, 'smooth': p.use_smooth}
        for p in mesh.polygons if all(i not in discard for i in p.vertices)}
    old_triangles = sum(len(p.vertices)-2 for p in mesh.polygons)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    vi = bm.verts.layers.int.new('beard_original_vertex')
    fi = bm.faces.layers.int.new('beard_original_face')
    for v in bm.verts:
        v[vi] = v.index
    for f in bm.faces:
        f[fi] = f.index
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v[vi] in discard], context='VERTS')
    bm.verts.index_update()
    bm.faces.index_update()
    mapping = {v.index: v[vi] for v in bm.verts}
    faces = {f.index: protected_faces[f[fi]] for f in bm.faces}
    for f in bm.faces:
        assert [v[vi] for v in f.verts] == faces[f.index]['vertices']
    bm.verts.layers.int.remove(vi)
    bm.faces.layers.int.remove(fi)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    new_weights = weights(obj)
    assert len(mapping) == len(protected_vertices)
    assert all((tuple(mesh.vertices[i].co), new_weights[i]) == protected_vertices[old]
               for i, old in mapping.items())
    error = restore_outfit_normals(mesh, faces)
    return {'removed_vertices': len(discard), 'removed_triangles': old_triangles - sum(len(p.vertices)-2 for p in mesh.polygons),
            'protected_outfit_vertices': len(mapping), 'protected_outfit_faces': len(faces),
            'other_outfit_positions_weights_uvs_topology_preserved': True,
            'maximum_protected_normal_vector_error': error}


def root_region(p, n):
    x = abs(p.x)
    # Central lower lip stays visible. Cheek line rises toward the sideburns.
    beard = (.0 <= x < .076 and p.y < .008 and 1.523 < p.z
             < 1.548 + .080 * (x / .076) ** 1.5
             and n.z > -.55 and n.y < -.12
             and not (p.y > -.037 and p.z < 1.551))
    moustache = (.003 < x < .031 and p.y < -.055 and n.y < -.45
                and 1.578 < p.z < 1.586 - .003 * x / .031)
    return 'moustache' if moustache else 'beard' if beard else None


def make_groom(face, outfit, arm, atlas_samples, seed):
    rng = random.Random(seed)
    mesh = face.data
    mesh.calc_loop_triangles()
    points = [face.matrix_world @ v.co for v in mesh.vertices]
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    surface = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    candidates = []
    areas = []
    for ids in triangles:
        a,b,c = (points[i] for i in ids)
        cross = (b-a).cross(c-a)
        if cross.length < 1e-10:
            continue
        n = cross.normalized()
        if root_region((a+b+c)/3, n):
            candidates.append((ids,n))
            areas.append(cross.length/2)
    roots = []
    counts = {'beard': 0, 'moustache': 0}
    targets = {'beard': 1500, 'moustache': 240}
    for attempt in range(50000):
        ids,n = rng.choices(candidates, weights=areas, k=1)[0]
        u = math.sqrt(rng.random())
        v = rng.random()
        bary = (1-u, u*(1-v), u*v)
        p = sum((points[i]*w for i,w in zip(ids,bary)), Vector())
        region = root_region(p,n)
        if not region or counts[region] >= targets[region]:
            continue
        roots.append((p,n,ids,bary,region))
        counts[region] += 1
        if counts == targets:
            break
    assert counts == targets, counts
    positions, polygons, vertex_uvs, bindings = [], [], [], []
    for root,normal,ids,bary,region in roots:
        sign = 1 if root.x >= 0 else -1
        undercoat = rng.random() < .38
        length = rng.uniform(.018, .032) + .013 * max(0, 1-abs(root.x)/.06)
        if root.z > 1.58:
            length *= .6
        if undercoat:
            length *= .6
        if region == 'moustache':
            length = rng.uniform(.008, .015)
            direction = Vector((sign*.85, -.17, -.5)).normalized()
        else:
            direction = Vector((-root.x*7, -.20, -1)).normalized()
        phase = rng.uniform(0, math.tau)
        radius = rng.uniform(.00055, .00085) if undercoat else rng.uniform(.00025, .00050)
        wave = rng.uniform(.001, .0022)
        tint = rng.choice(atlas_samples)['uv']
        centers = []
        for j in range(7):
            t = j/6
            point = root + normal*.00025 + direction*length*t
            point += normal * (.006*math.sin(t*math.pi*.85))
            point.x += wave * math.sin(t*8+phase) * math.sin(t*math.pi/2)
            point.y += wave * .5 * math.sin(t*7+phase) * t
            # Follow the cheek's convex surface without pulling free ends
            # back onto the neck below the jaw.
            hit, n, _, distance = surface.find_nearest(point)
            if j > 0 and (point-hit).dot(n) < .00025 and distance < .025:
                point = hit + n*.0003
            centers.append(point)
        first = len(positions)
        for j,point in enumerate(centers):
            tangent = centers[min(j+1,6)] - centers[max(0,j-1)]
            tangent.normalize()
            side = tangent.cross(normal).normalized()
            if side.length < .5:
                side = tangent.cross(Vector((1,0,0))).normalized()
            across = tangent.cross(side).normalized()
            t = j/6
            width = radius * (.25 + .75*min(1, t*7)) * (1-t)**.65
            width = max(width, .000015)
            for k in range(3):
                angle = math.tau*k/3
                positions.append(point + width*(side*math.cos(angle)+across*math.sin(angle)))
                vertex_uvs.append((tint[0] + math.cos(angle)*.00006, tint[1]+t*.0001))
                bindings.append((ids,bary))
            if j:
                for k in range(3):
                    a = first+(j-1)*3+k
                    b = first+(j-1)*3+(k+1)%3
                    c = first+j*3+(k+1)%3
                    d = first+j*3+k
                    polygons.append((a,b,c,d))
        polygons.append((first+2, first+1, first))
        polygons.append((first+18, first+19, first+20))
    data = bpy.data.meshes.new('Vigilante_Beard_Strands')
    data.from_pydata(positions, [], polygons)
    data.materials.append(outfit.data.materials[0])
    uv = data.uv_layers.new(name='UVMap')
    for loop in data.loops:
        uv.data[loop.index].uv = vertex_uvs[loop.vertex_index]
    for polygon in data.polygons:
        polygon.use_smooth = True
    groom = bpy.data.objects.new('Vigilante_Beard_Strands', data)
    bpy.context.collection.objects.link(groom)
    groom.parent = arm
    # Native shape keys must match the face names; every strand inherits
    # the barycentric displacement at its root for each expression.
    groom.shape_key_add(name='Basis')
    for key in list(face.data.shape_keys.key_blocks)[1:]:
        target = groom.shape_key_add(name=key.name)
        delta = [face.matrix_world.to_3x3() @ (k.co-v.co)
                 for k,v in zip(key.data, face.data.vertices)]
        # A translated root offset alone can cross its triangle when a lip
        # expression rotates that triangle. Transport the small root offset
        # with the local normal while retaining the strand's authored curve.
        normal_delta = {}
        for root,normal,ids,bary,region in roots:
            if ids not in normal_delta:
                a,b,c = (points[i]+delta[i] for i in ids)
                normal_delta[ids] = ((b-a).cross(c-a).normalized()-normal)*.00025
        for point, base, (ids,bary) in zip(target.data, positions, bindings):
            point.co = base + sum((delta[i]*w for i,w in zip(ids,bary)), Vector()) + normal_delta[ids]
    face_weights = weights(face)
    for index,(ids,bary) in enumerate(bindings):
        values = {}
        for i,w in zip(ids,bary):
            for name,weight in face_weights[i]:
                values[name] = values.get(name,0) + weight*w
        assert abs(sum(values.values())-1) < .001
        for name,weight in values.items():
            if weight > 1e-8:
                group = groom.vertex_groups.get(name) or groom.vertex_groups.new(name=name)
                group.add([index], weight, 'REPLACE')
    skin = groom.modifiers.new('Preserved_survivor_skin', 'ARMATURE')
    skin.object = arm
    assert groom.find_armature() == arm
    assert [k.name for k in groom.data.shape_keys.key_blocks] == [k.name for k in face.data.shape_keys.key_blocks]
    return groom, {'strand_count':len(roots), 'regions':counts, 'vertices':len(positions),
                   'triangles':sum(len(p.vertices)-2 for p in data.polygons),
                   'face_attached_morph_names':[k.name for k in groom.data.shape_keys.key_blocks][1:],
                   'root_bindings': [{'triangle':list(ids),'barycentric':list(bary),'region':region}
                                     for _,_,ids,bary,region in roots],
                   'seed':seed, 'root_clearance_m':.00025}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=91)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder = args.output.resolve()/'vigilante'
    folder.mkdir(parents=True, exist_ok=False)
    source = ROOT/'art/characters/identity-collar-vigilante-v2/vigilante/Vigilante.blend'
    assert sha(source) == 'c5bb3d68374360f25fedb89d78dd6c4ca665e817cf6b81898685b2ebcbf55844'
    work = ROOT/'game/tests/runs/polish-vigilante-beard-20260909'
    inspection = json.loads((ROOT/'game/tests/runs/polish-vigilante-collar-audit-20260909/source-neck-boundaries.json').read_text())
    samples = json.loads((work/'beard-atlas-samples.json').read_text())
    originals = {str(p):sha(p) for p in source.parent.rglob('*') if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:
            image.filepath = bpy.path.abspath(image.filepath)
    arm = bpy.data.objects['Survivor_Rig']
    rig = [(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    outfit = bpy.data.objects['Vigilante_Outfit_Assembly']
    face = bpy.data.objects['Survivor_Face_27Shapes']
    protected = {o.name:(coordinates(o), weights(o), [tuple(n.vector) for n in o.data.corner_normals])
                 for o in bpy.data.objects if o.type == 'MESH' and o != outfit}
    components = next(o for o in inspection['objects'] if o['name'] == outfit.name)['neck_components']
    removal = remove_blocks(outfit, components)
    groom, detail = make_groom(face, outfit, arm, samples, args.seed)
    assert protected == {name:(coordinates(bpy.data.objects[name]), weights(bpy.data.objects[name]),
                              [tuple(n.vector) for n in bpy.data.objects[name].data.corner_normals]) for name in protected}
    assert rig == [(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    spec = json.loads((source.parent/'manifest.json').read_text())
    spec['parts'] = [p for p in spec['parts'] if not p['name'].startswith('Beard_Braid')]
    spec['parts'].append({'name':groom.name,'vertices':detail['vertices'], 'bones':sorted(g.name for g in groom.vertex_groups)})
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
    spec['total_triangles'] = sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
    spec['outfit_triangles'] = sum(len(p.vertices)-2 for p in outfit.data.polygons)
    material_names = sorted({m.name for o in meshes for m in o.data.materials})
    assert material_names == spec['material_names']
    spec.update(beard_correction={**removal, **{k:v for k,v in detail.items() if k != 'root_bindings'}},
                status='Beard source candidate; source/native appearance and expression review required')
    blend = folder/'Vigilante.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale = Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        obj.data.transform(scale, shape_keys=True) if obj.type == 'MESH' else obj.data.transform(scale)
        obj.location *= 100
        inverse = obj.matrix_parent_inverse.copy()
        inverse.translation *= 100
        obj.matrix_parent_inverse = inverse
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fbx = folder/'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE','MESH'},
        add_leaf_bones=False, bake_anim=False, use_armature_deform_only=True, use_mesh_modifiers=False,
        mesh_smooth_type='FACE', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
    assert all(sha(Path(p)) == h for p,h in originals.items())
    spec['fbx_sha256'] = sha(fbx)
    (folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    (folder.parent/'root-bindings.json').write_text(json.dumps(detail['root_bindings'],indent=2)+'\n')
    report = {'source_sha256':sha(source), 'blend_sha256':sha(blend), 'fbx_sha256':sha(fbx),
              'protected_source_files_unchanged':True,'all_other_meshes_preserved':True,
              'rig_preserved':True,'native_imported':False,'beard_correction':spec['beard_correction'],
              'total_triangles':spec['total_triangles']}
    (folder.parent/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('BEARD_CANDIDATE_SAVED',detail['strand_count'],spec['total_triangles'],flush=True)


if __name__ == '__main__':
    main()
