"""Create explicit mappings for inspected provider topology exceptions.

This recovers weights on the exact approved mesh, never invents skin geometry.
Missing canonical finger/toe joints are unweighted compatibility joints, explicitly
recorded as synthetic; fingers remain at bind transforms in the body-motion clips.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
slug=sys.argv[1]
OUT=ROOT/'art/western/crew/playable-v001'/slug
bones=json.loads((OUT/'guide-bones.json').read_text());d={b['name']:b for b in bones};ch={n:[b['name'] for b in bones if b['parent']==n] for n in d}
layouts={
 'wyatt-earp':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::0_Left_Limb_0','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Left_Limb_4','bone_29'],legs=['tripo::0_Right_Limb_0','tripo::1_Left_Limb_0']),
 'laudanum-doctor':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::0_Right_Limb_0','tripo::Head_0'],centernames=['Hips','Spine','Spine1','Neck','Head'],hands=['tripo::0_Right_Limb_4','bone_14'],legs=['tripo::1_Left_Limb_0','bone_20']),
 'prospector':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_3','tripo::0_Left_Limb_3'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'sharpshooter':dict(center=['tripo::Root','tripo::0_Left_Limb_0','tripo::0_Left_Limb_1','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Neck','Head'],hands=['bone_7','bone_22'],legs=['bone_35','bone_39']),
 'drover':dict(center=['tripo::Root','tripo::0_Left_Limb_0','tripo::0_Left_Limb_1','tripo::0_Left_Limb_2'],centernames=['Hips','Spine','Spine1','Spine2'],hands=['bone_7','tripo::0_Left_Limb_6'],legs=['tripo::1_Left_Limb_0','tripo::0_Right_Limb_0']),
 'getaway-rider':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_3','tripo::Spine_6'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'charles-goodnight':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Head_0','bone_51'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_3','tripo::0_Left_Limb_2'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'claim-jumper':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_2','tripo::0_Left_Limb_3'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'coach-guard':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Head_0','tripo::Head_1','tripo::Head_2'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_2','tripo::0_Left_Limb_3'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'barn-burner':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::1_Left_Limb_0','tripo::Head_0'],centernames=['Hips','Spine','Spine1','Neck','Head'],hands=['tripo::1_Left_Limb_4','bone_27'],legs=['tripo::0_Right_Limb_0','tripo::0_Left_Limb_0']),
 'bounty-hunter':dict(center=['tripo::Root','tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['bone_9','tripo::0_Right_Limb_3'],legs=['tripo::1_Right_Limb_0','tripo::1_Left_Limb_0']),
 'homestead-defender':dict(center=['tripo::Root','tripo::Spine_0','tripo::0_Right_Limb_0','tripo::0_Right_Limb_1','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['tripo::0_Right_Limb_5','bone_24'],legs=['tripo::1_Left_Limb_0','tripo::0_Left_Limb_0']),
 'revival-sister':dict(center=['tripo::Root','tripo::0_Right_Limb_0','tripo::0_Right_Limb_1','tripo::0_Right_Limb_2','tripo::Head_0','tripo::Head_1'],centernames=['Hips','Spine','Spine1','Spine2','Neck','Head'],hands=['bone_9','tripo::0_Right_Limb_6'],legs=['tripo::1_Right_Limb_0','tripo::0_Left_Limb_0'])
}
c=layouts[slug];m=dict(zip(c['center'],c['centernames']));assert set(m)<=set(d)
def chain(n):
 r=[n]
 while ch[r[-1]]:
  assert len(ch[r[-1]])==1
  r+=ch[r[-1]]
 return r
def dist(a,b):return sum((d[a]['head'][i]-d[b]['head'][i])**2 for i in range(3))
for side,hand in zip(('Left','Right'),c['hands']):
 n=hand
 for part in ('Hand','ForeArm','Arm','Shoulder'):
  m[n]=side+part;n=d[n]['parent']
 if not ch[hand]: continue
 bases=sorted(ch[hand],key=lambda n:dist(n,hand));thumb=bases[0]
 bases=[thumb]+sorted(bases[1:],key=lambda n:dist(n,chain(thumb)[-1]))
 for base,finger in zip(bases,('Thumb','Index','Middle','Ring','Pinky')):
  for i,n in enumerate(chain(base),1):m[n]=side+'Hand'+finger+str(i)
for side,leg in zip(('Left','Right'),c['legs']):
 for i,n in enumerate(chain(leg)):m[n]=side+('UpLeg','Leg','Foot','ToeBase')[min(i,3)]
major={n:v for n,v in m.items() if 'Hand' not in v and v!='Hips'}
def segdist(point,a,b):
 v=[b[i]-a[i] for i in range(3)];t=max(0,min(1,sum((point[i]-a[i])*v[i] for i in range(3))/max(sum(x*x for x in v),1e-12)))
 return sum((point[i]-a[i]-t*v[i])**2 for i in range(3))
aux={}
for n in [b['name'] for b in bones if b['name'] not in m]:
 parent=d[n]['parent']
 if parent in m and m[parent].endswith(('ForeArm','Hand','Head')): target=m[parent]
 else:
  near=min(major,key=lambda a:segdist(d[n]['head'],d[a]['head'],d[a]['tail']));target=major[near]
 m[n]=target;aux[n]=target
assert set(m)==set(d)
previous=json.loads((OUT/'rig-settings.json').read_text()) if (OUT/'rig-settings.json').exists() else {}
settings=dict(synthesize_missing_bones=True,motion_constraints=['Finger local bind transforms remain unchanged in all body clips.'],guide_mapping_notes=['Explicit major anatomy inspected against provider joint positions.','Missing finger/toe compatibility joints are unweighted synthesized joints, not anatomical measurements.','Auxiliary garment/forearm chains collapse to their mapped anatomical parent or nearest major anatomical segment.'],auxiliary_bone_mapping=aux)
settings['motion_constraints']=previous.get('motion_constraints',settings['motion_constraints'])
settings['guide_mapping_notes']=list(dict.fromkeys(previous.get('guide_mapping_notes',[])+settings['guide_mapping_notes']))
settings={**previous,**settings}
(OUT/'explicit-bone-mapping.json').write_text(json.dumps(m,indent=2)+'\n')
if '--mapping-only' not in sys.argv:(OUT/'rig-settings.json').write_text(json.dumps(settings,indent=2)+'\n')
print(slug,'explicit bones',len(m),'auxiliary',aux)
