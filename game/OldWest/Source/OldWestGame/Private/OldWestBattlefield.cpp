#include "OldWestStampedeVisuals.h"
#include "OldWestDeliveryVisuals.h"
#include "OldWestDisplayNames.h"
#include "OldWestCrewCatalog.h"
#include "OldWestTroubleCatalog.h"
#include "OldWestExpansionHoldings.h"
#include "OldWestBattlefield.h"
#include "OldWestScientistSoleLandmarks.h"
#include "OldWestAnalysisPresentation.h"
#include "OldWestScientistPlayback.h"
#include "OldWestSession.h"
#include "OldWestCampVisuals.h"
#include "Core/json.hpp"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "OldWestManualAnimInstance.h"
#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/AudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/Material.h"
#include "Engine/Texture2D.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundAttenuation.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "PrimitiveSceneProxy.h"
#include "DrawDebugHelpers.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#if !UE_BUILD_SHIPPING
#include "RenderTimer.h"
#include "DynamicRHI.h"
#include "HAL/PlatformFileManager.h"
#include "PhysicsPublic.h"
#endif

using J = nlohmann::ordered_json;
namespace {
FString Text(const std::string& S) { return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(S.c_str()))); }
#if !UE_BUILD_SHIPPING
bool ProfilePresentation()
{
    static const bool Enabled = FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
        FParse::Param(FCommandLine::Get(), TEXT("OldWestPresentationProfile"));
    return Enabled;
}
struct FRagdollContactRecorder
{
    FString Path;
    bool Requested = false;
    bool WriteFailed = false;
    uint64 NextFallId = 0;
    uint64 WriteCalls = 0, BytesWritten = 0;
    double WriteSeconds = 0., MaxWriteSeconds = 0.;
    TUniquePtr<IFileHandle> Stream;
    std::string Pending;
    FRagdollContactRecorder()
    {
        Requested = FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
            FParse::Value(FCommandLine::Get(), TEXT("OldWestRagdollContactReport="), Path);
        if (Requested)
        {
            IPlatformFile& Files = FPlatformFileManager::Get().GetPlatformFile();
            // The harness supplies a fresh run directory. Refuse an existing
            // report rather than truncating evidence from an earlier run.
            if (!Files.FileExists(*Path)) Stream.Reset(Files.OpenWrite(*Path, false, true));
            if (!Stream) UE_LOG(LogTemp, Error, TEXT("OLDWEST_CONTACT_REPORT_ERROR: cannot create %s"), *Path);
        }
    }
    ~FRagdollContactRecorder() { Drain(); }
    bool Enabled() const { return Stream && !WriteFailed; }
    bool Write(const J& Event)
    {
        if (!Enabled()) return false;
        Pending += Event.dump();
        Pending += '\n';
        return Pending.size() < 65536 || Drain();
    }
    bool Drain()
    {
        if (!Enabled()) return false;
        if (Pending.empty()) return true;
        const double Started = FPlatformTime::Seconds();
        const bool Written = Stream->Write(reinterpret_cast<const uint8*>(Pending.data()), Pending.size());
        const double Seconds = FPlatformTime::Seconds() - Started;
        ++WriteCalls;
        WriteSeconds += Seconds;
        MaxWriteSeconds = FMath::Max(MaxWriteSeconds, Seconds);
        if (Written) BytesWritten += Pending.size();
        else
        {
            WriteFailed = true;
            UE_LOG(LogTemp, Error, TEXT("OLDWEST_CONTACT_REPORT_ERROR: cannot write %s"), *Path);
        }
        Pending.clear();
        // Make complete JSON lines visible to the harness without calling
        // IFileHandle::Flush (fdatasync on Linux) on the game thread.
        return Written;
    }
};
FRagdollContactRecorder& RagdollContacts()
{
    static FRagdollContactRecorder Recorder;
    return Recorder;
}
#endif
bool DiagnosticFallHold()
{
#if !UE_BUILD_SHIPPING
    static const bool Enabled = FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
        FParse::Param(FCommandLine::Get(), TEXT("OldWestCinematicDiagnostic"));
    return Enabled;
#else
    return false;
#endif
}
float PersonFallTimeLimit()
{
#if !UE_BUILD_SHIPPING
    // A grounded rolling fall can naturally settle after four seconds. Allow
    // that active shot up to six seconds; the queue budget and Skip stay separate.
    // Preserve the older forced four-second diagnostic hold for comparisons.
    static const float Limit = []()
    {
        const float Default = DiagnosticFallHold() ? 4.f : 6.f;
        float Seconds = Default;
        if (!FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) ||
            !FParse::Value(FCommandLine::Get(), TEXT("OldWestFallTimeLimit="), Seconds) ||
            !FMath::IsFinite(Seconds) || Seconds < 4.f || Seconds > 6.f) return Default;
        return Seconds;
    }();
    return Limit;
#else
    return 6.f;
#endif
}
void DrawFallDiagnostics(UWorld* World, USkeletalMeshComponent* Body)
{
#if !UE_BUILD_SHIPPING
    if (!DiagnosticFallHold() || !Body->GetPhysicsAsset()) return;
    for (const FBodyInstance* Instance : Body->Bodies) if (Instance && Instance->IsValidBodyInstance())
    {
        const FName Bone = Body->GetBoneName(Instance->InstanceBoneIndex);
        const int32 Index = Body->GetPhysicsAsset()->FindBodyIndex(Bone);
        if (Index == INDEX_NONE) continue;
        const USkeletalBodySetup* Setup = Body->GetPhysicsAsset()->SkeletalBodySetups[Index];
        const FTransform BodyWorld = Instance->GetUnrealWorldTransform();
        // Cm survivor scale is one. Use the actual body transform, not an
        // actor transform or a reference-pose approximation of the collider.
        for (const FKBoxElem& Shape : Setup->AggGeom.BoxElems)
        {
            const FTransform ShapeWorld = Shape.GetTransform() * BodyWorld;
            DrawDebugBox(World, ShapeWorld.GetLocation(), FVector(Shape.X, Shape.Y, Shape.Z) * .5f,
                ShapeWorld.GetRotation(), FColor::Cyan, false, -1.f, 1, 1.f);
        }
        for (const FKSphylElem& Shape : Setup->AggGeom.SphylElems)
        {
            const FTransform ShapeWorld = Shape.GetTransform() * BodyWorld;
            DrawDebugCapsule(World, ShapeWorld.GetLocation(), Shape.Length * .5f + Shape.Radius,
                Shape.Radius, ShapeWorld.GetRotation(), FColor::Cyan, false, -1.f, 1, 1.f);
        }
        for (const FKConvexElem& Shape : Setup->AggGeom.ConvexElems)
        {
            const FTransform ShapeWorld = Shape.GetTransform() * BodyWorld;
            const TArray<int32> Indices = Shape.GetChaosConvexIndices();
            for (int32 I = 0; I + 2 < Indices.Num(); I += 3)
                for (int32 Edge = 0; Edge < 3; ++Edge)
                {
                    const int32 A = Indices[I + Edge], B = Indices[I + (Edge + 1) % 3];
                    if (Shape.VertexData.IsValidIndex(A) && Shape.VertexData.IsValidIndex(B))
                        DrawDebugLine(World, ShapeWorld.TransformPosition(Shape.VertexData[A]),
                            ShapeWorld.TransformPosition(Shape.VertexData[B]), FColor::Cyan, false, -1.f, 1, 1.f);
                }
        }
        const FVector Center = Instance->GetCOMPosition();
        DrawDebugPoint(World, Body->GetSocketLocation(Bone), 4.f, FColor::White, false, -1.f, 1);
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(OldWestDiagnosticGround), true);
        Params.AddIgnoredComponent(Body);
        if (World->LineTraceSingleByChannel(Hit, Center + FVector(0, 0, 200.f), Center - FVector(0, 0, 600.f), ECC_Visibility, Params))
        {
            DrawDebugLine(World, Center, Hit.ImpactPoint, FColor::Yellow, false, -1.f, 1, .75f);
            DrawDebugPoint(World, Hit.ImpactPoint, 7.f, FColor::Magenta, false, -1.f, 1);
        }
    }
#endif
}
USoundBase* OldWestSound(const FString& Name)
{
    return LoadObject<USoundBase>(nullptr, *(TEXT("/Game/Audio/") + Name + TEXT(".") + Name));
}
void SpatialAudio(const UObject* Context, const FString& Name, const FVector& Location, float Volume)
{
    if (USoundBase* Sound = OldWestSound(Name))
    {
        // SpawnSoundAtLocation starts playback before returning. Supply the
        // attenuation object first so Play snapshots spatialization as enabled.
        USoundAttenuation* Attenuation = NewObject<USoundAttenuation>();
        Attenuation->Attenuation.bAttenuate = true;
        Attenuation->Attenuation.bSpatialize = true;
        Attenuation->Attenuation.AttenuationShapeExtents = FVector(2800.f, 0.f, 0.f);
        Attenuation->Attenuation.FalloffDistance = 6500.f;
        UGameplayStatics::SpawnSoundAtLocation(Context, Sound, Location,
            FRotator::ZeroRotator, Volume, 1.f, 0.f, Attenuation);
    }
}
// Native people's art carries no whiskey. Resolve the actual visible copy.
bool IsNativeVisual(const AOldWestUnit* Unit)
{
    if (!Unit || Unit->Camp) return false;
    if (Unit->GetVisualCardId() == TEXT("quanah_parker")) return true;
    const auto* Crew = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*Unit->GetVisualCardId()));
    return Crew && Crew->Native;
}

UAnimSequence* Animation(const TCHAR* Name, const FString& VisualId)
{
    const FString AssetName = FString(TEXT("RA_")) + Name;
    const auto* Crew = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*VisualId));
    const FString Directory = Crew ? FString(UTF8_TO_TCHAR(Crew->Animations)) : VisualId == TEXT("quanah_parker") ? TEXT("/Game/Art/Western/Quanah/Animations/") : VisualId == TEXT("punk") ? TEXT("/Game/Art/Western/Drifter/Animations/") : TEXT("/Game/Art/Survivors/SurvivorA/Animations/");
    return LoadObject<UAnimSequence>(nullptr, *(FString(Directory) + AssetName + TEXT(".") + AssetName));
}

FVector WalkGround(UWorld* World, FVector Position, const AActor* Ignore)
{
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestWalkGround), true);
    if (Ignore) Query.AddIgnoredActor(Ignore);
    if (World->LineTraceSingleByChannel(Hit, Position + FVector(0, 0, 250), Position - FVector(0, 0, 500), ECC_Visibility, Query))
        Position.Z = Hit.ImpactPoint.Z;
    return Position;
}

bool WalkSegmentClear(UWorld* World, const AActor* Ignore, const FVector& From, const FVector& To)
{
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestWalkClearance), true);
    if (Ignore) Query.AddIgnoredActor(Ignore);
    const FVector Height(0, 0, 98);
    const FCollisionShape Capsule = FCollisionShape::MakeCapsule(32.f, 86.f);
    return !World->OverlapBlockingTestByChannel(From + Height, FQuat::Identity, ECC_Camera, Capsule, Query) &&
        !World->SweepSingleByChannel(Hit, From + Height, To + Height, FQuat::Identity, ECC_Camera, Capsule, Query);
}

}

struct FUnitPresentationFrame
{
    int32 Id = 0, Side = 0, Damage = 0;
    FString Name, CardId, VisualId;
    bool Camp = false, Punk = false, Destroyed = false, Ready = false, EventToken = false;
    FVector Location = FVector::ZeroVector;
};
struct FCinematicBeat
{
    FString Kind, Detail;
    int32 Source = 0, Target = 0, Sequence = 0, Revision = 0, Player = 0, Count = 1;
    // Scene selection uses the public activated index, including grants100/101.
    // A copied ability retains its public subject before Target becomes the performer.
    int32 AbilityIndex = INDEX_NONE, CopiedAbilitySource = 0;
    int32 AnalysisSequence = 0, AnalysisPresentedThrough = 0;
    bool ScientistScene = false;
    TArray<int32> AnalysisMappedSequences;
    int32 QueueFromSlot = INDEX_NONE, QueueToSlot = INDEX_NONE, QueueCauseSource = 0;
    FString QueueMoveReason;
    bool HasQueueTransition = false;
    FUnitPresentationFrame Before, After, CopiedAbilityFrame, FinalActionFrame;
    // A public destroyed person's optional response is a last-moments reprise,
    // never a living card restored to the authoritative battlefield.
    bool FinalAction = false;
    // Shared by one public snapshot's beats. Lane insertion can shift people
    // without a separate move log; a later snapshot must not place those
    // background people in the destination of an earlier queued entrance.
    TSharedPtr<const TMap<int32, FVector>> DeploymentLayout;
    TSharedPtr<const TMap<int32, FVector>> DeploymentBeforeLayout;
    bool KnownTarget = false, KnownCopiedAbilitySource = false;
    // Resource attribution can name an already-resolved event, not a performer.
    bool ResourceOnly = false;
    bool Departure = false; // Public Run Out of Town removal; the canonical log remains destroy.
    float Duration = 0.85f;
};
static FVector EventEquipmentOrigin(const FCinematicBeat& Beat)
{
    return Beat.Before.Location + ((Beat.Kind == TEXT("event_play") || Beat.Kind == TEXT("raid_launch"))
        ? FVector(0, (Beat.Player == 0 ? 1.f : -1.f) * (Beat.Before.CardId == TEXT("stampede") ? 430.f : 180.f), 0) : FVector::ZeroVector);
}
static FString QueueOperationName(FString Name)
{
    for (const TCHAR* Suffix : {TEXT(" · IMMINENT"), TEXT(" · APPROACHING"), TEXT(" · ASSEMBLING")})
        Name.RemoveFromEnd(Suffix);
    return Name;
}
static FString QueueStageName(FString Name, int32 Slot)
{
    return QueueOperationName(Name) + (Slot == 0 ? TEXT(" · IMMINENT") : Slot == 1 ? TEXT(" · APPROACHING") : TEXT(" · ASSEMBLING"));
}
#if !UE_BUILD_SHIPPING
static void AddQueueTransitionDebug(J& Result, const FCinematicBeat& Beat)
{
    Result["queue_transition"] = {{"valid", Beat.HasQueueTransition}, {"from_slot", Beat.QueueFromSlot},
        {"to_slot", Beat.QueueToSlot}, {"cause_source", Beat.QueueCauseSource},
        {"move_reason", std::string(TCHAR_TO_UTF8(*Beat.QueueMoveReason))}};
}
static void AddAbilityPresentationDebug(J& Result, const FCinematicBeat& Beat)
{
    Result["resource_only"] = Beat.ResourceOnly;
    Result["final_action_reprise"] = Beat.FinalAction;
    Result["final_action_visual_id"] = Beat.FinalAction ? std::string(TCHAR_TO_UTF8(*Beat.FinalActionFrame.VisualId)) : std::string();
    Result["departure"] = Beat.Departure;
    Result["ability_index"] = Beat.AbilityIndex;
    Result["analysis_sequence"] = Beat.AnalysisSequence;
    Result["analysis_presented_through"] = Beat.AnalysisPresentedThrough;
    Result["scientist_scene"] = Beat.ScientistScene;
    Result["analysis_mapped_sequences"] = J::array();
    for (int32 Sequence : Beat.AnalysisMappedSequences) Result["analysis_mapped_sequences"].push_back(Sequence);
    Result["copied_ability_source"] = Beat.CopiedAbilitySource;
    Result["copied_ability_source_known"] = Beat.KnownCopiedAbilitySource;
    Result["copied_ability_source_punk"] = Beat.KnownCopiedAbilitySource && Beat.CopiedAbilityFrame.Punk;
    Result["copied_ability_public_card_id"] = Beat.KnownCopiedAbilitySource && !Beat.CopiedAbilityFrame.Punk ?
        std::string(TCHAR_TO_UTF8(*Beat.CopiedAbilityFrame.CardId)) : std::string();
}
static J ProjectSubjectBounds(const AOldWestUnit* Unit, const ACineCameraActor* Camera)
{
    if (!IsValid(Unit) || !IsValid(Camera)) return nullptr;
    const FBox Bounds = Unit->GetVisualBounds();
    const UCineCameraComponent* Lens = Camera->GetCineCameraComponent();
    if (!Bounds.IsValid || !Lens || Lens->CurrentFocalLength <= 0.f) return nullptr;
    const double TanHorizontal = Lens->Filmback.SensorWidth / (2. * Lens->CurrentFocalLength);
    const double TanVertical = Lens->Filmback.SensorHeight / (2. * Lens->CurrentFocalLength);
    if (TanHorizontal <= 0. || TanVertical <= 0.) return nullptr;
    FBox2D Frame(ForceInit);
    bool InFront = true;
    for (int32 Corner = 0; Corner < 8; ++Corner)
    {
        const FVector Point((Corner & 1) ? Bounds.Max.X : Bounds.Min.X,
            (Corner & 2) ? Bounds.Max.Y : Bounds.Min.Y, (Corner & 4) ? Bounds.Max.Z : Bounds.Min.Z);
        const FVector Local = Camera->GetActorQuat().UnrotateVector(Point - Camera->GetActorLocation());
        if (Local.X <= 1.) { InFront = false; continue; }
        Frame += FVector2D(.5 + Local.Y / (2. * Local.X * TanHorizontal),
            .5 - Local.Z / (2. * Local.X * TanVertical));
    }
    return {{"target", Unit->EntityId}, {"hidden", Unit->IsHidden()}, {"all_corners_in_front", InFront},
        {"normalized_min", Frame.bIsValid ? J::array({Frame.Min.X, Frame.Min.Y}) : J(nullptr)},
        {"normalized_max", Frame.bIsValid ? J::array({Frame.Max.X, Frame.Max.Y}) : J(nullptr)},
        {"sensor_width_mm", Lens->Filmback.SensorWidth}, {"sensor_height_mm", Lens->Filmback.SensorHeight},
        {"semantics", "Projected rendered AABB in the camera filmback, not a pixel-visibility or occlusion test."}};
}
#endif
struct FActionEffect
{
    TWeakObjectPtr<UStaticMeshComponent> Mesh;
    FVector From, To, Scale;
    FRotator Rotation;
    float Age = 0.f, Delay = 0.f, Duration = 1.f, Arc = 0.f, Spin = 0.f;
    bool Shrink = false;
    float WheelRadius = 0.f;
    bool Hinged = false;
    bool FallingCloth = false;
    FVector Pivot = FVector::ZeroVector;
    FVector HingeAxis = FVector::RightVector;
};
struct FOldWestPresentation
{
    TMap<int32, FUnitPresentationFrame> Latest;
    TMap<int32, FUnitPresentationFrame> DepartedPublicPeople;
    oldwest::presentation::AnalysisScenes Analysis;
    TMap<int32, TWeakObjectPtr<UOldWestScientistPlayback>> ScientistPlayback;
    // The final public snapshot may contain a replacement before its entrance
    // is presented. Keep its actor, but do not show it over the outgoing person.
    TMap<int32, int32> DeferredEntrances;
    TArray<FCinematicBeat> Pending, Simultaneous;
    TOptional<FCinematicBeat> Active;
    TArray<FActionEffect> Effects;
    TArray<TWeakObjectPtr<UOldWestDeliveryVisuals>> Deliveries;
    FString MatchId;
    int32 LastSequence = -1, LastRevision = -1, LastTurn = -1;
    int32 FocusRevision = -1, SkippedBeats = 0;
    double StartedAt = 0.;
    float Elapsed = 0.f;
    int32 FrameCount = 0;
    float LastFrameSeconds = 0.f, MaxFrameSeconds = 0.f, EstimatedPhysicsSeconds = 0.f;
    TMap<int32, FUnitPresentationFrame> WaitingStampedes;
    bool ImpactResolved = false, GroupShot = false;
    bool WaitForPersonSettling = false, AllRagdollsSettled = false;
    float SettleStableSeconds = 0.f;
#if !UE_BUILD_SHIPPING
    J CompletionHistory = J::array();
    struct FPerformanceFrame
    {
        uint64 Frame = 0;
        float Elapsed = 0.f, Delta = 0.f, PhysicsDelta = 0.f;
        uint32 Game = 0, GameWait = 0, GameCritical = 0;
        uint32 Render = 0, RenderWait = 0, RenderCritical = 0;
        uint32 Rhi = 0, Gpu = 0, Present = 0;
        bool SettlingRequired = false, AllSettled = false;
        float StableSeconds = 0.f;
        FString SettlingFailure;
    };
    TArray<FPerformanceFrame> PerformanceFrames;
    int32 PerformanceWriteIndex = 0;
    void ResetPerformanceFrames() { PerformanceFrames.Reset(); PerformanceWriteIndex = 0; }
    J PerformanceDebug() const
    {
        J Result = {{"enabled", ProfilePresentation()}};
        if (!ProfilePresentation()) return Result;
        Result["capacity"] = 600;
        Result["total_shot_frames"] = FrameCount;
        Result["dropped_oldest_frames"] = FMath::Max(0, FrameCount - PerformanceFrames.Num());
        Result["counter_semantics"] = "Latest completed viewport CPU counters and latest available GPU timing, sampled during PostUpdateWork; asynchronous counters are not synchronized to this physics frame. Zero GPU cycles means unavailable.";
        Result["samples"] = J::array();
        for (int32 Offset = 0; Offset < PerformanceFrames.Num(); ++Offset)
        {
            const int32 Index = PerformanceFrames.Num() == 600 ? (PerformanceWriteIndex + Offset) % 600 : Offset;
            const FPerformanceFrame& F = PerformanceFrames[Index];
            Result["samples"].push_back({{"frame", F.Frame}, {"elapsed", F.Elapsed},
                {"frame_delta_ms", F.Delta * 1000.f}, {"estimated_physics_delta_ms", F.PhysicsDelta * 1000.f},
                {"game_active_ms", FPlatformTime::ToMilliseconds(F.Game)},
                {"game_wait_ms", FPlatformTime::ToMilliseconds(F.GameWait)},
                {"game_critical_path_ms", FPlatformTime::ToMilliseconds(F.GameCritical)},
                {"render_active_ms", FPlatformTime::ToMilliseconds(F.Render)},
                {"render_wait_ms", FPlatformTime::ToMilliseconds(F.RenderWait)},
                {"render_critical_path_ms", FPlatformTime::ToMilliseconds(F.RenderCritical)},
                {"rhi_active_ms", FPlatformTime::ToMilliseconds(F.Rhi)},
                {"gpu_ms", F.Gpu ? J(FPlatformTime::ToMilliseconds(F.Gpu)) : J(nullptr)},
                {"present_ms", FPlatformTime::ToMilliseconds(F.Present)},
                {"settling_required", F.SettlingRequired}, {"all_ragdolls_settled", F.AllSettled},
                {"stable_seconds", F.StableSeconds},
                {"settling_failure", std::string(TCHAR_TO_UTF8(*F.SettlingFailure))}});
        }
        return Result;
    }
#endif
    FVector ShotOffset = FVector::ZeroVector;
    bool EffectFraming = false;
    FBox EffectFrameBounds = FBox(ForceInit);
    FVector EffectViewDirection = FVector::ZeroVector;
    TArray<FBox> ServiceLayouts;
    int32 ServiceLayoutFailures = 0;
#if !UE_BUILD_SHIPPING
    J CameraPostTick = J::object();
#endif
};

AOldWestUnit::AOldWestUnit()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    Body = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Survivor"));
    Body->SetupAttachment(RootComponent);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WoundBandage = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("WoundBandage"));
    WoundBandage->SetupAttachment(Body);
    WoundBandage->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WoundBandage->SetGenerateOverlapEvents(false);
    WoundBandage->bUseAttachParentBound = true;
    WoundBandage->SetVisibility(false);
    Structure = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Camp"));
    Structure->SetupAttachment(RootComponent);
    Structure->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Structure->SetCollisionResponseToAllChannels(ECR_Ignore);
    Structure->SetCollisionResponseToChannel(ECC_Camera, ECR_Block);
    CampVisuals = CreateDefaultSubobject<UOldWestCampVisuals>(TEXT("CampVisuals"));
    CampVisuals->SetupAttachment(RootComponent);
    StampedeVisuals = CreateDefaultSubobject<UOldWestStampedeVisuals>(TEXT("StampedeVisuals"));
    StampedeVisuals->SetupAttachment(RootComponent);
    Weapon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Weapon"));
    Weapon->SetupAttachment(RootComponent);
    Weapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Caption = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Name"));
    Caption->SetupAttachment(RootComponent);
    Caption->SetHorizontalAlignment(EHTA_Center);
    Caption->SetWorldSize(12.f);
    Caption->SetVisibility(false); // Compact screen labels are painted once by the HUD.
    Impact = CreateDefaultSubobject<UPointLightComponent>(TEXT("ImpactFlash"));
    Impact->SetupAttachment(RootComponent);
    Impact->SetRelativeLocation(FVector(0, 0, 110));
    Impact->SetIntensity(0.f);
    Impact->SetAttenuationRadius(320.f);
    Impact->SetCastShadows(false);
}

void AOldWestUnit::Configure(int32 Id, int32 InSide, const FString& Name, bool IsCamp, bool IsPunk, const FString& CardId, bool ForceUnarmed, const FString& VisualOverride)
{
    InterruptManualPresentation(TEXT("configure"));
    WoundBandage->SetVisibility(false);
    WoundBandage->SetLeaderPoseComponent(nullptr);
    WoundBandage->SetSkeletalMesh(nullptr);
    StampedeVisuals->Clear();
    for (UStaticMeshComponent* Part : EventParts) if (IsValid(Part)) Part->DestroyComponent();
    EventParts.Empty();
    EventEffectMaterial = nullptr;
    EventWheels.Empty();
    EventTurret = nullptr;
    EventWheelTravelCm = 0.;
    EventWheelRadiusCm = 14.f;
    EventToken = false;
    Body->SetComponentTickEnabled(true);
    EntityId = Id;
    Side = InSide;
    DisplayName = Name; // Callers pass display text that is already translated.
    Camp = IsCamp;
    Punk = IsPunk;
    const auto* DirectCrew = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*CardId));
    CanonicalCardId = DirectCrew ? FString(UTF8_TO_TCHAR(DirectCrew->Canonical)) : CardId;
    const auto* Crew = !IsPunk && !IsCamp ? OldWestCrew::Resolve(TCHAR_TO_UTF8(*CanonicalCardId), TCHAR_TO_UTF8(*VisualOverride)) : nullptr;
    if (!Crew && !IsPunk && !IsCamp) Crew = DirectCrew ? DirectCrew : OldWestCrew::ForCopy(TCHAR_TO_UTF8(*CanonicalCardId));
    // Approved Crew meshes already contain period equipment. Never add the
    // legacy modern rifle or drive these rigs with its ADS pose.
    Unarmed = Crew || IsPunk || CardId == TEXT("punk") || ForceUnarmed || CardId == TEXT("blacksmith");
    Raider = CardId == TEXT("stampede");
    VisualCardId = IsPunk ? TEXT("punk") : Crew ? FString(UTF8_TO_TCHAR(Crew->Visual)) : CardId;
    if (Crew) DisplayName = UTF8_TO_TCHAR(Crew->Name);
    IdleClip = Unarmed ? TEXT("MM_Idle") : TEXT("MF_Rifle_Idle_ADS");
    // Stable per-figure offsets keep a deployed squad from breathing in lockstep.
    const uint32 Identity = HashCombine(GetTypeHash(CardId), GetTypeHash(Id));
    IdlePhase = static_cast<float>(Identity % 997) / 997.f;
    IdleRate = .92f + static_cast<float>((Identity / 997) % 101) * .0016f;
    VisualDamage = -1;
    Facing = FRotator(0, Side == 0 ? 180 : 0, 0);
    ResetPose();
    Caption->SetText(FText::FromString(DisplayName));
    Caption->SetTextRenderColor(Side == 0 ? FColor(152, 213, 204) : FColor(240, 177, 133));
    Caption->SetRelativeLocation(FVector(0, 0, Camp ? 260 : 225));
    Body->SetVisibility(!Camp);
    Weapon->SetVisibility(!Camp && !Unarmed);
    Structure->SetVisibility(false);
    Structure->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CampVisuals->SetVisibility(Camp, true);
    if (Camp)
    {
        // Camp entrances and weapon muzzles are authored toward local -Y.
        // Each camp therefore faces its guards and the opposing camp line.
        CampVisuals->SetRelativeRotation(FRotator(0, Side == 0 ? 0 : 180, 0));
        CampVisuals->Build(CardId);
    }
    else if (!Raider)
    {
        // CardId is the public board identity. Hidden punks never select the
        // mechanical mesh from private peek data, including in portrait scenes.
        const TCHAR* MeshPath = TEXT("/Game/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm.SKM_Survivor_A_Cm");
        if (CardId == TEXT("blacksmith")) MeshPath = TEXT("/Game/Art/Survivors/RepairBot/SKM_RepairBot_Cm.SKM_RepairBot_Cm");
        else if (CardId == TEXT("prospector")) MeshPath = TEXT("/Game/Art/Survivors/Variants/SKM_Prospector_Cm.SKM_Prospector_Cm");
        else if (CardId == TEXT("gatling_gunner")) MeshPath = TEXT("/Game/Art/Survivors/Variants/SKM_GatlingGunner_Cm.SKM_GatlingGunner_Cm");
        else if (CardId == TEXT("bounty_hunter")) MeshPath = TEXT("/Game/Art/Survivors/Variants/SKM_BountyHunter_Cm.SKM_BountyHunter_Cm");
        FString IdentityPath;
        static const TSet<FString> Identities={TEXT("wyatt_earp"),TEXT("hellfire_preacher"),TEXT("pinkerton_agent"),TEXT("regulator"),TEXT("widow_with_a_shotgun"),TEXT("quanah_parker"),TEXT("claim_jumper"),TEXT("augustus_powder_pike"),TEXT("con_man"),TEXT("cornelius_ashby_railroad_baron"),TEXT("bartender"),TEXT("doc_holliday"),TEXT("barn_burner"),TEXT("ringleader"),TEXT("sarah_winnemucca"),TEXT("rustler"),TEXT("annie_oakley"),TEXT("duelist"),TEXT("charles_goodnight"),TEXT("vigilante"),TEXT("civil_war_veteran"),TEXT("poker_alice"),TEXT("punk")};
        if(IsPunk || Identities.Contains(CardId)) {
            const FString PublicId=IsPunk?TEXT("punk"):CardId;
            TArray<FString> Words;PublicId.ParseIntoArray(Words,TEXT("_"));
            FString AssetName;for(FString Word:Words) {if(!Word.IsEmpty())Word[0]=FChar::ToUpper(Word[0]);AssetName+=Word;}
            IdentityPath=TEXT("/Game/Art/Survivors/Identities/SKM_")+AssetName+TEXT("_Cm.SKM_")+AssetName+TEXT("_Cm");
            MeshPath=*IdentityPath;
        }
        // Every concealed card and decorative recruit uses this same public visual.
        const bool DrifterVisual = VisualCardId == TEXT("punk");
        if (Crew) { IdentityPath = UTF8_TO_TCHAR(Crew->Mesh); MeshPath = *IdentityPath; }
        if (DrifterVisual) MeshPath = TEXT("/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter");
        USkeletalMesh* PublicMesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
#if WITH_EDITOR
        // Editor gameplay can first load an uncached Crew material at a public
        // reveal. Finish only this visible mesh's materials before registering
        // it, so the reveal never paints the gray fallback. Cooked builds use
        // their cooked shaders. MeshPath above is always visibility-filtered;
        // private inspection must never select or warm a concealed identity.
        if (PublicMesh)
            for (const FSkeletalMaterial& Slot : PublicMesh->GetMaterials())
                if (Slot.MaterialInterface)
                {
                    Slot.MaterialInterface->CheckMaterialUsage(MATUSAGE_SkeletalMesh);
                    // CacheShaders(Synchronous) alone does not finalize an
                    // instance's inherited shader map in this engine version.
                    Slot.MaterialInterface->EnsureIsComplete();
                }
#endif
        Body->SetSkeletalMesh(PublicMesh);
        if (!Body->GetSkeletalMeshAsset())
            UE_LOG(LogTemp, Error, TEXT("OldWest public person '%s' has no visual mesh at %s"), *CardId, MeshPath);
        const FString PhysicsPath = Crew ? FString(UTF8_TO_TCHAR(Crew->Physics)) : DrifterVisual ?
            TEXT("/Game/Art/Western/Drifter/PA_Drifter.PA_Drifter") :
            TEXT("/Game/Art/Survivors/SurvivorA/PA_Survivor_Anatomical.PA_Survivor_Anatomical");
        Body->SetPhysicsAsset(LoadObject<UPhysicsAsset>(nullptr, *PhysicsPath));
        Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        PelvisBone = Body->GetBoneIndex(TEXT("Hips")) != INDEX_NONE ? FName(TEXT("Hips")) : FName(TEXT("mixamorig:Hips"));
        Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        PlayIdle();
        Weapon->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Weapons/Rifle/Meshes/SM_Rifle.SM_Rifle")));
        if (UMaterialInterface* Steel = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Art/CardPortraits/M_Portrait_Weapon.M_Portrait_Weapon")))
            for (int32 Slot = 0; Slot < Weapon->GetNumMaterials(); ++Slot) Weapon->SetMaterial(Slot, Steel);
        if (!Unarmed) AlignWeaponToHands();
    }
    else
    {
        Body->SetSkeletalMesh(nullptr);
        Body->SetVisibility(false);
        Weapon->SetVisibility(false);
        ActiveClip.Reset();
    }
    SetPreviewOnly(PreviewOnly);
}

