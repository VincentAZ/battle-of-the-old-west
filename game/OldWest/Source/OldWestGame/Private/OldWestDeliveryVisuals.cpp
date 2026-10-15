#include "OldWestDeliveryVisuals.h"
#include "OldWestManualAnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/Material.h"
#include "Core/json.hpp"

namespace
{
const FString Base(TEXT("/Game/Art/ActionProps/Delivery/"));
const TCHAR* WheelNames[] = {TEXT("FrontLeft"), TEXT("RearLeft"), TEXT("FrontRight"), TEXT("RearRight")};
const FVector WheelPositions[] = {FVector(-85,125,55), FVector(-85,-110,70), FVector(85,125,55), FVector(85,-110,70)};
constexpr float Radii[] = {55.f,70.f,55.f,70.f};
constexpr float YokeY[] = {411.2f,741.2f};
const FVector ChainAnchor(0,186.5f,85.f), ChainHook(0,-4.5f,130.f);
constexpr float ChainLengths[] = {223.6532064f,330.f};
}

void UOldWestDeliveryVisuals::Preload(TArray<TObjectPtr<UObject>>& Assets)
{
    TArray<FString> Paths = {Base+TEXT("Meshes/SM_Delivery_Wagon"), Base+TEXT("Hitch/Meshes/SM_Delivery_OxYoke"),
        Base+TEXT("Hitch/Meshes/SM_Delivery_DraftChain"), Base+TEXT("Hitch/Meshes/SM_Delivery_TeamChain"),
        Base+TEXT("Oxen/SK_DraftOx"), Base+TEXT("Oxen/Animations/A_DraftOx_Idle"), Base+TEXT("Oxen/Animations/A_DraftOx_Walk")};
    for (const TCHAR* Name : WheelNames) Paths.Add(Base+TEXT("Meshes/SM_Delivery_")+Name);
    for (const FString& Path : Paths)
        if (UObject* Asset = LoadObject<UObject>(nullptr,*Path))
        {
            Assets.Add(Asset);
            if (const UStaticMesh* Mesh = Cast<UStaticMesh>(Asset))
                for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
                    if (Slot.MaterialInterface) Slot.MaterialInterface->CacheShaders();
        }
}

void UOldWestDeliveryVisuals::Clear()
{
    for (USkeletalMeshComponent* Animal : Animals) if (IsValid(Animal)) Animal->DestroyComponent();
    for (UStaticMeshComponent* Mesh : Parts) if (IsValid(Mesh)) Mesh->DestroyComponent();
    Animals.Empty(); Parts.Empty(); Wheels.Empty(); Yokes.Empty(); Chains.Empty();
    Idle = Walk = nullptr; Age = Distance = Travel = MoveSeconds = 0.f;
}

UStaticMeshComponent* UOldWestDeliveryVisuals::Part(const FString& Path, const FVector& Offset)
{
    UStaticMesh* Asset = LoadObject<UStaticMesh>(nullptr,*Path);
    if (!Asset) { UE_LOG(LogTemp,Error,TEXT("OLDWEST_DELIVERY_ASSET_MISSING %s"),*Path); return nullptr; }
    auto* Mesh = NewObject<UStaticMeshComponent>(GetOwner());
    Mesh->ComponentTags.AddUnique(TEXT("OldWestDeliveryPart"));
    GetOwner()->AddInstanceComponent(Mesh); Mesh->SetupAttachment(this);
    Mesh->SetStaticMesh(Asset); Mesh->SetRelativeLocation(Offset);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision); Mesh->SetCanEverAffectNavigation(false);
    Mesh->RegisterComponent(); Parts.Add(Mesh); return Mesh;
}

