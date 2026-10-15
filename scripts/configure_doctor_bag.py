"""Add rigid carried doctor-bag weights while retaining the validated foot corrections."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'art/western/crew/playable-v001/laudanum-doctor';qa=out/'rig-mask-qa';qa.mkdir(exist_ok=True);p=out/'rig-settings.json'
if not (qa/'settings-before-bag.json').exists():shutil.copyfile(p,qa/'settings-before-bag.json')
s=json.loads((qa/'settings-before-bag.json').read_text());c=json.loads((out/'components.json').read_text());ids=[9,18,39,40,41,43,45,50,51,53,54,62,64,65,66,67,69,70,83,87,88,90,98,103,108];indices=sorted({i for n in ids for i in c['components'][n]['indices']})
s['source_geometry_uv_sha256']=c['geometry_uv_sha256'];s['rigid_regions']=[dict(name='DoctorBag',parent='LeftHand',vertex_indices=indices)];s['freeze_bones']=sorted(set(s.get('freeze_bones',[]))|{'DoctorBag'});s['motion_constraints']=[dict(type='preserve_bind_local_transform',bones=['DoctorBag'],reason='Leather doctor bag and handle remain rigid in the carrying left hand.')];s['bag_mask_provenance']=dict(component_ids=ids,notes=['Original foot rest bones and all existing weight overrides copied unchanged from settings-before-bag.json.','Complete leather/metal bag islands selected by source topology and atlas colors; skin fingers excluded.'])
p.write_text(json.dumps(s,indent=2)+'\n');print(len(indices))
