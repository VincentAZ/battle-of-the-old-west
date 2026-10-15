"""Build an editable, skinned survivor from CC0 source meshes and clothing.

Blender 5.2: blender -b --factory-startup --disable-autoexec --python scripts/export_survivor.py
Pass -- --render for the short studio preview. Source animation actions are removed.
The FBX contains geometry, skin weights and facial shapes; no Mixamo animation clips.
"""
import bpy
import bmesh
import json
import math
import shutil
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'art/characters/vitruvian/godot_project'
OUT = ROOT / 'art/characters/oldwest_survivor'
TEX = OUT / 'textures'
OUT.mkdir(parents=True, exist_ok=True)
TEX.mkdir(exist_ok=True)
for path in SRC.glob('vit_*.png'):
    target = TEX / path.name
    if not target.exists():
        shutil.copy2(path, target)

bpy.ops.wm.read_factory_settings(use_empty=True)
for name in ['vitruvian_body.glb', 'vitruvian_head.glb']:
    bpy.ops.import_scene.gltf(filepath=str(SRC / name))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.name = 'Survivor_Rig'
for o in list(bpy.data.objects):
    o.animation_data_clear()
    if o.type == 'MESH' and (not o.data.materials or o.name.startswith('Eyeshadow')):
        bpy.data.objects.remove(o, do_unlink=True)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
for bone in arm.pose.bones:
    bone.matrix_basis.identity()
bpy.context.view_layer.update()

HEAD = 'mixamorig:Head'
HIPS = 'mixamorig:Hips'
CHEST = 'mixamorig:Spine2'
material_specs = {}


def image_node(nodes, filename, color=True):
    node = nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(TEX / filename), check_existing=True)
    node.image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return node