void AOldWestUnit::ConfigureEvent(int32 Id, int32 InSide, const FString& Name, const FString& CardId)
{
    InterruptManualPresentation(TEXT("configure_event"));
    if (EventToken && Raider && EntityId == Id && Side == InSide && VisualCardId == CardId)
    {
        DisplayName = Name; Caption->SetText(FText::FromString(Name));
        return; // Queue-stage labels do not reset the herd's animation phase.
    }
    // Stage-name changes rebuild the same event. Preserve its wheel phase,
    // while a new/different entity starts with a fresh equipment pose.
    const double PriorWheelTravel = EntityId == Id && VisualCardId == CardId ? EventWheelTravelCm : 0.;
    Configure(Id, InSide, Name, false, false, CardId);
    EventWheelTravelCm = PriorWheelTravel;
    EventToken = true;
    Body->SetVisibility(false);
    Body->SetComponentTickEnabled(false);
    Weapon->SetVisibility(false);
    if (Raider)
    {
        Structure->SetStaticMesh(nullptr);
        Structure->SetVisibility(false);
        StampedeVisuals->Build(Side);
        Impact->SetIntensity(0.f);
        Caption->SetRelativeLocation(FVector(0,0,185));
        return;
    }
    Structure->SetRelativeRotation(FRotator::ZeroRotator);
    Structure->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
    Structure->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Art/WaterDepotV2/Materials/M_AgedGalvanized.M_AgedGalvanized")));
    Structure->SetRelativeScale3D(FVector(.82f, .6f, .37f));
    Structure->SetRelativeLocation(FVector(0, 0, 18.5f));
    Structure->SetVisibility(true);
    auto Part = [this](const TCHAR* Shape, const TCHAR* Material, FVector Location, FVector Scale, FRotator Rotation = FRotator::ZeroRotator)
    {
        UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this);
        AddInstanceComponent(Mesh); Mesh->SetupAttachment(RootComponent);
        const FString Path = FString(TEXT("/Engine/BasicShapes/")) + Shape + TEXT(".") + Shape;
        const FString MaterialPath = FString(TEXT("/Game/Art/WaterDepotV2/Materials/")) + Material + TEXT(".") + Material;
        Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, *Path));
        Mesh->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, *MaterialPath));
        Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision); Mesh->SetCanEverAffectNavigation(false);
        Mesh->SetRelativeLocation(Location); Mesh->SetRelativeScale3D(Scale); Mesh->SetRelativeRotation(Rotation);
        Mesh->RegisterComponent(); EventParts.Add(Mesh);
    };
    // Staging utilities have recognisable physical silhouettes. They share
    // the event-prop selection path, but are not disguised event cards.
    auto AssetPart = [this](const TCHAR* Path, FVector Base, float Width, FRotator Rotation = FRotator::ZeroRotator)
    {
        UStaticMesh* Asset=LoadObject<UStaticMesh>(nullptr,Path);
        if(!Asset){UE_LOG(LogTemp,Error,TEXT("OLDWEST_ACTION_PROP_ERROR Missing field prop %s"),Path);return;}
        const FBox Bounds=Asset->GetBoundingBox();
        const float Scale=Width/FMath::Max(1.,FMath::Max(Bounds.GetSize().X,Bounds.GetSize().Y));
        auto* Mesh=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Mesh);
        Mesh->SetupAttachment(RootComponent);Mesh->SetStaticMesh(Asset);
        Mesh->SetRelativeLocation(Base-Rotation.RotateVector(FVector(Bounds.GetCenter().X,Bounds.GetCenter().Y,Bounds.Min.Z)*Scale));
        Mesh->SetRelativeScale3D(FVector(Scale));Mesh->SetRelativeRotation(Rotation);
        Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);Mesh->SetCanEverAffectNavigation(false);
        Mesh->RegisterComponent();EventParts.Add(Mesh);
    };
    const TCHAR* Crate=TEXT("/Game/Art/ActionProps/Meshes/SM_Action_StorageCrate.SM_Action_StorageCrate");
    if(CardId.StartsWith(TEXT("field_")))
    {
        Structure->SetVisibility(false);
        if(CardId==TEXT("field_supply"))
        {
            for(int32 I=0;I<3;++I)AssetPart(Crate,FVector((I-1)*90,0,0),85);
            AssetPart(Crate,FVector(-40,0,65),85);
            // Whiskey replaces water (Western rebrand): a keg rides on the dry-goods crates.
            AssetPart(TEXT("/Game/Art/ActionProps/Meshes/SM_Action_WhiskeyKeg.SM_Action_WhiskeyKeg"),FVector(90,0,70),40);
        }
        else if(CardId==TEXT("field_water"))
        {
            const int32 Amount=FMath::Clamp(-4000-EntityId,1,999);
            for(int32 I=0;I<FMath::Min(Amount,3);++I)
                // Laid on their sides so the steep board camera sees amber glass and labels.
                AssetPart(TEXT("/Game/Art/ActionProps/Meshes/SM_Action_WhiskeyBottleLying.SM_Action_WhiskeyBottleLying"),FVector(0,(I-1)*26,0),70,FRotator(0,20,0));
        }
        else if(CardId==TEXT("field_silo"))
        {
            AssetPart(TEXT("/Game/Art/ActionProps/Meshes/SM_Action_HipFlaskLying.SM_Action_HipFlaskLying"),FVector::ZeroVector,95,FRotator(0,25,0));
        }
        else if(CardId==TEXT("field_pass"))
        {
            Part(TEXT("Cylinder"),TEXT("M_OiledSteel"),FVector(0,0,135),FVector(.07f,.07f,2.7f));
            Part(TEXT("Cube"),TEXT("M_FlakingOxide"),FVector(52,0,222),FVector(1.05f,.04f,.75f));
            AssetPart(Crate,FVector(0,0,0),65);
        }
        else if(CardId==TEXT("field_choices"))
        {
            for(float X:{-70.f,70.f})AssetPart(Crate,FVector(X,0,0),75);
            Part(TEXT("Cube"),TEXT("M_AgedGalvanized"),FVector(0,0,83),FVector(2.3f,1.0f,.10f));
            Part(TEXT("Cube"),TEXT("M_DarkGaugeGlass"),FVector(0,-10,105),FVector(.8f,.45f,.35f));
            Part(TEXT("Cylinder"),TEXT("M_OiledSteel"),FVector(80,25,160),FVector(.025f,.025f,1.55f));
        }
        else
        {
            AssetPart(Crate,FVector::ZeroVector,150);
            for(int32 I=0;I<5;++I)Part(TEXT("Cube"),TEXT("M_FlakingOxide"),FVector((I-2)*24,0,90+I*7),FVector(.8f,.5f,.07f),FRotator(I*7,I*31,15));
        }
        return;
    }
    if(const auto* Trouble=OldWestTrouble::ForCard(TCHAR_TO_UTF8(*CardId)))
    {
        // Each Trouble prop is a physical miniature on the fuse. Its movement and
        // event resolution still follow the canonical presentation sequence.
        Structure->SetVisibility(false);
        Structure->SetStaticMesh(nullptr);
        const FString Mesh=UTF8_TO_TCHAR(Trouble->Mesh);
        const FString Path=FString(TEXT("/Game/Art/Western/Trouble/"))+UTF8_TO_TCHAR(Trouble->Folder)+TEXT("/Meshes/")+Mesh+TEXT(".")+Mesh;
        // Load the effect-only material with the visible public prop so its
        // first firing does not begin shader compilation during the shot.
        if (CardId == TEXT("cannonade"))
        {
            EventEffectMaterial = LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_Smoke.M_Trouble_Smoke"));
            // Loading alone leaves first-use shader permutations deferred in
            // the editor. Submit those while the public prop is counting down.
            if (EventEffectMaterial) EventEffectMaterial->CacheShaders();
        }
        AssetPart(*Path,FVector::ZeroVector,190,FRotator(0,Side==0?0:180,0));
        Caption->SetRelativeLocation(FVector(0,0,Trouble->CaptionHeight));
        return;
    }
    if(CardId==TEXT("hip_flask"))
    {
        Structure->SetVisibility(false);
        AssetPart(TEXT("/Game/Art/ActionProps/Meshes/SM_Action_HipFlaskLying.SM_Action_HipFlaskLying"),FVector::ZeroVector,60,FRotator(0,25,0));
        return;
    }
    // All ten canonical Trouble types use sourced static miniatures above.
    // Retain a neutral marker only for an unknown future presentation token.
    Part(TEXT("Cylinder"), TEXT("M_OiledSteel"), FVector(0, 0, 83), FVector(.04f, .04f, .95f));
    Caption->SetRelativeLocation(FVector(0, 0, 165));
}

FVector AOldWestUnit::EventPropPoint(const FVector& LocalCentimeters) const
{
    // Includes imported bounds centering, miniature scale and the owner's
    // heading. Effect anchors use the imported mesh's coordinates.
    if (!EventParts.IsEmpty() && IsValid(EventParts[0]))
        return EventParts[0]->GetComponentTransform().TransformPosition(LocalCentimeters);
    return GetActorTransform().TransformPosition(LocalCentimeters);
}

void AOldWestUnit::MoveEventEquipment(const FVector& Location)
{
    // Queue lanes run along world Y. Accumulate actual displacement, including
    // backwards delays; repeated stationary reports cannot spin the wheels.
    if (!EventWheels.IsEmpty()) EventWheelTravelCm += Location.Y - GetActorLocation().Y;
    if (Raider && EventToken) StampedeVisuals->RecordMovement(Location - GetActorLocation());
    SetActorLocation(Location);
    if (EventWheels.IsEmpty() || EventWheelRadiusCm <= SMALL_NUMBER) return;
    const FQuat Roll(FVector::ForwardVector, -EventWheelTravelCm / EventWheelRadiusCm);
    const FQuat Heading = Raider ? FRotator(0, Side == 0 ? 180.f : 0.f, 0).Quaternion() : FQuat::Identity;
    for (UStaticMeshComponent* Wheel : EventWheels) if (IsValid(Wheel))
        Wheel->SetRelativeRotation(Roll * Heading * FRotator(90,0,0).Quaternion());
}

float AOldWestUnit::StageTravel(const FVector& From, const FVector& To, float Seconds, bool Withdraw, bool DirectRoute)
{
    InterruptManualPresentation(TEXT("travel"));
    if (Ragdoll || Camp || EventToken) return 0.f;
    ResetPose();
    TravelFrom = WalkGround(GetWorld(), From, this);
    TravelTo = WalkGround(GetWorld(), To, this);
    TravelRoute = {TravelFrom, TravelTo};
    if (!DirectRoute && !WalkSegmentClear(GetWorld(), this, TravelFrom, TravelTo))
    {
        // A small visibility graph routes around the actual current camp
        // envelopes. It changes presentation only; the final legal slot stays
        // fixed. Never sweep a person through an intervening camp to save time.
        TArray<FVector> Nodes = {TravelFrom, TravelTo};
        for (TActorIterator<AOldWestUnit> It(GetWorld()); It; ++It)
        {
            if (!It->Camp || It->IsPreviewOnly()) continue;
            const FBox Bounds = It->GetVisualBounds().ExpandBy(65.f);
            if (!Bounds.IsValid) continue;
            for (float X : {static_cast<float>(Bounds.Min.X), static_cast<float>(Bounds.Max.X)})
                for (float Y : {static_cast<float>(Bounds.Min.Y), static_cast<float>(Bounds.Max.Y)})
                    Nodes.Add(WalkGround(GetWorld(), FVector(X, Y, TravelFrom.Z), this));
        }
        TArray<float> Distance; Distance.Init(TNumericLimits<float>::Max(), Nodes.Num());
        TArray<int32> Parent; Parent.Init(INDEX_NONE, Nodes.Num());
        TArray<bool> Done; Done.Init(false, Nodes.Num()); Distance[0] = 0.f;
        for (int32 Step = 0; Step < Nodes.Num(); ++Step)
        {
            int32 Best = INDEX_NONE;
            for (int32 I = 0; I < Nodes.Num(); ++I)
                if (!Done[I] && (Best == INDEX_NONE || Distance[I] < Distance[Best])) Best = I;
            if (Best == INDEX_NONE || Distance[Best] == TNumericLimits<float>::Max() || Best == 1) break;
            Done[Best] = true;
            for (int32 Next = 0; Next < Nodes.Num(); ++Next)
            {
                if (Done[Next] || Next == Best) continue;
                const float Candidate = Distance[Best] + FVector::Distance(Nodes[Best], Nodes[Next]);
                if (Candidate < Distance[Next] && WalkSegmentClear(GetWorld(), this, Nodes[Best], Nodes[Next]))
                { Distance[Next] = Candidate; Parent[Next] = Best; }
            }
        }
        if (Parent[1] != INDEX_NONE)
        {
            TravelRoute.Reset();
            for (int32 At = 1; At != INDEX_NONE; At = Parent[At]) TravelRoute.Insert(Nodes[At], 0);
        }
        else
        {
            // No invented path through solid scenery. A confined position is
            // established directly and reported for visual follow-up.
            UE_LOG(LogTemp, Warning, TEXT("OldWest presentation has no clear walk route for public person%d"), EntityId);
            TravelRoute = {TravelTo, TravelTo}; TravelFrom = TravelTo;
        }
    }
    TravelLength = 0.f;
    for (int32 I = 1; I < TravelRoute.Num(); ++I) TravelLength += FVector::Distance(TravelRoute[I-1], TravelRoute[I]);
    // Walking clips have a finite stride. Long recruitment/rearrangement shots
    // keep their real travel time instead of accelerating across whole lanes.
    // The verified unarmed clip travels 467.1856cm in 1.5s before extraction.
    // Root locking/extraction and Tick's root compensation keep its pose local.
    TravelStrideSpeed = Unarmed ? 311.4571f : 185.f;
    TravelDuration = FMath::Max(FMath::Max(.35f, Seconds), TravelLength / TravelStrideSpeed);
    TravelElapsed = 0.f; WithdrawAfterTravel = Withdraw; Travelling = true;
    SetActorLocation(TravelFrom);
    AimAt(TravelRoute[1] + FVector(0, 0, 100));
    PlayClip(Unarmed ? TEXT("MF_Unarmed_Walk_Fwd") : TEXT("MF_Rifle_Walk_Fwd"), true);
    if (UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance())
    {
        const float Rate = TravelLength / TravelDuration / TravelStrideSpeed;
        // Short unarmed routes can legitimately need less than 0.6x playback.
        // A minimum faster than the actor would make planted feet slide.
        Instance->SetPlayRate(Unarmed ? FMath::Clamp(Rate, 0.f, 1.1f) : FMath::Clamp(Rate, .6f, 1.1f));
    }
    AnimationTime = TravelDuration + .1f;
    return TravelDuration;
}

void AOldWestUnit::SetCondition(int32 Damage, bool Destroyed, bool Ready)
{
    if (Destroyed) InterruptManualPresentation(TEXT("destroyed_condition"));
    if (Dead && !Destroyed) ResetPose();
    Dead = Destroyed;
    FString State = DisplayName;
    if (Destroyed) State += Camp ? TEXT(" · BURNED OUT") : TEXT(" · FALLEN");
    else if (Damage > 0) State += TEXT(" · DAMAGED");
    else if (!Ready && !Camp) State += TEXT(" · RECOVERING");
    Caption->SetText(FText::FromString(State));
    const int32 NewDamage = Destroyed ? 2 : Damage;
    if (Camp && VisualDamage != NewDamage)
    {
        CampVisuals->SetCondition(Damage, Destroyed);
    }
    if (Camp)
    {
        const FBox Bounds = CampVisuals->GetVisualBounds();
        if (Bounds.IsValid) Caption->SetWorldLocation(FVector(Bounds.GetCenter().X, Bounds.GetCenter().Y, Bounds.Max.Z + 40.f));
    }
    const bool Changed=VisualDamage!=NewDamage;
    VisualDamage = NewDamage;
    UpdateWoundBandage();
    if(Changed&&!Camp&&!EventToken&&!Dead&&!Travelling&&AnimationTime<=0.f)PlayIdle();
}

void AOldWestUnit::UpdateWoundBandage()
{
    const bool Wounded = !Camp && !EventToken && !Dead && VisualDamage == 1;
    if (Wounded && !WoundBandage->GetSkeletalMeshAsset())
    {
        // Resolve only the already filtered public visual. A private peek can
        // never select a named fit, even when the concealed card is wounded.
        const auto* Crew = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*VisualCardId));
        const FString Name = VisualCardId == TEXT("punk") ? TEXT("Drifter") :
            Crew ? FString(UTF8_TO_TCHAR(Crew->AssetName)) : FString();
        if (!Name.IsEmpty())
        {
            const FString Path = TEXT("/Game/Art/Western/Bandages/SK_Bandage_") + Name + TEXT(".SK_Bandage_") + Name;
            WoundBandage->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr, *Path));
            WoundBandage->SetLeaderPoseComponent(Body, true, false);
        }
    }
    WoundBandage->SetVisibility(Wounded && WoundBandage->GetSkeletalMeshAsset());
}

void AOldWestUnit::PlayClip(const TCHAR* Name, bool Loop)
{
    if (HasManualPresentation()) return;
    if (Camp || !Body->GetSkeletalMeshAsset()) return;
    ActiveClip = Name;
    Body->SetRelativeLocation(FVector::ZeroVector);
    Body->SetRelativeRotation(Facing);
    Body->PlayAnimation(Animation(Name, VisualCardId), Loop);
    if (UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance())
    {
        Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
        Instance->SetPlayRate(1.f);
        Instance->SetPosition(0.f, false);
    }
    Body->RefreshBoneTransforms();
    RootFrame = Body->GetSocketTransform(TEXT("root"), RTS_Component);
}

void AOldWestUnit::ApplyInjuredPose()
{
    // Retain the character's own idle upper body and rig proportions. Solve both
    // legs into a knees-down pose rather than scaling or sinking the whole mesh.
    const FReferenceSkeleton& Ref=Body->GetSkeletalMeshAsset()->GetRefSkeleton();
    TArray<FTransform> Pose=Body->GetBoneSpaceTransforms();
    if(Pose.Num()!=Ref.GetNum())return;
    auto Index=[&](const TCHAR* Name){int32 I=Ref.FindBoneIndex(FName(Name));if(I==INDEX_NONE)I=Ref.FindBoneIndex(FName(*(FString(TEXT("mixamorig:"))+Name)));return I;};
    const int32 Hip=Index(TEXT("Hips")),Knee=Index(TEXT("LeftLeg")),Thigh=Index(TEXT("LeftUpLeg"));
    if(Hip==INDEX_NONE||Knee==INDEX_NONE||Thigh==INDEX_NONE)return;
    auto Global=[&](int32 I){FTransform T=Pose[I];for(int32 P=Ref.GetParentIndex(I);P!=INDEX_NONE;P=Ref.GetParentIndex(P))T=T*Pose[P];return T;};
    const float LegLength=Pose[Knee].GetTranslation().Size();
    const FVector Lower(0,0,LegLength+12.f-Global(Hip).GetTranslation().Z);
    const int32 HipParent=Ref.GetParentIndex(Hip);
    Pose[Hip].AddToTranslation(HipParent==INDEX_NONE?Lower:Global(HipParent).InverseTransformVectorNoScale(Lower));
    auto Aim=[&](int32 Bone,int32 Child,const FVector& Direction)
    {
        if(Bone==INDEX_NONE||Child==INDEX_NONE)return;
        FTransform B=Global(Bone);const FVector Old=Global(Child).GetLocation()-B.GetLocation();
        const FQuat Rotation=FQuat::FindBetweenNormals(Old.GetSafeNormal(),Direction.GetSafeNormal())*B.GetRotation();
        const int32 Parent=Ref.GetParentIndex(Bone);
        Pose[Bone].SetRotation(Parent==INDEX_NONE?Rotation:Global(Parent).GetRotation().Inverse()*Rotation);
        Pose[Bone].NormalizeRotation();
    };
    for(const FString& SideName:{FString(TEXT("Left")),FString(TEXT("Right"))})
    {
        const int32 Upper=Index(*(SideName+TEXT("UpLeg"))),LowerLeg=Index(*(SideName+TEXT("Leg"))),Foot=Index(*(SideName+TEXT("Foot"))),Toe=Index(*(SideName+TEXT("ToeBase")));
        Aim(Upper,LowerLeg,FVector(0,0,-1));
        Aim(LowerLeg,Foot,FVector(0,-1,0));
        Aim(Foot,Toe,FVector(0,-1,-.12f));
    }
    Body->SetAnimInstanceClass(UOldWestManualAnimInstance::StaticClass());
    if(auto* Instance=Cast<UOldWestManualAnimInstance>(Body->GetAnimInstance()))
    {
        Instance->SetAnimationAsset(Animation(*IdleClip, VisualCardId),true,0.f);
        Instance->EntryLocalPose=MoveTemp(Pose);Instance->EntryAlpha=0.f;
        Instance->SetPlaying(false);Instance->SetPlayRate(0.f);
        Body->TickAnimation(0.f,false);Body->RefreshBoneTransforms();
        ActiveClip=TEXT("Injured_Kneeling");
    }
}

void AOldWestUnit::PlayIdle()
{
    if (HasManualPresentation()) return;
    if (Camp || EventToken || !Body->GetSkeletalMeshAsset()) return;
    PlayClip(*IdleClip, true);
    if (UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance())
    {
        Instance->SetPlayRate(IdleRate);
        if (UAnimSequence* Clip = Animation(*IdleClip, VisualCardId))
            Instance->SetPosition(Clip->GetPlayLength() * IdlePhase, false);
    }
    // Evaluate immediately so a newly dropped figure cannot show a reference
    // pose for one frame. Root-motion compensation remains active in Tick.
    Body->TickAnimation(0.f, false);
    Body->RefreshBoneTransforms();
    if(VisualDamage==1&&!Dead)ApplyInjuredPose();
    RootFrame = Body->GetSocketTransform(TEXT("root"), RTS_Component);
}

void AOldWestUnit::SetPreviewOnly(bool Enabled)
{
    PreviewOnly = Enabled;
    if (Enabled) Tags.AddUnique(TEXT("OldWestPortraitPreview"));
    else Tags.Remove(TEXT("OldWestPortraitPreview"));
    Caption->SetVisibility(false);
    Impact->SetVisibility(!Enabled);
    SetActorEnableCollision(!Enabled);
}

FBox AOldWestUnit::GetVisualBounds() const
{
    if (Camp) return CampVisuals->GetVisualBounds();
    if (Raider && EventToken) return StampedeVisuals->GetVisualBounds();
    if (EventToken)
    {
        FBox Bounds = Structure->Bounds.GetBox();
        for (const UStaticMeshComponent* Part : EventParts) if (IsValid(Part)) Bounds += Part->Bounds.GetBox();
        return Bounds;
    }
    return Body->Bounds.GetBox();
}

FString AOldWestUnit::GetIdleDebug() const
{
#if !UE_BUILD_SHIPPING
    const UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance();
    J Result = {{"card_id", std::string(TCHAR_TO_UTF8(*CanonicalCardId))}, {"visual_id", std::string(TCHAR_TO_UTF8(*VisualCardId))},
        {"preview_only", PreviewOnly}, {"raider", Raider}, {"camp", Camp}, {"event_token", EventToken}, {"unarmed", Unarmed},
        {"travelling", Travelling}, {"travel_elapsed", TravelElapsed}, {"travel_duration", TravelDuration},
        {"travel_length_cm", TravelLength}, {"travel_waypoint_count", TravelRoute.Num()},
        {"travel_stride_speed_cm_s", TravelStrideSpeed},
        {"travel_speed_cm_s", Travelling && TravelDuration > 0.f ? TravelLength / TravelDuration : 0.f},
        {"visual_mesh", Body->GetSkeletalMeshAsset() ? std::string(TCHAR_TO_UTF8(*Body->GetSkeletalMeshAsset()->GetPathName())) : std::string()},
        {"mesh_lod_count", Body->GetSkeletalMeshAsset() ? Body->GetSkeletalMeshAsset()->GetLODNum() : 0},
        {"forced_lod", Body->GetForcedLOD()}, {"predicted_lod", Body->GetPredictedLODLevel()},
        {"event_parts", EventParts.Num()},
        {"dead", Dead}, {"ragdoll", Ragdoll}, {"action_seconds", AnimationTime},
        {"idle_clip", std::string(TCHAR_TO_UTF8(*IdleClip))}, {"idle_rate", IdleRate}, {"idle_phase", IdlePhase}, {"ambient_activity",AmbientActivity},
        {"looping", Instance ? Instance->IsLooping() : false},
        {"playing", Instance ? Instance->IsPlaying() : false},
        {"active_clip", std::string(TCHAR_TO_UTF8(*ActiveClip))},
        {"animation_position", Instance ? Instance->GetCurrentTime() : 0.f}, {"root_drift_cm", GetRootDrift()}};
    Result["event_wheel_travel_cm"] = EventWheelTravelCm;
    Result["event_wheel_radius_cm"] = EventWheels.IsEmpty() ? 0. : EventWheelRadiusCm;
    Result["body_visible"] = Body->IsVisible();
    Result["damage"]=VisualDamage;
    Result["bandage"] = {{"visible", WoundBandage->IsVisible()},
        {"mesh", WoundBandage->GetSkeletalMeshAsset() ? std::string(TCHAR_TO_UTF8(*WoundBandage->GetSkeletalMeshAsset()->GetPathName())) : std::string()},
        {"follows_body", WoundBandage->LeaderPoseComponent.Get() == Body},
        {"collision_enabled", static_cast<int32>(WoundBandage->GetCollisionEnabled())}};
    Result["injury_joints"]=J::object();
    if(!Camp&&!EventToken&&Body->GetSkeletalMeshAsset())
        for(const TCHAR* Name:{TEXT("Hips"),TEXT("LeftLeg"),TEXT("RightLeg"),TEXT("LeftFoot"),TEXT("RightFoot"),TEXT("Head")})
        {
            const FVector P=Body->GetSocketLocation(FName(Name))-GetActorLocation();
            Result["injury_joints"][std::string(TCHAR_TO_UTF8(Name))]={P.X,P.Y,P.Z};
        }
    Result["weapon_visible"] = Weapon->IsVisible();
    if (Raider && EventToken)
    {
        const FVector Front = StampedeVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0,1,0));
        Result["faces_opponent"] = FVector::DotProduct(Front,FVector(0,Side==0?-1:1,0))>.99f;
        Result["turret_yaw"] = IsValid(EventTurret) ? EventTurret->GetRelativeRotation().Yaw : 0.f;
    }
    if (Raider && EventToken) Result["stampede"] = J::parse(TCHAR_TO_UTF8(*StampedeVisuals->GetDebug()));
    Result["event_equipment"] = J::array();
    if (EventToken)
    {
        auto EquipmentDebug = [&Result](const UStaticMeshComponent* Mesh, bool Wheel)
        {
            if (!IsValid(Mesh) || !Mesh->GetStaticMesh()) return;
            const FVector Position = Mesh->GetComponentLocation(), Scale = Mesh->GetComponentScale();
            const FQuat Rotation = Mesh->GetComponentQuat();
            J Materials = J::array();
            for (int32 Index = 0; Index < Mesh->GetNumMaterials(); ++Index)
                if (const UMaterialInterface* Material = Mesh->GetMaterial(Index))
                    Materials.push_back(std::string(TCHAR_TO_UTF8(*Material->GetPathName())));
            Result["event_equipment"].push_back({{"mesh", std::string(TCHAR_TO_UTF8(*Mesh->GetStaticMesh()->GetPathName()))},
                {"materials", Materials},
                {"wheel", Wheel}, {"visible", Mesh->IsVisible()}, {"collision_enabled", static_cast<int32>(Mesh->GetCollisionEnabled())},
                {"location", {Position.X,Position.Y,Position.Z}}, {"scale", {Scale.X,Scale.Y,Scale.Z}},
                {"quaternion_xyzw", {Rotation.X,Rotation.Y,Rotation.Z,Rotation.W}}});
        };
        EquipmentDebug(Structure, false);
        for (const UStaticMeshComponent* Part : EventParts) EquipmentDebug(Part, EventWheels.Contains(Part));
    }
    Result["animation_play_rate"] = Instance ? Instance->GetPlayRate() : 0.f;
    Result["manual_presentation"] = J::parse(TCHAR_TO_UTF8(*GetManualPresentationDebug()));
    if (Camp)
    {
        Result["design_id"] = std::string(TCHAR_TO_UTF8(*CampVisuals->GetDesignId()));
        Result["part_count"] = CampVisuals->GetPartCount();
        Result["ground_part_count"] = CampVisuals->GetGroundPartCount();
        Result["holding_components"] = J::array();
        TArray<UStaticMeshComponent*> HoldingComponents;
        CampVisuals->AppendHoldingDebugComponents(HoldingComponents);
        for (const UStaticMeshComponent* Component : HoldingComponents)
        {
            if (!Component->GetStaticMesh()) continue;
            const FTransform Transform = Component->GetComponentTransform();
            const FVector Location = Transform.GetLocation(), Scale = Transform.GetScale3D();
            const FQuat Rotation = Transform.GetRotation();
            J Textures = J::array();
            J GroundFit = nullptr;
            TSet<UTexture2D*> Seen;
            for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot)
                if (UMaterialInterface* Material = Component->GetMaterial(Slot))
                {
                    float Enabled = 0.f, RegionIndex = -1.f;
                    FLinearColor Origin = FLinearColor::Black, FoundationExtent = FLinearColor::Black;
                    if (Material->GetScalarParameterValue(FMaterialParameterInfo(TEXT("FitEnabled")), Enabled))
                    {
                        Material->GetScalarParameterValue(FMaterialParameterInfo(TEXT("Region")), RegionIndex);
                        Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("GroundOrigin")), Origin);
                        Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("FoundationExtent")), FoundationExtent);
                        GroundFit = {{"enabled", Enabled}, {"region", RegionIndex}, {"origin", {Origin.R, Origin.G, Origin.B}},
                            {"foundation_extent", {FoundationExtent.R, FoundationExtent.G, FoundationExtent.B}}};
                        GroundFit["material"] = TCHAR_TO_UTF8(*Material->GetMaterial()->GetPathName());
                    }
                    TArray<UTexture*> Used;
                    Material->GetUsedTextures(Used);
                    for (UTexture* Texture : Used)
                        if (UTexture2D* Image = Cast<UTexture2D>(Texture); Image && !Seen.Contains(Image))
                        {
                            Seen.Add(Image);
                            Textures.push_back({{"path", std::string(TCHAR_TO_UTF8(*Image->GetPathName()))},
                                {"resident_mips", Image->GetNumResidentMips()},
                                {"allowed_mips", Image->GetNumMipsAllowed(false)}, {"total_mips", Image->GetNumMips()}});
                        }
                }
            Result["holding_components"].push_back({
                {"mesh", std::string(TCHAR_TO_UTF8(*Component->GetStaticMesh()->GetPathName()))},
                {"visible", Component->IsVisible()}, {"location", {Location.X, Location.Y, Location.Z}},
                {"scale", {Scale.X, Scale.Y, Scale.Z}},
                {"quaternion_xyzw", {Rotation.X, Rotation.Y, Rotation.Z, Rotation.W}}, {"textures", Textures}, {"ground_fit", GroundFit}});
        }
        Result["animated_part_count"] = CampVisuals->GetAnimatedPartCount();
        Result["visible_damage_fire_parts"] = CampVisuals->GetVisibleDamageFireParts();
        Result["visible_ruin_smoke_parts"] = CampVisuals->GetVisibleRuinSmokeParts();
        const FVector Smoke = CampVisuals->GetRuinSmokeSample();
        Result["ruin_smoke_sample"] = J::array({Smoke.X,Smoke.Y,Smoke.Z});
        const FVector Front = CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0, -1, 0));
        Result["world_front"] = J::array({Front.X, Front.Y, Front.Z});
        Result["faces_opponent"] = FVector::DotProduct(Front, FVector(0, Side == 0 ? -1 : 1, 0)) > .99f;
    }
    else if (!EventToken && Body->GetSkeletalMeshAsset())
    {
        Result["pose_samples"] = J::array();
        for (const FName Bone : {FName(TEXT("Hips")), FName(TEXT("Head")), FName(TEXT("LeftHand")), FName(TEXT("RightHand"))})
        {
            const FVector Position = Body->GetSocketLocation(Bone) - GetActorLocation();
            Result["pose_samples"].push_back({Position.X, Position.Y, Position.Z});
        }
    }
    if (!Camp && !EventToken && !Unarmed && WeaponContactsValid)
    {
        auto Vector = [](const FVector& P) { return J::array({P.X, P.Y, P.Z}); };
        const FVector Right = Weapon->GetComponentTransform().TransformPosition(WeaponRightGripLocal);
        const FVector Left = Weapon->GetComponentTransform().TransformPosition(WeaponLeftGripLocal);
        Result["weapon_alignment"] = {{"native_forward_axis", "+Y"},
            {"right_grip_local", Vector(WeaponRightGripLocal)}, {"left_grip_local", Vector(WeaponLeftGripLocal)},
            {"right_palm_world", Vector(WeaponRightPalmWorld)}, {"left_palm_world", Vector(WeaponLeftPalmWorld)},
            {"right_grip_world", Vector(Right)}, {"left_grip_world", Vector(Left)},
            {"right_contact_gap_cm", FVector::Dist(Right, WeaponRightPalmWorld)},
            {"left_contact_gap_cm", FVector::Dist(Left, WeaponLeftPalmWorld)},
            {"live_right_palm_gap_cm", FVector::Dist(Right, PalmContact(TEXT("Right")))},
            {"live_left_palm_gap_cm", FVector::Dist(Left, PalmContact(TEXT("Left")))},
            {"two_hand_pose", ActiveClip.Contains(TEXT("Rifle"))},
            {"scale", Vector(Weapon->GetComponentScale())},
            {"material", Weapon->GetMaterial(0) ? std::string(TCHAR_TO_UTF8(*Weapon->GetMaterial(0)->GetPathName())) : std::string()}};
    }
    // Existing weapon_alignment remains the instantaneous call-site sample.
    // Lifecycle polling occurs in the controller's PrePhysics tick; the new
    // field is the last completed actor-tick snapshot with its own identity.
    Result["weapon_observation_query_frame"] = GFrameCounter;
    Result["completed_weapon_observation"] = CompletedWeaponObservation.IsEmpty()
        ? J(nullptr) : J::parse(TCHAR_TO_UTF8(*CompletedWeaponObservation));
    Result["completed_weapon_observation_age_frames"] = CompletedWeaponObservationFrame == MAX_uint64
        || GFrameCounter < CompletedWeaponObservationFrame ? J(nullptr) : J(GFrameCounter - CompletedWeaponObservationFrame);
    return Text(Result.dump());
#else
    return TEXT("{}");
#endif
}

#if !UE_BUILD_SHIPPING
void AOldWestUnit::SampleCompletedWeaponObservation(const FString& MatchId, int32 Sequence,
    const FString& Kind, float Elapsed, bool Busy)
{
    const UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance();
    const bool Eligible = !HasManualPresentation() && !Camp && !EventToken && !Unarmed && !PreviewOnly && !Dead && !Ragdoll
        && !IsHidden() && Body->IsVisible() && Weapon->IsVisible() && WeaponContactsValid
        && Body->GetSkeletalMeshAsset() && Weapon->GetStaticMesh();
    auto Vector = [](const FVector& P) { return J::array({P.X, P.Y, P.Z}); };
    auto Transform = [&Vector](const FTransform& T)
    {
        const FQuat Q = T.GetRotation();
        return J{{"location", Vector(T.GetLocation())}, {"scale", Vector(T.GetScale3D())},
            {"quaternion_xyzw", {Q.X, Q.Y, Q.Z, Q.W}}};
    };
    J Result = {{"semantics", "last_completed_world_post_actor_tick"}, {"sample_frame", GFrameCounter},
        {"match_id", std::string(TCHAR_TO_UTF8(*MatchId))}, {"sequence", Sequence},
        {"kind", std::string(TCHAR_TO_UTF8(*Kind))}, {"elapsed", Elapsed}, {"busy", Busy},
        {"id", EntityId}, {"side", Side}, {"card_id", std::string(TCHAR_TO_UTF8(*CanonicalCardId))}, {"visual_id", std::string(TCHAR_TO_UTF8(*VisualCardId))},
        {"eligible", Eligible}, {"preview_only", PreviewOnly}, {"hidden", IsHidden()},
        {"camp", Camp}, {"event_token", EventToken}, {"unarmed", Unarmed}, {"dead", Dead}, {"ragdoll", Ragdoll},
        {"active_clip", std::string(TCHAR_TO_UTF8(*ActiveClip))},
        {"idle_clip", std::string(TCHAR_TO_UTF8(*IdleClip))}, {"action_seconds", AnimationTime},
        {"playing", Instance ? Instance->IsPlaying() : false}, {"looping", Instance ? Instance->IsLooping() : false},
        {"animation_position", Instance ? Instance->GetCurrentTime() : 0.f},
        {"travelling", Travelling}, {"travel_elapsed", TravelElapsed}, {"travel_duration", TravelDuration},
        {"bone_revision", Body->GetBoneTransformRevisionNumber()}, {"bone_frame", Body->GetCurrentBoneTransformFrame()},
        {"alignment_frame", WeaponAlignmentFrame == MAX_uint64 ? J(nullptr) : J(WeaponAlignmentFrame)},
        {"alignment_bone_revision", WeaponAlignmentBoneRevision}, {"alignment_bone_frame", WeaponAlignmentBoneFrame},
        {"body_transform", Transform(Body->GetComponentTransform())},
        {"weapon_transform", Transform(Weapon->GetComponentTransform())}, {"weapon_alignment", nullptr}};
    Result["manual_presentation"] = J::parse(TCHAR_TO_UTF8(*GetManualPresentationDebug()));
    if (Eligible)
    {
        const FVector RightGrip = Weapon->GetComponentTransform().TransformPosition(WeaponRightGripLocal);
        const FVector LeftGrip = Weapon->GetComponentTransform().TransformPosition(WeaponLeftGripLocal);
        const FVector RightPalm = PalmContact(TEXT("Right")), LeftPalm = PalmContact(TEXT("Left"));
        Result["weapon_alignment"] = {{"native_forward_axis", "+Y"},
            {"right_grip_local", Vector(WeaponRightGripLocal)}, {"left_grip_local", Vector(WeaponLeftGripLocal)},
            {"right_palm_world", Vector(RightPalm)}, {"left_palm_world", Vector(LeftPalm)},
            {"right_grip_world", Vector(RightGrip)}, {"left_grip_world", Vector(LeftGrip)},
            {"cached_right_palm_world", Vector(WeaponRightPalmWorld)}, {"cached_left_palm_world", Vector(WeaponLeftPalmWorld)},
            {"right_contact_gap_cm", FVector::Dist(RightGrip, RightPalm)},
            {"left_contact_gap_cm", FVector::Dist(LeftGrip, LeftPalm)},
            {"live_right_palm_gap_cm", FVector::Dist(RightGrip, RightPalm)},
            {"live_left_palm_gap_cm", FVector::Dist(LeftGrip, LeftPalm)},
            {"two_hand_pose", ActiveClip.Contains(TEXT("Rifle"))},
            {"scale", Vector(Weapon->GetComponentScale())},
            {"material", Weapon->GetMaterial(0) ? std::string(TCHAR_TO_UTF8(*Weapon->GetMaterial(0)->GetPathName())) : std::string()}};
    }
    CompletedWeaponObservation = Text(Result.dump());
    CompletedWeaponObservationFrame = GFrameCounter;
}
#endif

void AOldWestUnit::ResetPose()
{
    InterruptManualPresentation(TEXT("reset_pose"));
    Travelling = false;
    RagdollDelay = -1.f;
    ResetRagdollPoseSamples();
    AnimationTime = 0.f;
    WeaponContactsValid = false;
    Dead = Ragdoll = false;
#if !UE_BUILD_SHIPPING
    RagdollInitialPhysics.Reset();
    if (RagdollContactId) Body->SetAllBodiesNotifyRigidBodyCollision(false);
    RagdollContactId = RagdollContactEvents = 0;
    CompletedWeaponObservation.Reset();
    CompletedWeaponObservationFrame = WeaponAlignmentFrame = MAX_uint64;
    WeaponAlignmentBoneRevision = WeaponAlignmentBoneFrame = 0;
#endif
    Body->SetForcedLOD(0);
    Body->bPauseAnims = false;
    Body->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
    Body->SetSimulatePhysics(false);
    Body->SetAllBodiesSimulatePhysics(false);
    Body->SetAllBodiesPhysicsBlendWeight(0.f);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Body->AttachToComponent(RootComponent, FAttachmentTransformRules::KeepRelativeTransform);
    Body->SetRelativeLocation(FVector::ZeroVector);
    Body->SetRelativeRotation(Facing);
    SetActorHiddenInGame(false);
    Caption->SetRelativeLocation(FVector(0, 0, Camp ? 260.f : EventToken ? 165.f : 225.f));
    Weapon->SetVisibility(!Camp && !Unarmed && !EventToken);
    PlayIdle();
}

