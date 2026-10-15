"""Derive a protected Punk equipment candidate from the reviewed costume source."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from author_vigilante_neck_candidate import coordinates,weights
from author_vigilante_headgear_candidate import remove_components
from character_punk_equipment import respirator,pauldron

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('inputs','inspection','output'):parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);output=args.output.resolve();folder=output/'punk';folder.mkdir(parents=True,exist_ok=False)
 item=json.loads(args.inputs.read_text())['cards'][0];assert item['card_id']=='punk'
 inspection=json.loads(args.inspection.read_text())['cards'][0]
 source=Path(item['source_blend']);assert sha(source)==item['source_blend_sha256']==inspection['source_sha256']
 assert sha(item['source_fbx'])==item['source_fbx_sha256'] and sha(item['native_path'])==item['native_sha256']
 bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
 for image in bpy.data.images:
  if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
 arm=bpy.data.objects['Survivor_Rig'];face=bpy.data.objects['Survivor_Face_27Shapes'];body=bpy.data.objects['Survivor_Body'];outfit=bpy.data.objects['Punk_Outfit_Assembly']
 protected={o.name:(coordinates(o),weights(o),[tuple(n.vector) for n in o.data.corner_normals]) for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm and o!=outfit}
 rig=[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
 components=inspection['components'];mask=[c for c in components if c['groups']==['mixamorig:Head']]
 shoulder=[c for c in components if c['count']==1106 and c['groups']==['mixamorig:LeftArm']]
 assert sorted(c['count'] for c in mask)==[256,256,1106] and len(shoulder)==1
 rubber=next(c for c in mask if c['count']==1106)['uv_sample'];metal=shoulder[0]['uv_sample']
 removed=remove_components(outfit,mask+shoulder,allowed_bones=('mixamorig:Head','mixamorig:LeftArm'))
 head,head_report=respirator(face,arm,outfit.data.materials[0],rubber,metal)
 armor,armor_report=pauldron(body,outfit,arm,outfit.data.materials[0],metal,rubber);added=head+armor
 assert protected=={name:(coordinates(bpy.data.objects[name]),weights(bpy.data.objects[name]),[tuple(n.vector) for n in bpy.data.objects[name].data.corner_normals]) for name in protected}
 assert rig==[(b.name,b.parent.name if b.parent else None,tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
 spec=json.loads((source.parent/'manifest.json').read_text())
 spec['parts']=[p for p in spec['parts'] if not p['name'].startswith(('Respirator_Mask','Mask_Filter','Shoulder_Plate_Left'))]
 spec['parts'] += [dict(name=o.name,vertices=len(o.data.vertices),bones=[g.name for g in o.vertex_groups]) for o in added]
 meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
 assert spec['material_names']==sorted({m.name for o in meshes for m in o.data.materials})
 spec['total_triangles']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
 details=dict(respirator=head_report,pauldron=armor_report,removed=removed,new_parts=[o.name for o in added],
              rig_preserved=True,body_face_neck_hands_crest_goggles_preserved=True,other_outfit_preserved=True)
 spec['equipment_refinement']=details;spec['status']='Equipment source candidate; source and native review required'
 blend=folder/'Punk.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 scale=Matrix.Scale(100,4)
 for obj in [arm]+meshes:
  obj.data.transform(scale,shape_keys=True) if obj.type=='MESH' else obj.data.transform(scale)
  obj.location*=100;inverse=obj.matrix_parent_inverse.copy();inverse.translation*=100;obj.matrix_parent_inverse=inverse
 bpy.context.scene.unit_settings.scale_length=.01;bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
 for obj in [arm]+meshes:obj.select_set(True)
 bpy.context.view_layer.objects.active=arm;fbx=folder/'Punk_Cm.fbx'
 bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
 assert sha(source)==item['source_blend_sha256'] and sha(item['source_fbx'])==item['source_fbx_sha256'] and sha(item['native_path'])==item['native_sha256']
 spec['fbx_sha256']=sha(fbx);(folder/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
 report=dict(**item,blend=str(blend),blend_sha256=sha(blend),fbx=str(fbx),fbx_sha256=sha(fbx),correction=details,native_imported=False)
 (folder/'authoring-report.json').write_text(json.dumps(report,indent=2)+'\n');(output/'authoring-report.json').write_text(json.dumps(dict(cards=[report]),indent=2)+'\n')
 print('PUNK_EQUIPMENT_CANDIDATE_SAVED',len(added),spec['total_triangles'],flush=True)
if __name__=='__main__':main()
