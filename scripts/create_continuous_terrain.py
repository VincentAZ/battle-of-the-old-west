"""Replace intersecting terrain sheets with one continuous gameplay surface.

Keeps the existing height function around the authored depot and battlefield,
then blends smoothly into the distant ridge function. The original northern
vista is retained, with continuous weathered ridge chains around the remaining
azimuths. New relief has exactly zero influence through 80 meters. The art-study
source is read for its material and never overwritten. CPU-only Blender export.
"""
import bpy
import json
import math
import hashlib
import shutil
import bisect
from mathutils import Vector, noise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/world'
OUT.mkdir(parents=True, exist_ok=True)
STUDY = ROOT/'art/water_depot_v2/WaterDepot.blend'
study_hash = hashlib.sha256(STUDY.read_bytes()).hexdigest()
backup = OUT/'backups'
backup.mkdir(exist_ok=True)
for name in ('ContinuousTerrain.blend','ContinuousTerrain.fbx','continuous-terrain.json'):
    source = OUT/name
    target = backup/(source.stem+'-before-360'+source.suffix)
    if source.exists() and not target.exists():
        shutil.copy2(source,target)
bpy.ops.wm.open_mainfile(filepath=str(backup/'ContinuousTerrain-before-360.blend'))
old_objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(old_objects)==1
old_points={(float(v.co.x),float(v.co.y)):float(v.co.z) for v in old_objects[0].data.vertices}
old_axis=sorted({p[0] for p in old_points})
bpy.ops.wm.open_mainfile(filepath=str(STUDY))
material = bpy.data.materials['DustAndGravel']
material.use_fake_user = True
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)


def near(x, y):
    f = noise.fractal(Vector((x*.09, y*.09, .74)), 1.0, 2.0, 4)
    flatten = min(1, max(0, (math.hypot(x, y-1)-6)/10))
    rut = -.05*(math.exp(-((x+.7)/.22)**2)+math.exp(-((x-1.0)/.22)**2)) if y < -3 else 0
    return -.06+f*.8*flatten+noise.noise_vector(Vector((x*1.6, y*1.6, 2.3))).z*.028+rut


def original_far(x, y):
    peaks = sum(h*math.exp(-((x-cx)/wx)**2-((y-cy)/wy)**2) for cx, cy, h, wx, wy in
                [(-150,140,58,115,90), (60,190,67,130,140), (235,155,68,120,110), (-310,230,75,150,170)])
    f = noise.fractal(Vector((x*.025, y*.025, 6.41)), 1.1, 2.1, 5)
    return (.20+.12*abs(f))*peaks*min(1,max(0,(math.hypot(x,y-5)-50)/35))-.6


def smooth(a,b,value):
    t=min(1.,max(0.,(value-a)/(b-a)))
    return t*t*t*(t*(t*6.-15.)+10.)


def distant_relief(x,y):
    radius=math.hypot(x,y)
    if radius<=80:
        return 0.
    angle=math.atan2(y,x)
    # Broad asymmetric chains enclose a dry basin, with different setbacks and
    # saddles in each direction. The second chain occludes the finite mesh edge.
    first_radius=405+76*math.sin(2*angle+.4)+42*math.sin(5*angle-1.1)
    second_radius=835+103*math.sin(3*angle-1.4)+49*math.cos(7*angle+.6)
    first_height=23+7*math.sin(3*angle+.8)+4*math.cos(6*angle-1.7)
    second_height=70+17*math.cos(2*angle-.5)+9*math.sin(5*angle+1.1)
    warp=noise.fractal(Vector((x*.009,y*.009,9.27)),1.0,2.0,3)
    first=first_height*math.exp(-((radius-first_radius-20*warp)/121)**2)
    second=second_height*math.exp(-((radius-second_radius-28*warp)/164)**2)
    foothill_radius=190+28*math.sin(4*angle)+21*math.cos(7*angle)
    foothill=(2.8+1.2*math.cos(3*angle))*math.exp(-((radius-foothill_radius)/82)**2)
    # Broad domain-warped drainage cuts avoid periodic radial teeth. Restrict
    # the smallest detail to a resolvable scale instead of jagged grid peaks.
    detail=noise.fractal(Vector((x*.012+warp*.2,y*.012-warp*.15,3.18)),1.15,2.,3)
    drainage=abs(noise.fractal(Vector((x*.008+warp*.17,y*.008,12.71)),1.1,2.,3))
    rough=max(.62,min(1.13,.90+.13*detail-.15*drainage))
    return (first+second+foothill)*rough*smooth(80,130,radius)


