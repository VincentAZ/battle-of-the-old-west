"""Apply an archived, repeatable rotation-only Crew attack gesture adjustment.

OLDWEST_CREW_SLUGS=barn-burner,bartender selects approved imported rigs.
OLDWEST_CREW_ATTACK_ALPHA=.4 retains this fraction of the original animated
rotation from bind. OLDWEST_CREW_ATTACK_BONES defaults to Spine,Spine1,Spine2.
Only each selected RA_MM_Attack_01 package may change; all original keys and
packages are archived outside Content before the first adjustment.
"""
import fcntl,json,math,os,shutil,sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from crew_unreal_contract import BASE,CONTENT,character,load_manifest,sha,snapshot
from crew_animation_constraints import frozen_bones
UPPER_BONES=('Spine','Spine1','Spine2','Neck','Head')+tuple(side+part for side in ('Left','Right') for part in ('Shoulder','Arm','ForeArm','Hand'))

def xyz(v):return [v.x,v.y,v.z]
def xyzw(q):return [q.x,q.y,q.z,q.w]
def value(t):return {'translation':xyz(t.translation),'rotation':xyzw(t.rotation),'scale':xyz(t.scale3d)}
def slerp(a,b,alpha):
 dot=sum(x*y for x,y in zip(a,b))
 if dot<0:b=[-v for v in b];dot=-dot
 dot=max(-1.,min(1.,dot))
 if dot>.9995:q=[x+alpha*(y-x) for x,y in zip(a,b)]
 else:
  theta=math.acos(dot);den=math.sin(theta)
  q=[(math.sin((1-alpha)*theta)*x+math.sin(alpha*theta)*y)/den for x,y in zip(a,b)]
 length=math.sqrt(sum(x*x for x in q));assert length>0
 return [x/length for x in q]
def package_hashes(dest):
 path=CONTENT/dest.removeprefix('/Game/')
 return {str(p.relative_to(CONTENT)):sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
def keys(animation,skeleton,names):
 model=animation.get_editor_property('data_model_interface');count=model.get_number_of_keys();length=animation.get_play_length();assert count>1
 reference=unreal.AnimPoseExtensions.get_reference_pose(skeleton)
 result={'count':count,'length':length,'reference':{},'bones':{n:[] for n in names}}
 for n in names:result['reference'][n]=value(unreal.AnimPoseExtensions.get_bone_pose(reference,n,unreal.AnimPoseSpaces.LOCAL))
 for frame in range(count):
  pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,length*frame/(count-1),unreal.AnimPoseEvaluationOptions())
  for n in names:result['bones'][n].append(value(unreal.AnimPoseExtensions.get_bone_pose(pose,n,unreal.AnimPoseSpaces.LOCAL)))
 return result

