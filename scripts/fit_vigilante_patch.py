"""Derive a garment-fitted Vigilante patch from the existing reviewed identity.

Run in Blender background mode. Refine and fit only the isolated patch island;
preserve the rest of the outfit, its corner normals, UVs, rig and textures.
"""
import hashlib
import json
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weights(vertex):
    return [(g.group,g.weight) for g in vertex.groups]


def update_geometry_manifest(spec,obj,arm,patch):
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    spec['total_triangles']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
    spec['outfit_triangles']=sum(len(p.vertices)-2 for p in obj.data.polygons)
    part=next(p for p in spec['parts'] if p['name']=='Rose_Chest_Patch')
    part['vertices']=len(patch)
    part['bones']=sorted({obj.vertex_groups[g.group].name for i in patch for g in obj.data.vertices[i].groups if g.weight>0})


def subdivide_patch(mesh, patch):
    """Add local support so patch faces follow the curved garment between vertices."""
    normals=[tuple(n.vector) for n in mesh.corner_normals]
    original_vertices={v.index:(tuple(v.co),weights(v)) for v in mesh.vertices if v.index not in patch}
    original_faces={p.index:{'uvs':[[tuple(layer.data[i].uv) for i in p.loop_indices] for layer in mesh.uv_layers],
        'normals':[normals[i] for i in p.loop_indices], 'vertices':list(p.vertices),
        'material':p.material_index,'smooth':p.use_smooth} for p in mesh.polygons if not any(i in patch for i in p.vertices)}
    bm=bmesh.new();bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
    # Store membership in mesh data: topology operators can recreate Python
    # BMesh wrappers, so object identity is not a stable island identifier.
    vertex_ids=bm.verts.layers.int.new('patch_original_vertex')
    face_ids=bm.faces.layers.int.new('patch_original_face')
    for v in bm.verts:v[vertex_ids]=v.index+1 if v.index in original_vertices else 0
    for f in bm.faces:f[face_ids]=f.index+1 if f.index in original_faces else 0
    patch_faces=lambda:[f for f in bm.faces if all(v[vertex_ids]==0 for v in f.verts)]
    bmesh.ops.triangulate(bm,faces=patch_faces())
    for iteration in range(16):
        long_edges=[e for e in bm.edges if all(v[vertex_ids]==0 for v in e.verts) and e.calc_length()>.008]
        print('PATCH_SUBDIVISION',iteration,len(long_edges),max((e.calc_length() for e in long_edges),default=0.),flush=True)
        if not long_edges:break
        bmesh.ops.subdivide_edges(bm,edges=long_edges,cuts=1,use_grid_fill=True)
        bmesh.ops.triangulate(bm,faces=patch_faces())
    else:raise AssertionError('Patch subdivision did not converge')
    bm.verts.index_update();bm.faces.index_update()
    vertices={v.index:original_vertices[v[vertex_ids]-1] for v in bm.verts if v[vertex_ids]}
    faces={f.index:original_faces[f[face_ids]-1] for f in bm.faces if f[face_ids]}
    assert len(vertices)==len(original_vertices) and len(faces)==len(original_faces)
    # Require untouched topology, including vertex order at each corner.
    for f in bm.faces:
        if f[face_ids]:assert [v[vertex_ids]-1 for v in f.verts]==original_faces[f[face_ids]-1]['vertices']
    patch={v.index for v in bm.verts if v[vertex_ids]==0}
    bm.verts.layers.int.remove(vertex_ids);bm.faces.layers.int.remove(face_ids)
    bm.to_mesh(mesh);bm.free();mesh.update()
    assert vertices=={i:(tuple(mesh.vertices[i].co),weights(mesh.vertices[i])) for i in vertices}
    return patch,vertices,faces