bool UOldWestDeliveryVisuals::Build(const FVector& From, const FVector& To, int32 Count, bool Whiskey, bool Medical)
{
    Clear(); Start=From; Finish=To; Distance=FVector::Dist2D(From,To);
    if (Distance < 1.f) return false;
    MoveSeconds=Distance/WalkSpeed; Walking=true; HasWhiskey=Whiskey; CargoCount=FMath::Clamp(Count,1,6);
    SetWorldLocation(Start); SetWorldScale3D(FVector(DioramaScale));
    SetWorldRotation(FRotator(0,(To-From).Rotation().Yaw-90.f,0));
    if (!Part(Base+TEXT("Meshes/SM_Delivery_Wagon"))) { Clear(); return false; }
    for (int32 I=0; I<4; ++I)
    {
        auto* Wheel=Part(Base+TEXT("Meshes/SM_Delivery_")+WheelNames[I],WheelPositions[I]);
        if (!Wheel) { Clear(); return false; } Wheels.Add(Wheel);
    }
    for (float Y : YokeY)
    {
        auto* Yoke=Part(Base+TEXT("Hitch/Meshes/SM_Delivery_OxYoke"),FVector(0,Y,0));
        if (!Yoke) { Clear(); return false; } Yokes.Add(Yoke);
    }
    for (const TCHAR* Name : {TEXT("DraftChain"),TEXT("TeamChain")})
    {
        auto* Chain=Part(Base+TEXT("Hitch/Meshes/SM_Delivery_")+Name);
        if (!Chain) { Clear(); return false; } Chains.Add(Chain);
    }
    USkeletalMesh* Ox=LoadObject<USkeletalMesh>(nullptr,*(Base+TEXT("Oxen/SK_DraftOx")));
    Idle=LoadObject<UAnimSequence>(nullptr,*(Base+TEXT("Oxen/Animations/A_DraftOx_Idle")));
    Walk=LoadObject<UAnimSequence>(nullptr,*(Base+TEXT("Oxen/Animations/A_DraftOx_Walk")));
    if (!Ox || !Idle || !Walk) { Clear(); return false; }
    for (int32 I=0; I<4; ++I)
    {
        auto* Animal=NewObject<USkeletalMeshComponent>(GetOwner());
        Animal->ComponentTags.AddUnique(TEXT("OldWestDeliveryPart"));
        GetOwner()->AddInstanceComponent(Animal); Animal->SetupAttachment(this);
        Animal->SetSkeletalMesh(Ox);
        Animal->SetRelativeLocation(FVector((I%2==0?-75.f:75.f)-5.2734f*AnimalScale,I<2?350.f:680.f,0));
        Animal->SetRelativeScale3D(FVector(AnimalScale));
        Animal->SetCollisionEnabled(ECollisionEnabled::NoCollision); Animal->SetCanEverAffectNavigation(false);
        Animal->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Animal->RegisterComponent(); Animal->SetAnimInstanceClass(UOldWestManualAnimInstance::StaticClass());
        Animal->SetComponentTickEnabled(false); Animals.Add(Animal);
        auto* Instance=Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance());
        if (!Instance) { Clear(); return false; }
        Instance->SetAnimationAsset(Walk,true,0.f); Instance->SetPlaying(false);
    }
    const FString CargoPath=TEXT("/Game/Art/ActionProps/Meshes/")+FString(Whiskey?TEXT("SM_Action_WhiskeyCase"):TEXT("SM_Action_CargoCrate"));
    for (int32 I=0; I<CargoCount; ++I)
    {
        // Small loads form one readable row; larger loads use two staggered
        // columns. All boxes stay supported by the existing floor. Derive
        // height from mesh bounds because the two existing cargo pivots differ.
        auto* Cargo=Part(CargoPath);
        if (!Cargo) { Clear(); return false; }
        const FBox Bounds=Cargo->GetStaticMesh()->GetBoundingBox();
        const bool SingleColumn = CargoCount <= 3;
        const FVector At(SingleColumn ? 0.f : (I%2==0 ? -27.f : 27.f),
            -100.f+(SingleColumn ? I*70.f : (I/2)*70.f+(I%2)*25.f),96.f-Bounds.Min.Z);
        Cargo->SetRelativeLocation(At);
        if (Medical && !Whiskey)
            for (const FVector& Scale : {FVector(.24f,.055f,.02f),FVector(.055f,.24f,.02f)})
            {
                auto* Mark=Part(TEXT("/Engine/BasicShapes/Cube"),At+FVector(0,0,Bounds.Max.Z+1.f));
                if (!Mark) { Clear(); return false; }
                Mark->SetRelativeScale3D(Scale);
                Mark->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/WaterDepotV2/Materials/M_ChalkMarkings")));
            }
    }
    Pose(); return true;
}

void UOldWestDeliveryVisuals::Advance(float DeltaSeconds)
{
    if (Animals.Num()!=4 || DeltaSeconds<=0.f) return;
    Age+=DeltaSeconds; Travel=FMath::Min(Distance,Age*WalkSpeed);
    SetWorldLocation(FMath::Lerp(Start,Finish,Travel/Distance));
    if (Walking && Age>=MoveSeconds)
    {
        Walking=false;
        for (USkeletalMeshComponent* Animal : Animals)
            if (auto* Instance=Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance()))
            {
                Instance->EntryLocalPose=Animal->GetBoneSpaceTransforms();
                Instance->SetAnimationAsset(Idle,true,0.f);
            }
    }
    Pose();
}

