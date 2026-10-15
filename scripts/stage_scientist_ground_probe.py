"""Stage a nonshipping, observation-only exact-sole terrain probe; no live edits."""
import difflib
import json
from pathlib import Path
from scientist_import_contract import ROOT,BASE,require,read,sha

out=BASE/'playback-stage/ground-probe-stage'
landmarks=out/'sole-landmarks-v2.json'
data=read(landmarks)
for path,digest in data['source_provenance'].items():require(sha(path)==digest,'Source changed',path)
live=ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp'
text=live.read_text()
header='''#pragma once

// Generated from exact original Prospector outsole/tread mesh vertices.
// Each selected vertex has weight1 on the named Foot bone. Six per foot,
// including the lowest tread point; this is not a whole-surface support proof.
namespace OldWestScientistSoles {
struct FPoint { const TCHAR* Side; const TCHAR* Object; int32 Vertex; const TCHAR* Bone; double X,Y,Z; };
static const FPoint Points[] = {
'''
for p in data['points']:
    require(len(p['weights'])==1 and abs(p['weights'][0]['weight']-1)<1e-7,'Probe must retain complete actual skin weights')
    w=p['weights'][0]
    header+='    {TEXT("%s"),TEXT("%s"),%d,TEXT("%s"),%.12g,%.12g,%.12g},\n'%(p['side'],p['object'],p['vertex'],w['bone'],*w['bone_local_cm'])
header+='};\n}\n'
code='''        // Observation only: exact source sole vertices transformed by the
        // current evaluated Foot bones; no teleport, IK, animation or physics write.
        J GroundProbe={{"read_only",true},{"query_frame",GFrameCounter},
            {"sample_frame",ManualSampleFrame},{"bone_frame",Body->GetCurrentBoneTransformFrame()},
            {"source_landmarks_sha256","LANDMARK_SHA"},{"points",J::array()}};
        const bool SourceMeshMatches=Body->GetSkeletalMeshAsset() &&
            Body->GetSkeletalMeshAsset()->GetPathName()==TEXT("/Game/Art/Survivors/Variants/SKM_Prospector_Cm.SKM_Prospector_Cm");
        GroundProbe["source_mesh_matches"]=SourceMeshMatches;
        if (UWorld* World=GetWorld(); World && SourceMeshMatches)
        {
            FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestScientistSoleGround),true);
            Query.AddIgnoredActor(this); // Also excludes this scene's decorative props.
            for (const auto& Point:OldWestScientistSoles::Points)
            {
                const FName Bone(Point.Bone);
                const bool BoneValid=Body->GetBoneIndex(Bone)!=INDEX_NONE;
                J Row={{"side",TCHAR_TO_UTF8(Point.Side)},{"source_object",TCHAR_TO_UTF8(Point.Object)},
                    {"source_vertex",Point.Vertex},{"bone",TCHAR_TO_UTF8(Point.Bone)},{"bone_valid",BoneValid}};
                if (BoneValid)
                {
                    const FVector Sole=Body->GetSocketTransform(Bone,RTS_World).TransformPosition(FVector(Point.X,Point.Y,Point.Z));
                    const FVector Start=Sole+FVector(0,0,150),End=Sole-FVector(0,0,150);
                    FHitResult Hit;
                    const bool Found=World->LineTraceSingleByChannel(Hit,Start,End,ECC_Visibility,Query);
                    Row["sole_world"]=Vector(Sole); Row["trace_start"]=Vector(Start); Row["trace_end"]=Vector(End);
                    Row["hit"]=Found;
                    if (Found)
                    {
                        Row["ground_world"]=Vector(Hit.ImpactPoint); Row["normal"]=Vector(Hit.ImpactNormal);
                        Row["vertical_clearance_cm"]=Sole.Z-Hit.ImpactPoint.Z;
                        Row["normal_clearance_cm"]=FVector::DotProduct(Sole-Hit.ImpactPoint,Hit.ImpactNormal);
                        Row["component"]=Hit.GetComponent()?std::string(TCHAR_TO_UTF8(*Hit.GetComponent()->GetPathName())):std::string();
                        Row["actor"]=Hit.GetActor()?std::string(TCHAR_TO_UTF8(*Hit.GetActor()->GetPathName())):std::string();
                        const UStaticMeshComponent* Surface=Cast<UStaticMeshComponent>(Hit.GetComponent());
                        Row["surface_mesh"]=Surface&&Surface->GetStaticMesh()?std::string(TCHAR_TO_UTF8(*Surface->GetStaticMesh()->GetPathName())):std::string();
                    }
                }
                GroundProbe["points"].push_back(MoveTemp(Row));
            }
        }
        Out["ground_probe"]=MoveTemp(GroundProbe);
'''.replace('LANDMARK_SHA',sha(landmarks))
start=text.index('FString AOldWestUnit::GetManualPresentationDebug() const')
prefix,method=text[:start],text[start:]
anchor='        Out["saved_policy"]='
require(method.count(anchor)==1,'Ground probe insertion anchor changed')
method=method.replace(anchor,code+anchor,1)
include='#include "OldWestScientistSoleLandmarks.h"\n'
require(prefix.count('#include "OldWestBattlefield.h"\n')==1,'Primary Unreal include changed')
proposed=prefix.replace('#include "OldWestBattlefield.h"\n','#include "OldWestBattlefield.h"\n'+include,1)+method
patch=''.join(difflib.unified_diff(text.splitlines(True),proposed.splitlines(True),
    fromfile='a/game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp',
    tofile='b/game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp'))
files={'OldWestScientistSoleLandmarks.h':header,'scientist-ground-probe.patch':patch,'ground-probe-snippet.cpp.inc':code}
for name,value in files.items():
    path=out/name;require(not path.exists(),'Preserve staged file',path);path.write_text(value)
manifest={'status':'staged only; no native compilation or terrain evidence', 'baseline':{'path':str(live),'sha256':sha(live)},
          'patch':{'path':str(out/'scientist-ground-probe.patch'),'sha256':sha(out/'scientist-ground-probe.patch')},
          'copy':{'source':str(out/'OldWestScientistSoleLandmarks.h'),
                  'destination':'game/OldWest/Source/OldWestGame/Private/OldWestScientistSoleLandmarks.h',
                  'sha256':sha(out/'OldWestScientistSoleLandmarks.h')},'landmarks_sha256':sha(landmarks),
          'scope':'Nonshipping manual presentation debug only, exact Prospector mesh path, 12 read-only complex visibility traces when queried.',
          'limits':['Six sampled source-geometry points per foot; no complete GPU skin or surface-support proof.',
                    'Surface mesh/actor identity retained; a prop or rock hit must not be labelled terrain automatically.',
                    'Do not assert zero clearance during legitimate Holster/Unholster stepping.',
                    'No change to pose, movement, collisions, physics, timing, camera or game state.']}
(out/'proposal.json').write_text(json.dumps(manifest,indent=2)+'\n')
require(sha(live)==manifest['baseline']['sha256'],'Live source changed during staging')
print(json.dumps({'patch':str(out/'scientist-ground-probe.patch'),'points':12,'live_unchanged':True}))
