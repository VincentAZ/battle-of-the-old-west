"""Author two terrain-fitted dunes and sourced Sonoran cacti without paid jobs."""
import hashlib
import json
import math
import random
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/regions/desert-v004'
BRIEF=ROOT/'research/western-presentation/desert-v002.json'
SOURCE=ROOT/'art/world/ContinuousTerrain.blend'
sys.path.insert(0,str(ROOT/'scripts'))
import create_regional_scenery as helpers
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)

def main():
    assert json.loads(BRIEF.read_text())['sources']
    OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'DesertScenery.blend').exists(),'Preserve existing review sources'
    before=sha(SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    terrain=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    bvh=BVHTree.FromObject(terrain,bpy.context.evaluated_depsgraph_get())
    def ground(x,y):
        hit,_,_,_=bvh.ray_cast(Vector((x,-y,400)),Vector((0,0,-1)),800)
        assert hit is not None,(x,y)
        return hit.z
    # Native coordinates in metres; FBX flips Y at import.
    def source(p):return (p[0],-p[1],p[2])
    def mesh(name,verts,faces,mats,slots=None):
        me=bpy.data.meshes.new(name);me.from_pydata([source(p) for p in verts],[],faces);me.update()
        for mat in mats:me.materials.append(mat)
        if slots:
            for f,i in zip(me.polygons,slots):f.material_index=i
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.000001)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        # Mirroring native Y to source Y reverses an open heightfield's winding.
        if 'Dune' in name:
            if sum(f.normal.z for f in bm.faces)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
            bm.normal_update()
            assert all(f.normal.z>0 for f in bm.faces),'Dune must face upward'
        bm.to_mesh(me);bm.free()
        uv=me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            axes=sorted(range(3),key=lambda i:abs(poly.normal[i]))[:2]
            for li in poly.loop_indices:
                point=me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv=(point[axes[0]],point[axes[1]])
        for f in me.polygons:f.use_smooth=True
        ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob);return ob
    palettes={'M_Region_DuneSandV004':(.48,.27,.095),'M_Region_CactusGreenV004':(.045,.19,.036),
              'M_Region_CactusLightV004':(.10,.27,.055),'M_Region_CactusSpineV004':(.36,.23,.09)}
    mats={k:helpers.material(k,v) for k,v in palettes.items()}
    assets=[];dunes=[]
    # Two side dunes: each has a long windward face and a shorter lee face.
    for i,(cx,cy,rx,ry,height,flip) in enumerate([(-52,14,17,27,5.8,1),(48,49,15,24,4.7,-1)]):
        verts=[];faces=[];weights=[];steps=100
        for row in range(steps+1):
            v=-1+row*2/steps
            for col in range(steps+1):
                u=-1+col*2/steps;x=cx+u*rx;y=cy+v*ry
                crest=flip*(-.14+.12*math.sin(v*math.pi))
                width=(1+crest) if u<crest else (1-crest)
                profile=max(0,1-abs(u-crest)/width)
                profile=profile**(1.1 if (u-crest)*flip<0 else 1.7)
                # Elliptical, tapering footprint: no rectangular sand patch.
                radial=math.sqrt(u*u+v*v)
                ends=max(0,1-v*v)**1.4*smooth((1-radial)/.24)
                lift=height*profile*ends
                # Fade vertical slope at the outer perimeter for a grounded edge.
                lift*=smooth((1-abs(u))/.15)*smooth((1-abs(v))/.15)
                z=ground(x,y)+lift-.008
                verts.append((x,y,z));weights.append(smooth(lift/.45))
                if row and col:
                    a=row*(steps+1)+col
                    faces.append((a-steps-2,a-steps-1,a,a-1))
        ob=mesh('SM_Region_DesertDuneV004_'+str(i),verts,faces,[mats['M_Region_DuneSandV004']])
        color=ob.data.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='POINT')
        for slot,w in zip(color.data,weights):slot.color=(1,1,1,w)
        assets.append(ob);dunes.append(dict(center=[cx,cy],radius=[rx,ry],height=height))
    verts=[];faces=[];slots=[]
    def face(points,slot):
        start=len(verts);verts.extend(points);faces.append(tuple(range(start,start+len(points))));slots.append(slot)
    def tube(path,radius,ribs=12,spines=True):
        rings=[];sides=ribs*6
        for j,center in enumerate(path):
            center=Vector(center);tangent=Vector(path[min(j+1,len(path)-1)])-Vector(path[max(0,j-1)])
            tangent.normalize();u=tangent.cross(Vector((0,1,0))).normalized();v=tangent.cross(u).normalized()
            rr=radius[j] if isinstance(radius,list) else radius
            ring=[]
            for k in range(sides):
                angle=k*math.tau/sides;r=rr*(1+.11*math.cos(angle*ribs))
                p=center+r*(u*math.cos(angle)+v*math.sin(angle));ring.append(p)
                if spines and j%2==0 and k%6==0 and rr>.055:
                    outward=(p-center).normalized();tip=p+outward*.07
                    face([p+tangent*.012,p-tangent*.012,tip+u*.013],2)
                    face([p+v*.01,p-v*.01,tip+tangent*.035],2)
            rings.append(ring)
        for j in range(1,len(rings)):
            for k in range(sides):face([rings[j-1][k],rings[j-1][(k+1)%sides],rings[j][(k+1)%sides],rings[j][k]],0 if k%6<4 else 1)
        face(list(reversed(rings[0])),0);face(rings[-1],1)
    def stem(x,y,z,h,r):
        path=[(x,y,z+h*j/30) for j in range(31)];radii=[r*(1-.12*j/30) for j in range(31)]
        for j in range(1,7):
            a=j*math.pi/12;path.append((x,y,z+h+math.sin(a)*r*.9));radii.append(max(.008,r*.88*math.cos(a)))
        tube(path,radii)
    # Cacti stay on stable ground, separate from both dune footprints.
    plants=[(-32,23,7.5,20),(-42,43,6.5,155),(32,28,8.5,35),(42,76,7.1,115),
            (-47,72,8.0,5),(24,-6,6.5,80),(-22,-8,7.4,145),(48,-21,8.6,55),
            (-35,67,3.0,0),(39,-4,2.7,0),(-43,-12,2.3,0)]
    for index,(x,y,h,yaw) in enumerate(plants):
        z=ground(x,y)-.04;radius=.29 if h>4 else .18;stem(x,y,z,h,radius)
        if h<4:continue
        for side in (-1,1):
            angle=math.radians(yaw)+(0 if side==1 else math.pi)
            d=Vector((math.cos(angle),math.sin(angle),0));base=Vector((x,y,z+h*(.47 if side==1 else .62)))
            elbow=.65 if side==1 else .52;path=[]
            for j in range(13):
                a=j*math.pi/24
                path.append(base+d*(radius*.4+elbow*math.sin(a))+Vector((0,0,elbow*(1-math.cos(a)))))
            armheight=h*(.25 if side==1 else .17)
            for j in range(1,15):path.append(path[12]+Vector((0,0,armheight*j/14)))
            end=path[-1];r=radius*.69;radii=[r]*len(path)
            for j in range(1,7):
                a=j*math.pi/12;path.append(end+Vector((0,0,math.sin(a)*r)));radii.append(max(.006,r*math.cos(a)))
            tube(path,radii,10)
    # Flattened, overlapping pads form low prickly-pear groups.
    clusters=[(-31,5),(30,23),(-32,51),(30,65),(-29,-12),(19,-12),(31,70),(-31,72)]
    rng=random.Random(1881)
    for x,y in clusters:
        base=ground(x,y)
        for pad in range(9):
            cx=x+rng.uniform(-.75,.75);cy=y+rng.uniform(-.5,.5)
            cz=base+.38+(pad//3)*.36;angle=rng.uniform(0,math.tau)
            u=Vector((math.cos(angle),math.sin(angle),0));v=Vector((-math.sin(angle),math.cos(angle),0));c=Vector((cx,cy,cz))
            rings=[]
            for j in range(13):
                lat=-math.pi/2+j*math.pi/12;ring=[]
                for k in range(24):
                    a=k*math.tau/24
                    ring.append(c+u*(.31*math.cos(lat)*math.cos(a))+v*(.085*math.cos(lat)*math.sin(a))+Vector((0,0,.43*math.sin(lat))))
                rings.append(ring)
            for j in range(12):
                for k in range(24):face([rings[j][k],rings[j][(k+1)%24],rings[j+1][(k+1)%24],rings[j+1][k]],1)
            for side in (-1,1):
                for j in range(4):
                    for k in range(3):
                        p=c+u*((k-1)*.13)+Vector((0,0,(j-1.5)*.16))+v*.08*side
                        face([p+u*.01,p-u*.01,p+v*.045*side],2)
    cacti=mesh('SM_Region_DesertCactiV004',verts,faces,[mats[n] for n in list(mats)[1:]],slots)
    assets.append(cacti)
    # Preserve only the new source objects; original terrain was opened read-only.
    for ob in list(bpy.data.objects):
        if ob not in assets:bpy.data.objects.remove(ob,do_unlink=True)
    helpers.OUT=OUT
    records=[helpers.export(ob) for ob in assets]
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'DesertScenery.blend'))
    assert sha(SOURCE)==before
    (OUT/'manifest.json').write_text(json.dumps(dict(brief_sha256=sha(BRIEF),source_terrain_sha256=before,
        assets=records,material_linear_rgb=palettes,dunes=dunes,saguaros=plants,prickly_pear_clusters=clusters,
        source_sha256=sha(OUT/'DesertScenery.blend'),collision=False,visual_review='pending'),indent=2)+'\n')
    print('DESERT_SCENERY_AUTHORED',len(records),flush=True)

if __name__=='__main__':main()
