"""Derive fitted costume candidates from the reviewed Scout/Punk crest sources."""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates, weights
from author_vigilante_headgear_candidate import remove_components
from author_vigilante_jaw_seam_candidate import attach_neck_expressions
from character_neck import fit_neck_seam
from character_fitted_accessories import fitted_goggles, scarf, fit_collar_weights

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def author(item, inspection, output):
    source=Path(item['source_blend']);assert sha(source)==item['source_blend_sha256']==inspection['source_sha256']
    assert sha(item['source_fbx'])==item['source_fbx_sha256'] and sha(item['native_path'])==item['native_sha256']
    folder=output/item['card_id'];folder.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    arm=bpy.data.objects['Survivor_Rig'];face=bpy.data.objects['Survivor_Face_27Shapes'];body=bpy.data.objects['Survivor_Body']
    outfit=bpy.data.objects[item['name']+'_Outfit_Assembly']
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals]) for o in meshes}
    rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    fitted=fit_neck_seam();neck=attach_neck_expressions(body,face)
    components=inspection['components']
    collar=fit_collar_weights(outfit,body,components)
    goggles=[c for c in components if c['groups']==['mixamorig:Head'] and c['bounds_m'][2][0]>1.61]
    assert sorted(c['count'] for c in goggles)==[40,256,256,256,256]
    rim=next(c for c in goggles if c['count']==256 and c['bounds_m'][1][0]>-.12)
    lens=next(c for c in goggles if c['count']==256 and c['bounds_m'][1][0]<-.12)
    added, goggle_bindings=fitted_goggles(face,arm,outfit.data.materials[0],rim['uv_sample'],lens['uv_sample'],item['name'])
    remove=list(goggles);scarf_binding=None;old=None
    if item['card_id']=='rustler':
        old=next(c for c in components if c['count']==24 and c['groups']==['mixamorig:Spine2'])
        remove.append(old)
    removed=remove_components(outfit,remove,allowed_bones=('mixamorig:Head','mixamorig:Spine2'))
    if old is not None:
        wrap,scarf_binding=scarf(face,body,arm,outfit.data.materials[0],old['uv_sample'],'Scout_Fitted_Scarf',garment=outfit)
        added.append(wrap)
    for obj in meshes:
        before,old_weights,normals=protected[obj.name];after=coordinates(obj)
        if obj==outfit:continue
        if obj==body:
            changed=[i for i,(a,b) in enumerate(zip(before['positions'],after['positions'])) if a!=b]
            assert changed and all(1.45<before['positions'][i][2]<1.535 for i in changed)
            after['positions']=before['positions'];after['shapes']={}
            assert old_weights==weights(obj)
        elif obj==face:
            assert old_weights!=weights(obj)
        else:
            assert old_weights==weights(obj) and normals==[tuple(n.vector) for n in obj.data.corner_normals]
        assert before==after,(obj.name,'protected data changed')
    assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    spec=json.loads((source.parent/'manifest.json').read_text())
    spec['parts']=[p for p in spec['parts'] if not p['name'].startswith(('Goggle_','Scout_Scarf'))]
    spec['parts'] += [dict(name=o.name,vertices=len(o.data.vertices),bones=[g.name for g in o.vertex_groups]) for o in added]
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    assert spec['material_names']==sorted({m.name for o in meshes for m in o.data.materials})
    spec['total_triangles']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
    details=dict(neck_vertices_fitted=fitted,face_neck_weights_transferred=face['neck_body_weight_transfer_vertices'],
                 neck_expressions={k:v for k,v in neck.items() if k!='bindings'},goggles=goggle_bindings,collar=collar,
                 scarf={k:v for k,v in scarf_binding.items() if k!='bindings'} if scarf_binding else None,
                 removal=removed,hand_weights_preserved=True,crest_mesh_expressions_weights_preserved=True,rig_preserved=True)
    spec['fitted_costume']=details;spec['status']='Fitted costume source candidate; source and native review required'
    blend=folder/(item['name']+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale=Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
        obj.location*=100;inverse=obj.matrix_parent_inverse.copy();inverse.translation*=100;obj.matrix_parent_inverse=inverse
    bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm]+meshes:obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=folder/(item['name']+'_Cm.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,
        use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    assert sha(source)==item['source_blend_sha256'] and sha(item['source_fbx'])==item['source_fbx_sha256'] and sha(item['native_path'])==item['native_sha256']
    spec['fbx_sha256']=sha(fbx);(folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
    report=dict(**item,blend=str(blend),blend_sha256=sha(blend),fbx=str(fbx),fbx_sha256=sha(fbx),correction=details,
                neck_bindings=neck['bindings'],scarf_bindings=scarf_binding['bindings'] if scarf_binding else [],native_imported=False)
    (folder/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COSTUME_CANDIDATE',item['card_id'],fitted,neck['bound_body_vertices'],flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('inputs','inspection','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    records=json.loads(args.inspection.read_text())['cards']
    cards=[author(c,next(r for r in records if r['card_id']==c['card_id']),args.output) for c in json.loads(args.inputs.read_text())['cards']]
    (args.output/'authoring-report.json').write_text(json.dumps(dict(cards=cards),indent=2)+'\n')
