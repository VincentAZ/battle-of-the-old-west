#include "OldWestScientistPlayback.h"
#include "OldWestScientistClock.h"
#include "OldWestBattlefield.h"
#include "Core/json.hpp"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

using J = nlohmann::ordered_json;
using Phase = FOldWestScientistClock::EPhase;
namespace
{
FString String(const std::string& S) { return FString(UTF8_TO_TCHAR(S.c_str())); }
const TCHAR* PhaseName(Phase P)
{
    switch (P)
    {
    case Phase::EntryBlend: return TEXT("entry_blend"); case Phase::Holster: return TEXT("holster");
    case Phase::Inspect: return TEXT("inspect"); case Phase::WorkHold: return TEXT("work_hold");
    case Phase::SortLeft: return TEXT("sort_left"); case Phase::SortMiddle: return TEXT("sort_middle");
    case Phase::SortRight: return TEXT("sort_right"); case Phase::Recover: return TEXT("recover");
    case Phase::SkipRecover: return TEXT("skip_recover"); case Phase::NoChoiceRecover: return TEXT("no_choice_recover");
    case Phase::Unholster: return TEXT("unholster");
    case Phase::Complete: return TEXT("complete"); default: return TEXT("inactive");
    }
}
FTransform ReadTransform(const J& Row)
{
    if (!Row.is_array() || Row.size() != 10) throw std::runtime_error("Prospector transform needs10 values");
    for (const J& Value : Row) if (!Value.is_number() || !FMath::IsFinite(Value.get<double>()))
        throw std::runtime_error("Nonfinite Prospector transform");
    FQuat Q(Row[3].get<double>(), Row[4].get<double>(), Row[5].get<double>(), Row[6].get<double>());
    if (FMath::Abs(Q.SizeSquared() - 1.) > .0001) throw std::runtime_error("Nonunit Prospector quaternion");
    for (int32 I = 7; I < 10; ++I) if (FMath::Abs(Row[I].get<double>() - 1.) > .001)
        throw std::runtime_error("Prospector scale mismatch");
    Q.Normalize();
    return FTransform(Q, FVector(Row[0].get<double>(),Row[1].get<double>(),Row[2].get<double>()), FVector::OneVector);
}
FTransform Interpolate(const FTransform& A, const FTransform& B, double Alpha)
{
    return FTransform(FQuat::Slerp(A.GetRotation(),B.GetRotation(),Alpha).GetNormalized(),
        FMath::Lerp(A.GetLocation(),B.GetLocation(),Alpha),FVector::OneVector);
}
J TransformJson(const FTransform& T)
{
    const FVector P=T.GetLocation(); const FQuat Q=T.GetRotation();
    return {{"position",{P.X,P.Y,P.Z}},{"quaternion_xyzw",{Q.X,Q.Y,Q.Z,Q.W}}};
}
struct FScientistFrame { TMap<FName,FTransform> Props; FTransform Rifle; bool HasRifle=false; };
struct FTrack { double Duration=0.; TArray<FScientistFrame> Frames; };
struct FPart { FName Name; FString Asset; int32 SampleIndex=-1; FTransform Initial; };
}

struct FOldWestScientistPlaybackState
{
    FOldWestScientistClock Clock;
    FString MatchId, LastReason, Error, NoChoiceReason;
    int32 AbilitySequence=0;
    TArray<FOldWestAnalysisSample> Samples;
    TArray<FPart> Definitions;
    TMap<FName,FTrack> Tracks;
    TMap<FName,FTransform> CurrentProps, FrozenSamples;
    FTransform ParkedRifle, EntryRifle;
    FBox Workspace=FBox(ForceInit);
    J FinalProps=J::array(), FinalBody=nullptr, FinalRifle=nullptr, FinalUnitManual=nullptr;
    uint64 LastAdvanceFrame=MAX_uint64;
    int32 SampleCalls=0;
    bool Loaded=false, OwnsPose=false, RifleHeld=false;
    double NativeClipSeconds=0.;
    FName NativeClip;
};

void FOldWestScientistStateDeleter::operator()(FOldWestScientistPlaybackState* State) const
{
    delete State;
}

