"""Paint restrained garment wear in Mixar, preserving the Drifter's geometry.

Mixar --background --factory-startup --python-exit-code 1 --python
scripts/weather_drifter_review.py -- art/western/drifter/review-v002
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry_hash(obj):
    mesh = obj.data
    values = ([(tuple(v.co)) for v in mesh.vertices],
              [tuple(p.vertices) for p in mesh.polygons],
              [tuple(uv.uv) for uv in mesh.uv_layers.active.data])
    return hashlib.sha256(repr(values).encode()).hexdigest()


def smooth(a, b, x):
    v = np.clip((x - a) / (b - a), 0, 1)
    return v * v * (3 - 2 * v)


def bell(value, center, width):
    return np.exp(-((value - center) / width) ** 2)


def main():
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    source = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    settings_path = source / 'wear-settings.json'
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    out = source / 'review'
    out.mkdir(exist_ok=False)
    (out / 'textures').mkdir()
    (out / 'previews').mkdir()
    before = source / 'Drifter-Before-Wear.blend'
    bpy.ops.wm.open_mainfile(filepath=str(before), use_scripts=False)
    obj = bpy.data.objects['Drifter_Appearance_Review']
    original_geometry = geometry_hash(obj)
    mesh = obj.data
    mesh.calc_loop_triangles()
    material = mesh.materials[0]
    images = {node.image.name: node.image for node in material.node_tree.nodes
              if node.type == 'TEX_IMAGE' and node.image}
    base = images['T_Drifter_BaseColor']
    width, height = base.size
    original = np.empty(width * height * 4, dtype=np.float32)
    base.pixels.foreach_get(original)
    original = original.reshape(height, width, 4)
    positions = np.zeros((height, width, 3), dtype=np.float32)
    covered = np.zeros((height, width), dtype=bool)
    uvdata = mesh.uv_layers.active.data
    # Paint on the actual model's UV atlas using interpolated object positions.
    # No resampling of the source atlas and no change to UVs or geometry.
    for triangle in mesh.loop_triangles:
        uv = np.array([uvdata[i].uv[:] for i in triangle.loops]) * [width, height] - .5
        points = np.array([mesh.vertices[i].co[:] for i in triangle.vertices])
        low = np.maximum(np.floor(uv.min(axis=0)).astype(int), 0)
        high = np.minimum(np.ceil(uv.max(axis=0)).astype(int), [width-1, height-1])
        if np.any(high < low):
            continue
        a, b, c = uv
        determinant = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(determinant) < 1e-8:
            continue
        gy, gx = np.mgrid[low[1]:high[1]+1, low[0]:high[0]+1]
        wa = ((b[1]-c[1])*(gx-c[0]) + (c[0]-b[0])*(gy-c[1])) / determinant
        wb = ((c[1]-a[1])*(gx-c[0]) + (a[0]-c[0])*(gy-c[1])) / determinant
        wc = 1-wa-wb
        inside = (wa >= -1e-5) & (wb >= -1e-5) & (wc >= -1e-5)
        yy, xx = gy[inside], gx[inside]
        positions[yy, xx] = wa[inside,None]*points[0]+wb[inside,None]*points[1]+wc[inside,None]*points[2]
        covered[yy, xx] = True
    x, y, z = positions.transpose(2, 0, 1)
    ax = np.abs(x)
    rgb = original[:,:,:3]
    # Protect the entire head and the central bandana, including its lower tip.
    # Extend beyond the visible cloth so texture filtering cannot bleed into it.
    protected = (z > 1.50) | ((z > 1.22) & (ax < .19) & (y < .03))
    jacket = smooth(.98, 1.015, z) * (1-smooth(1.45, 1.50, z))
    # The jacket's height mask excludes the gloves. Avoid a brightness mask:
    # it would amplify the original canvas grain into dark speckled stains.
    trousers = smooth(.14, .21, z) * (1-smooth(.91, .97, z)) * (1-smooth(.235, .29, ax))
    allowed = covered & ~protected
    jacket *= allowed
    trousers *= allowed
    # Smooth, deterministic 3D variation crosses UV seams naturally.
    broad = (.50 + .18*np.sin(x*18+y*13+z*23) + .12*np.sin(x*37-y*27+z*41)
             + .08*np.sin(x*73+y*51-z*66))
    grain = .5+.5*np.sin(x*717+y*631+z*853)*np.sin(x*433-y*911+z*557)
    front = 1-smooth(-.07, .04, y)
    shoulders = bell(z,1.425,.075)
    elbows = bell(z,1.17,.08)*smooth(.20,.29,ax)
    cuffs = bell(z,1.025,.03)*smooth(.29,.36,ax)
    hem = bell(z,1.01,.018)*(1-smooth(.22,.28,ax))
    pocket_edges = bell(ax,.135,.05)*bell(z,1.105,.085)*front
    knees = bell(z,.49,.105)*front
    seat = bell(z,.81,.09)*smooth(.00,.09,y)
    trouser_hems = bell(z,.21,.065)
    jacket_fade = jacket * ((.065+.11*broad) + .14*shoulders + .20*elbows + .21*cuffs
                            + .15*hem + .07*pocket_edges) * (.86+.14*grain)
    trouser_fade = trousers * ((.025+.05*broad) + .27*knees + .10*seat) * (.9+.1*grain)
    paint = rgb.copy()
    # Sun-faded canvas stays warm brown; abraded trousers stay dark charcoal.
    for amount, color in ((jacket_fade, (.66,.565,.435)),
                          (trouser_fade, (.405,.375,.325))):
        paint = paint*(1-amount[:,:,None])+np.array(color)*amount[:,:,None]
    dust = trousers * trouser_hems * (.085+.16*broad)
    paint = paint*(1-dust[:,:,None])+np.array((.46,.39,.30))*dust[:,:,None]
    if settings.get('profile') == 'readable_wear':
        # Local abrasion must read in a full-body render. The first pass was
        # only a small hue shift: target actual lighter exposed canvas fibers.
        paint = rgb.copy()
        fiber = (.72 + .20*np.sin(x*1091+y*887+z*523)
                 * np.sin(x*347-y*719+z*1217))
        irregular = .76+.24*np.sin(x*93+y*79+z*117)*np.sin(x*41-y*63+z*57)
        jacket_sun = jacket*(.14+.22*shoulders+.10*elbows)*(.8+.2*broad)
        paint = paint*(1-jacket_sun[:,:,None])+np.array((.80,.69,.53))*jacket_sun[:,:,None]
        # Follow the existing pockets and jacket hem rather than invent patches.
        pocket_side_inner = bell(ax,.108,.007)*bell(z,1.145,.07)*front
        pocket_side_outer = bell(ax,.181+.10*(1.23-z),.008)*bell(z,1.145,.07)*front
        pocket_top = bell(z,1.232,.008)*bell(ax,.141,.038)*front
        pocket_bottom = bell(z,1.061,.008)*bell(ax,.148,.039)*front
        rubbed_edges = jacket*np.clip(.38*(pocket_side_inner+pocket_side_outer)
                                       +.50*pocket_top+.30*pocket_bottom
                                       + .45*hem + .52*cuffs,0,.65)*fiber*irregular
        paint = paint*(1-rubbed_edges[:,:,None])+np.array((.82,.72,.56))*rubbed_edges[:,:,None]
        elbow_rub = jacket*elbows*.43*irregular
        paint = paint*(1-elbow_rub[:,:,None])+np.array((.78,.68,.53))*elbow_rub[:,:,None]
        # Unequal rubbed knee areas and seat wear keep the trousers functional.
        knee_shape = np.exp(-((z-(.48+.023*np.sign(x)))/.095)**4)
        knee_width = np.exp(-((ax-.105)/.058)**4)
        knee_rub = trousers*front*knee_shape*knee_width*.48*irregular
        seat_rub = trousers*seat*.20*irregular
        pants_rub = np.clip(knee_rub+seat_rub,0,.55)
        paint = paint*(1-pants_rub[:,:,None])+np.array((.59,.545,.465))*pants_rub[:,:,None]
        # Trail dust fades upward from intact trouser hems, with a narrow rubbed edge.
        lower_trousers = smooth(.115,.155,z)*(1-smooth(.31,.37,z))*(1-smooth(.235,.29,ax))*allowed
        hem_dust = lower_trousers*bell(z,.175,.082)*(.24+.17*broad)
        hem_edge = lower_trousers*bell(z,.145,.012)*.30*fiber
        amount = np.clip(hem_dust+hem_edge,0,.6)
        paint = paint*(1-amount[:,:,None])+np.array((.63,.53,.40))*amount[:,:,None]
    revised = original.copy()
    revised[:,:,:3] = np.clip(paint,0,1)
    revised[~allowed] = original[~allowed]
    assert np.array_equal(revised[protected], original[protected])
    base.pixels.foreach_set(revised.ravel())
    base.update()
    records = []
    for name, image in images.items():
        destination = out/'textures'/(name+'.png')
        # Force repacking the edited pixels, rather than the old embedded PNG.
        image.filepath_raw = str(destination)
        image.file_format = 'PNG'
        image.save()
        if image.packed_file:
            image.unpack(method='REMOVE')
        image.filepath_raw = str(destination)
        image.reload()
        image.pack()
        records.append({'channel':name.removeprefix('T_Drifter_'),'size':list(image.size),
                        'file':str(destination.relative_to(out)),'sha256':sha(destination)})
    # Reopen verification checks exact protected pixel preservation after PNG save.
    reloaded = np.empty(width*height*4,dtype=np.float32)
    base.pixels.foreach_get(reloaded)
    reloaded = reloaded.reshape(height,width,4)
    assert np.array_equal(reloaded[protected & covered],original[protected & covered])
    assert geometry_hash(obj) == original_geometry
    scene = bpy.context.scene
    scene.camera = bpy.data.objects['Review_three-quarter']
    obj['appearance_revision'] = 'Restrained garment wear; bandana, shape and UVs preserved'
    project = out/'Drifter-Review.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    manifest = json.loads((source/'before-wear-manifest.json').read_text())
    manifest.update(project_sha256=sha(project), textures=records, previews=[],
                    source_glb=str(source/'drifter-original.glb'),
                    revision='Worn but cared-for clothes; no tears or holes',
                    wear_settings=settings,
                    source_project=str(before), source_project_sha256=sha(before),
                    geometry_uv_sha256=original_geometry,
                    protected_head_bandana_texels=int((protected & covered).sum()),
                    protected_head_bandana_pixels_unchanged=True,
                    altered_texels=int(np.any(reloaded!=original,axis=2).sum()))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for view in ['three-quarter','front','side','rear','game-camera','face-detail','hands-detail','underside-diagnostic']:
        scene.camera = bpy.data.objects['Review_'+view]
        bpy.data.objects['Review_only_ground'].hide_render = view == 'underside-diagnostic'
        destination = out/'previews'/(view+'.png')
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        manifest['previews'].append({'view':view,'file':str(destination.relative_to(out)),
                                     'sha256':sha(destination)})
        print('DRIFTER_WEAR_PREVIEW',view,flush=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('DRIFTER_WEAR_READY',str(project),flush=True)


if __name__ == '__main__':
    main()