def material(name, color=(.15, .15, .15), base=None, normal=None, roughmap=None,
             rough=.75, metal=0.0, tiling=1.0, strength=.45, skin=False, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Specular IOR Level'].default_value = .3
    if skin:
        bsdf.inputs['Subsurface Weight'].default_value = .12
        bsdf.inputs['Subsurface Radius'].default_value = (1, .35, .18)
        bsdf.inputs['Subsurface Scale'].default_value = .015
    uv = nodes.new('ShaderNodeTexCoord')
    scale = nodes.new('ShaderNodeVectorMath')
    scale.operation = 'SCALE'
    scale.inputs[3].default_value = tiling
    links.new(uv.outputs['UV'], scale.inputs[0])
    if base:
        node = image_node(nodes, base)
        links.new(scale.outputs[0], node.inputs['Vector'])
        tint = nodes.new('ShaderNodeMixRGB')
        tint.blend_type = 'MULTIPLY'
        tint.inputs[0].default_value = 1
        tint.inputs[2].default_value = (*color, 1)
        links.new(node.outputs['Color'], tint.inputs[1])
        links.new(tint.outputs[0], bsdf.inputs['Base Color'])
    if roughmap:
        node = image_node(nodes, roughmap, False)
        links.new(scale.outputs[0], node.inputs['Vector'])
        links.new(node.outputs['Color'], bsdf.inputs['Roughness'])
    if normal:
        node = image_node(nodes, normal, False)
        links.new(scale.outputs[0], node.inputs['Vector'])
        nm = nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = strength
        links.new(node.outputs['Color'], nm.inputs['Color'])
        links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    if alpha:
        node = image_node(nodes, alpha, False)
        links.new(scale.outputs[0], node.inputs['Vector'])
        links.new(node.outputs['Color'], bsdf.inputs['Alpha'])
        m.surface_render_method = 'DITHERED'
        m.use_transparency_overlap = False
    material_specs[name] = {'base_color': list(color), 'base_color_texture': base,
        'normal_texture': normal, 'roughness_texture': roughmap, 'roughness': rough,
        'metallic': metal, 'uv_scale': tiling, 'normal_strength': strength,
        'subsurface': skin, 'opacity_texture': alpha, 'normal_convention': 'OpenGL',
        'two_sided': bool(alpha)}
    return m


skin_face = material('M_Survivor_Face', (1, 1, 1), 'vit_face_bc.png', 'vit_face_n.png', 'vit_face_rough.png', strength=.28, skin=True)
skin_body = material('M_Survivor_Skin', (1, 1, 1), 'vit_body_bc.png', 'vit_body_n.png', 'vit_body_rough.png', strength=.24, skin=True)
shirt = material('M_Survivor_WeatheredCloth', (.105, .137, .124), normal='fabric_pattern_05_nor_gl_2k.jpg', roughmap='fabric_pattern_05_rough_2k.jpg', tiling=5, strength=.28)
pants = material('M_Survivor_CargoCanvas', (.115, .088, .057), normal='fabric_pattern_05_nor_gl_2k.jpg', roughmap='fabric_pattern_05_rough_2k.jpg', tiling=6, strength=.22)
leather = material('M_Survivor_WornLeather', (.10, .079, .052), base='leather_red_02_coll2_2k.jpg', normal='leather_red_02_nor_gl_2k.jpg', roughmap='leather_red_02_rough_2k.jpg', tiling=2, strength=.42)
scarf = material('M_Survivor_WovenScarf', (.24, .20, .15), 'fabric_pattern_07_col_1_2k.jpg', 'fabric_pattern_07_nor_gl_2k.jpg', 'fabric_pattern_07_rough_2k.jpg', tiling=3, strength=.28)
steel = material('M_Survivor_OxidizedSteel', (.095, .106, .098), normal='leather_red_02_nor_gl_2k.jpg', rough=.52, metal=.72, tiling=3, strength=.12)
rubber = material('M_Survivor_BootRubber', (.023, .022, .019), rough=.84)
stitchmat = material('M_Survivor_Stitching', (.29, .235, .14), rough=.9)
lens = material('M_Survivor_SmokedLens', (.019, .045, .042), rough=.15, metal=.4)
eye_white = material('M_Survivor_Sclera', (.61, .64, .56), rough=.25)
iris = material('M_Survivor_Iris', (.65, .64, .53), 'vit_iris.png', rough=.3)
eyeback = material('M_Survivor_EyeBack', (.016, .013, .01), rough=.3)
cornea = material('M_Survivor_Cornea', (1, 1, 1), rough=.03)
cbsdf = cornea.node_tree.nodes.get('Principled BSDF')
cbsdf.inputs['Transmission Weight'].default_value = 1
cbsdf.inputs['IOR'].default_value = 1.376
material_specs[cornea.name]['transmission'] = 1
mouth = material('M_Survivor_Mouth', (1, 1, 1), 'vit_mouth.png', rough=.48)
tear = material('M_Survivor_Tearline', (.29, .07, .055), rough=.2)
hairmat = material('M_Survivor_Hair', (.045, .031, .016), 'vit_hair_diffuse.png', 'vit_hair_normal.png', rough=.65, strength=.22, alpha='vit_hair_opacity.png')


def bind(obj, bone=HEAD):
    vg = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
    obj.parent = arm
    mod = obj.modifiers.new('Survivor_Skinning', 'ARMATURE')
    mod.object = arm
    return obj


replacements = {'VitBody': skin_body, 'VitShoes': leather, 'VitSkin': skin_face,
    'VitMouth': mouth, 'VitShirt': shirt, 'VitPants': pants, 'VitSclera': eye_white,
    'VitIris': iris, 'VitEyeBack': eyeback, 'VitCornea2': cornea, 'VitTearline': tear,
    'VitCaruncle': tear}
for obj in list(bpy.data.objects):
    if obj.type != 'MESH':
        continue
    for idx, old in enumerate(obj.data.materials):
        key = old.name.split('.')[0]
        if key in replacements:
            obj.data.materials[idx] = replacements[key]
    if obj.find_armature() is None:
        bind(obj)
    if obj.name.startswith('Eye_'):
        # The Godot source used a shader to open the otherwise full sclera sphere.
        # Open the iris aperture geometrically for a standard UE/Blender material.
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        remove = [face for face in bm.faces if face.material_index == 0
                  and face.calc_center_median().y < -.009
                  and math.hypot(face.calc_center_median().x, face.calc_center_median().z) < .0084]
        bmesh.ops.delete(bm, geom=remove, context='FACES')
        bm.to_mesh(obj.data)
        bm.free()
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    if obj.name == 'Pants':
        obj.name = 'Survivor_CargoTrousers'
    elif obj.name == 'Shirt':
        obj.name = 'Survivor_FieldShirt'
    elif obj.data.shape_keys:
        obj.name = 'Survivor_Face_27Shapes'
    elif obj.name == 'cm_vitruvian':
        obj.name = 'Survivor_Body'

# Bind the existing card groom to the head and reduce it for real-time use.
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(SRC / 'vitruvian_hair_rigged.glb'))
new = set(bpy.data.objects) - before
for obj in list(new):
    if obj.type == 'MESH' and not obj.data.materials:
        # glTF importer may create a hidden custom bone-display mesh.
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    if obj.type == 'MESH':
        obj.parent = None
        obj.modifiers.clear()
        obj.vertex_groups.clear()
        obj.name = 'Survivor_HairCards'
        obj.data.materials.clear()
        obj.data.materials.append(hairmat)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        decimate = obj.modifiers.new('RealtimeHairReduction', 'DECIMATE')
        decimate.ratio = .1
        bpy.ops.object.modifier_apply(modifier=decimate.name)
        bind(obj)
    elif obj.type == 'ARMATURE':
        bpy.data.objects.remove(obj, do_unlink=True)


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def uv_smart(obj):
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=.01)
    bpy.ops.object.mode_set(mode='OBJECT')


