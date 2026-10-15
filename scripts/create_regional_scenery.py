"""Author sourced regional scenery locally in Mixar; no external generation.

Trees are meshes with individual branch/leaf geometry, not billboard cones.
Source terrain and earlier review assets are read-only. Units are metres.
"""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/regions/review-v002'
EVIDENCE = ROOT/'research/western-presentation/regional-battlefields.json'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class Geometry:
    def __init__(self): self.vertices, self.faces, self.materials = [], [], []

    def face(self, points, material):
        start=len(self.vertices); self.vertices.extend(points)
        self.faces.append(tuple(range(start,start+len(points)))); self.materials.append(material)

    def limb(self, a, b, radius, end_radius, material=0, sides=10):
        a,b=Vector(a),Vector(b); direction=(b-a).normalized()
        u=direction.cross(Vector((0,1,0))).normalized(); v=direction.cross(u).normalized()
        for i in range(sides):
            p,q=math.tau*i/sides,math.tau*(i+1)/sides
            x,y=u*math.cos(p)+v*math.sin(p),u*math.cos(q)+v*math.sin(q)
            self.face([a+x*radius,a+y*radius,b+y*end_radius,b+x*end_radius],material)

    def mesh(self,name,materials):
        mesh=bpy.data.meshes.new(name); mesh.from_pydata(self.vertices,[],self.faces); mesh.update()
        for material in materials: mesh.materials.append(material)
        for poly,index in zip(mesh.polygons,self.materials): poly.material_index=index
        ob=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(ob)
        return ob


def material(name,colour):
    mat=bpy.data.materials.new(name); mat.diffuse_color=(*colour,1); mat.use_nodes=True
    bsdf=mat.node_tree.nodes['Principled BSDF']; bsdf.inputs['Base Color'].default_value=(*colour,1)
    bsdf.inputs['Roughness'].default_value=.86
    return mat


def pine(name,seed,materials):
    rng=random.Random(seed); g=Geometry(); height=rng.uniform(12,17)
    # Slightly crooked tapered bole, orange plates over dark fissures.
    for j in range(16):
        z=j*height/16; z1=(j+1)*height/16
        a=(.1*math.sin(j*.4),.05*math.cos(j*.6),z)
        b=(.1*math.sin((j+1)*.4),.05*math.cos((j+1)*.6),z1)
        r=.36*(1-j/18); r1=.36*(1-(j+1)/18)
        g.limb(a,b,r,r1,0,12)
        for k in range(11):
            angle=k*math.tau/11+rng.uniform(-.06,.06)
            q=angle+.38; lo=z+.06; hi=z1-.08
            g.face([(math.cos(angle)*(r+.012),math.sin(angle)*(r+.012),lo),
                    (math.cos(q)*(r+.012),math.sin(q)*(r+.012),lo+.03),
                    (math.cos(q)*(r1+.012),math.sin(q)*(r1+.012),hi),
                    (math.cos(angle)*(r1+.012),math.sin(angle)*(r1+.012),hi-.04)],1)
    for j in range(48):
        z=rng.uniform(height*.36,height*.96); t=z/height
        angle=j*2.399+rng.uniform(-.2,.2); length=(math.sin(t*math.pi)**.55)*rng.uniform(2.0,3.4)
        tip=Vector((math.cos(angle)*length,math.sin(angle)*length,z+rng.uniform(.2,1.2)))
        base=Vector((0,0,z)); g.limb(base,tip,.09*(1-t)+.025,.008,0,7)
        for k in range(5):
            f=.43+k*.12; branch=base.lerp(tip,f)
            theta=angle+(-1 if k%2 else 1)*rng.uniform(.45,1)
            end=branch+Vector((math.cos(theta)*.75,math.sin(theta)*.75,.3))
            g.limb(branch,end,.02,.003,0,5)
            for m in range(300):
                origin=end+Vector((rng.uniform(-.48,.48),rng.uniform(-.48,.48),rng.uniform(-.14,.28)))
                angle2=rng.uniform(0,math.tau); tilt=rng.uniform(.15,.8)
                direction=Vector((math.cos(angle2),math.sin(angle2),tilt)).normalized()
                width=Vector((-direction.y,direction.x,0))*.016
                point=origin+direction*rng.uniform(.16,.29)
                g.face([origin-width,origin+width,point],2+(m%3==0))
    return g.mesh(name,materials)