void UOldWestDeliveryVisuals::Pose()
{
    for (int32 I=0; I<Animals.Num(); ++I)
    {
        USkeletalMeshComponent* Animal=Animals[I]; auto* Instance=Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance());
        if (!Instance) continue;
        const double Seconds=Walking?Travel/WalkSpeed+(I%2)*Walk->GetPlayLength()*.5:Age-MoveSeconds;
        const float Time=FMath::Fmod(FMath::Max(0.,Seconds),Walking?Walk->GetPlayLength():Idle->GetPlayLength());
        Instance->EntryAlpha=Walking?1.f:FMath::Clamp((Age-MoveSeconds)/.18f,0.f,1.f);
        Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
        Instance->SetPlaying(false); Instance->SetPlayRate(0.f); Instance->SetPosition(Time,false);
        Animal->TickAnimation(0.f,false); Animal->RefreshBoneTransforms();
    }
    for (int32 I=0; I<Wheels.Num(); ++I)
        Wheels[I]->SetRelativeRotation(FQuat(FVector::ForwardVector,-Travel/(Radii[I]*DioramaScale)));
    for (int32 Pair=0; Pair<2; ++Pair)
    {
        const float Z=(Animals[Pair*2]->GetSocketTransform(TEXT("Body"),RTS_Component).GetLocation().Z+
            Animals[Pair*2+1]->GetSocketTransform(TEXT("Body"),RTS_Component).GetLocation().Z)*.5f;
        Yokes[Pair]->SetRelativeLocation(FVector(0,YokeY[Pair],(Z-150.f)*AnimalScale));
    }
    const FVector Ends[]={ChainAnchor,Yokes[0]->GetRelativeLocation()+ChainHook,Yokes[1]->GetRelativeLocation()+ChainHook};
    for (int32 I=0; I<Chains.Num(); ++I)
    {
        const FVector Delta=Ends[I+1]-Ends[I];
        Chains[I]->SetRelativeLocation(Ends[I]);
        Chains[I]->SetRelativeRotation(FRotationMatrix::MakeFromZ(Delta).Rotator());
        Chains[I]->SetRelativeScale3D(FVector(1,1,Delta.Size()/ChainLengths[I]));
    }
}

FBox UOldWestDeliveryVisuals::GetVisualBounds() const
{
    FBox Bounds(ForceInit);
    for (const UStaticMeshComponent* Part : Parts) if (IsValid(Part)) Bounds+=Part->Bounds.GetBox();
    for (const USkeletalMeshComponent* Animal : Animals) if (IsValid(Animal)) Bounds+=Animal->Bounds.GetBox();
    return Bounds;
}

TArray<FVector> UOldWestDeliveryVisuals::GetVisibilityPoints() const
{
    TArray<FVector> Points;
    auto Add=[this,&Points](const FVector& Center)
    {
        const FVector Offset=Center-GetComponentLocation();
        Points.Add(Start+Offset); Points.Add(Finish+Offset);
    };
    for (const UStaticMeshComponent* Part : Parts) if (IsValid(Part)) Add(Part->Bounds.Origin);
    for (const USkeletalMeshComponent* Animal : Animals) if (IsValid(Animal)) Add(Animal->GetSocketLocation(TEXT("Head")));
    return Points;
}

FString UOldWestDeliveryVisuals::GetDebug() const
{
    using J=nlohmann::ordered_json;
    auto V=[](const FVector& P){return J::array({P.X,P.Y,P.Z});};
    J Out={{"age",Age},{"move_seconds",MoveSeconds},{"duration",GetDuration()},{"travel_cm",Travel},
        {"route_cm",Distance},{"walking",Walking},{"cargo_count",CargoCount},{"whiskey",HasWhiskey},
        {"from",V(Start)},{"to",V(Finish)},{"parts",J::array()},{"animals",J::array()}};
    for (const UStaticMeshComponent* Part : Parts)
    {
        int32 Wheel=INDEX_NONE; for(int32 I=0;I<Wheels.Num();++I) if(Wheels[I]==Part) Wheel=I;
        const FBox B=Part->Bounds.GetBox();
        Out["parts"].push_back({{"mesh",TCHAR_TO_UTF8(*Part->GetStaticMesh()->GetPathName())},{"visible",Part->IsVisible()},
            {"location",V(Part->GetComponentLocation())},{"scale",V(Part->GetComponentScale())},{"bounds",{V(B.Min),V(B.Max)}},
            {"rotation",{Part->GetComponentQuat().X,Part->GetComponentQuat().Y,Part->GetComponentQuat().Z,Part->GetComponentQuat().W}},
            {"age",Age},{"duration",MoveSeconds},{"wheel_radius_cm",Wheel==INDEX_NONE?0.f:Radii[Wheel]*DioramaScale},
            {"hinged",false},{"collision_enabled",static_cast<int32>(Part->GetCollisionEnabled())}});
    }
    for (const USkeletalMeshComponent* Animal : Animals)
    {
        const auto* Instance=Cast<UOldWestManualAnimInstance>(Animal->GetAnimInstance());
        J Row={{"mesh",TCHAR_TO_UTF8(*Animal->GetSkeletalMeshAsset()->GetPathName())},{"visible",Animal->IsVisible()},
            {"location",V(Animal->GetComponentLocation())},{"scale",V(Animal->GetComponentScale())},
            {"collision_enabled",static_cast<int32>(Animal->GetCollisionEnabled())},{"bones",J::object()},
            {"seconds",Instance?Instance->GetCurrentTime():0.f},{"clip",Walking?"Walk":"Idle"},
            {"entry_alpha",Instance?Instance->EntryAlpha:0.f}};
        for (const TCHAR* Bone : {TEXT("Root"),TEXT("Body"),TEXT("FrontFoot_L"),TEXT("FrontFoot_R"),TEXT("HindFoot_L"),TEXT("HindFoot_R")})
            Row["bones"][TCHAR_TO_UTF8(Bone)]=V(Animal->GetSocketLocation(Bone));
        Out["animals"].push_back(Row);
    }
    return UTF8_TO_TCHAR(Out.dump().c_str());
}
