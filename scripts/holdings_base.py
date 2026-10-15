"""Build the irregular, setting-specific ground base for one Western Holding in Mixar.

Run with Mixar --background --factory-startup --python-exit-code 1
    --python scripts/holdings_base.py -- --holding HOLDING.json --review DIR --output DIR
    [--strip-baked-slab] [--samples N]

Every holding gets its own organic outline (seeded from its slug, stretched to
the structure's footprint) instead of a shared rectangle, and a surface that
reflects its documented setting: water and a mud bank for River, prairie for
Range, a packed street for Town, scree for Mountains, ballast for Rail and
forest litter for Timber. Colours come from base-palettes.json, whose entries
cite the setting evidence. The edge feathers into the battlefield sand so the
base reads as ground, not a plinth. Water is a separate object so Unreal can
give it a moving surface. Static only: no rig, no keyframes.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
PALETTES = ROOT / 'art/western/holdings/base-palettes.json'
BATTLEFIELD_SAND = (0.41, 0.33, 0.23)  # mean albedo of the board's dirt texture; previews only, Unreal fades to the real texture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def srgb(c):
    return tuple(((x + .055) / 1.055) ** 2.4 if x > .04045 else x / 12.92 for x in c)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


class Outline:
    """A closed, smooth, irregular radius function around the structure's footprint."""

    def __init__(self, rng, half_x, half_y, margin, wobble, lobes=(2, 3, 5, 7)):
        self.hx, self.hy, self.margin = half_x, half_y, margin
        self.terms = [(k, rng.uniform(.25, 1) * wobble / k ** .6, rng.uniform(0, math.tau)) for k in lobes]

    def radius(self, angle):
        c, s = abs(math.cos(angle)), abs(math.sin(angle))
        # Distance to a rounded rectangle (superellipse, n=4) that hugs the structure.
        box = (c ** 4 / self.hx ** 4 + s ** 4 / self.hy ** 4) ** -.25
        noise = sum(a * math.sin(k * angle + p) for k, a, p in self.terms)
        return box + self.margin * (1 + noise)


def ground_mesh(name, outline, rng, palette, rings=14, segments=96, relief=.04, rim_drop=.05, bare_earth=None):
    def earth_weight(x, y):
        # Zero-sized clearings allow a stair approach without painting a spot
        # at the mesh centre, which otherwise produces a radial colour fan.
        patch = (max(abs(x)-bare_earth['half_width_m'], abs(y)-bare_earth['half_depth_m'])
                 if bare_earth['half_width_m'] > 0 and bare_earth['half_depth_m'] > 0 else math.inf)
        approach = max(abs(x-bare_earth.get('approach_center_x_m', 0))-bare_earth['approach_width_m']/2,
                       -y-bare_earth['half_depth_m']-bare_earth['approach_length_m'], y)
        return 1-min(1, max(0, min(patch, approach)/bare_earth['feather_m']))

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    colour = bm.loops.layers.color.new('Col')
    centre = bm.verts.new((0, 0, .004 + rim_drop))
    grid, tints = [], {}
    phase = [rng.uniform(0, math.tau) for _ in range(6)]
    for r in range(1, rings + 1):
        t = r / rings
        row = []
        for s in range(segments):
            a = s / segments * math.tau
            radius = outline.radius(a) * t
            x, y = math.cos(a) * radius, math.sin(a) * radius
            # Gentle relief, flat under the structure, sloping into the board at the rim.
            bump = relief * (math.sin(x * 1.7 + phase[0]) * math.cos(y * 1.3 + phase[1])
                             + .5 * math.sin(x * 4.1 + y * 3.3 + phase[2]))
            inner = min(1, max(0, (t - .55) / .45))
            # Raised a few centimetres inside so the structure's footing beds into it; the rim meets the board.
            z = .004 + rim_drop * (1 - inner ** 2.5) + bump * inner * (1 - inner)
            v = bm.verts.new((x, y, z))
            row.append(v)
            grain = .5 + .5 * math.sin(x * 2.3 + phase[3]) * math.sin(y * 2.9 + phase[4])
            base = lerp(palette['ground'], palette['ground_alt'], grain * rng.uniform(.6, 1))
            if palette.get('path') and abs(y + outline.hy * .1) < .45 * (1 + .3 * math.sin(x * 2 + phase[5])) and y < 0:
                base = lerp(base, palette['path'], .7)
            if bare_earth:
                # Optional documented camp clearance; front is -Y in the review.
                base = lerp(base, palette['earth'], earth_weight(x, y))
            # Vertex alpha carries the rim fade: Unreal blends into the board's own dirt texture.
            tints[v] = (*base, 1 - max(0, (t - .82) / .18) ** 1.5)
        grid.append(row)
    centre_tint = lerp(palette['ground'], palette['earth'], earth_weight(0, 0)) if bare_earth else palette['ground']
    tints[centre] = (*centre_tint, 1.)
    for s in range(segments):
        n = (s + 1) % segments
        bm.faces.new((centre, grid[0][s], grid[0][n]))
        for r in range(rings - 1):
            bm.faces.new((grid[r][s], grid[r + 1][s], grid[r + 1][n], grid[r][n]))
    for face in bm.faces:
        for loop in face.loops:
            loop[colour] = tints[loop.vert]  # sRGB bytes with the rim fade in alpha
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def vertex_colour_material(name, roughness=.95):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = nodes['Principled BSDF']
    attribute = nodes.new('ShaderNodeVertexColor')
    attribute.layer_name = 'Col'
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (*srgb(BATTLEFIELD_SAND), 1)
    links.new(attribute.outputs['Alpha'], mix.inputs['Factor'])
    links.new(attribute.outputs['Color'], mix.inputs['B'])
    links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = roughness
    return material


