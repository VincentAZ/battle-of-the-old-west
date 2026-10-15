"""Add a sourced spring setting to the accepted tent without changing its mesh."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import holdings_base as base
folder=ROOT/'art/western/holdings/expansion-review-v001/revival-tent'
out=folder/'base-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=json.loads((folder/'base-evidence-v001.json').read_text())
assert evidence['pre_modeling_review']['completed']
assert sha(folder/'holding.json')==evidence['holding_sha256']
for s in evidence['sources']:assert sha(ROOT/s['local'])==s['sha256']
assert not out.exists()
original_ground=base.ground_mesh

class Outline:
    def __init__(self,rng,half_x,half_y,margin,wobble):
        self.hx=half_x;self.hy=half_y;self.phase=rng.uniform(0,math.tau)
    def radius(self,a):
        return 3.18+.07*math.sin(3*a+self.phase)+.035*math.cos(7*a)

def ground_mesh(*args,**kwargs):
    ground=original_ground(*args,**kwargs)
    palette=args[3];colors=ground.data.color_attributes['Col']
    for v in ground.data.vertices:v.co.z=0
    for loop in ground.data.loops:
        p=ground.data.vertices[loop.vertex_index].co;r=math.hypot(p.x,p.y)
        mix=.5+.18*math.sin(p.x*3.1)*math.sin(p.y*3.8)+.12*math.cos(p.x*7-p.y*4)
        rgb=base.lerp(palette['ground'],palette['ground_alt'],mix)
        edge=2.25+.035*math.sin(p.x*4+p.y*3)
        turf=max(0,min(1,(r-edge)/.34))
        if p.y<-.4:turf*=max(0,min(1,(abs(p.x)-.26)/.25))
        earth=base.lerp(palette['earth'],(.46,.37,.26),mix)
        rgb=base.lerp(earth,rgb,turf)
        alpha=colors.data[loop.index].color[3]
        colors.data[loop.index].color_srgb=(*rgb,alpha)
    ground.data.update();return ground

def scatter(collection_name,rng,outline,kind,count,palette,keep_out,**kwargs):
    assert kind=='tuft'
    objects=[];centres=[]
    for attempt in range(2000):
        if len(centres)==count:break
        a=rng.uniform(0,math.tau);r=rng.uniform(2.40,outline.radius(a)-.16)
        x,y=r*math.cos(a),r*math.sin(a)
        if y<0 and abs(x)<.52:continue
        # Grass stays between guy/stake axes, away from timber or taut lines.
        bay=(a-math.pi/16)%(math.tau/16)
        if min(bay,math.tau/16-bay)<.075:continue
        if any(math.hypot(x-px,y-py)<.16 for px,py in centres):continue
        centres.append((x,y));tint=base.lerp(palette['grass'],palette['grass_alt'],rng.random())
        for j in range(rng.randint(6,9)):
            h=rng.uniform(.09,.18)
            bpy.ops.mesh.primitive_cone_add(vertices=3,radius1=.009,depth=h,location=(x+rng.uniform(-.035,.035),y+rng.uniform(-.035,.035),h/2))
            o=bpy.context.object;o.scale.y=.18
            o.rotation_euler=(rng.uniform(-.38,.38),rng.uniform(-.38,.38),rng.uniform(0,math.tau))
            bpy.context.view_layer.update()
            bottom=min((o.matrix_world@v.co).z for v in o.data.vertices)
            o.location.z-=bottom
            o.name=f'Holding_Base_grass_blade_{len(objects):03}'
            o.color=(*base.srgb(tint),1);objects.append(o)
    assert len(centres)==count,len(centres)
    return objects

base.Outline=Outline;base.ground_mesh=ground_mesh;base.scatter=scatter
sys.argv=[__file__,'--','--holding',str(folder/'holding.json'),'--review',str(folder/'review-v002'),'--output',str(out),'--samples','24']
base.main()
(out/'source-script.py').write_bytes(Path(__file__).read_bytes())
(out/'authoring.json').write_text(json.dumps(dict(project_sha256=sha(out/'revival-tent-Base.blend'),evidence_sha256=sha(folder/'base-evidence-v001.json'),helper_script_sha256=sha(Path(base.__file__)),script_sha256=sha(Path(__file__)),flat_contact_plane_z=0,grass_clumps=65,game_imported=False),indent=2)+'\n')