void AOldWestUnit::AimAt(const FVector& Target)
{
    InterruptManualPresentation(TEXT("aim_change"));
    if (Camp || Dead || EventToken) return;
    Facing = FRotator(0, (Target - GetActorLocation()).Rotation().Yaw - 90.f, 0);
    Body->SetRelativeRotation(Facing);
}

FVector AOldWestUnit::PalmContact(const TCHAR* SideName) const
{
    const FString Prefix(SideName);
    const FName Wrist(*FString(Prefix + TEXT("Hand")));
    const FName Knuckle(*FString(Prefix + TEXT("HandMiddle1")));
    const FName Finger(*FString(Prefix + TEXT("HandMiddle2")));
    const FVector Start = Body->GetSocketLocation(Wrist);
    if (Body->GetBoneIndex(Knuckle) == INDEX_NONE || Body->GetBoneIndex(Finger) == INDEX_NONE) return Start;
    const FVector Middle = Body->GetSocketLocation(Knuckle);
    const FVector AlongHand = (Middle - Start).GetSafeNormal();
    const FVector Bend = Body->GetSocketLocation(Finger) - Middle;
    // Finger curvature supplies the inward palm normal for either hand and
    // follows animated wrist roll. A wrist origin is behind the actual grip.
    const FVector IntoPalm = (Bend - AlongHand * FVector::DotProduct(Bend, AlongHand)).GetSafeNormal();
    const float Scale = Body->GetComponentScale().GetAbsMax();
    return FMath::Lerp(Start, Middle, .58f) + IntoPalm * (.9f * Scale);
}

void AOldWestUnit::AlignWeaponToHands()
{
    if (HasManualPresentation()) return;
    if (Camp || EventToken || Unarmed || Dead || !Body->GetSkeletalMeshAsset() || !Weapon->GetStaticMesh()) return;
    WeaponRightPalmWorld = PalmContact(TEXT("Right"));
    WeaponLeftPalmWorld = PalmContact(TEXT("Left"));
    const FVector BetweenPalms = WeaponLeftPalmWorld - WeaponRightPalmWorld;
    if (BetweenPalms.IsNearlyZero()) return;
    const FVector Scale = Weapon->GetComponentScale();
    const float UniformScale = FMath::Max(static_cast<float>(Scale.GetAbsMax()), .001f);
    const float Span = BetweenPalms.Size() / UniformScale;
    // The exported mesh has its muzzle along +Y, not +X. The right palm
    // contacts the pistol grip's left face. The left palm contacts the other
    // side of its underside rail (Y22.8..36.9, Z2.8cm). Idle/fire clips grip
    // different points along that real rail, without stretching the weapon.
    const float Across = WeaponLeftGripLocal.X - WeaponRightGripLocal.X;
    const float Up = WeaponLeftGripLocal.Z - WeaponRightGripLocal.Z;
    WeaponLeftGripLocal.Y = FMath::Clamp(static_cast<float>(WeaponRightGripLocal.Y) + FMath::Sqrt(FMath::Max(0.f,
        Span * Span - Across * Across - Up * Up)), 22.8f, 36.9f);
    const FVector LocalContacts = (WeaponLeftGripLocal - WeaponRightGripLocal) * Scale;
    const FQuat Orientation = FRotationMatrix::MakeFromYZ(BetweenPalms, FVector::UpVector).ToQuat()
        * FRotationMatrix::MakeFromYZ(LocalContacts, FVector::UpVector).ToQuat().Inverse();
    Weapon->SetWorldRotation(Orientation);
    Weapon->SetWorldLocation(WeaponRightPalmWorld - Orientation.RotateVector(WeaponRightGripLocal * Scale));
    WeaponContactsValid = true;
#if !UE_BUILD_SHIPPING
    WeaponAlignmentFrame = GFrameCounter;
    WeaponAlignmentBoneRevision = Body->GetBoneTransformRevisionNumber();
    WeaponAlignmentBoneFrame = Body->GetCurrentBoneTransformFrame();
#endif
}

FVector AOldWestUnit::GetPresentationFocus() const
{
    if (EventToken) return GetVisualBounds().GetCenter();
    if (!Camp && Body->GetBoneIndex(PelvisBone) != INDEX_NONE)
        return Body->GetSocketLocation(PelvisBone) + FVector(0, 0, Ragdoll ? 12.f : 30.f);
    if (Camp && CampVisuals->GetVisualBounds().IsValid) return CampVisuals->GetVisualBounds().GetCenter();
    return GetActorLocation() + FVector(0, 0, 100);
}

float AOldWestUnit::GetRootDrift() const
{
    if (Camp || Ragdoll || !Body->GetSkeletalMeshAsset()) return 0.f;
    const FVector Expected = GetActorLocation() + Facing.RotateVector(RootFrame.GetLocation());
    return FVector::Dist(Body->GetSocketLocation(TEXT("root")), Expected);
}

void AOldWestUnit::ResetRagdollPoseSamples()
{
    RagdollPoseSamples.Reset();
    RagdollPoseFrame = RagdollPosePreviousFrame = MAX_uint64;
    RagdollPoseDeltaSeconds = 0.f;
    RagdollPoseMaxSpeed = RagdollPoseMaxAngularSpeed = 0.;
    RagdollPoseSampleValid = RagdollPoseCacheComplete = false;
}

void AOldWestUnit::SampleRagdollPose(float DeltaSeconds)
{
    const uint64 Frame = GFrameCounter;
    if (RagdollPoseFrame == Frame) return;
    // Match the physics-time cap used by the presentation's stable interval.
    // A stalled render frame must not dilute measured physical movement.
    const UPhysicsSettings* Settings = UPhysicsSettings::Get();
    const float Cap = Settings->bSubstepping ? Settings->MaxSubstepDeltaTime * Settings->MaxSubsteps : Settings->MaxPhysicsDeltaTime;
    const float Step = Cap > 0.f ? FMath::Min(DeltaSeconds, Cap) : DeltaSeconds;
    const bool ValidInterval = FMath::IsFinite(DeltaSeconds) && FMath::IsFinite(Step) && Step > UE_SMALL_NUMBER;
    TArray<FRagdollPoseObservation> Current;
    Current.Reserve(Body->Bodies.Num());
    TSet<FName> Identities;
    bool Complete = Body->Bodies.Num() == 16;
    for (const FBodyInstance* Instance : Body->Bodies)
    {
        if (!Instance || !Instance->IsValidBodyInstance()) { Complete = false; continue; }
        const FName Bone = Body->GetBoneName(Instance->InstanceBoneIndex);
        // Obtain COM and its inertia-frame orientation from one physics read.
        // Separate reads can straddle an asynchronous physics update.
        const FTransform MassPose = Instance->GetMassSpaceToWorldSpace();
        const FVector Center = MassPose.GetLocation();
        FQuat Rotation = MassPose.GetRotation();
        const double RotationSizeSquared = Rotation.SizeSquared();
        if (Bone.IsNone() || Identities.Contains(Bone) || Center.ContainsNaN() || Rotation.ContainsNaN() ||
            !FMath::IsFinite(RotationSizeSquared) || RotationSizeSquared <= UE_SMALL_NUMBER)
        {
            Complete = false;
            continue;
        }
        Rotation.Normalize();
        Identities.Add(Bone);
        FRagdollPoseObservation& Pose = Current.AddDefaulted_GetRef();
        Pose.Bone = Bone;
        Pose.PreviousCenter = Pose.CurrentCenter = Center;
        Pose.PreviousRotation = Pose.CurrentRotation = Rotation;
    }
    Complete &= Current.Num() == 16;
    bool Comparable = Complete && ValidInterval && RagdollPoseCacheComplete &&
        RagdollPoseFrame != MAX_uint64 && RagdollPoseFrame + 1 == Frame &&
        RagdollPoseSamples.Num() == Current.Num();
    if (Comparable)
        for (int32 Index = 0; Index < Current.Num(); ++Index)
            Comparable &= Current[Index].Bone == RagdollPoseSamples[Index].Bone;
    RagdollPoseSampleValid = Comparable;
    RagdollPoseMaxSpeed = RagdollPoseMaxAngularSpeed = 0.;
    if (Comparable)
    {
        for (int32 Index = 0; Index < Current.Num(); ++Index)
        {
            FRagdollPoseObservation& Pose = Current[Index];
            Pose.PreviousCenter = RagdollPoseSamples[Index].CurrentCenter;
            Pose.PreviousRotation = RagdollPoseSamples[Index].CurrentRotation;
            Pose.Speed = FVector::Dist(Pose.PreviousCenter, Pose.CurrentCenter) / Step;
            const double Dot = FMath::Clamp(FMath::Abs(Pose.PreviousRotation | Pose.CurrentRotation), 0., 1.);
            Pose.AngularSpeed = FMath::RadiansToDegrees(2. * FMath::Acos(Dot)) / Step;
            if (!FMath::IsFinite(Pose.Speed) || !FMath::IsFinite(Pose.AngularSpeed)) RagdollPoseSampleValid = false;
            else
            {
                RagdollPoseMaxSpeed = FMath::Max(RagdollPoseMaxSpeed, Pose.Speed);
                RagdollPoseMaxAngularSpeed = FMath::Max(RagdollPoseMaxAngularSpeed, Pose.AngularSpeed);
            }
        }
    }
    RagdollPosePreviousFrame = RagdollPoseFrame;
    RagdollPoseFrame = Frame;
    RagdollPoseDeltaSeconds = ValidInterval ? Step : 0.f;
    RagdollPoseCacheComplete = Complete && ValidInterval;
    RagdollPoseSamples = MoveTemp(Current);
}

bool AOldWestUnit::IsRagdollSettled(FString* FailureReason) const
{
    if (FailureReason) FailureReason->Reset();
    auto Fail = [FailureReason](const TCHAR* Reason, FName Bone = NAME_None, double Value = 0.)
    {
        if (FailureReason)
            *FailureReason = FString::Printf(TEXT("%s:%s:%.6f"), Reason, *Bone.ToString(), Value);
        return false;
    };
    // Inspect the actual simulated rig in shipping too. A missing or invalid
    // body cannot make a shot look settled merely by reducing the sample set.
    // Projection may move a body without that movement appearing in its stored
    // velocity. Require independently measured motion from this physics frame.
    if (!Ragdoll) return Fail(TEXT("not_ragdoll"));
    if (Body->Bodies.Num() != 16) return Fail(TEXT("body_count"), NAME_None, Body->Bodies.Num());
    if (!RagdollPoseSampleValid) return Fail(TEXT("pose_invalid"));
    if (RagdollPoseFrame != GFrameCounter) return Fail(TEXT("pose_frame_age"), NAME_None, GFrameCounter - RagdollPoseFrame);
    if (RagdollPoseMaxSpeed > 20.) return Fail(TEXT("pose_linear_cm_s"), NAME_None, RagdollPoseMaxSpeed);
    if (RagdollPoseMaxAngularSpeed > 45.) return Fail(TEXT("pose_angular_deg_s"), NAME_None, RagdollPoseMaxAngularSpeed);
    for (const FBodyInstance* Instance : Body->Bodies)
    {
        if (!Instance || !Instance->IsValidBodyInstance()) return Fail(TEXT("invalid_body"));
        const float Speed = Instance->GetUnrealWorldVelocity().Size();
        const float AngularSpeed = Instance->GetUnrealWorldAngularVelocityInRadians().Size() * (180.f / PI);
        if (!FMath::IsFinite(Speed) || !FMath::IsFinite(AngularSpeed)) return Fail(TEXT("nonfinite_velocity"));
        if (Speed > 20.f) return Fail(TEXT("reported_linear_cm_s"), Body->GetBoneName(Instance->InstanceBoneIndex), Speed);
        if (AngularSpeed > 45.f) return Fail(TEXT("reported_angular_deg_s"), Body->GetBoneName(Instance->InstanceBoneIndex), AngularSpeed);
    }
    const FVector Pelvis = Body->GetSocketLocation(PelvisBone);
    FHitResult Ground;
    if (!GetWorld()->LineTraceSingleByChannel(Ground, Pelvis + FVector(0, 0, 200.f), Pelvis - FVector(0, 0, 600.f), ECC_Visibility)) return Fail(TEXT("ground_missing"));
    const float Clearance = Pelvis.Z - Ground.ImpactPoint.Z;
    if (!FMath::IsFinite(Clearance) || Clearance < -5.f || Clearance > 65.f) return Fail(TEXT("ground_clearance_cm"), NAME_None, Clearance);
    return true;
}

#if !UE_BUILD_SHIPPING
void AOldWestUnit::DispatchPhysicsCollisionHit(const FRigidBodyCollisionInfo& MyInfo,
    const FRigidBodyCollisionInfo& OtherInfo, const FCollisionImpactData& Collision)
{
    // Retain the engine's dispatched contact data before the standard actor
    // callback reduces it to one FHitResult. This does not alter an impulse.
    if (Ragdoll && RagdollContactId && MyInfo.Component.Get() == Body && RagdollContacts().Enabled())
    {
        auto Vector = [](const FVector& V) { return J::array({V.X, V.Y, V.Z}); };
        J Event = {{"fall_id", RagdollContactId}, {"event_index", RagdollContactEvents},
            {"target", EntityId}, {"card_id", std::string(TCHAR_TO_UTF8(*CanonicalCardId))}, {"visual_id", std::string(TCHAR_TO_UTF8(*VisualCardId))},
            {"actor", std::string(TCHAR_TO_UTF8(*GetPathName()))}, {"dispatch_frame", GFrameCounter},
            {"dispatch_world_seconds", GetWorld()->GetTimeSeconds()},
            {"seconds_since_ragdoll", GetWorld()->GetTimeSeconds() - RagdollContactStartSeconds},
            {"bone", std::string(TCHAR_TO_UTF8(*MyInfo.BoneName.ToString()))},
            {"other_bone", std::string(TCHAR_TO_UTF8(*OtherInfo.BoneName.ToString()))},
            {"other_component", OtherInfo.Component.IsValid() ? std::string(TCHAR_TO_UTF8(*OtherInfo.Component->GetPathName())) : std::string()},
            {"self_contact", OtherInfo.Component.Get() == Body},
            {"normal_impulse_native", Vector(Collision.TotalNormalImpulse)},
            {"friction_impulse_native", Vector(Collision.TotalFrictionImpulse)},
            {"body_delta_velocity_cm_s", Vector(MyInfo.DeltaVelocity)},
            {"other_body_delta_velocity_cm_s", Vector(OtherInfo.DeltaVelocity)},
            {"under_engine_velocity_delta_threshold", Collision.bIsVelocityDeltaUnderThreshold},
            {"contacts", J::array()}};
        for (const FRigidBodyContactInfo& Contact : Collision.ContactInfos)
            Event["contacts"].push_back({{"position_cm", Vector(Contact.ContactPosition)},
                {"normal_toward_body", Vector(Contact.ContactNormal)},
                {"penetration_cm", Contact.ContactPenetration}, {"probe", Contact.bContactProbe}});
        if (RagdollContacts().Write(Event)) ++RagdollContactEvents;
    }
    Super::DispatchPhysicsCollisionHit(MyInfo, OtherInfo, Collision);
}
#endif

FString AOldWestUnit::GetPhysicsDebug() const
{
#if !UE_BUILD_SHIPPING
    J Result = {{"bodies", J::array()}, {"max_speed_cm_s", 0.f}, {"max_angular_speed_deg_s", 0.f}};
    if (!Ragdoll) return Text(Result.dump());
    if (RagdollContacts().Requested)
    {
        RagdollContacts().Drain();
        Result["contact_recording"] = {{"enabled", RagdollContacts().Enabled()},
            {"fall_id", RagdollContactId}, {"events_written", RagdollContactEvents},
            {"report", std::string(TCHAR_TO_UTF8(*RagdollContacts().Path))},
            {"io_policy", "batched writes to OS cache; no forced disk synchronization"},
            {"write_calls", RagdollContacts().WriteCalls}, {"bytes_written", RagdollContacts().BytesWritten},
            {"write_ms_total", RagdollContacts().WriteSeconds * 1000.},
            {"write_ms_max", RagdollContacts().MaxWriteSeconds * 1000.},
            {"scope", "engine-dispatched collision notifications; not every solver manifold point or zero-impulse contact"}};
    }
    auto PoseVector = [](const FVector& V) { return J::array({V.X, V.Y, V.Z}); };
    auto PoseRotation = [](const FQuat& Q) { return J::array({Q.X, Q.Y, Q.Z, Q.W}); };
    J PoseMotion = {{"valid", RagdollPoseSampleValid},
        {"sample_frame", RagdollPoseFrame == MAX_uint64 ? J(nullptr) : J(RagdollPoseFrame)},
        {"previous_frame", RagdollPosePreviousFrame == MAX_uint64 ? J(nullptr) : J(RagdollPosePreviousFrame)},
        {"query_frame", GFrameCounter}, {"body_count", RagdollPoseSamples.Num()},
        {"delta_seconds", RagdollPoseDeltaSeconds},
        {"max_speed_cm_s", RagdollPoseSampleValid ? J(RagdollPoseMaxSpeed) : J(nullptr)},
        {"max_angular_speed_deg_s", RagdollPoseSampleValid ? J(RagdollPoseMaxAngularSpeed) : J(nullptr)},
        {"bodies", J::array()}};
    for (const FRagdollPoseObservation& Pose : RagdollPoseSamples)
        PoseMotion["bodies"].push_back({{"bone", std::string(TCHAR_TO_UTF8(*Pose.Bone.ToString()))},
            {"previous_com_cm", PoseVector(Pose.PreviousCenter)}, {"current_com_cm", PoseVector(Pose.CurrentCenter)},
            {"previous_rotation_xyzw", PoseRotation(Pose.PreviousRotation)}, {"current_rotation_xyzw", PoseRotation(Pose.CurrentRotation)},
            {"speed_cm_s", RagdollPoseSampleValid ? J(Pose.Speed) : J(nullptr)},
            {"angular_speed_deg_s", RagdollPoseSampleValid ? J(Pose.AngularSpeed) : J(nullptr)}});
    Result["pose_motion"] = MoveTemp(PoseMotion);
    Result["collision_responses"] = {{"object_type", static_cast<int32>(Body->GetCollisionObjectType())},
        {"physics_body_blocked", Body->GetCollisionResponseToChannel(ECC_PhysicsBody) == ECR_Block},
        {"world_static_blocked", Body->GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Block}};
    Result["forearm_chest_collision_enabled"] = J::object();
    const UPhysicsAsset* PhysicsAsset = Body->GetPhysicsAsset();
    const int32 LeftThigh = PhysicsAsset ? PhysicsAsset->FindBodyIndex(TEXT("LeftUpLeg")) : INDEX_NONE;
    const int32 RightThigh = PhysicsAsset ? PhysicsAsset->FindBodyIndex(TEXT("RightUpLeg")) : INDEX_NONE;
    Result["thigh_collision_enabled"] = LeftThigh != INDEX_NONE && RightThigh != INDEX_NONE &&
        PhysicsAsset->IsCollisionEnabled(LeftThigh, RightThigh);
    const int32 ChestIndex = PhysicsAsset ? PhysicsAsset->FindBodyIndex(TEXT("Spine2")) : INDEX_NONE;
    for (const FName Forearm : {FName(TEXT("LeftForeArm")), FName(TEXT("RightForeArm"))})
    {
        const int32 ForearmIndex = PhysicsAsset ? PhysicsAsset->FindBodyIndex(Forearm) : INDEX_NONE;
        Result["forearm_chest_collision_enabled"][std::string(TCHAR_TO_UTF8(*Forearm.ToString()))] =
            ChestIndex != INDEX_NONE && ForearmIndex != INDEX_NONE && PhysicsAsset->IsCollisionEnabled(ForearmIndex, ChestIndex);
    }
    if (!RagdollInitialPhysics.IsEmpty())
        Result["handoff_before_simulation"] = J::parse(TCHAR_TO_UTF8(*RagdollInitialPhysics));
    float Speed = 0.f, AngularSpeed = 0.f;
    for (const FBodyInstance* Instance : Body->Bodies) if (Instance && Instance->IsValidBodyInstance())
    {
        const FVector Velocity = Instance->GetUnrealWorldVelocity();
        const FVector AngularVelocity = Instance->GetUnrealWorldAngularVelocityInRadians() * (180.f / PI);
        const FVector Position = Instance->GetCOMPosition();
        const FQuat Rotation = Instance->GetUnrealWorldTransform().GetRotation();
        Speed = FMath::Max(Speed, static_cast<float>(Velocity.Size()));
        AngularSpeed = FMath::Max(AngularSpeed, static_cast<float>(AngularVelocity.Size()));
        const FVector Extent = Instance->GetBodyBounds().GetExtent();
        const UPhysicalMaterial* Material = Instance->GetSimplePhysicalMaterial();
        Result["bodies"].push_back({{"bone", std::string(TCHAR_TO_UTF8(*Body->GetBoneName(Instance->InstanceBoneIndex).ToString()))},
            {"mass_kg", Instance->GetBodyMass()}, {"extent_cm", {Extent.X, Extent.Y, Extent.Z}},
            {"position_cm", {Position.X, Position.Y, Position.Z}}, {"velocity_cm_s", {Velocity.X, Velocity.Y, Velocity.Z}},
            {"rotation_xyzw", {Rotation.X, Rotation.Y, Rotation.Z, Rotation.W}},
            {"angular_velocity_deg_s", {AngularVelocity.X, AngularVelocity.Y, AngularVelocity.Z}},
            {"speed_cm_s", Velocity.Size()}, {"angular_speed_deg_s", AngularVelocity.Size()}, {"awake", Instance->IsInstanceAwake()},
            {"restitution", Material ? Material->Restitution : -1.f},
            {"angular_damping", Instance->AngularDamping},
            {"collision_notifications_enabled", static_cast<bool>(Instance->bNotifyRigidBodyCollision)},
            {"physics_body_blocked", Instance->GetResponseToChannel(ECC_PhysicsBody) == ECR_Block},
            {"world_static_blocked", Instance->GetResponseToChannel(ECC_WorldStatic) == ECR_Block},
            {"iteration_overrides_enabled", Instance->GetPositionSolverIterationCount() >= 0},
            {"position_solver_iterations", Instance->GetPositionSolverIterationCount()},
            {"velocity_solver_iterations", Instance->GetVelocitySolverIterationCount()},
            {"projection_solver_iterations", Instance->GetProjectionSolverIterationCount()}});
    }
    Result["max_speed_cm_s"] = Speed; Result["max_angular_speed_deg_s"] = AngularSpeed;
    Result["joints"] = J::array();
    for (const FConstraintInstance* Joint : Body->Constraints)
        if (Joint && Joint->IsValidConstraintInstance())
        {
            float DriveSpring, DriveDamping, DriveForceLimit;
            Joint->GetAngularDriveParams(DriveSpring, DriveDamping, DriveForceLimit);
            J Entry = {{"joint", std::string(TCHAR_TO_UTF8(*Joint->JointName.ToString()))},
                {"orientation_drive_enabled", Joint->IsAngularOrientationDriveEnabled()},
                {"velocity_drive_enabled", Joint->IsAngularVelocityDriveEnabled()},
                {"drive_stiffness", DriveSpring}, {"drive_damping", DriveDamping},
                {"drive_force_limit", DriveForceLimit},
                {"swing1_degrees", FMath::RadiansToDegrees(Joint->GetCurrentSwing1())},
                {"swing2_degrees", FMath::RadiansToDegrees(Joint->GetCurrentSwing2())},
                {"twist_degrees", FMath::RadiansToDegrees(Joint->GetCurrentTwist())},
                {"angle_getter_semantics", "raw total-quaternion axis projections; swing1/2 are not solver swing coordinates"},
                {"swing1_limit_degrees", Joint->GetAngularSwing1Limit()},
                {"swing2_limit_degrees", Joint->GetAngularSwing2Limit()},
                {"twist_limit_degrees", Joint->GetAngularTwistLimit()},
                {"linear_solver_profile", static_cast<bool>(Joint->ProfileInstance.bUseLinearJointSolver)},
                {"mass_conditioning_enabled", Joint->IsMassConditioningEnabled()},
                {"projection_enabled", static_cast<bool>(Joint->ProfileInstance.bEnableProjection)}};
            const FBodyInstance* Child = Body->GetBodyInstance(Joint->ConstraintBone1);
            const FBodyInstance* Parent = Body->GetBodyInstance(Joint->ConstraintBone2);
            if (Child && Parent)
            {
                const FTransform ChildFrame = Joint->GetRefFrame(EConstraintFrame::Frame1) * Child->GetUnrealWorldTransform();
                const FTransform ParentFrame = Joint->GetRefFrame(EConstraintFrame::Frame2) * Parent->GetUnrealWorldTransform();
                Entry["anchor_separation_cm"] = FVector::Dist(ChildFrame.GetLocation(), ParentFrame.GetLocation());
            }
            Result["joints"].push_back(Entry);
        }
    const FVector Pelvis = Body->GetSocketLocation(PelvisBone);
    FHitResult Hit;
    const bool Ground = GetWorld()->LineTraceSingleByChannel(Hit, Pelvis + FVector(0, 0, 200.f), Pelvis - FVector(0, 0, 600.f), ECC_Visibility);
    Result["ground_found"] = Ground;
    Result["pelvis_ground_clearance_cm"] = Ground ? Pelvis.Z - Hit.ImpactPoint.Z : -1000.f;
    if (Ground)
    {
        Result["ground_hit_cm"] = {Hit.ImpactPoint.X, Hit.ImpactPoint.Y, Hit.ImpactPoint.Z};
        Result["ground_actor"] = Hit.GetActor() ? std::string(TCHAR_TO_UTF8(*Hit.GetActor()->GetPathName())) : std::string();
        Result["ground_component"] = Hit.GetComponent() ? std::string(TCHAR_TO_UTF8(*Hit.GetComponent()->GetPathName())) : std::string();
    }
    return Text(Result.dump());
#else
    return TEXT("{}");
#endif
}

void AOldWestUnit::StartRagdoll()
{
    InterruptManualPresentation(TEXT("ragdoll"));
    if (Camp || EventToken) return;
    RagdollDelay = -1.f;
    ResetRagdollPoseSamples();
    Weapon->SetVisibility(false);
    if (!Body->GetPhysicsAsset()) return;
    // All six supplied death clips end upright. Transfer the short reaction
    // to physics, with animation/drive updates stopped and initial velocity
    // cleared so the authored pose cannot continue driving the falling body.
    Body->bPauseAnims = true;
    Body->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    Body->bUpdateJointsFromAnimation = false;
    Body->SetCollisionObjectType(ECC_PhysicsBody);
    Body->SetCollisionResponseToAllChannels(ECR_Ignore);
    Body->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    // The physics asset excludes adjacent body pairs, while distant limbs
    // must still meet the torso. Ignoring PhysicsBody here suppresses those
    // intended self contacts and lets a falling hand pass through the pelvis.
    Body->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
    // A clothed body landing on dirt should not inherit the generic surface's
    // bounce. Preserve its other material properties and override restitution
    // only on this survivor, including its contacts with the terrain.
    if (!RagdollMaterial)
    {
        const FBodyInstance* Pelvis = Body->GetBodyInstance(PelvisBone);
        UPhysicalMaterial* Existing = Pelvis ? Pelvis->GetSimplePhysicalMaterial() : nullptr;
        RagdollMaterial = Existing ? DuplicateObject<UPhysicalMaterial>(Existing, this) : NewObject<UPhysicalMaterial>(this);
        RagdollMaterial->Restitution = 0.f;
        RagdollMaterial->bOverrideRestitutionCombineMode = true;
        RagdollMaterial->RestitutionCombineMode = EFrictionCombineMode::Min;
    }
    Body->SetPhysMaterialOverride(RagdollMaterial);
    Body->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Body->SetSimulatePhysics(true);
    Body->SetAllBodiesSimulatePhysics(true);
    Body->SetAllBodiesPhysicsBlendWeight(1.f);
    Body->SetAllMotorsAngularPositionDrive(false, false);
    Body->SetAllMotorsAngularVelocityDrive(false, false);
    // Recompute angular errors and axes during each solver iteration. The
    // cached linear solver sustained limb oscillation near angular limits on
    // this rig. Nonlinear joints use an elliptical swing cone. Avoid extra
    // joint-local mass/inertia scaling and post-solve projection against
    // contacts; retain authored angles, geometry, masses and body inertia.
    for (FConstraintInstance* Joint : Body->Constraints) if (Joint && Joint->IsValidConstraintInstance())
    {
        FConstraintProfileProperties Profile = Joint->ProfileInstance;
        Profile.bUseLinearJointSolver = false;
        Profile.bEnableMassConditioning = false;
        Profile.bEnableProjection = false;
        Joint->CopyProfilePropertiesFrom(Profile);
    }
#if !UE_BUILD_SHIPPING
    // Mass conditioning rescales inertia only for each joint, not its ground
    // or self contacts. Compare the authored physical masses consistently
    // across contacts and joints without changing the production joint solver.
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
        FParse::Param(FCommandLine::Get(), TEXT("OldWestRagdollNaturalMass")))
    {
        for (FConstraintInstance* Joint : Body->Constraints) if (Joint && Joint->IsValidConstraintInstance())
            Joint->DisableMassConditioning();
    }
    // Test hard joint solving with normal contacts, without a later projection
    // moving the child against a fixed parent and invalidating those contacts.
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
        FParse::Param(FCommandLine::Get(), TEXT("OldWestRagdollNoJointProjection")))
    {
        for (FConstraintInstance* Joint : Body->Constraints) if (Joint && Joint->IsValidConstraintInstance())
            Joint->DisableProjection();
    }
    // Isolated experiment: passive joint resistance with no pose target or
    // animation drive. Never enabled by a normal game launch.
    float DiagnosticJointDamping = 0.f;
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestCinematicDiagnostic")) &&
        FParse::Value(FCommandLine::Get(), TEXT("OldWestRagdollJointDamping="), DiagnosticJointDamping) &&
        FMath::IsFinite(DiagnosticJointDamping) && DiagnosticJointDamping > 0.f && DiagnosticJointDamping <= 100.f)
    {
        for (FConstraintInstance* Joint : Body->Constraints) if (Joint && Joint->IsValidConstraintInstance())
        {
            Joint->SetAngularDriveMode(EAngularDriveMode::SLERP);
            Joint->SetAngularDriveAccelerationMode(true);
            Joint->SetAngularVelocityTarget(FVector::ZeroVector);
            Joint->SetAngularDriveParams(0.f, DiagnosticJointDamping, 0.f);
            Joint->SetAngularVelocityDriveSLERP(true);
        }
    }
#endif
    // Some render-skeleton joints (clavicles and intermediate spine bones)
    // have no separate rigid body. Their animated pose moves the next body's
    // joint away from its reference-pose parent anchor. Align those linear
    // anchors once at handoff so the solver does not begin with a stretched
    // chain. The anatomical angular frames/limits remain in force afterwards.
    for (FConstraintInstance* Joint : Body->Constraints) if (Joint && Joint->IsValidConstraintInstance())
    {
        const FBodyInstance* Child = Body->GetBodyInstance(Joint->ConstraintBone1);
        const FBodyInstance* Parent = Body->GetBodyInstance(Joint->ConstraintBone2);
        if (!Child || !Parent) continue;
        const FTransform ChildFrame = Joint->GetRefFrame(EConstraintFrame::Frame1) * Child->GetUnrealWorldTransform();
        const FVector ParentAnchor = Parent->GetUnrealWorldTransform().InverseTransformPosition(ChildFrame.GetLocation());
        Joint->SetRefPosition(EConstraintFrame::Frame2, ParentAnchor);
    }
    Body->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    Body->SetAllPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    for (FBodyInstance* Instance : Body->Bodies) if (Instance)
    {
        // Skeletal initialization copies iteration counts from the component
        // after copying the asset body, replacing the authored values. Restore
        // the asset's enabled overrides on the live rigid bodies at handoff.
        const FName Bone = Body->GetBoneName(Instance->InstanceBoneIndex);
        const int32 DefinitionIndex = Body->GetPhysicsAsset()->FindBodyIndex(Bone);
        if (DefinitionIndex != INDEX_NONE)
        {
            const FBodyInstance& Authored = Body->GetPhysicsAsset()->SkeletalBodySetups[DefinitionIndex]->DefaultInstance;
            const int32 Positions = Authored.GetPositionSolverIterationCount();
            Instance->SetOverrideIterationCounts(Positions >= 0);
            if (Positions >= 0)
            {
                Instance->SetPositionSolverIterationCount(Positions);
                Instance->SetVelocitySolverIterationCount(Authored.GetVelocitySolverIterationCount());
                Instance->SetProjectionSolverIterationCount(Authored.GetProjectionSolverIterationCount());
            }
        }
        Instance->SetEnableGravity(true);
        Instance->LinearDamping = 0.5f;
        Instance->AngularDamping = 4.f;
        Instance->UpdateDampingProperties();
        Instance->SetMaxDepenetrationVelocity(60.f);
    }
    Body->WakeAllRigidBodies();
    Body->AddImpulse(FallDirection.GetSafeNormal2D() * 50.f, PelvisBone, true);
    Ragdoll = true;
#if !UE_BUILD_SHIPPING
    if (RagdollContacts().Enabled())
    {
        RagdollContactId = ++RagdollContacts().NextFallId;
        RagdollContactEvents = 0;
        RagdollContactStartSeconds = GetWorld()->GetTimeSeconds();
        Body->SetAllBodiesNotifyRigidBodyCollision(true);
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestCinematicDiagnostic")))
    {
        RagdollInitialPhysics.Reset();
        RagdollInitialPhysics = GetPhysicsDebug();
    }
#endif
}

void AOldWestUnit::PlayAction(const FString& Kind, const FVector& Direction)
{
    InterruptManualPresentation(TEXT("ordinary_action"));
    if (Raider && EventToken) { Impact->SetIntensity(0.f); return; }
    if (EventToken && (Kind == TEXT("damage") || Kind == TEXT("destroy"))) return;
    if (Kind == TEXT("destroy")) { Dead = true; UpdateWoundBandage(); }
    AnimationTime = Kind == TEXT("destroy") ? 1.2f : 0.65f;
    if (Kind == TEXT("restore"))
    {
        Impact->SetLightColor(FLinearColor(1.f, .78f, .44f));
        Impact->SetIntensity(180.f);
        if (!PreviewOnly) SpatialAudio(this, TEXT("SW_Ability_Restore"), GetPresentationFocus(), 0.85f);
    }
    else if (Kind == TEXT("damage") || Kind == TEXT("destroy"))
    {
        Impact->SetLightColor(FLinearColor(1.f, 0.28f, 0.05f));
        Impact->SetIntensity(1800.f);
        if (!PreviewOnly) SpatialAudio(this, Camp && Kind == TEXT("destroy") ? TEXT("SW_Camp_Collapse") :
            Camp ? FString(TEXT("SW_Impact_Wood_01")) :
                FString::Printf(TEXT("SW_Impact_Body_%02d"), FMath::RandRange(1, 2)),
            GetPresentationFocus(), Camp ? 0.8f : 0.65f);
        if (!Camp)
        {
            PlayClip(TEXT("MM_HitReact_Front_Lgt_01"), false);
            if (Kind == TEXT("destroy")) { RagdollDelay = 0.14f; FallDirection = Direction; }
        }
    }
    else if (Kind == TEXT("withdraw"))
    {
        Weapon->SetVisibility(false);
        SetActorHiddenInGame(true);
    }
    else if (Kind == TEXT("prepare_hit") && VisualCardId == TEXT("punk") && !Camp && !EventToken && !Dead)
    {
        // Only the opening guard of the existing generic attack, before a
        // strike. The authoritative, ordered damage beat still owns the hit.
        AimAt(GetActorLocation() + Direction);
        PlayClip(TEXT("MM_Attack_01"), false);
        if (UAnimSingleNodeInstance* Instance = Body->GetSingleNodeInstance()) Instance->SetPlayRate(.12f);
        AnimationTime = 1.3f;
        Impact->SetIntensity(0.f);
    }
    else if (Kind == TEXT("ability") || Kind == TEXT("event_resolve") || Kind == TEXT("expose_all"))
    {
        // A restrained warm action cue replaces the old blue machinery flash.
        Impact->SetLightColor(FLinearColor(1.f, .78f, .44f));
        Impact->SetIntensity(Camp || EventToken ? 350.f : 160.f);
        if (EventToken && OldWestTrouble::ForCard(TCHAR_TO_UTF8(*VisualCardId)))
        {
            Impact->SetLightColor(VisualCardId==TEXT("prairie_fire") ? FLinearColor(1.f,.24f,.025f) :
                VisualCardId==TEXT("hard_winter") ? FLinearColor(.72f,.85f,1.f) : FLinearColor(1.f,.78f,.44f));
            Impact->SetIntensity(350.f);
        }
        if (!PreviewOnly && Kind != TEXT("event_resolve"))
            SpatialAudio(this, Camp ? TEXT("SW_Impact_Wood_02") : TEXT("SW_Deck_Shuffle"), GetPresentationFocus(), .35f);
        if (!Camp && !EventToken && !Dead) AimAt(GetActorLocation() + Direction);
    }
    else if (!Camp && !EventToken && !Dead && Kind == TEXT("attack"))
    {
        // Retargeted clips are baked full poses, including the original additive
        // rifle motion, and are valid in a cooked single-node animation player.
        PlayClip(Unarmed ? TEXT("MM_Attack_01") : TEXT("MM_Rifle_Fire"), false);
        Impact->SetLightColor(FLinearColor(1.f, 0.65f, 0.27f));
        Impact->SetIntensity(650.f);
        if (!PreviewOnly) SpatialAudio(this, Unarmed ? FString(TEXT("SW_Melee_Swing")) :
            FString::Printf(TEXT("SW_Weapon_Rifle_%02d"), FMath::RandRange(1, 3)), GetPresentationFocus(), Unarmed ? .7f : .9f);
    }
}

