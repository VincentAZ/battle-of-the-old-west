"""Derive fitted Vigilante headgear while retaining the reviewed strand beard.

Blender --background --python this_file -- --output <new source directory>.
Creates a separate source candidate; native import requires visual review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates, weights
from fit_vigilante_patch import restore_outfit_normals

LENS = 'M_Vigilante_SmokedLens'
LENS_SPEC = {'kind':'solid_detail', 'base':[.009,.019,.015], 'roughness':.14,
             'specular':.5, 'two_sided':False}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_components(obj, blocks, allowed_bones=('mixamorig:Head',)):
    mesh = obj.data
    discard = {i for c in blocks for i in c['indices']}
    assert discard and not mesh.shape_keys
    for component in blocks:
        for axis, expected in enumerate(component['bounds_m']):
            values = [mesh.vertices[i].co[axis] for i in component['indices']]
            assert max(abs(a-b) for a,b in zip((min(values), max(values)), expected)) < 1e-7
    assert all(len(mesh.vertices[i].groups) == 1
               and obj.vertex_groups[mesh.vertices[i].groups[0].group].name in allowed_bones
               and mesh.vertices[i].groups[0].weight == 1. for i in discard)
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
    vi = bm.verts.layers.int.new('headgear_original_vertex')
    fi = bm.faces.layers.int.new('headgear_original_face')
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



class Geometry:
    def __init__(self):
        self.vertices, self.faces, self.uvs = [], [], []

    def vertex(self, point):
        self.vertices.append(Vector(point))
        return len(self.vertices)-1

    def face(self, indices, uvs=None):
        self.faces.append(tuple(indices))
        self.uvs.append(uvs or [(0.5,0.5)]*len(indices))

    def ring_tube(self, points, radius, uv, sides=8, closed=True):
        first = len(self.vertices)
        for i,p in enumerate(points):
            prev = points[(i-1)%len(points)] if closed or i else points[i]
            following = points[(i+1)%len(points)] if closed or i+1<len(points) else points[i]
            tangent = (following-prev).normalized()
            side = tangent.cross(Vector((0,0,1))).normalized()
            if side.length < .5:
                side = tangent.cross(Vector((0,1,0))).normalized()
            across = tangent.cross(side).normalized()
            for j in range(sides):
                angle = j*math.tau/sides
                self.vertex(p+radius*(side*math.cos(angle)+across*math.sin(angle)))
        for i in range(len(points) if closed else len(points)-1):
            for j in range(sides):
                self.face((first+i*sides+j, first+i*sides+(j+1)%sides,
                           first+(i+1)%len(points)*sides+(j+1)%sides,
                           first+(i+1)%len(points)*sides+j), [uv]*4)
        if not closed:
            self.face(tuple(first+j for j in reversed(range(sides))), [uv]*sides)
            self.face(tuple(first+(len(points)-1)*sides+j for j in range(sides)), [uv]*sides)

    def object(self, name, material, arm):
        data = bpy.data.meshes.new(name)
        data.from_pydata(self.vertices, [], self.faces)
        data.materials.append(material)
        uv = data.uv_layers.new(name='UVMap')
        for polygon, coords in zip(data.polygons,self.uvs):
            polygon.use_smooth = True
            for i,value in zip(polygon.loop_indices,coords):
                uv.data[i].uv = value
        # Recalculate the closed surfaces consistently after construction.
        bm = bmesh.new()
        bm.from_mesh(data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        boundary = sum(not e.is_manifold for e in bm.edges)
        bm.to_mesh(data)
        bm.free()
        obj = bpy.data.objects.new(name,data)
        bpy.context.collection.objects.link(obj)
        obj.parent = arm
        obj.vertex_groups.new(name='mixamorig:Head').add(list(range(len(data.vertices))),1,'REPLACE')
        skin = obj.modifiers.new('Preserved_survivor_skin','ARMATURE')
        skin.object = arm
        obj['nonmanifold_edges'] = boundary
        assert boundary == 0, (name,boundary)
        return obj


def face_surface(face):
    face.data.calc_loop_triangles()
    points = [face.matrix_world@v.co for v in face.data.vertices]
    triangles = [tuple(t.vertices) for t in face.data.loop_triangles]
    return BVHTree.FromPolygons(points,triangles,all_triangles=True)


def skin_front(tree,x,z,offset=.003):
    p,n,_,_ = tree.ray_cast(Vector((x,-.3,z)),Vector((0,1,0)),.4)
    assert p is not None and n.y < -.1, (x,z,p,n)
    return p+n*offset


def radial_skin(tree,angle,z,offset):
    direction = Vector((math.cos(angle),math.sin(angle),0))
    center = Vector((0,.025,z))
    p,n,_,_ = tree.ray_cast(center+direction*.25,-direction,.3)
    assert p is not None
    return p+n*offset


def bind_soft_expressions(obj, face, indices):
    """Attach soft fabric/pad vertices to the face without bending the lenses.

    Retain each authored offset and rotate it with its supporting face triangle.
    The front pad rings stay rigid, so the padded cup compresses behind its rim.
    """
    face.data.calc_loop_triangles()
    positions = [face.matrix_world @ v.co for v in face.data.vertices]
    triangles = [tuple(t.vertices) for t in face.data.loop_triangles]
    tree = BVHTree.FromPolygons(positions, triangles, all_triangles=True)
    inverse = obj.matrix_world.inverted()
    bindings = []
    for index in indices:
        point = obj.matrix_world @ obj.data.vertices[index].co
        hit, normal, triangle, _ = tree.find_nearest(point)
        ids = triangles[triangle]
        a,b,c = [positions[i] for i in ids]
        u,v,q = b-a,c-a,hit-a
        denominator = u.dot(u)*v.dot(v)-u.dot(v)**2
        assert denominator > 1e-16
        s = (q.dot(u)*v.dot(v)-q.dot(v)*u.dot(v))/denominator
        t = (q.dot(v)*u.dot(u)-q.dot(u)*u.dot(v))/denominator
        bindings.append((index, ids, (1-s-t,s,t), normal, point-hit))
    obj.shape_key_add(name='Basis')
    maximum = 0.
    for key in list(face.data.shape_keys.key_blocks)[1:]:
        target = obj.shape_key_add(name=key.name)
        moved = [face.matrix_world @ v.co for v in key.data]
        for index, ids, bary, normal, offset in bindings:
            a,b,c = [moved[i] for i in ids]
            new_normal = (b-a).cross(c-a).normalized()
            point = sum((moved[i]*w for i,w in zip(ids,bary)), Vector())
            point += normal.rotation_difference(new_normal) @ offset
            target.data[index].co = inverse @ point
            maximum = max(maximum, (target.data[index].co-obj.data.vertices[index].co).length)
    return {'bound_vertices':len(bindings), 'maximum_expression_displacement_mm':maximum*1000,
            'morph_names':[k.name for k in obj.data.shape_keys.key_blocks][1:]}


def bind_pad_compression(obj, face, indices):
    """Compress rear padding in depth, preserving the rigid rim's silhouette."""
    face.data.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in face.data.loop_triangles]
    points = {i:obj.matrix_world@obj.data.vertices[i].co for i in indices}
    def surface_y(tree, point):
        hit,_,_,_ = tree.ray_cast(Vector((point.x,-.3,point.z)),Vector((0,1,0)),.4)
        assert hit is not None, tuple(point)
        return hit.y
    base_tree = face_surface(face)
    baseline = {i:surface_y(base_tree,p) for i,p in points.items()}
    inverse = obj.matrix_world.inverted()
    obj.shape_key_add(name='Basis')
    maximum = 0.
    for key in list(face.data.shape_keys.key_blocks)[1:]:
        target = obj.shape_key_add(name=key.name)
        moved = [face.matrix_world@v.co for v in key.data]
        tree = BVHTree.FromPolygons(moved,triangles,all_triangles=True)
        for i,p in points.items():
            delta = surface_y(tree,p)-baseline[i]
            target.data[i].co = inverse@(p+Vector((0,delta,0)))
            maximum = max(maximum,abs(delta))
    return {'bound_vertices':len(points), 'maximum_expression_displacement_mm':maximum*1000,
            'method':'Rear padding follows front skin depth at fixed x/z; front rings stay rigid',
            'morph_names':[k.name for k in obj.data.shape_keys.key_blocks][1:]}