def finish(obj, name, mat, bone=HIPS, bevel=0):
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('EdgeWearRadius', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in obj.data.polygons:
        p.use_smooth = True
    uv_smart(obj)
    bind(obj, bone)
    return obj


def box(name, position, dims, mat, bone=HIPS, bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.dimensions = dims
    return finish(obj, name, mat, bone, bevel)


def cylinder(name, position, radius, depth, mat, bone=HIPS, axis=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=depth, location=position)
    obj = bpy.context.object
    if axis:
        obj.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat, bone, .002)


def tube(name, points, radius, mat, bone=CHEST):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    activate(obj)
    bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object, name, mat, bone)


def ribbon(name, points, width, mat, bone=CHEST):
    verts = [(x + offset, y, z) for x, y, z in points for offset in [-width / 2, width / 2]]
    faces = [(i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2) for i in range(len(points) - 1)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    activate(obj)
    solid = obj.modifiers.new('WebbingThickness', 'SOLIDIFY')
    solid.thickness = .004
    bpy.ops.object.modifier_apply(modifier=solid.name)
    return finish(obj, name, mat, bone, .0014)


def loft(name, rings, mat, bone=HIPS, segments=48):
    verts = []
    faces = []
    for z, cx, cy, rx, ry, wave in rings:
        for i in range(segments):
            a = i * 2 * math.pi / segments
            rr = 1 + wave * math.sin(9 * a + z * 27)
            verts.append((cx + rx * math.cos(a) * rr, cy + ry * math.sin(a) * rr, z))
    for row in range(len(rings) - 1):
        for i in range(segments):
            n = row * segments + i
            nn = row * segments + (i + 1) % segments
            faces.append((n, nn, nn + segments, n + segments))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat, bone)


# Wide battered boots with a distinct outsole, welt, ankle body, and lacing.
for side, x in [('Left', .148), ('Right', -.148)]:
    footbone = f'mixamorig:{side}Foot'
    boot = loft(f'Survivor_{side}_Boot', [
        (.002, x, -.045, .066, .151, 0), (.018, x, -.045, .070, .155, 0),
        (.05, x, -.036, .067, .143, .012), (.085, x, -.015, .062, .123, .015),
        (.115, x, .025, .058, .086, .018), (.17, x, .043, .059, .069, .027),
        (.215, x, .043, .057, .068, .012)], leather, footbone)
    loft(f'Survivor_{side}_Outsole', [(-.012,x,-.045,.071,.155,0),(.006,x,-.045,.071,.155,0)], rubber, footbone)
    for z in [.12, .145, .17, .193]:
        tube(f'{side}_Boot_Lace_{z}', [(x-.035,-.031,z),(x+.033,-.033,z+.009)], .002, stitchmat, footbone)
    for y in [-.16, -.13, -.10, -.07, -.03, .01, .05]:
        box(f'{side}_Tread', (x,y,-.013),(.10,.017,.014),rubber,footbone,.003)

