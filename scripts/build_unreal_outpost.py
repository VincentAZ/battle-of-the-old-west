"""Import the Blender outpost, create a lit map, and author a camera sequence.

Run in Unreal with -ExecutePythonScript=/absolute/path/to/this_file.py.
Creates only the prototype's named assets; refuses to overwrite an existing map.
"""
import unreal
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from outpost_exposure import configure_exposure
ART = ROOT / 'art' / 'water_outpost'
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
asset_lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
MAP = '/Game/Maps/WaterOutpost'
assert not asset_lib.does_asset_exist(MAP), 'Map already exists; preserve user edits.'
assert levels.new_level(MAP), 'Could not create prototype map'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

# Explicit legacy FBX settings preserve the single environment mesh and its slots.
unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
options = unreal.FbxImportUI()
options.set_editor_property('import_mesh', True)
options.set_editor_property('import_as_skeletal', False)
options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH)
options.set_editor_property('import_materials', False)
options.set_editor_property('import_textures', False)
options.set_editor_property('import_animations', False)
options.set_editor_property('automated_import_should_detect_type', False)
options.static_mesh_import_data.set_editor_property('combine_meshes', True)
options.static_mesh_import_data.set_editor_property('auto_generate_collision', False)
options.static_mesh_import_data.set_editor_property('generate_lightmap_u_vs', False)
task = unreal.AssetImportTask()
task.set_editor_property('filename', str(ART / 'WaterOutpost.fbx'))
task.set_editor_property('destination_path', '/Game/Art/WaterOutpost')
task.set_editor_property('destination_name', 'SM_WaterOutpost')
task.set_editor_property('automated', True)
task.set_editor_property('save', True)
task.set_editor_property('options', options)
task.set_editor_property('factory', unreal.FbxFactory())
tools.import_asset_tasks([task])
meshes = [obj for obj in task.get_objects() if isinstance(obj, unreal.StaticMesh)]
assert len(meshes) == 1, f'Expected one environment mesh, got {len(meshes)}'
mesh = meshes[0]
print('OUTPOST_IMPORT', mesh.get_path_name(), mesh.get_bounds())

# Rebuild PBR materials from the source palette instead of relying on FBX shaders.
palette = json.loads((ART / 'materials.json').read_text())
materials = {}
for name, values in palette.items():
    mat = tools.create_asset('M_' + name, '/Game/Art/WaterOutpost/Materials', unreal.Material, unreal.MaterialFactoryNew())
    color = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -350, -50)
    color.set_editor_property('constant', unreal.LinearColor(*values['color'], 1))
    unreal.MaterialEditingLibrary.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    for value, prop, y in [(values['metallic'], unreal.MaterialProperty.MP_METALLIC, 90), (values['roughness'], unreal.MaterialProperty.MP_ROUGHNESS, 180)]:
        scalar = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -200, y)
        scalar.set_editor_property('r', value)
        unreal.MaterialEditingLibrary.connect_material_property(scalar, '', prop)
    if values['emission']:
        glow = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -350, 280)
        glow.set_editor_property('constant', unreal.LinearColor(*(v * values['emission'] for v in values['color']), 1))
        unreal.MaterialEditingLibrary.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name == 'FlagCloth':
        mat.set_editor_property('two_sided', True)
    unreal.MaterialEditingLibrary.recompile_material(mat)
    materials[name] = mat
for index, slot in enumerate(mesh.get_editor_property('static_materials')):
    name = str(slot.get_editor_property('material_slot_name'))
    assert name in materials, f'Unmapped material slot: {name}'
    mesh.set_material(index, materials[name])
asset_lib.save_loaded_asset(mesh)

def spawn(cls, label, location=(0, 0, 0), rotation=(0, 0, 0)):
    actor = actors.spawn_actor_from_class(cls, unreal.Vector(*location), unreal.Rotator(*rotation))
    actor.set_actor_label(label)
    return actor

environment = spawn(unreal.StaticMeshActor, 'Water Stagecoach Station — Blender environment')
environment.static_mesh_component.set_static_mesh(mesh)
body = mesh.get_editor_property('body_setup')
body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)

