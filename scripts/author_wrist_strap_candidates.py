"""Derive protected Scout/Punk wrist-strap sources; export only on request."""
import argparse,json,sys,hashlib
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates,weights
from author_vigilante_headgear_candidate import remove_components
from character_wrist_straps import fitted_wrist_straps
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','inspection','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--export',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output.mkdir(parents=True,exist_ok=False)
    inspected={c['card_id']:c for c in json.loads(args.inspection.read_text())['cards']};reports=[]
    for item in json.loads(args.inputs.read_text())['cards']:
        info=inspected[item['card_id']];source=Path(item['source_blend'])
        assert sha(source)==item['source_blend_sha256']==info['source_sha256']
        assert sha(item['source_fbx'])==item['source_fbx_sha256'] and sha(item['native_path'])==item['native_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
        for image in bpy.data.images:
            if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
        arm=bpy.data.objects['Survivor_Rig'];body=bpy.data.objects['Survivor_Body'];outfit=bpy.data.objects[item['name']+'_Outfit_Assembly']
        protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals]) for o in bpy.data.objects if o.type=='MESH' and o!=outfit}
        rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
        removed=remove_components(outfit,info['components'],allowed_bones=('mixamorig:LeftForeArm','mixamorig:RightForeArm'))
        stud_uvs={next(iter(c['weights'])).split(':')[-1].replace('ForeArm',''):c['uv_sample'] for c in info['components']}
        added,details=fitted_wrist_straps(body,arm,outfit.data.materials[0],outfit.data.materials[0],info['strap_uv'],stud_uvs,item['name'])
        assert protected=={name:(coordinates(bpy.data.objects[name]),weights(bpy.data.objects[name]),[tuple(n.vector) for n in bpy.data.objects[name].data.corner_normals]) for name in protected}
        assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
        spec=json.loads((source.parent/'manifest.json').read_text());spec['parts']=[p for p in spec['parts'] if not p['name'].startswith('Cuff_Rivet_')]
        spec['parts'] += [dict(name=o.name,vertices=len(o.data.vertices),bones=[g.name for g in o.vertex_groups]) for o in added]
        meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
        assert spec['material_names']==sorted({m.name for o in meshes for m in o.data.materials})
        spec['total_triangles']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
        details.update(removed=removed,rig_and_all_other_meshes_preserved=True,other_outfit_preserved=True)
        spec['wrist_straps']=details;spec['status']='Wrist source candidate; source and native review required'
        folder=args.output/item['card_id'];folder.mkdir();blend=folder/(item['name']+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        report=dict(**item,blend=str(blend.resolve()),blend_sha256=sha(blend),correction=details,accepted=False,native_imported=False)
        if args.export:
            scale=Matrix.Scale(100,4)
            for obj in [arm]+meshes:
                obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
                obj.location*=100;inverse=obj.matrix_parent_inverse.copy();inverse.translation*=100;obj.matrix_parent_inverse=inverse
            bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
            for obj in [arm]+meshes:obj.select_set(True)
            bpy.context.view_layer.objects.active=arm;fbx=folder/(item['name']+'_Cm.fbx')
            bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
            report.update(fbx=str(fbx.resolve()),fbx_sha256=sha(fbx));spec['fbx_sha256']=sha(fbx)
        (folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n');(folder/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
        assert sha(source)==item['source_blend_sha256'] and sha(item['native_path'])==item['native_sha256']
        print('WRIST_STRAPS_AUTHORED',item['card_id'],spec['total_triangles'],flush=True)
    (args.output/'authoring-report.json').write_text(json.dumps(dict(cards=reports),indent=2)+'\n')
if __name__=='__main__':main()