UOldWestScientistPlayback::UOldWestScientistPlayback()
{
    PrimaryComponentTick.bCanEverTick=false;
    State.Reset(new FOldWestScientistPlaybackState());
}
UOldWestScientistPlayback::~UOldWestScientistPlayback() = default;

bool UOldWestScientistPlayback::LoadBundle()
{
    if (State->Loaded) return true;
    FString Content;
    if (!FFileHelper::LoadFileToString(Content,*(FPaths::ProjectContentDir()/TEXT("Data/scientist-presentation.json"))))
    { State->Error=TEXT("Prospector presentation data missing"); return false; }
    try
    {
        const J Data=J::parse(TCHAR_TO_UTF8(*Content));
        if (Data.at("schema")!="oldwest.scientist.presentation.v1" || Data.at("fps")!=30 || Data.at("native_bones")!=54
            || Data.at("props").size()!=11 || Data.at("tracks").size()!=7)
            throw std::runtime_error("Prospector bundle schema/count mismatch");
        State->ParkedRifle=ReadTransform(Data.at("rifle_parked"));
        for (const J& Item:Data.at("props"))
        {
            FPart Part; Part.Name=FName(*String(Item.at("name").get<std::string>()));
            Part.Asset=String(Item.at("asset").get<std::string>()); Part.SampleIndex=Item.at("sample_index").get<int32>();
            Part.Initial=ReadTransform(Item.at("initial"));
            if (!Part.Asset.StartsWith(TEXT("/Game/Art/Survivors/ScientistAnalysis/Props/"))
                || Part.SampleIndex < -1 || Part.SampleIndex > 2) throw std::runtime_error("Prospector prop identity mismatch");
            for (const FPart& Existing:State->Definitions) if (Existing.Name==Part.Name) throw std::runtime_error("Duplicate Prospector prop");
            State->Definitions.Add(Part);
        }
        for (auto It=Data.at("tracks").begin(); It!=Data.at("tracks").end(); ++It)
        {
            const FName Name(*String(It.key())); const J& Item=It.value();
            const FString Asset=String(Item.at("asset").get<std::string>());
            if (Asset!=TEXT("/Game/Art/Survivors/ScientistAnalysis/Animations/A_Scientist_")+String(It.key())+TEXT("_Cm"))
                throw std::runtime_error("Prospector clip path mismatch");
            UAnimSequence* Clip=LoadObject<UAnimSequence>(nullptr,*Asset);
            FTrack Track; Track.Duration=Item.at("seconds").get<double>();
            if (!Clip || !FMath::IsFinite(Track.Duration) || Track.Duration<=0.
                || FMath::Abs(Clip->GetPlayLength()-Track.Duration)>.002)
                throw std::runtime_error("Prospector clip duration/load failure");
            Clips.Add(Name,Clip);
            const bool WeaponTrack=Name==TEXT("Holster") || Name==TEXT("Unholster");
            int32 Index=0;
            for (const J& Row:Item.at("frames"))
            {
                if (FMath::Abs(Row.at("time").get<double>()-Index/30.)>.00001) throw std::runtime_error("Prospector frame clock mismatch");
                FScientistFrame Frame;
                for (auto Prop=Row.at("props").begin(); Prop!=Row.at("props").end(); ++Prop)
                    Frame.Props.Add(FName(*String(Prop.key())),ReadTransform(Prop.value()));
                if (WeaponTrack) { Frame.Rifle=ReadTransform(Row.at("rifle")); Frame.HasRifle=true; }
                else if (Frame.Props.Num()!=10) throw std::runtime_error("Prospector prop frame incomplete");
                Track.Frames.Add(MoveTemp(Frame)); ++Index;
            }
            if (Track.Frames.Num()!=FMath::RoundToInt(Track.Duration*30.)+1) throw std::runtime_error("Prospector sample coverage mismatch");
            State->Tracks.Add(Name,MoveTemp(Track));
        }
        for (FName Name:{FName(TEXT("Full")),FName(TEXT("Holster")),FName(TEXT("Unholster")),FName(TEXT("WorkHold")),
            FName(TEXT("SortLeft")),FName(TEXT("SortRight")),FName(TEXT("SkipRecover"))})
            if (!State->Tracks.Contains(Name)) throw std::runtime_error("Prospector required track missing");
        State->Loaded=true; return true;
    }
    catch (const std::exception& Error)
    {
        State->Error=String(Error.what()); State->Definitions.Reset(); State->Tracks.Reset(); Clips.Reset();
        UE_LOG(LogTemp,Error,TEXT("OLDWEST_SCIENTIST_SCENE_ERROR %s"),*State->Error); return false;
    }
}