def restore_outfit_normals(mesh, faces):
    # The patch changed shape. Recompute its normals while keeping every
    # untouched face's existing shading and UVs (including atlas seams).
    normals=[(0.,0.,0.) for _ in mesh.loops]
    for index,before in faces.items():
        face=mesh.polygons[index]
        assert face.material_index==before['material'] and face.use_smooth==before['smooth']
        # BMesh preserves each untouched face's loop ordering.
        for layer,uvs in zip(mesh.uv_layers,before['uvs']):
            assert [tuple(layer.data[i].uv) for i in face.loop_indices]==uvs
        for loop,normal in zip(face.loop_indices,before['normals']):normals[loop]=normal
    mesh.normals_split_custom_set(normals);mesh.update()
    actual=[tuple(n.vector) for n in mesh.corner_normals]
    largest=0.
    for index,before in faces.items():
        for loop,normal in zip(mesh.polygons[index].loop_indices,before['normals']):
            largest=max(largest,(Vector(actual[loop])-Vector(normal)).length)
    # Blender requantizes custom normals to two int16 components. Bound the
    # round trip to <0.06 degrees, and retain the measured error in the report.
    assert largest<.001,largest
    return largest


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output=args.output.resolve()
    folder=ROOT/'art/characters/identities/vigilante'
    source=folder/'Vigilante.blend'
    inspected=json.loads((ROOT/'game/tests/runs/polish-vigilante-patch-audit-20260909/source-inspection.json').read_text())
    assert sha(source)==inspected['source_sha256']
    spec=json.loads((folder/'manifest.json').read_text())
    original_files={str(p):sha(p) for p in folder.rglob('*') if p.is_file()}
    out=args.output.resolve()/'vigilante'
    out.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig']
    reference=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    obj=bpy.data.objects['Vigilante_Outfit_Assembly'];mesh=obj.data
    patch=set(inspected['patch_vertex_indices'])
    original_patch_vertices=len(patch)
    patch,before,untouched_faces=subdivide_patch(mesh,patch)
    mesh.calc_loop_triangles()
    vertices=[obj.matrix_world@v.co for v in mesh.vertices]
    triangles=[tuple(t.vertices) for t in mesh.loop_triangles if not any(v in patch for v in t.vertices)]
    surface=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
    inverse=obj.matrix_world.inverted()
    displacements=[]
    for index in sorted(patch):
        old=vertices[index]
        location,normal,face,distance=surface.ray_cast(Vector((old.x,-.6,old.z)),Vector((0,1,0)),1.2)
        assert location is not None and normal.y<-.2,(index,location,normal)
        a,b,c=[vertices[i] for i in triangles[face]]
        ab,ac,ap=b-a,c-a,location-a
        aa,bb,cc=ab.dot(ab),ab.dot(ac),ac.dot(ac)
        denominator=aa*cc-bb*bb
        v=(cc*ap.dot(ab)-bb*ap.dot(ac))/denominator
        w=(aa*ap.dot(ac)-bb*ap.dot(ab))/denominator
        barycentric=[1-v-w,v,w]
        assert min(barycentric)>-1e-5
        skin={}
        for vertex_index,factor in zip(triangles[face],barycentric):
            for group,weight in weights(mesh.vertices[vertex_index]):
                skin[group]=skin.get(group,0.)+max(0.,factor)*weight
        total=sum(skin.values());assert total>.99
        # Collapse the old 15 mm rigid block to a 0.8 mm fabric layer. Its
        # 1.4 mm back clearance covers skinning curvature in torso bends;
        # keep the front at 2.2 mm and preserve its baked UVs.
        depth=max(-1.,min(1.,(-.173-old.y)/.0075))
        fitted=location+normal*(.0018+.0004*depth)
        mesh.vertices[index].co=inverse@fitted
        for group in list(mesh.vertices[index].groups):obj.vertex_groups[group.group].remove([index])
        for group,weight in skin.items():
            if weight>1e-8:obj.vertex_groups[group].add([index],weight/total,'REPLACE')
        displacements.append((fitted-old).length*100)
    mesh.update()
    assert before=={v.index:(tuple(v.co),weights(v)) for v in mesh.vertices if v.index not in patch}
    normal_error=restore_outfit_normals(mesh,untouched_faces)
    assert reference==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    mesh.calc_loop_triangles()
    gaps=[]
    for tri in mesh.loop_triangles:
        if not all(i in patch for i in tri.vertices):continue
        corners=[obj.matrix_world@mesh.vertices[i].co for i in tri.vertices]
        for i in range(9):
            for j in range(9-i):
                point=corners[0]*(i/8)+corners[1]*(j/8)+corners[2]*(1-(i+j)/8)
                hit,normal,face,distance=surface.ray_cast(Vector((point.x,-.6,point.z)),Vector((0,1,0)),1.2)
                assert hit is not None
                gaps.append((point-hit).dot(normal)*100)
    details={'original_patch_vertices':original_patch_vertices,'fitted_patch_vertices':len(patch),
        'other_outfit_positions_and_weights_unchanged':True,'other_outfit_uvs_unchanged':True,
        'patch_uvs_interpolated_by_subdivision':True,'other_outfit_maximum_corner_normal_vector_error':normal_error,
        'rig_unchanged':True,'maximum_displacement_cm':max(displacements),
        'sampled_surface_gap_cm':{'minimum':min(gaps),'maximum':max(gaps),'samples':len(gaps)},
        'source_sha256':sha(source),'status':'source candidate; rendered fit and native motion review required'}
    spec.update(patch_fit=details,patch_fit_source_blend=str(source),status=details['status'])
    update_geometry_manifest(spec,obj,arm,patch)
    blend=out/'Vigilante.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    scale=Matrix.Scale(100,4)
    for o in [arm]+meshes:
        if o.type=='MESH':o.data.transform(scale,shape_keys=True)
        else:o.data.transform(scale)
        o.location*=100;parent_inverse=o.matrix_parent_inverse.copy();parent_inverse.translation*=100;o.matrix_parent_inverse=parent_inverse
    bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for o in [arm]+meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=out/'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert all(sha(Path(p))==digest for p,digest in original_files.items())
    spec['fbx_sha256']=sha(fbx)
    (out/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    (args.output/'authoring-report.json').write_text(json.dumps({'patch_fit':details,'blend_sha256':sha(blend),
        'fbx_sha256':sha(fbx),'original_source_files_unchanged':True},indent=2)+'\n')
    print(json.dumps(details,indent=2))


if __name__=='__main__':main()
