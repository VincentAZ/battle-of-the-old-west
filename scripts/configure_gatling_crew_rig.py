"""Explicit mapping for the inspected Gatling guide; no source/guide geometry edits.

Provider created extra clothing/gun branches. Human major chains are identified
from topology and positions; auxiliaries map to nearest anatomical segment. Entire
separate carriage is overridden rigidly by rig-settings, irrespective of provider
weights. Ambiguous fingers retain a documented manual map and stay unanimated.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/crew/playable-v001/gatling-gunner'
bones = json.loads((OUT/'guide-bones.json').read_text())
d = {b['name']: b for b in bones}
children = {n: [b['name'] for b in bones if b['parent'] == n] for n in d}
m = {'tripo::Root': 'Hips', 'tripo::0_Left_Limb_0': 'Spine', 'tripo::0_Left_Limb_1': 'Spine1', 'bone_3': 'Neck', 'tripo::Head_0': 'Head', 'tripo::Head_1': 'Head'}
for n, part in zip(['tripo::0_Left_Limb_'+str(i) for i in range(2, 6)], ('Shoulder', 'Arm', 'ForeArm', 'Hand')): m[n] = 'Left'+part
for n, part in zip(['bone_'+str(i) for i in range(25, 29)], ('Shoulder', 'Arm', 'ForeArm', 'Hand')): m[n] = 'Right'+part
for side, roots in [('Left', ['bone_22', 'tripo::0_Left_Limb_6', 'bone_13', 'bone_16', 'bone_19']), ('Right', ['bone_29', 'bone_32', 'bone_35', 'bone_38', 'bone_41'])]:
    for n, finger in zip(roots, ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')):
        for digit in range(1, 4):
            m[n] = side+'Hand'+finger+str(digit)
            if digit < 3:
                assert len(children[n]) == 1
                n = children[n][0]
for side, prefix in [('Left', 'tripo::1_Left_Limb_'), ('Right', 'tripo::0_Right_Limb_')]:
    for i, part in enumerate(('UpLeg', 'Leg', 'Foot', 'ToeBase')): m[prefix+str(i)] = side+part
anatomical = {n: v for n, v in m.items() if 'Hand' not in v and v != 'Hips'}

def segment_distance(point, a, b):
    vector = [b[i]-a[i] for i in range(3)]
    length2 = sum(x*x for x in vector)
    t = max(0, min(1, sum((point[i]-a[i])*vector[i] for i in range(3))/max(length2, 1e-12)))
    return sum((point[i]-a[i]-t*vector[i])**2 for i in range(3))

aux = {}
for n in [b['name'] for b in bones if b['name'] not in m]:
    nearest = min(anatomical, key=lambda a: segment_distance(d[n]['head'], d[a]['head'], d[a]['tail']))
    m[n] = anatomical[nearest]
    aux[n] = m[n]
assert set(m) == set(d)
(OUT/'explicit-bone-mapping.json').write_text(json.dumps(m, indent=2)+'\n')
settings = json.loads((OUT/'rig-settings.json').read_text())
settings['freeze_bones'] = [s+'Hand'+f+str(i) for s in ('Left', 'Right') for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky') for i in range(1, 4)]+['GatlingCarriage']
constraint='Keep all finger rotations at approved rest pose: cramped provider finger anatomy is ambiguous; no finger gesture clips until hand-specific QA.'
if constraint not in settings['motion_constraints']: settings['motion_constraints'].append(constraint)
components=json.loads((OUT/'components.json').read_text())
settings['source_geometry_uv_sha256']=components['geometry_uv_sha256']
settings['rigid_regions']=[dict(name='GatlingCarriage',parent='root',vertex_indices=sorted(i for c in components['components'] if c['max'][0]>-.315 for i in c['indices']))]
settings['guide_mapping_notes'] = ['Major human chains inspected by topology and anatomical position.', 'Left thumb is bone_22 chain at thumb-side proximal hand; provider chain order was not anatomical.', 'Auxiliary garment/prop branches collapsed to nearest major anatomical segment; complete carriage geometry overridden by rigid mask.']
settings['auxiliary_bone_mapping'] = aux
(OUT/'rig-settings.json').write_text(json.dumps(settings, indent=2)+'\n')
