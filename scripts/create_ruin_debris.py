"""Build fractured debris kits and wind-streaked ash meshes for native ruins."""
import bpy, math, random, json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parents[1]/'art/camps/ruin-debris'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
MATS={n:bpy.data.materials.new(n) for n in ['M_Ruin_M_Camp_Concrete','M_Ruin_M_Camp_CorrodedSteel','M_Camp_TreeChar','M_Ruin_Ash']}
records=[]
def mesh(name,verts,faces,mat):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);data.materials.append(MATS[mat]);return ob

def fragment(rng,p,size,mat):
    # Broken slabs have a chipped perimeter, tapered fracture faces and unequal thickness.
    n=rng.randint(5,8);angles=[(i+rng.uniform(-.22,.22))*math.tau/n for i in range(n)]
    ring=[(math.cos(a)*size[0]*rng.uniform(.65,1),math.sin(a)*size[1]*rng.uniform(.65,1)) for a in angles]
    v=[(x+p[0],y+p[1],p[2]) for x,y in ring]+[(x*rng.uniform(.7,1.1)+p[0],y*rng.uniform(.7,1.1)+p[1],p[2]+size[2]*rng.uniform(.5,1.2)) for x,y in ring]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh('Fractured slab',v,faces,mat)

def export(objects,name):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();ob=objects[0];ob.name=name
    tri=ob.modifiers.new("Stable fracture triangles","TRIANGULATE");bpy.ops.object.modifier_apply(modifier=tri.name)
    # UVs for substrate textures; ash carries authored streak UVs.
    if not ob.data.uv_layers:
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    path=OUT/(name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True)
    records.append({'name':name,'fbx':str(path),'materials':[m.name for m in ob.data.materials],'vertices':len(ob.data.vertices)})
    bpy.data.objects.remove(ob,do_unlink=True)

for variant in range(4):
    rng=random.Random(4921+variant);obs=[]
    for i in range(30):
        # Debris settles in a lopsided spill, with fine fragments beyond the main pile.
        x=rng.uniform(-.8,.8);y=rng.uniform(-.35,.5)+.15*x
        scale=rng.uniform(.025,.13) if i>10 else rng.uniform(.10,.28)
        obs.append(fragment(rng,(x,y,0),(scale,scale*rng.uniform(.5,1.1),scale*rng.uniform(.25,.65)),'M_Ruin_M_Camp_Concrete'))
    # Bent exposed reinforcing rods rather than clean rectangular silhouettes.
    for i in range(3):
        curve=bpy.data.curves.new('Bent rebar','CURVE');curve.dimensions='3D';curve.bevel_depth=.008;curve.bevel_resolution=1
        spline=curve.splines.new('POLY');spline.points.add(3)
        x=rng.uniform(-.4,.4);y=rng.uniform(-.25,.25)
        for j,p in enumerate(spline.points):p.co=(x+j*.1,y+math.sin(j)*.04,.04+j*.016,1)
        ob=bpy.data.objects.new('Bent rebar',curve);bpy.context.collection.objects.link(ob);curve.materials.append(MATS['M_Ruin_M_Camp_CorrodedSteel'])
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');obs.append(bpy.context.object)
    export(obs,f'SM_Ruin_Concrete_{variant}')
    obs=[]
    for i in range(23):
        x=rng.uniform(-.8,.8);y=rng.uniform(-.5,.5)
        ob=fragment(rng,(0,0,0),(rng.uniform(.12,.36),rng.uniform(.012,.055),rng.uniform(.015,.06)),'M_Camp_TreeChar')
        ob.rotation_euler.z=rng.uniform(-math.pi,math.pi);ob.location=(x,y,0);obs.append(ob)
    export(obs,f'SM_Ruin_Timber_{variant}')
    obs=[]
    for i in range(7):
        x=rng.uniform(-.55,.55);y=rng.uniform(-.3,.3);v=[];f=[]
        nx,ny=12,5;w=rng.uniform(.22,.7);d=rng.uniform(.18,.4)
        for j in range(ny+1):
            for k in range(nx+1):
                xx=k/nx*w;yy=j/ny*d
                z=.02+abs(math.sin(k*math.pi*.8))*.013+max(0,k/nx-.65)**2*.5
                v.append((xx+x+rng.uniform(-.014,.014),yy+y+rng.uniform(-.014,.014),z))
        for j in range(ny):
            for k in range(nx):
                if (k in (0,nx-1) or j in (0,ny-1)) and rng.random()<.35:continue
                a=j*(nx+1)+k;f.append((a,a+1,a+nx+2,a+nx+1))
        ob=mesh('Torn buckled corrugated sheet',v,f,'M_Ruin_M_Camp_CorrodedSteel')
        sol=ob.modifiers.new('Broken sheet thickness','SOLIDIFY');sol.thickness=.003
        bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=sol.name);obs.append(ob)
    export(obs,f'SM_Ruin_Metal_{variant}')
    # Long broken-edged drifts, never a radial patch or a disk.
    v=[];f=[];nx,ny=28,8
    for i in range(nx+1):
        x=(i/nx-.5)*2.;width=(.1+.17*rng.random())*(.3+.7*math.sin(math.pi*i/nx))
        center=.13*math.sin(i*.27+variant)
        for j in range(ny+1):
            t=j/ny;v.append((x,center+(t-.5)*width*2, .003+.018*math.sin(math.pi*t)*rng.uniform(.3,1)))
    for i in range(nx):
        for j in range(ny):
            if j in (0,ny-1) and rng.random()<.22:continue
            a=i*(ny+1)+j;f.extend([(a,a+ny+1,a+1),(a+1,a+ny+1,a+ny+2)])
    ob=mesh('Windblown ash drift',v,f,'M_Ruin_Ash');uv=ob.data.uv_layers.new(name='UVMap')
    for poly in ob.data.polygons:
        for loop in poly.loop_indices:
            idx=ob.data.loops[loop].vertex_index;uv.data[loop].uv=(idx//(ny+1)/nx,idx%(ny+1)/ny)
    export([ob],f'SM_Ruin_AshDrift_{variant}')
(OUT/'manifest.json').write_text(json.dumps(records,indent=2)+'\n')
print('Exported',len(records),'debris meshes')