void AOldWestUnit::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (IsValid(EventTurret))
    {
        const float Sweep = AnimationTime > 0.f ? 0.f : FMath::Sin(GetWorld()->GetTimeSeconds()*.65f + IdlePhase*6.28f)*11.f;
        const FRotator Aim(0,(Side==0?180.f:0.f)+Sweep,0);
        EventTurret->SetRelativeRotation(FMath::RInterpTo(EventTurret->GetRelativeRotation(),Aim,DeltaSeconds,4.f));
    }
    if (Travelling && !Ragdoll)
    {
        TravelElapsed += DeltaSeconds;
        const float T = FMath::Clamp(TravelElapsed / TravelDuration, 0.f, 1.f);
        float Remaining = T * TravelLength;
        FVector Location = TravelTo;
        for (int32 I = 1; I < TravelRoute.Num(); ++I)
        {
            const float Length = FVector::Distance(TravelRoute[I-1], TravelRoute[I]);
            if (Remaining <= Length || I == TravelRoute.Num() - 1)
            {
                Location = FMath::Lerp(TravelRoute[I-1], TravelRoute[I], Length > .01f ? FMath::Clamp(Remaining / Length, 0.f, 1.f) : 1.f);
                const FRotator Direction(0, (TravelRoute[I] - TravelRoute[I-1]).Rotation().Yaw - 90.f, 0);
                Facing = FMath::RInterpTo(Facing, Direction, DeltaSeconds, 8.f);
                break;
            }
            Remaining -= Length;
        }
        SetActorLocation(WalkGround(GetWorld(), Location, this));
        if (T >= 1.f)
        {
            Travelling = false;
            if (WithdrawAfterTravel) SetActorHiddenInGame(true);
            else { Facing = FRotator(0, Side == 0 ? 180 : 0, 0); PlayIdle(); }
        }
    }
    AmbientActivity=0.f;
    if(!HasManualPresentation()&&!Camp&&!EventToken&&!Dead&&!Ragdoll&&!Travelling&&VisualDamage==0&&AnimationTime<=0.f&&ActiveClip==IdleClip&&!PreviewOnly) {
        const auto* Player=Cast<AOldWestPlayerController>(GetWorld()->GetFirstPlayerController());
        const bool Cinematic=Player&&Player->IsCinematicBusy();
        const float Time=GetWorld()->GetTimeSeconds()+IdlePhase*29.f;
        const int32 Cycle=FMath::FloorToInt(Time/29.f);
        const uint32 ActivitySeed=HashCombine(GetTypeHash(EntityId),GetTypeHash(Cycle));
        const float Within=FMath::Fmod(Time,29.f);
        if(!Cinematic&&ActivitySeed%3==0&&Within<3.f)AmbientActivity=FMath::Square(FMath::Sin(PI*Within/3.f));
        if(auto* Instance=Body->GetSingleNodeInstance())Instance->SetPlayRate(IdleRate*AmbientActivity);
    }
    if (!HasManualPresentation() && !Camp && !EventToken && !Ragdoll && Body->GetSkeletalMeshAsset())
    {
        const FTransform AnimatedRoot = Body->GetSocketTransform(TEXT("root"), RTS_Component);
        const FQuat Rotation = Facing.Quaternion() * RootFrame.GetRotation() * AnimatedRoot.GetRotation().Inverse();
        Body->SetRelativeRotation(Rotation);
        Body->SetRelativeLocation(Facing.RotateVector(RootFrame.GetLocation()) - Rotation.RotateVector(AnimatedRoot.GetLocation()));
    }
    if (RagdollDelay >= 0.f)
    {
        RagdollDelay -= DeltaSeconds;
        if (RagdollDelay <= 0.f) StartRagdoll();
    }
    Impact->SetIntensity(FMath::FInterpTo(Impact->Intensity, 0.f, DeltaSeconds, 12.f));
    if (!HasManualPresentation() && AnimationTime > 0.f)
    {
        AnimationTime -= DeltaSeconds;
        if (AnimationTime <= 0.f && !Camp && !Dead) PlayIdle();
    }
    if (!HasManualPresentation() && !Camp && !EventToken && !Unarmed && !Dead && Body->GetSkeletalMeshAsset())
    {
        AlignWeaponToHands();
    }
    if (Ragdoll)
    {
        SampleRagdollPose(DeltaSeconds);
#if !UE_BUILD_SHIPPING
        if (RagdollContactId) RagdollContacts().Drain();
#endif
        Caption->SetWorldLocation(GetPresentationFocus() + FVector(0, 0, 55.f));
        DrawFallDiagnostics(GetWorld(), Body);
    }
    if (APlayerCameraManager* View = UGameplayStatics::GetPlayerCameraManager(this, 0))
        Caption->SetWorldRotation((View->GetCameraLocation() - Caption->GetComponentLocation()).Rotation());
}

bool AOldWestUnit::BeginManualPresentation(UObject* Owner,const FOldWestManualInterrupted& Interrupted)
{
    if (!IsValid(Owner) || HasManualPresentation() || Camp || EventToken || PreviewOnly || Dead || Ragdoll
        || Travelling || Unarmed || IsHidden() || !Body->GetSkeletalMeshAsset() || !Weapon->GetStaticMesh()
        || Body->GetAnimationMode()!=EAnimationMode::AnimationSingleNode) return false;
    UAnimSingleNodeInstance* Previous=Body->GetSingleNodeInstance();
    if (!Previous || ActiveClip!=IdleClip || AnimationTime>0.f) return false;
    ManualPreviousAsset=Previous->GetAnimationAsset(); ManualPreviousTime=Previous->GetCurrentTime();
    ManualPreviousRate=Previous->GetPlayRate(); ManualPreviousPlaying=Previous->IsPlaying();
    ManualPreviousLooping=Previous->IsLooping(); ManualPreviousActiveClip=ActiveClip;
    ManualEntryPose=Body->GetBoneSpaceTransforms();
    if (ManualEntryPose.Num()!=54) return false;
    ManualWeaponParent=Weapon->GetAttachParent(); ManualWeaponSocket=Weapon->GetAttachSocketName();
    ManualWeaponRelative=Weapon->GetRelativeTransform(); ManualWeaponVisible=Weapon->IsVisible(); ManualWeaponHidden=Weapon->bHiddenInGame;
    ManualBodyRelative=Body->GetRelativeTransform(); ManualBodyTick=Body->IsComponentTickEnabled();
    ManualBodyPause=Body->bPauseAnims; ManualBodyLOD=Body->GetForcedLOD();
    ManualPoseOwner=Owner; ManualInterrupted=Interrupted; ManualPhase=TEXT("entry_blend");
    ManualLastReleaseReason.Reset(); ManualSampleFrame=MAX_uint64; ManualSampleSeconds=0.; ManualEntryAlpha=0.f;
    // Keep the actor and physics tick policies untouched. Only this living
    // body's automatic animation tick is held while the director samples it.
    Body->SetComponentTickEnabled(false); Body->bPauseAnims=false; Body->SetForcedLOD(1);
    Body->SetAnimInstanceClass(UOldWestManualAnimInstance::StaticClass());
    if (!Cast<UOldWestManualAnimInstance>(Body->GetAnimInstance()))
    { EndManualPresentation(Owner,true,false); return false; }
    WeaponContactsValid=false; ManualRifleHeld=true; return true;
}

bool AOldWestUnit::SampleManualPresentation(UObject* Owner,UAnimSequence* Clip,double Seconds,float EntryAlpha,const FString& Phase)
{
    if (!OwnsManualPresentation(Owner) || Dead || Ragdoll || !Clip || !FMath::IsFinite(Seconds)
        || Seconds<0. || Seconds>Clip->GetPlayLength()+.00001 || !FMath::IsFinite(EntryAlpha)
        || Clip->GetSkeleton()!=Body->GetSkeletalMeshAsset()->GetSkeleton()) return false;
    auto* Instance=Cast<UOldWestManualAnimInstance>(Body->GetAnimInstance());
    if (!Instance) return false;
    Body->SetRelativeTransform(ManualBodyRelative);
    if (Instance->GetAnimationAsset()!=Clip) Instance->SetAnimationAsset(Clip,false,0.f);
    Instance->EntryLocalPose=ManualEntryPose; Instance->EntryAlpha=FMath::Clamp(EntryAlpha,0.f,1.f);
    Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
    Instance->SetPlaying(false); Instance->SetPlayRate(0.f); Instance->SetPosition(Seconds,false);
    Body->TickAnimation(0.f,false); Body->RefreshBoneTransforms();
    ActiveClip=Clip->GetName(); ManualPhase=Phase; WeaponContactsValid=false;
    ManualSampleFrame=GFrameCounter; ManualSampleSeconds=Seconds; ManualEntryAlpha=EntryAlpha;
    return true;
}

bool AOldWestUnit::SetManualPresentationRifle(UObject* Owner,const FTransform& BodyRelative,bool Held)
{
    if (!OwnsManualPresentation(Owner) || Dead || Ragdoll || BodyRelative.ContainsNaN()) return false;
    Weapon->SetWorldTransform(BodyRelative*Body->GetComponentTransform());
    ManualRifleHeld=Held; WeaponContactsValid=false; return true;
}
FVector AOldWestUnit::ManualPresentationPalm(const UObject* Owner,bool Right) const
{
    return OwnsManualPresentation(Owner) ? PalmContact(Right?TEXT("Right"):TEXT("Left")) : FVector::ZeroVector;
}

void AOldWestUnit::EndManualPresentation(UObject* Owner,bool ResumeLivingIdle,bool Completed)
{
    if (!OwnsManualPresentation(Owner)) return;
    ManualPoseOwner.Reset(); ManualInterrupted.Unbind(); ManualRifleHeld=false; ManualPhase.Reset();
    ManualLastReleaseReason=Completed?TEXT("completed"):ResumeLivingIdle?TEXT("cancel_restore"):TEXT("release_restore_prior_policy");
    // A physics handoff may already own these flags. Never undo its pause,
    // physics tick/LOD or skeletal instance after the actor became a ragdoll.
    if (!Ragdoll)
    {
        Body->SetComponentTickEnabled(ManualBodyTick); Body->bPauseAnims=ManualBodyPause; Body->SetForcedLOD(ManualBodyLOD);
        // Restoring the captured ordinary policy is mandatory for a living
        // same-identity actor, even Cancel(false) during a baseline/failure.
        // The caller may immediately supersede it with hit/travel/another clip.
        if (!Dead)
        {
            if (ManualWeaponParent.IsValid()) Weapon->AttachToComponent(ManualWeaponParent.Get(),FAttachmentTransformRules::KeepRelativeTransform,ManualWeaponSocket);
            else Weapon->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
            Weapon->SetRelativeTransform(ManualWeaponRelative); Weapon->SetVisibility(ManualWeaponVisible);
            Weapon->SetHiddenInGame(ManualWeaponHidden); Body->SetRelativeTransform(ManualBodyRelative);
            if (Completed && ResumeLivingIdle && !Travelling)
            {
                PlayIdle();
                // Unholster ends at actual native rifle-idle time0.
                if (UAnimSingleNodeInstance* Instance=Body->GetSingleNodeInstance()) Instance->SetPosition(0.f,false);
            }
            else
            {
                Body->PlayAnimation(ManualPreviousAsset,ManualPreviousLooping); ActiveClip=ManualPreviousActiveClip;
                if (UAnimSingleNodeInstance* Instance=Body->GetSingleNodeInstance())
                {
                    Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
                    Instance->SetPosition(ManualPreviousTime,false); Instance->SetPlayRate(ManualPreviousRate);
                    Instance->SetPlaying(ManualPreviousPlaying);
                }
            }
            Body->TickAnimation(0.f,false); Body->RefreshBoneTransforms();
            RootFrame=Body->GetSocketTransform(TEXT("root"),RTS_Component);
            AlignWeaponToHands();
        }
        else
        {
            // Preserve the exact displayed pose, including a partial entry
            // blend, until the ordinary death clip or physics owns this body.
            // This dead-only frozen instance never resumes idle or drives time.
            if (UAnimSingleNodeInstance* Instance=Body->GetSingleNodeInstance())
            {
                Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
                Instance->SetPlaying(false); Instance->SetPlayRate(0.f);
            }
            Body->TickAnimation(0.f,false); Body->RefreshBoneTransforms();
            Weapon->SetVisibility(false);
        }
    }
    ManualPreviousAsset=nullptr; ManualEntryPose.Reset();
}

void AOldWestUnit::InterruptManualPresentation(const FString& Reason)
{
    if (!HasManualPresentation()) return;
    UObject* Owner=ManualPoseOwner.Get(); const FOldWestManualInterrupted Callback=ManualInterrupted;
    EndManualPresentation(Owner,false,false);
    ManualLastReleaseReason=Reason;
    Callback.ExecuteIfBound(Reason);
}

FString AOldWestUnit::GetManualPresentationDebug() const
{
#if !UE_BUILD_SHIPPING
    auto Vector=[](const FVector& V){return J::array({V.X,V.Y,V.Z});};
    auto Transform=[&Vector](const FTransform& T){const FQuat Q=T.GetRotation(); return J{
        {"position",Vector(T.GetLocation())},{"quaternion_xyzw",{Q.X,Q.Y,Q.Z,Q.W}},{"scale",Vector(T.GetScale3D())}};};
    const UAnimSingleNodeInstance* Instance=Body->GetSingleNodeInstance();
    const USceneComponent* Parent=Weapon->GetAttachParent();
    J Out={{"owned",HasManualPresentation()},{"phase",std::string(TCHAR_TO_UTF8(*ManualPhase))},
        {"rifle_held",ManualRifleHeld},{"sample_frame",ManualSampleFrame==MAX_uint64?J(nullptr):J(ManualSampleFrame)},
        {"sample_seconds",ManualSampleSeconds},{"entry_alpha",ManualEntryAlpha},
        {"body_bone_frame",Body->GetCurrentBoneTransformFrame()},{"body_bone_revision",Body->GetBoneTransformRevisionNumber()},
        {"body_tick_enabled",Body->IsComponentTickEnabled()},{"body_paused",static_cast<bool>(Body->bPauseAnims)},
        {"body_forced_lod",Body->GetForcedLOD()},{"animation_mode",static_cast<int32>(Body->GetAnimationMode())},
        {"animation_instance",Body->GetAnimInstance()?std::string(TCHAR_TO_UTF8(*Body->GetAnimInstance()->GetClass()->GetName())):std::string()},
        {"animation_asset",Instance&&Instance->GetAnimationAsset()?std::string(TCHAR_TO_UTF8(*Instance->GetAnimationAsset()->GetPathName())):std::string()},
        {"animation_playing",Instance?Instance->IsPlaying():false},{"animation_rate",Instance?Instance->GetPlayRate():0.f},
        {"body",Transform(Body->GetComponentTransform())},{"body_relative",Transform(Body->GetRelativeTransform())},
        {"weapon",Transform(Weapon->GetComponentTransform())},{"weapon_relative",Transform(Weapon->GetRelativeTransform())},
        {"weapon_parent",Parent?std::string(TCHAR_TO_UTF8(*Parent->GetPathName())):std::string()},
        {"weapon_socket",std::string(TCHAR_TO_UTF8(*Weapon->GetAttachSocketName().ToString()))},
        {"weapon_visible",Weapon->IsVisible()},{"weapon_hidden",static_cast<bool>(Weapon->bHiddenInGame)},
        {"last_release_reason",std::string(TCHAR_TO_UTF8(*ManualLastReleaseReason))},
        {"dead",Dead},{"ragdoll",Ragdoll}};
    if (HasManualPresentation())
    {
        const FVector RightPalm=PalmContact(TEXT("Right")),LeftPalm=PalmContact(TEXT("Left"));
        const FVector RightGrip=Weapon->GetComponentTransform().TransformPosition(FVector(-1.8f,-1.f,-.7f));
        Out["right_palm_world"]=Vector(RightPalm); Out["left_palm_world"]=Vector(LeftPalm);
        Out["right_grip_world"]=Vector(RightGrip); Out["right_grip_local"]={-1.8f,-1.f,-.7f};
        Out["right_contact_gap_cm"]=FVector::Distance(RightPalm,RightGrip);
        Out["right_contact_required"]=ManualRifleHeld;
        Out["bones"]=J::object();
        for (FName Bone:{FName(TEXT("root")),FName(TEXT("Hips")),FName(TEXT("Head")),
            FName(TEXT("LeftHand")),FName(TEXT("RightHand")),FName(TEXT("LeftFoot")),FName(TEXT("RightFoot")),
            FName(TEXT("LeftHandIndex1")),FName(TEXT("LeftHandPinky1")),FName(TEXT("RightHandIndex1")),FName(TEXT("RightHandPinky1"))})
            Out["bones"][std::string(TCHAR_TO_UTF8(*Bone.ToString()))]={{"world",Transform(Body->GetSocketTransform(Bone,RTS_World))},
                {"body_relative",Transform(Body->GetSocketTransform(Bone,RTS_Component))}};
        // Observation only: exact source sole vertices transformed by the
        // current evaluated Foot bones; no teleport, IK, animation or physics write.
        J GroundProbe={{"read_only",true},{"query_frame",GFrameCounter},
            {"sample_frame",ManualSampleFrame},{"bone_frame",Body->GetCurrentBoneTransformFrame()},
            {"source_landmarks_sha256","aa3696f5967fba8e9f767e13ca0ee87de995053b422a72283b57494e9827bdde"},{"points",J::array()}};
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
        Out["saved_policy"]={{"asset",ManualPreviousAsset?std::string(TCHAR_TO_UTF8(*ManualPreviousAsset->GetPathName())):std::string()},
            {"time",ManualPreviousTime},{"playing",ManualPreviousPlaying},{"looping",ManualPreviousLooping},{"rate",ManualPreviousRate},
            {"body_tick",ManualBodyTick},{"body_pause",ManualBodyPause},{"body_lod",ManualBodyLOD},
            {"weapon_relative",Transform(ManualWeaponRelative)},{"weapon_visible",ManualWeaponVisible},{"weapon_hidden",ManualWeaponHidden}};
    }
    return Text(Out.dump());
#else
    return TEXT("{}");
#endif
}

AOldWestBattlefield::AOldWestBattlefield()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    Presentation = MakeShared<FOldWestPresentation>();
}
AOldWestBattlefield::~AOldWestBattlefield() = default;

void AOldWestBattlefield::Initialize(AOldWestPlayerController* Player)
{
    Controller = Player;
    UOldWestDeliveryVisuals::Preload(DeliveryAssets);
    // Retain and warm the public supply token before its first bonus action.
    BonusWhiskeyMesh = LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Art/ActionProps/Meshes/SM_Action_BonusWhiskeyGlass.SM_Action_BonusWhiskeyGlass"));
    if (BonusWhiskeyMesh) for (const FStaticMaterial& Slot : BonusWhiskeyMesh->GetStaticMaterials())
        if (Slot.MaterialInterface) Slot.MaterialInterface->CacheShaders();
    // One public generic cloth, independent of every concealed card identity.
    RevealBandanaMesh = LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Art/Western/Reveal/SM_Reveal_Bandana.SM_Reveal_Bandana"));
    if (RevealBandanaMesh) for (const FStaticMaterial& Slot : RevealBandanaMesh->GetStaticMaterials())
        if (Slot.MaterialInterface) Slot.MaterialInterface->EnsureIsComplete();
    // The original depot study occupies the new rear staging area. Its baked
    // scenery is replaced here by the playable camps and physical hand.
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        const UStaticMesh* Mesh=It->GetStaticMeshComponent()->GetStaticMesh();
        if(Mesh&&(Mesh->GetName()==TEXT("SM_Depot")||Mesh->GetName()==TEXT("SM_Props")))
        {It->SetActorHiddenInGame(true);It->SetActorEnableCollision(false);}
    }
#if !UE_BUILD_SHIPPING
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) && !CompletedActorTickHandle.IsValid())
        CompletedActorTickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(
            this, &AOldWestBattlefield::ObserveCompletedActorTick);
#endif
    for (TActorIterator<ALevelSequenceActor> It(GetWorld()); It; ++It)
        if (ULevelSequencePlayer* Sequence = It->GetSequencePlayer()) Sequence->Stop();
    Camera = GetWorld()->SpawnActor<ACineCameraActor>();
    if (Camera)
    {
        Camera->GetCineCameraComponent()->SetCurrentFocalLength(32.f);
        Camera->GetCineCameraComponent()->SetCurrentAperture(8.f);
        FCameraFilmbackSettings Filmback;
        Filmback.SensorWidth = 36.f;
        Filmback.SensorHeight = 20.25f;
        Camera->GetCineCameraComponent()->SetFilmback(Filmback);
        FCameraFocusSettings Focus;
        Focus.FocusMethod = ECameraFocusMethod::Disable;
        Camera->GetCineCameraComponent()->FocusSettings = Focus;
        ResetCamera();
        CameraFocus = DesiredFocus;
        Camera->SetActorLocation(DesiredCamera);
        Camera->SetActorRotation((DesiredFocus - DesiredCamera).Rotation());
        Player->SetViewTarget(Camera);
    }
    if (USoundBase* Sound = OldWestSound(TEXT("SW_Ambience_WindIndustrial")))
        Ambience = UGameplayStatics::SpawnSound2D(this, Sound, 0.65f);
}

#if !UE_BUILD_SHIPPING
void AOldWestBattlefield::ObserveCompletedActorTick(UWorld* World, ELevelTick TickType, float /*DeltaSeconds*/)
{
    // The engine broadcasts after PostUpdateWork, LastDemotable and EndFrame;
    // Body animation completion is chained to its tick completion task. This
    // reads completed transforms without forcing evaluation or another fit.
    if (World != GetWorld() || TickType == LEVELTICK_ViewportsOnly || !Presentation.IsValid()) return;
    const auto& P = *Presentation;
    const int32 Sequence = P.Active.IsSet() ? P.Active->Sequence : INDEX_NONE;
    const FString Kind = P.Active.IsSet() ? P.Active->Kind : FString();
    for (const auto& Pair : Units) if (IsValid(Pair.Value))
        Pair.Value->SampleCompletedWeaponObservation(P.MatchId, Sequence, Kind, P.Elapsed, IsCinematicBusy());
}
#endif

void AOldWestBattlefield::EndPlay(const EEndPlayReason::Type Reason)
{
#if !UE_BUILD_SHIPPING
    FWorldDelegates::OnWorldPostActorTick.Remove(CompletedActorTickHandle);
    CompletedActorTickHandle.Reset();
#endif
    ClearActionEffects();
    if (Presentation) { CancelScientistScenes(TEXT("end_play"), 0, false); Presentation->Analysis.Reset("end_play", true); }
    if (Ambience) Ambience->Stop();
    for (auto& Pair : Units) if (IsValid(Pair.Value)) Pair.Value->Destroy();
    Units.Empty();
    if (IsValid(Camera)) Camera->Destroy();
    Super::EndPlay(Reason);
}

void AOldWestBattlefield::SetOverview()
{
    // Tactical state is independent of the current shot, so synchronizing a
    // move or returning from a cinematic cannot erase the player's camera.
    DesiredFocus = TacticalFocus;
    const float Yaw = FMath::DegreesToRadians(TacticalYaw);
    const float Pitch = FMath::DegreesToRadians(TacticalPitch);
    DesiredCamera = DesiredFocus + FVector(FMath::Cos(Yaw) * FMath::Cos(Pitch),
        FMath::Sin(Yaw) * FMath::Cos(Pitch), FMath::Sin(Pitch)) * TacticalDistance;
    // Automatic framing avoids scenery; manual navigation permits floor-level inspection.
    if (!CameraCustomized)
    {
        // Keep low inspection angles above uneven terrain and solid camp pieces.
        FHitResult Ground;
        if (GetWorld()->LineTraceSingleByChannel(Ground, DesiredCamera + FVector(0, 0, 1200),
            DesiredCamera - FVector(0, 0, 3000), ECC_Visibility))
            DesiredCamera.Z = FMath::Max(DesiredCamera.Z, Ground.ImpactPoint.Z + 140.f);
        FCollisionQueryParams CameraParams(SCENE_QUERY_STAT(OldWestTacticalCamera), true);
        for (int32 Attempt = 0; Attempt < 8 && GetWorld()->OverlapBlockingTestByChannel(
            DesiredCamera, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(45.f), CameraParams); ++Attempt)
            DesiredCamera.Z += 100.f;
    }
    UpdateShotFocus();
}

bool AOldWestBattlefield::HasAnalysisChoiceView() const
{
    if (!Presentation || IsCinematicBusy() || ChoiceViewSequence <= 0) return false;
    const UOldWestScientistPlayback* Playback = Presentation->ScientistPlayback.FindRef(ChoiceViewSequence).Get();
    return IsValid(Playback) && Playback->IsAwaitingChoice();
}

bool AOldWestBattlefield::IsAnalysisChoiceFramed() const
{
    return ChoiceViewFramed && HasAnalysisChoiceView();
}

bool AOldWestBattlefield::RetainAnalysisChoiceView()
{
    auto& P = *Presentation;
    int32 Key = 0, Source = 0;
    for (const auto& Pair : P.ScientistPlayback)
    {
        const UOldWestScientistPlayback* Playback = Pair.Value.Get();
        if (!IsValid(Playback) || !Playback->IsAwaitingChoice()) continue;
        const J Context = P.Analysis.Get(Pair.Key);
        if (Context.is_null() || Context.value("accepted", false) ||
            !Context.value("boundary_reason", std::string()).empty()) continue;
        if (Pair.Key > Key) { Key = Pair.Key; Source = Context.value("source", 0); }
    }
    if (Key == 0)
    {
        ChoiceViewSequence = ChoiceViewSource = DismissedChoiceViewSequence = 0;
        ChoiceViewFramed = false;
        return false;
    }
    if (ChoiceViewSequence != Key)
    {
        // The final Inspect camera has already passed the actual workspace,
        // lid and performer visibility tests. Retain it across the response.
        ChoiceViewSequence = Key; ChoiceViewSource = Source;
        ChoiceViewPosition = DesiredCamera; ChoiceViewFocus = DesiredFocus;
        DismissedChoiceViewSequence = 0;
    }
    ChoiceViewFramed = !BirdOverview && DismissedChoiceViewSequence != Key;
    return IsAnalysisChoiceFramed();
}

void AOldWestBattlefield::SetAnalysisChoiceFramed(bool Framed)
{
    if (!HasAnalysisChoiceView()) return;
    if (!Framed)
    {
        DismissedChoiceViewSequence = ChoiceViewSequence;
        ChoiceViewFramed = false;
        SetOverview();
        return;
    }
    if (BirdOverview) return; // HUD closes its overview before refocusing.
    DismissedChoiceViewSequence = 0;
    ChoiceViewFramed = true;
    DesiredFocus = ChoiceViewFocus;
    DesiredCamera = ChooseShotPosition(DesiredFocus, ChoiceViewPosition, INDEX_NONE);
    ChoiceViewPosition = DesiredCamera;
    if (Camera)
    {
        CameraFocus = DesiredFocus;
        Camera->SetActorLocation(DesiredCamera);
        Camera->SetActorRotation((DesiredFocus - DesiredCamera).Rotation());
    }
    // Nonbusy choices retain ordinary f/8 focus policy and exposure. The next
    // actual accepted beat resumes its normal finite cinematic lens policy.
    UpdateShotFocus();
}

void AOldWestBattlefield::UpdateShotFocus()
{
    if (!Camera) return;
    UCineCameraComponent* Lens = Camera->GetCineCameraComponent();
    const auto& P = *Presentation;
    const bool Cinematic = P.Active.IsSet();
    float Aperture = 8.f;
    if (Cinematic && !P.GroupShot)
    {
        const FCinematicBeat& Beat = P.Active.GetValue();
        Aperture = P.EffectFraming ? 5.6f : Beat.Before.Camp || Beat.Before.EventToken ||
            Beat.Kind == TEXT("destroy") ? 4.f : 2.8f;
    }
    Lens->SetCurrentAperture(Aperture);
    Lens->FocusSettings.FocusMethod = Cinematic ? ECameraFocusMethod::Manual : ECameraFocusMethod::Disable;
    // The camera target already follows the current animated pose smoothly.
    // A second focus interpolation would lag at cuts and soften the subject.
    Lens->FocusSettings.bSmoothFocusChanges = false;
    Lens->FocusSettings.ManualFocusDistance = Cinematic ? FMath::Max(1.f,
        static_cast<float>(FVector::DotProduct(CameraFocus - Lens->GetComponentLocation(), Lens->GetForwardVector()))) : 0.f;
    // The map uses physical exposure at f/8, 1/60 s. UE exposure depends on
    // fstop^2 * shutter-speed, so compensate the actual (lens-clamped) aperture
    // while retaining the map's ISO, exposure bias and lighting.
    Lens->PostProcessSettings.bOverride_CameraShutterSpeed = true;
    Lens->PostProcessSettings.CameraShutterSpeed = 60.f * FMath::Square(8.f / Lens->CurrentAperture);
}
void AOldWestBattlefield::ToggleCamera()
{
    AlternateAngle = !AlternateAngle;
    ResetCamera();
}

void AOldWestBattlefield::ResetCamera()
{
    DismissedChoiceViewSequence = ChoiceViewSequence;
    ChoiceViewFramed = false;
    BirdOverview = false;
    const FVector DefaultPosition(AlternateAngle ? 0.f : -400.f,
        2500.f + (Seat == 0 ? 1.f : -1.f) * 6200.f, AlternateAngle ? 4400.f : 3400.f);
    const float ExtraRows = FMath::Max(0, FramingHandRows - 2);
    TacticalFocus = FVector(0, 2500+(Seat==0?1.f:-1.f)*(650.f+160.f*ExtraRows), 140);
    const FVector Offset = DefaultPosition - TacticalFocus;
    TacticalYaw = Offset.Rotation().Yaw;
    TacticalPitch = FMath::Clamp(Offset.Rotation().Pitch, -89.f, 89.f);
    TacticalDistance = Offset.Size()*(1.15f+.20f*ExtraRows);
    CameraCustomized = false;
    DefaultFramingPending = false;
    CameraInitialized = true;
    if (IsCinematicBusy()) SkipCinematics();
    else SetOverview();
}

void AOldWestBattlefield::SetOverviewCamera(bool Enabled)
{
    if (Enabled && IsAnalysisChoiceFramed()) SetAnalysisChoiceFramed(false);
    if (Enabled == BirdOverview) return;
    if (Enabled)
    {
        SavedTacticalFocus = TacticalFocus; SavedTacticalYaw = TacticalYaw;
        SavedTacticalPitch = TacticalPitch; SavedTacticalDistance = TacticalDistance;
        TacticalFocus = FVector(0, 2500, 100);
        TacticalYaw = Seat == 0 ? 90.f : -90.f;
        TacticalPitch = 76.f; TacticalDistance = 4800.f;
    }
    else
    {
        TacticalFocus = SavedTacticalFocus; TacticalYaw = SavedTacticalYaw;
        TacticalPitch = SavedTacticalPitch; TacticalDistance = SavedTacticalDistance;
    }
    BirdOverview = Enabled;
    if (!IsCinematicBusy()) SetOverview();
}

void AOldWestBattlefield::NavigateCamera(float OrbitX, float OrbitY, float PanX, float PanY, float Zoom, float Elevation)
{
    if (!FMath::IsFinite(OrbitX) || !FMath::IsFinite(OrbitY) || !FMath::IsFinite(PanX) ||
        !FMath::IsFinite(PanY) || !FMath::IsFinite(Zoom) || !FMath::IsFinite(Elevation)) return;
    CameraCustomized = true;
    if (IsAnalysisChoiceFramed() && Camera)
    {
        // Begin manual navigation from the inspected view, not from the old
        // distant tactical coordinates. This releases only camera ownership.
        TacticalFocus = CameraFocus;
        const FVector Offset = Camera->GetActorLocation() - TacticalFocus;
        TacticalYaw = Offset.Rotation().Yaw;
        TacticalPitch = FMath::Clamp(Offset.Rotation().Pitch, -89.f, 89.f);
        TacticalDistance = FMath::Clamp(static_cast<float>(Offset.Size()), 120.f, 24000.f);
        DismissedChoiceViewSequence = ChoiceViewSequence;
        ChoiceViewFramed = false;
    }
    // Navigation deliberately returns control to the player immediately.
    // Skip preserves the requested tactical view and reconciles pending hits.
    if (IsCinematicBusy()) SkipCinematics();
    TacticalYaw = FMath::UnwindDegrees(TacticalYaw - FMath::Clamp(OrbitX, -500.f, 500.f) * .22f);
    TacticalPitch = FMath::Clamp(TacticalPitch + FMath::Clamp(OrbitY, -500.f, 500.f) * .18f, -89.f, 89.f);
    TacticalDistance = FMath::Clamp(TacticalDistance * FMath::Pow(.88f, FMath::Clamp(Zoom, -10.f, 10.f)), 120.f, 24000.f);
    const float Yaw = FMath::DegreesToRadians(TacticalYaw);
    const FVector Right(-FMath::Sin(Yaw), FMath::Cos(Yaw), 0);
    const FVector Forward(-FMath::Cos(Yaw), -FMath::Sin(Yaw), 0);
    const float PixelScale = TacticalDistance * .0012f;
    TacticalFocus += (-Right * FMath::Clamp(PanX, -500.f, 500.f) + Forward * FMath::Clamp(PanY, -500.f, 500.f)) * PixelScale;
    TacticalFocus.Z = FMath::Clamp(TacticalFocus.Z + FMath::Clamp(Elevation, -500.f, 500.f) * PixelScale, -10000.f, 24000.f);
    TacticalFocus.X = FMath::Clamp(TacticalFocus.X, -10000.f, 10000.f);
    TacticalFocus.Y = FMath::Clamp(TacticalFocus.Y, -7500.f, 12500.f);
    SetOverview();
}

FVector AOldWestBattlefield::DeploymentPosition(int32 Side, int32 Column, int32 PersonPosition)
{
    return FVector((Column - 1) * 1350.f, 2500.f + (Side == 0 ? 1.f : -1.f) * (500.f + PersonPosition * 480.f), 0.f);
}

FVector AOldWestBattlefield::EventPosition(int32 Side, int32 Slot)
{
    return FVector(Side == 0 ? -2450.f : 2450.f,
        2500.f + (Side == 0 ? 1.f : -1.f) * (400.f + Slot * 560.f), 0.f);
}

FVector AOldWestBattlefield::GroundedDeploymentPosition(int32 Side, int32 Column, int32 PersonPosition) const
{
    FVector Position = DeploymentPosition(Side, Column, PersonPosition);
    FHitResult Ground;
    if (GetWorld()->LineTraceSingleByChannel(Ground, Position + FVector(0, 0, 500), Position - FVector(0, 0, 600), ECC_Visibility))
        Position.Z = Ground.ImpactPoint.Z;
    return Position;
}
bool AOldWestBattlefield::IsCinematicBusy() const
{
    return Presentation->Active.IsSet() || !Presentation->Pending.IsEmpty();
}

int32 AOldWestBattlefield::GetCinematicSequence() const
{
    return Presentation.IsValid() && Presentation->Active.IsSet() ? Presentation->Active->Sequence : INDEX_NONE;
}

void AOldWestBattlefield::SkipCinematics()
{
    auto& P = *Presentation;
    ClearActionEffects();
    CancelScientistScenes(TEXT("cinematic_skip"), 0, true);
    P.Analysis.Reset("cinematic_skip");
    RecordShotCompletion(TEXT("skipped"));
    P.SkippedBeats += P.Pending.Num() + P.Simultaneous.Num() + (P.Active.IsSet() ? 1 : 0);
    P.Active.Reset();
    P.Pending.Empty();
    P.Simultaneous.Empty();
    P.DeferredEntrances.Empty();
    P.Elapsed = 0.f;
    P.FrameCount = 0;
    P.LastFrameSeconds = P.MaxFrameSeconds = P.EstimatedPhysicsSeconds = 0.f;
#if !UE_BUILD_SHIPPING
    P.ResetPerformanceFrames();
#endif
    P.StartedAt = 0.;
    P.ImpactResolved = false;
    P.WaitForPersonSettling = P.AllRagdollsSettled = false;
    P.SettleStableSeconds = 0.f;
    P.FocusRevision = -1;
    for (auto& Pair : Units) if (IsValid(Pair.Value))
    {
        Pair.Value->ResetPose();
        // A skipped approach must end with the same battlefield facing as a
        // completed walk, rather than retaining its intermediate travel yaw.
        Pair.Value->AimAt(Pair.Value->GetActorLocation() + FVector(0, Pair.Value->Side == 0 ? -100.f : 100.f, 0));
        Pair.Value->Caption->SetVisibility(false);
    }
    ReconcileUnits();
    SetOverview();
    if (Camera)
    {
        CameraFocus = DesiredFocus;
        Camera->SetActorLocation(DesiredCamera);
        Camera->SetActorRotation((DesiredFocus - DesiredCamera).Rotation());
    }
}