sun = spawn(unreal.DirectionalLight, 'Desert sunset', (0, 0, 1200), (-18, -35, 0))
sunlight = sun.get_component_by_class(unreal.DirectionalLightComponent)
sunlight.set_mobility(unreal.ComponentMobility.MOVABLE)
sunlight.set_intensity(16000)
sunlight.set_light_color(unreal.LinearColor(1, .63, .39, 1))
sunlight.set_editor_property('atmosphere_sun_light', True)
spawn(unreal.SkyAtmosphere, 'Dusty sky')
sky = spawn(unreal.SkyLight, 'Sky fill', (0, 0, 1000))
skycomp = sky.get_component_by_class(unreal.SkyLightComponent)
skycomp.set_mobility(unreal.ComponentMobility.MOVABLE)
skycomp.set_editor_property('real_time_capture', True)
skycomp.set_intensity(1.2)
fog = spawn(unreal.ExponentialHeightFog, 'Desert haze')
fogcomp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fogcomp.set_editor_property('fog_density', .008)
fogcomp.set_editor_property('fog_height_falloff', .3)
configure_exposure()
for name, loc, color, intensity in [
    ('Cool canopy bounce', (0, 350, 220), (.04, .7, 1), 500),
    ('Magenta rim', (0, -500, 600), (1, .025, .13), 3500)]:
    light = spawn(unreal.PointLight, name, loc)
    component = light.get_component_by_class(unreal.PointLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_light_color(unreal.LinearColor(*color, 1))
    component.set_intensity(intensity)
    component.set_editor_property('attenuation_radius', 1300)

# Blender's right-handed coordinates map into Unreal's left-handed Y axis.
def position(xyz):
    return unreal.Vector(xyz[0] * 100, -xyz[1] * 100, xyz[2] * 100)

camera = spawn(unreal.CineCameraActor, 'Stagecoach Station reveal camera')
cc = camera.get_cine_camera_component()
cc.set_editor_property('current_focal_length', 43)
cc.set_editor_property('current_aperture', 8)
focus = cc.get_editor_property('focus_settings')
focus.set_editor_property('focus_method', unreal.CameraFocusMethod.DISABLE)
cc.set_editor_property('focus_settings', focus)
film = cc.get_editor_property('filmback')
film.set_editor_property('sensor_width', 36)
film.set_editor_property('sensor_height', 20.25)
cc.set_editor_property('filmback', film)

sequence = tools.create_asset('LS_OutpostReveal', '/Game/Cinematics', unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
sequence.set_display_rate(unreal.FrameRate(24, 1))
sequence.set_playback_start(0)
sequence.set_playback_end(192)
binding = sequence.add_possessable(camera)
section = binding.add_track(unreal.MovieScene3DTransformTrack).add_section()
section.set_range(0, 192)
channels = section.get_channels_by_type(unreal.MovieSceneScriptingDoubleChannel)
assert len(channels) >= 9, 'Expected transform channels'
for frame, xyz, target in [(0, (-11,-16,3.9), (0,0,3.1)), (96, (-9,-15,3.3), (.1,0,3.1)), (191, (-7,-14,2.8), (.5,.3,3.2))]:
    loc = position(xyz)
    rot = unreal.MathLibrary.find_look_at_rotation(loc, position(target))
    values = [loc.x, loc.y, loc.z, rot.roll, rot.pitch, rot.yaw, 1, 1, 1]
    for channel, value in zip(channels, values):
        channel.add_key(unreal.FrameNumber(frame), value)
    if frame == 96:
        camera.set_actor_location_and_rotation(loc, rot, False, False)
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(loc, rot)
        start = spawn(unreal.PlayerStart, 'Explore the outpost', (loc.x, loc.y, loc.z), (rot.pitch, rot.yaw, rot.roll))
cut = sequence.add_track(unreal.MovieSceneCameraCutTrack).add_section()
cut.set_range(0, 192)
cut.set_camera_binding_id(sequence.get_binding_id(binding))
sequence_actor = spawn(unreal.LevelSequenceActor, 'Play — eight second outpost reveal')
sequence_actor.set_sequence(sequence)
settings = sequence_actor.get_editor_property('playback_settings')
settings.set_editor_property('auto_play', True)
sequence_actor.set_editor_property('playback_settings', settings)
asset_lib.save_directory('/Game', only_if_is_dirty=True, recursive=True)
assert levels.save_current_level()
actors.set_selected_level_actors([])

report = dict(map=MAP, sequence=sequence.get_path_name(), static_mesh=mesh.get_path_name(), material_count=len(materials), duration_seconds=8, gameplay_implemented=False)
(ART / 'unreal-build.json').write_text(json.dumps(report, indent=2))
print('UNREAL_OUTPOST_READY', json.dumps(report))

# Wait for scene rendering/shader work before requesting a camera screenshot.
started = time.monotonic()
def capture_when_ready(delta):
    if time.monotonic() - started < 45:
        return
    unreal.unregister_slate_post_tick_callback(callback)
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(ART / 'UnrealOutpost.png'), camera=camera, delay=5)
callback = unreal.register_slate_post_tick_callback(capture_when_ready)
