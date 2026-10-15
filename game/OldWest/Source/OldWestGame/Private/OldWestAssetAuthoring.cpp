#include "OldWestCrewCatalog.h"
#include "OldWestAssetAuthoring.h"
#include "PhysicsEngine/PhysicsAsset.h"

#if WITH_EDITOR
#include "OldWestBattlefield.h"
#include "OldWestManualAnimInstance.h"
#include "Engine/World.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/AnimSequence.h"
#include "SkeletalRenderPublic.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Core/json.hpp"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/BodyInstance.h"
#include "UObject/Package.h"
#include "Math/RotationMatrix.h"
#include "Animation/MorphTarget.h"
#include "Animation/Skeleton.h"
#include "Rendering/SkeletalMeshModel.h"
#include "Rendering/SkeletalMeshLODModel.h"
#include "Misc/SecureHash.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/PackageName.h"
#include "PhysicsEngine/ConvexElem.h"
#include "Materials/MaterialInterface.h"

namespace
{
using J = nlohmann::ordered_json;
constexpr const TCHAR* MeshPath = TEXT("/Game/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm.SKM_Survivor_A_Cm");
constexpr const TCHAR* PackagePath = TEXT("/Game/Art/Survivors/SurvivorA/PA_Survivor_Anatomical");
constexpr const TCHAR* AssetName = TEXT("PA_Survivor_Anatomical");

struct FReferenceBody
{
    const FReferenceSkeleton& Skeleton;
    TArray<FTransform> World;
    explicit FReferenceBody(const USkeletalMesh* Mesh) : Skeleton(Mesh->GetRefSkeleton())
    {
        const auto& Local = Skeleton.GetRefBonePose();
        for (int32 I = 0; I < Local.Num(); ++I)
        {
            const int32 Parent = Skeleton.GetParentIndex(I);
            World.Add(Parent == INDEX_NONE ? Local[I] : Local[I] * World[Parent]);
        }
    }
    const FTransform& Transform(const FString& Bone) const
    {
        const int32 Index = Skeleton.FindBoneIndex(*Bone);
        checkf(Index != INDEX_NONE, TEXT("Missing survivor bone %s"), *Bone);
        return World[Index];
    }
    FVector Position(const FString& Bone) const { return Transform(Bone).GetLocation(); }
};

std::string Utf8(const FString& S) { return std::string(TCHAR_TO_UTF8(*S)); }
J Vector(const FVector& V) { return J::array({V.X, V.Y, V.Z}); }

USkeletalBodySetup* Body(UPhysicsAsset* Asset, const FString& Bone, float Mass)
{
    auto* Setup = NewObject<USkeletalBodySetup>(Asset, NAME_None, RF_Transactional);
    Setup->BoneName = *Bone;
    Setup->PhysicsType = PhysType_Default;
    Setup->bConsiderForBounds = true;
    Setup->bSkipScaleFromAnimation = true;
    Setup->CollisionTraceFlag = CTF_UseSimpleAsComplex;
    Setup->DefaultInstance.SetCollisionProfileName(TEXT("Ragdoll"));
    Setup->DefaultInstance.SetMassOverride(Mass, true);
    Setup->DefaultInstance.LinearDamping = 0.5f;
    Setup->DefaultInstance.AngularDamping = 4.f;
    Setup->DefaultInstance.SetPositionSolverIterationCount(12);
    Setup->DefaultInstance.SetVelocitySolverIterationCount(4);
    Setup->DefaultInstance.SetOverrideIterationCounts(true);
    Asset->SkeletalBodySetups.Add(Setup);
    return Setup;
}

void Capsule(UPhysicsAsset* Asset, const FReferenceBody& Ref, const FString& Bone,
             const FVector& Start, const FVector& End, float Radius, float Mass)
{
    auto* Setup = Body(Asset, Bone, Mass);
    const FVector Direction = End - Start;
    const FQuat Rotation = FRotationMatrix::MakeFromZ(Direction.GetSafeNormal()).ToQuat();
    const FTransform World(Rotation, (Start + End) * .5f);
    FKSphylElem Shape(Radius, FMath::Max(1.f, static_cast<float>(Direction.Size()) - 2.f * Radius));
    Shape.SetTransform(World.GetRelativeTransform(Ref.Transform(Bone)));
    Setup->AggGeom.SphylElems.Add(Shape);
}

void Box(UPhysicsAsset* Asset, const FReferenceBody& Ref, const FString& Bone,
         const FVector& Center, const FQuat& Rotation, const FVector& Size, float Mass)
{
    auto* Setup = Body(Asset, Bone, Mass);
    FKBoxElem Shape(Size.X, Size.Y, Size.Z);
    Shape.SetTransform(FTransform(Rotation, Center).GetRelativeTransform(Ref.Transform(Bone)));
    Setup->AggGeom.BoxElems.Add(Shape);
}

void RoundedPalm(UPhysicsAsset* Asset, const FReferenceBody& Ref, const FString& Bone,
                 const FVector& Center, const FQuat& Rotation)
{
    auto* Setup = Body(Asset, Bone, .5f);
    // Symmetric convex approximation of a box with a 6 mm edge radius. The
    // palm keeps its 14 x 7.5 x 4 cm envelope and broad resting faces, while
    // removing the sharp corners of the old box. No extra collision bodies.
    constexpr double Radius = .6;
    const FVector InnerHalf = FVector(7, 3.75, 2) - FVector(Radius);
    FKConvexElem Shape;
    for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) for (int32 Z : {-1, 1})
        for (int32 Mask = 1; Mask < 8; ++Mask)
        {
            const FVector Direction = FVector((Mask & 1) ? X : 0,
                (Mask & 2) ? Y : 0, (Mask & 4) ? Z : 0).GetSafeNormal();
            Shape.VertexData.Add(InnerHalf * FVector(X, Y, Z) + Radius * Direction);
        }
    Shape.UpdateElemBox();
    Shape.SetTransform(FTransform(Rotation, Center).GetRelativeTransform(Ref.Transform(Bone)));
    Setup->AggGeom.ConvexElems.Add(Shape);
}