void AOldWestBattlefield::ReconcileUnits()
{
    auto& P = *Presentation;
    TSet<int32> Held;
    TSet<int32> Staged;
    auto Stage = [&Staged](const FCinematicBeat& Beat) { Staged.Add(Beat.Source); Staged.Add(Beat.Target); };
    if (P.Active.IsSet()) Stage(P.Active.GetValue());
    for (const auto& Beat : P.Simultaneous) Stage(Beat);
    const FCinematicBeat* LayoutBeat = P.Active.IsSet() ? &P.Active.GetValue() : P.Pending.IsEmpty() ? nullptr : &P.Pending[0];
    TSet<FIntPoint> DepartingColumns;
    auto ReserveDeparture = [LayoutBeat, &DepartingColumns](const FCinematicBeat& Beat)
    {
        if (LayoutBeat && Beat.Revision == LayoutBeat->Revision && Beat.KnownTarget &&
            !Beat.Before.Camp && !Beat.Before.EventToken &&
            (Beat.Kind == TEXT("destroy") || Beat.Kind == TEXT("return")))
            DepartingColumns.Add(FIntPoint(Beat.Before.Side, FMath::RoundToInt(Beat.Before.Location.X)));
    };
    if (P.Active.IsSet()) ReserveDeparture(P.Active.GetValue());
    for (const auto& Beat : P.Simultaneous) ReserveDeparture(Beat);
    for (const auto& Beat : P.Pending) ReserveDeparture(Beat);
    // Explicit moves in this revision retain their recorded origin until their
    // own travel starts. Only implicit lane shifts happen at the shot cut.
    if (LayoutBeat)
        for (const auto& Beat : P.Pending)
            if (Beat.Revision == LayoutBeat->Revision && (Beat.Kind == TEXT("move") ||
                Beat.Kind == TEXT("recruit_id") || Beat.Kind == TEXT("hospital_id"))) Staged.Add(Beat.Target);
    auto ReconcileDeployment = [LayoutBeat, &Staged, &DepartingColumns](AOldWestUnit* Unit, int32 Id)
    {
        if (!LayoutBeat || !LayoutBeat->DeploymentLayout.IsValid() || Staged.Contains(Id)
            || Unit->Camp || Unit->IsEventToken() || Unit->IsVisuallyDead()) return;
        if (const FVector* Location = LayoutBeat->DeploymentLayout->Find(Id))
        {
            // The snapshot already compacts a lane after a removal. Keep that
            // lane's previous spacing while its death/return is still queued
            // or active; otherwise a survivor occupies the departing body.
            if (LayoutBeat->DeploymentBeforeLayout.IsValid() &&
                DepartingColumns.Contains(FIntPoint(Unit->Side, FMath::RoundToInt(Location->X))))
                if (const FVector* Before = LayoutBeat->DeploymentBeforeLayout->Find(Id)) Location = Before;
            Unit->SetActorLocation(*Location);
        }
    };
    auto Hold = [&Held](const FCinematicBeat& Beat)
    {
        if (!Beat.ResourceOnly) Held.Add(Beat.Source);
        Held.Add(Beat.Target);
    };
    for (const auto& Pair : P.WaitingStampedes) Held.Add(Pair.Key);
    if (P.Active.IsSet()) Hold(P.Active.GetValue());
    for (const auto& Beat : P.Pending) Hold(Beat);
    for (const auto& Beat : P.Simultaneous) Hold(Beat);
    // A nonbusy response wait still owns its planted body, rifle and workspace.
    for (const auto& Pair : P.ScientistPlayback)
    {
        const J Context = P.Analysis.Get(Pair.Key);
        const int32 Source = Context.is_null() ? 0 : Context.value("source", 0);
        if (P.Latest.Contains(Source)) { Held.Add(Source); Staged.Add(Source); }
    }
    for (const auto& Pair : P.Latest)
    {
        const FUnitPresentationFrame& Frame = Pair.Value;
        AOldWestUnit* Unit = Units.FindRef(Pair.Key);
        if (IsValid(Unit) && Held.Contains(Pair.Key))
        {
            if (P.DeferredEntrances.Contains(Pair.Key)) Unit->SetActorHiddenInGame(true);
            continue;
        }
        if (!IsValid(Unit))
        {
            Unit = GetWorld()->SpawnActor<AOldWestUnit>();
            if (!Unit) continue;
            Units.Add(Pair.Key, Unit);
            if (Frame.EventToken) Unit->ConfigureEvent(Frame.Id, Frame.Side, Frame.Name, Frame.CardId);
            else Unit->Configure(Frame.Id, Frame.Side, Frame.Name, Frame.Camp, Frame.Punk, Frame.CardId, false, Frame.VisualId);
        }
        else if (Unit->Side != Frame.Side || Unit->GetUnitName() != Frame.Name || Unit->Camp != Frame.Camp)
        {
            if (Frame.EventToken) Unit->ConfigureEvent(Frame.Id, Frame.Side, Frame.Name, Frame.CardId);
            else Unit->Configure(Frame.Id, Frame.Side, Frame.Name, Frame.Camp, Frame.Punk, Frame.CardId, false, Frame.VisualId);
        }
        // While playback is queued, an unrelated network update must not move
        // a person to its future lane slot. Their active beat owns animation.
        if (!LayoutBeat || Unit->Camp || Unit->IsEventToken()) Unit->SetActorLocation(Frame.Location);
        Unit->SetCondition(Frame.Damage, Frame.Destroyed, Frame.Ready);
        if (P.DeferredEntrances.Contains(Pair.Key)) Unit->SetActorHiddenInGame(true);
    }
    // Historical participants can already have left the newest snapshot.
    // They still occupy the recorded layout until their queued exit/death.
    for (const auto& Pair : Units) if (IsValid(Pair.Value)) ReconcileDeployment(Pair.Value, Pair.Key);
    TArray<int32> Remove;
    for (const auto& Pair : Units)
        if (!P.Latest.Contains(Pair.Key) && !Held.Contains(Pair.Key))
        {
            CancelScientistScenes(TEXT("source_removed"), Pair.Key, false);
            // A final-response actor is temporary, but its public three-card
            // choice can outlive its shot. The existing turn/Skip/baseline
            // boundaries still retire that metadata.
            if (!P.DepartedPublicPeople.Contains(Pair.Key))
                P.Analysis.CancelSource(Pair.Key, "source_removed");
            if (IsValid(Pair.Value)) Pair.Value->Destroy();
            Remove.Add(Pair.Key);
        }
    for (int32 Id : Remove) Units.Remove(Id);
    UpdateCinematicLODs();
}

void AOldWestBattlefield::UpdateCinematicLODs()
{
    TSet<int32> Participants;
    auto Add = [&Participants](const FCinematicBeat& Beat) { Participants.Add(Beat.Source); Participants.Add(Beat.Target); };
    if (Presentation->Active.IsSet()) Add(Presentation->Active.GetValue());
    for (const auto& Beat : Presentation->Simultaneous) Add(Beat);
    for (const auto& Pair : Presentation->ScientistPlayback)
    {
        const J Context = Presentation->Analysis.Get(Pair.Key);
        if (!Context.is_null()) Participants.Add(Context.value("source", 0));
    }
    for (auto& Pair : Units) if (IsValid(Pair.Value) && !Pair.Value->Camp && !Pair.Value->IsEventToken())
    {
        USkeletalMeshComponent* Mesh = Pair.Value->Body;
        const int32 Forced = Participants.Contains(Pair.Key) ? 1 : 0;
        // UE's setter is one-based: 1 requests full LOD0, 0 resumes automatic
        // distance selection. Restrict the request to this shot's participants.
        if (Mesh->GetForcedLOD() != Forced) Mesh->SetForcedLOD(Forced);
    }
}

void AOldWestBattlefield::ApplySnapshot(const FString& Payload)
{
    J Data;
    try { Data = J::parse(TCHAR_TO_UTF8(*Payload)); } catch (const std::exception&) { return; }
    if (!Data.contains("view")) return;
    const J& View = Data["view"];
    auto& P = *Presentation;
    const int32 NewSeat = Data.value("seat", 0);
    const int32 Revision = View.value("revision", 0);
    const int32 Turn = View.value("turn", 0);
    const FString MatchId = Text(Data.value("match_id", std::string()));
    const bool Baseline = P.LastRevision < 0 || P.MatchId != MatchId || NewSeat != Seat || Revision < P.LastRevision || Turn < P.LastTurn;
    const bool SeatChanged = NewSeat != Seat;
    Seat = NewSeat;
    int32 HandPeople = 0, HandEvents = 0;
    for (const auto& Card : View["players"][Seat]["hand"])
        if (Card.value("type", std::string()) == "person") ++HandPeople; else ++HandEvents;
    const int32 HandRows = FMath::Max(1, (FMath::Max(HandPeople, HandEvents)+4)/5);
    if (HandRows != FramingHandRows) { FramingHandRows = HandRows; DefaultFramingPending = true; }
    if (!CameraInitialized || SeatChanged) ResetCamera();
    TMap<int32, FUnitPresentationFrame> Next;
    for (int32 Player = 0; Player < 2; ++Player) for (int32 ColumnId = 0; ColumnId < 3; ++ColumnId)
    {
        const J& Column = View["players"][Player]["columns"][ColumnId];
        int32 CampIndex = -1, CampRow = 2;
        for (int32 I = 0; I < static_cast<int32>(Column.size()); ++I)
            if (Column[I].value("type", std::string()) == "camp")
            { CampIndex = I; CampRow = 2 - Column[I].value("advance", 0); }
        for (int32 Position = 0; Position < static_cast<int32>(Column.size()); ++Position)
        {
            const J& Card = Column[Position];
            FUnitPresentationFrame Frame;
            Frame.Id = Card["id"];
            Frame.Side = Player;
            Frame.Name = Text(Card.value("name", std::string("Punk")));
            Frame.CardId = Text(Card.value("card_id", std::string()));
            Frame.VisualId = Text(Card.value("visual_id", Card.value("card_id",std::string())));
            Frame.Camp = Card.value("type", std::string()) == "camp";
            Frame.Punk = Card.value("punk", false);
            Frame.Damage = Card.value("damage", 0);
            Frame.Destroyed = Card.value("destroyed", false);
            Frame.Ready = Card.value("ready", false);
            const int32 Row = CampIndex < 0 ? 3 - static_cast<int32>(Column.size()) + Position : CampRow + Position - CampIndex;
            Frame.Location = GroundedDeploymentPosition(Player, ColumnId, Row);
            Next.Add(Frame.Id, Frame);
        }
    }
    // Public events occupy their own approach line. The Stampede shares the
    // existing Raider identity; equipment remains at its real queue slot.
    // Hidden hand contents never create world actors.
    for (int32 Player = 0; Player < 2; ++Player)
    {
        const J& Queue = View["players"][Player]["queue"];
        for (int32 Slot = 0; Slot < static_cast<int32>(Queue.size()); ++Slot)
        {
            const J& Card = Queue[Slot];
            if (Card.is_null()) continue;
            FUnitPresentationFrame Frame;
            Frame.Id = Card["id"];
            Frame.Side = Player;
            Frame.CardId = Text(Card.value("card_id", std::string()));
            Frame.VisualId = Text(Card.value("visual_id", Card.value("card_id",std::string())));
            Frame.EventToken = true;
            Frame.Name = Text(Card.value("name", std::string("Event"))) + FString::Printf(TEXT(" · %s"), Slot == 0 ? TEXT("IMMINENT") : Slot == 1 ? TEXT("APPROACHING") : TEXT("ASSEMBLING"));
            Frame.Ready = true;
            Frame.Location = EventPosition(Player, Slot);
            FHitResult Ground;
            if (GetWorld()->LineTraceSingleByChannel(Ground, Frame.Location + FVector(0, 0, 500), Frame.Location - FVector(0, 0, 600), ECC_Visibility))
                Frame.Location.Z = Ground.ImpactPoint.Z;
            Next.Add(Frame.Id, Frame);
        }
    }
    const bool Immediate = Baseline || !Data.value("hosted", false) || Data.value("connected", 0) != 2 ||
        View.value("status", std::string()) == "selection";
    int32 NewestSequence = P.LastSequence;
    for (const auto& Event : View["log"]) NewestSequence = FMath::Max(NewestSequence, Event.value("sequence", 0));
    if (Baseline)
    {
        CancelScientistScenes(TEXT("baseline"), 0, false);
        P.Analysis.Reset("baseline", true);
        P.LastSequence = -1;
        NewestSequence = -1;
        for (const auto& Event : View["log"]) NewestSequence = FMath::Max(NewestSequence, Event.value("sequence", 0));
        for (auto& Pair : Units) if (IsValid(Pair.Value)) Pair.Value->Destroy();
        Units.Empty();
        P.WaitingStampedes.Empty();
    }
    if (Baseline || Turn != P.LastTurn) P.DepartedPublicPeople.Empty();
    TMap<int32, FUnitPresentationFrame> Working = P.Latest;
    auto DeploymentLayout = MakeShared<TMap<int32, FVector>>();
    auto DeploymentBeforeLayout = MakeShared<TMap<int32, FVector>>();
    for (const auto& Pair : Next)
        if (!Pair.Value.Camp && !Pair.Value.EventToken) DeploymentLayout->Add(Pair.Key, Pair.Value.Location);
    for (const auto& Pair : P.Latest)
        if (!Pair.Value.Camp && !Pair.Value.EventToken) DeploymentBeforeLayout->Add(Pair.Key, Pair.Value.Location);
    if (!Immediate)
    {
        int32 ContextSource = 0;
        std::string ContextEvent;
        const J& Log = View["log"];
        for (int32 I = 0; I < static_cast<int32>(Log.size()); ++I)
        {
            const J& Event = Log[I];
            FString Kind = Text(Event.value("type", std::string()));
            if (Kind == TEXT("turn_start") || Kind == TEXT("junk")) { ContextSource = 0; ContextEvent.clear(); }
            if (Kind == TEXT("ability") || Kind == TEXT("event_resolve"))
            {
                ContextSource = Event.value("source", 0);
                ContextEvent = Kind == TEXT("event_resolve") ? Event.value("detail", std::string()) : std::string();
            }
            const int32 Sequence = Event.value("sequence", 0);
            if (Sequence <= P.LastSequence) continue;
            // Rule-log markers are the causal contract. Resource logs intentionally
            // omit private card identities; a sealed supply prop represents draws.
            if (Kind == TEXT("analysis_choice"))
            {
                // Public accepted decision, not a new unknown action/actor.
                // Reconnect or explicit cinematic Skip may have no work context.
                if (P.Analysis.AcceptEvent(Event))
                {
                    const int32 Key = Event.value("analysis_sequence", 0);
                    const J Context = P.Analysis.Get(Key);
                    FCinematicBeat Continuation;
                    Continuation.DeploymentLayout = DeploymentLayout;
                    Continuation.DeploymentBeforeLayout = DeploymentBeforeLayout;
                    Continuation.Kind = TEXT("analysis_choice"); Continuation.Sequence = Sequence;
                    Continuation.Revision = Event.value("revision", Revision); Continuation.Player = Event.value("player", 0);
                    Continuation.Source = Context.value("source", 0); Continuation.Target = Continuation.Source;
                    Continuation.AnalysisSequence = Key; Continuation.AnalysisPresentedThrough = Sequence;
                    const FUnitPresentationFrame* Frame = Working.Find(Continuation.Source);
                    if (!Frame) Frame = Next.Find(Continuation.Source);
                    if (Frame) { Continuation.Before = Continuation.After = *Frame; Continuation.KnownTarget = true; }
                    P.Pending.Add(MoveTemp(Continuation));
                }
                continue;
            }
            if (Kind == TEXT("turn_end")) continue; // The following turn_start stages the handover.
            if (Kind == TEXT("rearrange"))
            {
                for (const auto& Pair : Working)
                    if (const auto* CurrentFrame = Next.Find(Pair.Key); CurrentFrame &&
                        !CurrentFrame->Camp && !CurrentFrame->EventToken && !CurrentFrame->Location.Equals(Pair.Value.Location, 1.f))
                    {
                        FCinematicBeat Move;
                        Move.DeploymentLayout = DeploymentLayout;
                        Move.DeploymentBeforeLayout = DeploymentBeforeLayout;
                        Move.Kind = TEXT("move"); Move.Source = Event.value("source", 0);
                        Move.Target = Pair.Key; Move.Player = CurrentFrame->Side;
                        Move.Sequence = Sequence; Move.Revision = Event.value("revision", Revision);
                        Move.Before = Pair.Value; Move.After = *CurrentFrame; Move.KnownTarget = true;
                        Move.Duration = FMath::Clamp(static_cast<float>(FVector::Distance(Move.Before.Location, Move.After.Location)) / 700.f, 1.1f, 3.2f);
                        P.Pending.Add(Move);
                    }
                for (auto& Pair : Working) if (const auto* CurrentFrame = Next.Find(Pair.Key)) Pair.Value = *CurrentFrame;
                continue;
            }
            FCinematicBeat Beat;
            Beat.DeploymentLayout = DeploymentLayout;
            Beat.DeploymentBeforeLayout = DeploymentBeforeLayout;
            Beat.Kind = Kind;
            if (Kind == TEXT("event_advance"))
            {
                Beat.QueueFromSlot = Event.value("from_slot", INDEX_NONE);
                Beat.QueueToSlot = Event.value("to_slot", INDEX_NONE);
                Beat.QueueCauseSource = Event.value("cause_source", 0);
                Beat.QueueMoveReason = Text(Event.value("move_reason", std::string()));
                Beat.HasQueueTransition = Beat.QueueFromSlot >= 0 && Beat.QueueFromSlot < 3 &&
                    Beat.QueueToSlot >= 0 && Beat.QueueToSlot < 3 && Beat.QueueFromSlot != Beat.QueueToSlot;
            }
            Beat.Player = FMath::Clamp(Event.value("player", Seat), 0, 1);
            Beat.Detail = Text(Event.value("detail", std::string()));
            if (Kind == TEXT("water") && Beat.Detail.IsNumeric())
                Beat.Count = FMath::Max(0, FCString::Atoi(*Beat.Detail));
            Beat.Source = Event.value("source", 0);
            if (Beat.Source == 0 && (Kind == TEXT("damage") || Kind == TEXT("destroy"))) Beat.Source = ContextSource;
            Beat.Target = Event.value("target", 0);
            if (!Next.Contains(Beat.Source))
                if (const auto* Departed = P.DepartedPublicPeople.Find(Beat.Source))
                {
                    Beat.FinalAction = true;
                    Beat.FinalActionFrame = *Departed;
                }
            if (Kind == TEXT("ability"))
            {
                Beat.AbilityIndex = Event.value("ability_index", INDEX_NONE);
                Beat.CopiedAbilitySource = Beat.Target;
                const FUnitPresentationFrame* Copied = Working.Find(Beat.CopiedAbilitySource);
                if (!Copied) Copied = Next.Find(Beat.CopiedAbilitySource);
                if (!Copied) Copied = P.DepartedPublicPeople.Find(Beat.CopiedAbilitySource);
                if (Copied)
                {
                    Beat.CopiedAbilityFrame = *Copied;
                    Beat.KnownCopiedAbilitySource = true;
                    // Keep this safe even if an owner-view representation later
                    // learns more about its own punk. No hidden face selects a scene.
                    if (Beat.CopiedAbilityFrame.Punk)
                    {
                        Beat.CopiedAbilityFrame.CardId.Reset();
                        Beat.CopiedAbilityFrame.Name = TEXT("Drifter");
                    }
                }
            }
            if (Kind == TEXT("ability"))
            {
                const FUnitPresentationFrame* Performer = Working.Find(Beat.Source);
                if (!Performer) Performer = Next.Find(Beat.Source);
                if (!Performer && Beat.FinalAction) Performer = &Beat.FinalActionFrame;
                const FUnitPresentationFrame* Definition = Beat.CopiedAbilitySource > 0
                    ? (Beat.KnownCopiedAbilitySource ? &Beat.CopiedAbilityFrame : nullptr) : Performer;
                const bool PublicPerson = Performer && !Performer->Camp && !Performer->Punk && !Performer->EventToken;
                const FString PublicId = Definition && !Definition->Punk ? Definition->CardId : FString();
                if (P.Analysis.Begin(Sequence, Beat.Source, Beat.Player, Beat.AbilityIndex,
                    std::string(TCHAR_TO_UTF8(*PublicId)), PublicPerson, Beat.CopiedAbilitySource, Event.value("turn", Turn)))
                    Beat.AnalysisSequence = Sequence;
            }
            else if (Kind == TEXT("reveal_discard") && P.Analysis.RevealEvent(Event))
                Beat.AnalysisSequence = Event.value("analysis_sequence", 0);
            if (Beat.AnalysisSequence > 0) Beat.AnalysisPresentedThrough = Sequence;
            if (Kind == TEXT("ability") || Kind == TEXT("event_play") || Kind == TEXT("event_advance") ||
                Kind == TEXT("event_resolve") || Kind == TEXT("camp_advance") || Kind == TEXT("expose_all")) Beat.Target = Beat.Source;
            if (Kind == TEXT("water") && Beat.Target == 0) Beat.Target = Beat.Source;
            Beat.Sequence = Sequence;
            Beat.Revision = Event.value("revision", Revision);
            // A lethal damage effect emits two adjacent rule log records. It is
            // one hit, with the original attacker retained for that single beat.
            if (Kind == TEXT("damage") && I + 1 < static_cast<int32>(Log.size()) &&
                Log[I + 1].value("type", std::string()) == "destroy" &&
                Log[I + 1].value("target", 0) == Beat.Target && Log[I + 1].value("revision", -1) == Beat.Revision)
            {
                Beat.Kind = TEXT("destroy");
                Beat.Sequence = Log[++I].value("sequence", Sequence);
            }
            const FUnitPresentationFrame* Previous = Working.Find(Beat.Target);
            const FUnitPresentationFrame* Current = Next.Find(Beat.Target);
            if (Previous) { Beat.Before = *Previous; Beat.KnownTarget = true; }
            else if (Current) { Beat.Before = *Current; Beat.KnownTarget = true; }
            if (Kind == TEXT("water") && Beat.Detail.IsEmpty() &&
                ((Beat.Before.EventToken && Beat.Before.CardId == TEXT("stampede")) ||
                 Event.value("source_name", std::string()) == "Stampede"))
            {
                // The completed Stampede attributes a bonus, but its herd must
                // not survive the hit or respawn as the resource-shot target.
                Beat.ResourceOnly = true;
                Beat.KnownTarget = false;
                Beat.Target = 0;
                Beat.Before = FUnitPresentationFrame();
            }
            if (Kind == TEXT("ability") && Beat.FinalAction)
            {
                Beat.Before = Beat.FinalActionFrame;
                Beat.KnownTarget = true;
            }
            if (!Beat.KnownTarget)
            {
                // Stage the public action at this side's supply line. This is a
                // camera/effect anchor, never a fabricated hidden-card person.
                Beat.Before.Side = Beat.Player;
                Beat.Before.Location = Kind==TEXT("event_resolve")?EventPosition(Beat.Player,-1):
                    EventPosition(Beat.Player, 2) + FVector(Beat.Player == 0 ? 230.f : -230.f, 220.f, 0);
                if(Kind==TEXT("event_resolve"))Beat.Before.Name=Text(Event.value("source_name",std::string(TCHAR_TO_UTF8(*Beat.Detail))));
                FHitResult Ground;
                if (GetWorld()->LineTraceSingleByChannel(Ground, Beat.Before.Location + FVector(0, 0, 500),
                    Beat.Before.Location - FVector(0, 0, 600), ECC_Visibility)) Beat.Before.Location.Z = Ground.ImpactPoint.Z;
                if (Kind == TEXT("event_resolve"))
                {
                    // The public resolution log reveals an instant event even
                    // when it never occupied a queue slot. Resolve its canonical
                    // name before display translation; never inspect either hand.
                    const std::string PublicName = Event.value("detail", std::string());
                    const FString PublicId = FString(UTF8_TO_TCHAR(PublicName.c_str())).ToLower().Replace(TEXT(" "), TEXT("_"));
                    if (const auto* Trouble = OldWestTrouble::ForCard(TCHAR_TO_UTF8(*PublicId)))
                    {
                        Beat.Before.Id = Beat.Source;
                        Beat.Before.CardId = UTF8_TO_TCHAR(Trouble->CardId);
                        Beat.Before.EventToken = true; Beat.Before.Ready = true;
                        Beat.KnownTarget = true;
                    }
                }
            }
            if (Kind == TEXT("event_resolve") && (Beat.Before.CardId == TEXT("stampede") ||
                Event.value("detail", std::string()) == "Stampede"))
            {
                if (!Beat.KnownTarget)
                {
                    Beat.Before.Id = Beat.Source; Beat.Before.Side = Beat.Player;
                    Beat.Before.CardId = TEXT("stampede"); Beat.Before.Name = TEXT("Stampede");
                    Beat.Before.EventToken = true; Beat.Before.Ready = true;
                    Beat.KnownTarget = true;
                }
                P.WaitingStampedes.Add(Beat.Source, Beat.Before);
            }
            Beat.After = Beat.Before;
            // Choice resolution may arrive after the public event prop was
            // removed. Its public log still identifies the cause; never query
            // private hands or infer identity from the departing person.
            Beat.Departure = Beat.Kind == TEXT("destroy") && Beat.KnownTarget &&
                !Beat.Before.Camp && !Beat.Before.EventToken && Beat.Source == ContextSource && ContextEvent == "Run Out of Town";
            if (Beat.Kind == TEXT("destroy") && Beat.KnownTarget && !Beat.Departure &&
                !Beat.Before.Camp && !Beat.Before.EventToken)
            {
                FUnitPresentationFrame Public = Beat.Before;
                if (Public.Punk)
                {
                    Public.CardId.Reset();
                    Public.VisualId = TEXT("punk");
                    Public.Name = TEXT("Drifter");
                }
                P.DepartedPublicPeople.Add(Public.Id, MoveTemp(Public));
            }
            if (Beat.Kind == TEXT("damage")) { Beat.After.Damage = 1; Beat.After.Ready = false; }
            else if (Beat.Kind == TEXT("restore")) { Beat.After.Damage = 0; Beat.After.Destroyed = false; }
            else if (Beat.Kind == TEXT("destroy")) { Beat.After.Damage = 2; Beat.After.Destroyed = true; Beat.After.Ready = false; }
            else if (Current && (Kind == TEXT("enter") || Kind == TEXT("move") || Kind == TEXT("reveal_person") ||
                Kind == TEXT("recruit_id") || Kind == TEXT("hospital_id") || Kind == TEXT("camp_advance") ||
                Kind == TEXT("event_advance") || Kind == TEXT("event_play"))) Beat.After = *Current;
            if (Beat.HasQueueTransition && Beat.KnownTarget)
            {
                // One revision can move the same event more than once. Stage
                // each public transition rather than jumping to final Next.
                auto GroundedSlot = [this, &Beat](int32 Slot)
                {
                    FVector Position = EventPosition(Beat.Player, Slot);
                    FHitResult Ground;
                    if (GetWorld()->LineTraceSingleByChannel(Ground, Position + FVector(0, 0, 500),
                        Position - FVector(0, 0, 600), ECC_Visibility)) Position.Z = Ground.ImpactPoint.Z;
                    return Position;
                };
                Beat.Before.Location = GroundedSlot(Beat.QueueFromSlot);
                Beat.Before.Name = QueueStageName(Beat.Before.Name, Beat.QueueFromSlot);
                Beat.After = Beat.Before;
                Beat.After.Location = GroundedSlot(Beat.QueueToSlot);
                Beat.After.Name = QueueStageName(Beat.After.Name, Beat.QueueToSlot);
            }
            if (Beat.Kind == TEXT("destroy")) Beat.Duration = Beat.Before.Camp ? 1.3f : DiagnosticFallHold() ? 4.f : 1.95f;
            else if (Kind == TEXT("reveal_person")) Beat.Duration = 1.5f;
            else if (Kind == TEXT("enter") || Kind == TEXT("return") || Kind == TEXT("raid_launch")) Beat.Duration = 1.8f;
            else if (Kind == TEXT("move") || Kind == TEXT("recruit_id") || Kind == TEXT("hospital_id"))
                Beat.Duration = FMath::Clamp(static_cast<float>(FVector::Distance(Beat.Before.Location, Beat.After.Location)) / 700.f, 1.1f, 3.2f);
            else if (Kind == TEXT("draw_card") || Kind == TEXT("junk") || Kind == TEXT("discard") || Kind == TEXT("water") ||
                Kind == TEXT("store_water") || Kind == TEXT("reveal_discard") || Kind == TEXT("event_resolve") ||
                Kind == TEXT("event_play") || Kind == TEXT("event_advance") || Kind == TEXT("camp_advance") ||
                Kind == TEXT("turn_start") || Kind == TEXT("ability") || Kind == TEXT("restore") || Kind == TEXT("reshuffle")) Beat.Duration = 1.5f;
            else if (Kind == TEXT("victory") || Kind == TEXT("draw_game")) Beat.Duration = 2.f;
            if ((Kind == TEXT("enter") || Kind == TEXT("raid_launch") || Kind == TEXT("event_play")) && Beat.KnownTarget && !IsValid(Units.FindRef(Beat.Target)) &&
                !P.DeferredEntrances.Contains(Beat.Target))
                P.DeferredEntrances.Add(Beat.Target, Beat.Sequence);
            if ((Beat.Kind == TEXT("damage") || Beat.Kind == TEXT("destroy")) && Beat.Before.Camp)
                if (const auto* Waiting = P.WaitingStampedes.Find(Beat.Source))
                {
                    // This hit is authoritative output after a choice (or an
                    // automatic sole option). Animation never selects a victim.
                    FCinematicBeat Charge;
                    Charge.Kind = TEXT("stampede_charge"); Charge.Sequence = Beat.Sequence;
                    Charge.Revision = Beat.Revision; Charge.Player = Waiting->Side;
                    Charge.Source = Beat.Target; Charge.Target = Beat.Source;
                    Charge.Before = Charge.After = *Waiting; Charge.KnownTarget = true;
                    Charge.After.Location = WalkGround(GetWorld(), Beat.Before.Location +
                        FVector(0,Waiting->Side == 0 ? 360.f : -360.f,0), Units.FindRef(Beat.Target));
                    Charge.Duration = FMath::Clamp(float(FVector::Dist2D(Charge.Before.Location,Charge.After.Location))/650.f,1.2f,4.f);
                    P.Pending.Add(Charge);
                    Working.Add(Charge.Target,Charge.After);
                    P.WaitingStampedes.Remove(Beat.Source);
                }
            if (Beat.KnownTarget) Working.Add(Beat.Target, Beat.After);
            // A multi-card draw/discard is one visible delivery batch, not
            // repeated identical cuts. Preserve the public quantity in staging.
            if (!P.Pending.IsEmpty() && P.Pending.Last().Revision == Beat.Revision && P.Pending.Last().Player == Beat.Player &&
                P.Pending.Last().Kind == Kind && P.Pending.Last().AnalysisSequence == Beat.AnalysisSequence &&
                (Kind == TEXT("draw_card") || Kind == TEXT("discard") || Kind == TEXT("reveal_discard")))
            {
                ++P.Pending.Last().Count;
                P.Pending.Last().AnalysisPresentedThrough = FMath::Max(P.Pending.Last().AnalysisPresentedThrough, Beat.AnalysisPresentedThrough);
            }
            else P.Pending.Add(MoveTemp(Beat));
        }
    }
    const std::string Status = View.value("status", std::string());
    const bool MatchFinished = Status == "won" || Status == "draw";
    if (MatchFinished || View.value("choice", J()).is_null()) P.WaitingStampedes.Empty();
    if (MatchFinished || (!Baseline && Turn != P.LastTurn))
    {
        std::vector<int> QueuedAnalyses;
        auto KeepAnalysis = [&QueuedAnalyses](const FCinematicBeat& B) {
            if (B.AnalysisSequence > 0) QueuedAnalyses.push_back(B.AnalysisSequence);
        };
        if (P.Active.IsSet()) KeepAnalysis(P.Active.GetValue());
        for (const auto& B : P.Pending) KeepAnalysis(B);
        for (const auto& B : P.Simultaneous) KeepAnalysis(B);
        for (const auto& Pair : P.ScientistPlayback) QueuedAnalyses.push_back(Pair.Key);
        P.Analysis.Boundary(MatchFinished ? "match_finished_after_queued_reveals" : "turn_changed_after_queued_reveals",
            Turn, MatchFinished, QueuedAnalyses);
    }
    P.Latest = MoveTemp(Next);
    P.MatchId = MatchId;
    P.LastRevision = Revision;
    P.LastTurn = Turn;
    P.LastSequence = NewestSequence;
    if (Immediate)
    {
        SkipCinematics();
        return;
    }
    for (const auto& Pair : P.ScientistPlayback)
    {
        const J Context = P.Analysis.Get(Pair.Key);
        if (Context.is_null() || Context.value("accepted", false) || Context.value("boundary_reason", std::string()).empty()) continue;
        bool Queued = P.Active.IsSet() && P.Active->AnalysisSequence == Pair.Key;
        for (const auto& B : P.Pending) Queued |= B.AnalysisSequence == Pair.Key;
        if (!Queued)
        {
            FCinematicBeat Close; Close.Kind = TEXT("analysis_close"); Close.Sequence = Pair.Key;
            Close.Revision = Revision; Close.AnalysisSequence = Pair.Key; Close.Source = Close.Target = Context.value("source", 0);
            Close.Player = Context.value("player", 0);
            if (const FUnitPresentationFrame* Frame = P.Latest.Find(Close.Source)) { Close.Before = Close.After = *Frame; Close.KnownTarget = true; }
            P.Pending.Insert(MoveTemp(Close), 0);
        }
    }
    ReconcileUnits();
    if (!P.Active.IsSet() && !P.Pending.IsEmpty())
    {
        P.StartedAt = FPlatformTime::Seconds();
        BeginNextBeat();
    }
    else if (!P.Active.IsSet() && P.Pending.IsEmpty()) P.Analysis.FinishFallbacks();
}

bool AOldWestBattlefield::IsScientistBeat() const
{
    return Presentation.IsValid() && Presentation->Active.IsSet() && Presentation->Active->ScientistScene;
}

void AOldWestBattlefield::CancelScientistScenes(const TCHAR* Reason, int32 Source, bool ResumeLivingIdle)
{
    auto& P = *Presentation;
    TArray<int32> Remove;
    for (const auto& Pair : P.ScientistPlayback)
    {
        const J Context = P.Analysis.Get(Pair.Key);
        if (Source > 0 && (Context.is_null() || Context.value("source", 0) != Source)) continue;
        J Final;
        if (UOldWestScientistPlayback* Playback = Pair.Value.Get(); IsValid(Playback))
        {
            Playback->Cancel(Reason, ResumeLivingIdle);
            Final = J::parse(TCHAR_TO_UTF8(*Playback->GetDebugJson()));
            Playback->DestroyComponent();
        }
        P.Analysis.FinishPresentation(Pair.Key, TCHAR_TO_UTF8(Reason), Final);
        Remove.Add(Pair.Key);
    }
    for (int32 Key : Remove) P.ScientistPlayback.Remove(Key);
    if (Remove.Contains(ChoiceViewSequence))
    {
        ChoiceViewSequence = ChoiceViewSource = DismissedChoiceViewSequence = 0;
        ChoiceViewFramed = false;
        if (!IsCinematicBusy() && Camera) SetOverview();
    }
}