bool UOldWestScientistPlayback::Begin(AOldWestUnit* Unit,const FString& MatchId,int32 AbilitySequence,
    const TArray<FOldWestAnalysisSample>& PublicSamples)
{
    if (IsActive() || !IsValid(Unit) || GetWorld()!=Unit->GetWorld() || MatchId.IsEmpty() || AbilitySequence<=0 || PublicSamples.Num()>3) return false;
    TSet<int32> Handles;
    for (int32 I=0; I<PublicSamples.Num(); ++I)
        if (PublicSamples[I].Index!=I || PublicSamples[I].Handle<=0 || Handles.Contains(PublicSamples[I].Handle)) return false;
        else Handles.Add(PublicSamples[I].Handle);
    if (!LoadBundle()) return false;
    State->MatchId=MatchId; State->AbilitySequence=AbilitySequence; State->Samples=PublicSamples;
    State->Error.Reset(); State->LastReason.Reset(); State->NoChoiceReason.Reset(); State->FrozenSamples.Reset(); State->CurrentProps.Reset();
    State->FinalProps=J::array(); State->FinalBody=State->FinalRifle=State->FinalUnitManual=nullptr; State->SampleCalls=0;
    State->Workspace=FBox(ForceInit);
    Performer=Unit;
    State->EntryRifle=Unit->Weapon->GetComponentTransform().GetRelativeTransform(Unit->Body->GetComponentTransform());
    if (!Unit->BeginManualPresentation(this,FOldWestManualInterrupted::CreateUObject(this,&UOldWestScientistPlayback::Cancel,false)))
    { Performer=nullptr; return false; }
    State->OwnsPose=true;
    for (const FPart& Def:State->Definitions)
    {
        UStaticMesh* Asset=LoadObject<UStaticMesh>(nullptr,*Def.Asset);
        if (!Asset) { State->Error=TEXT("Missing Prospector prop: ")+Def.Asset; Cancel(State->Error); return false; }
        UStaticMeshComponent* Part=NewObject<UStaticMeshComponent>(Unit,NAME_None,RF_Transient);
        Unit->AddInstanceComponent(Part); Part->SetStaticMesh(Asset);
        Part->SetupAttachment(Unit->Body); Part->SetMobility(EComponentMobility::Movable);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision); Part->SetGenerateOverlapEvents(false);
        Part->SetCanEverAffectNavigation(false); Part->ComponentTags.Add(TEXT("OldWestScientistScene"));
        Part->SetRelativeTransform(Def.Initial); Part->SetVisibility(Def.SampleIndex<0 || Def.SampleIndex<PublicSamples.Num());
        Part->RegisterComponent(); Parts.Add(Part);
        // Include every prop's full authored trajectory before a camera chooses
        // a view. This also includes missing public sample positions as empty
        // workspace, but never renders or invents an unavailable sample.
        const FBox MeshBounds=Asset->GetBoundingBox();
        State->Workspace+=MeshBounds.TransformBy(Def.Initial);
        for (const auto& Pair:State->Tracks) for (const FScientistFrame& Frame:Pair.Value.Frames)
            if (const FTransform* Local=Frame.Props.Find(Def.Name)) State->Workspace+=MeshBounds.TransformBy(*Local);
    }
    if (const UStaticMesh* Rifle=Unit->Weapon->GetStaticMesh())
        for (const auto& Pair:State->Tracks) for (const FScientistFrame& Frame:Pair.Value.Frames)
            if (Frame.HasRifle) State->Workspace+=Rifle->GetBoundingBox().TransformBy(Frame.Rifle);
    State->Clock.Begin(); State->LastAdvanceFrame=MAX_uint64;
    if (!SampleCurrent(static_cast<int32>(Phase::EntryBlend),0.)) { Cancel(TEXT("entry_sample_failed")); return false; }
    return true;
}

