#include "OldWestStampedeVisuals.h"
#include "OldWestManualAnimInstance.h"
#include "OldWestBattlefield.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimSequence.h"
#include "EngineUtils.h"
#include "Core/json.hpp"

namespace { constexpr float AnimalScale = .72f; constexpr float StrideSpeed = 225.f * AnimalScale; }
UOldWestStampedeVisuals::UOldWestStampedeVisuals()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}
void UOldWestStampedeVisuals::Clear()
{
    SetComponentTickEnabled(false);
    for (USkeletalMeshComponent* Animal : Animals) if (IsValid(Animal)) Animal->DestroyComponent();
    Animals.Empty(); Idle = Run = nullptr;
    Movement = FVector::ZeroVector; IdleSeconds = RunSeconds = TravelCm = 0.;
    BlendSeconds = 1.f; Speed = 0.f; Running = false;
}
void UOldWestStampedeVisuals::Build(int32 Side)
{
    Clear();
    USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Art/Western/StampedeStudy/SK_Longhorn.SK_Longhorn"));
    Idle = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/Art/Western/StampedeStudy/Animations/A_Longhorn_Idle.A_Longhorn_Idle"));
    Run = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/Art/Western/StampedeStudy/Animations/A_Longhorn_Run.A_Longhorn_Run"));
    if (!Mesh || !Idle || !Run)
    { UE_LOG(LogTemp, Error, TEXT("OLDWEST_STAMPEDE_ASSET_MISSING")); return; }
    HomeYaw = Side == 0 ? 180.f : 0.f;
    SetRelativeRotation(FRotator(0, HomeYaw, 0));
    const FVector Formation[] = {FVector(0,115,0), FVector(-92,-100,0), FVector(92,-100,0)};
    for (int32 Index = 0; Index < 3; ++Index)
    {
        auto* Animal = NewObject<USkeletalMeshComponent>(GetOwner());
        GetOwner()->AddInstanceComponent(Animal); Animal->SetupAttachment(this);
        Animal->SetSkeletalMesh(Mesh);
        Animal->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Animal->SetCanEverAffectNavigation(false);
        Animal->SetRelativeLocation(Formation[Index]); Animal->SetRelativeScale3D(FVector(AnimalScale));
        Animal->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Animal->RegisterComponent();
        Animal->SetAnimInstanceClass(UOldWestManualAnimInstance::StaticClass());
        Animal->SetComponentTickEnabled(false);
        if (auto* Instance = Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance()))
        {
            Instance->SetAnimationAsset(Idle, true, 0.f);
            Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
            Instance->SetPlaying(false); Instance->SetPosition(Index * Idle->GetPlayLength() / 3.f, false);
            Animal->TickAnimation(0.f, false); Animal->RefreshBoneTransforms();
        }
        Animals.Add(Animal);
    }
    // The existing director moves actors in PostUpdateWork. Sample after it.
    for (TActorIterator<AOldWestBattlefield> It(GetWorld()); It; ++It) AddTickPrerequisiteActor(*It);
    SetComponentTickEnabled(true);
}
void UOldWestStampedeVisuals::RecordMovement(const FVector& Delta)
{
    Movement += FVector(Delta.X, Delta.Y, 0);
}
void UOldWestStampedeVisuals::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Function)
{
    Super::TickComponent(DeltaTime, TickType, Function);
    if (Animals.Num() != 3 || DeltaTime <= 0.f) return;
    const double Distance = Movement.Size();
    Speed = Distance / DeltaTime;
    const bool Moving = Speed > .5f;
    TravelCm += Distance;
    IdleSeconds += DeltaTime;
    if (Moving != Running)
    {
        Running = Moving; BlendSeconds = 0.f;
        for (USkeletalMeshComponent* Animal : Animals)
            if (auto* Instance = Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance()))
            {
                Instance->EntryLocalPose = Animal->GetBoneSpaceTransforms();
                Instance->SetAnimationAsset(Running ? Run : Idle, true, 0.f);
            }
    }
    // Backward delays use the same authored run played backward, while each
    // animal continues facing the opponent. A resolved charge turns to its path.
    double Sign = 1.;
    if (Moving)
    {
        const FVector Home = FRotator(0, HomeYaw, 0).RotateVector(FVector(0,1,0));
        if (FMath::Abs(Movement.X) < .01f)
        { SetRelativeRotation(FRotator(0,HomeYaw,0)); Sign = FVector::DotProduct(Movement,Home) < 0 ? -1. : 1.; }
        else SetRelativeRotation(FRotator(0,Movement.Rotation().Yaw - 90.f,0));
    }
    RunSeconds += Sign * Distance / StrideSpeed;
    BlendSeconds += DeltaTime;
    for (int32 Index=0; Index<Animals.Num(); ++Index)
    {
        USkeletalMeshComponent* Animal = Animals[Index];
        auto* Instance = Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance());
        if (!Instance) continue;
        UAnimSequence* Clip = Running ? Run : Idle;
        const double Length = Clip->GetPlayLength();
        double Time = FMath::Fmod((Running ? RunSeconds : IdleSeconds) + Index * Length / 3., Length);
        if (Time < 0) Time += Length;
        Instance->EntryAlpha = FMath::Clamp(BlendSeconds / .12f,0.f,1.f);
        Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
        Instance->SetPlaying(false); Instance->SetPlayRate(0.f); Instance->SetPosition(Time,false);
        Animal->TickAnimation(0.f,false); Animal->RefreshBoneTransforms();
    }
    Movement = FVector::ZeroVector;
}
FBox UOldWestStampedeVisuals::GetVisualBounds() const
{
    FBox Bounds(ForceInit);
    for (const USkeletalMeshComponent* Animal : Animals) if (IsValid(Animal)) Bounds += Animal->Bounds.GetBox();
    return Bounds;
}
FString UOldWestStampedeVisuals::GetDebug() const
{
    using J = nlohmann::ordered_json;
    J Out={{"animal_count",Animals.Num()},{"running",Running},{"speed_cm_s",Speed},{"travel_cm",TravelCm},{"animals",J::array()}};
    for (const USkeletalMeshComponent* Animal : Animals)
    {
        const auto* Instance=Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance());
        const FVector Location=Animal->GetComponentLocation(), Offset=Animal->GetRelativeLocation();
        const FVector Root=Animal->GetSocketTransform(TEXT("Root"),RTS_Component).GetLocation();
        Out["animals"].push_back({{"mesh",TCHAR_TO_UTF8(*Animal->GetSkeletalMeshAsset()->GetPathName())},
            {"visible",Animal->IsVisible()},{"collision",static_cast<int32>(Animal->GetCollisionEnabled())},
            {"location",{Location.X,Location.Y,Location.Z}},{"offset",{Offset.X,Offset.Y,Offset.Z}},
            {"scale",Animal->GetComponentScale().X},{"root_drift_cm",Root.Size()},
            {"clip",Instance && Instance->GetAnimationAsset()?TCHAR_TO_UTF8(*Instance->GetAnimationAsset()->GetName()):""},
            {"seconds",Instance?Instance->GetCurrentTime():0.f}});
    }
    return UTF8_TO_TCHAR(Out.dump().c_str());
}