bool AOldWestBattlefield::StartScientistBeat()
{
    auto& P = *Presentation;
    if (!P.Active.IsSet() || P.Active->AnalysisSequence <= 0) return false;
    auto& Beat = P.Active.GetValue();
    const J Context = P.Analysis.Get(Beat.AnalysisSequence);
    if (Context.is_null()) return false;
    if (Beat.Kind == TEXT("analysis_choice") || Beat.Kind == TEXT("analysis_close"))
    {
        UOldWestScientistPlayback* Playback = P.ScientistPlayback.FindRef(Beat.AnalysisSequence).Get();
        if (!IsValid(Playback) || !Playback->IsAwaitingChoice() || (Beat.Kind == TEXT("analysis_choice") && !Context.value("accepted", false))) return false;
        const bool Accepted = Beat.Kind == TEXT("analysis_close")
            ? Playback->FinishWithoutDecision(P.MatchId, Beat.AnalysisSequence, Text(Context.value("boundary_reason", std::string())))
            : Playback->SetDecision(P.MatchId, Beat.AnalysisSequence, Context.value("reveal_index", -1), Context.value("target", 0));
        if (!Accepted)
        {
            UE_LOG(LogTemp, Error, TEXT("OLDWEST_SCIENTIST_PRESENTATION_ERROR Rejected matched public decision %d"), Beat.Sequence);
            CancelScientistScenes(TEXT("decision_playback_rejected"), Beat.Source, true);
            return false;
        }
        Beat.ScientistScene = true;
        // Completion follows the single owned animation/prop clock below.
        Beat.Duration = 12.f;
        return true;
    }
    if (Beat.Kind != TEXT("ability")) return false;
    AOldWestUnit* Performer = Units.FindRef(Beat.Source);
    if (!IsValid(Performer) || Performer->Camp || Performer->IsEventToken() || Performer->IsVisuallyDead())
    {
        P.Analysis.SetFallback(Beat.AnalysisSequence, "public_performer_unavailable"); return false;
    }
    if (Performer->Body->GetSkeletalMeshAsset() && Performer->Body->GetSkeletalMeshAsset()->GetPathName().StartsWith(TEXT("/Game/Art/Western/")))
    {
        // Keep the same public ability, reveal and choice sequence, using its
        // normal presentation rather than the old sci-fi specimen-case bundle.
        P.Analysis.SetFallback(Beat.AnalysisSequence, "western_crew_generic_action"); return false;
    }
    // The case replaces only this analysis's immediately following public
    // reveal batch. An interleaved reshuffle remains ordinary ordered staging;
    // do not show a later sample before that supply transition has played.
    int32 RevealBeats = 0, RevealCount = 0;
    for (const auto& Pending : P.Pending)
    {
        if (Pending.Kind != TEXT("reveal_discard") || Pending.AnalysisSequence != Beat.AnalysisSequence) break;
        ++RevealBeats; RevealCount += Pending.Count;
    }
    if (RevealCount != static_cast<int32>(Context["reveals"].size()))
    {
        P.Analysis.SetFallback(Beat.AnalysisSequence, "interleaved_public_supply_transition"); return false;
    }
    TArray<FOldWestAnalysisSample> Samples;
    for (const J& Reveal : Context["reveals"])
    {
        FOldWestAnalysisSample Sample;
        Sample.Index = Reveal.value("reveal_index", -1); Sample.Handle = Reveal.value("target", 0);
        Sample.Name = Text(Reveal.value("name", std::string())); Sample.Effect = Text(Reveal.value("junk_effect", std::string()));
        Samples.Add(MoveTemp(Sample));
    }
    CancelScientistScenes(TEXT("new_analysis_for_performer"), Beat.Source, true);
    UOldWestScientistPlayback* Playback = NewObject<UOldWestScientistPlayback>(this);
    AddInstanceComponent(Playback); Playback->RegisterComponent();
    if (!Playback->Begin(Performer, P.MatchId, Beat.AnalysisSequence, Samples))
    {
        Playback->Cancel(TEXT("begin_failed"), true); Playback->DestroyComponent();
        P.Analysis.SetFallback(Beat.AnalysisSequence, "playback_bundle_or_performer_rejected");
        return false;
    }
    P.ScientistPlayback.Add(Beat.AnalysisSequence, Playback);
    P.Analysis.SetBespoke(Beat.AnalysisSequence);
    Beat.ScientistScene = true;
    Beat.Duration = 8.f;
    for (const J& Reveal : Context["reveals"])
    {
        const int32 Sequence = Reveal.value("sequence", 0);
        Beat.AnalysisMappedSequences.Add(Sequence);
        Beat.AnalysisPresentedThrough = FMath::Max(Beat.AnalysisPresentedThrough, Sequence);
    }
    if (RevealBeats > 0) P.Pending.RemoveAt(0, RevealBeats);
    // No SetDecision here, even if an AI/remote response is already public.
    // Its continuation occupies the real log position ahead of junk results.
    return true;
}

void AOldWestBattlefield::FrameScientistScene(int32 Key)
{
    auto& P = *Presentation;
    UOldWestScientistPlayback* Playback = P.ScientistPlayback.FindRef(Key).Get();
    if (!IsValid(Playback) || !P.Active.IsSet() || P.Active->AnalysisSequence != Key) return;
    FBox Bounds = Playback->GetSceneBounds();
    AOldWestUnit* Unit = Units.FindRef(P.Active->Source);
    if (IsValid(Unit)) Bounds += Unit->GetVisualBounds();
    if (!Bounds.IsValid) return;
    P.EffectFraming = true; P.EffectFrameBounds = Bounds;
    P.EffectViewDirection = IsValid(Unit) && Unit->Body
        ? Unit->Body->GetComponentQuat().RotateVector(FVector(1.f, 1.f, 0)).GetSafeNormal2D()
        : FVector(1.f, Seat == 0 ? 1.f : -1.f, 0).GetSafeNormal2D();
}

void AOldWestBattlefield::AdvanceScientistScenes(float DeltaSeconds)
{
    auto& P = *Presentation;
    TArray<int32> Remove;
    for (const auto& Pair : P.ScientistPlayback)
    {
        UOldWestScientistPlayback* Playback = Pair.Value.Get();
        const J Context = P.Analysis.Get(Pair.Key);
        if (!IsValid(Playback) || Context.is_null())
        {
            if (IsValid(Playback)) { Playback->Cancel(TEXT("context_missing"), true); Playback->DestroyComponent(); }
            P.Analysis.FinishPresentation(Pair.Key, "context_or_component_missing", nullptr);
            Remove.Add(Pair.Key); continue;
        }
        const FString PreviousPhase = Playback->GetPhaseName();
        // One clock, once per Battlefield PostUpdateWork, even in nonbusy hold.
        const bool Advanced = Playback->Advance(DeltaSeconds);
        if (!Advanced)
        {
            UE_LOG(LogTemp, Error, TEXT("OLDWEST_SCIENTIST_PRESENTATION_ERROR Playback sampling failed %d"), Pair.Key);
            Playback->Cancel(TEXT("sample_failed"), true);
        }
        if (Playback->IsAwaitingChoice() || Playback->IsComplete())
        {
            int32 Through = Pair.Key;
            for (const J& Reveal : Context["reveals"]) Through = FMath::Max(Through, Reveal.value("sequence", 0));
            P.Analysis.Presented(Pair.Key, Through);
        }
        if (Playback->IsComplete() || !Playback->IsActive())
        {
            const J Final = J::parse(TCHAR_TO_UTF8(*Playback->GetDebugJson()));
            const char* Reason = Playback->IsComplete() ? "bespoke_scene_completed" : "bespoke_scene_cancelled";
            P.Analysis.FinishPresentation(Pair.Key, Reason, Final);
            Playback->DestroyComponent(); Remove.Add(Pair.Key); continue;
        }
        if (IsScientistBeat() && P.Active->AnalysisSequence == Pair.Key)
        {
            FrameScientistScene(Pair.Key);
            if (Playback->GetPhaseName() != PreviousPhase)
                FocusAction(P.Active->Source, P.Active->Target, P.Active->Kind, P.Active->Revision);
            else if (IsShotObstructed(DesiredFocus, DesiredCamera, INDEX_NONE))
            {
                DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, INDEX_NONE);
                P.ShotOffset = DesiredCamera - DesiredFocus;
                if (Camera) Camera->SetActorLocation(DesiredCamera);
            }
        }
    }
    for (int32 Key : Remove) P.ScientistPlayback.Remove(Key);
}

void AOldWestBattlefield::ClearActionEffects()
{
    if (!Presentation) return;
    for (auto& Effect : Presentation->Effects) if (Effect.Mesh.IsValid()) Effect.Mesh->DestroyComponent();
    Presentation->Effects.Empty();
    for (auto& Delivery : Presentation->Deliveries) if (Delivery.IsValid())
    { Delivery->Clear(); Delivery->DestroyComponent(); }
    Presentation->Deliveries.Empty();
    Presentation->EffectFraming = false;
    Presentation->EffectFrameBounds = FBox(ForceInit);
    Presentation->EffectViewDirection = FVector::ZeroVector;
    Presentation->ServiceLayouts.Empty();
    Presentation->ServiceLayoutFailures = 0;
}

void AOldWestBattlefield::StageActionEffects(bool ImpactPhase)
{
    auto& P = *Presentation;
    if (!P.Active.IsSet()) return;
    if (IsScientistBeat()) { if (!ImpactPhase) FrameScientistScene(P.Active->AnalysisSequence); return; }
    auto Shape = [this, &P](const TCHAR* MeshName, const TCHAR* MaterialName, const FVector& From, const FVector& To,
        const FVector& Scale, float Duration, float Delay = 0.f, float Arc = 0.f, float Spin = 0.f, bool Shrink = false,
        FRotator Rotation = FRotator::ZeroRotator, float WheelRadius = 0.f) -> UStaticMeshComponent*
    {
        // Imported meshes retain all authored material slots; primitives may
        // request their existing single material. Both use the same shot life.
        if (P.Effects.Num() >= 120) return nullptr;
        const FString Name(MeshName);
        const FString MeshPath = Name.StartsWith(TEXT("/")) ? Name :
            FString(TEXT("/Engine/BasicShapes/")) + Name + TEXT(".") + Name;
        UStaticMesh* Asset = LoadObject<UStaticMesh>(nullptr, *MeshPath);
        if (!Asset)
        {
            UE_LOG(LogTemp, Error, TEXT("OLDWEST_ACTION_PROP_ERROR Missing mesh %s"), *MeshPath);
            return nullptr;
        }
        UMaterialInterface* Material = nullptr;
        if (MaterialName)
        {
            const FString NameOfMaterial(MaterialName);
            const FString Path = NameOfMaterial.StartsWith(TEXT("/")) ? NameOfMaterial :
                FString(TEXT("/Game/Art/WaterDepotV2/Materials/")) + NameOfMaterial + TEXT(".") + NameOfMaterial;
            Material = LoadObject<UMaterialInterface>(nullptr, *Path);
            if (!Material)
            {
                UE_LOG(LogTemp, Error, TEXT("OLDWEST_ACTION_PROP_ERROR Missing material %s"), *Path);
                return nullptr;
            }
        }
        UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this);
        AddInstanceComponent(Mesh);
        Mesh->SetupAttachment(GetRootComponent());
        Mesh->SetStaticMesh(Asset);
        if (Material) Mesh->SetMaterial(0, Material);
        if (MaterialName && FString(MaterialName).Contains(TEXT("M_Trouble_Smoke"))) Mesh->SetCastShadow(false);
        Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Mesh->SetCanEverAffectNavigation(false);
        Mesh->RegisterComponent();
        Mesh->SetWorldLocation(From); Mesh->SetWorldRotation(Rotation); Mesh->SetWorldScale3D(Scale);
        Mesh->SetVisibility(Delay <= 0.f);
        FActionEffect Effect;
        Effect.Mesh = Mesh; Effect.From = From; Effect.To = To; Effect.Scale = Scale; Effect.Rotation = Rotation;
        Effect.Duration = FMath::Max(.05f, Duration); Effect.Delay = Delay; Effect.Arc = Arc; Effect.Spin = Spin; Effect.Shrink = Shrink;
        Effect.WheelRadius = WheelRadius;
        P.Effects.Add(Effect);
        return Mesh;
    };
    auto Supply = [&Shape](const FString& Name, const FVector& From, const FVector& To, float Duration = 1.5f,
        FRotator Rotation = FRotator::ZeroRotator, float Spin = 0.f, float WheelRadius = 0.f,
        FVector Scale = FVector::OneVector) -> UStaticMeshComponent*
    {
        const FString Path = TEXT("/Game/Art/ActionProps/Meshes/") + Name + TEXT(".") + Name;
        return Shape(*Path, nullptr, From, To, Scale, Duration, 0.f, 0.f, Spin, false, Rotation, WheelRadius);
    };
    auto Transport = [this, &P](FVector Ground, const FVector& Rear, int32 Count, bool Water, bool Medical, bool Store)
    {
        const FVector Direction=Store?Rear:-Rear;
        const FRotator Facing(0,Direction.Rotation().Yaw-90.f,0);
        const FVector Travel=Direction*UOldWestDeliveryVisuals::RouteLength;
        // Conservative source-team footprint at the documented .4 diorama
        // scale. The actual imported assembly is checked against it below.
        const FBox TeamBounds(FVector(-60,-90,0),FVector(60,360,125));
        TArray<FVector> Offsets;
        for (float Forward=0;Forward<=1080;Forward+=120)
            for (float Side : {0.f,-180.f,180.f,-360.f,360.f,-540.f,540.f})
                Offsets.Add(-Rear*Forward+FVector(Side,0,0));
        Offsets.StableSort([](const FVector& A,const FVector& B){return A.SizeSquared()<B.SizeSquared();});
        FVector From,To; FBox Layout(ForceInit); bool Found=false;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestDeliveryClearance),true); Query.AddIgnoredActor(this);
        for (const FVector& Offset : Offsets)
        {
            const FVector Near=WalkGround(GetWorld(),Ground+Offset,this);
            const FVector Back=WalkGround(GetWorld(),Near+Rear*UOldWestDeliveryVisuals::RouteLength,this);
            if (FMath::Abs(Near.Z-Back.Z)>2.f) continue;
            const FVector A=Store?Near:Back, B=A+Travel;
            FBox Candidate=TeamBounds.TransformBy(FTransform(Facing,A));
            Candidate+=TeamBounds.TransformBy(FTransform(Facing,B));
            bool Blocked=false;
            for (int32 Side=0;Side<2;++Side)
            {
                const float Sign=Side==0?1.f:-1.f;
                const FVector Fuse=EventPosition(Side,-1)+FVector(240.f*Sign,0,0);
                const float End=Fuse.Y+Sign*1860.f;
                if (Candidate.Min.X<Fuse.X+45.f && Candidate.Max.X>Fuse.X-45.f &&
                    Candidate.Min.Y<FMath::Max(Fuse.Y,End)+35.f && Candidate.Max.Y>FMath::Min(Fuse.Y,End)-35.f) Blocked=true;
            }
            for (const auto& Pair : Units) if (IsValid(Pair.Value) && !Pair.Value->IsHidden() &&
                Candidate.Intersect(Pair.Value->GetVisualBounds().ExpandBy(12.f))) { Blocked=true; break; }
            for (const FBox& Existing : P.ServiceLayouts) if (Candidate.Intersect(Existing)) Blocked=true;
            FBox Probe=Candidate; Probe.Min.Z+=12.f;
            if (Blocked || GetWorld()->OverlapBlockingTestByChannel(Probe.GetCenter(),FQuat::Identity,
                ECC_Camera,FCollisionShape::MakeBox(Probe.GetExtent()),Query)) continue;
            From=A; To=B; Layout=Candidate; Found=true; break;
        }
        if (!Found) { ++P.ServiceLayoutFailures; return; }
        auto* Delivery=NewObject<UOldWestDeliveryVisuals>(this);
        AddInstanceComponent(Delivery); Delivery->SetupAttachment(GetRootComponent()); Delivery->RegisterComponent();
        if (!Delivery->Build(From,To,Count,Water,Medical))
        { Delivery->Clear(); Delivery->DestroyComponent(); ++P.ServiceLayoutFailures; return; }
        const FBox Bounds=Delivery->GetVisualBounds();
        const FBox Allowance=Layout.ExpandBy(2.f);
        if (!Allowance.IsInsideOrOn(Bounds.Min) || !Allowance.IsInsideOrOn(Bounds.Max))
        {
            UE_LOG(LogTemp,Error,TEXT("OLDWEST_DELIVERY_LAYOUT_TOO_SMALL %s %s"),*Layout.ToString(),*Bounds.ToString());
            Delivery->Clear(); Delivery->DestroyComponent(); ++P.ServiceLayoutFailures; return;
        }
        P.Deliveries.Add(Delivery); P.ServiceLayouts.Add(Layout);
        P.Active->Duration=FMath::Max(P.Active->Duration,Delivery->GetDuration());
        P.EffectFraming=true; P.EffectFrameBounds+=Layout;
        // Look into the uncovered rear cargo bed in either travel direction.
        // Public crates stay visible without displaying private card identities.
        P.EffectViewDirection=(FVector(.85f,0,0)-Direction*1.25f).GetSafeNormal()+FVector(0,0,.35f);
    };
    auto Fragments = [&Shape](const FVector& Center, int32 Seed, bool Metal, int32 Count)
    {
        FRandomStream Random(Seed);
        for (int32 I = 0; I < Count; ++I)
        {
            const FVector End = Center + FVector(Random.FRandRange(-130, 130), Random.FRandRange(-130, 130), -65.f);
            const float Size = Random.FRandRange(.025f, .065f);
            Shape(TEXT("Cube"), Metal ? TEXT("M_ExposedZinc") : TEXT("M_DustAndGravel"), Center, End,
                FVector(Size, Size * .45f, Size * .8f), .58f + I * .014f, 0.f, Random.FRandRange(25, 85), Random.FRandRange(-240, 240), true);
        }
    };
    auto Stage = [this, &P, &Shape, &Supply, &Transport, &Fragments, ImpactPhase](const FCinematicBeat& Beat)
    {
        AOldWestUnit* Unit = Beat.KnownTarget ? Units.FindRef(Beat.Target) : nullptr;
        AOldWestUnit* Source = Beat.ResourceOnly ? nullptr : Units.FindRef(Beat.Source);
        const FVector Center = Unit ? Unit->GetPresentationFocus() : Beat.Before.Location + FVector(0, 0, 60);
        FVector Ground = Unit ? Unit->GetActorLocation() : Beat.Before.Location;
        FVector Operation = Center;
        if (Unit && Unit->Camp)
        {
            const FBox Bounds = Unit->GetVisualBounds();
            const FVector Front = Unit->CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0, -1, 0));
            Operation = Bounds.GetCenter() + Front * (Bounds.GetExtent().Y + 75.f);
            Operation = WalkGround(GetWorld(), Operation, Unit) + FVector(0, 0, 75);
        }
        const FVector Rear(0, Beat.Player == 0 ? 1.f : -1.f, 0);
        const FString& Kind = Beat.Kind;
        if (Beat.Departure) return;
        const bool Hit = Kind == TEXT("damage") || Kind == TEXT("destroy");
        // A quarantine marker is not a gun. The authoritative wound beat still
        // changes each victim's condition, without projectiles or impact debris.
        if (Hit && Source && Source->IsEventToken() &&
            (Source->GetVisualCardId() == TEXT("cholera") || Source->GetVisualCardId() == TEXT("run_out_of_town"))) return;
        if (ImpactPhase)
        {
            if (Kind == TEXT("reveal_person") && Unit && Beat.Before.Punk && !Beat.After.Punk && !Beat.After.Camp)
            {
                // Only the public reveal beat drops cloth. Private inspection
                // never enters this path. Sample the still-generic Drifter's
                // face before ResolveImpact swaps to the public Crew model.
                const FQuat Facing = Unit->Body->GetComponentQuat();
                const FVector Front = Facing.RotateVector(FVector(0, 1, 0)).GetSafeNormal2D();
                const FVector Head = Unit->Body->DoesSocketExist(TEXT("Head")) ?
                    Unit->Body->GetSocketLocation(TEXT("Head")) : Ground + FVector(0, 0, 165);
                const FVector From = Head + Front * 14.f - FVector(0, 0, 11.f);
                const FVector To = WalkGround(GetWorld(), Ground + Front * 70.f, Unit) + FVector(0, 0, 6.f);
                if (UStaticMeshComponent* Cloth = Shape(TEXT("/Game/Art/Western/Reveal/SM_Reveal_Bandana.SM_Reveal_Bandana"),
                    nullptr, From, To, FVector(1.f), .95f, 0.f, 0.f, 0.f, false, Facing.Rotator()))
                {
                    Cloth->ComponentTags.Add(TEXT("OldWestRevealBandana"));
                    P.Effects.Last().FallingCloth = true;
                }
            }
            else if (Hit) Fragments(Center, Beat.Sequence, Unit && Unit->Camp, Unit && Unit->Camp ? 22 : 9);
            else if (Kind == TEXT("junk") || Kind == TEXT("discard") || Kind == TEXT("reveal_discard") || Kind == TEXT("remove_ruin"))
            {
                if (!P.EffectFraming) Fragments(Center, Beat.Sequence, true, 18);
                SpatialAudio(this, TEXT("SW_Impact_Metal_02"), Center, .45f);
            }
            return;
        }
        if (Hit)
        {
            if (Source && Source->IsRaider() && Source->IsEventToken())
            {
                // The charge supplies the attack presentation. Frame the herd
                // and holding together; cattle never emit weapon projectiles.
                P.EffectFraming = true;
                P.EffectFrameBounds = Source->GetVisualBounds();
                if (Unit) P.EffectFrameBounds += Unit->GetVisualBounds();
                P.EffectViewDirection = Unit && Unit->Camp
                    ? Unit->CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0,-1,0)).RotateAngleAxis(25.f,FVector::UpVector).GetSafeNormal2D()
                    : FVector(-.6f,1.f,0).GetSafeNormal();
                return;
            }
            if (Source && Source != Unit)
            {
                const FVector Start = Source->Weapon->IsVisible() ? Source->Weapon->GetComponentLocation() : Source->GetPresentationFocus();
                const FVector Direction = (Center - Start).GetSafeNormal();
                Shape(TEXT("Cylinder"), TEXT("M_WarmLamp"), Start, Center, FVector(.018f, .018f, .75f), .16f,
                    0.f, 0.f, 0.f, true, FRotationMatrix::MakeFromZ(Direction).Rotator());
            }
            return;
        }
        if (Kind == TEXT("draw_card") || Kind == TEXT("water") || Kind == TEXT("store_water") || Kind == TEXT("reshuffle"))
        {
            // Whiskey stands in for water, but never in Native characters' presentation
            // (REBRAND_GUARDRAILS): their deliveries carry plain trade crates instead.
            const bool Water = (Kind == TEXT("water") || Kind == TEXT("store_water"))
                && !IsNativeVisual(Unit) && !IsNativeVisual(Source);
            const int32 Count = FMath::Clamp(Beat.Count, 1, 6);
            FVector SupplyGround = Unit && Unit->Camp ? Operation - FVector(0, 0, 75) : Ground;
            if (Unit) SupplyGround += FVector(190, 0, 0);
            SupplyGround = WalkGround(GetWorld(), SupplyGround, Unit);
            if (Water && Kind == TEXT("water") && Beat.Detail.IsEmpty())
            {
                // A public one-unit bonus has no numeric refill detail. The
                // enlarged bar glass is a currency token, never a drink pose.
                // Find room for the barrel and its supported glass together.
                bool Clear = false;
                FBox Layout(ForceInit);
                for (float Forward = 0.f; Forward <= 960.f && !Clear; Forward += 120.f)
                    for (float Side : {0.f,-180.f,180.f,-360.f,360.f})
                    {
                        const FVector At = WalkGround(GetWorld(),SupplyGround-Rear*Forward+FVector(Side,0,0),this);
                        const FBox Candidate(At+FVector(-43,-43,12),At+FVector(43,43,120));
                        bool Blocked = false;
                        // The cosmetic fuse deliberately has no collision.
                        // Reserve its cord and54cm notch ties nevertheless;
                        // otherwise the resource-only anchor lands on it.
                        for (int32 SideIndex=0;SideIndex<2;++SideIndex)
                        {
                            const float Direction=SideIndex==0?1.f:-1.f;
                            const FVector FuseStart=EventPosition(SideIndex,-1)+FVector(240.f*Direction,0,0);
                            const float FuseEndY=FuseStart.Y+Direction*1860.f;
                            if (Candidate.Min.X<FuseStart.X+45.f && Candidate.Max.X>FuseStart.X-45.f &&
                                Candidate.Min.Y<FMath::Max(FuseStart.Y,FuseEndY)+35.f &&
                                Candidate.Max.Y>FMath::Min(FuseStart.Y,FuseEndY)-35.f) Blocked=true;
                        }
                        for (const auto& Pair : Units) if (IsValid(Pair.Value) && !Pair.Value->IsHidden() &&
                            Candidate.Intersect(Pair.Value->GetVisualBounds().ExpandBy(12.f))) { Blocked=true; break; }
                        for (const FBox& Existing : P.ServiceLayouts) if (Candidate.Intersect(Existing)) Blocked=true;
                        FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestBonusClearance),true); Query.AddIgnoredActor(this);
                        if (Blocked || GetWorld()->OverlapBlockingTestByChannel(Candidate.GetCenter(),FQuat::Identity,
                            ECC_Camera,FCollisionShape::MakeBox(Candidate.GetExtent()),Query)) continue;
                        SupplyGround=At; Layout=Candidate; Clear=true; break;
                    }
                if (Clear)
                {
                    P.ServiceLayouts.Add(Layout);
                    UStaticMeshComponent* Barrel=Supply(TEXT("SM_Action_WhiskeyBarrel"),SupplyGround,SupplyGround);
                    if (Barrel)
                    {
                        // Existing barrel: 84cm high, head inset2cm, head
                        // thickness.8cm. Rest on its actual top face at82.4cm.
                        const FVector Top=SupplyGround+FVector(0,0,82.4f);
                        Supply(TEXT("SM_Action_BonusWhiskeyGlass"),Top,Top,1.5f,FRotator::ZeroRotator,0.f,0.f,FVector(4.5f));
                    }
                    P.EffectFraming=true; P.EffectFrameBounds+=Layout;
                    P.EffectViewDirection=(-Rear+FVector(.25f,0,0)).GetSafeNormal();
                }
                else ++P.ServiceLayoutFailures;
            }
            else Transport(SupplyGround, Rear, Count, Water, false, Kind == TEXT("store_water"));
            SpatialAudio(this, Water ? TEXT("SW_Water_Delivery") :
                Kind == TEXT("reshuffle") ? TEXT("SW_Deck_Shuffle") : TEXT("SW_Supply_Delivery"), Center, .6f);
        }
        else if (Kind == TEXT("turn_start"))
        {
            // Establish the newly active camp line. Replenishment is a separate
            // public water log emitted after event decisions actually finish.
            for (const auto& Pair : Units) if (AOldWestUnit* Camp = Pair.Value; Camp && Camp->Camp && Camp->Side == Beat.Player && !Camp->IsVisuallyDead())
            {
                const FBox Bounds = Camp->GetVisualBounds();
                const FVector Front = Camp->CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0, -1, 0));
                FVector Base = WalkGround(GetWorld(), Bounds.GetCenter() + Front * (Bounds.GetExtent().Y + 50.f), Camp);
                Shape(TEXT("Cylinder"), TEXT("M_OiledSteel"), Base + FVector(0, 0, 58), Base + FVector(0, 0, 58), FVector(.035f, .035f, 1.16f), 1.5f);
                const FVector Pivot = Base + FVector(0, 0, 115);
                if (Shape(TEXT("Cube"), TEXT("M_WornOchrePaint"), Pivot + FVector(25, 0, 0), Pivot + FVector(25, 0, 0), FVector(.5f, .035f, .17f), 1.1f, 0.f, 0.f, -75.f))
                {
                    P.Effects.Last().Hinged = true; P.Effects.Last().Pivot = Pivot;
                }
            }
        }
        else if (Kind == TEXT("junk") || Kind == TEXT("discard") || Kind == TEXT("reveal_discard"))
        {
            FVector SupplyGround = Unit && Unit->Camp ? Operation - FVector(0, 0, 75) : Ground;
            if (Unit) SupplyGround += FVector(190, 0, 0);
            Transport(WalkGround(GetWorld(), SupplyGround, Unit), Rear, Beat.Count, false, false, true);
        }

        // Treatment supplies belong to the restore beat. The subsequent
        // hospital transfer follows the walking patient; spawning another
        // wagon there would pin the camera to the departure point.
        else if (Kind == TEXT("restore"))
        {
            FVector SupplyGround = Unit && Unit->Camp ? Operation - FVector(0, 0, 75) : Ground;
            SupplyGround = WalkGround(GetWorld(), SupplyGround + FVector(190, 0, 0), Unit);
            Transport(SupplyGround, Rear, 1, false, true, false);
            if (Unit && !Unit->Camp) P.EffectFrameBounds += Unit->GetVisualBounds();
        }

        else if (Kind == TEXT("event_resolve"))
        {
            // Instant events never occupy a queue actor. Announce their actual
            // Play Now footprint as well as the resolving card's name.
            if(!Beat.KnownTarget) {
                for(float Y:{-190.f,190.f}) {
                    const FVector At=Ground+FVector(0,Y,10);
                    Shape(TEXT("Cube"),TEXT("M_WarmLamp"),At,At,FVector(4.4f,.08f,.06f),1.5f,0.f,0.f,0.f,true);
                }
                for(float X:{-220.f,220.f}) {
                    const FVector At=Ground+FVector(X,0,10);
                    Shape(TEXT("Cube"),TEXT("M_WarmLamp"),At,At,FVector(.08f,3.8f,.06f),1.5f,0.f,0.f,0.f,true);
                }
            }
            const FString Identity = (Beat.Before.CardId + TEXT(" ") + Beat.Detail.ToLower()).Replace(TEXT(" "), TEXT("_"));
            if (Unit && Unit->IsRaider())
            {
                // The herd waits here. Only a later authoritative hit names
                // the defender's selected holding; no weapon flash or audio.

            }
            else if (Identity.Contains(TEXT("poker_night")))
            {
                for (int32 I=0;I<4;++I)
                    Shape(TEXT("Cube"),TEXT("/Game/Art/Western/Trouble/Objects/Materials/M_Trouble_Paper.M_Trouble_Paper"),
                        Ground+FVector(I*14-21,0,32),Ground+FVector(I*24-36,12,88),FVector(.12f,.18f,.006f),
                        .9f,I*.05f,12.f,25.f,true);
            }
            else if (Identity.Contains(TEXT("gold_rush")))
            {
                const FVector Pan=Unit?Unit->EventPropPoint(FVector(0,0,32)):Ground+FVector(0,0,35);
                for (int32 I=0;I<3;++I)
                    Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_Gold.M_Trouble_Gold"),
                        Pan+FVector(I*12-12,0,0),Pan+FVector(I*17-17,0,50),FVector(.025f),.9f,I*.09f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("curfew")))
            {
                const FVector Lamp=Unit?Unit->EventPropPoint(FVector(0,-18,216)):Ground+FVector(0,0,222);
                Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_FlameAmber.M_Trouble_FlameAmber"),
                    Lamp,Lamp,FVector(.075f,.075f,.13f),1.1f,0.f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("cannonade")))
            {
                // FBX conversion mirrors the source Blender Y axis. Using the
                // component transform also handles the opposite player's yaw.
                const FVector Muzzle=Unit?Unit->EventPropPoint(FVector(0,87.2f,98)):Ground+FVector(0,0,101);
                const FVector Forward=Unit?(Unit->EventPropPoint(FVector(0,100,98))-Muzzle).GetSafeNormal():Rear;
                Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_FlameAmber.M_Trouble_FlameAmber"),
                    Muzzle,Muzzle+Forward*15.f,FVector(.16f),.22f,0.f,0.f,0.f,true);
                for (int32 I=0;I<6;++I)
                    Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_Smoke.M_Trouble_Smoke"),Muzzle+Forward*12.f,
                        Muzzle+Forward*(30+I*8)+FVector(I*7-18,0,25+I*10),FVector(.12f+I*.025f),
                        1.1f,I*.04f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("ambush")))
            {
                const FVector Muzzle=Unit?Unit->EventPropPoint(FVector(79.85f,45.77f,83)):Ground+FVector(0,0,85);
                const FVector Forward=Unit?(Unit->EventPropPoint(FVector(91,51,83))-Muzzle).GetSafeNormal():Rear;
                for (int32 I=0;I<3;++I)
                    Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_FlameAmber.M_Trouble_FlameAmber"),
                        Muzzle,Muzzle+Forward*14.f,FVector(.055f),.16f,I*.18f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("run_out_of_town")))
            {
                const FVector Coil=Unit?Unit->EventPropPoint(FVector(6,-6,72)):Ground+FVector(0,0,75);
                for (int32 I=0;I<5;++I)
                    Shape(TEXT("Sphere"),TEXT("/Game/Art/Western/Trouble/Schemes/Materials/M_Trouble_FlameAmber.M_Trouble_FlameAmber"),
                        Coil,Coil+FVector(I*7-10,9,20+I*4),FVector(.016f),
                        .9f,I*.05f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("box_canyon")))
                for (int32 I = 0; I < 6; ++I)
                    Shape(TEXT("Cube"), TEXT("/Game/Art/Western/Trouble/Landscapes/Materials/M_Trouble_SandstoneDark.M_Trouble_SandstoneDark"),
                        Ground+FVector(I*12-30,0,42),Ground+FVector(I*20-50,24,12),FVector(.04f,.035f,.045f),
                        1.f,I*.04f,8.f,40.f,true);
            else if (Identity.Contains(TEXT("hard_winter")))
            {
                for (int32 I = 0; I < 24; ++I)
                    Shape(TEXT("Sphere"), TEXT("/Game/Art/Western/Trouble/Landscapes/Materials/M_Trouble_Snow.M_Trouble_Snow"),
                        Ground+FVector((I%6)*25-65,(I/6)*20-30,115+(I%3)*9),
                        Ground+FVector((I%6)*25-95,(I/6)*20-15,14),FVector(.018f),
                        1.f,I*.015f,0.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("prairie_fire")))
            {
                for (int32 I = 0; I < 16; ++I)
                    Shape(TEXT("Sphere"), TEXT("/Game/Art/Western/Trouble/Landscapes/Materials/M_Trouble_FlameGold.M_Trouble_FlameGold"),
                        Ground+FVector((I%8)*19-65,(I/8)*20-10,45),
                        Ground+FVector((I%8)*22-45,(I/8)*35,155+(I%3)*12),FVector(.025f),
                        1.f,I*.02f,8.f,0.f,true);
            }
            else if (Identity.Contains(TEXT("cholera")))
                for (int32 I = 0; I < 5; ++I)
                {
                    Shape(TEXT("Cube"),TEXT("/Game/Art/Western/Trouble/Objects/Materials/M_Trouble_Yellow.M_Trouble_Yellow"),
                        Ground+FVector(I*17-35,0,140),Ground+FVector(I*20-40,-12,185),
                        FVector(.08f,.003f,.11f),1.f,I*.03f,5.f,20.f,true);
                }
            else
            {
                // Launch ordinance along the public operation's approach line;
                // subsequent authoritative hit beats show its actual victims.
                const FVector End = Center - Rear * 700.f + FVector(0, 0, 260);
                Shape(TEXT("Sphere"), TEXT("M_WarmLamp"), Center, End, FVector(.11f), .75f, .06f, 110.f, 0.f, true);
                Fragments(Center, Beat.Sequence, false, 12);
            }
            if (Unit) Unit->PlayAction(TEXT("event_resolve"), -Rear);
            if (!OldWestTrouble::ForCard(TCHAR_TO_UTF8(*Beat.Before.CardId)))
                SpatialAudio(this, TEXT("SW_Impact_Metal_01"), Center, .45f);
        }
        else if (Kind == TEXT("ability") || Kind == TEXT("expose_all"))
        {
            const bool DrifterHitPreparation = Unit && !Unit->Camp && Beat.AbilityIndex == 101 &&
                Unit->Body && Unit->Body->GetSkeletalMeshAsset() &&
                Unit->Body->GetSkeletalMeshAsset()->GetPathName() == TEXT("/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter");
            if (Unit) Unit->PlayAction(DrifterHitPreparation ? TEXT("prepare_hit") : TEXT("ability"), -Rear);
            const bool WesternPerformer=Unit && (
                (!Unit->Camp && Unit->Body && Unit->Body->GetSkeletalMeshAsset() &&
                 Unit->Body->GetSkeletalMeshAsset()->GetPathName().StartsWith(TEXT("/Game/Art/Western/"))) ||
                (Unit->Camp && OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*Beat.Before.CardId))));
            if(WesternPerformer)
            {
                // The approved body/holding performs the public preparation.
                // Its subsequent ordered hit, hire or restore beat supplies the
                // outcome; no unrelated industrial control box is introduced.
                // Keep the ordinary subject camera: an effect-box centre is
                // inside a closed building and is not a visible prop target.
            }
            else
            {
            // An exterior control station has a real lever pivot, gearbox
            // and footing. Its moving parts remain outside the source building
            // instead of disappearing inside that building's bounds center.
            FVector Base = Unit && Unit->Camp ? Operation - FVector(0, 0, 75) : Ground + FVector(105, 0, 0);
            Base = WalkGround(GetWorld(), Base, Unit);
            Shape(TEXT("Cube"), TEXT("M_OiledSteel"), Base + FVector(0, 0, 34), Base + FVector(0, 0, 34), FVector(.48f, .4f, .68f), 1.5f);
            Shape(TEXT("Cube"), TEXT("M_AgedGalvanized"), Base + FVector(0, 0, 4), Base + FVector(0, 0, 4), FVector(.75f, .64f, .08f), 1.5f);
            Shape(TEXT("Cube"), TEXT("M_DarkGaugeGlass"), Base + FVector(0, -22, 45), Base + FVector(0, -22, 45), FVector(.33f, .04f, .26f), 1.5f);
            const FVector Pivot = Base + FVector(0, 0, 70);
            Shape(TEXT("Cylinder"), TEXT("M_WornOchrePaint"), Pivot, Pivot, FVector(.19f, .19f, .24f), 1.5f, 0.f, 0.f, 0.f, false, FRotator(0, 0, 90));
            if (Shape(TEXT("Cylinder"), TEXT("M_AgedGalvanized"), Pivot + FVector(0, 0, 21), Pivot + FVector(0, 0, 21), FVector(.035f, .035f, .42f), 1.05f, 0.f, 0.f, 42.f))
            {
                P.Effects.Last().Hinged = true; P.Effects.Last().Pivot = Pivot;
            }
            if (Shape(TEXT("Sphere"), TEXT("M_FlakingOxide"), Pivot + FVector(0, 0, 44), Pivot + FVector(0, 0, 44), FVector(.105f), 1.05f, 0.f, 0.f, 42.f))
            {
                P.Effects.Last().Hinged = true; P.Effects.Last().Pivot = Pivot;
            }
            Shape(TEXT("Cube"), TEXT("M_StatusLED"), Base + FVector(0, -25, 49), Base + FVector(0, -25, 49), FVector(.16f, .03f, .05f), 1.5f);
            P.EffectFraming = true;
            P.EffectFrameBounds += FBox(Base - FVector(110, 95, 0), Base + FVector(110, 95, 145));
            if (Unit && !Unit->Camp) P.EffectFrameBounds += Unit->GetVisualBounds();
            }
        }

        else if (Kind == TEXT("enter") || Kind == TEXT("move") || Kind == TEXT("return") || Kind == TEXT("recruit_id") || Kind == TEXT("raid_launch"))
        {
            // Small ground debris trails the physical walking figure; the
            // character, rather than a floating symbol, carries this action.
            const FVector Start = Ground + FVector(0, 0, 14);
            for (int32 I = 0; I < 5; ++I)
                Shape(TEXT("Sphere"), TEXT("M_DustAndGravel"), Start, Start + Rear * (25.f + I * 12.f),
                    FVector(.075f, .12f, .035f), .65f, I * .1f, 12.f, 0.f, true);
        }
        else if(Kind==TEXT("event_play"))
        {
            // Announce the actual queue/Play Now footprint before its effects
            // resolve, so a small event prop cannot disappear unnoticed.
            for(float Y:{-190.f,190.f}) {
                const FVector At=Ground+FVector(0,Y,10);
                Shape(TEXT("Cube"),TEXT("M_WarmLamp"),At,At,FVector(4.4f,.08f,.06f),1.6f,0.f,0.f,0.f,true);
            }
            for(float X:{-220.f,220.f}) {
                const FVector At=Ground+FVector(X,0,10);
                Shape(TEXT("Cube"),TEXT("M_WarmLamp"),At,At,FVector(.08f,3.8f,.06f),1.6f,0.f,0.f,0.f,true);
            }
            SpatialAudio(this,TEXT("SW_Event_Advance"),Center,.65f);
        }
        else if (Kind == TEXT("event_advance") || Kind == TEXT("camp_advance") || Kind == TEXT("remove_ruin"))
        {
            if (Unit && Unit->IsRaider()) return;
            Fragments(Ground + FVector(0, 0, 65), Beat.Sequence, Kind == TEXT("remove_ruin"), 12);
            SpatialAudio(this, Kind == TEXT("event_advance") || Kind == TEXT("camp_advance") ?
                TEXT("SW_Event_Advance") : TEXT("SW_Impact_Metal_02"), Center, .45f);
        }
        else if (Kind == TEXT("victory") || Kind == TEXT("draw_game"))
        {
            for (int32 I = 0; I < 3; ++I)
            {
                const FVector Start = GroundedDeploymentPosition(Beat.Player, I, 2) + FVector(0, 0, 100);
                Shape(TEXT("Sphere"), TEXT("M_WarmLamp"), Start, Start + FVector(0, 0, 520), FVector(.16f), 1.7f, I * .08f, 80.f, 0.f, true);
            }
            if (USoundBase* Sound = OldWestSound(TEXT("SW_Match_End")))
                UGameplayStatics::PlaySound2D(this, Sound, .65f);
        }
    };
    Stage(P.Active.GetValue());
    for (const auto& Beat : P.Simultaneous) Stage(Beat);
}