def fitted_cap(outfit,component,tree,arm):
    ids = component['indices']
    assert len(ids)==1690
    inverse_ids = {old:i for i,old in enumerate(ids)}
    mesh = outfit.data
    old_faces = [p for p in mesh.polygons if all(i in inverse_ids for i in p.vertices)]
    geo = Geometry()
    center = Vector((0,.025,1.674))
    for layer in range(2):
        for row in range(13):
            theta = max(.004,(1-row/12)*math.pi/2)
            for col in range(64):
                phi = col*math.tau/64
                direction = Vector((math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta)))
                p,n,_,_ = tree.ray_cast(center+direction*.3,-direction,.4)
                assert p is not None
                lift = .004 if layer==0 else .0012
                geo.vertex(p+n*lift)
    for face in old_faces:
        old = [inverse_ids[i] for i in face.vertices]
        layers = {i//845 for i in old}
        rows = {(i%845)//65 for i in old}
        cols = {(i%845)%65 for i in old}
        # The old loft had duplicate end walls along its UV seam and an
        # uncapped crown. Weld the circumference and cap each crown surface.
        if len(layers)>1 and (rows=={12} or cols in ({0},{64})):
            continue
        mapped = [(i//845)*832+((i%845)//65)*64+(i%65)%64 for i in old]
        if len(set(mapped))<3:
            continue
        geo.face(mapped,[tuple(mesh.uv_layers.active.data[i].uv) for i in face.loop_indices])
    sample = component['uv_samples'][0]
    crown, crown_normal, _, _ = tree.ray_cast(center+Vector((0,0,.3)),Vector((0,0,-1)),.4)
    assert crown is not None
    for layer in range(2):
        top = geo.vertex(crown+crown_normal*(.004 if layer==0 else .0012))
        for col in range(64):
            ring = layer*832+12*64
            geo.face((ring+col,ring+(col+1)%64,top),[sample]*3)
    cap = geo.object('Vigilante_Fitted_Cap',mesh.materials[0],arm)
    detail = Geometry()
    for z,radius in [(1.675,.0016),(1.685,.0008)]:
        points = [radial_skin(tree,i*math.tau/96,z,.005) for i in range(96)]
        detail.ring_tube(points,radius,sample)
    # Two panel seams cross the crown, with continuous closed thread cords.
    for phi in [0,math.pi/2]:
        points=[]
        for i in range(49):
            theta=-math.pi/2+i*math.pi/48
            direction=Vector((math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta)))
            p,n,_,_=tree.ray_cast(center+direction*.3,-direction,.4)
            assert p is not None
            points.append(p+n*.005)
        detail.ring_tube(points,.00065,sample,sides=6,closed=False)
    seam=detail.object('Vigilante_Cap_Hem_And_Seams',mesh.materials[0],arm)
    return [cap,seam]


def goggles(tree,arm,material,uv):
    cups,frames,lenses = Geometry(),Geometry(),Geometry()
    count = 64
    for sign in [-1,1]:
        cx,cz = sign*.0335,1.638
        first = len(cups.vertices)
        front_points=[]
        for ring in range(4):
            for i in range(count):
                angle=i*math.tau/count
                rx,rz=[(.027,.023),(.022,.0185),(.022,.0185),(.027,.023)][ring]
                x,z=cx+rx*math.cos(angle),cz+rz*math.sin(angle)
                y=-.078+sign*(x-cx)*.65
                p=Vector((x,y,z)) if ring<2 else skin_front(tree,x,z,.003)
                cups.vertex(p)
                if ring==0:
                    front_points.append(Vector((x,y-.0008,z)))
        for ring in range(4):
            for i in range(count):
                cups.face((first+ring*count+i, first+ring*count+(i+1)%count,
                           first+(ring+1)%4*count+(i+1)%count,first+(ring+1)%4*count+i),[uv]*4)
        frames.ring_tube(front_points,.0017,uv)
        first=len(lenses.vertices)
        for row in range(6):
            r=max(.005,1-row/5)
            for i in range(count):
                theta=i*math.tau/count
                x,z=cx+.022*r*math.cos(theta),cz+.0185*r*math.sin(theta)
                y=-.078+sign*(x-cx)*.65-.003*(1-r*r)-.0004
                lenses.vertex((x,y,z))
        for row in range(5):
            for i in range(count):
                lenses.face((first+row*count+i,first+row*count+(i+1)%count,
                             first+(row+1)*count+(i+1)%count,first+(row+1)*count+i))
        lenses.face(tuple(first+i for i in reversed(range(count))))
        lenses.face(tuple(first+5*count+i for i in range(count)))
    # Join the bridge to the front rim at its actual ellipse coordinates.
    bridge_x = .0335-.027*math.sqrt(1-((1.646-1.638)/.023)**2)
    bridge_y = -.078+(bridge_x-.0335)*.65-.0008
    bridge=[Vector((-bridge_x,bridge_y,1.646)),Vector((-.004,-.097,1.651)),Vector((0,-.097,1.653)),
            Vector((.004,-.097,1.651)),Vector((bridge_x,bridge_y,1.646))]
    frames.ring_tube(bridge,.0022,uv,closed=False)
    strap=Geometry()
    centers=[]
    for i in range(65):
        angle=-.55+(math.pi+1.1)*i/64
        centers.append(radial_skin(tree,angle,1.666,.006))
    centers=[Vector((.061,-.057,1.645)),Vector((.071,-.044,1.654))]+centers+[Vector((-.071,-.044,1.654)),Vector((-.061,-.057,1.645))]
    for p in centers:
        outward=Vector((p.x,p.y-.025,0)).normalized()
        for dz,depth in [(-.0045,0),(.0045,0),(.0045,.0018),(-.0045,.0018)]:
            strap.vertex(p+Vector((0,0,dz))+outward*depth)
    for row in range(len(centers)-1):
        for side in range(4):
            strap.face((row*4+side,row*4+(side+1)%4,(row+1)*4+(side+1)%4,(row+1)*4+side),[uv]*4)
    strap.face((3,2,1,0),[uv]*4)
    strap.face(tuple((len(centers)-1)*4+i for i in range(4)),[uv]*4)
    lens_mat=bpy.data.materials.new(LENS)
    lens_mat.use_nodes=True
    p=lens_mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*LENS_SPEC['base'],1)
    p.inputs['Roughness'].default_value=LENS_SPEC['roughness']
    p.inputs['Specular IOR Level'].default_value=LENS_SPEC['specular']
    return [cups.object('Vigilante_Goggle_Cups',material,arm),
            frames.object('Vigilante_Goggle_Rims_And_Bridge',material,arm),
            strap.object('Vigilante_Goggle_Continuous_Strap',material,arm),
            lenses.object('Vigilante_Goggle_Convex_Lenses',lens_mat,arm)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=args.output.resolve()/'vigilante'
    folder.mkdir(parents=True,exist_ok=False)
    source=ROOT/'art/characters/identity-beard-vigilante-v3/vigilante/Vigilante.blend'
    assert sha(source)=='a930ea77456465987a54027f2d8e5d5d3f8f286d2f9ea2b3529ebcc6450199df'
    work=ROOT/'game/tests/runs/polish-vigilante-headgear-20260909'
    inspected=json.loads((work/'source-inspection.json').read_text())
    assert inspected['source_sha256']==sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:
            image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig']
    outfit=bpy.data.objects['Vigilante_Outfit_Assembly']
    face=bpy.data.objects['Survivor_Face_27Shapes']
    originals={str(p):sha(p) for p in source.parent.rglob('*') if p.is_file()}
    protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals])
               for o in bpy.data.objects if o.type=='MESH' and o!=outfit}
    rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    tree=face_surface(face)
    components=inspected['components']
    assert sorted(c['count'] for c in components)==[40,256,256,256,256,1690]
    cap=next(c for c in components if c['count']==1690)
    added=fitted_cap(outfit,cap,tree,arm)
    added+=goggles(tree,arm,outfit.data.materials[0],cap['uv_samples'][0])
    expression_bindings = {}
    for obj in added:
        if obj.name in ('Vigilante_Fitted_Cap','Vigilante_Cap_Hem_And_Seams'):
            selected = range(len(obj.data.vertices))
        elif obj.name == 'Vigilante_Goggle_Cups':
            selected = [v.index for v in obj.data.vertices if (v.index%256)//64 >= 2]
            expression_bindings[obj.name] = bind_pad_compression(obj,face,selected)
            continue
        else:
            continue
        expression_bindings[obj.name] = bind_soft_expressions(obj,face,selected)
    removal=remove_components(outfit,components)
    assert protected=={name:(coordinates(bpy.data.objects[name]),weights(bpy.data.objects[name]),
                             [tuple(n.vector) for n in bpy.data.objects[name].data.corner_normals]) for name in protected}
    assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    spec=json.loads((source.parent/'manifest.json').read_text())
    spec['parts']=[p for p in spec['parts'] if not (p['name']=='Cap' or p['name'].startswith('Goggle_'))]
    spec['parts'] += [{'name':o.name,'vertices':len(o.data.vertices),'bones':['mixamorig:Head']} for o in added]
    spec['materials'][LENS]=LENS_SPEC
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    spec['material_names']=sorted({m.name for o in meshes for m in o.data.materials})
    spec['total_triangles']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
    spec['outfit_triangles']=sum(len(p.vertices)-2 for p in outfit.data.polygons)
    spec['headgear_correction']={**removal,'new_parts':[o.name for o in added],
        'all_other_meshes_including_beard_preserved':True,'rig_preserved':True,
        'soft_part_expression_bindings':expression_bindings,
        'new_lens_material':LENS_SPEC,'source_visual_review_required':True}
    spec['status']='Fitted cap/goggles candidate; source and native review required'
    blend=folder/'Vigilante.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale=Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
        obj.location*=100
        inv=obj.matrix_parent_inverse.copy();inv.translation*=100;obj.matrix_parent_inverse=inv
    bpy.context.scene.unit_settings.scale_length=.01
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=folder/'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert all(sha(Path(p))==h for p,h in originals.items())
    spec['fbx_sha256']=sha(fbx)
    (folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    report={'source_sha256':sha(source),'blend_sha256':sha(blend),'fbx_sha256':sha(fbx),
            'headgear_correction':spec['headgear_correction'],'total_triangles':spec['total_triangles'],
            'source_files_unchanged':True,'native_imported':False}
    (folder.parent/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('HEADGEAR_CANDIDATE_SAVED',spec['total_triangles'],flush=True)


if __name__=='__main__':
    main()
