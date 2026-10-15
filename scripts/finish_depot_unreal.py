"""Verify and tune the saved depot without rerunning asset generation."""
import unreal,json,math,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'art/water_depot_v2'
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/WaterDepotV2')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
allactors=actors.get_all_level_actors();bylabel={a.get_actor_label():a for a in allactors}
print('ROTATOR_PROBE',unreal.Rotator(10,20,30))
for aid in ['rock_07','coast_rocks_05']:
    mesh=unreal.load_asset('/Game/Art/WaterDepotV2/Meshes/SM_'+aid)
    print('ROCK_BOUNDS',aid,mesh.get_bounds())
data=json.loads((ART/'geometry.json').read_text())
for i,inst in enumerate(data['instances']):
    a=bylabel[inst['asset']+' '+str(i)]
    if i in [0,len(data['instances'])-2]:print('ROCK_BEFORE',i,a.get_actor_rotation())
    rx,ry,rz=inst['rotation']
    a.set_actor_rotation(unreal.Rotator(pitch=-math.degrees(ry),yaw=-math.degrees(rz),roll=math.degrees(rx)),False)
    if i in [0,len(data['instances'])-2]:print('ROCK_AFTER',i,a.get_actor_rotation())

for c in ['r.Editor.Viewport.ScreenPercentageMode.RealTime 0',
          'r.Editor.Viewport.ScreenPercentageMode.NonRealTime 0',
          'r.Editor.Viewport.ScreenPercentage 100',
          'r.Editor.Viewport.OverridePIEScreenPercentage 0',
          'r.ScreenPercentage 100','r.Streaming.PoolSize 8192',
          'r.Streaming.FullyLoadUsedTextures 1','r.MaxAnisotropy 16',
          'r.Tonemapper.Sharpen 0.3']:
    unreal.SystemLibrary.execute_console_command(world,c)
# Fill the unlit side with soft, neutral skylight instead of a strong yellow cast.
sun=bylabel['Late afternoon key'].get_component_by_class(unreal.DirectionalLightComponent)
sun.set_intensity(18000);sun.set_light_color(unreal.LinearColor(1,.86,.70,1))
sky=bylabel['Open sky fill'].get_component_by_class(unreal.SkyLightComponent);sky.set_intensity(2.0)
fill=bylabel['Soft camera-side fill'].get_component_by_class(unreal.RectLightComponent)
fill.set_intensity(450000);fill.set_light_color(unreal.LinearColor(.76,.86,1,1))
post=bylabel['Fixed cinematic exposure'];settings=post.get_editor_property('settings')
settings.set_editor_property('auto_exposure_bias',1.1);post.set_editor_property('settings',settings)
cam=bylabel['Depot reveal camera']
unreal.EditorLevelLibrary.set_level_viewport_camera_info(cam.get_actor_location(),cam.get_actor_rotation())
assert levels.save_current_level()
started=time.monotonic();phase=0
def tick(delta):
    global phase
    try:
        if phase==0 and time.monotonic()-started>30:
            phase=1
            unreal.AutomationLibrary.take_high_res_screenshot(3840,2160,str(ART/'UnrealDepot_4K.png'),camera=cam,delay=5)
            print('DEPOT_FINAL_CAPTURE_REQUESTED')
        elif phase==1 and time.monotonic()-started>45:
            phase=2
            print('DEPOT_FINAL_READY')
    except Exception as error:
        unreal.log_error('DEPOT_FINISH_ERROR '+str(error));phase=2
    # A scoped local mailbox permits subsequent quality fixes in this editor.
    mailbox=ART/'editor-request.py'
    if phase==2 and mailbox.exists():
        code=mailbox.read_text();mailbox.unlink()
        try:exec(compile(code,str(mailbox),'exec'),globals())
        except Exception as error:unreal.log_error('DEPOT_REQUEST_ERROR '+repr(error))
handle=unreal.register_slate_post_tick_callback(tick)