void AOldWestBattlefield::UpdateActionEffects(float DeltaSeconds)
{
    auto& P = *Presentation;
    for (auto& Delivery : P.Deliveries) if (Delivery.IsValid()) Delivery->Advance(DeltaSeconds);
    for (auto& Effect : P.Effects) if (UStaticMeshComponent* Mesh = Effect.Mesh.Get())
    {
        Effect.Age += DeltaSeconds;
        const float Age = Effect.Age - Effect.Delay;
        Mesh->SetVisibility(Age >= 0.f && (Age <= Effect.Duration || !Effect.Shrink));
        if (Age < 0.f) continue;
        const float T = FMath::Clamp(Age / Effect.Duration, 0.f, 1.f);
        FVector Location = FMath::Lerp(Effect.From, Effect.To, T * T * (3.f - 2.f * T));
        Location.Z += FMath::Sin(T * PI) * Effect.Arc;
        FQuat Rotation = (Effect.Rotation + FRotator(Effect.Spin * T, Effect.Spin * T * .7f, 0)).Quaternion();
        if (Effect.FallingCloth)
        {
            // A short, bounded cloth drop with diminishing flutter. No cloth
            // collision or physics can influence the authoritative board.
            Location = FMath::Lerp(Effect.From, Effect.To, T * T * (3.f - 2.f * T));
            const float Flutter = FMath::Sin(T * PI * 4.f) * (1.f - T);
            const FQuat Lower(FVector::ForwardVector, FMath::DegreesToRadians(90.f * T + 10.f * Flutter));
            const FQuat Twist(FVector::UpVector, FMath::DegreesToRadians(12.f * Flutter));
            Rotation = Effect.Rotation.Quaternion() * Twist * Lower;
        }
        if (Effect.WheelRadius > 0.f)
            Rotation = FQuat(FVector::ForwardVector, -(Location.Y - Effect.From.Y) / Effect.WheelRadius) * Effect.Rotation.Quaternion();
        if (Effect.Hinged)
        {
            const FQuat Hinge(Effect.HingeAxis, FMath::DegreesToRadians(Effect.Spin * T));
            Location = Effect.Pivot + Hinge.RotateVector(Effect.From - Effect.Pivot);
            Rotation = Hinge * Effect.Rotation.Quaternion();
        }
        Mesh->SetWorldLocation(Location);
        Mesh->SetWorldRotation(Rotation);
        Mesh->SetWorldScale3D(Effect.Scale * (Effect.Shrink ? FMath::Max(.001f, 1.f - T * T) : 1.f));
    }
    if (!P.Active.IsSet()) return;
    auto MoveEquipment = [this, &P](const FCinematicBeat& Beat)
    {
        if (Beat.Kind != TEXT("camp_advance") && Beat.Kind != TEXT("event_advance") && Beat.Kind != TEXT("event_play") && Beat.Kind != TEXT("raid_launch") && Beat.Kind != TEXT("stampede_charge")) return;
        if (AOldWestUnit* Unit = Units.FindRef(Beat.Target); Unit && (Unit->Camp || Unit->IsEventToken()))
        {
            const float T = FMath::Clamp(P.Elapsed / FMath::Max(.1f, Beat.Duration - .1f), 0.f, 1.f);
            const FVector From = EventEquipmentOrigin(Beat);
            Unit->MoveEventEquipment(FMath::Lerp(From, Beat.After.Location, T * T * (3.f - 2.f * T)));
        }
    };
    MoveEquipment(P.Active.GetValue());
    for (const auto& Beat : P.Simultaneous) MoveEquipment(Beat);
}

void AOldWestBattlefield::BeginNextBeat()
{
    auto& P = *Presentation;
    ClearActionEffects();
    P.Simultaneous.Empty();
    P.WaitForPersonSettling = P.AllRagdollsSettled = false;
    P.SettleStableSeconds = 0.f;
    // Accepted metadata for a skipped/reconnected/unavailable generic setup
    // cannot recreate a case or become an unknown filler action.
    while (!P.Pending.IsEmpty() && (P.Pending[0].Kind == TEXT("analysis_choice") || P.Pending[0].Kind == TEXT("analysis_close")) &&
        !P.ScientistPlayback.FindRef(P.Pending[0].AnalysisSequence).IsValid())
        P.Pending.RemoveAt(0);
    if (P.Pending.IsEmpty())
    {
        P.Active.Reset();
        // A pending rule choice does not keep a cinematic busy. The public
        // analysis context survives while ordinary response controls reappear.
        P.Analysis.FinishFallbacks();
        P.FocusRevision = -1;
        P.StartedAt = 0.;
        ReconcileUnits();
        if (!RetainAnalysisChoiceView()) SetOverview();
        if (Camera)
        {
            CameraFocus = DesiredFocus;
            Camera->SetActorLocation(DesiredCamera);
            Camera->SetActorRotation((DesiredFocus - DesiredCamera).Rotation());
        }
        return;
    }
    ChoiceViewFramed = false;
    P.Active = MoveTemp(P.Pending[0]);
    P.Pending.RemoveAt(0);
    P.Elapsed = 0.f;
    P.FrameCount = 0;
    P.LastFrameSeconds = P.MaxFrameSeconds = P.EstimatedPhysicsSeconds = 0.f;
#if !UE_BUILD_SHIPPING
    P.ResetPerformanceFrames();
#endif
    P.ImpactResolved = false;
    auto& Beat = P.Active.GetValue();
    auto IsHit = [](const FCinematicBeat& B) { return B.Kind == TEXT("damage") || B.Kind == TEXT("destroy"); };
    if (IsHit(Beat) || Beat.Kind == TEXT("move"))
    {
        TSet<int32> Targets;
        Targets.Add(Beat.Target);
        // Distinct hit targets from one rule action share an impact and camera.
        // Repeated effects on one target, or intervening moves/restores, retain
        // their order. A six-target attack therefore fits one bounded shot.
        while (!P.Pending.IsEmpty() && P.Pending[0].Revision == Beat.Revision &&
            ((IsHit(Beat) && IsHit(P.Pending[0])) || (Beat.Kind == TEXT("move") && P.Pending[0].Kind == TEXT("move"))) &&
            !Targets.Contains(P.Pending[0].Target))
        {
            Targets.Add(P.Pending[0].Target);
            Beat.Duration = FMath::Max(Beat.Duration, P.Pending[0].Duration);
            P.Simultaneous.Add(MoveTemp(P.Pending[0]));
            P.Pending.RemoveAt(0);
        }
    }
    auto IsPersonDeath = [](const FCinematicBeat& B) { return B.Kind == TEXT("destroy") && !B.Before.Camp && !B.Departure; };
    P.WaitForPersonSettling = IsPersonDeath(Beat);
    for (const auto& Other : P.Simultaneous) P.WaitForPersonSettling |= IsPersonDeath(Other);
    ReconcileUnits();
    auto Prepare = [this](FCinematicBeat& B)
    {
        if (B.FinalAction)
        {
            // Only the recorded public appearance is replayed. Ordinary
            // reconciliation removes this cosmetic actor between response
            // beats and on Skip; it is never inserted into Latest.
            AOldWestUnit* Performer = Units.FindRef(B.Source);
            if (!IsValid(Performer))
            {
                Performer = GetWorld()->SpawnActor<AOldWestUnit>();
                if (Performer) Units.Add(B.Source, Performer);
            }
            if (Performer)
            {
                const auto& Frame = B.FinalActionFrame;
                Performer->Configure(Frame.Id, Frame.Side, Frame.Name, false, Frame.Punk, Frame.CardId, false, Frame.VisualId);
                Performer->SetActorLocation(Frame.Location);
                Performer->SetCondition(Frame.Damage, false, Frame.Ready);
                Performer->ResetPose();
            }
        }
        if (B.Kind == TEXT("destroy"))
        {
            CancelScientistScenes(TEXT("source_death"), B.Target, false);
            // One received snapshot can queue death and its later free
            // response together. Death must not cancel that newer context.
            Presentation->Analysis.CancelSource(B.Target, "source_death", B.Sequence);
        }
        if ((B.Kind == TEXT("analysis_choice") || B.Kind == TEXT("analysis_close")) &&
            Presentation->ScientistPlayback.FindRef(B.AnalysisSequence).IsValid()) return;
        if (B.AnalysisSequence <= 0)
        {
            if (B.Source > 0) CancelScientistScenes(TEXT("source_other_action"), B.Source, true);
            if (B.Target > 0 && B.Target != B.Source) CancelScientistScenes(TEXT("target_other_action"), B.Target, B.Kind != TEXT("destroy"));
        }
        Presentation->Analysis.Started(B.AnalysisSequence);
        if (!B.KnownTarget) return;
        AOldWestUnit* Victim = Units.FindRef(B.Target);
        if (!IsValid(Victim))
        {
            Victim = GetWorld()->SpawnActor<AOldWestUnit>();
            if (Victim) Units.Add(B.Target, Victim);
        }
        if (!Victim) return;
        if (const int32* Entrance = Presentation->DeferredEntrances.Find(B.Target); Entrance && B.Sequence >= *Entrance)
        {
            Presentation->DeferredEntrances.Remove(B.Target);
            Victim->SetActorHiddenInGame(false);
        }
        const auto& Frame = B.Before;
        if (Victim->EntityId != Frame.Id || Victim->Side != Frame.Side || Victim->GetUnitName() != Frame.Name)
        {
            if (Frame.EventToken) Victim->ConfigureEvent(Frame.Id, Frame.Side, Frame.Name, Frame.CardId);
            else Victim->Configure(Frame.Id, Frame.Side, Frame.Name, Frame.Camp, Frame.Punk, Frame.CardId, false, Frame.VisualId);
        }
        // Stage equipment at its actual path origin before the first
        // painted frame, so event play cannot jump backwards on its first tick.
        Victim->SetActorLocation(Frame.EventToken ? EventEquipmentOrigin(B) : Frame.Location);
        Victim->SetCondition(Frame.Damage, Frame.Destroyed, Frame.Ready);
        if (B.Kind == TEXT("enter") || B.Kind == TEXT("reveal_person")) Victim->ResetPose();
        const FVector Rear(0, B.Player == 0 ? 1.f : -1.f, 0);
        auto Approach = [this, Victim, &Rear](const FVector& Goal)
        {
            const float Preferred = (Victim->EntityId & 1) ? 1.f : -1.f;
            for (float Length : {230.f, 160.f, 85.f})
                for (float Side : {Preferred, -Preferred})
                {
                    const FVector Candidate = WalkGround(GetWorld(), Goal + FVector(Side * Length, 0, 0) - Rear * 65.f, Victim);
                    if (WalkSegmentClear(GetWorld(), Victim, Candidate, Goal)) return Candidate;
                }
            return Goal;
        };
        if (B.Kind == TEXT("enter") || (B.Kind == TEXT("raid_launch") && !Frame.EventToken))
            B.Duration = Victim->StageTravel(Approach(B.After.Location), B.After.Location, B.Duration - .1f) + .1f;
        else if (B.Kind == TEXT("return") || B.Departure)
            B.Duration = Victim->StageTravel(B.Before.Location, Approach(B.Before.Location), B.Duration - .1f, true) + .1f;
        else if (B.Kind == TEXT("recruit_id"))
            // Recruitment crosses the board to an already resolved legal slot.
            // Do not detour around scenery via the general camp walk graph.
            B.Duration = Victim->StageTravel(B.Before.Location, B.After.Location, B.Duration - .1f, false, true) + .1f;
        else if (B.Kind == TEXT("move") || B.Kind == TEXT("hospital_id") ||
            (B.Kind == TEXT("event_advance") && !Frame.EventToken))
            B.Duration = Victim->StageTravel(B.Before.Location, B.After.Location, B.Duration - .1f) + .1f;
        // Configure/ResetPose can restore visibility. An earlier log referring
        // to this public object must not reveal a still-pending entrance.
        if (Presentation->DeferredEntrances.Contains(B.Target)) Victim->SetActorHiddenInGame(true);
    };
    Prepare(Beat);
    for (auto& Other : P.Simultaneous)
    {
        Prepare(Other);
        Beat.Duration = FMath::Max(Beat.Duration, Other.Duration);
    }

    UpdateCinematicLODs();
    const bool ScientistStarted = StartScientistBeat();
    if (!ScientistStarted && (Beat.Kind == TEXT("analysis_choice") || Beat.Kind == TEXT("analysis_close")))
    {
        P.Analysis.FinishFallbacks(); P.Active.Reset(); BeginNextBeat(); return;
    }
    TSet<int32> AnimatedSources;
    auto Attack = [this, &AnimatedSources, &IsHit](const FCinematicBeat& B)
    {
        AOldWestUnit* Source = Units.FindRef(B.Source);
        AOldWestUnit* Victim = Units.FindRef(B.Target);
        if (!AnimatedSources.Contains(B.Source) && IsValid(Source) && IsValid(Victim) && Source != Victim &&
            Source->Side != Victim->Side && !Source->Camp && !Source->IsEventToken() && !Source->IsVisuallyDead() && IsHit(B))
        {
            Source->AimAt(Victim->GetPresentationFocus());
            Source->PlayAction(TEXT("attack"));
            AnimatedSources.Add(B.Source);
        }
    };
    Attack(Beat);
    for (const auto& Other : P.Simultaneous) Attack(Other);
    StageActionEffects(false);
    FocusAction(Beat.Source, Beat.Target, Beat.Kind, Beat.Revision);
}

void AOldWestBattlefield::RecordShotCompletion(const TCHAR* Reason)
{
#if !UE_BUILD_SHIPPING
    auto& P = *Presentation;
    if (!P.Active.IsSet()) return;
    J Record = {{"reason", std::string(TCHAR_TO_UTF8(Reason))}, {"sequence", P.Active->Sequence},
        {"match_id", std::string(TCHAR_TO_UTF8(*P.MatchId))},
        {"kind", std::string(TCHAR_TO_UTF8(*P.Active->Kind))}, {"elapsed", P.Elapsed},
        {"waited_for_settling", P.WaitForPersonSettling}, {"stable_seconds", P.SettleStableSeconds},
        {"all_ragdolls_settled", P.AllRagdollsSettled}, {"targets", J::array()}};
    AddAbilityPresentationDebug(Record, P.Active.GetValue());
    AddQueueTransitionDebug(Record, P.Active.GetValue());
    Record["frame_timing"] = {{"frames", P.FrameCount}, {"last_delta_seconds", P.LastFrameSeconds},
        {"maximum_delta_seconds", P.MaxFrameSeconds}, {"estimated_physics_seconds", P.EstimatedPhysicsSeconds}};
    if (ProfilePresentation()) Record["frame_performance"] = P.PerformanceDebug();
    auto Capture = [this, &Record](const FCinematicBeat& Beat)
    {
        J Target = {{"target", Beat.Target}, {"sequence", Beat.Sequence},
            {"kind", std::string(TCHAR_TO_UTF8(*Beat.Kind))}, {"camp", Beat.Before.Camp},
            {"ragdoll", false}, {"physics", nullptr}};
        AddAbilityPresentationDebug(Target, Beat);
        AddQueueTransitionDebug(Target, Beat);
        if (const AOldWestUnit* Unit = Units.FindRef(Beat.Target); IsValid(Unit))
        {
            Target["ragdoll"] = Unit->IsRagdoll();
            Target["physics"] = J::parse(TCHAR_TO_UTF8(*Unit->GetPhysicsDebug()));
        }
        Record["targets"].push_back(MoveTemp(Target));
    };
    Capture(P.Active.GetValue());
    for (const auto& Other : P.Simultaneous) Capture(Other);
    P.CompletionHistory.push_back(MoveTemp(Record));
    if (P.CompletionHistory.size() > 8) P.CompletionHistory.erase(P.CompletionHistory.begin());
#endif
}

void AOldWestBattlefield::ResolveImpact()
{
    auto& P = *Presentation;
    if (!P.Active.IsSet() || P.ImpactResolved) return;
    P.ImpactResolved = true;
    if (IsScientistBeat()) return;
    StageActionEffects(true);
    auto Resolve = [this](const FCinematicBeat& Beat)
    {
        AOldWestUnit* Victim = Units.FindRef(Beat.Target);
        if (!IsValid(Victim)) return;
        // The removal is already authoritative. Keep its cosmetic withdrawal
        // alive until it leaves, then ordinary reconciliation removes the actor.
        if (Beat.Departure) return;
        AOldWestUnit* Source = Units.FindRef(Beat.Source);
        const FVector Direction = Source && Source != Victim ? Victim->GetActorLocation() - Source->GetActorLocation() :
            FVector(0, Victim->Side == 0 ? 1.f : -1.f, 0);
        const auto& Frame = Beat.After;
        if (Beat.Kind == TEXT("reveal_person"))
        {
            if (Victim->Side != Frame.Side || Victim->GetUnitName() != Frame.Name)
                Victim->Configure(Frame.Id, Frame.Side, Frame.Name, Frame.Camp, Frame.Punk, Frame.CardId, false, Frame.VisualId);
            Victim->SetActorLocation(Frame.Location);
            Victim->ResetPose();
        }
        Victim->SetCondition(Frame.Damage, Frame.Destroyed, Frame.Ready);
        const bool IllnessWound = Beat.Kind == TEXT("damage") && Source && Source->IsEventToken()
            && Source->GetVisualCardId() == TEXT("cholera");
        if (!IllnessWound && (Beat.Kind == TEXT("damage") || Beat.Kind == TEXT("destroy") || Beat.Kind == TEXT("restore")))
            Victim->PlayAction(Beat.Kind, Direction);
    };
    Resolve(P.Active.GetValue());
    for (const auto& Other : P.Simultaneous) Resolve(Other);
    // Enter, move and restore can reset a pose during the impact. Keep the
    // active shot at full detail after those resets as well as at its start.
    UpdateCinematicLODs();
}

bool AOldWestBattlefield::IsShotObstructed(const FVector& Focus, const FVector& Position, int32 Target, FString* Detail) const
{
    if (Detail) Detail->Empty();
    // Imported camps use complex-as-simple collision. Trace their actual
    // triangles: a ruined tower's broad bounds contain a great deal of air.
    FCollisionQueryParams PointParams(SCENE_QUERY_STAT(OldWestCinematicCamera), true);
    if (GetWorld()->OverlapBlockingTestByChannel(Position, FQuat::Identity, ECC_Camera,
        FCollisionShape::MakeSphere(45.f), PointParams))
    {
        if (Detail) *Detail = TEXT("camera sphere overlaps blocking scenery");
        return true;
    }
    if (Presentation->EffectFraming || IsAnalysisChoiceFramed())
        for (const auto& Pair : Units)
        {
            const AOldWestUnit* Other = Pair.Value;
            if (!IsValid(Other) || Other->Camp || Other->IsEventToken() || Other->IsHidden() ||
                (Presentation->Active.IsSet() && (Pair.Key == Presentation->Active->Target || Pair.Key == Presentation->Active->Source)) ||
                (IsAnalysisChoiceFramed() && Pair.Key == ChoiceViewSource)) continue;
            // Animated people intentionally have no picking/physics collision.
            // Their real rendered bounds still must not mask a service shot.
            const FBox Bounds = Other->GetVisualBounds().ExpandBy(6.f);
            if (FMath::LineBoxIntersection(Bounds, Focus, Position, Position - Focus))
            {
                if (Detail) *Detail = FString::Printf(TEXT("effect focus blocked by person %d"), Pair.Key);
                return true;
            }
        }
    auto Hidden = [this, &Position, Detail](int32 Id, const FVector& Fallback)
    {
        const AOldWestUnit* Unit = Units.FindRef(Id);
        FCollisionQueryParams SightParams(SCENE_QUERY_STAT(OldWestCinematicVisibility), true);
        TArray<FVector> Points;
        Points.Add(Unit ? Unit->GetPresentationFocus() : Fallback);
        if (Unit)
        {
            SightParams.AddIgnoredActor(Unit);
            // A clear ray to the pelvis can still leave a head or both legs
            // behind machinery. Check the actual animated body extremities,
            // slightly above ground contact to avoid tracing into the floor.
            if (!Unit->Camp && !Unit->IsEventToken() && Unit->Body->GetSkeletalMeshAsset())
                for (FName Bone : {FName(TEXT("Head")), FName(TEXT("LeftFoot")), FName(TEXT("RightFoot"))})
                    if (Unit->Body->GetBoneIndex(Bone) != INDEX_NONE)
                        Points.Add(Unit->Body->GetSocketLocation(Bone) + FVector(0, 0, 8.f));
        }
        FHitResult Hit;
        for (const FVector& Point : Points)
        {
            if (GetWorld()->LineTraceSingleByChannel(Hit, Point, Position, ECC_Camera, SightParams))
            {
                if (Detail) *Detail = FString::Printf(TEXT("subject %d at %s blocked by %s / %s at %s"),
                    Id, *Point.ToString(), *GetNameSafe(Hit.GetActor()), *GetNameSafe(Hit.GetComponent()), *Hit.ImpactPoint.ToString());
                return true;
            }
            if (Unit && !Unit->Camp && !Unit->IsEventToken())
                for (const auto& Pair : Units)
                {
                    const AOldWestUnit* Other = Pair.Value;
                    if (!IsValid(Other) || Other == Unit || Other->Camp || Other->IsEventToken() || Other->IsHidden()) continue;
                    // Deployed people have no camera-query collision. Their
                    // silhouettes can still hide a falling or walking subject,
                    // especially another person in the same battlefield lane.
                    const FBox Bounds = Other->GetVisualBounds().ExpandBy(6.f);
                    if (Bounds.IsValid && FMath::LineBoxIntersection(Bounds, Point, Position, Position - Point))
                    {
                        if (Detail) *Detail = FString::Printf(TEXT("subject %d at %s blocked by person %d bounds %s; probe inside=%d"),
                            Id, *Point.ToString(), Pair.Key, *Bounds.ToString(), Bounds.IsInsideOrOn(Point));
                        return true;
                    }
                }
        }
        return false;
    };
    if (Presentation->Active.IsSet() && Presentation->Active->Kind == TEXT("turn_start"))
    {
        // The crew's aggregate center may be inside its middle camp. Reuse
        // real subject rays so each camp ignores itself but not other scenery.
        // No broad camp-box obstruction test or private card data is involved.
        bool HasCamp = false;
        for (const auto& Pair : Units)
        {
            const AOldWestUnit* Unit = Pair.Value;
            if (IsValid(Unit) && Unit->Side == Presentation->Active->Player && Unit->Camp
                && !Unit->IsPreviewOnly() && !Unit->IsHidden() && Unit->GetVisualBounds().IsValid) HasCamp = true;
        }
        if (HasCamp)
        {
            for (const auto& Pair : Units)
            {
                const AOldWestUnit* Unit = Pair.Value;
                if (!IsValid(Unit) || Unit->Side != Presentation->Active->Player || Unit->IsPreviewOnly()
                    || Unit->IsHidden() || Unit->IsEventToken() || (!Unit->Camp && Unit->IsVisuallyDead())
                    || !Unit->GetVisualBounds().IsValid) continue;
                if (Hidden(Pair.Key, Focus)) return true;
            }
            for (const FActionEffect& Effect : Presentation->Effects)
                if (const UStaticMeshComponent* Mesh = Effect.Mesh.Get(); IsValid(Mesh) && Mesh->GetStaticMesh() && !Effect.Shrink)
                {
                    if (Hidden(INDEX_NONE, Mesh->Bounds.Origin + FVector(0, 0, 4))) return true;
                    if (Effect.Hinged && Hidden(INDEX_NONE, Effect.Pivot + FVector(0, 0, 4))) return true;
                }
            return false;
        }
    }
    if (IsAnalysisChoiceFramed())
        if (const UOldWestScientistPlayback* Playback = Presentation->ScientistPlayback.FindRef(ChoiceViewSequence).Get(); IsValid(Playback))
        {
            if (Playback->IsCaseLidObstructing(Position) || Hidden(ChoiceViewSource, Focus)) return true;
            for (const FVector& Point : Playback->GetVisibilityPoints())
                if (Hidden(INDEX_NONE, Point)) return true;
        }
    if (Presentation->EffectFraming)
    {
        // Effect framing selects a combined focus, but it still presents real
        // people. INDEX_NONE must not bypass their head/pelvis/foot checks.
        TSet<int32> People;
        auto AddPeople = [this, &People](const FCinematicBeat& Beat)
        {
            for (int32 Id : {Beat.Source, Beat.Target})
                if (const AOldWestUnit* Unit = Units.FindRef(Id); IsValid(Unit) && !Unit->IsHidden()
                    && !Unit->IsPreviewOnly() && !Unit->Camp && !Unit->IsEventToken()) People.Add(Id);
        };
        if (Presentation->Active.IsSet()) AddPeople(Presentation->Active.GetValue());
        for (const FCinematicBeat& Beat : Presentation->Simultaneous) AddPeople(Beat);
        for (int32 Id : People) if (Hidden(Id, Focus)) return true;
        for (const auto& Delivery : Presentation->Deliveries) if (Delivery.IsValid())
            for (const FVector& Point : Delivery->GetVisibilityPoints())
                if (Hidden(INDEX_NONE,Point)) return true;

        // Probe actual persistent equipment parts, not the empty corners of a
        // combined camp box. Transient sparks/debris do not choose the shot.
        // Camera-channel rays still hit real triangles of hollow/ruined camps.
        for (const FActionEffect& Effect : Presentation->Effects)
            if (const UStaticMeshComponent* Mesh = Effect.Mesh.Get(); IsValid(Mesh)
                && Mesh->GetStaticMesh() && !Effect.Shrink)
            {
                const FVector Lift(0, 0, 4.f); // Keep thin rail/base probes off the ground surface.
                if (Hidden(INDEX_NONE, Mesh->Bounds.Origin + Lift)) return true;
                if (!Effect.Hinged && !Effect.From.Equals(Effect.To, 1.f))
                {
                    // A fixed delivery view must keep both ends of the cart's
                    // authored translation visible before the cart departs.
                    const FVector LocalCenter = Mesh->GetStaticMesh()->GetBoundingBox().GetCenter() * Effect.Scale;
                    const FVector CenterOffset = Effect.Rotation.RotateVector(LocalCenter);
                    if (Hidden(INDEX_NONE, Effect.From + CenterOffset + Lift)
                        || Hidden(INDEX_NONE, Effect.To + CenterOffset + Lift)) return true;
                }
            }
        if (Presentation->Active.IsSet() && Presentation->Active->ScientistScene)
            if (const UOldWestScientistPlayback* Playback = Presentation->ScientistPlayback.FindRef(Presentation->Active->AnalysisSequence).Get(); IsValid(Playback))
            {
                if (Playback->IsCaseLidObstructing(Position)) return true;
                for (const FVector& Point : Playback->GetVisibilityPoints())
                    if (Hidden(INDEX_NONE, Point)) return true;
            }
        return Hidden(INDEX_NONE, Focus);
    }
    if (Target != 0) return Hidden(Target, Focus);
    // The group center is abstract: each displayed target needs a visible
    // silhouette, including figures removed by the authoritative snapshot.
    if (Presentation->Active.IsSet() && Hidden(Presentation->Active->Target, Focus)) return true;
    for (const auto& Beat : Presentation->Simultaneous) if (Hidden(Beat.Target, Focus)) return true;
    return false;
}

FVector AOldWestBattlefield::ChooseShotPosition(const FVector& Focus, const FVector& Preferred, int32 Target) const
{
    if (!IsShotObstructed(Focus, Preferred, Target)) return Preferred;
    const FVector Offset = Preferred - Focus;
    const float Distance = FMath::Max(Offset.Size2D(), 600.f);
    const FVector Direction = Offset.GetSafeNormal2D();
    // Keep the intended side if clear, then try neighboring angles before
    // elevating the shot. Never interpolate a camera through an obstruction.
    const float Angles[] = {0.f, 45.f, -45.f, 90.f, -90.f, 135.f, -135.f, 180.f};
    const float Heights[] = {FMath::Max(Offset.Z, 160.f), 350.f, 650.f, 1100.f};
    for (float Height : Heights) for (float Angle : Angles)
    {
        const FVector Candidate = Focus + Direction.RotateAngleAxis(Angle, FVector::UpVector) * Distance + FVector(0, 0, Height);
        if (!IsShotObstructed(Focus, Candidate, Target)) return Candidate;
    }
    // If a figure is completely enclosed by scenery, a high local view is
    // still bounded and outside the structures; tactical controls remain live.
    return Focus + FVector(-900.f, Seat == 0 ? 900.f : -900.f, 1800.f);
}