bool UOldWestScientistPlayback::SetDecision(const FString& MatchId,int32 AbilitySequence,int32 Index,int32 Handle)
{
    if (!IsActive() || MatchId!=State->MatchId || AbilitySequence!=State->AbilitySequence) return false;
    if (Index==-1 ? Handle!=0 : !State->Samples.IsValidIndex(Index) || State->Samples[Index].Handle!=Handle) return false;
    return State->Clock.SetDecision(Index);
}

bool UOldWestScientistPlayback::FinishWithoutDecision(const FString& MatchId,int32 AbilitySequence,const FString& Reason)
{
    if (!IsActive() || MatchId!=State->MatchId || AbilitySequence!=State->AbilitySequence || Reason.IsEmpty()
        || !State->Clock.FinishWithoutDecision()) return false;
    State->NoChoiceReason=Reason; return true;
}

bool UOldWestScientistPlayback::SampleCurrent(int32 PhaseValue,double Seconds)
{
    if (!IsValid(Performer) || !Performer->OwnsManualPresentation(this) || Performer->IsVisuallyDead() || Performer->IsRagdoll()) return false;
    const Phase Current=static_cast<Phase>(PhaseValue);
    FName TrackName=TEXT("Full"); double Time=Seconds; float EntryAlpha=1.f;
    switch (Current)
    {
    case Phase::EntryBlend: TrackName=TEXT("Holster"); Time=0.; EntryAlpha=FMath::Clamp(Seconds/.3,0.,1.); break;
    case Phase::Holster: TrackName=TEXT("Holster"); break;
    case Phase::WorkHold: TrackName=TEXT("WorkHold"); break;
    case Phase::SortLeft: TrackName=TEXT("SortLeft"); break;
    case Phase::SortRight: TrackName=TEXT("SortRight"); break;
    case Phase::SortMiddle: Time+=134./30.; break;
    case Phase::Recover: Time+=184./30.; break;
    case Phase::SkipRecover: case Phase::NoChoiceRecover: TrackName=TEXT("SkipRecover"); break;
    case Phase::Unholster: TrackName=TEXT("Unholster"); break;
    default: break;
    }
    const FTrack* Track=State->Tracks.Find(TrackName); UAnimSequence* Clip=Clips.FindRef(TrackName);
    if (!Track || !Clip || Time<0. || Time>Track->Duration+.00001) return false;
    if (!Performer->SampleManualPresentation(this,Clip,Time,EntryAlpha,PhaseName(Current))) return false;
    State->NativeClip=TrackName; State->NativeClipSeconds=Time; ++State->SampleCalls;
    const double Frame=FMath::Clamp(Time*30.,0.,static_cast<double>(Track->Frames.Num()-1));
    const int32 A=FMath::FloorToInt(Frame), B=FMath::Min(A+1,Track->Frames.Num()-1); const double Alpha=Frame-A;
    const FScientistFrame& First=Track->Frames[A]; const FScientistFrame& Last=Track->Frames[B];
    for (int32 I=0; I<State->Definitions.Num(); ++I)
    {
        const FPart& Def=State->Definitions[I]; FTransform Local=Def.Initial;
        if (const FTransform* Start=First.Props.Find(Def.Name))
        {
            const FTransform* End=Last.Props.Find(Def.Name); if (!End) return false;
            Local=Interpolate(*Start,*End,Alpha);
        }
        if (Current==Phase::Recover && Def.SampleIndex>=0)
        {
            const FTransform* Frozen=State->FrozenSamples.Find(Def.Name); if (!Frozen) return false;
            Local=*Frozen;
        }
        // During Unholster, preserve the closed case and actual sample state
        // left by Recover/Skip instead of restoring an initial fake selection.
        if (Current==Phase::Unholster && Def.Name!=TEXT("RifleHolster_Receiver"))
            if (const FTransform* Previous=State->CurrentProps.Find(Def.Name)) Local=*Previous;
        Parts[I]->SetRelativeTransform(Local); State->CurrentProps.Add(Def.Name,Local);
    }
    FTransform Rifle=First.HasRifle ? Interpolate(First.Rifle,Last.Rifle,Alpha) : State->ParkedRifle;
    if (Current==Phase::EntryBlend)
    {
        Rifle=Interpolate(State->EntryRifle,Rifle,EntryAlpha);
        // Keep actual right-palm contact while blending from the currently
        // displayed ordinary pose; a linear transform alone can slide the grip.
        const FVector PalmBody=Performer->Body->GetComponentTransform().InverseTransformPosition(Performer->ManualPresentationPalm(this,true));
        Rifle.SetLocation(PalmBody-Rifle.GetRotation().RotateVector(FVector(-1.8f,-1.f,-.7f)));
    }
    State->RifleHeld=Current==Phase::EntryBlend || (Current==Phase::Holster && Seconds<=64./30.)
        || (Current==Phase::Unholster && Seconds>=26./30.);
    return Performer->SetManualPresentationRifle(this,Rifle,State->RifleHeld);
}

