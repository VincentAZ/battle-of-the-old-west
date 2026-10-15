"""Package the single-animal animation checkpoint with reproducible local sources.

Does not submit generation jobs, import assets, publish, cook, or change launcher.
Run after visual inspection of both studio/native previews and native readback.
"""
import hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/stampede/animation-v001'
APPEARANCE=OUT.parent/'review-v001'
CONTENT=ROOT/'game/OldWest/Content'
NATIVE=CONTENT/'Art/Western/StampedeStudy'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
source=read(OUT/'source-readback.json');native=read(OUT/'unreal-readback.json')
assert source['ok'] and native['ok'] and native['existing_content_unchanged']
assert sha(OUT/'Longhorn-Animated.blend')==source['project_sha256']==native['source_project_sha256']
for p,h in native['protected_content_sha256'].items():assert sha(CONTENT/p)==h,p
for p,h in native['new_assets_sha256'].items():assert sha(CONTENT/p)==h,p
baseline=read(APPEARANCE/'baseline.json')
for p,h in baseline['protected_sha256'].items():assert sha(ROOT/p)==h,p
assert str((ROOT/'dist/current').resolve())==baseline['current_package']
captures=read(OUT/'unreal-captures.json');sequence=read(OUT/'unreal-run-frames.json')
assert captures['ok'] and sequence['ok']
# The sequence run also rechecks the opposite heading with explicit yaw fields.
latest={v['file']:v for v in sequence['captures']}
captures['captures']=[latest.get(v['file'],v) for v in captures['captures']]
for v in captures['captures']+sequence['captures']:assert sha(OUT/v['file'])==v['sha256']
write(OUT/'unreal-captures.json',captures)
for name,frames,w,h in [('Longhorn-Idle.mp4',240,960,720),('Longhorn-Run.mp4',192,960,720),('Longhorn-Run-Unreal.mp4',192,1280,720)]:
    file=OUT/'previews'/name
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(file)]))['streams'][0]
    assert info['codec_name']=='h264' and info['pix_fmt']=='yuv420p'
    assert int(info['nb_frames'])==frames and info['width']==w and info['height']==h
validation={'stage':'B','status':'ready_for_user_animation_review','source':source,
    'native':{k:v for k,v in native.items() if k not in ['protected_content_sha256','new_assets_sha256']},
    'gameplay_baseline_unchanged':True,'protected_rule_ai_catalog_files':len(baseline['protected_sha256']),
    'existing_content_unchanged':True,'current_package_unchanged':True,
    'baseline_portable_tests':'Stage A rules and AI suites passed; unchanged hashes verified again; not rerun for asset-only work',
    'visual_inspection':'Studio key poses and native idle/run poses at 720p/1080p; user motion approval pending',
    'remaining_gates':['User animation approval','Three-animal herd integration and presentation mapping','Gameplay lifecycle/seeded equivalence tests','Separate packaged review build and performance comparison','User approval before launcher promotion']}
if (OUT/'editor-shutdown-diagnostic.json').exists():validation['editor_shutdown']=read(OUT/'editor-shutdown-diagnostic.json')
write(OUT/'validation-summary.json',validation)
manifest=read(OUT/'manifest.json')
manifest.update(status='ready_for_user_animation_review',unreal_imported=True,native_destination='/Game/Art/Western/StampedeStudy',
    native_forward='+Y',native_up='+Z',native_units='centimeters',gameplay_integrated=False,
    gameplay_baseline_unchanged=True,package_promoted=False,
    reports=['source-readback.json','unreal-readback.json','unreal-captures.json','unreal-run-frames.json','validation-summary.json'],
    previews=['previews/Longhorn-Idle.mp4','previews/Longhorn-Run.mp4','previews/Longhorn-Run-Unreal.mp4']+[v['file'] for v in captures['captures']])
write(OUT/'manifest.json',manifest)
files=[OUT/p for p in ['Longhorn-Animated.blend','Longhorn-Approved.glb','longhorn-rigged-original.glb','appearance-approval.json',
    'rig-request.json','rig-inspection.json','manifest.json','animation-validation.json','source-readback.json','export-settings.json',
    'expected-native-poses.json','unreal-import.json','unreal-readback.json','unreal-captures.json','unreal-run-frames.json','validation-summary.json','native-log-classification.json']]
files+=list((OUT/'exports').glob('*'))+list(NATIVE.glob('**/*.uasset'))
files += [p for p in (OUT/'previews').iterdir() if p.is_file() and p.suffix in {'.png','.jpg','.mp4'} and '-frame-' not in p.name]
files += [APPEARANCE/p for p in ['review/Longhorn-Review.blend','model-request.json','reference-v2-request.json','longhorn-reference-v2.png','baseline.json','baseline-core-tests.log','longhorn-original.glb']]
files += list((APPEARANCE/'review/textures').glob('*.png'))+list((ROOT/'scripts').glob('*stampede*.py'))+[ROOT/'game/STAMPEDE_PILOT.md']
for optional in ['editor-shutdown-diagnostic.json','editor-exit-control.json','editor-exit-control.py']:
    if (OUT/optional).exists():files.append(OUT/optional)
files=sorted(set(files));assert all(p.is_file() for p in files)
index={str(p.relative_to(ROOT)):sha(p) for p in files}
write(OUT/'bundle-files.json',index);files.append(OUT/'bundle-files.json')
archive=OUT/'Longhorn-Animation-Review.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in files:z.write(path,str(path.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
current={'stage':'B','approval':'awaiting_animation_review','project':'Longhorn-Animated.blend','bundle':archive.name,'bundle_sha256':sha(archive),'bundle_bytes':archive.stat().st_size,'next':'Approve idle/run animation before three-animal Stampede integration'}
write(OUT/'CURRENT.json',current)
print(json.dumps({'files':len(files),**current},indent=2))
