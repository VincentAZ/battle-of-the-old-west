"""Generate Unit-only/build-data patches and copies manifest; no live edits."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'art/characters/scientist_gesture/playback-stage'
OUT=STAGE/'unit-integration-build17'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
CPP='game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp'
HEADER='game/OldWest/Source/OldWestGame/Public/OldWestBattlefield.h'
BUILD='game/OldWest/Source/OldWestGame/OldWestGame.Build.cs'
before={path:(ROOT/path).read_text() for path in (CPP,HEADER,BUILD)}
source_hashes={path:sha(ROOT/path) for path in before}
assert source_hashes[CPP].startswith('2d3b610'),('Expected frozen build17 Unit baseline',source_hashes[CPP])
cpp,header,build=(before[path] for path in (CPP,HEADER,BUILD))


def one(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new,1)


def edit_unit(name,edit):
    global cpp
    start=cpp.index('AOldWestUnit::'+name+'(')
    end=cpp.index('\n}\n',start)+3
    old=cpp[start:end]
    cpp=cpp[:start]+edit(old)+cpp[end:]


def prefix(name,line):
    edit_unit(name,lambda block:one(block,'\n{\n','\n{\n    '+line+'\n'))


cpp=one(cpp,'#include "Animation/AnimSingleNodeInstance.h"','#include "Animation/AnimSingleNodeInstance.h"\n#include "OldWestManualAnimInstance.h"')
for name,reason in [('Configure','configure'),('ConfigureEvent','configure_event'),('ResetPose','reset_pose'),
                    ('StageTravel','travel'),('PlayAction','ordinary_action'),('StartRagdoll','ragdoll'),('AimAt','aim_change')]:
    prefix(name,f'InterruptManualPresentation(TEXT("{reason}"));')
prefix('SetCondition','if (Destroyed) InterruptManualPresentation(TEXT("destroyed_condition"));')
for name in ('PlayClip','PlayIdle','AlignWeaponToHands'):
    prefix(name,'if (HasManualPresentation()) return;')


def tick(block):
    block=one(block,'if (!Camp && !EventToken && !Ragdoll && Body->GetSkeletalMeshAsset())',
              'if (!HasManualPresentation() && !Camp && !EventToken && !Ragdoll && Body->GetSkeletalMeshAsset())')
    block=one(block,'if (AnimationTime > 0.f)','if (!HasManualPresentation() && AnimationTime > 0.f)')
    return one(block,'if (!Camp && !EventToken && !Unarmed && !Dead && Body->GetSkeletalMeshAsset())',
               'if (!HasManualPresentation() && !Camp && !EventToken && !Unarmed && !Dead && Body->GetSkeletalMeshAsset())')
edit_unit('Tick',tick)


def idle_debug(block):
    return one(block,'    Result["animation_play_rate"] = Instance ? Instance->GetPlayRate() : 0.f;',
        '    Result["animation_play_rate"] = Instance ? Instance->GetPlayRate() : 0.f;\n'
        '    Result["manual_presentation"] = J::parse(TCHAR_TO_UTF8(*GetManualPresentationDebug()));')
edit_unit('GetIdleDebug',idle_debug)


def completed_debug(block):
    block=one(block,'const bool Eligible = !Camp','const bool Eligible = !HasManualPresentation() && !Camp')
    return one(block,'    if (Eligible)\n','    Result["manual_presentation"] = J::parse(TCHAR_TO_UTF8(*GetManualPresentationDebug()));\n    if (Eligible)\n')
edit_unit('SampleCompletedWeaponObservation',completed_debug)
methods=(STAGE/'unit-methods.cpp.inc').read_text()
methods=methods[methods.index('bool AOldWestUnit::BeginManualPresentation'):]
cpp=one(cpp,'AOldWestBattlefield::AOldWestBattlefield()',methods+'\nAOldWestBattlefield::AOldWestBattlefield()')

api=(STAGE/'unit-api.h.inc').read_text()
forwards=api.split('// Forward declarations / delegate before AOldWestUnit:\n',1)[1].split('// AOldWestUnit public:',1)[0]
public=api.split('// AOldWestUnit public:\n',1)[1].split('// AOldWestUnit private:',1)[0]
private=api.split('// AOldWestUnit private:\n',1)[1]
indent=lambda value:'\n'.join('    '+line if line else '' for line in value.rstrip().splitlines())+'\n'
header=one(header,'struct FOldWestPresentation;','struct FOldWestPresentation;\nclass USceneComponent;\n'+forwards.rstrip())
header=one(header,'    void ConfigureEvent(',indent(public)+'    void ConfigureEvent(')
header=one(header,'    void PlayClip(',indent(private)+'    void PlayClip(')
build=one(build,'        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/cards.json", StagedFileType.UFS);',
    '        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/cards.json", StagedFileType.UFS);\n'
    '        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/scientist-presentation.json", StagedFileType.UFS);')
after={CPP:cpp,HEADER:header,BUILD:build}
OUT.mkdir(parents=True,exist_ok=True)
patch=''.join(''.join(difflib.unified_diff(before[path].splitlines(True),after[path].splitlines(True),
    fromfile='a/'+path,tofile='b/'+path)) for path in before)
for path in before:
    (OUT/(Path(path).name+'.before')).write_text(before[path])
    (OUT/(Path(path).name+'.proposed')).write_text(after[path])
(OUT/'scientist-unit-only.patch').write_text(patch)
copies=[]
for path in sorted((STAGE/'source').glob('*')):
    copies.append({'source':str(path.relative_to(ROOT)),'destination':'game/OldWest/Source/OldWestGame/Private/'+path.name,'sha256':sha(path)})
data=STAGE/'Data/scientist-presentation.json'
copies.append({'source':str(data.relative_to(ROOT)),'destination':'game/OldWest/Content/Data/scientist-presentation.json','sha256':sha(data)})
for item in copies:
    assert not (ROOT/item['destination']).exists(),('Preserve existing destination; coordinate explicit replacement',item['destination'])
assert source_hashes=={path:sha(ROOT/path) for path in before},'Live source changed while staging'
manifest={'status':'staged_only_no_live_source_or_content_mutation','baseline_sha256':source_hashes,
    'proposed_sha256':{path:hashlib.sha256(after[path].encode()).hexdigest() for path in after},
    'patch':str((OUT/'scientist-unit-only.patch').relative_to(ROOT)),
    'patch_sha256':sha(OUT/'scientist-unit-only.patch'),'new_files':copies,
    'unit_scope':['exact manual-pose API and implementation','7 external interruption guards plus destroyed condition',
        '3 ordinary clip/alignment method guards','3 Unit.Tick ownership guards',
        'completed-frame and ordinary debug fields with narrow carried-rifle eligibility gate'],
    'build_scope':'Stage only the additional Prospector JSON UFS dependency',
    'release_policy':'Living actors always restore captured ordinary policy, including Cancel(false); existing ragdolls retain physics-owned state; dead pending actors keep the last pose without idle.',
    'requires':['Apply BF orchestration independently to same baseline, dry-run both orders','UHT and native compile','Actual legal branch/contact/cleanup and strict fall regression'],
    'generator_sha256':sha(__file__)}
(OUT/'copy-and-patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'patch':manifest['patch'],'new_files':len(copies),'baseline':source_hashes[CPP],'live_changed':False}))
