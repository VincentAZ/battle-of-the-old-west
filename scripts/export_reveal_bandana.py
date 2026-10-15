"""Prepare a thin separate cloth prop from the reviewed Drifter extraction."""
import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/drifter/reveal-bandana-v001'
SOURCE = BASE/'extraction-v004'
OUT = BASE/'prop-v002'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
record = json.loads((SOURCE/'authoring.json').read_text())
review = json.loads((SOURCE/'visual-review.json').read_text())
assert review['status'] == 'accepted_for_prop_preparation'
assert review['authoring_sha256'] == sha(SOURCE/'authoring.json')
project = SOURCE/'Bandana_Drop_Candidate.blend'
assert sha(project) == record['project_sha256']
assert sha(ROOT/record['source']) == record['source_sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
prop = bpy.data.objects['Bandana_Drop_Candidate']
prop.name = 'SM_Reveal_Bandana'
prop.data.transform(prop.matrix_world)
prop.matrix_world = Matrix.Identity(4)
points = [v.co for v in prop.data.vertices]
center = Vector([(min(p[k] for p in points)+max(p[k] for p in points))*.5 for k in range(3)])
bpy.ops.object.select_all(action='DESELECT')
prop.select_set(True)
bpy.context.view_layer.objects.active = prop
decimate = prop.modifiers.new('Prop triangle budget', 'DECIMATE')
decimate.ratio = .60
bpy.ops.object.modifier_apply(modifier=decimate.name)
# A two-sided sheet avoids extruded spikes at the tightly folded source edge.
# It is a visual cloth surface, not a claim about measured textile thickness.
tri = prop.modifiers.new('Export triangles', 'TRIANGULATE')
bpy.ops.object.modifier_apply(modifier=tri.name)
scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = 700
captures = []
camera = scene.camera
for name, offset in [('front', (0, -2, 0)), ('quarter', (.8, -2, .1)), ('rear', (0, 2, 0))]:
    camera.location = center+Vector(offset)
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    target = OUT/(name+'.png')
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
    captures.append(dict(path=str(target.relative_to(ROOT)), sha256=sha(target)))
prepared = OUT/'Reveal_Bandana.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(prepared))
# FBX mesh is centimetres about its own centre, with the same axis convention
# as the existing Drifter. The actor transform supplies the public-facing pose.
prop.data.transform(Matrix.Translation(-center))
prop.data.transform(Matrix.Scale(100, 4))
scene.unit_settings.scale_length = .01
fbx = OUT/'SM_Reveal_Bandana.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
    bake_anim=False, use_mesh_modifiers=False, mesh_smooth_type='FACE',
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z')
points = [v.co for v in prop.data.vertices]
assert sha(project) == record['project_sha256']
assert sha(ROOT/record['source']) == record['source_sha256']
(OUT/'manifest.json').write_text(json.dumps(dict(name=prop.name, fbx=fbx.name,
    fbx_sha256=sha(fbx), project_sha256=sha(prepared), source_project_sha256=sha(project),
    approved_drifter_source=record['source'], approved_drifter_sha256=record['source_sha256'],
    source_review_sha256=sha(SOURCE/'visual-review.json'),
    brief_sha256=sha(ROOT/'research/western-presentation/drifter-reveal-bandana.json'),
    center_in_source_m=list(center), size_cm=[max(p[k] for p in points)-min(p[k] for p in points) for k in range(3)],
    triangles=len(prop.data.polygons), two_sided=True,
    thickness_note='Two-sided visual sheet; no claim of measured historic textile thickness.',
    unreal_material='/Game/Art/Western/Drifter/M_Drifter.M_Drifter',
    captures=captures, source_unchanged=True), indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
