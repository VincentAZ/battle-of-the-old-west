"""Author the sourced bonus-resource tumbler locally; preserves the prior kit."""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/whiskey/bonus-v002'
EVIDENCE = ROOT / 'research/western-presentation/bonus-whiskey.json'


def lathe(name, profile, material):
    n = 96
    vertices = [(r*math.cos(i*math.tau/n), r*math.sin(i*math.tau/n), z)
                for r, z in profile for i in range(n)]
    faces = [(j*n+i, j*n+(i+1)%n, ((j+1)%len(profile))*n+(i+1)%n,
              ((j+1)%len(profile))*n+i) for j in range(len(profile)) for i in range(n)]
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    mesh.materials.append(material)
    for p in mesh.polygons: p.use_smooth = True
    # Merge axis vertices and consistently orient the two closed solids.
    bpy.context.view_layer.objects.active = obj; obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=.000001); bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT'); obj.select_set(False)
    return obj


def main():
    evidence = json.loads(EVIDENCE.read_text()); assert evidence['sources'] and evidence['render_brief']
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True, exist_ok=True); bpy.ops.wm.read_factory_settings(use_empty=True)
    glass = bpy.data.materials.new('M_Bonus_ClearGlass'); glass.use_nodes = True
    p = glass.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (.95, .985, .98, 1)
    p.inputs['Roughness'].default_value = .08; p.inputs['IOR'].default_value = 1.5
    p.inputs['Transmission Weight'].default_value = 1
    amber = bpy.data.materials.new('M_Bonus_Amber'); amber.use_nodes = True
    p = amber.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (.65, .24, .018, 1)
    p.inputs['Roughness'].default_value = .12; p.inputs['Transmission Weight'].default_value = .5
    p.inputs['IOR'].default_value = 1.36
    # Metres. Cross-section proceeds along the exterior, over the rounded lip,
    # down the open interior and back through the substantial closed base.
    body = lathe('PlainBarTumbler', [(0, 0), (.025, 0), (.026, .0005), (.0265, .002),
        (.0314, .0695), (.0315, .0702), (.0312, .0708), (.0306, .071),
        (.0300, .0708), (.0295, .0702), (.02935, .0692), (.0227, .015),
        (.0222, .014), (0, .014)], glass)
    liquid = lathe('AmberWhiskey', [(0, .0142), (.02205, .0142), (.02248, .015),
        (.02464, .0326), (.02455, .0329), (.024, .03255), (0, .03255)], amber)
    for obj in (body, liquid): obj.select_set(True)
    bpy.context.view_layer.objects.active = body; bpy.ops.object.join(); obj = bpy.context.object
    obj.name = evidence['asset']; obj.data.calc_loop_triangles()
    project = OUT / (obj.name+'.blend'); fbx = OUT / (obj.name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE')
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    scene = bpy.context.scene; scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
    scene.cycles.samples = 96; scene.cycles.use_denoising = True
    scene.render.resolution_x = 1000; scene.render.resolution_y = 1000; scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.world = bpy.data.worlds.new('ClearDay'); scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.6, .75, 1, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .6
    floor = bpy.data.materials.new('ReviewFloor'); floor.diffuse_color = (.11, .19, .26, 1)
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, -.0003)); bpy.context.object.data.materials.append(floor)
    for pos, power, size in [((.12, -.08, .18), .12, .09), ((-.12, .02, .12), .08, .12), ((.02, .14, .16), .14, .08)]:
        bpy.ops.object.light_add(type='AREA', location=pos); lamp=bpy.context.object
        lamp.data.energy=power; lamp.data.shape='DISK'; lamp.data.size=size
        lamp.rotation_euler=(Vector((0, 0, .035))-lamp.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(.11, -.17, .13)); camera=bpy.context.object
    camera.rotation_euler=(Vector((0, 0, .034))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=.105; camera.data.clip_start=.001; scene.camera=camera
    scene.render.filepath=str(OUT/'glass.png'); bpy.ops.render.render(write_still=True)
    sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/'manifest.json').write_text(json.dumps(dict(name=obj.name, fbx=fbx.name, sha256=sha(fbx),
        project_sha256=sha(project), evidence_sha256=sha(EVIDENCE), authoring_sha256=sha(Path(__file__)),
        triangles=len(obj.data.loop_triangles), size_cm=[round(float(v)*100, 4) for v in obj.dimensions],
        materials=[m.name for m in obj.data.materials], render_sha256=sha(OUT/'glass.png'),
        visual_review='pending', authoring_application=bpy.app.binary_path), indent=2)+'\n')
    print('BONUS_WHISKEY_AUTHORED', flush=True)


if __name__ == '__main__': main()
