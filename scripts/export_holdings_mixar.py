"""Export one reviewed Holding to an Unreal-ready FBX and texture set.

Run with Mixar --background --factory-startup --python-exit-code 1
    --python scripts/export_holdings_mixar.py -- SLUG

Reads the static review project without saving it. The copy is turned 180
degrees about Z so its -Y Blender front lands on the camp's -Y Unreal front
(Blender -Y imports as Unreal +Y). Units: metres in Blender, centimetres in FBX.

When the holding has a setting base (review-v002 and later, built by
holdings_base.py) the same turn is applied to SM_HoldingBase_<Name> (ground and
scatter, vertex coloured) and SM_HoldingWater_<Name> (river water), which share
the holding's origin. A seamless ripple normal map for the moving water is
written once per game directory.
"""
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import REVIEW, HOLDINGS_SET  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'art/western/holdings' / REVIEW.name.replace('review-', 'game-')
TURN = Matrix.Rotation(math.pi, 4, 'Z')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_fbx(path):
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                             axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
                             mesh_smooth_type='FACE', use_tspace=True, path_mode='STRIP', embed_textures=False,
                             # Unreal stores FBX vertex colours raw; M_HoldingBase decodes the sRGB values.
                             colors_type='SRGB')


def ripple_normal(path, size=512):
    """Seamless ripple normal map: integer-frequency waves tile exactly."""
    import numpy as np
    rng = np.random.default_rng(1865)
    u, v = np.meshgrid(np.arange(size) / size, np.arange(size) / size)
    dx = np.zeros((size, size)); dy = np.zeros((size, size))
    for _ in range(14):
        kx, ky = rng.integers(-9, 10, 2)
        if kx == 0 and ky == 0:
            continue
        amp = 1 / np.hypot(kx, ky) ** 1.2
        phase = rng.uniform(0, 2 * np.pi)
        c = np.cos(2 * np.pi * (kx * u + ky * v) + phase) * amp
        dx += c * kx; dy += c * ky
    scale = .35 / max(np.abs(dx).max(), np.abs(dy).max())
    n = np.dstack([-dx * scale, -dy * scale, np.ones_like(dx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    rgba = np.dstack([n * .5 + .5, np.ones((size, size, 1))]).astype(np.float32)
    image = bpy.data.images.new('T_HoldingWater_Ripples_N', size, size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(rgba[::-1].ravel())
    image.filepath_raw = str(path); image.file_format = 'PNG'; image.save()


def export_base(slug, name, out):
    """Export the setting base and water that holdings_base.py built around this holding."""
    base_version = os.environ.get('OLDWEST_HOLDINGS_BASE_VERSION', 'base')
    assert Path(base_version).name == base_version
    record_path = REVIEW / slug / base_version / 'base.json'
    if not record_path.exists():
        return None
    record = json.loads(record_path.read_text())
    blend = REVIEW / slug / base_version / (slug + '-Base.blend')
    bpy.ops.wm.open_mainfile(filepath=str(blend), use_scripts=False)
    result = {'base_json_sha256': sha(record_path), 'base_blend_sha256': sha(blend), 'setting': record['setting']}
    ground = [bpy.data.objects[n] for n in record['objects'] if n != 'Holding_Base_Water']
    groups = {'SM_HoldingBase_' + name: ground}
    if record.get('water_surface'):
        groups['SM_HoldingWater_' + name] = [bpy.data.objects['Holding_Base_Water']]
    for asset, sources in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        copies = []
        for source in sources:
            copy = source.copy(); copy.data = source.data.copy()
            bpy.context.scene.collection.objects.link(copy)
            copy.data.transform(TURN @ source.matrix_world)
            copy.matrix_world = Matrix.Identity(4)
            copy.select_set(True); copies.append(copy)
        bpy.context.view_layer.objects.active = copies[0]
        if len(copies) > 1:
            bpy.ops.object.join()
        joined = bpy.context.object
        joined.name = asset
        joined.data.materials.clear()
        joined.data.materials.append(bpy.data.materials.new('M_' + asset[3:]))
        fbx = out / (asset + '.fbx')
        export_fbx(fbx)
        joined.data.calc_loop_triangles()
        coords = [v.co for v in joined.data.vertices]
        result[asset] = {'fbx': fbx.name, 'fbx_sha256': sha(fbx), 'triangles': len(joined.data.loop_triangles),
                         'vertex_colors': bool(joined.data.color_attributes),
                         'bounds_m': {'min': [min(c[i] for c in coords) for i in range(3)],
                                      'max': [max(c[i] for c in coords) for i in range(3)]}}
    if record.get('water_surface'):
        ripples = GAME / 'T_HoldingWater_Ripples_N.png'
        if not ripples.exists():
            ripple_normal(ripples)
        result['water_normal'] = {'file': str(ripples.relative_to(ROOT)), 'sha256': sha(ripples)}
        palettes = json.loads((ROOT / 'art/western/holdings/base-palettes.json').read_text())
        result['water_color_srgb'] = record.get('water_color_srgb', palettes['settings'][record['setting']]['colors']['water'])
        assert len(result['water_color_srgb']) == 3 and all(0 <= x <= 1 for x in result['water_color_srgb'])
        result['water_color_source'] = 'reviewed_base' if 'water_color_srgb' in record else 'shared_setting_palette'
    return result


def asset_name(slug):
    return ''.join(part.title() for part in slug.split('-'))


def feeds_transmission(node, visited=None):
    visited = set() if visited is None else visited
    if node in visited:
        return False
    visited.add(node)
    for socket in node.outputs:
        for link in socket.links:
            if link.to_node.type == 'BSDF_PRINCIPLED':
                if link.to_socket.name in {'Transmission Weight', 'Transmission'}:
                    return True
            elif feeds_transmission(link.to_node, visited):
                return True
    return False


def main():
    slug = sys.argv[sys.argv.index('--') + 1]
    assert 'mixar' in Path(bpy.app.binary_path).name.lower(), 'Use the installed Mixar executable'
    review = REVIEW / slug / 'review'
    if HOLDINGS_SET == 'boomtown':
        roster = json.loads((REVIEW / 'roster-status.json').read_text())
        review = ROOT / roster['assets'][slug].get('review_directory', str(review))
    manifest = json.loads((review / 'manifest.json').read_text())
    project = review / manifest['project']
    assert sha(project) == manifest['project_sha256'], 'Review project changed since validation'
    name = asset_name(slug)
    out = GAME / slug / 'exports'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
    source = bpy.data.objects[manifest['mesh_object']]
    bpy.ops.object.select_all(action='DESELECT')
    copy = source.copy()
    copy.data = source.data.copy()
    bpy.context.scene.collection.objects.link(copy)
    copy.name = 'SM_Holding_' + name
    copy.data.transform(TURN)
    copy.matrix_world = Matrix.Identity(4)
    material = copy.data.materials[0]
    material.name = 'M_Holding_' + name
    copy.select_set(True)
    bpy.context.view_layer.objects.active = copy
    fbx = out / ('SM_Holding_' + name + '.fbx')
    export_fbx(fbx)
    textures = {}
    for record in manifest['textures']:
        channel = record['channel']
        # Older review manifests called every non-colour image ORM, including
        # transmission. Resolve the actual shader connection before exporting.
        matching = [n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE'
                    and n.image and Path(n.image.filepath).name == Path(record['file']).name]
        if any(feeds_transmission(node) for node in matching):
            channel = 'Transmission'
        assert channel in {'BaseColor', 'Normal', 'ORM', 'Transmission'}, channel
        assert channel not in textures, ('Ambiguous texture channel', slug, channel)
        destination = out / ('T_Holding_' + name + '_' + channel + '.png')
        shutil.copy2(review / record['file'], destination)
        assert sha(destination) == record['sha256']
        textures[channel] = {'file': destination.name, 'sha256': sha(destination)}
    coords = [v.co for v in copy.data.vertices]
    lo = [min(c[i] for c in coords) for i in range(3)]
    hi = [max(c[i] for c in coords) for i in range(3)]
    report = {'slug': slug, 'asset_name': name, 'source_project': str(project.relative_to(ROOT)),
              'source_project_sha256': manifest['project_sha256'], 'fbx': fbx.name, 'fbx_sha256': sha(fbx),
              'textures': textures, 'triangles': manifest['triangles'], 'material': material.name,
              'yaw_degrees_baked': 180, 'fbx_axes': {'forward': '-Y', 'up': 'Z'}, 'units': 'centimetres in FBX',
              'bounds_m_after_turn': {'min': lo, 'max': hi},
              'expected_unreal_size_cm': [round((hi[i] - lo[i]) * 100, 2) for i in range(3)],
              'source_saved': False}
    report['base'] = export_base(slug, name, out)
    (out.parent / 'export.json').write_text(json.dumps(report, indent=2) + '\n')
    print('HOLDING_EXPORTED', json.dumps({'slug': slug, 'fbx': str(fbx)}), flush=True)


if __name__ == '__main__':
    main()
