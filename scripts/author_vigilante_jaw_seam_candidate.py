"""Attach the overlapping body neck to face expressions in a separate candidate.

Blender --background --python this_file -- --output <new source root>.
Retains all neutral geometry, rig, weights and other meshes; no native import.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates,weights


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def attach_neck_expressions(body,face):
    assert not body.data.shape_keys
    face.data.calc_loop_triangles()
    points=[face.matrix_world@v.co for v in face.data.vertices]
    triangles=[tuple(t.vertices) for t in face.data.loop_triangles]
    tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
    bottom=min(p.z for p in points)
    ring=[p for p in points if bottom<=p.z<=bottom+.025]
    center_y=(min(p.y for p in ring)+max(p.y for p in ring))/2
    inverse=body.matrix_world.inverted();bindings=[]
    for vertex in body.data.vertices:
        point=body.matrix_world@vertex.co
        if point.z<bottom-.016 or point.z>bottom+.060:continue
        if not .005<Vector((point.x,point.y-center_y,0)).length<.09:continue
        hit,normal,triangle,distance=tree.find_nearest(point)
        assert distance<.04
        ids=triangles[triangle];a,b,c=[points[i] for i in ids]
        u,v,q=b-a,c-a,hit-a
        denominator=u.dot(u)*v.dot(v)-u.dot(v)**2
        assert denominator>1e-16
        s=(q.dot(u)*v.dot(v)-q.dot(v)*u.dot(v))/denominator
        t=(q.dot(v)*u.dot(u)-q.dot(u)*u.dot(v))/denominator
        alpha=max(0.,min(1.,(point.z-(bottom-.016))/.016));alpha=alpha*alpha*(3-2*alpha)
        bindings.append((vertex.index,ids,(1-s-t,s,t),normal,point-hit,alpha))
    body.shape_key_add(name='Basis');maximum=0.;changed_by_expression={}
    for key in list(face.data.shape_keys.key_blocks)[1:]:
        target=body.shape_key_add(name=key.name)
        moved=[face.matrix_world@p.co for p in key.data];changed=0
        for index,ids,bary,normal,offset,alpha in bindings:
            a,b,c=[moved[i] for i in ids];new_normal=(b-a).cross(c-a).normalized()
            projected=sum((moved[i]*w for i,w in zip(ids,bary)),Vector())
            projected+=normal.rotation_difference(new_normal)@offset
            original=body.data.vertices[index].co
            delta=(inverse@projected-original)*alpha
            # The two differently textured skins must remain separated after
            # interpolation and their slightly different native bone weights.
            # Keep the neutral shape exact; grow 0.5 mm of inward allowance
            # with the expression's movement, fading below the face boundary.
            allowance=.0005*min(1.,delta.length/.001)*alpha
            delta-=inverse.to_3x3()@new_normal*allowance
            target.data[index].co=original+delta
            maximum=max(maximum,delta.length)
            changed+=delta.length>1e-7
        changed_by_expression[key.name]=changed
    assert bindings and changed_by_expression['Jaw_Lower']>0
    return {'bound_body_vertices':len(bindings),'face_bottom_m':bottom,
            'maximum_expression_displacement_mm':maximum*1000,
            'maximum_expression_clearance_allowance_mm':.5,
            'changed_vertices_by_expression':changed_by_expression,
            'method':'Barycentric face displacement with transported offset; fade below face boundary',
            'bindings':[{'body_vertex':i,'face_triangle':list(ids),'barycentric':list(bary),'offset_m':list(offset),'fade':alpha} for i,ids,bary,_,offset,alpha in bindings]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=args.output.resolve()/'vigilante';folder.mkdir(parents=True,exist_ok=False)
    source=ROOT/'art/characters/identity-headgear-vigilante-v3/vigilante/Vigilante.blend'
    assert sha(source)=='61390cc635ac13fe957ae67d9f5a8e51707f3487514043520358f542113a247d'
    originals={str(p):sha(p) for p in source.parent.rglob('*') if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig'];body=bpy.data.objects['Survivor_Body'];face=bpy.data.objects['Survivor_Face_27Shapes']
    rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals]) for o in meshes}
    binding=attach_neck_expressions(body,face)
    for obj in meshes:
        before,old_weights,normals=protected[obj.name];after=coordinates(obj)
        if obj==body:
            assert all(tuple(a.co)==p for a,p in zip(obj.data.shape_keys.key_blocks['Basis'].data,before['positions']))
            after['shapes']={}
        assert before==after,(obj.name,'protected geometry, UV or material changed')
        assert old_weights==weights(obj) and normals==[tuple(n.vector) for n in obj.data.corner_normals],obj.name
    assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    spec=json.loads((source.parent/'manifest.json').read_text())
    spec['jaw_neck_correction']={k:v for k,v in binding.items() if k!='bindings'}
    spec['jaw_neck_correction'].update(neutral_geometry_uvs_normals_and_weights_preserved=True,
        other_meshes_including_face_beard_headgear_preserved=True,rig_preserved=True)
    spec['status']='Body neck expression candidate; source and native review required'
    blend=folder/'Vigilante.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale=Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
        obj.location*=100;inv=obj.matrix_parent_inverse.copy();inv.translation*=100;obj.matrix_parent_inverse=inv
    bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=folder/'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert all(sha(Path(p))==digest for p,digest in originals.items())
    spec['fbx_sha256']=sha(fbx);(folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    report={'source_sha256':sha(source),'blend_sha256':sha(blend),'fbx_sha256':sha(fbx),
        'correction':spec['jaw_neck_correction'],'body_bindings':binding['bindings'],
        'source_files_unchanged':True,'native_imported':False}
    (folder.parent/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('JAW_NECK_CANDIDATE',binding['bound_body_vertices'],binding['maximum_expression_displacement_mm'],flush=True)


if __name__=='__main__':main()