bool UOldWestScientistPlayback::PhaseBoundary(int32 PreviousValue,int32 FollowingValue)
{
    const Phase Previous=static_cast<Phase>(PreviousValue), Following=static_cast<Phase>(FollowingValue);
    if (Following==Phase::Recover)
    {
        State->FrozenSamples.Reset();
        for (const FPart& Def:State->Definitions) if (Def.SampleIndex>=0)
        {
            const FTransform* Actual=State->CurrentProps.Find(Def.Name); if (!Actual) return false;
            State->FrozenSamples.Add(Def.Name,*Actual);
        }
    }
    if (Previous==Phase::Unholster && Following==Phase::Complete) Release(TEXT("completed"),true,true);
    return true;
}

bool UOldWestScientistPlayback::Advance(float DeltaSeconds)
{
    if (State->Clock.Phase==Phase::Complete) return true;
    if (!IsActive()) return false;
    if (State->LastAdvanceFrame==GFrameCounter) return true; // No duplicate time from two director paths.
    State->LastAdvanceFrame=GFrameCounter;
    if (!State->Clock.Advance(DeltaSeconds,[this](Phase P,double Time){return SampleCurrent(static_cast<int32>(P),Time);},
        [this](Phase A,Phase B){return PhaseBoundary(static_cast<int32>(A),static_cast<int32>(B));}))
    { Cancel(TEXT("manual_pose_or_clock_invalid"),true); return false; }
    return true;
}
bool UOldWestScientistPlayback::IsAwaitingChoice() const { return IsActive() && State->Clock.AwaitingChoice(); }
bool UOldWestScientistPlayback::IsComplete() const { return State->Clock.Phase==Phase::Complete; }
bool UOldWestScientistPlayback::IsActive() const { return State->OwnsPose && IsValid(Performer); }
FString UOldWestScientistPlayback::GetPhaseName() const { return PhaseName(State->Clock.Phase); }
FBox UOldWestScientistPlayback::GetSceneBounds() const
{
    FBox Bounds(ForceInit);
    if (IsValid(Performer))
    {
        Bounds+=Performer->GetVisualBounds();
        if (State->Workspace.IsValid) Bounds+=State->Workspace.TransformBy(Performer->Body->GetComponentTransform());
        if (Performer->Weapon->IsVisible()) Bounds+=Performer->Weapon->Bounds.GetBox();
    }
    for (const UStaticMeshComponent* Part:Parts) if (IsValid(Part) && Part->IsVisible()) Bounds+=Part->Bounds.GetBox();
    return Bounds;
}
TArray<FVector> UOldWestScientistPlayback::GetVisibilityPoints() const
{
    TArray<FVector> Points;
    if (IsValid(Performer))
    {
        Points.Add(Performer->GetPresentationFocus());
        for (FName Name:{FName(TEXT("Head")),FName(TEXT("LeftHand")),FName(TEXT("RightHand")),FName(TEXT("LeftFoot")),FName(TEXT("RightFoot"))})
            if (Performer->Body->GetBoneIndex(Name)!=INDEX_NONE) Points.Add(Performer->Body->GetSocketLocation(Name)+FVector(0,0,4));
        if (Performer->Weapon->IsVisible()) Points.Add(Performer->Weapon->Bounds.Origin);
    }
    for (const UStaticMeshComponent* Part:Parts) if (IsValid(Part) && Part->IsVisible()) Points.Add(Part->Bounds.Origin+FVector(0,0,4));
    return Points;
}
bool UOldWestScientistPlayback::IsCaseLidObstructing(const FVector& CameraPosition) const
{
    if (!IsValid(Performer) || !IsActive()) return false;
    const UStaticMeshComponent* Lid=nullptr;
    for (int32 I=0; I<State->Definitions.Num() && I<Parts.Num(); ++I)
        if (State->Definitions[I].Name==TEXT("AnalysisCase_Lid_Hinge")) { Lid=Parts[I].Get(); break; }
    if (!IsValid(Lid) || !Lid->IsVisible() || !Lid->GetStaticMesh()) return false;
    // The solid case lid has no gameplay collision. Its oriented local mesh
    // bounds are a conservative camera occluder; a whole-workspace box would
    // incorrectly treat the open air above the trays as opaque.
    const FTransform World=Lid->GetComponentTransform();
    const FBox Bounds=Lid->GetStaticMesh()->GetBoundingBox();
    const FVector LocalCamera=World.InverseTransformPosition(CameraPosition);
    TArray<FVector> Points;
    Points.Add(Performer->Body->GetSocketLocation(TEXT("Head")));
    // The authored lid opens to70 degrees. Until it reaches that working
    // position, covering the trays and the hand closing/opening it is expected.
    // Demanding visibility through a half-closed case made the camera orbit
    // behind the Prospector; only the open workspace needs these extra rays.
    const bool WorkspaceOpen=Lid->GetRelativeTransform().GetRotation().GetAngle()>=FMath::DegreesToRadians(69.f);
    if (WorkspaceOpen)
    {
        const Phase Current=State->Clock.Phase;
        const bool Working=Current==Phase::WorkHold || Current==Phase::SortLeft || Current==Phase::SortMiddle
            || Current==Phase::SortRight || (Current==Phase::Inspect && State->NativeClipSeconds>=80./30.);
        // The right hand passes behind the raised lid while releasing its
        // handle and while reaching back to close it. Keep the face framed
        // through those expected brief occlusions; demand both palms during
        // the authored Scan segment and the player's selected sample work.
        if (Working)
        {
            Points.Add(Performer->ManualPresentationPalm(this,false));
            Points.Add(Performer->ManualPresentationPalm(this,true));
        }
        for (int32 I=0; I<State->Definitions.Num() && I<Parts.Num(); ++I)
            if (IsValid(Parts[I]) && Parts[I]->IsVisible() && (State->Definitions[I].SampleIndex>=0
                || State->Definitions[I].Name==TEXT("HandScanner_GripAnchor"))) Points.Add(Parts[I]->Bounds.Origin);
    }
    for (const FVector& Point:Points)
    {
        const FVector LocalPoint=World.InverseTransformPosition(Point);
        // A hand touching the lid or a sample enclosed by the closed case is
        // not a visibility demand through solid material.
        if (Bounds.ExpandBy(1.f).IsInsideOrOn(LocalPoint)) continue;
        if (FMath::LineBoxIntersection(Bounds,LocalPoint,LocalCamera,LocalCamera-LocalPoint)) return true;
    }
    return false;
}