def cottonwood(name,seed,materials,willow=False):
    rng=random.Random(seed); g=Geometry(); height=4 if willow else 14
    g.limb((0,0,0),(.25,0,height*.72),.14 if willow else .45,.035,0,12)
    for j in range(22 if willow else 36):
        a=j*2.399; z=rng.uniform(height*.3,height*.8)
        length=rng.uniform(1,2.3) if willow else rng.uniform(2.6,4.2)
        tip=Vector((math.cos(a)*length,math.sin(a)*length,z+rng.uniform(.5,2)))
        root=Vector((0,0,z*.85)); g.limb(root,tip,.03 if willow else .085,.009,0,8)
        for k in range(7):
            start=root.lerp(tip,.25+k*.1); angle=a+rng.uniform(-1.1,1.1)
            end=start+Vector((math.cos(angle)*.9,math.sin(angle)*.9,rng.uniform(.2,1)))
            g.limb(start,end,.012,.0025,0,5)
            for l in range(140):
                c=start.lerp(end,rng.uniform(.35,1))+Vector((rng.uniform(-.5,.5),rng.uniform(-.5,.5),rng.uniform(-.25,.5)))
                direction=Vector((math.cos(angle+l),math.sin(angle+l),rng.uniform(-.2,.7))).normalized()
                cross=direction.cross(Vector((0,0,1))).normalized()
                size=rng.uniform(.08,.13) if not willow else rng.uniform(.07,.12)
                # Cottonwood: broad triangular blade, serrated edges. Willow: narrow blade.
                w=size*(.2 if willow else .68)
                points=[c-direction*size, c-direction*size*.55+cross*w*.65,
                        c-direction*size*.35+cross*w*.6,c-direction*size*.2+cross*w,
                        c+direction*size*.2+cross*w*.65,c+direction*size,
                        c+direction*size*.2-cross*w*.65,c-direction*size*.2-cross*w,
                        c-direction*size*.35-cross*w*.6,c-direction*size*.55-cross*w*.65]
                g.face(points,1+(l%3==0))
    return g.mesh(name,materials)


def export(ob):
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(OUT/(ob.name+'.fbx')),use_selection=True,object_types={'MESH'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
    ob.data.calc_loop_triangles()
    return dict(name=ob.name,fbx=ob.name+'.fbx',sha256=digest(OUT/(ob.name+'.fbx')),
                triangles=len(ob.data.loop_triangles),materials=[m.name for m in ob.data.materials])


def main():
    evidence=json.loads(EVIDENCE.read_text()); assert len(evidence['regions'])==3
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True,exist_ok=True); bpy.ops.wm.read_factory_settings(use_empty=True)
    palettes={'M_Region_PineFissure':(.075,.031,.013),'M_Region_PineBark':(.30,.11,.026),
              'M_Region_Needle':(.025,.12,.016),'M_Region_NeedleTip':(.07,.20,.028),
              'M_Region_CottonwoodBark':(.13,.105,.075),'M_Region_Leaf':(.055,.23,.022),
              'M_Region_LeafLight':(.14,.34,.035)}
    mats={k:material(k,v) for k,v in palettes.items()}; objects=[]
    for i in range(3):objects.append(pine('SM_Region_Ponderosa'+str(i),141+i,list(mats.values())[:4]))
    for i in range(2):objects.append(cottonwood('SM_Region_Cottonwood'+str(i),191+i,list(mats.values())[4:]))
    objects.append(cottonwood('SM_Region_Willow',291,list(mats.values())[4:],True))
    assets=[export(ob) for ob in objects]
    # Editable tree source preserves every mesh at its local base origin.
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'RegionalScenery.blend'))
    # Contact view positions are preview-only, not source geometry transforms.
    for i,ob in enumerate(objects): ob.location=(i*11-27,0,0)
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU';scene.cycles.samples=24
    scene.render.resolution_x=1600;scene.render.resolution_y=700;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('ClearSky'); scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.65,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    sun=bpy.data.objects.new('Sun',bpy.data.lights.new('Sun','SUN'));scene.collection.objects.link(sun)
    sun.rotation_euler=(.35,-.45,-.4);sun.data.energy=3;sun.data.angle=.12;sun.data.color=(1,.92,.8)
    bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.data.materials.append(material('PreviewGrass',(.09,.17,.035)))
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera
    camera.location=(30,-85,37);camera.rotation_euler=(Vector((0,0,7))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=77
    scene.render.filepath=str(OUT/'trees-contact.png');bpy.ops.render.render(write_still=True)
    (OUT/'manifest.json').write_text(json.dumps(dict(evidence_sha256=digest(EVIDENCE),assets=assets,
        material_linear_rgb=palettes,source_sha256=digest(OUT/'RegionalScenery.blend'),
        visual_review='pending',external_services_used=False),indent=2)+'\n')
    print('REGIONAL_SCENERY_AUTHORED',len(assets),flush=True)


if __name__=='__main__':main()