void Joint(UPhysicsAsset* Asset, const FReferenceBody& Ref, const FString& Child,
           const FString& Parent, const FVector& Position, const FQuat& WorldRotation,
           float Swing1, float Swing2, float Twist, float TwistCenter = 0.f, bool CenterTwistOnChild = false)
{
    auto* Template = NewObject<UPhysicsConstraintTemplate>(Asset, NAME_None, RF_Transactional);
    FConstraintInstance& C = Template->DefaultInstance;
    C.JointName = *Child;
    C.ConstraintBone1 = *Child;
    C.ConstraintBone2 = *Parent;
    const FTransform Frame(CenterTwistOnChild ? WorldRotation * FQuat(FVector::XAxisVector,
        FMath::DegreesToRadians(-TwistCenter)) : WorldRotation, Position);
    C.SetRefFrame(EConstraintFrame::Frame1, Frame.GetRelativeTransform(Ref.Transform(Child)));
    const FTransform ParentFrame(CenterTwistOnChild ? WorldRotation : WorldRotation *
        FQuat(FVector::XAxisVector, FMath::DegreesToRadians(TwistCenter)), Position);
    C.SetRefFrame(EConstraintFrame::Frame2, ParentFrame.GetRelativeTransform(Ref.Transform(Parent)));
    C.SetLinearLimits(LCM_Locked, LCM_Locked, LCM_Locked, 0.f);
    C.SetAngularSwing1Limit(Swing1 > 0 ? ACM_Limited : ACM_Locked, Swing1);
    C.SetAngularSwing2Limit(Swing2 > 0 ? ACM_Limited : ACM_Locked, Swing2);
    C.SetAngularTwistLimit(Twist > 0 ? ACM_Limited : ACM_Locked, Twist);
    C.SetDisableCollision(true);
    C.SetProjectionParams(true, .1f, .1f, 5.f, 30.f);
    C.EnableMassConditioning();
    C.SetParentDominates(false);
    Template->SetDefaultProfile(C);
    Asset->ConstraintSetup.Add(Template);
}
}
#endif

bool UOldWestAssetAuthoring::RefreshCrewSkeletonReference(USkeletalMesh* Mesh)
{
#if WITH_EDITOR
    if (!Mesh || !Mesh->GetSkeleton()) return false;
    const FString MeshName = Mesh->GetName();
    if (!MeshName.StartsWith(TEXT("SK_"))) return false;
    const auto* Entry = OldWestCrew::ForAssetName(TCHAR_TO_UTF8(*MeshName.Mid(3)));
    if (!Entry || Entry->Native || Mesh->GetPathName() != UTF8_TO_TCHAR(Entry->Mesh)) return false;
    const FString Directory = TEXT("/Game/Art/Western/Crew/") + FString(UTF8_TO_TCHAR(Entry->AssetName));
    USkeleton* Skeleton = Mesh->GetSkeleton();
    if (FPackageName::GetLongPackagePath(Mesh->GetOutermost()->GetName()) != Directory ||
        FPackageName::GetLongPackagePath(Skeleton->GetOutermost()->GetName()) != Directory) return false;

    // Reference transforms may be stale after FBX reimport, but this helper
    // never changes or merges a different bone hierarchy.
    const FReferenceSkeleton& MeshReference = Mesh->GetRefSkeleton();
    const FReferenceSkeleton& SkeletonReference = Skeleton->GetReferenceSkeleton();
    if (MeshReference.GetNum() != SkeletonReference.GetNum()) return false;
    for (int32 Index = 0; Index < MeshReference.GetNum(); ++Index)
    {
        if (MeshReference.GetBoneName(Index) != SkeletonReference.GetBoneName(Index) ||
            MeshReference.GetParentIndex(Index) != SkeletonReference.GetParentIndex(Index)) return false;
    }
    Skeleton->Modify();
    Skeleton->UpdateReferencePoseFromMesh(Mesh);
    Skeleton->MarkPackageDirty();
    for (int32 Index = 0; Index < MeshReference.GetNum(); ++Index)
    {
        if (!MeshReference.GetRefBonePose()[Index].Equals(
            Skeleton->GetReferenceSkeleton().GetRefBonePose()[Index], 0.001f)) return false;
    }
    return true;
#else
    return false;
#endif
}

