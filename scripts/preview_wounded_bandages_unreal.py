"""Native pose/geometry review using transient real presentation actors.

UnrealEditor <project> -ExecutePythonScript=<this> -unattended -nosplash
OLDWEST_BANDAGE_PREVIEW_OUTPUT must name a new evidence directory.
Optional OLDWEST_BANDAGE_PREVIEW_SLUGS limits an initial diagnostic run.
No map/asset saves, rules calls, network state or game-world actor injection.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/bandages'
OUT = Path(os.environ['OLDWEST_BANDAGE_PREVIEW_OUTPUT']).resolve()
assert OUT.is_relative_to(BASE) and not OUT.exists(), 'Use a new bandage evidence directory'
OUT.mkdir(parents=True)
manifest = json.loads((BASE/'current-manifest.json').read_text())
selected = os.environ.get('OLDWEST_BANDAGE_PREVIEW_SLUGS')
slugs = selected.split(',') if selected else sorted(manifest['characters'])
assert set(slugs) <= set(manifest['characters'])
content = ROOT/'game/OldWest/Content'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    return {str(p.relative_to(content)): sha(p) for p in content.rglob('*') if p.is_file()}


before = snapshot()
(OUT/'content-before.json').write_text(json.dumps(before, indent=2)+'\n')
report = dict(ok=False, scope='Transient native presentation actors; sampled poses, not a live match or continuous collision proof',
              slugs=slugs, captures=[], states=[], errors=[],
              module_sha256=sha(ROOT/'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'))
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/WaterDepotV2')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for command in ('r.ScreenPercentage 100', 'r.Streaming.FullyLoadUsedTextures 1',
                'r.Streaming.PoolSize 4096', 'r.MotionBlurQuality 0'):
    unreal.SystemLibrary.execute_console_command(world, command)
origin = unreal.Vector(0, 2500, 1000)
floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, origin)
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(200, 200, 1))
camera = actors.spawn_actor_from_class(unreal.CineCameraActor, origin+unreal.Vector(0,600,200))
lens = camera.get_cine_camera_component()
lens.set_editor_property('current_focal_length', 55)
lens.set_editor_property('current_aperture', 8)
lens.set_editor_property('filmback', unreal.CameraFilmbackSettings(sensor_width=36, sensor_height=27))
focus = unreal.CameraFocusSettings()
focus.focus_method = unreal.CameraFocusMethod.DISABLE
lens.set_editor_property('focus_settings', focus)
lights = []
for offset in [(-300,400,400),(300,-400,400)]:
    light = actors.spawn_actor_from_class(unreal.RectLight, origin+unreal.Vector(*offset))
    light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(light.get_actor_location(),origin+unreal.Vector(0,0,100)),False)
    component = light.get_component_by_class(unreal.RectLightComponent)
    component.set_intensity(5000)
    component.set_editor_property('source_width',300)
    component.set_editor_property('source_height',300)
    lights.append(light)
poses = [('wounded',0.)] + [(kind,phase) for kind in ('hit','attack') for phase in (.15,.45,.75)] + [('walk',phase) for phase in (0.,.25,.5,.75)] + [('concealed',0.),('healthy',0.),('destroyed',0.)]
jobs = [(slug,kind,phase) for slug in slugs for kind,phase in poses]
job_index = 0
unit = None
phase = 'prepare'
deadline = time.monotonic()+3
timeout = time.monotonic()+120
capture_views = []
current = None
geometry = None
masked_pose = None
closed = False
unreal.EditorPythonScripting.set_keep_python_script_alive(True)


def save():
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')


def finish():
    global closed
    if closed:
        return
    closed = True
    unreal.unregister_slate_post_tick_callback(handle)
    report['content_unchanged'] = snapshot() == before
    report['ok'] = not report['errors'] and report['content_unchanged'] and len(report['states']) == len(jobs)
    for actor in [unit, camera, floor, *lights]:
        if actor:
            actors.destroy_actor(actor)
    save()
    unreal.SystemLibrary.quit_editor()


def aim(view):
    points = geometry['body']['vertices'] if view == 'full' else geometry['bandage']['vertices']
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    center = [(a+b)*50 for a,b in zip(low,high)]
    target = origin+unreal.Vector(*center)
    if view == 'full':
        distance = max(260., (high[2]-low[2])*210., (high[0]-low[0])*240.)
        offset = unreal.Vector(-distance*.35,-distance,distance*.25)
    else:
        sign = -1 if center[0] < 0 else 1
        offset = unreal.Vector(sign*30,-75 if view == 'front' else 75,20)
    camera.set_actor_location(target+offset,False,False)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),target),False)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())


def tick(delta):
    global unit,job_index,phase,deadline,timeout,current,geometry,capture_views,masked_pose
    if closed or time.monotonic() < deadline:
        return
    try:
        slug,kind,fraction = jobs[job_index]
        if phase == 'prepare':
            unit = unreal.OldWestAssetAuthoring.create_crew_wound_preview(world,slug,'wounded' if kind=='concealed' else kind,fraction,kind=='concealed',unit)
            assert unit, (slug,kind)
            unit.set_actor_location(origin,False,False)
            current = dict(slug=slug,pose=kind,fraction=fraction)
            phase = 'geometry'
            deadline,timeout = time.monotonic()+1.,time.monotonic()+90
            return
        if phase == 'geometry':
            state = json.loads(unreal.OldWestAssetAuthoring.describe_crew_wound_preview(unit,False))
            if not state.get('ready'):
                assert time.monotonic()<timeout, 'Mesh compilation did not finish'
                deadline=time.monotonic()+.2
                return
            expected = kind not in ('healthy','destroyed')
            assert state['bandage']['visible'] == expected and state['bandage']['collision_enabled']==0, state
            assert state['bandage']['follows_body']
            if kind == 'wounded':
                assert state['active_clip']=='Injured_Kneeling'
            elif kind in ('hit','attack','walk'):
                fragments = {'hit':('HitReact',),'attack':('Attack','Rifle_Fire'),'walk':('Walk',)}[kind]
                assert any(fragment in state['active_clip'] for fragment in fragments), state['active_clip']
            if kind == 'concealed':
                assert state['visual_id']=='punk' and state['card_id']=='punk'
                assert state['visual_mesh'].endswith('/SK_Drifter.SK_Drifter')
                assert state['bandage']['mesh'].endswith('/SK_Bandage_Drifter.SK_Bandage_Drifter')
                masked = json.dumps(state['bone_transforms'],sort_keys=True)
                if masked_pose is None:
                    masked_pose = masked
                assert masked == masked_pose, 'Concealed fit depends on private visual override'
            current['native'] = state
            capture_views = []
            if kind not in ('concealed','healthy','destroyed'):
                exported = json.loads(unreal.OldWestAssetAuthoring.describe_crew_wound_preview(unit,True))
                geometry = exported.pop('geometry')
                after_export = json.loads(unreal.OldWestAssetAuthoring.describe_crew_wound_preview(unit,False))
                if after_export['bone_transforms'] != state['bone_transforms']:
                    current['after_export'] = after_export
                    report['states'].append(current)
                    raise AssertionError('CPU export changed pose')
                folder=OUT/slug
                folder.mkdir(exist_ok=True)
                label=f'{kind}-{fraction:.2f}'
                destination=folder/(label+'.json.gz')
                with gzip.open(destination,'wt') as stream:
                    json.dump(dict(state=current,geometry=geometry),stream,separators=(',',':'))
                current['geometry'] = str(destination.relative_to(OUT))
                current['geometry_sha256'] = sha(destination)
                capture_views = ['full','front','rear'] if kind=='wounded' else ['front']
            report['states'].append(current)
            phase='aim' if capture_views else 'next'
            deadline=time.monotonic()+.1
            return
        if phase == 'aim':
            view=capture_views[0]
            aim(view)
            phase='capture'
            deadline=time.monotonic()+.4
            return
        if phase == 'capture':
            destination=OUT/slug/f'{kind}-{fraction:.2f}-{capture_views[0]}.png'
            assert not destination.exists()
            unreal.AutomationLibrary.take_high_res_screenshot(960,720,str(destination),camera=camera,delay=.1)
            phase='wait_image'
            deadline,timeout=time.monotonic()+.7,time.monotonic()+30
            return
        if phase == 'wait_image':
            destination=OUT/slug/f'{kind}-{fraction:.2f}-{capture_views[0]}.png'
            if not destination.exists() or not destination.read_bytes().endswith(b'IEND\xaeB`\x82'):
                assert time.monotonic()<timeout,'Incomplete screenshot'
                deadline=time.monotonic()+.1
                return
            state=json.loads(unreal.OldWestAssetAuthoring.describe_crew_wound_preview(unit,False))
            if state['bone_transforms'] != current['native']['bone_transforms']:
                current['after_capture'] = state
                raise AssertionError('Pose changed during capture')
            report['captures'].append(dict(slug=slug,pose=kind,fraction=fraction,view=capture_views.pop(0),path=str(destination.relative_to(OUT)),sha256=sha(destination)))
            phase='aim' if capture_views else 'next'
            deadline=time.monotonic()+.1
            return
        if phase == 'next':
            save()
            job_index+=1
            if job_index == len(jobs):
                finish()
                return
            if jobs[job_index][0]!=slug:
                unreal.log_warning('WOUND_ROSTER_CAPTURED '+slug)
            phase='prepare'
            deadline=time.monotonic()+.1
    except Exception:
        report['errors'].append(traceback.format_exc())
        unreal.log_error(report['errors'][-1])
        finish()


handle = unreal.register_slate_post_tick_callback(tick)
