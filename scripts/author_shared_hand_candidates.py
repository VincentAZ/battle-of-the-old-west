"""Derive hand-weight candidates from a pinned current-source inventory.

Blender --background --python this_file -- --inputs inventory.json --output new-root
Preserves all geometry, expressions, materials and rig; never imports native assets.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from character_hands import correct_isolated_ring_vertex
from author_vigilante_neck_candidate import coordinates, weights

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rig_signature(arm):
    return [(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]

def author(item,output):
    source=Path(item['source_blend']);assert sha(source)==item['source_blend_sha256']
    assert sha(Path(item['source_fbx']))==item['source_fbx_sha256']
    assert sha(Path(item['native_path']))==item['native_sha256']
    folder=output/item['card_id'];folder.mkdir(parents=True,exist_ok=False)
    originals={str(p):sha(p) for p in source.parent.rglob('*') if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig'];body=bpy.data.objects['Survivor_Body']
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    rig=rig_signature(arm)
    protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals]) for o in meshes}
    repairs=correct_isolated_ring_vertex(body);assert len(repairs)==1, item['card_id']
    assert correct_isolated_ring_vertex(body)==[], 'Repair must be idempotent'
    changed_id=repairs[0]['vertex']
    for obj in meshes:
        before,old_weights,normals=protected[obj.name]
        assert coordinates(obj)==before,(obj.name,'geometry, expression, UV or material changed')
        assert normals==[tuple(n.vector) for n in obj.data.corner_normals],obj.name
        changed=[i for i,(a,b) in enumerate(zip(old_weights,weights(obj))) if a!=b]
        assert changed==([changed_id] if obj==body else []),(obj.name,changed)
    assert rig_signature(arm)==rig
    spec=json.loads((source.parent/'manifest.json').read_text())
    spec.update(hand_weight_corrections=repairs,status='Single finger-weight correction; source and native review required')
    blend=folder/f"{item['name']}.blend";bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale=Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
        obj.location*=100;inverse=obj.matrix_parent_inverse.copy();inverse.translation*=100;obj.matrix_parent_inverse=inverse
    bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=folder/f"{item['name']}_Cm.fbx"
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert all(sha(Path(p))==digest for p,digest in originals.items())
    spec['fbx_sha256']=sha(fbx);(folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    report={**item,'blend':str(blend),'blend_sha256':sha(blend),'fbx':str(fbx),'fbx_sha256':sha(fbx),
        'repairs':repairs,'geometry_uvs_normals_expressions_preserved':True,'other_weights_and_meshes_preserved':True,
        'rig_preserved':True,'source_files_unchanged':True,'native_imported':False}
    (folder/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('HAND_CANDIDATE',item['card_id'],changed_id,report['blend_sha256'],flush=True)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    inputs=json.loads(args.inputs.read_text());cards=[author(item,args.output) for item in inputs['cards']]
    (args.output/'authoring-report.json').write_text(json.dumps({'inputs_sha256':sha(args.inputs),'cards':cards},indent=2)+'\n')

if __name__=='__main__':main()