UPhysicsAsset* UOldWestAssetAuthoring::CreateSurvivorPhysicsAsset(bool bReplaceExisting, bool bAnatomicalWristFrames, bool bDrifter, bool bQuanah, FString WesternCharacter)
{
#if WITH_EDITOR
    const TCHAR* SelectedMeshPath = bQuanah ? TEXT("/Game/Art/Western/Quanah/SK_Quanah.SK_Quanah") : bDrifter ? TEXT("/Game/Art/Western/Drifter/SK_Drifter.SK_Drifter") : MeshPath;
    const TCHAR* SelectedPackagePath = bQuanah ? TEXT("/Game/Art/Western/Quanah/PA_Quanah") : bDrifter ? TEXT("/Game/Art/Western/Drifter/PA_Drifter") : PackagePath;
    const TCHAR* SelectedAssetName = bQuanah ? TEXT("PA_Quanah") : bDrifter ? TEXT("PA_Drifter") : AssetName;
    FString WesternMesh, WesternPackage, WesternAsset;
    if (!WesternCharacter.IsEmpty())
    {
        FString Name = WesternCharacter;
        if (WesternCharacter.StartsWith(TEXT("Crew/")))
        {
            Name = WesternCharacter.Mid(5);
            const auto* Entry = OldWestCrew::ForAssetName(TCHAR_TO_UTF8(*Name));
            if (!Entry || Entry->Native) return nullptr;
        }
        else if (WesternCharacter != TEXT("Lozen") && WesternCharacter != TEXT("Sarah")) return nullptr;
        const FString Directory = TEXT("/Game/Art/Western/") + WesternCharacter + TEXT("/");
        WesternMesh = Directory + TEXT("SK_") + Name + TEXT(".SK_") + Name;
        WesternAsset = TEXT("PA_") + Name;
        WesternPackage = Directory + WesternAsset;
        SelectedMeshPath = *WesternMesh;
        SelectedPackagePath = *WesternPackage;
        SelectedAssetName = *WesternAsset;
    }
    auto* Mesh = LoadObject<USkeletalMesh>(nullptr, SelectedMeshPath);
    if (!Mesh) return nullptr;
    const FReferenceBody Ref(Mesh);
    const float TorsoSpan = FVector::Distance(Ref.Position(TEXT("Head")), Ref.Position(TEXT("Hips")));
    if (!ensureMsgf(TorsoSpan > 40.f && TorsoSpan < 80.f, TEXT("Survivor reference skeleton must have centimeter anatomy"))) return nullptr;
    UPackage* Package = CreatePackage(SelectedPackagePath);
    auto* Asset = LoadObject<UPhysicsAsset>(nullptr, *(FString(SelectedPackagePath) + TEXT(".") + SelectedAssetName));
    if (Asset && !bReplaceExisting) return Asset;
    if (!Asset) Asset = NewObject<UPhysicsAsset>(Package, SelectedAssetName, RF_Public | RF_Standalone | RF_Transactional);
    Asset->Modify();
    Asset->SkeletalBodySetups.Reset();
    Asset->ConstraintSetup.Reset();
    Asset->CollisionDisableTable.Reset();
    Asset->BodySetupIndexMap.Reset();
    Asset->BoundsBodies.Reset();
    Asset->SetPreviewMesh(Mesh, false);
    Asset->SolverType = EPhysicsAssetSolverType::World;

    const FVector Up = FVector::UpVector;
    FVector Forward = (Ref.Position(TEXT("LeftToeBase")) - Ref.Position(TEXT("LeftFoot")) +
                       Ref.Position(TEXT("RightToeBase")) - Ref.Position(TEXT("RightFoot"))).GetSafeNormal2D();
    if (Forward.IsNearlyZero()) Forward = FVector::ForwardVector;
    const FVector Lateral = FVector::CrossProduct(Up, Forward).GetSafeNormal();
    const FQuat TorsoRotation = FRotationMatrix::MakeFromXZ(Forward, Up).ToQuat();
    const FQuat HingeRotation = FRotationMatrix::MakeFromXZ(Lateral, Up).ToQuat();

    // Anatomy, not clothed render-vertex bounds: neither backpack nor goggles
    // contributes to collision size. No root/finger/clavicle physics bodies.
    Box(Asset, Ref, TEXT("Hips"), Ref.Position(TEXT("Hips")) - Up, TorsoRotation, FVector(20, 28, 16), 12.5f);
    Capsule(Asset, Ref, TEXT("Spine"), Ref.Position(TEXT("Spine")), Ref.Position(TEXT("Spine2")), 9.5f, 8.5f);
    const FVector Chest = FMath::Lerp(Ref.Position(TEXT("Spine2")), Ref.Position(TEXT("Neck")), .38f);
    Box(Asset, Ref, TEXT("Spine2"), Chest, TorsoRotation, FVector(20, 32, 23), 17.f);
    Capsule(Asset, Ref, TEXT("Head"), Ref.Position(TEXT("Head")) - Up * 3.f,
            Ref.Position(TEXT("Head")) + Up * 22.f, 8.3f, 4.5f);
    Joint(Asset, Ref, TEXT("Spine"), TEXT("Hips"), Ref.Position(TEXT("Spine")), TorsoRotation, 22, 18, 18);
    Joint(Asset, Ref, TEXT("Spine2"), TEXT("Spine"), Ref.Position(TEXT("Spine2")), TorsoRotation, 20, 18, 18);
    Joint(Asset, Ref, TEXT("Head"), TEXT("Spine2"), Ref.Position(TEXT("Neck")), TorsoRotation, 38, 32, 50);

    for (const FString& Side : {FString(TEXT("Left")), FString(TEXT("Right"))})
    {
        const FString Arm = Side + TEXT("Arm"), Forearm = Side + TEXT("ForeArm"), Hand = Side + TEXT("Hand");
        const FString Thigh = Side + TEXT("UpLeg"), Shin = Side + TEXT("Leg"), Foot = Side + TEXT("Foot");
        Capsule(Asset, Ref, Arm, Ref.Position(Arm), Ref.Position(Forearm), 4.8f, 2.2f);
        Capsule(Asset, Ref, Forearm, Ref.Position(Forearm), Ref.Position(Hand), 3.8f, 1.3f);
        const FVector HandEnd = Ref.Position(Side + TEXT("HandMiddle3"));
        const FVector HandAxis = (HandEnd - Ref.Position(Hand)).GetSafeNormal();
        const FQuat HandRotation = FRotationMatrix::MakeFromXZ(HandAxis, Forward).ToQuat();
        // Opt-in authoring candidate until native contact/pose review passes.
        if (FParse::Param(FCommandLine::Get(), TEXT("SurvivorRoundedPalms")))
            RoundedPalm(Asset, Ref, Hand, Ref.Position(Hand) + HandAxis * 6.f, HandRotation);
        else
            Box(Asset, Ref, Hand, Ref.Position(Hand) + HandAxis * 6.f, HandRotation, FVector(14, 7.5f, 4), .5f);
        Capsule(Asset, Ref, Thigh, Ref.Position(Thigh), Ref.Position(Shin), 7.f, 6.5f);
        Capsule(Asset, Ref, Shin, Ref.Position(Shin), Ref.Position(Foot), 5.f, 3.5f);
        const FVector ToeDirection = (Ref.Position(Side + TEXT("ToeBase")) - Ref.Position(Foot)).GetSafeNormal2D();
        const FQuat FootRotation = FRotationMatrix::MakeFromXZ(ToeDirection, Up).ToQuat();
        Box(Asset, Ref, Foot, Ref.Position(Foot) + ToeDirection * 6.f - Up * 4.f, FootRotation, FVector(28, 11, 9), 1.4f);

        const FVector ArmDirection = (Ref.Position(Forearm) - Ref.Position(Arm)).GetSafeNormal();
        const FVector ElbowAxis = FVector::CrossProduct(ArmDirection, Forward).GetSafeNormal();
        const FQuat ElbowRotation = FRotationMatrix::MakeFromXZ(ElbowAxis, ArmDirection).ToQuat();
        Joint(Asset, Ref, Arm, TEXT("Spine2"), Ref.Position(Arm), TorsoRotation, 80, 70, 65);
        // X is elbow flexion; Z follows the arm and allows forearm roll.
        // Chaos Swing1 rotates about Z. Locking both secondary axes to five
        // degrees rejected the supporting arm's pose and resisted pronation
        // during contact. Keep sideways bending narrow while admitting roll.
        // Shift the child frame for the anatomical elbow range. With
        // relative rotation Swing * Twist, a child X offset changes only
        // Twist; the existing narrow sideways cone and forearm roll remain
        // unchanged. A parent offset would rotate that elliptical swing cone.
        const bool OneWayElbows = !FParse::Param(FCommandLine::Get(), TEXT("SurvivorLegacyElbowRange"));
        Joint(Asset, Ref, Forearm, Arm, Ref.Position(Forearm), ElbowRotation, 80, 5,
            OneWayElbows ? 60.f : 115.f, OneWayElbows ? 55.f : 0.f, OneWayElbows);
        // Wrist axes follow the forearm/hand. The retargeted supporting hand
        // carries about 104 degrees of longitudinal roll at handoff, including
        // the source rig's forearm twist. Admit that authored pose so switching
        // to physics does not inject a large corrective wrist impulse.
        Joint(Asset, Ref, Hand, Forearm, Ref.Position(Hand), bAnatomicalWristFrames ? HandRotation : TorsoRotation, 60, 40, 110);
        Joint(Asset, Ref, Thigh, TEXT("Hips"), Ref.Position(Thigh), TorsoRotation, 65, 45, 35);
        // Positive twist around Up x Forward flexes the shin backward. The
        // old symmetric +/-115 degree limit also admitted a deeply reversed
        // knee. Center a 60 degree half-range at +55 for -5..115 degrees of
        // physical motion, without changing anchors or adding a pose drive.
        const bool OneWayKnees = !FParse::Param(FCommandLine::Get(), TEXT("SurvivorLegacyKneeRange"));
        Joint(Asset, Ref, Shin, Thigh, Ref.Position(Shin), HingeRotation, 5, 5,
            OneWayKnees ? 60.f : 115.f, OneWayKnees ? 55.f : 0.f);
        Joint(Asset, Ref, Foot, Shin, Ref.Position(Foot), TorsoRotation, 30, 20, 15);
    }

    Asset->UpdateBodySetupIndexMap();
    Asset->UpdateBoundsBodiesArray();
    // Suppress adjacent and immediately neighboring bodies, which meet at a
    // joint or overlap naturally when folded. Distant limbs can still collide.
    const int32 Count = Asset->SkeletalBodySetups.Num();
    TArray<TArray<int32>> Distance;
    for (int32 I = 0; I < Count; ++I) { TArray<int32> Row; Row.Init(100, Count); Row[I] = 0; Distance.Add(Row); }
    for (UPhysicsConstraintTemplate* C : Asset->ConstraintSetup)
    {
        const int32 A = Asset->FindBodyIndex(C->DefaultInstance.ConstraintBone1), B = Asset->FindBodyIndex(C->DefaultInstance.ConstraintBone2);
        Distance[A][B] = Distance[B][A] = 1;
    }
    for (int32 K = 0; K < Count; ++K) for (int32 I = 0; I < Count; ++I) for (int32 L = 0; L < Count; ++L)
        Distance[I][L] = FMath::Min(Distance[I][L], Distance[I][K] + Distance[K][L]);
    for (int32 I = 0; I < Count; ++I) for (int32 K = I + 1; K < Count; ++K)
        if (Distance[I][K] <= 2) Asset->DisableCollision(I, K);
    // Forearms do not meet the chest at a joint. Suppressing this pair lets
    // a folded forearm enter the chest while its hand and opposite arm still
    // collide, trapping the chain in an anatomically impossible pose.
    const int32 ChestIndex = Asset->FindBodyIndex(TEXT("Spine2"));
    for (const FName Forearm : {FName(TEXT("LeftForeArm")), FName(TEXT("RightForeArm"))})
        Asset->EnableCollision(Asset->FindBodyIndex(Forearm), ChestIndex);
    // The two thighs share a pelvis but do not meet at a joint. The blanket
    // two-link exclusion let them cross deeply and trap a shin against the
    // opposite leg during a fall. Keep their actual anatomical separation.
    Asset->EnableCollision(Asset->FindBodyIndex(TEXT("LeftUpLeg")), Asset->FindBodyIndex(TEXT("RightUpLeg")));
    for (USkeletalBodySetup* Setup : Asset->SkeletalBodySetups)
    {
        Setup->InvalidatePhysicsData();
        Setup->CreatePhysicsMeshes();
    }
    Asset->PostEditChange();
    Asset->MarkPackageDirty();
    return Asset;
#else
    return nullptr;
#endif
}

