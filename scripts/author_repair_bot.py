"""Author a mechanical service robot on the preserved Survivor_A rest skeleton.

Coordinated invocation (does not overwrite the survivor):
  blender -b --factory-startup --disable-autoexec --python scripts/author_repair_bot.py
Optional -- --render adds studio front/three-quarter/back renders. This script
creates an editable meter-scale .blend, a centimeter FBX, and baked PBR maps.
All geometry is authored here; only the existing CC0 character's rig is reused.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/oldwest_survivor/Survivor_A.blend'
OUT = ROOT / 'art/characters/repair_bot'
TEX = OUT / 'textures'
OUT.mkdir(parents=True, exist_ok=True)
TEX.mkdir(exist_ok=True)
SOURCE_SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for obj in list(bpy.data.objects):
    if obj != arm:
        bpy.data.objects.remove(obj, do_unlink=True)
arm.animation_data_clear()
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
for bone in arm.pose.bones:
    bone.matrix_basis.identity()
# UE's FBX importer retains the non-"Armature" object as an extra root bone.
# Preserve its exact name as well as the 53 Blender bones: the existing native
# skeleton has 54 entries, including Survivor_Rig. Renaming this object would
# produce an incompatible root even with identical deform-bone transforms.
assert arm.name == 'Survivor_Rig', arm.name
assert len(arm.data.bones) == 53
assert all(abs(v - 1) < .00001 for v in arm.scale)


def rig_signature():
    return [{'name': b.name, 'parent': b.parent.name if b.parent else None,
             'matrix': [[float(v) for v in row] for row in b.matrix_local],
             'head': list(b.head_local), 'tail': list(b.tail_local),
             'deform': b.use_deform} for b in arm.data.bones]


rig_before = rig_signature()
parts = []
specs = {}


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def material(name, base, roughness, metallic, noise_scale=95, bump=.0003, emission=0, wear=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*base, 1)
    n, link = mat.node_tree.nodes, mat.node_tree.links
    p = n.get('Principled BSDF')
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Specular IOR Level'].default_value = .5
    tex = n.new('ShaderNodeTexCoord')
    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = noise_scale
    noise.inputs['Detail'].default_value = 3
    noise.inputs['Roughness'].default_value = .7
    link.new(tex.outputs['Object'], noise.inputs['Vector'])
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .12
    ramp.color_ramp.elements[0].color = (*(v * .63 for v in base), 1)
    ramp.color_ramp.elements[1].position = .87
    ramp.color_ramp.elements[1].color = (*(min(v * 1.15, .94) for v in base), 1)
    link.new(noise.outputs['Fac'], ramp.inputs[0])
    link.new(ramp.outputs['Color'], p.inputs['Base Color'])
    if wear:
        # Bake chipped exposed metal at real convex edges, with broken coverage.
        # The manufactured bevel geometry supplies the pointiness signal.
        geometry = n.new('ShaderNodeNewGeometry')
        edge = n.new('ShaderNodeMapRange')
        edge.clamp = True
        edge.inputs['From Min'].default_value = .50
        edge.inputs['From Max'].default_value = .58
        link.new(geometry.outputs['Pointiness'], edge.inputs['Value'])
        broken = n.new('ShaderNodeMath'); broken.operation = 'MULTIPLY'
        link.new(edge.outputs['Result'], broken.inputs[0]); link.new(noise.outputs['Fac'], broken.inputs[1])
        worn_color = n.new('ShaderNodeMixRGB'); worn_color.blend_type = 'MIX'
        worn_color.inputs[2].default_value = (.22, .235, .23, 1)
        link.new(broken.outputs[0], worn_color.inputs[0]); link.new(ramp.outputs['Color'], worn_color.inputs[1])
        link.new(worn_color.outputs[0], p.inputs['Base Color'])
        exposed = n.new('ShaderNodeMapRange')
        exposed.inputs['To Min'].default_value = metallic; exposed.inputs['To Max'].default_value = .92
        link.new(broken.outputs[0], exposed.inputs['Value']); link.new(exposed.outputs['Result'], p.inputs['Metallic'])
    rough = n.new('ShaderNodeMapRange')
    rough.inputs['From Min'].default_value = .0
    rough.inputs['From Max'].default_value = 1
    rough.inputs['To Min'].default_value = max(.1, roughness - .12)
    rough.inputs['To Max'].default_value = min(.98, roughness + .1)
    link.new(noise.outputs['Fac'], rough.inputs['Value'])
    link.new(rough.outputs['Result'], p.inputs['Roughness'])
    normal = n.new('ShaderNodeBump')
    normal.inputs['Distance'].default_value = bump
    normal.inputs['Strength'].default_value = .28
    link.new(noise.outputs['Fac'], normal.inputs['Height'])
    link.new(normal.outputs['Normal'], p.inputs['Normal'])
    if emission:
        p.inputs['Emission Color'].default_value = (*base, 1)
        p.inputs['Emission Strength'].default_value = emission
    specs[name] = {'base': base, 'roughness': roughness, 'metallic': metallic,
                   'noise_scale_per_meter': noise_scale, 'bump_meters': bump, 'emission': emission,
                   'geometry_edge_wear_baked': wear}
    return mat


paint = material('M_RepairBot_Enamel', (.055, .235, .22), .46, .15, wear=True)
cream = material('M_RepairBot_Ceramic', (.59, .55, .39), .40, .12, wear=True)
steel = material('M_RepairBot_MachinedSteel', (.29, .32, .33), .32, .94, 220, .00013)
dark = material('M_RepairBot_DarkSteel', (.035, .045, .047), .51, .80)
rubber = material('M_RepairBot_Bellows', (.016, .021, .02), .86, .0, 160)
copper = material('M_RepairBot_Copper', (.33, .13, .045), .42, .92, 120)
signal = material('M_RepairBot_Optic', (.04, .55, .72), .16, .20, 50, 0, 2.0)
marking = material('M_RepairBot_ServiceYellow', (.68, .35, .045), .59, .05)


def finish(obj, name, mat, bone, bevel=0):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        m = obj.modifiers.new('Machined_edge_radius', 'BEVEL')
        m.width = bevel
        m.segments = 3
        bpy.ops.object.modifier_apply(modifier=m.name)
    for face in obj.data.polygons:
        face.use_smooth = True
    weighted = obj.modifiers.new('Weighted_surface_normals', 'WEIGHTED_NORMAL')
    weighted.keep_sharp = True
    weighted.weight = 40
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    assert bone in arm.data.bones, bone
    obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
    obj.parent = arm
    skin = obj.modifiers.new('Rigid_mechanical_skin', 'ARMATURE')
    skin.object = arm
    parts.append(obj)
    return obj


def cylinder(name, p, radius, depth, mat, bone, axis=(0, 0, 1), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=p)
    obj = bpy.context.object
    obj.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat, bone, min(.0025, radius * .09))


def beam(name, a, b, radius, mat, bone):
    a, b = Vector(a), Vector(b)
    return cylinder(name, (a + b) * .5, radius, (b - a).length, mat, bone, b - a)


def box(name, p, size, mat, bone, bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=p)
    obj = bpy.context.object
    obj.dimensions = size
    return finish(obj, name, mat, bone, bevel)


def ellipsoid(name, p, radius, mat, bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, radius=1, location=p)
    obj = bpy.context.object
    obj.scale = radius
    return finish(obj, name, mat, bone)


def torus(name, p, major, minor, mat, bone, axis=(0, 0, 1)):
    bpy.ops.mesh.primitive_torus_add(major_segments=36, minor_segments=10,
                                   major_radius=major, minor_radius=minor, location=p)
    obj = bpy.context.object
    obj.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat, bone)


def tube(name, points, radius, mat, bone):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    activate(obj)
    bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object, name, mat, bone)


def shell(name, a, b, rings, mat, bone, sides=32):
    """Lathed elliptical housing with changing section; no cube torso/limbs."""
    a, b = Vector(a), Vector(b)
    direction = (b - a).normalized()
    x = direction.cross(Vector((0, 1, 0))).normalized()
    y = direction.cross(x).normalized()
    vertices = []
    for t, rx, ry in rings:
        center = a.lerp(b, t)
        for i in range(sides):
            theta = i * 2 * math.pi / sides
            vertices.append(center + x * math.cos(theta) * rx + y * math.sin(theta) * ry)
    faces = []
    for r in range(len(rings) - 1):
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((r * sides + i, r * sides + j, (r + 1) * sides + j, (r + 1) * sides + i))
    faces += [tuple(reversed(range(sides))), tuple(range((len(rings) - 1) * sides, len(rings) * sides))]
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat, bone, .002)


def bone_points(name):
    b = arm.data.bones[name]
    return b.head_local.copy(), b.tail_local.copy()


HIPS, CHEST, HEAD = 'mixamorig:Hips', 'mixamorig:Spine2', 'mixamorig:Head'
hip = arm.data.bones[HIPS].head_local.copy()
neck = arm.data.bones['mixamorig:Neck'].head_local.copy()
spine = arm.data.bones['mixamorig:Spine1'].head_local.copy()

# Overlapping clamshell chest, service bay and cooling fins have actual depth.
shell('Pelvic_casting', hip + Vector((0, 0, -.04)), hip + Vector((0, 0, .11)),
      [(0, .12, .078), (.10, .17, .095), (.78, .17, .095), (1, .11, .07)], dark, HIPS)
for z in [hip.z + .13 + i * .025 for i in range(5)]:
    torus('Flexible_spinal_bellows', (0, .015, z), .079, .008, rubber, 'mixamorig:Spine')
shell('Thoracic_pressure_housing', spine + Vector((0, .015, 0)), neck + Vector((0, .015, -.02)),
      [(0, .105, .072), (.1, .16, .1), (.52, .22, .126), (.84, .20, .112), (1, .14, .08)], paint, CHEST)
chest_z = (spine.z + neck.z) * .5
shell('Front_service_hatch', Vector((0, -.105, chest_z - .09)), Vector((0, -.105, chest_z + .07)),
      [(0, .082, .022), (.12, .115, .035), (.87, .115, .035), (1, .095, .02)], cream, CHEST)
for x in [-.085, .085]:
    for z in [chest_z - .052, chest_z + .05]:
        cylinder('Captive_hatch_screw', (x, -.144, z), .007, .005, steel, CHEST, (0, 1, 0), 12)
for i in range(7):
    box('Lower_chest_louver', (-.072 + i * .024, -.13, chest_z - .13), (.012, .016, .044), dark, CHEST, .003)
box('Service_cross_horizontal', (0, -.146, chest_z + .006), (.075, .005, .024), marking, CHEST, .003)
box('Service_cross_vertical', (0, -.147, chest_z + .006), (.023, .006, .073), marking, CHEST, .003)
for side in [-1, 1]:
    for i in range(4):
        cylinder('Exposed_rib_fastener', (side * .198, -.06, chest_z -.02 + i * .025), .006, .01, steel, CHEST, (1, 0, 0), 12)
    tube('Torso_hydraulic_line', [(side * .09, -.08, spine.z), (side * .14, -.105, chest_z -.12),
         (side * .185, -.08, chest_z), (side * .14, -.075, neck.z -.06)], .006, copper, CHEST)
shell('Backpack_cooling_body', (0, .16, chest_z -.15), (0, .16, chest_z +.16),
      [(0,.10,.06),(.08,.14,.065),(.92,.14,.065),(1,.10,.05)], dark, CHEST)
for i in range(10):
    box('Radiator_fin', (0, .224, chest_z -.13 + i*.029), (.235, .025, .007), steel, CHEST, .002)
for x in [-.17,.17]:
    cylinder('Service_canister', (x,.17,chest_z-.04), .033, .21, marking, CHEST)
    torus('Canister_retainer', (x,.17,chest_z-.10), .035,.004,dark,CHEST)
    torus('Canister_retainer', (x,.17,chest_z+.02), .035,.004,dark,CHEST)

# Optical head is a curved manufactured casing with an asymmetric sensor cluster.
head_a, head_b = bone_points(HEAD)
head_center = head_a.lerp(head_b, .42)
ellipsoid('Optical_head_casting', head_center, (.118, .104, .119), cream, HEAD)
ellipsoid('Rear_head_shroud', head_center + Vector((0,.030,0)), (.121,.090,.112), paint, HEAD)
beam('Neck_actuator', neck, head_a + Vector((0,0,.035)), .044, dark, 'mixamorig:Neck')
eye = head_center + Vector((-.029,-.096,.009))
cylinder('Camera_barrel', eye, .047, .040, dark, HEAD, (0,1,0))
torus('Optical_retaining_ring', eye + Vector((0,-.023,0)), .040, .006, copper, HEAD, (0,1,0))
cylinder('Recessed_optical_glass', eye + Vector((0,-.027,0)), .034, .008, signal, HEAD, (0,1,0), 48)
cylinder('Iris_aperture', eye + Vector((0,-.032,0)), .014, .002, dark, HEAD, (0,1,0))
for i in range(3):
    p = head_center + Vector((.067,-.095,.032-i*.024))
    cylinder('Diagnostic_indicator_bezel', p, .010, .01, dark, HEAD,(0,1,0),20)
    cylinder('Diagnostic_indicator', p+Vector((0,-.006,0)), .006, .005, signal, HEAD,(0,1,0),20)
for x in [-.086,.086]:
    cylinder('Temple_pivot', head_center+Vector((x,0,0)),.026,.065,dark,HEAD,(1,0,0))
    cylinder('Temple_cap', head_center+Vector((x*1.4,0,0)),.020,.005,steel,HEAD,(1,0,0))
tube('Antenna_whip',[head_center+Vector((.085,.025,.07)),head_center+Vector((.093,.03,.18)),
                    head_center+Vector((.105,.045,.21))],.0028,steel,HEAD)

# Segmented limbs use the actual rig's bone endpoints, preserving animation rest
# transforms and collision proportions rather than introducing a scaled skeleton.
for side in ['Left','Right']:
    for suffix, radius in [('Arm',.063),('ForeArm',.052),('UpLeg',.082),('Leg',.064)]:
        bone = 'mixamorig:'+side+suffix
        a,b = bone_points(bone)
        direction = (b-a).normalized()
        beam(side+suffix+'_internal_actuator',a,b,radius*.43,steel,bone)
        shell(side+suffix+'_segmented_casting',a,b,
              [(.16,radius*.68,radius*.70),(.22,radius,radius*.87),(.69,radius*.88,radius*.81),(.78,radius*.63,radius*.63)],
              paint if suffix in ['Arm','Leg'] else cream,bone)
        for t in [.21,.70]:
            cylinder(side+suffix+'_end_seal',a.lerp(b,t),radius*.9,.016,dark,bone,direction)
        ellipsoid(side+suffix+'_ball_joint',a,(radius*.77,)*3,dark,bone)
        cylinder(side+suffix+'_pivot_bearing',a,radius*.58,radius*1.6,steel,bone,(0,1,0))
        cylinder(side+suffix+'_pivot_hub',a+Vector((0,-radius*.87,0)),radius*.36,.006,copper,bone,(0,1,0),24)
        outward = Vector((0,-radius*.89,0))
        tube(side+suffix+'_protected_cable',[a.lerp(b,.19)+outward,a.lerp(b,.34)+outward*1.28,
             a.lerp(b,.59)+outward*1.3,a.lerp(b,.75)+outward],.005,rubber,bone)
        for t in [.28,.61]:
            p = a.lerp(b,t)+outward
            cylinder(side+suffix+'_service_bolt',p,.006,.007,steel,bone,(0,1,0),12)
    hand = 'mixamorig:'+side+'Hand'
    a,b = bone_points(hand)
    shell(side+'_tool_hand',a,b,[(0,.034,.025),(.12,.043,.026),(.76,.035,.022),(1,.025,.018)],dark,hand)
    for finger in ['Thumb','Index','Middle','Ring','Pinky']:
        for joint in range(1,4):
            bone = 'mixamorig:'+side+'Hand'+finger+str(joint)
            if bone not in arm.data.bones:
                continue
            a,b = bone_points(bone)
            if (b-a).length < .002:
                continue
            beam(side+finger+str(joint)+'_phalange',a.lerp(b,.12),a.lerp(b,.91),.008 if finger=='Thumb' else .0065,steel,bone)
            ellipsoid(side+finger+str(joint)+'_knuckle',a,(.009,)*3,dark,bone)
    foot = 'mixamorig:'+side+'Foot'
    a,b = bone_points(foot)
    center = Vector((a.x, min(a.y,b.y)-.005, .056))
    box(side+'_traction_foot',center,(.12,.25,.105),dark,foot,.028)
    box(side+'_toe_shell',center+Vector((0,-.053,.030)),(.125,.13,.075),paint,foot,.022)
    for i in range(5):
        box(side+'_replaceable_sole_tread',center+Vector((0,-.095+i*.046,-.048)),(.126,.023,.020),rubber,foot,.005)
    for x in [-.047,.047]:
        cylinder(side+'_foot_fastener',center+Vector((x,-.046,.07)),.006,.006,steel,foot,(0,0,1),12)

# A clearly manufactured wrist service spool distinguishes repair equipment
# from the generic rifle carried by combat characters.
forearm='mixamorig:RightForeArm'
a,b=bone_points(forearm)
spool=a.lerp(b,.62)+Vector((0,-.071,0))
cylinder('Wrist_service_spool',spool,.045,.036,dark,forearm,(0,1,0))
for offset in [-.020,.020]:
    cylinder('Spool_flange',spool+Vector((0,offset,0)),.048,.006,steel,forearm,(0,1,0))
for i in range(5):
    torus('Copper_service_wire',spool+Vector((0,-.013+i*.006,0)),.039,.0025,copper,forearm,(0,1,0))

assert rig_signature()==rig_before, 'Authoring changed the reference skeleton'
part_manifest=[{'name':o.name,'vertices':len(o.data.vertices),'bone':o.vertex_groups[0].name,
                'material':o.data.materials[0].name} for o in parts]

# One shared atlas keeps the runtime skeletal mesh at one material section.
# UV allocation follows actual surface area, including bevels and fasteners.
activate(parts[0])
for obj in parts:
    obj.select_set(True)
bpy.ops.object.join()
mesh=bpy.context.object
mesh.name='RepairBot_MechanicalAssembly'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.004)
bpy.ops.object.mode_set(mode='OBJECT')
assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<.00001 for v in mesh.data.vertices)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.cycles.samples=8
scene.render.bake.margin=12
scene.render.bake.use_clear=True
images={}


def bake(channel, bake_type):
    img=bpy.data.images.new('T_RepairBot_'+channel,width=2048,height=2048,alpha=False)
    img.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
    swaps=[]
    for mat in mesh.data.materials:
        n,link=mat.node_tree.nodes,mat.node_tree.links
        p=n.get('Principled BSDF'); output=next(x for x in n if x.type=='OUTPUT_MATERIAL')
        target=n.new('ShaderNodeTexImage');target.image=img;n.active=target
        if bake_type=='EMIT':
            emission=n.new('ShaderNodeEmission')
            source=p.inputs[{'BaseColor':'Base Color','Roughness':'Roughness','Metallic':'Metallic','Emission':'Emission Color'}[channel]]
            if source.is_linked:
                link.new(source.links[0].from_socket,emission.inputs['Color'])
            else:
                value=source.default_value
                emission.inputs['Color'].default_value=(*value[:3],1) if hasattr(value,'__len__') else (value,value,value,1)
            if channel=='Emission':
                emission.inputs['Strength'].default_value=p.inputs['Emission Strength'].default_value
            link.new(emission.outputs[0],output.inputs['Surface'])
            swaps.append((mat,p,output,emission))
    activate(mesh)
    bpy.ops.object.bake(type=bake_type)
    for mat,p,output,emission in swaps:
        mat.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
        mat.node_tree.nodes.remove(emission)
    img.filepath_raw=str(TEX/('T_RepairBot_'+channel+'.png'));img.file_format='PNG';img.save()
    images[channel]=img


for channel in ['BaseColor','Roughness','Metallic','Emission']:
    bake(channel,'EMIT')
bake('Normal','NORMAL')

atlas=bpy.data.materials.new('M_RepairBot_Atlas');atlas.use_nodes=True
n,link=atlas.node_tree.nodes,atlas.node_tree.links;p=n.get('Principled BSDF')
for channel,socket in [('BaseColor','Base Color'),('Roughness','Roughness'),('Metallic','Metallic'),('Emission','Emission Color')]:
    tex=n.new('ShaderNodeTexImage');tex.image=images[channel]
    link.new(tex.outputs['Color'],p.inputs[socket])
p.inputs['Emission Strength'].default_value=1
tex=n.new('ShaderNodeTexImage');tex.image=images['Normal']
normal=n.new('ShaderNodeNormalMap');link.new(tex.outputs['Color'],normal.inputs['Color']);link.new(normal.outputs['Normal'],p.inputs['Normal'])
mesh.data.materials.clear();mesh.data.materials.append(atlas)
for face in mesh.data.polygons:face.material_index=0
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'RepairBot.blend'))

triangles=sum(len(p.vertices)-2 for p in mesh.data.polygons)
report={'name':'Blacksmith R-07','status':'authored; Unreal animation/physics and visual review pending',
        'source_rig':str(SOURCE),'source_rig_sha256':SOURCE_SHA,'source_rig_license':'CC0-1.0',
        'original_survivor_unchanged':True,'rig_bones':len(rig_before),'rig_reference':rig_before,
        'armature_object_name':arm.name,'expected_unreal_reference_bones':54,
        'parts':part_manifest,'mesh_vertices':len(mesh.data.vertices),'triangles':triangles,
        'skin_weight_policy':'One exact existing bone per rigid mechanical part; normalized weight 1',
        'material_slots':1,'procedural_surface_specs':specs,
        'texture_resolution':[2048,2048],'normal_convention':'OpenGL tangent; flip green at Unreal import',
        'textures':{k:{'path':str(TEX/('T_RepairBot_'+k+'.png')),
                      'sha256':hashlib.sha256((TEX/('T_RepairBot_'+k+'.png')).read_bytes()).hexdigest()} for k in images},
        'mesh_dimensions_m':list(mesh.dimensions)}

# Match the proven centimeter export's bone/data conversion without ever saving
# those converted transforms over the editable meter source.
scale=Matrix.Scale(100,4)
for obj in [arm,mesh]:
    obj.data.transform(scale)
    obj.location*=100
    parent_inverse=obj.matrix_parent_inverse.copy();parent_inverse.translation*=100;obj.matrix_parent_inverse=parent_inverse
scene.unit_settings.scale_length=.01
bpy.context.view_layer.update();activate(arm);mesh.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'RepairBot_Cm.fbx'),use_selection=True,
    object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,
    use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
report['fbx_sha256']=hashlib.sha256((OUT/'RepairBot_Cm.fbx').read_bytes()).hexdigest()
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
(OUT/'repair-bot-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('REPAIR_BOT_AUTHORED',json.dumps({k:report[k] for k in ['rig_bones','triangles','mesh_vertices','mesh_dimensions_m']}),flush=True)

if '--render' in sys.argv:
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'RepairBot.blend'),use_scripts=False)
    scene=bpy.context.scene;scene.cycles.samples=48
    scene.render.resolution_x=1400;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('RepairBot_Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.16,.18,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.01))
    floor=bpy.context.object;floor.data.materials.append(material('Studio_floor',(.025,.034,.038),.8,0))
    for name,location,energy,size,color in [('Key',(-3,-4,5),650,4,(1,.86,.69)),('Fill',(3,-2,3),350,3,(.58,.79,1)),('Rim',(1,3,4),850,3,(.81,.93,1))]:
        data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=size;data.color=color
        obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=location
        obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    camera_data=bpy.data.cameras.new('Robot_review_camera');camera=bpy.data.objects.new('Robot_review_camera',camera_data)
    bpy.context.collection.objects.link(camera);scene.camera=camera;camera_data.lens=65
    for name,location in [('front',(0,-4.7,1.9)),('three-quarter',(-3.2,-4,2.4)),('back',(2.5,4.2,2.1))]:
        camera.location=location;camera.rotation_euler=(Vector((0,0,.94))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/('RepairBot_'+name+'.png'));bpy.ops.render.render(write_still=True)