def previous_height(x,y):
    # Reuse authored float values. mathutils.noise.noise_vector can vary across
    # Blender sessions, so evaluating an unchanged formula is not preservation.
    if (x,y) in old_points:
        return old_points[(x,y)]
    if old_axis[0]<=x<=old_axis[-1] and old_axis[0]<=y<=old_axis[-1]:
        ix=max(1,min(len(old_axis)-1,bisect.bisect_left(old_axis,x)))
        iy=max(1,min(len(old_axis)-1,bisect.bisect_left(old_axis,y)))
        x0,x1=old_axis[ix-1:ix+1]
        y0,y1=old_axis[iy-1:iy+1]
        u,v=(x-x0)/(x1-x0),(y-y0)/(y1-y0)
        return ((1-u)*(1-v)*old_points[(x0,y0)]+u*(1-v)*old_points[(x1,y0)]+
                (1-u)*v*old_points[(x0,y1)]+u*v*old_points[(x1,y1)])
    blend=min(1,max(0,(math.hypot(x,y)-38)/32))
    blend=blend*blend*(3-2*blend)
    n=near(x,y) if blend<1 else 0
    return n*(1-blend)+original_far(x,y)*blend


def height(x,y,extra=True):
    return previous_height(x,y)+(distant_relief(x,y) if extra else 0)


# Keep every original coordinate, including the exact gameplay triangulation.
# Add profile detail only outside 65m, with 3m spacing through the ridge chains.
original_axis=sorted(set([i*.5 for i in range(-130,131)] + [sign*(65+i*6.0) for sign in (-1,1) for i in range(1,107)]))
axis=sorted(set(original_axis+[sign*(68+i*3.) for sign in (-1,1) for i in range(345)] + [sign*(1100+i*12.) for sign in (-1,1) for i in range(1,25)]))
vertices, faces = [], []
max_near_error = 0
max_existing_error_80 = 0
for y in axis:
    for x in axis:
        z = height(x,y)
        vertices.append((x,y,z))
        if math.hypot(x,y) <= 38:
            max_near_error = max(max_near_error,abs(z-old_points[(x,y)]))
        if math.hypot(x,y) <= 80:
            max_existing_error_80=max(max_existing_error_80,abs(z-height(x,y,False)))
count = len(axis)
for row in range(count-1):
    for col in range(count-1):
        a = row*count+col
        faces.append((a,a+1,a+1+count,a+count))
mesh = bpy.data.meshes.new('ContinuousTerrain')
mesh.from_pydata(vertices, [], faces)
mesh.materials.append(material)
uv = mesh.uv_layers.new(name='UVMap')
for polygon in mesh.polygons:
    polygon.use_smooth = True
    for loop in polygon.loop_indices:
        point = vertices[mesh.loops[loop].vertex_index]
        uv.data[loop].uv = (point[0]/3.5,point[1]/3.5)
mesh.update()
obj = bpy.data.objects.new('SM_ContinuousTerrain', mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ContinuousTerrain.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'ContinuousTerrain.fbx'), use_selection=True,
    object_types={'MESH'}, apply_unit_scale=True, add_leaf_bones=False, bake_anim=False,
    axis_forward='-Y', axis_up='Z',mesh_smooth_type='FACE')
horizon=[]
for azimuth in range(360):
    theta=math.radians(azimuth)
    samples=[(r,height(math.cos(theta)*r,25+math.sin(theta)*r)) for r in range(90,1351,6)]
    old_samples=[(r,height(math.cos(theta)*r,25+math.sin(theta)*r,False)) for r in range(90,699,12)]
    horizon.append({'azimuth_degrees':azimuth,
                    'elevation_degrees':max(math.degrees(math.atan2(z-1.8,r)) for r,z in samples),
                    'previous_elevation_degrees':max(math.degrees(math.atan2(z-1.8,r)) for r,z in old_samples)})
assert max_near_error==0 and max_existing_error_80==0
assert min(s['elevation_degrees'] for s in horizon)>2.5, 'Missing distant silhouette in an azimuth'
assert hashlib.sha256(STUDY.read_bytes()).hexdigest()==study_hash
report = {'vertices': len(vertices), 'triangles': len(faces)*2, 'units': 'meters',
          'preserved_radius_m': 38, 'maximum_preserved_height_error_m': max_near_error,
          'new_relief_zero_radius_m':80,'maximum_additive_height_within_80_m':max_existing_error_80,
          'preservation_method':'literal vertices from preserved pre-360 Blender mesh; identical grid and faces within 65m square',
          'extent_m':max(axis),'height_range_m':[min(v[2] for v in vertices),max(v[2] for v in vertices)],
          'horizon_observer_m':[0,25,1.8], 'horizon_samples':horizon,
          'minimum_horizon_elevation_degrees':min(s['elevation_degrees'] for s in horizon),
          'maximum_horizon_elevation_degrees':max(s['elevation_degrees'] for s in horizon),
          'boundary_edges':4*(count-1),'interior_holes':0,'grid_axis_count':count,
          'continuous_single_surface': True, 'uses_existing_cc0_material': 'DustAndGravel',
          'source_study_modified': False,'source_study_sha256':study_hash,
          'previous_continuous_surface_preserved_under':'art/world/backups'}
(OUT/'continuous-terrain.json').write_text(json.dumps(report,indent=2)+'\n')
print('CONTINUOUS_TERRAIN_EXPORTED',json.dumps({k:v for k,v in report.items() if k!='horizon_samples'}),flush=True)