FString UOldWestAssetAuthoring::DescribeSurvivorPhysicsAsset(UPhysicsAsset* Asset)
{
#if WITH_EDITOR
    if (!Asset) return TEXT("{}");
    auto* Mesh = Asset->GetPreviewMesh();
    if (!Mesh) return TEXT("{}");
    const FReferenceBody Ref(Mesh);
    J Result = {{"asset", Utf8(Asset->GetPathName())}, {"body_count", Asset->SkeletalBodySetups.Num()},
        {"constraint_count", Asset->ConstraintSetup.Num()}, {"disabled_collision_pairs", Asset->CollisionDisableTable.Num()},
        {"disabled_collision_pair_names", J::array()}, {"forearm_chest_collision_enabled", J::object()},
        {"total_mass_kg", 0.f}, {"bodies", J::array()}, {"constraints", J::array()}};
    Result["reference_forward"] = Vector((Ref.Position(TEXT("LeftToeBase")) - Ref.Position(TEXT("LeftFoot")) +
        Ref.Position(TEXT("RightToeBase")) - Ref.Position(TEXT("RightFoot"))).GetSafeNormal2D());
    for (int32 A = 0; A < Asset->SkeletalBodySetups.Num(); ++A)
        for (int32 B = A + 1; B < Asset->SkeletalBodySetups.Num(); ++B)
            if (!Asset->IsCollisionEnabled(A, B))
                Result["disabled_collision_pair_names"].push_back({
                    Utf8(Asset->SkeletalBodySetups[A]->BoneName.ToString()),
                    Utf8(Asset->SkeletalBodySetups[B]->BoneName.ToString())});
    const int32 ChestIndex = Asset->FindBodyIndex(TEXT("Spine2"));
    Result["thigh_collision_enabled"] = Asset->IsCollisionEnabled(
        Asset->FindBodyIndex(TEXT("LeftUpLeg")), Asset->FindBodyIndex(TEXT("RightUpLeg")));
    for (const FName Forearm : {FName(TEXT("LeftForeArm")), FName(TEXT("RightForeArm"))})
    {
        const int32 ForearmIndex = Asset->FindBodyIndex(Forearm);
        Result["forearm_chest_collision_enabled"][Utf8(Forearm.ToString())] =
            ChestIndex != INDEX_NONE && ForearmIndex != INDEX_NONE && Asset->IsCollisionEnabled(ForearmIndex, ChestIndex);
    }
    float TotalMass = 0.f;
    for (USkeletalBodySetup* Setup : Asset->SkeletalBodySetups)
    {
        const FString Name = Setup->BoneName.ToString();
        const FBox Bounds = Setup->AggGeom.CalcAABB(Ref.Transform(Name));
        const float Mass = Setup->DefaultInstance.GetMassOverride();
        TotalMass += Mass;
        J Row = {{"bone", Utf8(Name)}, {"mass_kg", Mass}, {"reference_position_cm", Vector(Ref.Position(Name))},
            {"iteration_overrides_enabled", Setup->DefaultInstance.GetPositionSolverIterationCount() >= 0},
            {"position_solver_iterations", Setup->DefaultInstance.GetPositionSolverIterationCount()},
            {"velocity_solver_iterations", Setup->DefaultInstance.GetVelocitySolverIterationCount()},
            {"projection_solver_iterations", Setup->DefaultInstance.GetProjectionSolverIterationCount()},
            {"bounds_center_cm", Vector(Bounds.GetCenter())}, {"bounds_size_cm", Vector(Bounds.GetSize())},
            {"capsules", J::array()}, {"boxes", J::array()}, {"convexes", J::array()}};
        for (const auto& S : Setup->AggGeom.SphylElems)
            Row["capsules"].push_back({{"radius_cm", S.Radius}, {"cylinder_length_cm", S.Length},
                {"center_local_cm", Vector(S.Center)}, {"rotation_local_degrees", Vector(S.Rotation.Euler())}});
        for (const auto& S : Setup->AggGeom.BoxElems)
            Row["boxes"].push_back({{"size_cm", {S.X, S.Y, S.Z}}, {"center_local_cm", Vector(S.Center)},
                {"rotation_local_degrees", Vector(S.Rotation.Euler())}});
        for (const auto& S : Setup->AggGeom.ConvexElems)
        {
            J Vertices = J::array(), Indices = J::array();
            for (const FVector& V : S.VertexData) Vertices.push_back(Vector(V));
            const TArray<int32> HullIndices = S.GetChaosConvexIndices();
            for (int32 I : HullIndices) Indices.push_back(I);
            double SignedVolume = 0;
            for (int32 I = 0; I + 2 < HullIndices.Num(); I += 3)
                SignedVolume += FVector::DotProduct(S.VertexData[HullIndices[I]],
                    FVector::CrossProduct(S.VertexData[HullIndices[I + 1]], S.VertexData[HullIndices[I + 2]])) / 6.;
            Row["convexes"].push_back({{"vertices_cm", Vertices}, {"indices", Indices},
                {"size_cm", Vector(S.ElemBox.GetSize())},
                {"center_local_cm", Vector(S.GetTransform().GetLocation())},
                {"rotation_local_degrees", Vector(S.GetTransform().GetRotation().Euler())},
                {"volume_cm3", FMath::Abs(SignedVolume)}});
        }
        Result["bodies"].push_back(Row);
    }
    for (UPhysicsConstraintTemplate* Template : Asset->ConstraintSetup)
    {
        const auto& C = Template->DefaultInstance;
        const FQuat ChildWorld = (C.GetRefFrame(EConstraintFrame::Frame1) * Ref.Transform(C.ConstraintBone1.ToString())).GetRotation();
        const FQuat ParentWorld = (C.GetRefFrame(EConstraintFrame::Frame2) * Ref.Transform(C.ConstraintBone2.ToString())).GetRotation();
        const float NeutralTwist = FMath::RadiansToDegrees((ParentWorld.Inverse() * ChildWorld).GetTwistAngle(FVector::XAxisVector));
        Result["constraints"].push_back({{"child", Utf8(C.ConstraintBone1.ToString())}, {"parent", Utf8(C.ConstraintBone2.ToString())},
            {"swing1_degrees", C.GetAngularSwing1Limit()}, {"swing2_degrees", C.GetAngularSwing2Limit()},
            {"twist_degrees", C.GetAngularTwistLimit()}, {"adjacent_collision_disabled", C.IsCollisionDisabled()},
            {"child_frame_rotation_degrees", Vector(C.GetRefFrame(EConstraintFrame::Frame1).GetRotation().Euler())},
            {"parent_frame_rotation_degrees", Vector(C.GetRefFrame(EConstraintFrame::Frame2).GetRotation().Euler())},
            {"child_frame_reference_world_quaternion_xyzw", {ChildWorld.X, ChildWorld.Y, ChildWorld.Z, ChildWorld.W}},
            {"parent_frame_reference_world_quaternion_xyzw", {ParentWorld.X, ParentWorld.Y, ParentWorld.Z, ParentWorld.W}},
            {"reference_twist_axis", Vector(ChildWorld.RotateVector(FVector::XAxisVector))},
            {"neutral_twist_degrees", NeutralTwist},
            {"physical_twist_range_degrees", {-C.GetAngularTwistLimit() - NeutralTwist, C.GetAngularTwistLimit() - NeutralTwist}},
            {"projection_enabled", static_cast<bool>(C.ProfileInstance.bEnableProjection)}});
    }
    Result["total_mass_kg"] = TotalMass;
    const std::string Json = Result.dump();
    return FString(UTF8_TO_TCHAR(Json.c_str()));
#else
    return TEXT("{}");
#endif
}