void AOldWestBattlefield::FocusAction(int32 Source, int32 Target, const FString& Kind, int32 Revision)
{
    auto& P = *Presentation;
    AOldWestUnit* Victim = Units.FindRef(Target);
    AOldWestUnit* Actor = Units.FindRef(Source);
    if (!P.Active.IsSet()) return;
    const FCinematicBeat& Primary = P.Active.GetValue();
    const bool Finale = Kind == TEXT("victory") || Kind == TEXT("draw_game") || Kind == TEXT("turn_start");
    FBox TurnCrewBounds(ForceInit);
    FVector TurnCrewFront = FVector::ZeroVector;
    if (Kind == TEXT("turn_start") && !P.EffectFraming)
    {
        int32 CampCount = 0;
        for (const auto& Pair : Units)
        {
            const AOldWestUnit* Unit = Pair.Value;
            if (!IsValid(Unit) || Unit->Side != Primary.Player || Unit->IsPreviewOnly() || Unit->IsHidden()
                || Unit->IsEventToken() || (!Unit->Camp && Unit->IsVisuallyDead())) continue;
            const FBox Bounds = Unit->GetVisualBounds();
            if (!Bounds.IsValid) continue;
            TurnCrewBounds += Bounds;
            if (Unit->Camp)
            {
                ++CampCount;
                TurnCrewFront += Unit->CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0, -1, 0)).GetSafeNormal2D();
            }
        }
        if (CampCount == 0) TurnCrewBounds = FBox(ForceInit);
        else
        {
            // Turn-start service flags stand beyond their camp's front edge.
            // Their meshes belong to the action, not the camp visual bounds.
            for (const FActionEffect& Effect : P.Effects)
                if (const UStaticMeshComponent* Mesh = Effect.Mesh.Get(); IsValid(Mesh) && Mesh->GetStaticMesh() && !Effect.Shrink)
                {
                    TurnCrewBounds += Mesh->Bounds.GetBox();
                    if (Effect.Hinged)
                    {
                        const double Radius = Mesh->Bounds.BoxExtent.Size() + FVector::Distance(Mesh->Bounds.Origin, Effect.Pivot);
                        TurnCrewBounds += FBox(Effect.Pivot - FVector(Radius), Effect.Pivot + FVector(Radius));
                    }
                }
            // Actual flag/foliage/fire bounds are already included. Keep a
            // small additional margin for their restrained local idle loops.
            TurnCrewBounds = TurnCrewBounds.ExpandBy(FVector(24, 24, 40));
            TurnCrewFront = TurnCrewFront.GetSafeNormal2D();
            if (TurnCrewFront.IsNearlyZero()) TurnCrewFront = FVector(0, Primary.Player == 0 ? -1.f : 1.f, 0);
        }
    }
    FBox Group(ForceInit), GroupVisualBounds(ForceInit);
    if (Victim && Victim->GetVisualBounds().IsValid) GroupVisualBounds += Victim->GetVisualBounds();
    Group += Victim ? Victim->GetPresentationFocus() : Primary.Before.Location + FVector(0, 0, 65);
    if (Kind == TEXT("move")) Group += Primary.After.Location + FVector(0, 0, 110);
    TSet<int32> Targets;
    Targets.Add(Target);
    for (const auto& Beat : P.Simultaneous)
        if (AOldWestUnit* Unit = Units.FindRef(Beat.Target))
        {
            Group += Unit->GetPresentationFocus(); Targets.Add(Beat.Target);
            if (Unit->GetVisualBounds().IsValid) GroupVisualBounds += Unit->GetVisualBounds();
            if (Beat.Kind == TEXT("move")) Group += Beat.After.Location + FVector(0, 0, 110);
        }
    P.FocusRevision = Revision;
    P.GroupShot = Targets.Num() > 1 || Finale;
    if (P.EffectFraming && P.EffectFrameBounds.IsValid)
    {
        DesiredFocus = P.EffectFrameBounds.GetCenter();
        const float Distance = FMath::Max(430.f, static_cast<float>(P.EffectFrameBounds.GetExtent().Size()) * 2.5f);
        const FVector Direction = P.EffectViewDirection.IsNearlyZero() ?
            FVector(-.65f, Seat == 0 ? 1.f : -1.f, 0).GetSafeNormal() : P.EffectViewDirection;
        const bool BonusGlassShot = P.Effects.ContainsByPredicate([this](const FActionEffect& Effect)
        {
            const UStaticMeshComponent* Mesh = Effect.Mesh.Get();
            return BonusWhiskeyMesh && Mesh && Mesh->GetStaticMesh() == BonusWhiskeyMesh;
        });
        // Back the clear tumbler with the wooden barrel head, including on snow.
        // Keep a similar focus distance and leave every other effect shot alone.
        DesiredCamera = DesiredFocus + Direction * Distance * (BonusGlassShot ? .20f : 1.f)
            + FVector(0, 0, Distance * (BonusGlassShot ? 1.04f : .42f));
    }
    else if (TurnCrewBounds.IsValid)
    {
        DesiredFocus = TurnCrewBounds.GetCenter();
        // Face the new active crew, independent of the viewing player's seat.
        // A small three-quarter angle reveals depth without hiding a flank.
        DesiredCamera = DesiredFocus + TurnCrewFront.RotateAngleAxis(15.f, FVector::UpVector) * 1000.f + FVector(0, 0, 700.f);
    }
    else if (Finale)
    {
        DesiredFocus = FVector(0, 2500, 200);
        DesiredCamera = DesiredFocus + FVector(-1500, Seat == 0 ? 2000 : -2000, 1400);
    }
    else if (P.GroupShot)
    {
        DesiredFocus = GroupVisualBounds.IsValid ? GroupVisualBounds.GetCenter() : Group.GetCenter();
        const float Distance = FMath::Clamp(Group.GetExtent().GetMax() * 2.2f + 900.f, 1050.f, 3200.f);
        DesiredCamera = DesiredFocus + FVector(-0.6f, Seat == 0 ? 1.f : -1.f, 0.f).GetSafeNormal() * Distance + FVector(0, 0, Distance * 0.6f);
    }
    else
    {
        DesiredFocus = Victim ? Victim->GetPresentationFocus() : Primary.Before.Location + FVector(0, 0, 65);
        float Distance = Victim ? 600.f : 370.f;
        if (Victim && Victim->Camp && Victim->GetVisualBounds().IsValid)
            Distance = FMath::Max(1000.f, static_cast<float>(Victim->GetVisualBounds().GetExtent().Size()) * 4.f);
        const bool HerdShot = Victim && Victim->IsRaider() && Victim->IsEventToken();
        if (HerdShot)
            Distance = FMath::Max(1200.f, static_cast<float>(Victim->GetVisualBounds().GetExtent().Size()) * 4.f);
        const FVector Origin = Actor && Actor != Victim ? Actor->GetActorLocation() : DesiredFocus + FVector(-400, Seat == 0 ? 500 : -500, 0);
        FVector Direction = (Origin - DesiredFocus).GetSafeNormal2D();
        if (Victim && Victim->Camp)
            Direction = Victim->CampVisuals->GetComponentTransform().TransformVectorNoScale(FVector(0, -1, 0)).RotateAngleAxis(25.f, FVector::UpVector).GetSafeNormal2D();
        else if (Victim && (Primary.Kind == TEXT("reveal_person") ||
            (Primary.Kind == TEXT("ability") && Primary.AbilityIndex == 101 && Victim->Body &&
             Victim->Body->GetSkeletalMeshAsset() && Victim->Body->GetSkeletalMeshAsset()->GetPathName() ==
                TEXT("/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter"))))
            // Crew face local +Y. Show the stranger's covered face and the
            // public identity from the same front three-quarter view, for
            // either seat; the ordinary obstruction search still applies.
            Direction = Victim->Body->GetComponentTransform().TransformVectorNoScale(FVector(0, 1, 0))
                .RotateAngleAxis(25.f, FVector::UpVector).GetSafeNormal2D();
        if (Direction.IsNearlyZero()) Direction = FVector(-0.6f, Seat == 0 ? 1.f : -1.f, 0).GetSafeNormal();
        if (HerdShot) Direction = Direction.RotateAngleAxis(25.f, FVector::UpVector);
        DesiredCamera = DesiredFocus + Direction * Distance + FVector(0, 0,
            HerdShot ? Distance * .5f : Victim && Victim->Camp ? Distance * 0.22f : Victim ? 160.f : 135.f);
    }
    const FBox FramingBounds = TurnCrewBounds.IsValid ? TurnCrewBounds :
        (P.GroupShot && !Finale && !P.EffectFraming ? GroupVisualBounds : FBox(ForceInit));
    if (FramingBounds.IsValid)
    {
        const UCineCameraComponent* Lens = Camera ? Camera->GetCineCameraComponent() : nullptr;
        const double FocalLength = Lens ? FMath::Max(1.f, Lens->CurrentFocalLength) : 32.f;
        const double TanHorizontal = (Lens ? Lens->Filmback.SensorWidth : 36.f) / (2. * FocalLength);
        const double TanVertical = (Lens ? Lens->Filmback.SensorHeight : 20.25f) / (2. * FocalLength);
        auto FitSubjects = [this, &FramingBounds, TanHorizontal, TanVertical](const FVector& Position)
        {
            const FVector Away = (Position - DesiredFocus).GetSafeNormal();
            const FVector Forward = -Away;
            const FRotator ViewRotation = Forward.Rotation();
            const FVector Right = ViewRotation.RotateVector(FVector::RightVector);
            const FVector Up = ViewRotation.RotateVector(FVector::UpVector);
            double Distance = FMath::Max(300., FVector::Distance(Position, DesiredFocus));
            for (int32 X : {0, 1}) for (int32 Y : {0, 1}) for (int32 Z : {0, 1})
            {
                const FVector Corner(X ? FramingBounds.Max.X : FramingBounds.Min.X,
                    Y ? FramingBounds.Max.Y : FramingBounds.Min.Y, Z ? FramingBounds.Max.Z : FramingBounds.Min.Z);
                const FVector Offset = Corner - DesiredFocus;
                const double DepthOffset = FVector::DotProduct(Offset, Forward);
                // 6% horizontal margins and 13% top/bottom margins reserve
                // space for flags and the unchanged lower cinematic caption.
                Distance = FMath::Max(Distance, FMath::Abs(FVector::DotProduct(Offset, Right)) / FMath::Max(.01, TanHorizontal * .88) - DepthOffset);
                Distance = FMath::Max(Distance, FMath::Abs(FVector::DotProduct(Offset, Up)) / FMath::Max(.01, TanVertical * .74) - DepthOffset);
                Distance = FMath::Max(Distance, 80. - DepthOffset);
            }
            return DesiredFocus + Away * Distance;
        };
        DesiredCamera = FitSubjects(DesiredCamera);
        // Existing obstacle candidates can change view direction. Refit their
        // actual returned direction and recheck any outward move; never assume
        // that an empty aggregate-box corner certifies a visible camp.
        for (int32 Attempt = 0; Attempt < 3; ++Attempt)
        {
            DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, 0);
            DesiredCamera = FitSubjects(DesiredCamera);
            if (!IsShotObstructed(DesiredFocus, DesiredCamera, 0)) break;
        }
        // The existing obstruction telemetry retains an impossible-view
        // failure; this bounded fit does not suppress or relabel that result.
    }
    else
    DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, P.EffectFraming ? INDEX_NONE : P.GroupShot ? 0 : Target);
    P.ShotOffset = DesiredCamera - DesiredFocus;
    // Deliberate cuts avoid flying the camera through buildings between lanes.
    if (Camera)
    {
        CameraFocus = DesiredFocus;
        Camera->SetActorLocation(DesiredCamera);
        Camera->SetActorRotation((DesiredFocus - DesiredCamera).Rotation());
    }
    UpdateShotFocus();
}

FString AOldWestBattlefield::GetCinematicCaption() const
{
    if (!Presentation->Active.IsSet()) return FString();
    const FCinematicBeat& Beat = Presentation->Active.GetValue();
    if (!Presentation->Simultaneous.IsEmpty())
    {
        TArray<FString> Names;
        Names.Add(Beat.Before.Name);
        Names.Add(Presentation->Simultaneous[0].Before.Name);
        FString Label = FString::Join(Names, TEXT(" + "));
        if (Presentation->Simultaneous.Num() > 1)
            Label += FString::Printf(TEXT(" + %d more"), Presentation->Simultaneous.Num() - 1);
        return Label + (Beat.Kind == TEXT("move") ? TEXT(" reposition") : TEXT(" struck"));
    }
    const FString& Name = Beat.Kind == TEXT("reveal_person") ? Beat.After.Name : Beat.Before.Name;
    if (Beat.ScientistScene)
    {
        if (Beat.Kind == TEXT("analysis_choice"))
        {
            const J Context = Presentation->Analysis.Get(Beat.AnalysisSequence);
            return Name + (!Context.is_null() && Context.value("selection", std::string()) == "skip" ? TEXT(" closes the analysis") : TEXT(" processes the selected sample"));
        }
        return Name + TEXT(" inspects the recovered samples");
    }
    if (Beat.Departure) return Name + TEXT(" is run out of town");
    if (Beat.Kind == TEXT("destroy")) return Name + (Beat.Before.Camp ? TEXT(" collapses") : TEXT(" falls"));
    if (Beat.Kind == TEXT("damage")) return Name + TEXT(" takes a hit");
    if (Beat.Kind == TEXT("restore")) return Name + TEXT(" patched up");
    if (Beat.Kind == TEXT("enter")) return Name + TEXT(" enters the fight");
    if (Beat.Kind == TEXT("return")) return Name + TEXT(" withdraws");
    if (Beat.Kind == TEXT("move")) return Name + TEXT(" moves");
    if (Beat.Kind == TEXT("reveal_person")) return Name + TEXT(" revealed");
    if (Beat.Kind == TEXT("recruit_id")) return Name + TEXT(" joins the other outfit");
    if (Beat.Kind == TEXT("hospital_id")) return Name + TEXT(" evacuated to field care");
    if (Beat.Kind == TEXT("raid_launch")) return TEXT("Stampede approaches");
    if (Beat.Kind == TEXT("stampede_charge")) return TEXT("Stampede charges the chosen holding");
    if (Beat.Kind == TEXT("draw_card")) return FString::Printf(TEXT("Supplies secured · %d card%s"), Beat.Count, Beat.Count == 1 ? TEXT("") : TEXT("s"));
    if (Beat.Kind == TEXT("water"))
    {
        if (IsNativeVisual(Units.FindRef(Beat.Source)) || IsNativeVisual(Units.FindRef(Beat.Target)))
            return TEXT("Supplies secured");
        return Beat.Detail.IsEmpty() ? TEXT("Round on the house") : FString::Printf(TEXT("%d whiskey delivered"), Beat.Count);
    }
    if (Beat.Kind == TEXT("store_water")) return TEXT("Whiskey stowed for later");
    if (Beat.Kind == TEXT("turn_start")) return Beat.Player == Seat ? TEXT("Your watch begins") : TEXT("The opposing watch begins");
    if (Beat.Kind == TEXT("junk")) return TEXT("Hocked ")+(Beat.Detail.IsEmpty()?Name:Beat.Detail);
    if (Beat.Kind == TEXT("discard") || Beat.Kind == TEXT("reveal_discard")) return TEXT("Supplies discarded");
    if (Beat.Kind == TEXT("reshuffle")) return TEXT("The supply line is replenished");
    if (Beat.Kind == TEXT("event_play")) return Name.IsEmpty() ? TEXT("Trouble played") : Name + TEXT(" played");
    if (Beat.Kind == TEXT("event_advance"))
    {
        const FString Operation = QueueOperationName(Name);
        return Operation + (Beat.HasQueueTransition && Beat.QueueToSlot > Beat.QueueFromSlot ? TEXT(" is delayed") : TEXT(" advances"));
    }
    if (Beat.Kind == TEXT("camp_advance")) return Name + TEXT(" pushes forward");
    if (Beat.Kind == TEXT("event_resolve")) return (Name.IsEmpty()?Beat.Detail:Name) + TEXT(" resolves");
    if (Beat.Kind == TEXT("ability") && Beat.FinalAction) return Name + TEXT(" · last moments");
    if (Beat.Kind == TEXT("ability")) return Name + (Beat.Detail.IsEmpty() ? TEXT(" prepares an action") : TEXT(" · ") + Beat.Detail);
    if (Beat.Kind == TEXT("expose_all")) return TEXT("Cover is stripped away");
    if (Beat.Kind == TEXT("remove_ruin")) return TEXT("The burned-out position is cleared");
    if (Beat.Kind == TEXT("victory")) return Beat.Player == Seat ? TEXT("The territory is yours") : TEXT("Your holding has fallen");
    if (Beat.Kind == TEXT("draw_game")) return TEXT("Both forces are exhausted");
    return TEXT("The battlefield changes");
}

FString AOldWestBattlefield::GetCinematicDebug() const
{
#if !UE_BUILD_SHIPPING
    const auto& P = *Presentation;
    J Result = {{"busy", IsCinematicBusy()}, {"pending", P.Pending.Num()}, {"impact_resolved", P.ImpactResolved},
        {"elapsed", P.Elapsed}, {"skipped_beats", P.SkippedBeats}, {"last_sequence", P.LastSequence}, {"group_shot", P.GroupShot},
        {"diagnostic_fall_hold", DiagnosticFallHold()}};
    Result["presentation_policy"] = "all public action beats retained until completion or explicit Skip";
    Result["scientist_analysis"] = P.Analysis.Debug();
    Result["scientist_analysis"]["mode"] = "public_directed_playback_with_explicit_fallback";
    Result["scientist_analysis"]["bespoke_assets_enabled"] = true;
    Result["scientist_analysis"]["fallback_reason"] = "Per-context fallback is explicit; native visual acceptance is separate";
    Result["scientist_analysis"]["choice_view"] = {{"available", HasAnalysisChoiceView()},
        {"framed", IsAnalysisChoiceFramed()}, {"analysis_sequence", ChoiceViewSequence}, {"source", ChoiceViewSource},
        {"dismissed_sequence", DismissedChoiceViewSequence},
        {"camera", {ChoiceViewPosition.X, ChoiceViewPosition.Y, ChoiceViewPosition.Z}},
        {"focus", {ChoiceViewFocus.X, ChoiceViewFocus.Y, ChoiceViewFocus.Z}}};
    Result["scientist_analysis"]["playbacks"] = J::array();
    for (const auto& Pair : P.ScientistPlayback)
        if (const UOldWestScientistPlayback* Playback = Pair.Value.Get(); IsValid(Playback))
            Result["scientist_analysis"]["playbacks"].push_back(J::parse(TCHAR_TO_UTF8(*Playback->GetDebugJson())));
    Result["effect_framing"] = P.EffectFraming;
    Result["effect_view_direction"] = {P.EffectViewDirection.X, P.EffectViewDirection.Y, P.EffectViewDirection.Z};
    Result["service_layout_failures"] = P.ServiceLayoutFailures;
    Result["service_layouts"] = J::array();
    for (const FBox& Bounds : P.ServiceLayouts)
        Result["service_layouts"].push_back({{"min", {Bounds.Min.X, Bounds.Min.Y, Bounds.Min.Z}},
            {"max", {Bounds.Max.X, Bounds.Max.Y, Bounds.Max.Z}}});
    Result["action_effects"] = J::array();
    for (const auto& Effect : P.Effects) if (const UStaticMeshComponent* Mesh = Effect.Mesh.Get())
    {
        const FVector Location = Mesh->GetComponentLocation();
        const FBox EffectBounds = Mesh->Bounds.GetBox();
        const FVector EffectScale = Mesh->GetComponentScale();
        J Materials = J::array();
        for (int32 Slot = 0; Slot < Mesh->GetNumMaterials(); ++Slot)
            Materials.push_back(Mesh->GetMaterial(Slot) ?
                std::string(TCHAR_TO_UTF8(*Mesh->GetMaterial(Slot)->GetPathName())) : std::string());
        Result["action_effects"].push_back({{"visible", Mesh->IsVisible()}, {"age", Effect.Age},
            {"materials", Materials},
            {"mesh", Mesh->GetStaticMesh() ? std::string(TCHAR_TO_UTF8(*Mesh->GetStaticMesh()->GetPathName())) : std::string()},
            {"scale", {EffectScale.X,EffectScale.Y,EffectScale.Z}},
            {"bounds", {{EffectBounds.Min.X, EffectBounds.Min.Y, EffectBounds.Min.Z}, {EffectBounds.Max.X, EffectBounds.Max.Y, EffectBounds.Max.Z}}},
            {"hinge_pivot", {Effect.Pivot.X, Effect.Pivot.Y, Effect.Pivot.Z}},
            {"duration", Effect.Duration}, {"location", {Location.X, Location.Y, Location.Z}},
            {"wheel_radius_cm", Effect.WheelRadius}, {"hinged", Effect.Hinged},
            {"falling_cloth", Effect.FallingCloth},
            {"collision_enabled", static_cast<int32>(Mesh->GetCollisionEnabled())}});
    }
    Result["deliveries"]=J::array();
    // Observe registered scene components independently of the bookkeeping
    // array, so cleanup tests can detect orphaned wagon/cargo/animal meshes.
    int32 DeliveryRoots=0,DeliveryParts=0,RevealCloths=0;
    TArray<UActorComponent*> ActorComponents; GetComponents(ActorComponents);
    for (const UActorComponent* Component : ActorComponents) if (IsValid(Component) && Component->IsRegistered())
    {
        if (Cast<UOldWestDeliveryVisuals>(Component)) ++DeliveryRoots;
        if (Component->ComponentHasTag(TEXT("OldWestDeliveryPart"))) ++DeliveryParts;
        if (Component->ComponentHasTag(TEXT("OldWestRevealBandana"))) ++RevealCloths;
    }
    Result["delivery_component_counts"]={{"roots",DeliveryRoots},{"parts",DeliveryParts}};
    Result["reveal_cloth_components"]=RevealCloths;
    for (const auto& Delivery : P.Deliveries) if (Delivery.IsValid())
    {
        const J Record=J::parse(TCHAR_TO_UTF8(*Delivery->GetDebug()));
        Result["deliveries"].push_back(Record);
        for (const auto& Part : Record["parts"]) Result["action_effects"].push_back(Part);
    }
    Result["settle_hold"] = {{"required", P.WaitForPersonSettling}, {"stable_seconds", P.SettleStableSeconds},
        {"all_settled", P.AllRagdollsSettled}, {"minimum_seconds", 1.95f}, {"maximum_seconds", PersonFallTimeLimit()},
        {"required_stable_seconds", .25f}};
    Result["completion_history"] = P.CompletionHistory;
    auto Vector = [](const FVector& V) { return J::array({V.X, V.Y, V.Z}); };
    const UPhysicsSettings* Settings = UPhysicsSettings::Get();
    Result["frame_timing"] = {{"frames", P.FrameCount}, {"last_delta_seconds", P.LastFrameSeconds},
        {"maximum_delta_seconds", P.MaxFrameSeconds}, {"estimated_physics_seconds", P.EstimatedPhysicsSeconds},
        {"substepping", Settings->bSubstepping}, {"maximum_physics_delta_seconds", Settings->MaxPhysicsDeltaTime},
        {"maximum_substep_delta_seconds", Settings->MaxSubstepDeltaTime}, {"maximum_substeps", Settings->MaxSubsteps}};
    Result["frame_performance"] = P.PerformanceDebug();
    Result["terrain_renderer"] = nullptr;
    for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
    {
        const UStaticMeshComponent* Component = It->GetStaticMeshComponent();
        const UStaticMesh* Mesh = Component ? Component->GetStaticMesh() : nullptr;
        if (!Mesh || Mesh->GetName() != TEXT("SM_ContinuousTerrain")) continue;
        // IsNaniteMesh reads an immutable proxy-type flag. This reports the
        // actual live scene proxy, not the asset's requested enable setting.
        const FPrimitiveSceneProxy* Proxy = Component->GetSceneProxy();
        Result["terrain_renderer"] = {{"mesh", std::string(TCHAR_TO_UTF8(*Mesh->GetPathName()))},
            {"location", Vector(Component->GetComponentLocation())},
            {"scale", Vector(Component->GetComponentScale())},
            {"rotation_degrees", Vector(Component->GetComponentRotation().Euler())},
            {"scene_proxy_present", Proxy != nullptr}, {"nanite_mesh_proxy", Proxy ? J(Proxy->IsNaniteMesh()) : J(nullptr)}};
        break;
    }
    Result["simultaneous_targets"] = J::array();
    Result["survivor_lods"] = J::array();
    Result["tactical_camera"] = {{"yaw", TacticalYaw}, {"pitch", TacticalPitch}, {"distance", TacticalDistance},
        {"birds_eye", BirdOverview},
        {"focus", Vector(TacticalFocus)}, {"desired_camera", Vector(DesiredCamera)},
        {"minimum_distance", 120.f}, {"maximum_distance", 24000.f},
        {"minimum_pitch", -89.f}, {"maximum_pitch", 89.f}};
    Result["units"] = J::array();
    for (const auto& Pair : Units) if (IsValid(Pair.Value))
    {
        J Unit = J::parse(TCHAR_TO_UTF8(*Pair.Value->GetIdleDebug()));
        Unit["id"] = Pair.Key;
        Unit["side"] = Pair.Value->Side;
        Unit["hidden"] = Pair.Value->IsHidden();
        const int32* Entrance = P.DeferredEntrances.Find(Pair.Key);
        Unit["deferred_enter_sequence"] = Entrance ? J(*Entrance) : J(nullptr);
        Unit["location"] = Vector(Pair.Value->GetActorLocation());
        const FBox Bounds = Pair.Value->GetVisualBounds();
        if (Bounds.IsValid) Unit["bounds"] = {Vector(Bounds.Min), Vector(Bounds.Max)};
        Result["units"].push_back(MoveTemp(Unit));
    }
    // Event vehicles use static meshes. Their unused Body component does not
    // represent a rendered survivor LOD and must not enter skeletal LOD checks.
    for (const auto& Pair : Units) if (IsValid(Pair.Value) && !Pair.Value->Camp && !Pair.Value->IsEventToken())
        Result["survivor_lods"].push_back({{"target", Pair.Key}, {"forced_lod", Pair.Value->Body->GetForcedLOD()},
            {"predicted_lod", Pair.Value->Body->GetPredictedLODLevel()}});
    for (const auto& Other : P.Simultaneous)
    {
        J Entry = {{"target", Other.Target}, {"sequence", Other.Sequence}, {"kind", std::string(TCHAR_TO_UTF8(*Other.Kind))},
            {"before_damage", Other.Before.Damage}, {"after_damage", Other.After.Damage}};
        AddAbilityPresentationDebug(Entry, Other);
        AddQueueTransitionDebug(Entry, Other);
        if (AOldWestUnit* Unit = Units.FindRef(Other.Target))
        {
            Entry["displayed_damage"] = Unit->GetVisualDamage(); Entry["ragdoll"] = Unit->IsRagdoll(); Entry["camp"] = Unit->Camp;
            Entry["body_focus"] = Vector(Unit->GetPresentationFocus());
            Entry["subject_frame"] = ProjectSubjectBounds(Unit, Camera);
            Entry["event_token"] = Unit->IsEventToken();
            if (!Unit->Camp && !Unit->IsEventToken()) { Entry["predicted_lod"] = Unit->Body->GetPredictedLODLevel(); Entry["forced_lod"] = Unit->Body->GetForcedLOD(); }
            Entry["physics"] = J::parse(TCHAR_TO_UTF8(*Unit->GetPhysicsDebug()));
        }
        Result["simultaneous_targets"].push_back(Entry);
    }
    Result["camera_focus"] = Vector(CameraFocus);
    Result["subject_frame"] = P.Active.IsSet() ? ProjectSubjectBounds(Units.FindRef(P.Active->Target), Camera) : J(nullptr);
    if (Camera)
    {
        Result["camera_location"] = Vector(Camera->GetActorLocation());
        const UCineCameraComponent* Lens = Camera->GetCineCameraComponent();
        Result["lens"] = {{"focus_method", Lens->FocusSettings.FocusMethod == ECameraFocusMethod::Manual ? "manual" : "disabled"},
            {"manual_focus_distance_cm", Lens->FocusSettings.ManualFocusDistance},
            {"current_focus_distance_cm", Lens->CurrentFocusDistance},
            {"aperture", Lens->CurrentAperture}, {"focal_length_mm", Lens->CurrentFocalLength},
            {"filmback_sensor_width_mm", Lens->Filmback.SensorWidth}, {"filmback_sensor_height_mm", Lens->Filmback.SensorHeight},
            {"shutter_speed", Lens->PostProcessSettings.CameraShutterSpeed},
            {"shutter_override", static_cast<bool>(Lens->PostProcessSettings.bOverride_CameraShutterSpeed)},
            {"postprocess_blend_weight", Lens->PostProcessBlendWeight},
            {"exposure_product", FMath::Square(Lens->CurrentAperture) * Lens->PostProcessSettings.CameraShutterSpeed},
            {"baseline_exposure_product", 8.f * 8.f * 60.f}, {"camera_forward", Vector(Lens->GetForwardVector())}};
    }
    if (P.Active.IsSet())
    {
        const auto& Beat = P.Active.GetValue();
        Result["kind"] = std::string(TCHAR_TO_UTF8(*Beat.Kind));
        Result["source"] = Beat.Source; Result["target"] = Beat.Target; Result["sequence"] = Beat.Sequence;
        Result["player"] = Beat.Player; Result["count"] = Beat.Count; Result["known_target"] = Beat.KnownTarget;
        Result["detail"] = std::string(TCHAR_TO_UTF8(*Beat.Detail));
        Result["caption"] = std::string(TCHAR_TO_UTF8(*GetCinematicCaption()));
        AddAbilityPresentationDebug(Result, Beat);
        AddQueueTransitionDebug(Result, Beat);
        Result["before_damage"] = Beat.Before.Damage; Result["after_damage"] = Beat.After.Damage;
        FString ObstructionDetail;
        Result["camera_obstructed"] = Camera && IsShotObstructed(CameraFocus, Camera->GetActorLocation(), P.EffectFraming ? INDEX_NONE : P.GroupShot ? 0 : Beat.Target, &ObstructionDetail);
        Result["camera_obstruction_detail"] = std::string(TCHAR_TO_UTF8(*ObstructionDetail));
#if !UE_BUILD_SHIPPING
        Result["camera_post_tick"] = P.CameraPostTick;
#endif
        AOldWestUnit* DisplayedTarget = Units.FindRef(Beat.Target);
        const bool TargetVisible = IsValid(DisplayedTarget) && !DisplayedTarget->IsHidden();
        Result["target_actor_visible"] = TargetVisible;
        // A recycled card can already have a hidden actor for a later entrance.
        // Its future pose/condition is not displayed by an earlier hand action.
        // Raw actor diagnostics remain available in units, including hidden ones.
        if (AOldWestUnit* Unit = DisplayedTarget; Beat.KnownTarget && TargetVisible)
        {
            Result["physics"] = J::parse(TCHAR_TO_UTF8(*Unit->GetPhysicsDebug()));
            Result["root_drift_cm"] = Unit->GetRootDrift(); Result["ragdoll"] = Unit->IsRagdoll();
            Result["displayed_damage"] = Unit->GetVisualDamage(); Result["body_focus"] = Vector(Unit->GetPresentationFocus());
            Result["target_location"] = Vector(Unit->GetActorLocation()); Result["camp"] = Unit->Camp;
            Result["event_token"] = Unit->IsEventToken();
            if (!Unit->Camp && !Unit->IsEventToken()) { Result["predicted_lod"] = Unit->Body->GetPredictedLODLevel(); Result["forced_lod"] = Unit->Body->GetForcedLOD(); }
        }
    }
    return Text(Result.dump());
#else
    return TEXT("{}");
#endif
}

void AOldWestBattlefield::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    // Fit growing hands only while the player still uses the default camera.
    // Wait for the presentation to finish so fitting never skips an action.
    if (DefaultFramingPending && !CameraCustomized && !BirdOverview && !IsCinematicBusy()) ResetCamera();
    auto& P = *Presentation;
    AdvanceScientistScenes(DeltaSeconds);
    if (P.Active.IsSet())
    {
        P.Elapsed += DeltaSeconds;
        ++P.FrameCount;
        P.LastFrameSeconds = DeltaSeconds;
        P.MaxFrameSeconds = FMath::Max(P.MaxFrameSeconds, DeltaSeconds);
        const UPhysicsSettings* Settings = UPhysicsSettings::Get();
        const float Cap = Settings->bSubstepping ? Settings->MaxSubstepDeltaTime * Settings->MaxSubsteps : Settings->MaxPhysicsDeltaTime;
        // This is the per-frame time submitted by ChaosScene::SetUpForFrame,
        // estimated from observed deltas/settings, not a solver completion clock.
        P.EstimatedPhysicsSeconds += Cap > 0.f ? FMath::Min(DeltaSeconds, Cap) : DeltaSeconds;
#if !UE_BUILD_SHIPPING
        if (ProfilePresentation())
        {
            FOldWestPresentation::FPerformanceFrame Sample;
            Sample.Frame = GFrameCounter; Sample.Elapsed = P.Elapsed; Sample.Delta = DeltaSeconds;
            Sample.PhysicsDelta = Cap > 0.f ? FMath::Min(DeltaSeconds, Cap) : DeltaSeconds;
            Sample.Game = GGameThreadTime; Sample.GameWait = GGameThreadWaitTime;
            Sample.GameCritical = GGameThreadTimeCriticalPath;
            Sample.Render = GRenderThreadTime; Sample.RenderWait = GRenderThreadWaitTime;
            Sample.RenderCritical = GRenderThreadTimeCriticalPath;
            Sample.Rhi = GRHIThreadTime; Sample.Gpu = GDynamicRHI ? RHIGetGPUFrameCycles() : 0;
            Sample.Present = GSwapBufferTime;
            if (P.PerformanceFrames.Num() < 600) P.PerformanceFrames.Add(Sample);
            else P.PerformanceFrames[P.PerformanceWriteIndex] = Sample;
            P.PerformanceWriteIndex = (P.PerformanceWriteIndex + 1) % 600;
        }
#endif
        UpdateActionEffects(DeltaSeconds);
        if (P.Elapsed >= 0.18f) ResolveImpact();
        if (!P.GroupShot && !P.EffectFraming)
            if (AOldWestUnit* Unit = Units.FindRef(P.Active->Target))
            {
                DesiredFocus = Unit->GetPresentationFocus();
                DesiredCamera = DesiredFocus + P.ShotOffset;
                if (IsShotObstructed(DesiredFocus, DesiredCamera, P.Active->Target))
                {
                    DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, P.Active->Target);
                    P.ShotOffset = DesiredCamera - DesiredFocus;
                    if (Camera) Camera->SetActorLocation(DesiredCamera);
                }
            }
        if (P.GroupShot && !P.EffectFraming && IsShotObstructed(DesiredFocus, DesiredCamera, 0))
        {
            if (P.Active->Kind == TEXT("turn_start"))
                FocusAction(P.Active->Source, P.Active->Target, P.Active->Kind, P.Active->Revision);
            else
            {
                DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, 0);
                if (Camera) Camera->SetActorLocation(DesiredCamera);
            }
        }
        bool Complete = P.Elapsed >= P.Active->Duration;
        const TCHAR* CompletionReason = TEXT("duration");
        if (P.Active->ScientistScene)
        {
            UOldWestScientistPlayback* Playback = P.ScientistPlayback.FindRef(P.Active->AnalysisSequence).Get();
            const J Context = P.Analysis.Get(P.Active->AnalysisSequence);
            if (IsValid(Playback) && Playback->IsAwaitingChoice() && !Context.is_null() &&
                !Context.value("accepted", false) && !Context.value("boundary_reason", std::string()).empty())
                Playback->FinishWithoutDecision(P.MatchId, P.Active->AnalysisSequence, Text(Context.value("boundary_reason", std::string())));
            Complete = !IsValid(Playback) || !Playback->IsActive() || Playback->IsComplete() ||
                (P.Active->Kind == TEXT("ability") && Playback->IsAwaitingChoice());
            CompletionReason = IsValid(Playback) && Playback->IsAwaitingChoice() ? TEXT("analysis_ready_for_choice") : TEXT("analysis_playback_finished");
        }
        if (P.WaitForPersonSettling)
        {
            FString SettlingFailures;
            auto Settled = [this, &SettlingFailures](const FCinematicBeat& Beat)
            {
                if (Beat.Kind != TEXT("destroy") || Beat.Before.Camp) return true;
                const AOldWestUnit* Unit = Units.FindRef(Beat.Target);
#if !UE_BUILD_SHIPPING
                if (ProfilePresentation())
                {
                    FString Reason;
                    const bool Ready = IsValid(Unit) && Unit->IsRagdollSettled(&Reason);
                    if (!Ready) SettlingFailures += FString::Printf(TEXT("%d=%s;"), Beat.Target,
                        IsValid(Unit) ? *Reason : TEXT("missing_unit"));
                    return Ready;
                }
#endif
                return IsValid(Unit) && Unit->IsRagdollSettled();
            };
            P.AllRagdollsSettled = Settled(P.Active.GetValue());
            for (const auto& Other : P.Simultaneous) P.AllRagdollsSettled &= Settled(Other);
            // Count simulated frame time, so a stalled rendering frame cannot
            // stand in for a quarter-second of observed stable physics.
            const float PhysicsStep = Cap > 0.f ? FMath::Min(DeltaSeconds, Cap) : DeltaSeconds;
            P.SettleStableSeconds = P.AllRagdollsSettled ? P.SettleStableSeconds + PhysicsStep : 0.f;
#if !UE_BUILD_SHIPPING
            if (ProfilePresentation() && !P.PerformanceFrames.IsEmpty())
            {
                auto& Sample = P.PerformanceFrames[(P.PerformanceWriteIndex + 599) % 600];
                check(Sample.Frame == GFrameCounter);
                Sample.SettlingRequired = true;
                Sample.AllSettled = P.AllRagdollsSettled;
                Sample.StableSeconds = P.SettleStableSeconds;
                Sample.SettlingFailure = MoveTemp(SettlingFailures);
            }
#endif
            const bool NaturalCompletion = P.Elapsed >= 1.95f && P.SettleStableSeconds >= .25f;
            Complete = (NaturalCompletion && !DiagnosticFallHold()) || P.Elapsed >= PersonFallTimeLimit();
            CompletionReason = NaturalCompletion ? TEXT("settled") : TEXT("timeout");
        }
        if (Complete)
        {
            P.Analysis.Presented(P.Active->AnalysisSequence, P.Active->AnalysisPresentedThrough);
            RecordShotCompletion(CompletionReason);
            P.Active.Reset();
            P.Simultaneous.Empty();
            ReconcileUnits();
            // Normal playback preserves every authoritative action. Only the
            // player's explicit Skip abandons queued presentation work.
            BeginNextBeat();
        }
    }
    if (IsAnalysisChoiceFramed() && IsShotObstructed(DesiredFocus, DesiredCamera, INDEX_NONE))
    {
        DesiredCamera = ChooseShotPosition(DesiredFocus, DesiredCamera, INDEX_NONE);
        ChoiceViewPosition = DesiredCamera;
        if (Camera) Camera->SetActorLocation(DesiredCamera);
    }
    // Names remain readable in the tactical view. Their world-space size
    // overwhelms close shots, where the focused figure supplies the context.
    for (auto& Pair : Units) if (IsValid(Pair.Value)) Pair.Value->Caption->SetVisibility(false);
    if (!Camera) return;
    CameraFocus = FMath::VInterpTo(CameraFocus, DesiredFocus, DeltaSeconds, 9.f);
    FVector Position = FMath::VInterpTo(Camera->GetActorLocation(), DesiredCamera, DeltaSeconds, 9.f);
    if (IsCinematicBusy())
    {
        // A clear destination does not guarantee a clear interpolated frame:
        // while a person walks, the trailing camera can see through a nearby
        // camp or another person's silhouette. Check the position we actually
        // render and cut to a clear shot instead of smoothing through it.
        const int32 ShotTarget = P.EffectFraming || IsAnalysisChoiceFramed() ? INDEX_NONE :
            P.GroupShot ? 0 : P.Active.IsSet() ? P.Active->Target : INDEX_NONE;
        if (IsShotObstructed(CameraFocus, Position, ShotTarget))
        {
            Position = ChooseShotPosition(DesiredFocus, DesiredCamera, ShotTarget);
            CameraFocus = DesiredFocus;
            DesiredCamera = Position;
            if (P.Active.IsSet() && !P.GroupShot && !P.EffectFraming)
                P.ShotOffset = Position - DesiredFocus;
            if (IsAnalysisChoiceFramed()) ChoiceViewPosition = Position;
        }
    }
    else
    {
        FHitResult Obstacle;
        FCollisionQueryParams CameraParams(SCENE_QUERY_STAT(OldWestTacticalCameraMotion), true);
        if (GetWorld()->SweepSingleByChannel(Obstacle, Camera->GetActorLocation(), Position, FQuat::Identity,
            ECC_Camera, FCollisionShape::MakeSphere(45.f), CameraParams))
        {
            Position = Obstacle.Location + Obstacle.ImpactNormal * 5.f;
            // Lift over an obstacle while orbiting; never interpolate through
            // a camp merely because the final orbit position is unobstructed.
            Position.Z += FMath::Min(DeltaSeconds * 700.f, 80.f);
        }
    }
    Camera->SetActorLocation(Position);
    Camera->SetActorRotation((CameraFocus - Position).Rotation());
    UpdateShotFocus();
#if !UE_BUILD_SHIPPING
    // Lifecycle reports run in the controller's earlier tick. Retain the
    // final camera check after unit motion and camera correction, as well as
    // the existing live report-time check, to distinguish mixed-frame probes.
    if (P.Active.IsSet())
    {
        const int32 Sequence = P.Active->Sequence;
        if (P.CameraPostTick.value("sequence", -1) != Sequence)
            P.CameraPostTick = {{"sequence", Sequence}, {"samples", 0}, {"obstructed_frames", 0}};
        const int32 Target = P.EffectFraming ? INDEX_NONE : P.GroupShot ? 0 : P.Active->Target;
        FString Detail;
        const bool Obstructed = IsShotObstructed(CameraFocus, Camera->GetActorLocation(), Target, &Detail);
        P.CameraPostTick["samples"] = P.CameraPostTick.value("samples", 0) + 1;
        P.CameraPostTick["frame"] = GFrameCounter;
        P.CameraPostTick["obstructed"] = Obstructed;
        P.CameraPostTick["detail"] = std::string(TCHAR_TO_UTF8(*Detail));
        if (Obstructed)
        {
            P.CameraPostTick["obstructed_frames"] = P.CameraPostTick.value("obstructed_frames", 0) + 1;
            P.CameraPostTick["last_failure"] = std::string(TCHAR_TO_UTF8(*Detail));
        }
    }
    else P.CameraPostTick = J::object();
#endif
}