# A worn utility belt follows the body rather than floating at a single plane.
loft('Survivor_UtilityBelt', [(.982,0,.021,.184,.138,.005),(1.032,0,.021,.181,.137,.005)], leather)
box('Survivor_BeltBuckle', (0,-.124,1.008),(.055,.009,.038),steel,bevel=.003)
for x,z in [(-.138,.948),(.143,.943)]:
    box('Survivor_BeltPouch', (x,-.11,z),(.084,.074,.12),leather,bevel=.014)
    box('Survivor_PouchFlap', (x,-.153,z+.025),(.087,.012,.065),pants,bevel=.007)
    cylinder('Survivor_PouchStud',(x,-.163,z+.02),.005,.003,steel,axis=(0,1,0))
for side, x in [('Left', .176), ('Right', -.176)]:
    leg=f'mixamorig:{side}UpLeg'
    box(f'Survivor_{side}_CargoPocket',(x,.016,.75),(.076,.119,.17),pants,leg,.019)
    box(f'Survivor_{side}_PocketFlap',(x*1.17,.016,.79),(.014,.13,.068),leather,leg,.005)

# Layered cloth around the neck; irregular rings produce actual folds.
loft('Survivor_DustScarf',[(1.393,0,.02,.121,.089,.025),(1.423,0,.029,.126,.091,.075),
    (1.45,0,.031,.112,.085,.085),(1.477,0,.04,.102,.077,.07),(1.506,0,.04,.091,.068,.04)],scarf,CHEST)
for i,z in enumerate([1.428,1.447,1.469]):
    points=[]
    for k in range(65):
        a=2*math.pi*k/64
        points.append((.112*math.cos(a),.027+.084*math.sin(a),z+.007*math.sin(3*a+i)))
    tube('Survivor_ScarfFold',points,.005,scarf,CHEST)

# Reinforced field harness: stitched shoulder straps and small armour plate.
for side in [-1,1]:
    points=[(side*.112,-.108,1.056),(side*.101,-.155,1.18),(side*.083,-.146,1.32),
            (side*.112,-.084,1.426),(side*.148,.016,1.46),(side*.132,.132,1.37)]
    ribbon('Survivor_HarnessWebbing',points,.037,leather,CHEST)
    tube('Survivor_HarnessSeam',[(x+side*.013,y-.014,z) for x,y,z in points[:4]],.0012,stitchmat,CHEST)
    box('Survivor_HarnessFastener',(side*.101,-.172,1.232),(.045,.014,.034),steel,CHEST,.003)
box('Survivor_ChestPatch',(-.076,-.164,1.315),(.054,.011,.03),pants,CHEST,.002)
plate=box('Survivor_LeftShoulderPlate',(.224,.003,1.395),(.144,.20,.045),steel,'mixamorig:LeftArm',.023)
plate.rotation_euler.y=-.4
for y in [-.065,.063]:
    cylinder('Survivor_ArmourRivet',(.21,y,1.424),.006,.006,steel,'mixamorig:LeftArm')

# Metal water bottle and rolled bedding provide a survivor silhouette.
can=cylinder('Survivor_Canteen',(.225,.10,.978),.056,.143,steel)
can.scale.y=.57
cylinder('Survivor_CanteenCap',(.225,.10,1.06),.025,.025,leather)
roll=cylinder('Survivor_Bedroll',(0,.206,1.12),.076,.31,pants,CHEST,axis=(1,0,0))
for x in [-.099,.099]:
    points=[(x,.206+.079*math.cos(a),1.12+.079*math.sin(a)) for a in [k*math.pi/24 for k in range(49)]]
    tube('Survivor_BedrollStrap',points,.009,leather,CHEST)

# Dust goggles rest above the eyes; proper glass and frames replace toy accents.
for x in [-.043,.043]:
    frame=box('Survivor_GoggleFrame',(x,-.074,1.693),(.077,.033,.043),leather,HEAD,.013)
    pane=box('Survivor_GoggleLens',(x,-.093,1.693),(.059,.005,.029),lens,HEAD,.01)