#if WITH_EDITOR
namespace
{
    struct FLodDigest
    {
        FSHA1 Hash;
        template<typename T> void Add(const T& Value) { Hash.Update(reinterpret_cast<const uint8*>(&Value), sizeof(T)); }
        void Name(const FString& Value)
        {
            FTCHARToUTF8 Bytes(*Value);
            const int32 Length = Bytes.Length(); Add(Length);
            Hash.Update(reinterpret_cast<const uint8*>(Bytes.Get()), Length);
        }
        FString Finish()
        {
            Hash.Final(); uint8 Bytes[FSHA1::DigestSize]; Hash.GetHash(Bytes);
            return BytesToHex(Bytes, UE_ARRAY_COUNT(Bytes));
        }
    };
}
#endif

FString UOldWestAssetAuthoring::DescribeSurvivorLods()
{
#if WITH_EDITOR
    auto* Mesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
    if (!Mesh || !Mesh->GetImportedModel()) return TEXT("{}");
    J Report = {{"mesh", Utf8(Mesh->GetPathName())}, {"lods", J::array()},
        {"materials", J::array()}, {"skeleton", Utf8(Mesh->GetSkeleton()->GetPathName())}};
    for (const FSkeletalMaterial& Material : Mesh->GetMaterials())
        Report["materials"].push_back({{"slot", Utf8(Material.MaterialSlotName.ToString())},
            {"asset", Material.MaterialInterface ? Utf8(Material.MaterialInterface->GetPathName()) : ""}});
    FLodDigest SkeletonDigest;
    const FReferenceSkeleton& Skeleton = Mesh->GetRefSkeleton();
    for (int32 Bone = 0; Bone < Skeleton.GetNum(); ++Bone)
    {
        SkeletonDigest.Name(Skeleton.GetBoneName(Bone).ToString());
        SkeletonDigest.Add(Skeleton.GetParentIndex(Bone));
        const auto& Transform = Skeleton.GetRefBonePose()[Bone];
        const FVector P = Transform.GetLocation(), S = Transform.GetScale3D();
        const FQuat Q = Transform.GetRotation();
        for (double V : {P.X,P.Y,P.Z,S.X,S.Y,S.Z,Q.X,Q.Y,Q.Z,Q.W}) SkeletonDigest.Add(V);
    }
    Report["reference_skeleton_sha1"] = Utf8(SkeletonDigest.Finish());
    Report["reference_bones"] = Skeleton.GetNum();
    for (int32 Lod = 0; Lod < Mesh->GetImportedModel()->LODModels.Num(); ++Lod)
    {
        const auto& Model = Mesh->GetImportedModel()->LODModels[Lod];
        FLodDigest Geometry;
        int32 InvalidWeights = 0, InvalidBones = 0, NonFinite = 0, MaximumInfluences = 0;
        J Sections = J::array();
        for (const auto& Section : Model.Sections)
        {
            Geometry.Add(Section.MaterialIndex); Geometry.Add(Section.BaseIndex);
            Geometry.Add(Section.NumTriangles); Geometry.Add(Section.BaseVertexIndex);
            for (const auto Bone : Section.BoneMap) Geometry.Add(Bone);
            Sections.push_back({{"material",Section.MaterialIndex},{"triangles",Section.NumTriangles},
                {"vertices",Section.NumVertices},{"disabled",Section.bDisabled}});
            for (const FSoftSkinVertex& V : Section.SoftVertices)
            {
                Geometry.Add(V.Position); Geometry.Add(V.TangentX); Geometry.Add(V.TangentY); Geometry.Add(V.TangentZ);
                Geometry.Add(V.Color);
                for (int32 UV = 0; UV < static_cast<int32>(Model.NumTexCoords); ++UV) Geometry.Add(V.UVs[UV]);
                uint32 Sum = 0; int32 Influences = 0;
                for (int32 I = 0; I < UE_ARRAY_COUNT(V.InfluenceWeights); ++I)
                {
                    Geometry.Add(V.InfluenceWeights[I]); Geometry.Add(V.InfluenceBones[I]);
                    if (V.InfluenceWeights[I])
                    {
                        ++Influences; Sum += V.InfluenceWeights[I];
                        if (!Section.BoneMap.IsValidIndex(V.InfluenceBones[I]) ||
                            Section.BoneMap[V.InfluenceBones[I]] >= Skeleton.GetNum()) ++InvalidBones;
                    }
                }
                MaximumInfluences = FMath::Max(MaximumInfluences, Influences);
                if (FMath::Abs(static_cast<int32>(Sum) - 65535) > 16) ++InvalidWeights;
                if (V.Position.ContainsNaN() || V.TangentX.ContainsNaN() || V.TangentY.ContainsNaN() || V.TangentZ.ContainsNaN()) ++NonFinite;
            }
        }
        for (uint32 Index : Model.IndexBuffer) Geometry.Add(Index);
        J Morphs = J::object();
        for (const UMorphTarget* Morph : Mesh->GetMorphTargets())
        {
            FLodDigest DeltaDigest;
            const auto Deltas = Morph->GetMorphTargetDeltas(Lod);
            for (const FMorphTargetDelta& Delta : Deltas)
            {
                DeltaDigest.Add(Delta.SourceIdx); DeltaDigest.Add(Delta.PositionDelta); DeltaDigest.Add(Delta.TangentZDelta);
            }
            Morphs[Utf8(Morph->GetName())] = {{"deltas",Deltas.Num()},{"sha1",Utf8(DeltaDigest.Finish())}};
        }
        Report["lods"].push_back({{"lod",Lod},{"vertices",Model.NumVertices},{"triangles",Model.IndexBuffer.Num()/3},
            {"sections",Sections},{"geometry_weights_sha1",Utf8(Geometry.Finish())},{"morphs",Morphs},
            {"invalid_weight_vertices",InvalidWeights},{"invalid_bone_influences",InvalidBones},
            {"non_finite_vertices",NonFinite},{"max_influences",MaximumInfluences}});
    }
    const std::string Json = Report.dump();
    return FString(UTF8_TO_TCHAR(Json.c_str()));
#else
    return TEXT("{}");
#endif
}

