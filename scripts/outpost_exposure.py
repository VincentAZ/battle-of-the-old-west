"""Set consistent physical exposure for the prototype's 16,000-lux sunlight."""
import unreal
import time
import json
from pathlib import Path

def configure_exposure():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = [a for a in actors.get_all_level_actors() if a.get_actor_label() == 'Stagecoach Station camera exposure']
    volume = existing[0] if existing else actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector())
    volume.set_actor_label('Stagecoach Station camera exposure')
    volume.set_editor_property('unbound', True)
    volume.set_editor_property('priority', 100)
    settings = volume.get_editor_property('settings')
    for name, value in {
        'auto_exposure_method': unreal.AutoExposureMethod.AEM_MANUAL,
        'auto_exposure_apply_physical_camera_exposure': True,
        'auto_exposure_bias': 0.7,
        'camera_shutter_speed': 60.0,
        'camera_iso': 100.0,
        'depth_of_field_fstop': 8.0,
    }.items():
        settings.set_editor_property('override_' + name, True)
        settings.set_editor_property(name, value)
    volume.set_editor_property('settings', settings)
    fill_matches = [a for a in actors.get_all_level_actors() if a.get_actor_label() == 'Cinematic sky bounce']
    fill = fill_matches[0] if fill_matches else actors.spawn_actor_from_class(unreal.RectLight, unreal.Vector(-650, 900, 650))
    fill.set_actor_label('Cinematic sky bounce')
    fill.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(fill.get_actor_location(), unreal.Vector(0, 0, 240)), False)
    light = fill.get_component_by_class(unreal.RectLightComponent)
    light.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.set_intensity(150000)
    light.set_light_color(unreal.LinearColor(.31, .57, 1, 1))
    light.set_editor_property('source_width', 600)
    light.set_editor_property('source_height', 600)
    light.set_editor_property('attenuation_radius', 2500)
    # Physical sunlight needs brighter emissive surfaces than the Blender study.
    for name, rgb in [('WaterLight', (.025, .65, .8)), ('WarningLight', (1, .22, .025))]:
        mat = unreal.load_asset('/Game/Art/WaterOutpost/Materials/M_' + name)
        if not mat:
            continue
        edit = unreal.MaterialEditingLibrary
        edit.delete_all_material_expressions(mat)
        color = edit.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -200, 0)
        color.set_editor_property('constant', unreal.LinearColor(*rgb, 1))
        edit.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
        glow = edit.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -200, 150)
        glow.set_editor_property('constant', unreal.LinearColor(*(v * 1600 for v in rgb), 1))
        edit.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        edit.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return volume

if __name__ == '__main__':
    ROOT = Path(__file__).resolve().parents[1]
    SCREENSHOT = str(ROOT / 'art/water_outpost/UnrealOutpost.png')
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    configure_exposure()
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    camera = next(a for a in actors.get_all_level_actors() if a.get_actor_label() == 'Stagecoach Station reveal camera')
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
    started = time.monotonic()
    phase = 0
    play_started = None
    def capture(delta):
        global phase, play_started
        elapsed = time.monotonic() - started
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        try:
            if phase == 0 and elapsed > 10:
                phase = 1
                unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, SCREENSHOT, camera=camera, delay=3)
                print('OUTPOST_EXPOSURE_VERIFIED_CAPTURE_REQUESTED')
            elif phase == 1 and elapsed > 20:
                phase = 2
                levels.editor_request_begin_play()
            elif phase == 2 and levels.is_in_play_in_editor():
                play_started = time.monotonic()
                phase = 3
            elif phase == 3 and time.monotonic() - play_started > 3:
                game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
                sequences = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.LevelSequenceActor)
                assert len(sequences) == 1, 'Expected one intro sequence'
                player = sequences[0].get_editor_property('sequence_player')
                assert player and player.is_playing(), 'Intro sequence did not start in Play mode'
                cams = unreal.GameplayStatics.get_all_actors_of_class(game, unreal.CineCameraActor)
                assert len(cams) == 1
                loc = cams[0].get_actor_location()
                assert loc.x > -1090, 'Camera did not advance from its initial position'
                report = {'play_in_editor': True, 'sequence_playing': True, 'camera_moved': True, 'camera_position_cm': [loc.x, loc.y, loc.z]}
                (ROOT / 'art/water_outpost/playback-validation.json').write_text(json.dumps(report, indent=2))
                print('OUTPOST_PLAYBACK_VERIFIED', json.dumps(report))
                levels.editor_request_end_play()
                unreal.unregister_slate_post_tick_callback(handle)
            elif elapsed > 60:
                raise RuntimeError('Play mode validation timed out')
        except Exception as error:
            unreal.log_error('OUTPOST_PLAYBACK_FAILED: ' + str(error))
            levels.editor_request_end_play()
            unreal.unregister_slate_post_tick_callback(handle)
    handle = unreal.register_slate_post_tick_callback(capture)
