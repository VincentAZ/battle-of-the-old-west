"""Rigid-bind the free hand's source islands, preserving rifle and planted-pose constraints."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/sharpshooter';qa=out/'rig-mask-qa';qa.mkdir(exist_ok=True);p=out/'rig-settings.json'
if not (qa/'settings-before-free-hand.json').exists():shutil.copyfile(p,qa/'settings-before-free-hand.json')
s=json.loads((qa/'settings-before-free-hand.json').read_text());c=json.loads((out/'components.json').read_text());ids=[61,69,75,76,86,90,91,92];indices=sorted({i for n in ids for i in c['components'][n]['indices']});s['rigid_regions'].append(dict(name='FreeHand',parent='LeftHand',vertex_indices=indices));s['freeze_bones']=sorted(set(s['freeze_bones'])|{'FreeHand'});s['motion_constraints'].append(dict(type='preserve_bind_local_transform',bones=['FreeHand'],reason='Free left hand keeps approved finger shape, following the animated LeftHand bone.'))
s['free_hand_provenance']=dict(component_ids=ids,notes=['Original rifle region and constraints preserved. Free hand islands no longer inherit lower-body guide weights.'])
p.write_text(json.dumps(s,indent=2)+'\n');print(len(indices))