AActor* UOldWestAssetAuthoring::CreateCrewWoundPreview(UObject* WorldContext, FString VisualId, FString Pose, float Phase, bool Concealed, AActor* Existing)
{
#if WITH_EDITOR
    UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    if (!World || (World->WorldType != EWorldType::Editor && World->WorldType != EWorldType::EditorPreview)) return nullptr;
    const auto* Crew = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*VisualId));
    if (!Crew && VisualId != TEXT("drifter")) return nullptr;
    if (Pose != TEXT("wounded") && Pose != TEXT("hit") && Pose != TEXT("attack") &&
        Pose != TEXT("walk") && Pose != TEXT("healthy") && Pose != TEXT("destroyed")) return nullptr;
    FActorSpawnParameters Parameters;
    Parameters.ObjectFlags |= RF_Transient;
    AOldWestUnit* Unit = Cast<AOldWestUnit>(Existing);
    if (Existing && (!Unit || Unit->GetWorld()!=World || !Unit->HasAnyFlags(RF_Transient) ||
        !Unit->IsPreviewOnly() || !Unit->Tags.Contains(TEXT("OldWestBandageReview")))) return nullptr;
    if (!Unit) Unit = World->SpawnActor<AOldWestUnit>(FVector::ZeroVector, FRotator::ZeroRotator, Parameters);
    if (!Unit) return nullptr;
    Unit->Tags.Add(TEXT("OldWestBandageReview"));
    Unit->SetPreviewOnly(true);
    const bool Drifter = Concealed || !Crew;
    Unit->Configure(900001, 0, Drifter ? TEXT("Drifter") : FString(UTF8_TO_TCHAR(Crew->Name)), false, Drifter,
        Drifter ? TEXT("punk") : FString(UTF8_TO_TCHAR(Crew->Canonical)), false, VisualId);
    Unit->SetCondition(1, false, true);
    if (Pose == TEXT("healthy")) Unit->SetCondition(0, false, true);
    else if (Pose == TEXT("destroyed")) Unit->SetCondition(1, true, false);
    else if (Pose == TEXT("hit")) Unit->PlayAction(TEXT("damage"));
    else if (Pose == TEXT("attack")) Unit->PlayAction(TEXT("attack"));
    else if (Pose == TEXT("walk")) Unit->StageTravel(FVector::ZeroVector, FVector(0,200,0), 2.f, false, true);
    if (Pose == TEXT("hit") || Pose == TEXT("attack") || Pose == TEXT("walk"))
        if (auto* Instance = Unit->Body->GetSingleNodeInstance())
        {
            Instance->SetPlaying(false);
            Instance->SetPlayRate(0.f);
            Instance->SetPosition(Instance->GetLength() * FMath::Clamp(Phase,0.f,1.f), false);
            Unit->Body->TickAnimation(0.f, false);
            Unit->Body->RefreshBoneTransforms();
        }
    Unit->Tick(0.f); // Same root compensation as gameplay; no elapsed game time.
    // CPU geometry extraction refreshes the leader pose. Preserve this exact
    // sampled local pose through that refresh and through screenshot rendering;
    // do not allow a second sequence evaluation to change the evidence frame.
    if (auto* Previous = Unit->Body->GetSingleNodeInstance())
    {
        UAnimationAsset* Asset = Previous->GetAnimationAsset();
        const float Position = Previous->GetCurrentTime();
        const bool Looping = Previous->IsLooping();
        const TArray<FTransform> SampledPose = Unit->Body->GetBoneSpaceTransforms();
        Unit->Body->SetAnimInstanceClass(UOldWestManualAnimInstance::StaticClass());
        if (auto* Frozen = Cast<UOldWestManualAnimInstance>(Unit->Body->GetAnimInstance()))
        {
            Frozen->SetAnimationAsset(Asset, Looping, 0.f);
            Frozen->EntryLocalPose = SampledPose;
            Frozen->EntryAlpha = 0.f;
            Frozen->SetPlaying(false);
            Frozen->SetPlayRate(0.f);
            Frozen->SetPosition(Position, false);
            Unit->Body->TickAnimation(0.f, false);
            Unit->Body->RefreshBoneTransforms();
        }
    }
    Unit->SetActorTickEnabled(false);
    Unit->Body->SetUpdateAnimationInEditor(false);
    Unit->Body->SetComponentTickEnabled(false);
    Unit->Body->SetForcedLOD(1);
    Unit->WoundBandage->SetForcedLOD(1);
    return Unit;