void UOldWestScientistPlayback::Release(const FString& Reason,bool ResumeLivingIdle,bool Completed)
{
    State->LastReason=Reason;
    if (!Parts.IsEmpty())
    {
        const J Final=J::parse(TCHAR_TO_UTF8(*GetDebugJson()));
        State->FinalProps=Final.at("props"); State->FinalBody=Final.value("body",J(nullptr)); State->FinalRifle=Final.value("rifle",J(nullptr));
        State->FinalUnitManual=Final.value("unit_manual",J(nullptr));
    }
    if (IsValid(Performer) && State->OwnsPose) Performer->EndManualPresentation(this,ResumeLivingIdle,Completed);
    State->OwnsPose=false;
    for (UStaticMeshComponent* Part:Parts) if (IsValid(Part))
    { if (AActor* Owner=Part->GetOwner()) Owner->RemoveInstanceComponent(Part); Part->DestroyComponent(); }
    Parts.Reset();
}
void UOldWestScientistPlayback::Cancel(const FString& Reason,bool ResumeLivingIdle)
{
    Release(Reason,ResumeLivingIdle,false); State->Clock.Cancel();
}
void UOldWestScientistPlayback::EndPlay(const EEndPlayReason::Type Reason)
{
    Cancel(TEXT("end_play"),false); Super::EndPlay(Reason);
}
FString UOldWestScientistPlayback::GetDebugJson() const
{
    J Out={{"active",IsActive()},{"complete",IsComplete()},{"awaiting_choice",IsAwaitingChoice()},
        {"live_prop_count",Parts.Num()},{"retained_props_after_cleanup",Parts.IsEmpty()&&!State->FinalProps.empty()},
        {"match_id",std::string(TCHAR_TO_UTF8(*State->MatchId))},{"analysis_sequence",State->AbilitySequence},
        {"phase",std::string(TCHAR_TO_UTF8(PhaseName(State->Clock.Phase)))},{"phase_seconds",State->Clock.Seconds},
        {"total_seconds",State->Clock.TotalSeconds},{"selected_index",State->Clock.Decision},
        {"no_choice_recovery",State->Clock.NoChoice},{"no_choice_reason",std::string(TCHAR_TO_UTF8(*State->NoChoiceReason))},
        {"manual_pose_owned",State->OwnsPose},{"rifle_held",State->RifleHeld},
        {"clip",std::string(TCHAR_TO_UTF8(*State->NativeClip.ToString()))},{"clip_seconds",State->NativeClipSeconds},
        {"sample_calls",State->SampleCalls},{"last_reason",std::string(TCHAR_TO_UTF8(*State->LastReason))},
        {"error",std::string(TCHAR_TO_UTF8(*State->Error))},{"props",Parts.IsEmpty()?State->FinalProps:J::array()},
        {"last_sample_body",State->FinalBody},{"last_sample_rifle",State->FinalRifle},{"last_sample_unit_manual",State->FinalUnitManual}};
    for (int32 I=0; I<Parts.Num(); ++I)
    {
        const FPart& Def=State->Definitions[I]; const UStaticMeshComponent* Part=Parts[I].Get();
        Out["props"].push_back({{"name",std::string(TCHAR_TO_UTF8(*Def.Name.ToString()))},{"visible",Part->IsVisible()},
            {"sample_index",Def.SampleIndex},{"public_handle",State->Samples.IsValidIndex(Def.SampleIndex)?State->Samples[Def.SampleIndex].Handle:0},
            {"local",TransformJson(Part->GetRelativeTransform())},{"world",TransformJson(Part->GetComponentTransform())}});
    }
    if (IsValid(Performer))
    {
        Out["performer_id"]=Performer->EntityId; Out["performer_side"]=Performer->Side;
        Out["unit_manual"]=J::parse(TCHAR_TO_UTF8(*Performer->GetManualPresentationDebug()));
        if (const UAnimSequence* Clip=Clips.FindRef(State->NativeClip)) Out["clip_asset"]=std::string(TCHAR_TO_UTF8(*Clip->GetPathName()));
        Out["body"]=TransformJson(Performer->Body->GetComponentTransform());
        Out["rifle"]=TransformJson(Performer->Weapon->GetComponentTransform());
        if (State->OwnsPose && State->RifleHeld)
            Out["held_right_palm_gap_cm"]=FVector::Distance(Performer->ManualPresentationPalm(const_cast<UOldWestScientistPlayback*>(this),true),
                Performer->Weapon->GetComponentTransform().TransformPosition(FVector(-1.8f,-1.f,-.7f)));
    }
    return String(Out.dump());
}
