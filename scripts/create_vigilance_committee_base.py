"""Add a documented Montana town setting to the unchanged reviewed hall."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import holdings_base as base
folder=ROOT/'art/western/holdings/expansion-review-v001/vigilance-committee';out=folder/'base-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((folder/'base-evidence-v001.json').read_text());assert e['pre_modeling_review']['completed']
assert sha(folder/'holding.json')==e['holding_sha256'];assert sha(folder/'base-holding-v001.json')==e['base_configuration_sha256']
for s in e['sources']:assert sha(ROOT/s['local'])==s['sha256']
assert not out.exists()
original_ground=base.ground_mesh
class Outline:
    def __init__(self,rng,half_x,half_y,margin,wobble):self.phase=rng.uniform(0,math.tau)
    def radius(self,a):
        hy=2.98 if math.sin(a)<0 else 2.56
        return (abs(math.cos(a)/3.32)**4+abs(math.sin(a)/hy)**4)**(-.25)*(1+.028*math.sin(5*a+self.phase)+.016*math.cos(9*a))
def ground_mesh(*args,**kwargs):
    o=original_ground(*args,**kwargs);palette=args[3];col=o.data.color_attributes['Col']
    for v in o.data.vertices:v.co.z=0
    for loop in o.data.loops:
        p=o.data.vertices[loop.vertex_index].co;grain=.5+.24*math.sin(p.x*4.3+p.y)*math.cos(p.y*5.9)
        rgb=base.lerp(palette['ground'],palette['ground_alt'],grain)
        edge=max(abs(p.x)/3.05,abs(p.y)/2.38);turf=max(0,min(.82,(edge-.70)*2.5))*(.65+.35*math.sin(p.x*3.6+p.y)**2)
        if abs(p.x)<2.80 and p.y<0:turf=0
        rgb=base.lerp(rgb,base.lerp(palette['grass'],palette['grass_alt'],grain),turf)
        col.data[loop.index].color_srgb=(*rgb,col.data[loop.index].color[3])
    o.data.update();return o
def scatter(collection_name,rng,outline,kind,count,palette,keep_out,**kwargs):
    objects=[];centres=[]
    for attempt in range(15000):
        if len(centres)==count:break
        a=rng.uniform(0,math.tau);r=outline.radius(a)*math.sqrt(rng.uniform(.2,.86));x,y=r*math.cos(a),r*math.sin(a)
        if abs(x)<2.86 and -1.96<y<2.03:continue
        if abs(x)<2.80 and y<0:continue
        if any(math.hypot(x-px,y-py)<(.16 if kind=='tuft' else .12)for px,py in centres):continue
        centres.append((x,y))
        if kind=='tuft':
            tint=base.lerp(palette['grass'],palette['grass_alt'],rng.random())
            for j in range(rng.randint(6,9)):
                h=rng.uniform(.08,.18);bpy.ops.mesh.primitive_cone_add(vertices=3,radius1=.010,depth=h,location=(x+rng.uniform(-.025,.025),y+rng.uniform(-.025,.025),h/2))
                o=bpy.context.object;o.scale.y=.20;o.rotation_euler=(rng.uniform(-.4,.4),rng.uniform(-.4,.4),rng.uniform(0,math.tau))
                bpy.context.view_layer.update();o.location.z-=min((o.matrix_world@v.co).z for v in o.data.vertices)
                o.name=f'Holding_Base_grass_{len(objects):03}';o.color=(*base.srgb(tint),1);objects.append(o)
        elif kind=='rock':
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,0));o=bpy.context.object
            o.scale=(rng.uniform(.065,.14),rng.uniform(.06,.13),rng.uniform(.035,.085));o.rotation_euler=(rng.uniform(-.3,.3),rng.uniform(-.3,.3),rng.uniform(0,math.tau))
            bpy.context.view_layer.update();o.location.z-=min((o.matrix_world@v.co).z for v in o.data.vertices)
            o.name=f'Holding_Base_rock_{len(objects):03}';o.color=(*base.srgb(base.lerp(palette['rock'],palette['rock_alt'],rng.random())),1);objects.append(o)
        else:
            assert kind=='needle';length=rng.uniform(.08,.16);bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,.0015));o=bpy.context.object;o.dimensions=(length,.003,.003);o.rotation_euler.z=rng.uniform(0,math.tau);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            o.name=f'Holding_Base_needle_{len(objects):03}';o.color=(*base.srgb((.43+rng.uniform(-.04,.04),.25,.10)),1);objects.append(o)
    assert len(centres)==count,(kind,len(centres))
    return objects
base.Outline=Outline;base.ground_mesh=ground_mesh;base.scatter=scatter
sys.argv=[__file__,'--','--holding',str(folder/'base-holding-v001.json'),'--review',str(folder/'review-v006'),'--output',str(out),'--samples','24'];base.main()
(out/'source-script.py').write_bytes(Path(__file__).read_bytes())
(out/'authoring.json').write_text(json.dumps(dict(project_sha256=sha(out/'vigilance-committee-Base.blend'),evidence_sha256=sha(folder/'base-evidence-v001.json'),helper_script_sha256=sha(Path(base.__file__)),script_sha256=sha(Path(__file__)),grass_clumps=48,stones=12,game_imported=False),indent=2)+'\n')