#else
    return nullptr;
#endif
}

FString UOldWestAssetAuthoring::DescribeCrewWoundPreview(AActor* Actor, bool IncludeGeometry)
{
#if WITH_EDITOR
    auto* Unit = Cast<AOldWestUnit>(Actor);
    if (!IsValid(Unit) || !Unit->HasAnyFlags(RF_Transient) || !Unit->Tags.Contains(TEXT("OldWestBandageReview")) ||
        !Unit->IsPreviewOnly() || !Unit->GetWorld() ||
        (Unit->GetWorld()->WorldType != EWorldType::Editor && Unit->GetWorld()->WorldType != EWorldType::EditorPreview)) return TEXT("{}");
    J Report = J::parse(TCHAR_TO_UTF8(*Unit->GetIdleDebug()));
    const bool Ready = Unit->Body->GetSkeletalMeshAsset() && !Unit->Body->GetSkeletalMeshAsset()->IsCompiling() &&
        Unit->WoundBandage->GetSkeletalMeshAsset() && !Unit->WoundBandage->GetSkeletalMeshAsset()->IsCompiling();
    Report["ready"] = Ready;
    Report["editor_preview_only"] = true;
    Report["bone_transforms"] = J::object();
    for (const FName Bone : {FName(TEXT("Hips")), FName(TEXT("LeftForeArm")), FName(TEXT("RightForeArm")), FName(TEXT("LeftHand")), FName(TEXT("RightHand"))})
    {
        const FTransform Transform = Unit->Body->GetSocketTransform(Bone, RTS_Component);
        const FVector P = Transform.GetTranslation();
        const FQuat Q = Transform.GetRotation();
        Report["bone_transforms"][TCHAR_TO_UTF8(*Bone.ToString())] = {P.X,P.Y,P.Z,Q.X,Q.Y,Q.Z,Q.W};
    }
    if (Ready && IncludeGeometry)
    {
        Report["geometry"] = J::object();
        for (const auto& Pair : {TPair<const char*,USkeletalMeshComponent*>("body",Unit->Body), {"bandage",Unit->WoundBandage}})
        {
            USkeletalMeshComponent* Component = Pair.Value;
            TArray<FFinalSkinVertex> Vertices;
            Component->GetCPUSkinnedVertices(Vertices,0);
            TArray<uint32> Indices;
            Component->GetSkeletalMeshAsset()->GetResourceForRendering()->LODRenderData[0].MultiSizeIndexContainer.GetIndexBuffer(Indices);
            J Positions = J::array(), Triangles = J::array();
            for (const auto& Vertex : Vertices)
            {
                const FVector P = (Component->GetComponentTransform().TransformPosition(FVector(Vertex.Position))-Unit->GetActorLocation())*.01;
                Positions.push_back({P.X,P.Y,P.Z});
            }
            for (int32 I=0; I+2<Indices.Num(); I+=3) Triangles.push_back({Indices[I],Indices[I+1],Indices[I+2]});
            Report["geometry"][Pair.Key] = {{"vertices",Positions},{"triangles",Triangles},{"space","actor-relative world-axis meters"}};
        }
    }
    return UTF8_TO_TCHAR(Report.dump().c_str());
#else
    return TEXT("{}");
#endif
}
