"""Create a flat, sourced corral setting without changing the accepted wagons."""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import holdings_base as base

folder=ROOT/'art/western/holdings/expansion-review-v001/wagon-fort'
out=folder/'base-v004'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=json.loads((folder/'base-evidence-v001.json').read_text())
assert evidence['pre_modeling_review']['completed']
assert sha(folder/'holding.json')==evidence['holding_sha256']
for source in evidence['sources']:assert sha(ROOT/source['local'])==source['sha256']
assert not out.exists()
original_ground=base.ground_mesh


def flat_ground(*args,**kwargs):
    ground=original_ground(*args,**kwargs)
    # All tires and slack chain links were authored at Z=0. Keeping the
    # independent ground at the same plane prevents buried wheel rims.
    for vertex in ground.data.vertices:vertex.co.z=0
    palette=args[3]
    colors=ground.data.color_attributes['Col']
    for loop in ground.data.loops:
        p=ground.data.vertices[loop.vertex_index].co
        blend=.5+.24*math.sin(p.x*2.3+.7)*math.sin(p.y*2.9+1.3)+.10*math.sin(p.x*7+p.y*4)
        rgb=base.lerp(palette['ground'],palette['ground_alt'],blend)
        alpha=colors.data[loop.index].color[3]
        colors.data[loop.index].color_srgb=(*rgb,alpha)
    ground.data.update()
    return ground


class CorralOutline:
    def __init__(self,rng,half_x,half_y,margin,wobble):
        self.hx=half_x;self.hy=half_y
        self.phase=rng.uniform(0,math.tau)
    def radius(self,angle):
        ellipse=(math.cos(angle)**2/self.hx**2+math.sin(angle)**2/self.hy**2)**-.5
        return ellipse+.40*(1+.10*math.sin(3*angle+self.phase))

base.Outline=CorralOutline
base.ground_mesh=flat_ground
sys.argv=[__file__,'--','--holding',str(folder/'holding.json'),
          '--review',str(folder/'review-v002'),'--output',str(out),'--samples','24']
base.main()
(out/'source-script.py').write_bytes(Path(__file__).read_bytes())
(out/'authoring.json').write_text(json.dumps(dict(
    project_sha256=sha(out/'wagon-fort-Base.blend'),
    evidence_sha256=sha(folder/'base-evidence-v001.json'),
    helper_script_sha256=sha(Path(base.__file__)),
    script_sha256=sha(Path(__file__)),
    flat_contact_plane_z=0,game_imported=False),indent=2)+'\n')