def main():
 slugs=os.environ['OLDWEST_CREW_SLUGS'].split(',');alpha=float(os.environ.get('OLDWEST_CREW_ATTACK_ALPHA','.4'))
 requested_bones=os.environ.get('OLDWEST_CREW_ATTACK_BONES','Spine,Spine1,Spine2').split(',')
 assert slugs and len(set(slugs))==len(slugs) and 0<alpha<=1 and set(requested_bones)<=set(UPPER_BONES)
 manifest=load_manifest();configs=[character(s,manifest) for s in slugs]
 paths=[CONTENT/c['dest'].removeprefix('/Game/')/'Animations/RA_MM_Attack_01.uasset' for c in configs]
 with (BASE/'.unreal-authoring.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  before=snapshot(paths)
  try:
   for config,file in zip(configs,paths):
    out=config['out'];asset_path=out/'unreal-assets.json';assets=json.loads(asset_path.read_text())
    available=json.loads((out/'unreal-bones.json').read_text())['target']
    frozen=set(frozen_bones(config['validation'],available))
    bones=[bone for bone in requested_bones if bone not in frozen]
    if not bones:
     print('CREW_ATTACK_GESTURE_SKIP_FROZEN',config['slug'],flush=True);continue
    assert assets['rig_project_sha256']==config['validation']['project_sha256']
    assert assets['rig_validation_sha256']==sha(out/'rig-validation.json')
    assert assets['files']==package_hashes(config['dest']), 'Current saved packages differ from manifest'
    relative=str(file.relative_to(CONTENT));assert relative in assets['files']
    baseline=out/'attack-gesture-baseline-v001';baseline.mkdir(exist_ok=True)
    original_assets=baseline/'unreal-assets.json'
    if not original_assets.exists():
     shutil.copy2(asset_path,original_assets)
     for name in ['unreal-pose-captures.json','animation-visual-review.json','unreal-pose-contact.jpg']:
      if (out/name).is_file():shutil.copy2(out/name,baseline/name)
     if (out/'previews').is_dir():shutil.copytree(out/'previews',baseline/'previews',dirs_exist_ok=True)
     for original in file.parent.glob(file.stem+'.*'):shutil.copy2(original,baseline/original.name)
    original=json.loads(original_assets.read_text())
    assert original['rig_project_sha256']==assets['rig_project_sha256'] and original['rig_validation_sha256']==assets['rig_validation_sha256'], 'Use a new baseline after a rig change'
    assert set(original['files'])==set(assets['files'])
    assert all(original['files'][p]==assets['files'][p] for p in assets['files'] if p!=relative), 'Non-attack packages changed since baseline'
    mesh=unreal.load_asset(config['dest']+'/SK_'+config['name']);skeleton=mesh.get_editor_property('skeleton')
    animation=unreal.load_asset(config['dest']+'/Animations/RA_MM_Attack_01')
    names=json.loads((out/'unreal-bones.json').read_text())['target'];assert set(bones)<=set(names)
    source_path=baseline/'attack-source-keys.json'
    if not source_path.exists():
     assert sha(file)==original['files'][relative], 'Cannot sample original keys after mutation'
     source=keys(animation,skeleton,names);source['source_package_sha256']=sha(file)
     source_path.write_text(json.dumps(source,indent=2)+'\n')
    source=json.loads(source_path.read_text());assert source['source_package_sha256']==original['files'][relative]
    model=animation.get_editor_property('data_model_interface');assert source['count']==model.get_number_of_keys() and abs(source['length']-animation.get_play_length())<1e-6
    current=keys(animation,skeleton,names)
    controller=animation.get_editor_property('controller');controller.open_bracket('Bounded Crew attack spine gesture',False)
    try:
     # Restore every previously adjusted allowed bone from original keys, then
     # apply this trial. This prevents alpha trials from compounding.
     for bone in UPPER_BONES:
      transforms=source['bones'][bone]
      quats=[slerp(source['reference'][bone]['rotation'],t['rotation'],alpha) if bone in bones else t['rotation'] for t in transforms]
      assert controller.set_bone_track_keys(bone,[unreal.Vector(*t['translation']) for t in transforms],[unreal.Quat(*q) for q in quats],[unreal.Vector(*t['scale']) for t in transforms],False)
    finally:controller.close_bracket(False)
    assert unreal.EditorAssetLibrary.save_loaded_asset(animation)
    measured=keys(animation,skeleton,names);maxima={'unedited_translation_cm':0.,'unedited_quaternion':0.,'unedited_scale':0.,'edited_quaternion_error':0.}
    for bone in names:
     for i,t in enumerate(measured['bones'][bone]):
      original_key=source['bones'][bone][i]
      assert math.dist(t['translation'],original_key['translation'])<.001 and math.dist(t['scale'],original_key['scale'])<.00001
      expected=slerp(source['reference'][bone]['rotation'],original_key['rotation'],alpha) if bone in bones else original_key['rotation']
      error=min(math.dist(t['rotation'],expected),math.dist(t['rotation'],[-v for v in expected]))
      if bone in bones:maxima['edited_quaternion_error']=max(maxima['edited_quaternion_error'],error)
      else:
       maxima['unedited_translation_cm']=max(maxima['unedited_translation_cm'],math.dist(t['translation'],original_key['translation']))
       maxima['unedited_quaternion']=max(maxima['unedited_quaternion'],error)
       maxima['unedited_scale']=max(maxima['unedited_scale'],math.dist(t['scale'],original_key['scale']))
    assert maxima['unedited_quaternion']<.001 and maxima['edited_quaternion_error']<.001,maxima
    after_files=package_hashes(config['dest']);assert set(after_files)==set(assets['files'])
    assert all(after_files[p]==assets['files'][p] for p in after_files if p!=relative)
    assets['files']=after_files;asset_path.write_text(json.dumps(assets,indent=2)+'\n')
    report={'status':'applied_pending_visual_review','slug':config['slug'],'alpha_from_bind':alpha,'bones':bones,'requested_bones':requested_bones,'preserved_frozen_bones':sorted(frozen),'rig_project_sha256':config['validation']['project_sha256'],'rig_validation_sha256':sha(out/'rig-validation.json'),'baseline_assets_sha256':sha(original_assets),'original_keys_sha256':sha(source_path),'source_attack_package_sha256':original['files'][relative],'adjusted_attack_package_sha256':after_files[relative],'maximum_key_errors':maxima,'all_non_attack_packages_unchanged':True,'script_sha256':sha(Path(__file__))}
    (out/'attack-gesture-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CREW_ATTACK_GESTURE',config['slug'],alpha,bones,maxima,flush=True)
  finally:
   assert snapshot(paths)==before,'Content outside selected attack packages changed'

if __name__=='__main__':main()
