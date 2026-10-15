"""Shape the existing textured card groom without baking away its strand mask.

Hair stays a separate skinned mesh/material. Joining it into the opaque outfit
atlas discards the transparency that gives the groom its fine silhouette.
"""
import hashlib

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

import author_survivor_variants as a


def author_hair(material, long=False, sidecut=False):
    # The base character's 90% reduction collapsed thin strips into visible
    # splinters. Recover the source groom and keep half its triangles for close
    # shots; the original rig, source file and base asset remain untouched.
    bpy.data.objects.remove(bpy.data.objects['Survivor_HairCards'], do_unlink=True)
    source = a.ROOT / 'art/characters/vitruvian/godot_project/vitruvian_hair_rigged.glb'
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(source))
    added = set(bpy.data.objects) - before
    meshes = [obj for obj in added if obj.type == 'MESH' and obj.data.materials]
    assert len(meshes) == 1
    hair = meshes[0]
    transform = hair.matrix_world.copy()
    hair.parent = None
    hair.matrix_world = transform
    hair.modifiers.clear()
    hair.vertex_groups.clear()
    for obj in added - {hair}:
        bpy.data.objects.remove(obj, do_unlink=True)
    a.activate(hair)
    reduction = hair.modifiers.new('HairCardReduction', 'DECIMATE')
    reduction.ratio = .5
    bpy.ops.object.modifier_apply(modifier=reduction.name)
    hair.name = material.name + '_HairCards'
    bm = bmesh.new()
    bm.from_mesh(hair.data)
    if sidecut:
        # Keep textured triangles on the long side of the undercut. Existing
        # fine strands make the part less mechanical than a solid cap.
        discarded = [face for face in bm.faces if any(vertex.co.x < .008 for vertex in face.verts)]
        bmesh.ops.delete(bm, geom=discarded, context='FACES')
    # The original decimation leaves many vertices without any rendered face.
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(hair.data)
    bm.free()
    face = bpy.data.objects['Survivor_Face_27Shapes']
    scalp = BVHTree.FromPolygons([face.matrix_world @ v.co for v in face.data.vertices],
                                 [list(p.vertices) for p in face.data.polygons])
    longitudinal = {}
    uv = hair.data.uv_layers.active
    for loop in hair.data.loops:
        longitudinal[loop.vertex_index] = max(longitudinal.get(loop.vertex_index, 0), uv.data[loop.index].uv.y)
    roots_fitted = 0
    for vertex in hair.data.vertices:
        blend = max(0., min(1., (longitudinal.get(vertex.index, 0) - .55) / .45))
        if blend <= 0:
            continue
        hit, normal, _, distance = scalp.find_nearest(vertex.co)
        if hit is not None and distance < .05:
            vertex.co = vertex.co.lerp(hit + normal * .0015, blend * blend * (3 - 2 * blend))
            roots_fitted += 1
    hair.vertex_groups.new(name=a.HEAD).add(list(range(len(hair.data.vertices))), 1, 'REPLACE')
    hair.parent = a.arm
    skin = hair.modifiers.new('Preserved_survivor_skin', 'ARMATURE')
    skin.object = a.arm
    for vertex in hair.data.vertices:
        p = vertex.co
        # Preserve crown/forehead; lengthen the existing side/back layers.
        if long and (abs(p.x) > .068 or p.y > .045):
            fall = max(0., 1.68 - p.z)
            p.z -= .78 * fall
            p.x *= 1 + min(.12, fall * .8)
            p.y += min(.015, fall * .12)
    hair.data.update()
    for polygon in hair.data.polygons:
        polygon.use_smooth = True
    color = tuple(float(v) * .72 for v in material.diffuse_color[:3])
    name = material.name + '_Hair'
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    mat.surface_render_method = 'DITHERED'
    mat.use_transparency_overlap = False
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .78
    shader.inputs['Specular IOR Level'].default_value = .18
    shader.inputs['Metallic'].default_value = 0
    texture = a.ROOT / 'art/characters/oldwest_survivor/textures/vit_hair_opacity.png'
    strands = nodes.new('ShaderNodeTexImage')
    strands.image = bpy.data.images.load(str(texture), check_existing=True)
    strands.image.colorspace_settings.name = 'Non-Color'
    diffuse_path = texture.with_name('vit_hair_diffuse.png')
    diffuse = nodes.new('ShaderNodeTexImage')
    diffuse.image = bpy.data.images.load(str(diffuse_path), check_existing=True)
    diffuse.image.colorspace_settings.name = 'sRGB'
    luminance = nodes.new('ShaderNodeRGBToBW')
    links.new(diffuse.outputs['Color'], luminance.inputs[0])
    variation = nodes.new('ShaderNodeMapRange')
    variation.inputs['From Max'].default_value = .024
    variation.inputs['To Min'].default_value = 0
    variation.inputs['To Max'].default_value = 1
    links.new(luminance.outputs[0], variation.inputs['Value'])
    tint = nodes.new('ShaderNodeMixRGB')
    tint.inputs[1].default_value = (*(v * .35 for v in color), 1)
    tint.inputs[2].default_value = (*color, 1)
    links.new(variation.outputs[0], tint.inputs[0])
    links.new(tint.outputs[0], shader.inputs['Base Color'])
    coord = nodes.new('ShaderNodeTexCoord')
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord.outputs['UV'], separate.inputs[0])
    root_fade = nodes.new('ShaderNodeMapRange')
    root_fade.inputs['From Min'].default_value = .95
    root_fade.inputs['From Max'].default_value = 1
    root_fade.inputs['To Min'].default_value = 1
    root_fade.inputs['To Max'].default_value = 0
    links.new(separate.outputs['Y'], root_fade.inputs['Value'])
    opacity = nodes.new('ShaderNodeMath')
    opacity.operation = 'MULTIPLY'
    links.new(strands.outputs['Color'], opacity.inputs[0])
    links.new(root_fade.outputs[0], opacity.inputs[1])
    links.new(opacity.outputs[0], shader.inputs['Alpha'])
    hair.data.materials.clear()
    hair.data.materials.append(mat)
    assert hair.find_armature() == a.arm
    assert all(abs(sum(g.weight for g in v.groups) - 1) < .001 for v in hair.data.vertices)
    a.specs[name] = {
        'kind': 'masked_hair', 'base': color, 'roughness': .78, 'specular': .18,
        'strand_shadow': .35, 'opacity_clip': .33,
        'opacity_texture': str(texture),
        'opacity_sha256': hashlib.sha256(texture.read_bytes()).hexdigest(),
        'diffuse_texture': str(diffuse_path),
        'diffuse_sha256': hashlib.sha256(diffuse_path.read_bytes()).hexdigest(),
        'diffuse_luminance_max': .024,
        'root_fade_start': .95, 'scalp_fitted_vertices': roots_fitted,
        'long': long, 'sidecut': sidecut,
        'source_groom': str(source), 'source_groom_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'reduction_ratio': .5,
    }
    hair['hair_material_preserves_strand_mask'] = True
    return hair