tube('Survivor_GoggleBridge',[(-.009,-.091,1.697),(0,-.096,1.701),(.009,-.091,1.697)],.006,steel,HEAD)
strap_points=[]
for i in range(65):
    a=2*math.pi*i/64
    strap_points.append((.098*math.cos(a),.018+.113*math.sin(a),1.688+.007*math.sin(2*a)))
tube('Survivor_GoggleStrap',strap_points,.004,leather,HEAD)

# Bake surface colour variation, woven normal detail and roughness to ordinary
# texture maps, so native Unreal materials reproduce the Blender appearance.
# These are material bakes from native 3D shaders, not a painted preview image.
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
if '--render' in sys.argv:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    for device in prefs.get_devices_for_type('OPTIX'):
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
for mat in [shirt, pants, leather, steel]:
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    uv = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 7.3
    noise.inputs['Detail'].default_value = 5
    noise.inputs['Roughness'].default_value = .75
    links.new(uv.outputs['UV'], noise.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .24
    ramp.color_ramp.elements[0].color = (.10, .08, .05, 1)
    ramp.color_ramp.elements[1].position = .72
    ramp.color_ramp.elements[1].color = (.85, .79, .62, 1)
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    original = bsdf.inputs['Base Color'].links[0].from_socket if bsdf.inputs['Base Color'].is_linked else None
    multiply = nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = .83
    if original:
        links.new(original, multiply.inputs[1])
    else:
        multiply.inputs[1].default_value = bsdf.inputs['Base Color'].default_value
    links.new(ramp.outputs[0], multiply.inputs[2])
    links.new(multiply.outputs[0], bsdf.inputs['Base Color'])
    bpy.ops.mesh.primitive_plane_add(size=2, location=(5, 0, 0))
    bake_obj = bpy.context.object
    bake_obj.name = 'Temporary_MaterialBake'
    bake_obj.data.materials.append(mat)
    activate(bake_obj)
    baked = {}
    for channel in ['BaseColor', 'Normal', 'Roughness']:
        filename = mat.name.replace('M_', 'T_') + '_' + channel + '.png'
        img = bpy.data.images.new(filename, width=2048, height=2048, alpha=False)
        img.colorspace_settings.name = 'sRGB' if channel == 'BaseColor' else 'Non-Color'
        target = nodes.new('ShaderNodeTexImage')
        target.image = img
        nodes.active = target
        if channel != 'Normal':
            emit = nodes.new('ShaderNodeEmission')
            src = bsdf.inputs['Base Color' if channel == 'BaseColor' else 'Roughness']
            if src.is_linked:
                links.new(src.links[0].from_socket, emit.inputs[0])
            else:
                val = src.default_value
                emit.inputs[0].default_value = (*val[:3], 1) if channel == 'BaseColor' else (val,val,val,1)
            links.new(emit.outputs[0], output.inputs['Surface'])
            bpy.ops.object.bake(type='EMIT', margin=4, use_clear=True)
            links.new(bsdf.outputs[0], output.inputs['Surface'])
            nodes.remove(emit)
        else:
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=4, use_clear=True)
        img.filepath_raw = str(TEX / filename)
        img.file_format = 'PNG'
        img.save()
        baked[channel] = filename
        nodes.remove(target)
    bpy.data.objects.remove(bake_obj, do_unlink=True)
    # Replace the procedural graph by the same three images Unreal will import.
    for socket_name in ['Base Color', 'Normal', 'Roughness']:
        for link in list(bsdf.inputs[socket_name].links):
            links.remove(link)
    for channel, socket_name in [('BaseColor', 'Base Color'), ('Roughness', 'Roughness')]:
        node = image_node(nodes, baked[channel], channel == 'BaseColor')
        links.new(node.outputs['Color'], bsdf.inputs[socket_name])
    normal = image_node(nodes, baked['Normal'], False)
    normalmap = nodes.new('ShaderNodeNormalMap')
    links.new(normal.outputs['Color'], normalmap.inputs['Color'])
    links.new(normalmap.outputs[0], bsdf.inputs['Normal'])
    material_specs[mat.name].update(base_color=[1,1,1], base_color_texture=baked['BaseColor'],
        normal_texture=baked['Normal'], roughness_texture=baked['Roughness'],
        uv_scale=1, normal_strength=1)
    print('MATERIAL_BAKED', mat.name, flush=True)

