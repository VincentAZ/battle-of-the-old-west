"""Read-only comparison of each approved Crew mesh and USkeleton bind transforms."""
import json,math,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from crew_unreal_contract import BASE,CONTENT,NATIVE,load_manifest,character,snapshot,sha

def data(t):
 return {'translation_cm':[t.translation.x,t.translation.y,t.translation.z], 'quaternion_xyzw':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w], 'scale':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}

report={'status':'running','characters':[],'content_modified':False}
before=snapshot(())
try:
 assert not unreal.OldWestAssetAuthoring.refresh_crew_skeleton_reference(None)
 native=unreal.load_asset('/Game/Art/Western/Quanah/SK_Quanah');assert native
 assert not unreal.OldWestAssetAuthoring.refresh_crew_skeleton_reference(native)
 report['refresh_helper_rejects_null_and_native']=True
 manifest=load_manifest()
 for slug in sorted(set(manifest['characters'])-NATIVE):
  c=character(slug,manifest);mesh=unreal.load_asset(c['dest']+'/SK_'+c['name']);skeleton=mesh.get_editor_property('skeleton')
  comp=unreal.SkeletalMeshComponent();comp.set_skeletal_mesh_asset(mesh)
  ref=unreal.AnimPoseExtensions.get_reference_pose(skeleton)
  names=json.loads((c['out']/'unreal-bones.json').read_text())['target'];bones={};mismatches=[]
  for name in names:
   index=comp.get_bone_index(name);assert index>=0
   mesh_t=data(comp.get_ref_pose_transform(index));skeleton_t=data(unreal.AnimPoseExtensions.get_bone_pose(ref,name,unreal.AnimPoseSpaces.LOCAL))
   distance=math.dist(mesh_t['translation_cm'],skeleton_t['translation_cm']);scale=math.dist(mesh_t['scale'],skeleton_t['scale']);a=mesh_t['quaternion_xyzw'];b=skeleton_t['quaternion_xyzw'];rotation=min(math.dist(a,b),math.dist(a,[-v for v in b]))
   bones[name]={'mesh_reference':mesh_t,'skeleton_reference':skeleton_t,'translation_error_cm':distance,'quaternion_error':rotation,'scale_error':scale}
   if distance>.001 or rotation>.0001 or scale>.00001:mismatches.append(name)
  item={'slug':slug,'rig_project_sha256':c['validation']['project_sha256'],'unreal_assets_sha256':sha(c['out']/'unreal-assets.json'),'mismatched_bones':mismatches,'bones':bones}
  report['characters'].append(item);print('CREW_REFERENCE_AUDIT',slug,mismatches,flush=True)
 report['status']='passed' if all(not x['mismatched_bones'] for x in report['characters']) else 'mismatches_detected'
except Exception:
 report['status']='error';report['error']=traceback.format_exc();raise
finally:
 report['content_modified']=before!=snapshot(())
 (BASE/'integration/skeleton-reference-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 assert not report['content_modified']
