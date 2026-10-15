"""Create a sourced woodland setting around the unchanged static ram."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import holdings_base as base
folder=ROOT/'art/western/holdings/expansion-review-v001/timber-ram'
out=folder/'base-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((folder/'base-evidence-v001.json').read_text())
assert e['pre_modeling_review']['completed']
assert sha(folder/'holding.json')==e['holding_sha256']
for s in e['sources']:assert sha(ROOT/s['local'])==s['sha256']
assert not out.exists()
original_ground=base.ground_mesh
theta=math.radians(155)
def axial(x,y):return x*math.cos(theta)+y*math.sin(theta),-x*math.sin(theta)+y*math.cos(theta)
class Outline:
    def __init__(self,rng,half_x,half_y,margin,wobble):
        self.hx=half_x;self.hy=half_y;self.phase=rng.uniform(0,math.tau)
    def radius(self,a):
        t=a-theta
        return (abs(math.cos(t)/3.65)**3+abs(math.sin(t)/.98)**3)**(-1/3)*(1+.045*math.sin(a*5+self.phase)+.023*math.cos(a*9))
def ground_mesh(*args,**kwargs):
    o=original_ground(*args,**kwargs);palette=args[3];col=o.data.color_attributes['Col']
    for v in o.data.vertices:v.co.z=0
    for loop in o.data.loops:
        p=o.data.vertices[loop.vertex_index].co;a,b=axial(p.x,p.y)
        grain=.5+.22*math.sin(p.x*5.3+p.y*3)*math.cos(p.y*6.9)
        rgb=base.lerp(palette['ground'],palette['ground_alt'],grain)
        turf=max(0,min(.76,(abs(b)-.46)*1.8))*(.65+.35*math.sin(a*3.6)**2)
        rgb=base.lerp(rgb,base.lerp(palette['grass'],palette['grass_alt'],grain),turf)
        col.data[loop.index].color_srgb=(*rgb,col.data[loop.index].color[3])
    o.data.update();return o
def scatter(collection_name,rng,outline,kind,count,palette,keep_out,**kwargs):
    objects=[];centres=[]
    for attempt in range(10000):
        if len(centres)==count:break
        a=rng.uniform(0,math.tau);r=outline.radius(a)*math.sqrt(rng.uniform(.04,.85))
        x,y=r*math.cos(a),r*math.sin(a);along,across=axial(x,y)
        # A generous clear strip prevents vegetation piercing the log.
        if abs(across)<(.55 if kind=='tuft' else .47) and abs(along)<3.4:continue
        if any(math.hypot(x-px,y-py)<(.13 if kind=='tuft' else .07)for px,py in centres):continue
        centres.append((x,y))
        if kind=='tuft':
            tint=base.lerp(palette['grass'],palette['grass_alt'],rng.random())
            for j in range(rng.randint(6,9)):
                h=rng.uniform(.08,.17)
                bpy.ops.mesh.primitive_cone_add(vertices=3,radius1=.009,depth=h,location=(x+rng.uniform(-.025,.025),y+rng.uniform(-.025,.025),h/2))
                o=bpy.context.object;o.scale.y=.20;o.rotation_euler=(rng.uniform(-.4,.4),rng.uniform(-.4,.4),rng.uniform(0,math.tau))
                bpy.context.view_layer.update();o.location.z-=min((o.matrix_world@v.co).z for v in o.data.vertices)
                o.name=f'Holding_Base_grass_{len(objects):03}';o.color=(*base.srgb(tint),1);objects.append(o)
        else:
            assert kind=='needle'
            length=rng.uniform(.08,.16)
            bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,.0015))
            o=bpy.context.object;o.dimensions=(length,.003,.003);o.rotation_euler.z=rng.uniform(0,math.tau)
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            o.name=f'Holding_Base_needle_{len(objects):03}';o.color=(*base.srgb((.43+rng.uniform(-.04,.04),.25,.10)),1);objects.append(o)
    assert len(centres)==count,(kind,len(centres))
    return objects
base.Outline=Outline;base.ground_mesh=ground_mesh;base.scatter=scatter
sys.argv=[__file__,'--','--holding',str(folder/'holding.json'),'--review',str(folder/'review-v002'),'--output',str(out),'--samples','24']
base.main()
(out/'source-script.py').write_bytes(Path(__file__).read_bytes())
(out/'authoring.json').write_text(json.dumps(dict(project_sha256=sha(out/'timber-ram-Base.blend'),evidence_sha256=sha(folder/'base-evidence-v001.json'),helper_script_sha256=sha(Path(base.__file__)),script_sha256=sha(Path(__file__)),grass_clumps=60,fallen_needles=100,game_imported=False),indent=2)+'\n')
