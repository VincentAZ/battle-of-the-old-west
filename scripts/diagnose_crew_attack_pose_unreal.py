"""Read saved reference/half-attack transforms for every bone; never modify Content."""
import json, math, sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from crew_unreal_contract import BASE, CONTENT, sha, snapshot

def vector(v): return [v.x,v.y,v.z]
def rotation(q): return [q.x,q.y,q.z,q.w]
def transform(t): return {'translation_cm':vector(t.translation),'quaternion_xyzw':rotation(t.rotation),'scale':vector(t.scale3d)}
def inspect(slug,mesh_path,animation_path):
 mesh=unreal.load_asset(mesh_path);animation=unreal.load_asset(animation_path)
 assert mesh and animation
 skeleton=mesh.get_editor_property('skeleton')
 component=unreal.SkeletalMeshComponent();component.set_skeletal_mesh_asset(mesh)
 reference=unreal.AnimPoseExtensions.get_reference_pose(skeleton)
 seconds=animation.get_play_length()*.5
 posed=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,seconds,unreal.AnimPoseEvaluationOptions())
 assert unreal.AnimPoseExtensions.is_valid(reference) and unreal.AnimPoseExtensions.is_valid(posed)
 bones={}
 for index in range(component.get_num_bones()):
  name=str(component.get_bone_name(index));entry={'parent':str(component.get_parent_bone(name))}
  for label,pose in [('reference',reference),('attack02',posed)]:
   entry[label]={space.lower():transform(unreal.AnimPoseExtensions.get_bone_pose(pose,name,getattr(unreal.AnimPoseSpaces,space))) for space in ['LOCAL','WORLD']}
  a,b=entry['reference']['local'],entry['attack02']['local']
  dot=abs(sum(x*y for x,y in zip(a['quaternion_xyzw'],b['quaternion_xyzw'])))
  entry['local_delta']={'translation_cm':math.dist(a['translation_cm'],b['translation_cm']),'rotation_degrees':math.degrees(2*math.acos(min(1.,dot))),'scale':math.dist(a['scale'],b['scale'])}
  bones[name]=entry
 files={}
 for path in [mesh_path,animation_path]:
  file=CONTENT/(path.removeprefix('/Game/')+'.uasset');files[str(file.relative_to(CONTENT))]=sha(file)
 result={'slug':slug,'mesh':mesh_path,'animation':animation_path,'seconds':seconds,'fraction':.5,'world_space_meaning':'Skeleton component space; no actor transform applied','bones':bones,'files':files}
 if slug!='manny':result['imported_rig_project_sha256']=json.loads((BASE/slug/'unreal-assets.json').read_text())['rig_project_sha256']
 return result
before=snapshot()
report={'scope':'Read-only all-bone reference versus exact Attack02 transform diagnostic','characters':[]}
try:
 for slug,name in [('barn-burner','BarnBurner'),('bartender','Bartender'),('claim-jumper','ClaimJumper'),('jesse-james','JesseJames')]:
  base='/Game/Art/Western/Crew/'+name
  report['characters'].append(inspect(slug,base+'/SK_'+name,base+'/Animations/RA_MM_Attack_01'))
 report['characters'].append(inspect('manny','/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple','/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01'))
finally:
 report['existing_content_unchanged']=snapshot()==before
 target=BASE/'integration/attack-pose-diagnostic.json';temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(target)
 print('CREW_ATTACK_DIAGNOSTIC',str(target),report['existing_content_unchanged'],flush=True)
assert report['existing_content_unchanged']
