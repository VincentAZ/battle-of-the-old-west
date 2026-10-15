"""Derive a Vigilante neck-seam candidate while retaining the reviewed patch.

Blender --background --python this_file -- --output <new directory>
This saves separate source files only; it does not import or change Build S.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from character_neck import fit_neck_seam


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def coordinates(obj):
    mesh=obj.data
    return {'positions':[tuple(v.co) for v in mesh.vertices],
        'faces':[tuple(p.vertices) for p in mesh.polygons],
        'uvs':[[tuple(d.uv) for d in layer.data] for layer in mesh.uv_layers],
        'shapes':{key.name:[tuple(v.co) for v in key.data] for key in mesh.shape_keys.key_blocks} if mesh.shape_keys else {},
        'materials':[m.name for m in mesh.materials]}


def weights(obj):
    return [[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in obj.data.vertices]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output=args.output.resolve();folder=args.output/'vigilante';folder.mkdir(parents=True,exist_ok=False)
    source_root=ROOT/'art/characters/identity-patch-candidates-v6'
    source=source_root/'vigilante/Vigilante.blend'
    review=json.loads((source_root/'source-review.json').read_text())
    assert review['source_reviewed'] and sha(source)==review['cards'][0]['blend_sha256']
    originals={str(p):sha(p) for p in (source_root/'vigilante').rglob('*') if p.is_file()}
    spec=json.loads((source.parent/'manifest.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig']
    rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    face=bpy.data.objects['Survivor_Face_27Shapes'];body=bpy.data.objects['Survivor_Body']
    protected={o.name:(coordinates(o),weights(o)) for o in bpy.data.objects if o.type=='MESH' and o not in (face,body)}
    face_before=coordinates(face);body_weights=weights(body)
    changed=fit_neck_seam()
    assert coordinates(face)==face_before, 'Facial geometry, UVs or expressions changed'
    assert weights(body)==body_weights
    assert protected=={name:(coordinates(bpy.data.objects[name]),weights(bpy.data.objects[name])) for name in protected}
    assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    details={'body_vertices_fitted':changed,'body_weights_preserved':True,
        'face_vertices_weight_transferred':face['neck_body_weight_transfer_vertices'],
        'face_geometry_uvs_and_expressions_preserved':True,'other_mesh_geometry_uvs_weights_preserved':True,
        'reviewed_patch_preserved':True,'rig_preserved':True,'native_deformation_review_required':True}
    spec.update(neck_correction=details,neck_correction_source_blend=str(source),
        status='neck seam source candidate; source and native motion review required')
    blend=folder/'Vigilante.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    scale=Matrix.Scale(100,4)
    for o in [arm]+meshes:
        if o.type=='MESH':o.data.transform(scale,shape_keys=True)
        else:o.data.transform(scale)
        o.location*=100;inverse=o.matrix_parent_inverse.copy();inverse.translation*=100;o.matrix_parent_inverse=inverse
    bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for o in [arm]+meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=folder/'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert all(sha(Path(p))==digest for p,digest in originals.items())
    spec['fbx_sha256']=sha(fbx);(folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    report={'neck_correction':details,'source_sha256':sha(source),'blend_sha256':sha(blend),'fbx_sha256':sha(fbx),
        'original_source_files_unchanged':True,'native_imported':False}
    (args.output/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