def water_material(palette):
    material = bpy.data.materials.new('M_Holding_Water')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*srgb(palette['water']), 1)
    bsdf.inputs['Roughness'].default_value = .06
    bsdf.inputs['Coat Weight'].default_value = .4
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 14
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .18
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return material


def scatter(collection_name, rng, outline, kind, count, palette, keep_out, size=1., blade_width=None, blade_count=(7, 12), clear_approach=None):
    """Low-poly natural scatter (grass tufts, stones, reeds) kept off the structure's footprint."""
    objects = []
    hx, hy = keep_out
    for i in range(count * 6):
        if len(objects) >= count:
            break
        a = rng.uniform(0, math.tau)
        t = rng.uniform(.35, .92) ** .7
        r = outline.radius(a) * t
        x, y = math.cos(a) * r, math.sin(a) * r
        if abs(x) < hx and abs(y) < hy:
            continue
        if clear_approach and y < 0:
            if (abs(x-clear_approach.get('approach_center_x_m', 0)) < clear_approach['approach_width_m']/2 + .08
                    and -y < clear_approach['half_depth_m'] + clear_approach['approach_length_m']):
                continue
        if kind == 'stone':
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size * rng.uniform(.08, .28), location=(x, y, 0))
            ob = bpy.context.object
            ob.scale = (rng.uniform(.8, 1.4), rng.uniform(.8, 1.3), rng.uniform(.35, .7))
            tint = lerp(palette['stone'], palette['stone_alt'], rng.random())
        else:  # tuft or reed: a splayed clump of thin blades, not a cone
            height = size * (rng.uniform(.28, .55) if kind == 'tuft' else rng.uniform(.5, .9))
            blades = []
            for _ in range(rng.randint(*blade_count)):
                h = height * rng.uniform(.6, 1)
                radius = blade_width * .5 if blade_width is not None else h * .08
                bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=radius, depth=h, location=(x, y, h / 2))
                blade = bpy.context.object
                if blade_width is not None:
                    blade.scale.y = .15  # narrow flattened leaf, not a broad cone
                blade.rotation_euler = (rng.uniform(-.45, .45), rng.uniform(-.45, .45), rng.uniform(0, math.tau))
                blade.location.x += rng.uniform(-.05, .05)
                blade.location.y += rng.uniform(-.05, .05)
                blades.append(blade)
            bpy.ops.object.select_all(action='DESELECT')
            for blade in blades:
                blade.select_set(True)
            bpy.context.view_layer.objects.active = blades[0]
            bpy.ops.object.join()
            ob = bpy.context.object
            tint = lerp(palette['grass'], palette['grass_alt'], rng.random())
        if kind == 'stone':
            ob.rotation_euler.z = rng.uniform(0, math.tau)
        ob.color = (*srgb(tint), 1)
        ob.name = f'{collection_name}_{kind}_{i:02d}'
        objects.append(ob)
    return objects