# Only skinned character geometry is exported. Apply transforms consistently.
meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
for obj in meshes:
    activate(obj)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for polygon in obj.data.polygons:
        polygon.use_smooth=True
    # glTF bodies have redundant alternate UV maps; keep the exported principal UV.
    for uv in list(obj.data.uv_layers)[1:]:
        obj.data.uv_layers.remove(uv)
    if obj.data.uv_layers:
        obj.data.uv_layers[0].name='UVMap'

# A non-deforming root gives Unreal a single skeleton root at ground level.
activate(arm)
bpy.ops.object.mode_set(mode='EDIT')
root=arm.data.edit_bones.new('root')
root.head=(0,0,0)
root.tail=(0,0,.08)
root.use_deform=False
arm.data.edit_bones[HIPS].parent=root
bpy.ops.object.mode_set(mode='OBJECT')

scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
scene.render.fps=30
scene.frame_start=1
scene.frame_end=90
scene.frame_set(1)
bpy.context.view_layer.update()

# Saving source is deliberately before the optional display pose below.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Survivor_A.blend'))
activate(arm)
for obj in meshes:
    obj.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'Survivor_A.fbx'),use_selection=True,
    object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,
    use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
    apply_unit_scale=True,axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')

report={'name':'Survivor_A','status':'art candidate; gameplay retarget validation required',
    'source_mesh_license':'CC0-1.0','source_animation_clips_included':False,
    'forward_axis':'-Y (Blender)','up_axis':'Z','units':'meters',
    'skeleton':{'bones':len(arm.data.bones),'root':'root','pelvis':HIPS,
        'naming':'Mixamo-compatible body names with root added',
        'requires_retarget_from':'Epic UE5 Manny; different rest pose and bone hierarchy'},
    'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),
        'material_slots':[m.name for m in o.data.materials],
        'vertex_groups':len(o.vertex_groups),
        'shape_keys':[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else []} for o in meshes],
    'materials':material_specs,
    'texture_root':str(TEX),
    'textures':[{'file':img.filepath,'resolution':list(img.size)} for img in bpy.data.images if img.source=='FILE']}
(OUT/'survivor-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('SURVIVOR_EXPORT',len(meshes),'meshes',sum(r['triangles'] for r in report['meshes']),'triangles',flush=True)

if '--render' in sys.argv:
    # This is a short lookdev image, separate from the exported neutral pose.
    scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    for device in prefs.get_devices_for_type('OPTIX'):
        device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1400
    scene.render.resolution_y=1800
    scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('Survivor_Studio')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.095,.111,.125,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.029))
    plane=bpy.context.object
    plane.data.materials.append(material('StudioFloor',(.047,.050,.051),rough=.88))
    def area(name,location,energy,color,size,target=(0,0,1.1)):
        data=bpy.data.lights.new(name,'AREA');obj=bpy.data.objects.new(name,data)
        scene.collection.objects.link(obj);obj.location=location
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
        data.energy=energy;data.color=color;data.shape='DISK';data.size=size
    area('Warm_Key',(-2.7,-3.8,3.5),470,(1,.84,.68),3)
    area('Cool_Fill',(2.8,-1.6,1.8),190,(.65,.77,1),3)
    area('Rim',(1.0,2.0,2.8),650,(1,.79,.48),2)
    camdata=bpy.data.cameras.new('Character_Preview')
    cam=bpy.data.objects.new('Character_Preview',camdata)
    scene.collection.objects.link(cam)
    cam.location=(2.3,-5.2,1.62)
    cam.rotation_euler=(Vector((0,0,.91))-cam.location).to_track_quat('-Z','Y').to_euler()
    camdata.type='ORTHO';camdata.ortho_scale=2.14
    scene.camera=cam
    scene.view_settings.view_transform='AgX'
    scene.render.image_settings.file_format='PNG'
    scene.render.filepath=str(OUT/'Survivor_A_Preview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Survivor_A.blend'))
    bpy.ops.render.render(write_still=True)
    print('SURVIVOR_PREVIEW_COMPLETE',flush=True)