def join(objects, name, colour_layer=True):
    """Join scatter into one mesh, baking each object's tint into vertex colours."""
    if not objects:
        return None
    for ob in objects:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        layer = ob.data.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        for item in layer.data:
            item.color = ob.color
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.object
    joined.name = name
    return joined


def strip_slab(holding, height):
    """Delete the thin generated ground sheet: near-flat faces in the bottom few centimetres."""
    bm = bmesh.new()
    bm.from_mesh(holding.data)
    limit = .025 * height + .02
    doomed = [f for f in bm.faces if all(v.co.z < limit for v in f.verts) and abs(f.normal.z) > .5]
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(holding.data)
    bm.free()
    return len(doomed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--holding', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True, help='Validated review directory with *-Review.blend')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--strip-baked-slab', action='store_true',
                        help='Prototype only: remove the v001 generated ground sheet from the copied mesh')
    parser.add_argument('--samples', type=int, default=32)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use the installed Mixar executable'
    info = json.loads(args.holding.read_text())
    palettes = json.loads(PALETTES.read_text())
    setting = palettes['settings'][info['setting']]
    palette = {k: tuple(v) for k, v in setting['colors'].items()}
    # A holding may carry documented ground of its own (the prize ring's turf floor).
    override = info.get('base_colors', {})
    # A natural landform can explicitly omit the default access-path stripe.
    assert all(v is not None or k == 'path' for k, v in override.get('colors', {}).items())
    palette.update({k: tuple(v) if v is not None else None for k, v in override.get('colors', {}).items()})
    project = next(args.review.glob('*-Review.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(project))  # read only; never saved back
    studio_floor = bpy.data.objects.get('Review_only_ground')
    if studio_floor:  # sit the studio floor just under the base rim
        studio_floor.location.z = -.01
    holding = next(ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and ob.name.endswith('_Holding_Review'))
    removed = strip_slab(holding, holding.dimensions.z) if args.strip_baked_slab else 0
    points = [holding.matrix_world @ v.co for v in holding.data.vertices]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    hx, hy = (hi.x - lo.x) / 2, (hi.y - lo.y) / 2
    rng = random.Random(info['slug'])
    shape = setting['shape']
    outline = Outline(rng, hx, hy, margin=shape['margin_m'], wobble=shape['wobble'])
    ground = ground_mesh('Holding_Base_Ground', outline, rng, palette, relief=shape['relief_m'],
                         bare_earth=info.get('base_bare_earth'))
    ground.data.materials.append(vertex_colour_material('M_Holding_Base'))
    extras = []
    water = None
    # Water placement is per holding: a boat sits in the river ('surround'); the
    # Hubbell post has its wash along the back of the site ('behind'); 'none' keeps
    # a river-setting holding dry.
    water_mode = info.get('base_water', 'surround' if setting.get('water') else 'none')
    inner = None
    if water_mode != 'none':
        inner = Outline(rng, hx * 1.02, hy * 1.1, margin=shape['margin_m'] * (.55 if water_mode == 'surround' else .8),
                        wobble=shape['wobble'] * .7)

    def in_water(x, y):
        if inner is None or math.hypot(x, y) >= inner.radius(math.atan2(y, x)) * .97:
            return False
        return water_mode == 'surround' or y > hy + .3 + .12 * math.sin(x * 1.3)

    if inner is not None:
        water = ground_mesh('Holding_Base_Water', inner, rng, {'ground': palette['water'], 'ground_alt': palette['water_alt']},
                            rings=6, segments=96, relief=0, rim_drop=0)
        if water_mode == 'behind':
            bm = bmesh.new()
            bm.from_mesh(water.data)
            dry = [v for v in bm.verts if not in_water(v.co.x, v.co.y) and v.co.xy.length < inner.radius(math.atan2(v.co.y, v.co.x)) * .97]
            bmesh.ops.delete(bm, geom=dry, context='VERTS')
            bm.to_mesh(water.data)
            bm.free()
        water.location.z = .05 + setting['water']['level_fraction'] * (hi.z - lo.z)
        water.data.materials.append(water_material(palette))
        bm = bmesh.new()
        bm.from_mesh(ground.data)
        for v in bm.verts:
            if in_water(v.co.x, v.co.y):
                v.co.z = .01  # river bed sits just under the water line, above the board
        bm.to_mesh(ground.data)
        bm.free()
    for kind, count in info.get('base_scatter', setting.get('scatter', {})).items():
        part = join(scatter('Holding_Base', rng, outline, kind, count, palette, (hx * 1.05, hy * 1.05),
                            size=info.get('base_scatter_size', {}).get(kind, setting.get('scatter_size', {}).get(kind, 1.)),
                            blade_width=info.get('base_blade_width_m', {}).get(kind),
                            blade_count=info.get('base_blade_count', {}).get(kind, (7, 12)),
                            clear_approach=info.get('base_bare_earth') if info.get('base_clear_approach') else None),
                    'Holding_Base_' + kind.title())
        if part:
            part.data.materials.append(bpy.data.materials['M_Holding_Base'])
            extras.append(part)
    if water:  # reeds and stones only on the bank, never floating on the water
        for part in extras:
            bm = bmesh.new()
            bm.from_mesh(part.data)
            sunk = [v for v in bm.verts if in_water(v.co.x, v.co.y)]
            bmesh.ops.delete(bm, geom=sunk, context='VERTS')
            bm.to_mesh(part.data)
            bm.free()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.cycles.samples = args.samples
    # Thin structures can have bases much wider than the source footprint.
    # Frame the actual combined geometry instead of enlarging by a fixed ratio.
    framed_objects = [holding, ground] + extras + ([water] if water else [])
    framed_points = [ob.matrix_world @ vertex.co for ob in framed_objects for vertex in ob.data.vertices]
    aspect = scene.render.resolution_y / scene.render.resolution_x
    camera_frames = {}
    for name in ('three-quarter', 'game-camera', 'overhead'):
        camera = bpy.data.objects.get('Review_' + name)
        if not camera:
            camera = next((ob for ob in scene.objects if ob.type == 'CAMERA'
                           and ob.name.startswith('Review_' + name + '.')), None)
            if camera:
                camera.name = 'Review_' + name
        if not camera:
            continue
        right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
        up = camera.rotation_euler.to_quaternion() @ Vector((0, 1, 0))
        xs = [(p-camera.location).dot(right) for p in framed_points]
        ys = [(p-camera.location).dot(up) for p in framed_points]
        width, height = max(xs)-min(xs), max(ys)-min(ys)
        camera.location += right*((max(xs)+min(xs))/2) + up*((max(ys)+min(ys))/2)
        camera.data.ortho_scale = 1.12 * max(width, height/aspect)
        camera_frames[name] = {'projected_extent_m': [width, height], 'ortho_width_m': camera.data.ortho_scale}
        scene.camera = camera
        scene.render.filepath = str(out / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    base_objects = [ground] + extras + ([water] if water else [])
    triangles = 0
    for ob in base_objects:
        ob.data.calc_loop_triangles()
        triangles += len(ob.data.loop_triangles)
    record = {'slug': info['slug'], 'setting': info['setting'], 'palette_source': str(PALETTES.relative_to(ROOT)),
              'palette_sha256': digest(PALETTES), 'seed': info['slug'], 'baked_slab_faces_removed': removed,
              'outline_extent_m': [2 * outline.radius(0), 2 * outline.radius(math.pi / 2)],
              'base_triangles': triangles, 'objects': [ob.name for ob in base_objects],
              'water_surface': bool(water), 'water_mode': water_mode, 'animated': False,
              'camera_frames': camera_frames,
              'scope': 'Static base prototype; Unreal water motion is a material effect added at integration'}
    (out / 'base.json').write_text(json.dumps(record, indent=2) + '\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (info['slug'] + '-Base.blend')))
    print('HOLDING_BASE_READY', json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
