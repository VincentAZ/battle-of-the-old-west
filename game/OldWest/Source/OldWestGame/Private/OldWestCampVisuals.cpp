#include "OldWestCampVisuals.h"
#include "OldWestFireVisuals.h"
#include "OldWestHoldingsCatalog.h"
#include "OldWestExpansionHoldings.h"
#include "OldWestRegion.h"
#include "EngineUtils.h"
#include "Misc/PackageName.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/RotationMatrix.h"
#include "Misc/Paths.h"

namespace
{
constexpr const TCHAR* Steel = TEXT("DarkSteel");
constexpr const TCHAR* Rust = TEXT("CorrodedSteel");
constexpr const TCHAR* Zinc = TEXT("Galvanized");
constexpr const TCHAR* Concrete = TEXT("Concrete");
constexpr const TCHAR* Canvas = TEXT("DustCanvas");
constexpr const TCHAR* Wood = TEXT("Wood");
constexpr const TCHAR* Copper = TEXT("Copper");
constexpr const TCHAR* Teal = TEXT("FadedTurquoise");
constexpr const TCHAR* Red = TEXT("FadedRose");
constexpr const TCHAR* Glass = TEXT("SmokedGlass");
constexpr const TCHAR* Rubber = TEXT("Rubber");
constexpr const TCHAR* Chalk = TEXT("StencilledChalk");
constexpr const TCHAR* Lamp = TEXT("AmberLamp");
constexpr const TCHAR* Signal = TEXT("StatusLight");
constexpr const TCHAR* RockMesh = TEXT("/Game/Art/WaterDepotV2/Meshes/SM_rock_07.SM_rock_07");
constexpr const TCHAR* FlameMaterial = TEXT("/Game/Art/CardPortraits/M_Portrait_Flame.M_Portrait_Flame");

FString DetailMesh(const TCHAR* Name)
{
    return FString(TEXT("/Game/Art/Camps/Meshes/SM_Camp_")) + Name + TEXT(".SM_Camp_") + Name;
}
}

UOldWestCampVisuals::UOldWestCampVisuals()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 1.f / 30.f;
}

UMaterialInterface* UOldWestCampVisuals::Material(const TCHAR* Name)
{
    if (!Name || !*Name) return nullptr;
    const FString Key(Name);
    if (const auto* Existing = Materials.Find(Key)) return Existing->Get();
    const FString ObjectName = TEXT("M_Camp_") + Key;
    const FString ObjectPath = Key.StartsWith(TEXT("/")) ? Key :
        TEXT("/Game/Art/Camps/Materials/") + ObjectName + TEXT(".") + ObjectName;
    UMaterialInterface* Result = LoadObject<UMaterialInterface>(nullptr, *ObjectPath);
    if (!Result) UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing material %s"), *DesignId, Name);
    if (Result && Key == FlameMaterial)
    {
        UMaterialInstanceDynamic* Instance = UMaterialInstanceDynamic::Create(Result, this);
        // The battlefield uses physical daylight exposure. Portrait capture
        // explicitly overrides this parameter for its much softer studio lights.
        Instance->SetScalarParameterValue(TEXT("EmissionScale"), 350.f);
        Result = Instance;
    }
    Materials.Add(Key, Result);
    return Result;
}

UMaterialInterface* UOldWestCampVisuals::ScorchedMaterial(UMaterialInterface* Source)
{
    if (!Source) return nullptr;
    // Preserve the existing authored bark/leaf response. The same rule also
    // applies to bark slots inside imported multi-material Logging Camp logs.
    const FString Name = Source->GetName();
    if (Name == TEXT("M_Camp_TreeBark")) return Material(TEXT("TreeChar"));
    if (Name == TEXT("M_Camp_TreeChar") || Name == TEXT("M_Camp_DryLeaf") ||
        Name == TEXT("M_Camp_Burnt")) return Source;
    if (Name == TEXT("M_Camp_TreeLeaf")) return Material(TEXT("DryLeaf"));
    const FString Key = Source->GetPathName() + (Ruined ? TEXT("_Ruin") : TEXT(""));
    if (const auto* Existing = ScorchedMaterials.Find(Key))
        return Existing->Get() ? Existing->Get() : Source;
    const FString ObjectName = (Ruined ? TEXT("M_Ruin_") : TEXT("M_Soot_")) + Name;
    const FString Path = Name.StartsWith(TEXT("M_Holding_")) ?
        FPaths::GetPath(Source->GetPathName()) + TEXT("/Conditions/") + ObjectName + TEXT(".") + ObjectName :
        (Ruined ? TEXT("/Game/Art/Camps/Ruins/") : TEXT("/Game/Art/Camps/Conditions/")) + ObjectName + TEXT(".") + ObjectName;
    UMaterialInterface* Result = LoadObject<UMaterialInterface>(nullptr, *Path);
    if (!Result)
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing scorch variant for %s"), *DesignId, *Key);
    ScorchedMaterials.Add(Key, Result);
    // A missing authored variant remains an explicit test failure; preserve
    // the source surface rather than introducing unrelated rust as fallback.
    return Result ? Result : Source;
}

int32 UOldWestCampVisuals::Part(const TCHAR* Mesh, const FVector& P, const FVector& D,
                               const TCHAR* M, const FRotator& R)
{
    const FString Key(Mesh);
    UStaticMesh* Asset = nullptr;
    if (const auto* Existing = Meshes.Find(Key)) Asset = Existing->Get();
    else
    {
        const FString Path = Key.StartsWith(TEXT("/")) ? Key : TEXT("/Engine/BasicShapes/") + Key + TEXT(".") + Key;
        Asset = LoadObject<UStaticMesh>(nullptr, *Path);
        Meshes.Add(Key, Asset);
    }
    if (!Asset || !GetOwner())
    {
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing mesh %s"), *DesignId, Mesh);
        return INDEX_NONE;
    }
    UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(GetOwner());
    GetOwner()->AddInstanceComponent(Component);
    Component->SetupAttachment(this);
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetStaticMesh(Asset);
    const FBox Bounds = Asset->GetBoundingBox();
    const FVector Size = Bounds.GetSize().ComponentMax(FVector(0.01));
    const FVector Scale = D / Size;
    Component->SetRelativeTransform(FTransform(R, P - R.RotateVector(Bounds.GetCenter() * Scale), Scale));
    // The same physical grain scale applies to a small bolt and a full wall.
    // Object-space mapping follows moving machinery instead of swimming over it.
    Component->SetCustomPrimitiveDataVector3(0, Scale.GetAbs());
    Component->SetCustomPrimitiveDataVector3(4, D.GetAbs() * .5);
    if (M && *M) for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot) Component->SetMaterial(Slot, Material(M));
    Component->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Component->SetCollisionResponseToAllChannels(ECR_Ignore);
    Component->SetCollisionResponseToChannel(ECC_Camera, ECR_Block);
    Component->SetGenerateOverlapEvents(false);
    Component->SetCanEverAffectNavigation(false);
    Component->RegisterComponent();
    const int32 Index = Parts.Add(Component);
    RestTransforms.Add(Component->GetRelativeTransform());
    ConditionIndices.Add(NextConditionIndex++);
    RestMaterials.Add(M ? FString(M) : FString());
    RestSlotOffsets.Add(RestSlotMaterials.Num());
    for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot)
        RestSlotMaterials.Add(Component->GetMaterial(Slot));
    return Index;
}

int32 UOldWestCampVisuals::Box(const FVector& P, const FVector& D, const TCHAR* M, const FRotator& R)
{
    const FVector Size = D.GetAbs();
    const int32 LongAxis = Size.X >= Size.Y && Size.X >= Size.Z ? 0 : Size.Y >= Size.Z ? 1 : 2;
    const int32 ShortAxis = Size.X <= Size.Y && Size.X <= Size.Z ? 0 : Size.Y <= Size.Z ? 1 : 2;
    const float Middle = static_cast<float>(Size.X + Size.Y + Size.Z - Size[LongAxis] - Size[ShortAxis]);
    const TCHAR* Beams[] = {TEXT("BevelBeamX"), TEXT("BevelBeamY"), TEXT("BevelBeamZ")};
    const TCHAR* Panels[] = {TEXT("BevelPanelX"), TEXT("BevelPanelY"), TEXT("BevelPanelZ")};
    const TCHAR* Shape = Size[LongAxis] > Middle * 3.5f ? Beams[LongAxis] :
        Middle > Size[ShortAxis] * 3.5f ? Panels[ShortAxis] : TEXT("BevelBlock");
    return Part(*DetailMesh(Shape), P, D, M, R);
}
int32 UOldWestCampVisuals::Drum(const FVector& P, float D, float H, const TCHAR* M, const FRotator& R)
{
    const TCHAR* Shape = H > D * 3.f ? TEXT("BevelPipe") : H < D * .2f ? TEXT("BevelDisc") : TEXT("BevelCylinder");
    return Part(*DetailMesh(Shape), P, FVector(D, D, H), M, R);
}
int32 UOldWestCampVisuals::Orb(const FVector& P, const FVector& D, const TCHAR* M)
{ return Part(TEXT("Sphere"), P, D, M); }
int32 UOldWestCampVisuals::Cone(const FVector& P, float D, float H, const TCHAR* M)
{ return Part(TEXT("Cone"), P, FVector(D, D, H), M); }

void UOldWestCampVisuals::Beam(const FVector& A, const FVector& B, float W, const TCHAR* M)
{
    Box((A + B) * .5, FVector(W, W, FVector::Distance(A, B)), M,
        FQuat::FindBetweenNormals(FVector::UpVector, (B - A).GetSafeNormal()).Rotator());
}
void UOldWestCampVisuals::Pipe(const FVector& A, const FVector& B, float D, const TCHAR* M)
{
    Drum((A + B) * .5, D, FVector::Distance(A, B), M,
        FQuat::FindBetweenNormals(FVector::UpVector, (B - A).GetSafeNormal()).Rotator());
}
void UOldWestCampVisuals::Move(int32 I, EMotion Kind, const FVector& Axis, float Speed,
                               float Amplitude, const FVector& Pivot, float Phase)
{
    if (!Parts.IsValidIndex(I)) return;
    Motions.Add({I, Kind, Axis.GetSafeNormal(), Pivot, Speed, Amplitude, Phase});
}

void UOldWestCampVisuals::Frame(const FVector& P, const FVector& S, const TCHAR* M, bool Roof)
{
    // Explicit authored metal-shell scope; canvas, masonry and wooden camps
    // retain their existing construction and camp-specific roof/landmarks.
    const bool DetailedDesign = DesignId == TEXT("saloon") || DesignId == TEXT("livery_barn") ||
        DesignId == TEXT("bunkhouse") || DesignId == TEXT("cattle_ranch") || DesignId == TEXT("bordello") ||
        DesignId == TEXT("stagecoach_station") || DesignId == TEXT("general_store") || DesignId == TEXT("barn_raising") ||
        DesignId == TEXT("freight_warehouse") || DesignId == TEXT("gunsmith") || DesignId == TEXT("revival_tent") ||
        DesignId == TEXT("post_office") || DesignId == TEXT("rustlers_corral") || DesignId == TEXT("pony_express_station") ||
        DesignId == TEXT("cattlemen_s_club") || DesignId == TEXT("smuggler_s_landing");
    const FString Cladding(M ? M : TEXT(""));
    const bool MetalCladding = Cladding == Steel || Cladding == Zinc || Cladding == Rust ||
        Cladding == Teal || Cladding == Red || Cladding == TEXT("ClinicPaint");
    if (DetailedDesign && MetalCladding)
    {
        const int32 ConditionStart = NextConditionIndex;
        const auto Module = [this, ConditionStart, M](const TCHAR* Name, const FVector& Location,
            const FVector& Size, int32 LegacyIndex, bool Paint = false, const FRotator& Rotation = FRotator::ZeroRotator)
        {
            const FString AssetName = FString(TEXT("SM_Shelter_")) + Name;
            const FString Path = TEXT("/Game/Art/Camps/ShelterStudy/Meshes/") + AssetName + TEXT(".") + AssetName;
            const int32 Index = Part(*Path, Location, Size, nullptr, Rotation);
            if (!Parts.IsValidIndex(Index)) return;
            ConditionIndices[Index] = ConditionStart + LegacyIndex;
            if (!Paint) return;
            // Change only the authored skin slot. Rails, patches and fasteners
            // keep their metal families; every actual source pointer is stored
            // for the existing reversible per-slot soot/repair policy.
            UStaticMeshComponent* Component = Parts[Index];
            for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot)
            {
                UMaterialInterface* Source = Component->GetMaterial(Slot);
                if (Source && Source->GetName() == TEXT("M_Camp_FadedTurquoise"))
                {
                    UMaterialInterface* Surface = Material(M);
                    Component->SetMaterial(Slot, Surface);
                    RestSlotMaterials[RestSlotOffsets[Index] + Slot] = Surface;
                }
            }
        };
        Module(TEXT("ConcreteBase"), P + FVector(0, 0, 7), FVector(S.X + 14, S.Y + 14, 14), 0);
        int32 ColumnIndex = 1;
        for (int32 X : {-1, 1}) for (int32 Y : {-1, 1})
        {
            const FString Name = FString(TEXT("Column_")) + (X < 0 ? TEXT("N_") : TEXT("P_")) +
                (Y < 0 ? TEXT("N") : TEXT("P"));
            Module(*Name, P + FVector(X * S.X * .5 - .075, Y * S.Y * .5, S.Z * .5),
                FVector(10.15, 10, S.Z - 1.6), ColumnIndex++);
        }
        Module(TEXT("BackCladding"), P + FVector(0, S.Y * .5 + .15, S.Z * .48),
            FVector(S.X - 6.5, 8.2, S.Z * .96), 5, true);
        Module(TEXT("LeftCladding"), P + FVector(-S.X * .5 - .15, 0, S.Z * .48),
            FVector(8.2, S.Y - 6.5, S.Z * .96), 6, true);
        Module(TEXT("RightCladding"), P + FVector(S.X * .5 + .15, 0, S.Z * .48),
            FVector(8.2, S.Y - 6.5, S.Z * .96), 7, true);
        if (Roof)
        {
            Module(TEXT("RoofAssembly"), P + FVector(0, 0, S.Z - .775),
                FVector(S.X + 28, S.Y + 28, 5.05), 8, false, FRotator(0, 0, -3));
            Module(TEXT("SideRoofRail_N"), P + FVector(-S.X * .5, 0, S.Z - 4), FVector(4, S.Y, 4.5), 9);
            Module(TEXT("SideRoofRail_P"), P + FVector(S.X * .5, 0, S.Z - 4), FVector(4, S.Y, 4.5), 10);
        }
        // The old helper contributes 19 logical condition slots, or 16 with
        // a caller-owned roof. Preserve later landmarks' exact scorch choices,
        // lean directions and rubble offsets without invisible placeholder parts.
        NextConditionIndex = ConditionStart + (Roof ? 19 : 16);
        return;
    }
    Box(P + FVector(0, 0, 7), FVector(S.X + 14, S.Y + 14, 14), Concrete);
    for (int32 X : {-1, 1}) for (int32 Y : {-1, 1})
        Box(P + FVector(X * S.X * .5, Y * S.Y * .5, S.Z * .5), FVector(10, 10, S.Z), Steel);
    Box(P + FVector(0, S.Y * .5, S.Z * .48), FVector(S.X, 9, S.Z * .96), M);
    for (int32 X : {-1, 1}) Box(P + FVector(X * S.X * .5, 0, S.Z * .48), FVector(9, S.Y, S.Z * .96), M);
    if (Roof)
    {
        Part(*DetailMesh(TEXT("CorrugatedSheet")), P + FVector(0, 0, S.Z), FVector(S.X + 28, S.Y + 28, 7), Zinc, FRotator(0, 0, -3));
        for (int32 Y : {-1, 1})
            Box(P + FVector(0, Y * (S.Y * .5 + 12), S.Z - 3), FVector(S.X + 28, 5, 10), Steel);
    }
    // Front corner straps, bolt heads and panel returns give the open shelter
    // actual assembly scale without hiding its camp-specific machinery.
    for (int32 X : {-1, 1})
    {
        Box(P + FVector(X * S.X * .5, -S.Y * .5 - 2, S.Z * .5), FVector(15, 3, S.Z - 10), Steel);
        for (float Z : {.16f, .51f, .86f})
            Drum(P + FVector(X * S.X * .5, -S.Y * .5 - 4.5f, S.Z * Z), 3.5f, 2.f, Zinc, FRotator(0, 0, 90));
    }
}

void UOldWestCampVisuals::Tank(const FVector& P, float D, float H, const TCHAR* M)
{
    Drum(P + FVector(0, 0, H * .5), D, H, M);
    for (float Z : {.12f, .82f}) Drum(P + FVector(0, 0, H * Z), D + 4, 5, Steel);
    Orb(P + FVector(0, 0, H), FVector(D, D, D * .3), M);
    Drum(P + FVector(0, 0, H + D * .18), D * .24, 8, Steel);
    Pipe(P + FVector(D * .4, 0, 20), P + FVector(D * .8, 0, 20), 10, Copper);
}

void UOldWestCampVisuals::Wheel(const FVector& P, float D, bool Spin)
{
    Drum(P, D, 17, Rubber, FRotator(90, 0, 0));
    const int32 Hub = Drum(P + FVector(11, 0, 0), D * .52, 8, Zinc, FRotator(90, 0, 0));
    if (Spin) Move(Hub, EMotion::Rotate, FVector::ForwardVector, 60, 1, P);
    for (int32 I = 0; I < 3; ++I)
    {
        const int32 Spoke = Box(P + FVector(16, 0, 0), FVector(6, D * .65, 5), Rust, FRotator(0, 0, I * 60));
        if (Spin) Move(Spoke, EMotion::Rotate, FVector::ForwardVector, 60, 1, P);
    }
}

void UOldWestCampVisuals::Fan(const FVector& P, float D, float Speed, const FRotator& R)
{
    const FVector Axis = R.RotateVector(FVector::UpVector);
    Drum(P, D * .18, 10, Steel, R);
    for (int32 I = 0; I < 4; ++I)
    {
        const FRotator BladeRotation = (R.Quaternion() * FQuat(FVector::UpVector, I * UE_PI * .5)).Rotator();
        const FVector Offset = BladeRotation.RotateVector(FVector(D * .25, 0, 0));
        const int32 Blade = Box(P + Offset, FVector(D * .46, D * .13, 5), Zinc, BladeRotation);
        Move(Blade, EMotion::Rotate, Axis, Speed, 1, P);
    }
}

void UOldWestCampVisuals::Flag(const FVector& P, float H, const TCHAR* M)
{
    Pipe(P, P + FVector(0, 0, H), 5, Steel);
    const FVector Pivot = P + FVector(0, 0, H - 24);
    for (int32 I = 0; I < 3; ++I)
    {
        const int32 Cloth = Box(Pivot + FVector(15 + I * 29, 0, -I * 3), FVector(30, 2, 44 - I * 5), M);
        Move(Cloth, EMotion::Sway, FVector::UpVector, 1.9f, 5.f + I * 2.f, Pivot, I * .45f);
    }
}

void UOldWestCampVisuals::Fire(const FVector& P, float S, bool IncludePrimitiveFuel)
{
    for (int32 I = 0; IncludePrimitiveFuel && I < 5; ++I)
    {
        const float A = I * 2.f * UE_PI / 5.f;
        Pipe(P + FVector(FMath::Cos(A) * S * .6, FMath::Sin(A) * S * .6, 3), P + FVector(-FMath::Cos(A) * S * .6, -FMath::Sin(A) * S * .6, 11), S * .15, TEXT("Burnt"));
    }
    UOldWestFireVisuals* Fire = NewObject<UOldWestFireVisuals>(GetOwner());
    GetOwner()->AddInstanceComponent(Fire);
    Fire->SetupAttachment(this);
    Fire->SetRelativeLocation(P + FVector(0, 0, 2));
    Fire->RegisterComponent();
    // Furnace fire stays in its reviewed chamber; it does not emit smoke
    // through the shell. Outdoor fires have sparse rising smoke layers.
    Fire->Build(S, S * 1.3f, P.X * .013f + P.Y * .011f, 350.f, DesignId != TEXT("pawn_shop"));
    // Daylight camera exposure needs more flame radiance than the preview
    // stage. Keep smoke at its existing level; portrait adaptation resets both.
    Fire->SetEmissionScale(900.f, 350.f);
    Fires.Add(Fire);
}

void UOldWestCampVisuals::Antenna(const FVector& P, float H, bool Scan)
{
    Pipe(P, P + FVector(0, 0, H), 7, Steel);
    for (int32 I : {-1, 1}) Beam(P + FVector(I * 50, 0, 0), P + FVector(0, 0, H * .7), 3, Steel);
    const FVector Pivot = P + FVector(0, 0, H);
    const int32 Array = Box(Pivot, FVector(95, 8, 36), Zinc, FRotator(0, 0, 12));
    if (Scan) Move(Array, EMotion::Sway, FVector::UpVector, .45, 58, Pivot);
    else for (int32 I = -2; I <= 2; ++I) Box(Pivot + FVector(I * 17, 0, 18), FVector(3, 3, 50 - FMath::Abs(I) * 10), Zinc);
    Orb(Pivot + FVector(0, 0, 35), FVector(9), Signal);
}

void UOldWestCampVisuals::Crates(const FVector& P, int32 N)
{
    for (int32 I = 0; I < N; ++I)
    {
        const FVector C = P + FVector((I % 3) * 48, (I / 3 % 2) * 44, 22 + (I / 6) * 45);
        Part(*DetailMesh(TEXT("PlankCrate")), C, FVector(43, 40, 42), Wood);
        for (int32 S : {-1, 1}) Box(C + FVector(S * 14, 0, 0), FVector(2, 42, 44), Steel);
    }
}

void UOldWestCampVisuals::Fence(const FVector& A, const FVector& B, float H)
{
    const int32 N = FMath::Max(1, FMath::CeilToInt(FVector::Distance(A, B) / 65.f));
    for (int32 I = 0; I <= N; ++I) Pipe(FMath::Lerp(A, B, float(I) / N), FMath::Lerp(A, B, float(I) / N) + FVector(0, 0, H), 5, Rust);
    for (float Z : {.3f, .7f, 1.f}) Pipe(A + FVector(0, 0, H * Z), B + FVector(0, 0, H * Z), 3, Steel);
}

void UOldWestCampVisuals::Cross(const FVector& P, float S)
{
    Box(P, FVector(S * .25, 5, S), Red);
    Box(P, FVector(S, 6, S * .25), Red);
}

void UOldWestCampVisuals::Tree(const FVector& P, float H, const TCHAR* /*Foliage*/)
{
    // Each literal camp theme has its own plant silhouette. All pieces share
    // the authored root pivot; imported bounds preserve their assembly even
    // when the FBX coordinate conversion mirrors a horizontal axis.
    const TCHAR* Kind = nullptr;
    int32 CanopyCount = 0;
    if (DesignId == TEXT("hot_springs")) { Kind = TEXT("Sapling"); CanopyCount = 3; }
    else if (DesignId == TEXT("trading_post")) { Kind = TEXT("Palm"); CanopyCount = 4; }
    else if (DesignId == TEXT("boot_hill")) { Kind = TEXT("DeadTree"); }
    else if (DesignId == TEXT("quaker_settlement")) { Kind = TEXT("Broadleaf"); CanopyCount = 4; }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: unauthored tree theme %s"), *DesignId);
        return;
    }
    TArray<FString> Paths;
    TArray<UStaticMesh*> Assets;
    FBox TreeBounds(ForceInit);
    for (int32 I = 0; I <= CanopyCount; ++I)
    {
        const FString Suffix = I == 0 ? FString(TEXT("Trunk")) : FString::Printf(TEXT("Foliage%d"), I);
        const FString Name = FString(Kind) + Suffix;
        const FString Path = DetailMesh(*Name);
        UStaticMesh* Asset = LoadObject<UStaticMesh>(nullptr, *Path);
        if (!Asset)
        {
            UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing foliage kit %s"), *DesignId, *Path);
            return;
        }
        Paths.Add(Path); Assets.Add(Asset); Meshes.Add(Path, Asset);
        TreeBounds += Asset->GetBoundingBox();
    }
    const float Scale = H / FMath::Max(1.f, static_cast<float>(TreeBounds.GetSize().Z));
    const FVector GroundOffset(0, 0, -TreeBounds.Min.Z);
    const FRotator Rotation(0, FMath::Fmod(P.X * .31f + P.Y * .17f, 360.f), 0);
    for (int32 I = 0; I < Assets.Num(); ++I)
    {
        const FBox Bounds = Assets[I]->GetBoundingBox();
        const FVector Center = P + Rotation.RotateVector((Bounds.GetCenter() + GroundOffset) * Scale);
        const int32 Index = Part(*Paths[I], Center, Bounds.GetSize() * Scale,
            I == 0 ? TEXT("TreeBark") : TEXT("TreeLeaf"), Rotation);
        if (I > 0 && Parts.IsValidIndex(Index))
        {
            FoliageParts.Add(Index);
            // Separate canopy groups move a fraction of a degree while the
            // leaf shader bends individual free tips without moving their base.
            Move(Index, EMotion::Sway, FVector::RightVector, .8f + I * .09f, .55f,
                P + FVector(0, 0, H * .61f), I * 1.1f + P.X * .013f);
        }
    }
}

void UOldWestCampVisuals::Vehicle(const FVector& P, bool Armoured)
{
    Box(P + FVector(0, 0, 70), FVector(160, 260, 50), Armoured ? Steel : Teal);
    Box(P + FVector(0, -35, 128), FVector(142, 110, 68), Armoured ? Rust : Teal);
    Box(P + FVector(0, -92, 137), FVector(118, 4, 30), Glass);
    for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) Wheel(P + FVector(X * 83, Y * 84, 43), 73);
    Box(P + FVector(0, -140, 57), FVector(185, 16, 18), Zinc);
    for (int32 X : {-1, 1}) Orb(P + FVector(X * 56, -137, 88), FVector(18, 7, 18), Lamp);
    if (Armoured) for (int32 X : {-1, 1}) Beam(P + FVector(X * 65, -150, 50), P + FVector(X * 95, -185, 25), 14, Rust);
}

void UOldWestCampVisuals::Bed(const FVector& P, const TCHAR* M)
{
    for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) Box(P + FVector(X * 31, Y * 64, 22), FVector(6, 6, 44), Zinc);
    Box(P + FVector(0, 0, 47), FVector(68, 142, 12), M);
    Box(P + FVector(0, 43, 56), FVector(50, 32, 8), Chalk);
}

void UOldWestCampVisuals::Torus(const FVector& P, float D, float Tube, const TCHAR* M, const FRotator& R)
{
    Part(*DetailMesh(Tube / D < .04f ? TEXT("RingThin") : TEXT("Ring")), P,
         FVector(D + Tube, D + Tube, Tube), M, R);
}

TArray<FString> UOldWestCampVisuals::GetSupportedCampIds()
{
    return {
        TEXT("saloon"), TEXT("livery_barn"), TEXT("hot_springs"), TEXT("silver_mine"), TEXT("logging_camp"),
        TEXT("stockyards"), TEXT("army_fort"), TEXT("dynamite_shack"), TEXT("bunkhouse"), TEXT("roundup_corral"),
        TEXT("cattle_ranch"), TEXT("riverboat"), TEXT("railroad_work_camp"), TEXT("toll_bridge"), TEXT("undertaker"),
        TEXT("bordello"), TEXT("trading_post"), TEXT("land_office"), TEXT("telegraph_office"), TEXT("stagecoach_station"),
        TEXT("railroad_depot"), TEXT("homestead_cabin"), TEXT("gatling_emplacement"), TEXT("powder_magazine"), TEXT("church_bell_tower"),
        TEXT("salvage_yard"), TEXT("artillery_battery"), TEXT("general_store"), TEXT("bare_knuckle_ring"), TEXT("breaking_pen"),
        TEXT("barn_raising"), TEXT("rodeo_grounds"), TEXT("freight_warehouse"), TEXT("mountain_hideout"),
        TEXT("gunsmith"), TEXT("jailhouse"), TEXT("robbers_roost"), TEXT("timber_ram"), TEXT("smuggler_s_landing"),
        TEXT("rockslide_ridge"), TEXT("bounty_office"), TEXT("packer_s_cabin"), TEXT("revival_tent"), TEXT("vigilance_committee"),
        TEXT("courthouse"), TEXT("post_office"), TEXT("army_surgeon_s_tent"), TEXT("wagon_fort"), TEXT("free_homestead"),
        TEXT("coal_yard"), TEXT("gallows"), TEXT("pawn_shop"), TEXT("nitro_works"), TEXT("crimp_house"),
        TEXT("wanted_poster_board"), TEXT("boot_hill"), TEXT("boarding_house"), TEXT("rustlers_corral"), TEXT("quaker_settlement"),
        TEXT("chuckwagon"), TEXT("horse_trader"), TEXT("pony_express_station"), TEXT("lookout_ridge"), TEXT("dance_hall"),
        TEXT("apothecary"), TEXT("cattlemen_s_club")
    };
}

void UOldWestCampVisuals::Build(const FString& CardId)
{
    if (GroundRegion.IsValid())
        GroundRegion->SetLandingFoundation(this,FVector::ZeroVector,FVector::ZeroVector,false);
    if(IsValid(RuinSmoke))RuinSmoke->DestroyComponent();
    RuinSmoke=nullptr;
    for (UOldWestFireVisuals* Fire : DamageFires) if (IsValid(Fire)) Fire->DestroyComponent();
    DamageFires.Reset();
    for (UOldWestFireVisuals* Fire : Fires) if (IsValid(Fire)) Fire->DestroyComponent();
    Fires.Reset();
    for (UStaticMeshComponent* Component : Parts) if (IsValid(Component)) Component->DestroyComponent();
    for (UStaticMeshComponent* Component : GroundParts) if (IsValid(Component)) Component->DestroyComponent();
    GroundParts.Reset();
    GroundFitMaterial = nullptr;
    GroundRegion.Reset();
    GroundFitPortrait = false;
    Parts.Reset(); RestTransforms.Reset(); RestMaterials.Reset(); RestSlotMaterials.Reset(); RestSlotOffsets.Reset(); Motions.Reset(); FlameParts.Reset(); FoliageParts.Reset();
    ConditionIndices.Reset(); AshParts.Reset(); RuinConsumedParts.Reset(); NextConditionIndex = 0;
    Clock = 0.f; CurrentDamage = 0; Ruined = false; DesignId = CardId; HoldingPart = INDEX_NONE; HoldingRuinPart = INDEX_NONE; HoldingDamagedPart = INDEX_NONE;
    SetComponentTickEnabled(true);

    if (const auto* Holding = OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*CardId)))
    {
        if (BuildHolding(UTF8_TO_TCHAR(Holding->Asset), true, Holding->PresentationScale))
        {
            SetCondition(0, false);
            return;
        }
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing expansion holding %s"),
            *CardId, UTF8_TO_TCHAR(Holding->Asset));
    }

    // Western holdings: one static, sourced mesh per base camp. The authored
    // wasteland scene below remains the fallback only if an asset is missing.
    if (const auto* Holding = OldWestHoldings::ForCamp(TCHAR_TO_UTF8(*CardId)))
    {
        if (BuildHolding(UTF8_TO_TCHAR(Holding->Asset)))
        {
            SetCondition(0, false);
            return;
        }
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: %s missing holding asset %s; using the authored camp scene"),
            *CardId, UTF8_TO_TCHAR(Holding->Asset));
    }

    // Each branch is an authored landmark, rather than a hash into a reusable building.
    // Front is -Y; all pieces share this component's parent transform.
    if (CardId == TEXT("saloon"))
    {
        Frame(FVector(70, 35, 0), FVector(250, 200, 205), TEXT("ClinicPaint"));
        Bed(FVector(70, -30, 0), Rubber);
        for (int32 I = 0; I < 3; ++I)
        {
            Tank(FVector(-175 + I * 67, 70, 0), 48, 180 + I * 20, Teal);
            Pipe(FVector(-175 + I * 67, 70, 170), FVector(30, 30, 180), 6, Copper);
        }
        Fan(FVector(70, 35, 225), 100, 135);
        Cross(FVector(70, -74, 172), 58);
        Box(FVector(156, -65, 90), FVector(30, 18, 62), Steel);
        Box(FVector(156, -77, 99), FVector(22, 3, 26), Signal);
    }
    else if (CardId == TEXT("livery_barn"))
    {
        Frame(FVector(0, 50, 0), FVector(330, 150, 205), Teal);
        Box(FVector(0, -41, 224), FVector(340, 20, 46), Rust);
        for (int32 I = 0; I < 4; ++I)
        {
            const FVector P(-120 + I * 80, -40, 0);
            Box(P + FVector(0, 0, 64), FVector(58, 60, 125), I % 2 ? Red : Teal);
            Box(P + FVector(0, -31, 108), FVector(44, 5, 42), Glass, FRotator(0, 0, -8));
            const int32 Display = Box(P + FVector(0, -35, 108), FVector(20, 3, 8), Signal);
            Move(Display, EMotion::Translate, FVector::UpVector, 1.4 + I * .2, 10, FVector::ZeroVector, I);
            Box(P + FVector(0, -40, 75), FVector(52, 28, 6), Steel);
            Drum(P + FVector(-12, -43, 82), 5, 14, Zinc);
        }
        for (int32 I = -3; I <= 3; ++I) Orb(FVector(I * 46, -54, 225), FVector(9), Lamp);
    }
    else if (CardId == TEXT("hot_springs"))
    {
        for (int32 I : {-1, 1})
        {
            Box(FVector(I * 125, 0, 20), FVector(100, 285, 40), Concrete);
            for (int32 J = -1; J <= 1; ++J) Tree(FVector(I * 125, J * 86, 40), 100 + J * 12, Teal);
        }
        Tank(FVector(0, 130, 0), 85, 220, Zinc);
        Pipe(FVector(0, 130, 175), FVector(0, -120, 175), 9, Copper);
        Fan(FVector(0, 130, 253), 115, 80);
        for (int32 I : {-1, 1}) Pipe(FVector(0, 0, 175), FVector(I * 135, 0, 175), 6, Copper);
    }
    else if (CardId == TEXT("silver_mine"))
    {
        Frame(FVector(-70, 50, 0), FVector(190, 205, 200), Chalk);
        Cross(FVector(-70, -58, 158), 70);
        for (int32 I = 0; I < 2; ++I)
        {
            Tank(FVector(115, -65 + I * 160, 0), 105, 185, Red);
            Pipe(FVector(115, -65 + I * 160, 35), FVector(-35, -65 + I * 110, 35), 13, Copper);
        }
        const int32 Gauge = Box(FVector(122, -120, 105), FVector(3, 4, 40), Chalk);
        Move(Gauge, EMotion::Sway, FVector::RightVector, 2, 22, FVector(122, -120, 85));
        Bed(FVector(-75, -75, 0), Red);
        Fan(FVector(-70, 50, 220), 70, 90);
    }
    else if (CardId == TEXT("logging_camp"))
    {
        // Keep the original stone ring and flame dimensions. Imported
        // wood modules preserve their authored PBR material slots.
        for (int32 I = 0; I < 9; ++I)
        {
            const float A = I * 2.f * UE_PI / 9.f;
            Part(RockMesh, FVector(FMath::Cos(A) * 125, FMath::Sin(A) * 125, 22), FVector(60, 50, 45), nullptr);
        }
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_01.SM_Bonfire_FuelLog_01"), FVector(-5.668074f, -48.241669f, 18.157691f), FVector(170.384526f, 52.283025f, 36.235392f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_02.SM_Bonfire_FuelLog_02"), FVector(3.748789f, 45.988852f, 15.312839f), FVector(159.079957f, 52.596235f, 30.545688f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_03.SM_Bonfire_FuelLog_03"), FVector(-41.371182f, -0.942877f, 45.499456f), FVector(40.279812f, 158.306885f, 37.132382f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_04.SM_Bonfire_FuelLog_04"), FVector(38.834506f, 2.644080f, 47.755402f), FVector(58.078337f, 151.585746f, 38.790929f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_05.SM_Bonfire_FuelLog_05"), FVector(-4.888299f, -39.724916f, 73.701143f), FVector(149.796009f, 42.902890f, 23.180747f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_FuelLog_06.SM_Bonfire_FuelLog_06"), FVector(2.461040f, 48.653239f, 67.450976f), FVector(143.444240f, 36.372781f, 30.578279f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_CharcoalBed.SM_Bonfire_CharcoalBed"), FVector(-7.550952f, 3.362358f, 2.489977f), FVector(173.298907f, 202.684999f, 4.979955f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_Bench_Left.SM_Bonfire_Bench_Left"), FVector(-190.129948f, -9.388661f, 23.010065f), FVector(68.297708f, 167.157507f, 46.020129f), nullptr);
        Part(TEXT("/Game/Art/Camps/BonfireStudy/Meshes/SM_Bonfire_Bench_Right.SM_Bonfire_Bench_Right"), FVector(189.870048f, -10.642809f, 23.010065f), FVector(68.297720f, 167.094576f, 46.020129f), nullptr);
        // These meshes already contain the fuel: suppress only this
        // call's old helper cylinders, not the native flame or smoke.
        Fire(FVector(0, 0, 60), 160, false);
    }
    else if (CardId == TEXT("stockyards"))
    {
        Part(RockMesh, FVector(-135, 75, 48), FVector(215, 180, 100), nullptr);
        Part(RockMesh, FVector(130, 90, 60), FVector(155, 190, 125), nullptr);
        Box(FVector(0, 20, 18), FVector(260, 170, 25), Concrete);
        Box(FVector(0, 75, 118), FVector(235, 15, 170), Rust, FRotator(-35, 0, 0));
        Crates(FVector(-83, -60, 30), 5);
        Tank(FVector(180, -65, 0), 55, 90, Zinc);
        Flag(FVector(-180, -100, 0), 155, Canvas);
    }
    else if (CardId == TEXT("army_fort"))
    {
        Box(FVector(0, 25, 35), FVector(245, 225, 60), Concrete);
        Drum(FVector(0, 20, 100), 160, 55, Steel);
        Pipe(FVector(0, 60, 150), FVector(0, -210, 235), 72, Rust);
        Pipe(FVector(0, -198, 231), FVector(0, -230, 241), 87, Steel);
        for (int32 X : {-1, 1}) Wheel(FVector(X * 108, 25, 100), 120);
        Crates(FVector(145, 60, 0), 3);
        Fan(FVector(0, 150, 150), 66, 100, FRotator(0, 0, 90));
        Fence(FVector(-180, -165, 0), FVector(180, -165, 0), 36);
    }
    else if (CardId == TEXT("dynamite_shack"))
    {
        Box(FVector(0, 0, 32), FVector(280, 290, 26), Rust);
        for (int32 X : {-1, 1})
        {
            Beam(FVector(X * 105, -110, 42), FVector(X * 80, 25, 220), 18, Steel);
            Beam(FVector(X * 105, 130, 42), FVector(X * 80, 25, 220), 18, Steel);
            for (int32 Y : {-1, 1}) Wheel(FVector(X * 145, Y * 90, 45), 76);
        }
        Pipe(FVector(-100, 25, 220), FVector(100, 25, 220), 23, Zinc);
        const FVector Pivot(0, 25, 220);
        const FVector ArmFront(0, -174, 280);
        const FVector ArmBack = Pivot - (ArmFront - Pivot) * .55;
        const int32 Arm = Box((ArmFront + ArmBack) * .5,
            FVector(24, 26, FVector::Distance(ArmFront, ArmBack)), Rust,
            FQuat::FindBetweenNormals(FVector::UpVector, (ArmFront - ArmBack).GetSafeNormal()).Rotator());
        Move(Arm, EMotion::Sway, FVector::ForwardVector, .8, 2, Pivot);
        const int32 Basket = Drum(FVector(0, -174, 290), 90, 35, Steel);
        Move(Basket, EMotion::Sway, FVector::ForwardVector, .8, 2, Pivot);
        Crates(FVector(160, 40, 0), 2);
    }
    else if (CardId == TEXT("bunkhouse"))
    {
        Frame(FVector(-50, 15, 0), FVector(285, 230, 165), Steel);
        Box(FVector(-50, -118, 75), FVector(220, 20, 115), Rust);
        for (int32 I = -1; I <= 1; ++I) Box(FVector(-50 + I * 67, -133, 98), FVector(47, 4, 31), Signal);
        Antenna(FVector(145, 80, 0), 370, true);
        Antenna(FVector(-155, 60, 170), 125, false);
        Flag(FVector(-200, -135, 0), 225, Red);
        Crates(FVector(110, -100, 0), 3);
    }
    else if (CardId == TEXT("roundup_corral"))
    {
        Box(FVector(-140, 90, 35), FVector(125, 120, 70), Concrete);
        for (int32 X : {-1, 1}) Beam(FVector(-140 + X * 40, 90, 70), FVector(-140 + X * 25, 90, 355), 14, Rust);
        Beam(FVector(-220, 90, 355), FVector(205, 90, 355), 24, Zinc);
        Beam(FVector(-140, 90, 425), FVector(195, 90, 355), 7, Steel);
        Pipe(FVector(145, 90, 350), FVector(145, 90, 140), 4, Steel);
        const int32 Load = Box(FVector(145, 90, 130), FVector(85, 90, 36), Concrete);
        Move(Load, EMotion::Sway, FVector::RightVector, .65, 2.4, FVector(145, 90, 350));
        for (int32 I = 0; I < 4; ++I) Beam(FVector(-170, -110 + I * 26, 18), FVector(125, -110 + I * 26, 18), 18, Rust);
        Crates(FVector(95, -100, 0), 4);
    }
    else if (CardId == TEXT("cattle_ranch"))
    {
        Frame(FVector(0, 55, 0), FVector(340, 205, 220), Rust);
        Vehicle(FVector(10, -50, 0), false);
        Box(FVector(-190, -90, 60), FVector(48, 55, 110), Red);
        Fan(FVector(0, 161, 176), 110, 140, FRotator(0, 0, 90));
        Wheel(FVector(205, 30, 44), 83);
        Flag(FVector(190, 115, 0), 265, Canvas);
    }
    else if (CardId == TEXT("riverboat"))
    {
        Vehicle(FVector(0, 10, 0), true);
        Box(FVector(0, 50, 173), FVector(150, 160, 70), Rust);
        Pipe(FVector(0, 0, 213), FVector(0, -240, 245), 32, Steel);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 115, 0, 55), FVector(50, 335, 100), Rubber);
            for (int32 Y = -2; Y <= 2; ++Y) Wheel(FVector(X * 145, Y * 59, 57), 47, true);
        }
        Box(FVector(0, -197, 45), FVector(300, 55, 95), Rust, FRotator(0, 0, -25));
        Flag(FVector(-55, 105, 190), 120, Red);
    }
    else if (CardId == TEXT("railroad_work_camp"))
    {
        Frame(FVector(90, 90, 0), FVector(220, 120, 155), Canvas);
        Fence(FVector(-220, -120, 0), FVector(-220, 160, 0), 165);
        Fence(FVector(-220, 160, 0), FVector(210, 160, 0), 165);
        for (int32 I = 0; I < 3; ++I) Part(RockMesh, FVector(-140 + I * 95, -40, 30), FVector(70, 70, 65), nullptr);
        for (int32 I = 0; I < 2; ++I)
        {
            const int32 Hammer = Box(FVector(-120 + I * 110, -85, 103), FVector(55, 18, 22), Steel);
            Move(Hammer, EMotion::Sway, FVector::ForwardVector, 1.8, 9, FVector(-120 + I * 110, -85, 45), I * 2);
            Box(FVector(-120 + I * 110, -85, 70), FVector(7, 7, 66), Rust);
        }
        Flag(FVector(195, -90, 0), 245, Canvas);
    }
    else if (CardId == TEXT("toll_bridge"))
    {
        Frame(FVector(-65, 65, 0), FVector(285, 180, 145), Canvas);
        Box(FVector(-65, 65, 185), FVector(330, 225, 10), Canvas, FRotator(0, 0, -12));
        for (int32 I = 0; I < 5; ++I)
        {
            Box(FVector(-150 + I * 58, -105, 42), FVector(62, 32, 68), Concrete);
            Pipe(FVector(-150 + I * 58, -70, 45), FVector(-150 + I * 58, -120, 138), 7, Steel);
        }
        Crates(FVector(130, 40, 0), 5);
        Antenna(FVector(165, 125, 0), 230, true);
    }
    else if (CardId == TEXT("undertaker"))
    {
        Box(FVector(0, 30, 70), FVector(280, 220, 135), Rust);
        for (int32 X : {-1, 1})
        {
            Drum(FVector(X * 63, -18, 156), 97, 195, Steel, FRotator(0, 0, 90));
            for (int32 I = -2; I <= 2; ++I)
            {
                const FVector Pivot(X * 63, I * 32, 156);
                const int32 Tooth = Box(Pivot, FVector(122, 13, 18), Zinc);
                Move(Tooth, EMotion::Rotate, FVector::RightVector, X * 75, 1, Pivot, I * .6);
            }
            Box(FVector(X * 127, 0, 225), FVector(16, 225, 115), Rust, FRotator(0, 0, X * 18));
        }
        Box(FVector(0, -185, 48), FVector(220, 160, 15), Rubber, FRotator(0, 0, 12));
        Crates(FVector(150, 90, 0), 2);
    }
    else if (CardId == TEXT("bordello"))
    {
        Frame(FVector(0, 30, 0), FVector(200, 175, 140), Steel);
        Frame(FVector(35, 30, 145), FVector(155, 140, 120), Rust);
        for (int32 I = 0; I < 3; ++I) Antenna(FVector(-175 + I * 160, 75, I == 1 ? 270 : 0), 160 + I * 30, true);
        Box(FVector(35, -45, 221), FVector(125, 5, 22), Glass);
        for (int32 I = 0; I < 3; ++I) Box(FVector(-80 + I * 80, -63, 82), FVector(55, 6, 35), Signal);
    }
    else if (CardId == TEXT("trading_post"))
    {
        Orb(FVector(0, 0, 8), FVector(365, 250, 16), Glass);
        Torus(FVector(0, 0, 8), 260, 11, Teal);
        Tree(FVector(-160, 55, 0), 310, nullptr);
        Tree(FVector(135, 90, 0), 255, nullptr);
        Tree(FVector(-185, -105, 0), 120, nullptr);
        for (int32 I = 0; I < 5; ++I) Part(RockMesh, FVector(-130 + I * 65, -135, 15), FVector(58, 44, 30), nullptr);
        const int32 Ripple = Drum(FVector(30, 0, 18), 95, 1, Teal);
        Move(Ripple, EMotion::Breathe, FVector::OneVector, .8, .08);
    }
    else if (CardId == TEXT("land_office"))
    {
        Box(FVector(0, 0, 15), FVector(260, 250, 30), Concrete);
        Box(FVector(0, 0, 53), FVector(190, 180, 46), Steel);
        Box(FVector(0, 0, 205), FVector(85, 90, 275), Concrete);
        Cone(FVector(0, 0, 382), 122, 78, Concrete);
        for (int32 I = 0; I < 5; ++I) Box(FVector(0, -46, 125 + I * 40), FVector(25, 3, 5), Copper);
        for (int32 X : {-1, 1})
        {
            Drum(FVector(X * 150, -105, 52), 40, 100, Steel);
            Fire(FVector(X * 150, -105, 105), 28);
        }
    }
    else if (CardId == TEXT("telegraph_office"))
    {
        for (int32 X : {-1, 1}) Beam(FVector(X * 120, 0, 0), FVector(X * 70, 0, 300), 22, Rust);
        const FVector Face(0, -10, 275);
        Drum(Face, 215, 28, Zinc, FRotator(0, 0, 90));
        Drum(Face + FVector(0, -17, 0), 191, 6, Steel, FRotator(0, 0, 90));
        Torus(Face + FVector(0, -24, 0), 204, 8, Rust, FRotator(0, 0, 90));
        for (int32 I = 0; I < 8; ++I)
        {
            const float A = I * UE_PI / 4.f;
            Drum(Face + FVector(FMath::Sin(A) * 99, -30, FMath::Cos(A) * 99), 5, 3, Zinc, FRotator(0, 0, 90));
        }
        for (int32 I = 0; I < 12; ++I)
        {
            const float A = I * UE_PI / 6.f;
            Box(Face + FVector(FMath::Sin(A) * 80, -24, FMath::Cos(A) * 80), FVector(8, 4, 16), Chalk, FRotator(0, 0, -I * 30));
        }
        for (int32 I = 0; I < 2; ++I)
        {
            const int32 Hand = Box(Face + FVector(0, -30 - I * 3, 27 + I * 9), FVector(6 - I, 4, 58 + I * 18), I ? Red : Chalk);
            Move(Hand, EMotion::Rotate, FVector::RightVector, I ? 9 : .75, 1, Face);
        }
        Drum(FVector(0, 0, 25), 150, 40, Concrete);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 114, 0, 9), FVector(55, 62, 15), Steel);
            for (int32 Y : {-1, 1}) Drum(FVector(X * 114, Y * 22, 18), 8, 5, Zinc);
        }
    }
    else if (CardId == TEXT("stagecoach_station"))
    {
        Frame(FVector(-65, 45, 0), FVector(255, 185, 150), Teal);
        Tank(FVector(145, 75, 0), 102, 215, Zinc);
        Box(FVector(-65, -105, 95), FVector(280, 90, 8), Canvas, FRotator(0, 0, -8));
        Crates(FVector(-130, -90, 0), 3);
        Antenna(FVector(-160, 100, 155), 150, true);
        Flag(FVector(170, -120, 0), 240, Teal);
    }
    else if (CardId == TEXT("railroad_depot"))
    {
        Box(FVector(0, 20, 9), FVector(390, 290, 18), Concrete);
        for (int32 X : {-1, 1}) Box(FVector(X * 165, 90, 145), FVector(16, 16, 290), Zinc);
        Beam(FVector(-165, 90, 290), FVector(165, 90, 290), 18, Steel);
        const FVector Pivot(0, 90, 290);
        const int32 Chute = Orb(FVector(0, 60, 257), FVector(255, 150, 45), Canvas);
        Move(Chute, EMotion::Sway, FVector::RightVector, .9, 2.5, Pivot);
        for (int32 X : {-1, 1}) Pipe(FVector(X * 105, 45, 240), FVector(X * 35, 15, 130), 2, Steel);
        Crates(FVector(-135, -120, 15), 5);
        Flag(FVector(200, 95, 0), 335, Red);
        Box(FVector(0, -95, 20), FVector(100, 10, 3), Chalk);
        Box(FVector(0, -95, 20), FVector(10, 100, 3), Chalk);
    }
    else if (CardId == TEXT("homestead_cabin"))
    {
        Part(*DetailMesh(TEXT("BunkerEmbrasure")), FVector(0, 10, 75), FVector(330, 330, 150), Concrete);
        Drum(FVector(0, 10, 156), 350, 22, Concrete);
        Box(FVector(0, -132, 106), FVector(138, 5, 34), Rubber);
        Box(FVector(0, -154, 132), FVector(150, 18, 9), Steel);
        Pipe(FVector(0, -160, 105), FVector(0, -240, 105), 12, Steel);
        for (int32 I = 0; I < 7; ++I)
            Part(*DetailMesh(TEXT("Sandbag")), FVector(-180 + I * 60, -180, 20), FVector(65, 38, 34), Canvas, FRotator(0, I % 2 ? 6 : -5, 0));
        for (int32 I = 0; I < 3; ++I)
            Part(*DetailMesh(TEXT("Sandbag")), FVector(-58 + I * 57, -179, 49), FVector(62, 37, 28), Canvas, FRotator(0, I * 4, 0));
        Drum(FVector(-55, 38, 174), 94, 12, Steel);
        Torus(FVector(-55, 38, 181), 86, 5, Zinc);
        Beam(FVector(-72, 38, 185), FVector(-38, 38, 185), 5, Rust);
        Antenna(FVector(75, 60, 170), 145, true);
        Tank(FVector(-180, 105, 0), 55, 95, Rust);
    }
    else if (CardId == TEXT("gatling_emplacement"))
    {
        Box(FVector(0, 20, 30), FVector(270, 270, 55), Concrete);
        Drum(FVector(0, 20, 80), 150, 55, Steel);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 37, -75, 180), FVector(27, 370, 34), Zinc, FRotator(0, 0, -8));
            for (int32 I = 0; I < 5; ++I) Box(FVector(X * 40, 50 - I * 61, 163 + I * 9), FVector(44, 17, 68), Copper, FRotator(0, 0, -8));
            Tank(FVector(X * 165, 90, 0), 67, 115, Teal);
        }
        Fan(FVector(0, 132, 138), 85, 170, FRotator(0, 0, 90));
        Pipe(FVector(-165, 90, 40), FVector(-40, 60, 138), 9, Copper);
    }
    else if (CardId == TEXT("powder_magazine"))
    {
        Drum(FVector(0, 15, 20), 285, 40, Concrete);
        Tank(FVector(0, 15, 40), 165, 270, Steel);
        for (int32 I = 0; I < 4; ++I)
        {
            const float A = I * UE_PI * .5;
            const FVector P(FMath::Cos(A) * 135, 15 + FMath::Sin(A) * 135, 0);
            Tank(P, 48, 200, Copper);
            Pipe(P + FVector(0, 0, 150), FVector(0, 15, 150), 16, Zinc);
        }
        Torus(FVector(0, 15, 175), 235, 13, Copper);
        Fan(FVector(0, 15, 350), 125, 120);
        for (int32 X : {-1, 1}) Box(FVector(X * 55, -72, 195), FVector(16, 5, 95), Signal);
    }
    else if (CardId == TEXT("church_bell_tower"))
    {
        Box(FVector(0, 25, 24), FVector(285, 230, 44), Concrete);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 100, 15, 185), FVector(44, 70, 315), Steel);
            Box(FVector(X * 100, 15, 335), FVector(72, 85, 30), Copper);
            const int32 Fork = Box(FVector(X * 100, -27, 205), FVector(22, 10, 240), Zinc);
            Move(Fork, EMotion::Translate, FVector::ForwardVector, 5, 1.5);
        }
        Beam(FVector(-100, 15, 85), FVector(100, 15, 85), 42, Copper);
        Pipe(FVector(0, -85, 46), FVector(0, -85, 178), 9, Steel);
        for (int32 I = 0; I < 3; ++I) Drum(FVector(0, -85, 65 + I * 52), 80 - I * 12, 12, Copper);
        Fan(FVector(0, 110, 95), 80, 90, FRotator(0, 0, 90));
    }
    else if (CardId == TEXT("salvage_yard"))
    {
        const FRotator RoofRotation(0, 0, 28);
        for (int32 I = 0; I < 5; ++I) Box(FVector(-90 + I * 43, 80, 165), FVector(47, 160, 8), I % 2 ? Rust : Zinc, RoofRotation);
        for (int32 Side : {-1, 1})
        {
            const FVector Left = FVector(-107, 80, 165) + RoofRotation.RotateVector(FVector(0, Side * 73, -4));
            const FVector Right = FVector(99, 80, 165) + RoofRotation.RotateVector(FVector(0, Side * 73, -4));
            Beam(FVector(Left.X, Left.Y, 0), Left, 10, Steel);
            Beam(FVector(Right.X, Right.Y, 0), Right, 10, Steel);
            Beam(Left, Right, 10, Steel);
        }
        Crates(FVector(-120, -80, 0), 8);
        for (int32 I = 0; I < 3; ++I) Wheel(FVector(180, 50 - I * 70, 34), 65);
        Tank(FVector(155, 135, 0), 75, 105, Rust);
        Fire(FVector(90, -145, 0), 42);
        Flag(FVector(-190, 115, 0), 205, Canvas);
    }
    else if (CardId == TEXT("artillery_battery"))
    {
        Vehicle(FVector(0, 45, 0), true);
        Beam(FVector(0, 45, 100), FVector(0, 115, 305), 24, Steel);
        Pipe(FVector(0, -170, 145), FVector(0, 120, 355), 56, Chalk);
        Part(TEXT("Cone"), FVector(0, 143, 372), FVector(56, 56, 85), Red,
            FQuat::FindBetweenNormals(FVector::UpVector, FVector(0, 290, 210).GetSafeNormal()).Rotator());
        for (int32 X : {-1, 1}) Box(FVector(X * 28, -140, 165), FVector(75, 52, 6), Zinc, FRotator(0, 0, -36));
        Antenna(FVector(-130, 95, 0), 205, true);
        Crates(FVector(120, -115, 0), 3);
    }
    else if (CardId == TEXT("general_store"))
    {
        Frame(FVector(0, 75, 0), FVector(315, 160, 210), Zinc);
        Crates(FVector(-125, 30, 12), 10);
        Crates(FVector(-155, -100, 0), 4);
        Tank(FVector(190, -25, 0), 70, 125, Teal);
        Box(FVector(0, -15, 237), FVector(255, 12, 36), Teal);
        Fan(FVector(0, 160, 180), 90, 115, FRotator(0, 0, 90));
        Flag(FVector(-195, 135, 0), 280, Canvas);
    }
    else if (CardId == TEXT("bare_knuckle_ring"))
    {
        Drum(FVector(0, 0, 17), 360, 34, Concrete);
        for (int32 I = 0; I < 8; ++I)
        {
            const float A = I * UE_PI / 4.f, B = (I + 1) * UE_PI / 4.f;
            const FVector P(FMath::Cos(A) * 180, FMath::Sin(A) * 180, 34), Q(FMath::Cos(B) * 180, FMath::Sin(B) * 180, 34);
            Fence(P, Q, 130);
            if (I % 2 == 0) Flag(P, 190, I % 4 ? Red : Canvas);
        }
        Box(FVector(0, 0, 37), FVector(170, 12, 3), Red, FRotator(0, 45, 0));
        Box(FVector(0, 0, 38), FVector(170, 12, 3), Red, FRotator(0, -45, 0));
    }
    else if (CardId == TEXT("breaking_pen"))
    {
        for (int32 I = 0; I < 3; ++I)
        {
            const FVector P(-145 + I * 140, 85, 0);
            Beam(P, P + FVector(0, 0, 180), 12, Steel);
            const int32 Target = Orb(P + FVector(0, -5, 139), FVector(45, 18, 50), Red);
            Move(Target, EMotion::Sway, FVector::RightVector, 1.1, 5, P + FVector(0, 0, 180), I);
            Box(P + FVector(0, 0, 99), FVector(75, 20, 60), Canvas);
        }
        for (int32 I = 0; I < 6; ++I) Drum(FVector(-130 + I % 3 * 120, -50 - I / 3 * 80, 12), 75, 24, Rubber);
        Beam(FVector(-190, -170, 90), FVector(190, -170, 90), 12, Rust);
        for (int32 X : {-1, 1})
        {
            Beam(FVector(X * 155, -170, 0), FVector(X * 155, -170, 90), 14, Steel);
            Beam(FVector(X * 155, -195, 5), FVector(X * 155, -145, 5), 12, Steel);
        }
        Flag(FVector(215, 125, 0), 260, Teal);
    }
    else if (CardId == TEXT("barn_raising"))
    {
        Frame(FVector(0, 35, 0), FVector(290, 240, 205), TEXT("ClinicPaint"));
        Bed(FVector(-62, -25, 10), Teal); Bed(FVector(62, -25, 10), Red);
        Pipe(FVector(0, 110, 10), FVector(0, 110, 183), 11, Zinc);
        Beam(FVector(0, 110, 178), FVector(0, -50, 178), 12, Zinc);
        const int32 Light = Drum(FVector(0, -50, 168), 92, 15, Chalk);
        Move(Light, EMotion::Sway, FVector::RightVector, .6, 3, FVector(0, -50, 178));
        Cross(FVector(0, -91, 175), 70);
        Tank(FVector(185, 65, 0), 70, 180, Teal);
        Fan(FVector(0, 40, 221), 105, 95);
    }
    else if (CardId == TEXT("rodeo_grounds"))
    {
        Drum(FVector(0, 0, 18), 220, 36, Concrete);
        Pipe(FVector(0, 0, 30), FVector(0, 0, 335), 35, Rust);
        for (int32 I = 0; I < 3; ++I)
        {
            Box(FVector(0, 0, 135 + I * 72), FVector(160 - I * 25, 35, 28), Zinc, FRotator(0, 0, I % 2 ? 8 : -8));
            Orb(FVector(0, -25, 148 + I * 72), FVector(43, 28, 39), Chalk);
        }
        for (int32 X : {-1, 1}) Flag(FVector(X * 95, 20, 0), 270, Red);
        Fire(FVector(0, -130, 0), 45);
    }
    else if (CardId == TEXT("freight_warehouse"))
    {
        Frame(FVector(0, 65, 0), FVector(350, 210, 245), Zinc);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 105, -42, 130), FVector(105, 9, 230), Rust);
            for (int32 I = 0; I < 4; ++I) Box(FVector(X * 105, -49, 53 + I * 49), FVector(97, 4, 3), Steel);
        }
        Crates(FVector(-35, -90, 0), 3);
        Box(FVector(0, -160, 22), FVector(265, 90, 15), Steel);
        Fan(FVector(0, 177, 203), 90, 100, FRotator(0, 0, 90));
        Antenna(FVector(110, 110, 250), 130, true);
    }
    else if (CardId == TEXT("mountain_hideout"))
    {
        for (int32 X : {-1, 1}) for (int32 Y : {-1, 1})
            Beam(FVector(X * 105, Y * 105, 0), FVector(X * 72, Y * 72, 285), 15, Rust);
        for (int32 X : {-1, 1})
        {
            Beam(FVector(X * 100, -95, 30), FVector(X * 75, 75, 245), 8, Zinc);
            Beam(FVector(X * 100, 95, 30), FVector(X * 75, -75, 245), 8, Zinc);
        }
        Frame(FVector(0, 0, 265), FVector(185, 175, 90), Wood);
        Box(FVector(0, -87, 320), FVector(150, 8, 45), Steel);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 100, 0, 269), FVector(18, 203, 14), Steel);
            for (int32 Y : {-1, 1})
            {
                Box(FVector(X * 104, Y * 104, 7), FVector(46, 46, 14), Concrete);
                Box(FVector(X * 104, Y * 104, 17), FVector(31, 31, 7), Steel);
                Drum(FVector(X * 112, Y * 112, 23), 7, 5, Zinc);
            }
        }
        for (int32 X : {-1, 1}) Beam(FVector(X * 30, -100, 0), FVector(X * 30, -100, 277), 7, Zinc);
        for (int32 I = 0; I < 10; ++I) Beam(FVector(-28, -100, 25 + I * 25), FVector(28, -100, 25 + I * 25), 5, Steel);
        Antenna(FVector(0, 0, 363), 105, true);
        Flag(FVector(100, 65, 265), 145, Red);
    }
    else if (CardId == TEXT("gunsmith"))
    {
        Frame(FVector(0, 70, 0), FVector(300, 190, 205), Steel);
        for (int32 I = 0; I < 6; ++I)
        {
            Pipe(FVector(-110 + I * 43, 145, 60), FVector(-110 + I * 43, 145, 180), 7, Zinc);
            Box(FVector(-110 + I * 43, 145, 78), FVector(13, 20, 48), Rust);
        }
        Box(FVector(0, 125, 70), FVector(275, 18, 14), Rust);
        Crates(FVector(-155, -90, 0), 7);
        Fan(FVector(0, 170, 170), 70, 100, FRotator(0, 0, 90));
        Flag(FVector(185, 95, 0), 270, Red);
    }
    else if (CardId == TEXT("jailhouse"))
    {
        Frame(FVector(-40, 55, 0), FVector(260, 205, 240), Concrete);
        for (int32 I = 0; I < 3; ++I)
        {
            Box(FVector(-120 + I * 80, -50, 154), FVector(55, 7, 95), Glass);
            for (int32 J = 0; J < 3; ++J) Box(FVector(-138 + I * 80 + J * 18, -57, 154), FVector(4, 4, 95), Zinc);
        }
        Fence(FVector(110, -120, 0), FVector(110, 155, 0), 165);
        Fence(FVector(110, -120, 0), FVector(220, -120, 0), 165);
        Box(FVector(-40, -61, 53), FVector(65, 12, 105), Steel);
        Antenna(FVector(-135, 110, 245), 145, true);
        const int32 LampHead = Orb(FVector(167, -105, 205), FVector(26), Lamp);
        Pipe(FVector(167, -105, 0), FVector(167, -105, 205), 6, Steel);
        Move(LampHead, EMotion::Breathe, FVector::OneVector, 4, .025);
    }
    else if (CardId == TEXT("robbers_roost"))
    {
        Vehicle(FVector(95, 35, 0), true);
        for (int32 I = 0; I < 4; ++I) Box(FVector(-170 + I * 65, -142, 65), FVector(48, 15, 130), Rust, FRotator(0, 0, I % 2 ? 11 : -7));
        Frame(FVector(-120, 80, 0), FVector(130, 145, 130), Canvas);
        Flag(FVector(-175, 115, 0), 285, Red);
        Fire(FVector(-90, -45, 0), 40);
        Crates(FVector(150, -160, 0), 2);
    }
    else if (CardId == TEXT("timber_ram"))
    {
        for (int32 X : {-1, 1})
        {
            for (int32 Y : {-1, 1})
            {
                Beam(FVector(X * 100, Y * 110, 45), FVector(X * 65, Y * 110, 210), 18, Steel);
                Wheel(FVector(X * 120, Y * 110, 40), 72);
            }
            Box(FVector(X * 55, 0, 235), FVector(155, 310, 12), Zinc, FRotator(-X * 25, 0, 0));
        }
        Pipe(FVector(0, -160, 122), FVector(0, 135, 122), 65, Rust);
        const int32 Head = Drum(FVector(0, -180, 122), 102, 45, Steel, FRotator(0, 0, 90));
        Move(Head, EMotion::Translate, FVector::RightVector, .8, 4);
        for (int32 Y : {-1, 1}) Pipe(FVector(0, Y * 100, 220), FVector(0, Y * 100, 130), 6, Steel);
        Flag(FVector(-75, 120, 240), 95, Red);
    }
    else if (CardId == TEXT("smuggler_s_landing"))
    {
        for (int32 I : {-1, 1})
        {
            Frame(FVector(I * 112, 40, 0), FVector(175, 175, 125), I < 0 ? Red : Canvas, false);
            const FVector Pivot(I * 112, 115, 190);
            const int32 Awning = Box(FVector(I * 112, 10, 172), FVector(205, 225, 5), I < 0 ? Red : Teal, FRotator(0, 0, -8));
            Move(Awning, EMotion::Sway, FVector::ForwardVector, .8, .7, Pivot, I);
            Crates(FVector(I * 112 - 48, -30, 20), 3);
            Orb(FVector(I * 112, -92, 149), FVector(19), Lamp);
        }
        Beam(FVector(-205, -92, 188), FVector(205, -92, 188), 3, Steel);
        for (int32 I = -3; I <= 3; ++I) Orb(FVector(I * 57, -92, 185 - (3 - FMath::Abs(I)) * 8), FVector(9), Lamp);
    }
    else if (CardId == TEXT("rockslide_ridge"))
    {
        Part(RockMesh, FVector(0, 45, 245), FVector(330, 315, 350), nullptr);
        Part(RockMesh, FVector(0, 70, 64), FVector(430, 350, 125), nullptr);
        for (int32 X : {-1, 1})
        {
            Beam(FVector(X * 95, -155, 0), FVector(X * 110, 30, 135), 18, Rust);
            Box(FVector(X * 115, -95, 61), FVector(60, 30, 38), Steel, FRotator(0, 0, -20));
        }
        Flag(FVector(190, 95, 0), 270, Red);
        // The stone stays still; wind warns at its release mechanism.
        const int32 Cable = Box(FVector(0, -159, 87), FVector(155, 2, 4), Copper);
        Move(Cable, EMotion::Translate, FVector::UpVector, 1.5, 1);
    }
    else if (CardId == TEXT("bounty_office"))
    {
        Frame(FVector(45, 50, 0), FVector(230, 190, 200), Canvas);
        Box(FVector(45, -49, 185), FVector(250, 15, 45), Rust);
        Box(FVector(45, -49, 85), FVector(140, 8, 70), Glass);
        Box(FVector(-150, -85, 122), FVector(105, 10, 120), Rust);
        for (int32 I = 0; I < 4; ++I) Box(FVector(-172 + I % 2 * 44, -92, 95 + I / 2 * 52), FVector(32, 2, 42), Chalk, FRotator(0, 0, I * 2 - 3));
        for (int32 X : {-1, 1}) Pipe(FVector(-150 + X * 38, -85, 0), FVector(-150 + X * 38, -85, 190), 8, Steel);
        Flag(FVector(180, 85, 0), 255, Red);
    }
    else if (CardId == TEXT("packer_s_cabin"))
    {
        Pipe(FVector(0, 0, 0), FVector(0, 0, 310), 38, TEXT("Burnt"));
        for (int32 I = 0; I < 4; ++I)
        {
            Orb(FVector(0, -17, 100 + I * 60), FVector(63, 43, 56), Chalk);
            for (int32 X : {-1, 1}) Orb(FVector(X * 14, -40, 108 + I * 60), FVector(13, 7, 13), Steel);
            Beam(FVector(-80 + I * 5, 0, 85 + I * 60), FVector(80 - I * 5, 0, 85 + I * 60), 12, Rust);
        }
        for (int32 X : {-1, 1})
        {
            Fire(FVector(X * 135, -65, 0), 50);
            Flag(FVector(X * 105, 50, 0), 190, Red);
        }
        Crates(FVector(-55, 100, 0), 3);
    }
    else if (CardId == TEXT("revival_tent"))
    {
        Frame(FVector(0, 55, 0), FVector(280, 190, 150), Steel, false);
        for (int32 X : {-1, 1}) Box(FVector(X * 80, 55, 225), FVector(205, 225, 10), Rust, FRotator(-X * 40, 0, 0));
        Box(FVector(0, -46, 105), FVector(74, 10, 155), TEXT("Burnt"));
        Drum(FVector(0, -145, 25), 100, 50, Concrete);
        for (int32 X : {-1, 1})
        {
            Flag(FVector(X * 170, -55, 0), 230, Red);
            Fire(FVector(X * 100, -130, 0), 30);
        }
        Torus(FVector(0, -50, 237), 80, 7, Copper, FRotator(0, 0, 90));
        Beam(FVector(-40, -52, 198), FVector(40, -52, 278), 7, Copper);
    }
    else if (CardId == TEXT("vigilance_committee"))
    {
        Drum(FVector(0, 25, 42), 225, 80, Steel);
        Pipe(FVector(0, 20, 85), FVector(0, 20, 235), 45, Rust);
        for (int32 I = 0; I < 4; ++I)
            Torus(FVector(0, 0 - I * 53, 250 + I * 10), 130 + I * 16, 11, Copper, FRotator(0, 0, 100));
        Orb(FVector(0, -182, 284), FVector(62, 20, 62), Signal);
        for (int32 X : {-1, 1}) Tank(FVector(X * 170, 95, 0), 75, 220, Teal);
        Fan(FVector(0, 100, 270), 98, 160, FRotator(0, 0, 90));
        Pipe(FVector(-170, 95, 70), FVector(0, 20, 160), 12, Copper);
    }
    else if (CardId == TEXT("courthouse"))
    {
        Vehicle(FVector(-115, 0, 0), true);
        Vehicle(FVector(115, 40, 0), false);
        for (int32 I = 0; I < 7; ++I) Drum(FVector(-195 + I * 65, -165, 18), 64, 36, Rubber);
        Flag(FVector(-195, 160, 0), 300, Chalk);
        Flag(FVector(195, 160, 0), 300, Steel);
        Beam(FVector(-195, 160, 260), FVector(195, 160, 260), 8, Steel);
        for (int32 I = 0; I < 5; ++I) Box(FVector(-140 + I * 70, 160, 258), FVector(50, 8, 30), I % 2 ? Chalk : Steel);
    }
    else if (CardId == TEXT("post_office"))
    {
        Frame(FVector(15, 55, 0), FVector(285, 175, 195), Teal);
        Box(FVector(15, -41, 198), FVector(305, 15, 42), Chalk);
        Box(FVector(15, -43, 100), FVector(110, 8, 55), Glass);
        Box(FVector(15, -78, 71), FVector(170, 65, 10), Zinc);
        for (int32 I = 0; I < 3; ++I) Box(FVector(-35 + I * 48, -80, 83 + I * 2), FVector(30, 36, 12), Chalk);
        Fence(FVector(-170, -150, 0), FVector(150, -150, 0), 70);
        Flag(FVector(-175, 105, 0), 310, Teal);
        Antenna(FVector(130, 110, 200), 95, true);
    }
    else if (CardId == TEXT("army_surgeon_s_tent"))
    {
        for (int32 X : {-1, 1}) Box(FVector(X * 97, 40, 177), FVector(250, 290, 7), Canvas, FRotator(-X * 27, 0, 0));
        for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) Pipe(FVector(X * 200, 40 + Y * 140, 0), FVector(X * 200, 40 + Y * 140, 127), 7, Zinc);
        Bed(FVector(-90, 25, 0), Canvas); Bed(FVector(90, 25, 0), Canvas);
        Cross(FVector(0, -110, 169), 65);
        Tank(FVector(205, -90, 0), 40, 115, Teal);
        Flag(FVector(-220, -110, 0), 270, Chalk);
        Cross(FVector(-175, -112, 246), 28);
        Fire(FVector(0, -180, 0), 27);
    }
    else if (CardId == TEXT("wagon_fort"))
    {
        Box(FVector(0, 75, 102), FVector(380, 105, 205), Concrete);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 150, -40, 130), FVector(100, 180, 260), Concrete);
            for (int32 Y = -1; Y <= 1; ++Y) Box(FVector(X * 150, -40 + Y * 68, 280), FVector(110, 38, 42), Concrete);
            Box(FVector(X * 150, -135, 145), FVector(45, 5, 18), Steel);
        }
        Box(FVector(0, 18, 90), FVector(110, 15, 175), Rust);
        for (int32 X = -2; X <= 2; ++X) Box(FVector(X * 74, 75, 227), FVector(39, 112, 43), Concrete);
        Flag(FVector(150, 15, 300), 120, Red);
    }
    else if (CardId == TEXT("free_homestead"))
    {
        for (int32 X : {-1, 1})
        {
            Frame(FVector(X * 135, 65, 0), FVector(125, 155, 100), Canvas);
            Box(FVector(X * 135, 65, 127), FVector(160, 195, 6), Teal, FRotator(0, 0, X * 15));
        }
        Fire(FVector(0, -35, 0), 42);
        for (int32 X : {-1, 1}) Box(FVector(X * 110, -110, 25), FVector(55, 100, 25), Canvas);
        Flag(FVector(0, 140, 0), 330, Teal);
        Crates(FVector(-45, 55, 0), 2);
        // An open gate identifies refuge; nothing cages this camp.
        Box(FVector(-210, -140, 70), FVector(8, 90, 135), Zinc, FRotator(0, 45, 0));
    }
    else if (CardId == TEXT("coal_yard"))
    {
        for (int32 X : {-1, 1}) Pipe(FVector(X * 160, 20, 0), FVector(X * 160, 20, 220), 14, Zinc);
        Box(FVector(0, 20, 225), FVector(410, 285, 24), Teal);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 95, -20, 75), FVector(62, 60, 148), Red);
            Box(FVector(X * 95, -52, 115), FVector(43, 5, 25), Glass);
            Pipe(FVector(X * 128, -20, 130), FVector(X * 142, -20, 45), 5, Rubber);
            Pipe(FVector(X * 142, -20, 45), FVector(X * 160, -20, 105), 5, Rubber);
        }
        Tank(FVector(0, 150, 0), 65, 125, Rust);
        Fan(FVector(0, 35, 250), 90, 130);
        Flag(FVector(210, 125, 0), 320, Canvas);
    }
    else if (CardId == TEXT("gallows"))
    {
        Box(FVector(0, 15, 24), FVector(270, 245, 45), Rust);
        for (int32 X : {-1, 1}) Box(FVector(X * 74, 30, 205), FVector(24, 30, 330), Steel);
        Box(FVector(0, 30, 363), FVector(185, 37, 25), Rust);
        const int32 Blade = Box(FVector(0, 30, 273), FVector(127, 12, 86), Zinc, FRotator(9, 0, 0));
        Move(Blade, EMotion::Translate, FVector::UpVector, .55, 2);
        Pipe(FVector(87, 30, 350), FVector(120, 30, 120), 4, Canvas);
        Box(FVector(0, 15, 140), FVector(165, 36, 25), Rust);
        Bed(FVector(0, -58, 45), TEXT("Burnt"));
        Drum(FVector(0, 122, 61), 88, 65, Rust);
        Flag(FVector(-155, 90, 0), 180, Red);
    }
    else if (CardId == TEXT("pawn_shop"))
    {
        // A real open combustion chamber, rather than a solid cube hiding
        // both its contents and the supposedly visible fire behind the grate.
        Box(FVector(0, 148, 110), FVector(240, 14, 220), Rust);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 113, 35, 110), FVector(14, 240, 220), Rust);
            Box(FVector(X * 96, -82, 110), FVector(47, 14, 220), Rust);
        }
        Box(FVector(0, 35, 213), FVector(240, 240, 14), Rust);
        Box(FVector(0, 35, 7), FVector(240, 240, 14), Steel);
        Box(FVector(0, -82, 191), FVector(145, 14, 58), Rust);
        Box(FVector(0, -82, 27), FVector(145, 14, 54), Rust);
        Box(FVector(0, -5, 109), FVector(180, 6, 130), TEXT("Burnt"));
        for (int32 I = -3; I <= 3; ++I) Box(FVector(I * 20, -95, 90), FVector(6, 7, 123), Zinc);
        Fire(FVector(0, -55, 48), 80);
        for (int32 X : {-1, 1})
        {
            Pipe(FVector(X * 70, 75, 215), FVector(X * 70, 75, 365 + X * 35), 43, Steel);
            Drum(FVector(X * 70, 75, 368 + X * 35), 59, 8, Rust);
        }
        Fan(FVector(126, 35, 140), 94, 160, FRotator(90, 0, 0));
        Box(FVector(0, -160, 27), FVector(160, 150, 12), Steel, FRotator(0, 0, -11));
    }
    else if (CardId == TEXT("nitro_works"))
    {
        Drum(FVector(0, 10, 20), 230, 40, Concrete);
        for (int32 X : {-1, 1}) for (int32 Y : {-1, 1})
            Beam(FVector(X * 80, 10 + Y * 80, 40), FVector(X * 34, 10 + Y * 34, 315), 13, Steel);
        Drum(FVector(0, 10, 325), 150, 25, Zinc);
        Box(FVector(0, -10, 362), FVector(88, 105, 55), Steel);
        Pipe(FVector(0, -65, 362), FVector(0, -135, 362), 26, Copper);
        Orb(FVector(0, -140, 362), FVector(22, 7, 22), Signal);
        Fan(FVector(0, 42, 363), 59, 90, FRotator(0, 0, 90));
        Tank(FVector(-150, 90, 0), 65, 175, Teal);
        Pipe(FVector(-150, 90, 30), FVector(0, 10, 90), 12, Copper);
    }
    else if (CardId == TEXT("crimp_house"))
    {
        Box(FVector(0, 30, 14), FVector(260, 260, 28), Concrete);
        Drum(FVector(0, 30, 34), 100, 12, Steel);
        Drum(FVector(0, 30, 60), 45, 48, Zinc);
        Box(FVector(0, 30, 93), FVector(72, 80, 18), Rubber);
        Box(FVector(0, 70, 140), FVector(72, 14, 115), Rubber, FRotator(0, 0, -10));
        Beam(FVector(-49, 30, 84), FVector(49, 30, 84), 9, Zinc);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 49, 20, 116), FVector(15, 100, 12), Zinc);
            Pipe(FVector(X * 49, 30, 84), FVector(X * 49, 30, 116), 8, Zinc);
        }
        Beam(FVector(-105, 100, 0), FVector(-105, 100, 265), 14, Steel);
        Beam(FVector(-105, 100, 265), FVector(0, 45, 265), 14, Steel);
        Pipe(FVector(0, 45, 265), FVector(0, 45, 235), 9, Zinc);
        const int32 Helmet = Orb(FVector(0, 45, 216), FVector(80, 75, 48), Zinc);
        Move(Helmet, EMotion::Sway, FVector::UpVector, .8, 4, FVector(0, 45, 265));
        for (int32 X : {-1, 1}) Pipe(FVector(X * 30, 45, 225), FVector(X * 85, 95, 160), 5, Copper);
        Box(FVector(145, 75, 90), FVector(70, 110, 175), Teal);
        Box(FVector(145, 17, 120), FVector(51, 5, 62), Signal);
        Fan(FVector(145, 75, 195), 58, 100);
    }
    else if (CardId == TEXT("wanted_poster_board"))
    {
        Box(FVector(0, 25, 18), FVector(355, 235, 36), Rust);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 170, 95, 150), FVector(17, 17, 290), Zinc);
            const int32 Curtain = Box(FVector(X * 122, 88, 164), FVector(86, 5, 240), Red);
            Move(Curtain, EMotion::Sway, FVector::RightVector, .8, 2.3, FVector(X * 170, 88, 285), X);
        }
        Beam(FVector(-180, 95, 290), FVector(180, 95, 290), 22, Rust);
        for (int32 X : {-1, 1})
        {
            Orb(FVector(X * 59, 65, 210), FVector(88, 25, 115), X < 0 ? Chalk : Zinc);
            for (int32 E : {-1, 1}) Orb(FVector(X * 59 + E * 19, 50, 225), FVector(19, 5, 14), Steel);
        }
        for (int32 I = -3; I <= 3; ++I) Orb(FVector(I * 47, -97, 46), FVector(17), Lamp);
    }
    else if (CardId == TEXT("boot_hill"))
    {
        Box(FVector(0, 15, 12), FVector(340, 245, 24), Concrete);
        Box(FVector(0, 75, 125), FVector(250, 36, 220), Concrete);
        for (int32 I = 0; I < 6; ++I) Box(FVector(0, 55, 72 + I * 25), FVector(175 - I % 2 * 25, 3, 4), Zinc);
        for (int32 I = 0; I < 5; ++I)
        {
            const FVector P(-140 + I * 70, -100, 24);
            Drum(P + FVector(0, 0, 15), 12, 30, Canvas);
            const int32 Candle = Orb(P + FVector(0, 0, 35), FVector(6, 6, 13), Lamp);
            Move(Candle, EMotion::Breathe, FVector::UpVector, 3 + I * .2, .15, P, I);
        }
        Pipe(FVector(-130, 90, 0), FVector(-130, 90, 300), 5, Steel);
        Flag(FVector(-130, 90, 50), 190, Canvas);
        Tree(FVector(180, 100, 0), 135, nullptr);
    }
    else if (CardId == TEXT("boarding_house"))
    {
        Part(RockMesh, FVector(0, 105, 105), FVector(395, 205, 225), nullptr);
        Box(FVector(0, -5, 94), FVector(150, 12, 165), TEXT("Burnt"));
        for (int32 X : {-1, 1})
        {
            Beam(FVector(X * 88, -17, 0), FVector(X * 75, -17, 205), 22, Rust);
            Beam(FVector(X * 43, -210, 8), FVector(X * 43, 95, 8), 8, Steel);
        }
        Beam(FVector(-92, -17, 200), FVector(92, -17, 200), 26, Rust);
        Box(FVector(0, -130, 63), FVector(106, 104, 87), Rust);
        for (int32 X : {-1, 1}) Wheel(FVector(X * 59, -135, 24), 38);
        Fan(FVector(150, 5, 215), 105, 85, FRotator(0, 0, 90));
        Pipe(FVector(150, 50, 0), FVector(150, 50, 225), 16, Steel);
        Orb(FVector(0, -28, 185), FVector(17), Lamp);
    }
    else if (CardId == TEXT("rustlers_corral"))
    {
        Frame(FVector(0, 90, 0), FVector(280, 130, 175), Rust);
        Box(FVector(0, 20, 197), FVector(295, 16, 38), Steel);
        for (int32 I = 0; I < 3; ++I)
        {
            const FVector P(-140 + I * 140, -90, 0);
            Wheel(P + FVector(0, -65, 39), 69); Wheel(P + FVector(0, 65, 39), 69);
            Beam(P + FVector(0, -65, 40), P + FVector(0, 35, 90), 9, Zinc);
            Beam(P + FVector(0, 65, 40), P + FVector(0, -25, 87), 9, Steel);
            Orb(P + FVector(0, -5, 88), FVector(40, 63, 35), I == 1 ? Red : Teal);
            Box(P + FVector(0, 38, 87), FVector(36, 48, 12), Rubber);
            for (int32 X : {-1, 1}) Pipe(P + FVector(X * 11, -65, 40), P + FVector(X * 11, -53, 108), 6, Zinc);
            Pipe(P + FVector(0, -53, 106), P + FVector(0, -53, 115), 9, Steel);
            Beam(P + FVector(-13, -53, 108), P + FVector(13, -53, 108), 8, Steel);
            Beam(P + FVector(0, -53, 106), P + FVector(0, 35, 87), 8, Steel);
            Beam(P + FVector(-28, -53, 115), P + FVector(28, -53, 115), 5, Zinc);
        }
        Flag(FVector(-190, 110, 0), 295, Red);
    }
    else if (CardId == TEXT("quaker_settlement"))
    {
        for (int32 I = 0; I < 3; ++I)
        {
            const FVector P(-155 + I * 155, 55 + (I % 2) * 45, 0);
            Frame(P, FVector(105, 105, 110 + I % 2 * 35), Canvas, false);
            Cone(P + FVector(0, 0, 140 + I % 2 * 35), 165, 85, Rust);
            Box(P + FVector(0, -56, 39), FVector(35, 5, 74), Steel);
        }
        Tree(FVector(165, -95, 0), 155, nullptr);
        Drum(FVector(-60, -115, 20), 75, 40, Concrete);
        Pipe(FVector(-60, -115, 40), FVector(-60, -115, 97), 8, Zinc);
        const int32 Pump = Box(FVector(-60, -122, 106), FVector(8, 67, 7), Steel);
        Move(Pump, EMotion::Sway, FVector::ForwardVector, 1.1, 9, FVector(-60, -115, 97));
        Crates(FVector(0, -110, 0), 2);
    }
    else if (CardId == TEXT("chuckwagon"))
    {
        Frame(FVector(-85, 45, 0), FVector(190, 230, 180), Concrete);
        for (int32 X : {-1, 1})
        {
            Tank(FVector(-85 + X * 48, 95, 185), 62, 170 + X * 30, Steel);
        }
        for (int32 I = 0; I < 3; ++I)
        {
            Drum(FVector(140, -70 + I * 75, 72), 50, 120, Copper);
            Pipe(FVector(140, -70 + I * 75, 0), FVector(140, -70 + I * 75, 230), 9, Steel);
            for (int32 J = 0; J < 3; ++J) Drum(FVector(140, -70 + I * 75, 175 + J * 17), 35, 8, Chalk);
        }
        Fan(FVector(-85, -78, 127), 105, 180, FRotator(0, 0, 90));
        Fence(FVector(200, -145, 0), FVector(200, 155, 0), 85);
    }
    else if (CardId == TEXT("horse_trader"))
    {
        Box(FVector(65, 85, 95), FVector(220, 165, 185), Teal);
        Box(FVector(65, -2, 91), FVector(155, 10, 100), Steel);
        Box(FVector(65, -116, 61), FVector(170, 230, 14), Rubber, FRotator(0, 0, -12));
        for (int32 I = 0; I < 4; ++I)
        {
            const int32 Bale = Box(FVector(20 + I % 2 * 85, -160 + I / 2 * 85, 70 + I / 2 * 18), FVector(48, 50, 32), I % 2 ? Rust : Zinc);
            Move(Bale, EMotion::Translate, FVector(0, 1, .21), .8, 12, FVector::ZeroVector, I * 1.2);
        }
        for (int32 I = 0; I < 3; ++I) Tank(FVector(-170, -90 + I * 92, 0), 65, 105, I == 1 ? Red : Rust);
        Fan(FVector(65, 90, 211), 110, 130);
    }
    else if (CardId == TEXT("pony_express_station"))
    {
        Frame(FVector(-60, 65, 0), FVector(215, 145, 165), Teal);
        Cross(FVector(-60, -12, 144), 62);
        Antenna(FVector(-135, 95, 170), 210, true);
        Bed(FVector(135, 10, 0), Canvas);
        for (int32 X : {-1, 1}) Pipe(FVector(135 + X * 38, -80, 48), FVector(135 + X * 38, 95, 48), 6, Zinc);
        Crates(FVector(-160, -100, 0), 3);
        Flag(FVector(190, 130, 0), 275, Chalk);
        Tank(FVector(5, 120, 0), 50, 100, Red);
    }
    else if (CardId == TEXT("lookout_ridge"))
    {
        for (int32 I = 0; I < 3; ++I)
            Part(RockMesh, FVector(-135 + I * 130, 40 + I % 2 * 40, 78 + I * 33), FVector(230, 260, 180 + I * 65), nullptr);
        Box(FVector(100, 30, 290), FVector(120, 120, 12), Rust);
        Antenna(FVector(125, 75, 290), 150, true);
        Fence(FVector(160, -20, 220), FVector(190, 90, 270), 65);
        Flag(FVector(-180, 55, 120), 195, Canvas);
        Crates(FVector(-145, -100, 0), 2);
    }
    else if (CardId == TEXT("dance_hall"))
    {
        Frame(FVector(0, 70, 0), FVector(310, 190, 210), Canvas);
        Box(FVector(0, -31, 236), FVector(330, 16, 66), Rust);
        for (int32 X : {-1, 1})
        {
            Box(FVector(X * 111, -30, 125), FVector(57, 8, 83), Glass);
            const int32 Door = Box(FVector(X * 32, -34, 83), FVector(60, 9, 66), Rust);
            Move(Door, EMotion::Sway, FVector::UpVector, .7, 6, FVector(X * 63, -34, 83), X * .7);
            Drum(FVector(X * 166, -116, 38), 58, 76, Rust);
        }
        Box(FVector(0, -80, 20), FVector(350, 100, 35), Concrete);
        Beam(FVector(-175, -140, 44), FVector(175, -140, 44), 7, Zinc);
        for (int32 X : {-1, 1}) Orb(FVector(X * 90, -43, 189), FVector(18), Lamp);
    }
    else if (CardId == TEXT("apothecary"))
    {
        Frame(FVector(-50, 40, 0), FVector(245, 210, 185), Chalk);
        Box(FVector(-50, -52, 76), FVector(215, 65, 12), Zinc);
        for (int32 I = 0; I < 4; ++I)
        {
            Drum(FVector(-130 + I * 52, -52, 107), 19, 54 + I * 9, Glass);
            Orb(FVector(-130 + I * 52, -52, 94), FVector(30, 30, 25), I % 2 ? Teal : Copper);
        }
        const FVector Pivot(160, 65, 170);
        Pipe(FVector(160, 65, 0), Pivot, 20, Steel);
        const int32 Lens = Drum(Pivot + FVector(0, -35, 30), 100, 15, Zinc, FRotator(0, 0, 45));
        Move(Lens, EMotion::Sway, FVector::UpVector, .4, 24, Pivot);
        Fan(FVector(-50, 40, 210), 80, 95);
        Tank(FVector(160, -105, 0), 70, 105, Teal);
    }
    else if (CardId == TEXT("cattlemen_s_club"))
    {
        Frame(FVector(0, 65, 0), FVector(315, 215, 185), Steel, false);
        Box(FVector(0, 178, 205), FVector(340, 20, 90), Concrete);
        Box(FVector(0, 166, 210), FVector(215, 4, 52), Teal);
        Box(FVector(0, 5, 90), FVector(205, 150, 12), Zinc);
        for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) Box(FVector(X * 75, 5 + Y * 48, 45), FVector(10, 10, 90), Steel);
        for (int32 I = 0; I < 7; ++I) Cone(FVector(-60 + I % 4 * 40, -30 + I / 4 * 60, 107), 14, 21, I % 2 ? Red : Teal);
        Antenna(FVector(-190, 135, 0), 340, true);
        Antenna(FVector(190, 105, 0), 250, false);
        Crates(FVector(105, -140, 0), 3);
        Flag(FVector(-180, -130, 0), 190, Red);
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_CAMP_VISUAL_ERROR: unsupported card %s"), *CardId);
        DesignId = TEXT("unsupported:") + CardId;
    }
    DressIdentity();
    SetCondition(0, false);
}

void UOldWestCampVisuals::AppendHoldingDebugComponents(TArray<UStaticMeshComponent*>& Out) const
{
    for (int32 Index : {HoldingPart, HoldingRuinPart, HoldingDamagedPart})
        if (Parts.IsValidIndex(Index) && IsValid(Parts[Index])) Out.Add(Parts[Index]);
    for (UStaticMeshComponent* Component : GroundParts)
        if (IsValid(Component)) Out.Add(Component);
}

bool UOldWestCampVisuals::BuildHolding(const FString& Asset, bool Expansion, float PresentationScale)
{
    const FString Name = TEXT("SM_Holding_") + Asset;
    const FString Folder = Expansion ? TEXT("/Game/Art/Western/ExpansionHoldings/") : TEXT("/Game/Art/Western/Holdings/");
    const FString Path = Folder + Asset + TEXT("/") + Name + TEXT(".") + Name;
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path);
    if (!Mesh) return false;
    // Imported in centimetres, centred, ground at zero, entrance toward -Y.
    // Fit the battlefield lane: 6 m wide, 4.8 m deep, never enlarged.
    const FVector Size = Mesh->GetBoundingBox().GetSize().ComponentMax(FVector(1.0));
    const float Scale = FMath::Min3(PresentationScale, 600.f / static_cast<float>(Size.X), 480.f / static_cast<float>(Size.Y));
    // Condition index 1 gives damaged holdings the soot variant; it never tilts.
    NextConditionIndex = 1;
    HoldingPart = Part(*Path, FVector(0, 0, Size.Z * Scale * .5f), Size * Scale, nullptr);
    const FString RuinName = TEXT("SM_HoldingRuin_") + Asset;
    const FString RuinPath = Folder + Asset + TEXT("/") + RuinName;
    if (Expansion && HoldingPart != INDEX_NONE && FPackageName::DoesPackageExist(RuinPath))
        if (UStaticMesh* Ruin = LoadObject<UStaticMesh>(nullptr, *(RuinPath + TEXT(".") + RuinName)))
        {
            // Both authored meshes share the healthy source's exact origin and
            // scale. Never fit the lower ruin independently to the lane.
            const FBox Bounds = Ruin->GetBoundingBox();
            HoldingRuinPart = Part(*(RuinPath + TEXT(".") + RuinName),
                Bounds.GetCenter() * Scale, Bounds.GetSize() * Scale, nullptr);
        }
    const FString DamagedName = TEXT("SM_HoldingDamaged_") + Asset;
    const FString DamagedPath = Folder + Asset + TEXT("/") + DamagedName;
    if (Expansion && HoldingPart != INDEX_NONE && FPackageName::DoesPackageExist(DamagedPath))
        if (UStaticMesh* Damaged = LoadObject<UStaticMesh>(nullptr, *(DamagedPath + TEXT(".") + DamagedName)))
        {
            const FBox Bounds = Damaged->GetBoundingBox();
            HoldingDamagedPart = Part(*(DamagedPath + TEXT(".") + DamagedName),
                Bounds.GetCenter() * Scale, Bounds.GetSize() * Scale, nullptr);
        }
    if (Expansion)
        for (int32 Index : {HoldingPart, HoldingRuinPart, HoldingDamagedPart})
            if (Parts.IsValidIndex(Index))
            {
                // These small shared atlases must survive a tactical-to-close
                // camera cut. Scope residency to instantiated components;
                // destroying the component removes its streaming demand.
                Parts[Index]->bForceMipStreaming = true;
                Parts[Index]->MarkRenderStateDirty();
            }
    if (HoldingPart != INDEX_NONE) BuildHoldingGround(Asset, Scale, Expansion);
    return HoldingPart != INDEX_NONE;
}

void UOldWestCampVisuals::BuildHoldingGround(const FString& Asset, float HoldingScale, bool Expansion)
{
    // Each holding's irregular, setting-specific base shares the holding's
    // origin and scale. Columns are 13.5 m apart and crew stand 4.8 m in front:
    // the base stays within 11 m wide, and within 7 m deep where it carries
    // river water so nobody stands in the river (9 m on dry ground).
    const FString Root = Expansion ? TEXT("/Game/Art/Western/ExpansionHoldings/") : TEXT("/Game/Art/Western/Holdings/");
    const FString Folder = Root + Asset + TEXT("/");
    const FString BaseName = TEXT("SM_HoldingBase_") + Asset, WaterName = TEXT("SM_HoldingWater_") + Asset;
    if (!GetOwner() || !FPackageName::DoesPackageExist(Folder + BaseName)) return;
    UStaticMesh* Base = LoadObject<UStaticMesh>(nullptr, *(Folder + BaseName + TEXT(".") + BaseName));
    UStaticMesh* Water = FPackageName::DoesPackageExist(Folder + WaterName)
        ? LoadObject<UStaticMesh>(nullptr, *(Folder + WaterName + TEXT(".") + WaterName)) : nullptr;
    if (!Base) return;
    const FVector Size = Base->GetBoundingBox().GetSize().ComponentMax(FVector(1.0));
    const float ScaleXY = FMath::Min3(HoldingScale, 1100.f / static_cast<float>(Size.X),
        (Water ? 700.f : 900.f) / static_cast<float>(Size.Y));
    for (UStaticMesh* Mesh : {Base, Water})
    {
        if (!Mesh) continue;
        UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(GetOwner());
        GetOwner()->AddInstanceComponent(Component);
        Component->SetupAttachment(this);
        Component->SetMobility(EComponentMobility::Movable);
        Component->SetStaticMesh(Mesh);
        // Opt in individually reviewed dry bases. The material retains its
        // original pilot asset path; foundation dimensions are per holding.
        const auto* Reviewed = Expansion ? OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId)) : nullptr;
        if (Reviewed && (Reviewed->GroundFitExtent[2] > 0.f || Asset == TEXT("SmugglersLanding")) && Mesh == Base)
        {
            const TCHAR* FitPath = Asset == TEXT("SmugglersLanding")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002/M_LandingDryBankV003.M_LandingDryBankV003")
                : Asset == TEXT("ArmySurgeonsTent")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitTentV001/M_ArmySurgeonsTentGroundFit.M_ArmySurgeonsTentGroundFit")
                : Asset == TEXT("BountyOffice")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitBountyOfficeV001/M_BountyOfficeGroundFit.M_BountyOfficeGroundFit")
                : Asset == TEXT("RobbersRoost")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitRobbersRoostV001/M_RobbersRoostGroundFit.M_RobbersRoostGroundFit")
                : Asset == TEXT("Gallows")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitGallowsV001/M_GallowsGroundFit.M_GallowsGroundFit")
                : Asset == TEXT("LookoutRidge")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitLookoutRidgeV001/M_LookoutRidgeGroundFit.M_LookoutRidgeGroundFit")
                : Asset == TEXT("RockslideRidge")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitRockslideV001/M_RockslideRidgeGroundFit.M_RockslideRidgeGroundFit")
                : Asset == TEXT("Courthouse")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitCourthouseV001/M_CourthouseGroundFit.M_CourthouseGroundFit")
                : Asset == TEXT("FreeHomestead")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitFreeHomesteadV001/M_FreeHomesteadGroundFit.M_FreeHomesteadGroundFit")
                : Asset == TEXT("Chuckwagon")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitChuckwagonV001/M_ChuckwagonGroundFit.M_ChuckwagonGroundFit")
                : Asset == TEXT("PonyExpressStation")
                ? TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitPonyExpressStationV001/M_PonyExpressStationGroundFit.M_PonyExpressStationGroundFit")
                : TEXT("/Game/Art/Western/ExpansionHoldings/GroundFitV001/M_PostOfficeGroundFit.M_PostOfficeGroundFit");
            if (UMaterialInterface* Fit = LoadObject<UMaterialInterface>(nullptr, FitPath))
            {
                GroundFitMaterial = UMaterialInstanceDynamic::Create(Fit, this);
                GroundFitMaterial->SetVectorParameterValue(TEXT("FoundationExtent"), FLinearColor(
                    Reviewed->GroundFitExtent[0], Reviewed->GroundFitExtent[1], Reviewed->GroundFitExtent[2]));
                Component->SetMaterial(0, GroundFitMaterial);
                // Material's explicit WPO bound covers the displaced surface.
            }
        }
        Component->SetRelativeTransform(FTransform(FRotator::ZeroRotator, FVector::ZeroVector, FVector(ScaleXY, ScaleXY, HoldingScale)));
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetGenerateOverlapEvents(false);
        Component->SetCanEverAffectNavigation(false);
        Component->SetCastShadow(Mesh == Base);
        Component->RegisterComponent();
        GroundParts.Add(Component);
    }
    UpdateHoldingGroundFit();
}

void UOldWestCampVisuals::UpdateHoldingGroundFit()
{
    const bool Landing = DesignId == TEXT("smuggler_s_landing") && GroundParts.Num() > 0;
    // Healthy portrait construction precedes its first explicit condition
    // update. The owner tag excludes that initial build as well.
    const bool Portrait = GroundFitPortrait ||
        (GetOwner() && GetOwner()->ActorHasTag(TEXT("OldWestPortraitPreview")));
    if (!GroundFitMaterial && !Landing) return;
    if (!GroundRegion.IsValid() && GetWorld())
    {
        TActorIterator<AOldWestRegion> It(GetWorld());
        if (It) GroundRegion = *It;
    }
    const FVector Origin = GetComponentLocation();
    if (Landing && GroundRegion.IsValid())
    {
        UStaticMeshComponent* Base = GroundParts[0];
        const float Yaw = FMath::DegreesToRadians(Base->GetComponentRotation().Yaw);
        const FVector Frame(FMath::Cos(Yaw),FMath::Sin(Yaw),Base->GetComponentScale().X);
        if (GroundFitMaterial) GroundFitMaterial->SetVectorParameterValue(TEXT("GroundFrame"),FLinearColor(Frame));
        // This public, static miniature has level water. Fit visual terrain
        // below its wet footprint; the dry apron follows the fitted surface.
        // Water, boat, ramp and the authoritative collider remain unchanged.
        GroundRegion->SetLandingFoundation(this,Origin,Frame,!Portrait && !GetOwner()->IsHidden());
    }
    if (!GroundFitMaterial) return;
    GroundFitMaterial->SetVectorParameterValue(TEXT("GroundOrigin"), FLinearColor(Origin));
    const int32 RegionIndex = GroundRegion.IsValid() ? GroundRegion->GetRegionIndex() : -1;
    GroundFitMaterial->SetScalarParameterValue(TEXT("Region"), FMath::Max(0, RegionIndex));
    GroundFitMaterial->SetScalarParameterValue(TEXT("FitEnabled"), !Portrait && RegionIndex >= 0 ? 1.f : 0.f);
}

void UOldWestCampVisuals::OnComponentDestroyed(bool DestroyingHierarchy)
{
    if (GroundRegion.IsValid())
        GroundRegion->SetLandingFoundation(this,FVector::ZeroVector,FVector::ZeroVector,false);
    Super::OnComponentDestroyed(DestroyingHierarchy);
}

void UOldWestCampVisuals::DressIdentity()
{
    auto Is=[this](std::initializer_list<const TCHAR*> Names){for(const TCHAR* N:Names)if(DesignId==N)return true;return false;};
    // Static dressing only. Existing machinery, camera shots and animations
    // retain their authored transforms and timing. All added parts participate
    // in the same damage/ruin/repair material and geometry lifecycle.
    auto Bench=[this](FVector P,const TCHAR* M) {
        Box(P+FVector(0,0,74),FVector(112,62,9),M);
        for(int X:{-1,1})for(int Y:{-1,1})Box(P+FVector(X*47,Y*23,35),FVector(7,7,70),Steel);
    };
    auto Gauge=[this](FVector P) {
        Drum(P,22,7,Steel,FRotator(0,0,90));Drum(P+FVector(0,-5,0),17,2,Chalk,FRotator(0,0,90));
        Beam(P+FVector(0,-7,0),P+FVector(5,-7,5),1.4f,Red);
    };
    auto Crate=[this](FVector P,const TCHAR* M) {
        Box(P+FVector(0,0,26),FVector(66,47,49),M);
        for(int X:{-1,1})Box(P+FVector(X*25,-25,26),FVector(5,3,47),Steel);
        for(int Z:{5,45})Box(P+FVector(0,-25,Z),FVector(65,3,5),Steel);
        Box(P+FVector(0,-27,27),FVector(18,3,7),Chalk);
    };
    auto LampPost=[this](FVector P,float H) {
        Pipe(P,P+FVector(0,0,H),5,Steel);Beam(P+FVector(0,0,H),P+FVector(23,0,H),4,Steel);
        Box(P+FVector(23,0,H-6),FVector(20,18,12),Steel);Box(P+FVector(23,-10,H-6),FVector(15,2,7),Lamp);
    };
    auto Round=[this](FVector P) {
        Drum(P+FVector(0,0,22),12,44,Copper);Cone(P+FVector(0,0,52),12,16,Steel);
    };
    if(Is({TEXT("saloon"),TEXT("silver_mine"),TEXT("barn_raising"),TEXT("army_surgeon_s_tent"),TEXT("pony_express_station"),TEXT("apothecary"),TEXT("crimp_house"),TEXT("jailhouse")})) {
        const FVector P(-190,-145,0);Bench(P,TEXT("ClinicPaint"));
        for(int I=0;I<3;++I){Drum(P+FVector(-31+I*29,0,92),18,28,I==0?Red:Glass);Drum(P+FVector(-31+I*29,0,108),19,5,Zinc);}
        Pipe(P+FVector(63,0,0),P+FVector(63,0,165),4,Zinc);Beam(P+FVector(63,0,165),P+FVector(33,0,165),3,Zinc);
        Box(P+FVector(33,0,144),FVector(21,11,32),Glass);Pipe(P+FVector(33,0,127),P+FVector(20,0,90),2,Rubber);
        Cross(P+FVector(0,-33,55),27);Crate(FVector(155,-125,0),TEXT("ClinicPaint"));
    } else if(Is({TEXT("bunkhouse"),TEXT("bordello"),TEXT("cattlemen_s_club"),TEXT("mountain_hideout"),TEXT("stagecoach_station"),TEXT("church_bell_tower"),TEXT("telegraph_office")})) {
        const FVector P(-185,-135,0);Bench(P,Wood);
        Box(P+FVector(0,0,99),FVector(80,40,43),Steel);Box(P+FVector(-17,-22,100),FVector(28,3,19),Glass);
        for(int I=0;I<3;++I)Drum(P+FVector(12+I*10,-24,99),5,5,Copper,FRotator(0,0,90));
        for(int I=0;I<5;++I)Box(P+FVector(-29+I*13,-22,85),FVector(8,3,2),Chalk);
        Pipe(P+FVector(31,12,118),P+FVector(31,12,192),2,Zinc);
        Box(P+FVector(12,-4,125),FVector(44,14,9),Rubber);LampPost(FVector(160,-150,0),158);
        if(DesignId==TEXT("bunkhouse")) {
            Box(FVector(0,-157,157),FVector(115,8,75),Wood);Box(FVector(0,-162,157),FVector(105,2,65),Canvas);
            for(int I=0;I<6;++I)Beam(FVector(-40+I*15,-164,138),FVector(-26+I*11,-164,172),2,I%2?Red:Teal);
        }
    } else if(Is({TEXT("cattle_ranch"),TEXT("roundup_corral"),TEXT("railroad_work_camp"),TEXT("undertaker"),TEXT("powder_magazine"),TEXT("chuckwagon"),TEXT("boarding_house"),TEXT("horse_trader"),TEXT("pawn_shop")})) {
        const FVector P(-175,-130,0);Bench(P,Steel);
        Box(P+FVector(0,5,107),FVector(74,25,56),Teal);Gauge(P+FVector(-18,-10,113));Gauge(P+FVector(18,-10,113));
        for(int I=0;I<6;++I)Box(P+FVector(-31+I*12,-10,91),FVector(7,4,6),I%2?Lamp:Rubber);
        Pipe(P+FVector(43,0,78),P+FVector(75,0,15),7,Rubber);
        for(int I=0;I<5;++I){Box(FVector(180,-155,14+I*6),FVector(70,80,5),Zinc);}
        for(int I=0;I<4;++I)Box(FVector(-47+I*31,-202,13),FVector(19,36,3),I%2?Steel:Chalk,FRotator(0,28,0));
        LampPost(FVector(220,-105,0),185);
    } else if(Is({TEXT("army_fort"),TEXT("dynamite_shack"),TEXT("toll_bridge"),TEXT("homestead_cabin"),TEXT("gatling_emplacement"),TEXT("artillery_battery"),TEXT("gunsmith"),TEXT("vigilance_committee"),TEXT("nitro_works"),TEXT("timber_ram"),TEXT("wagon_fort")})) {
        const FVector P(-175,-130,0);Crate(P,Wood);Crate(P+FVector(0,55,0),Steel);
        for(int I=0;I<4;++I)Round(P+FVector(-23+I*15,0,52));
        Box(FVector(165,-120,43),FVector(90,50,86),Steel);Box(FVector(165,-148,43),FVector(80,4,75),Rust);
        for(int I=0;I<4;++I)Box(FVector(136+I*19,-151,44),FVector(4,3,53),Zinc);
        for(int I=0;I<4;++I)Orb(FVector(-68+I*45,-208,13),FVector(52,29,25),Canvas);
    } else if(Is({TEXT("revival_tent"),TEXT("packer_s_cabin"),TEXT("rodeo_grounds"),TEXT("land_office"),TEXT("logging_camp"),TEXT("gallows"),TEXT("bare_knuckle_ring"),TEXT("boot_hill")})) {
        for(int S:{-1,1}) {
            const FVector P(S*180,-130,0);Drum(P+FVector(0,0,13),62,26,Concrete);Drum(P+FVector(0,0,57),24,65,Wood);
            Orb(P+FVector(0,0,101),FVector(38,30,43),Chalk);
            for(int E:{-1,1})Orb(P+FVector(E*8,-14,105),FVector(8,6,10),Rubber);
            Box(P+FVector(0,-13,85),FVector(21,8,9),Chalk);
            for(int I=0;I<3;++I)Drum(P+FVector(-38+I*20,-20,15),7,25,Canvas);
        }
    } else if(Is({TEXT("riverboat"),TEXT("courthouse"),TEXT("rustlers_corral"),TEXT("coal_yard"),TEXT("robbers_roost")})) {
        Wheel(FVector(-180,-120,30),60,false);Wheel(FVector(-178,-55,30),60,false);
        const FVector P(180,-125,0);Drum(P+FVector(0,0,55),64,110,Red);
        for(int Z:{15,94})Drum(P+FVector(0,0,Z),67,6,Steel);
        Pipe(P+FVector(0,0,110),P+FVector(0,0,145),7,Zinc);Beam(P+FVector(-22,0,145),P+FVector(22,0,145),4,Zinc);
        Pipe(P+FVector(17,0,118),P+FVector(50,-10,35),5,Rubber);Crate(FVector(160,10,0),Wood);
    } else if(Is({TEXT("hot_springs"),TEXT("trading_post"),TEXT("quaker_settlement"),TEXT("rockslide_ridge"),TEXT("lookout_ridge")})) {
        const FVector P(-175,-130,0);Box(P+FVector(0,0,25),FVector(96,70,46),Wood);Box(P+FVector(0,0,49),FVector(83,57,5),TEXT("Burnt"));
        for(int I=0;I<5;++I) {
            Pipe(P+FVector(-32+I*16,0,50),P+FVector(-30+I*16,0,75),2,Wood);
            Orb(P+FVector(-27+I*16,0,70),FVector(13,5,17),Teal);
        }
        Drum(FVector(170,-110,45),52,90,Zinc);Pipe(FVector(170,-110,65),FVector(110,-110,65),5,Copper);
        for(int I=0;I<6;++I)Box(FVector(-20+I%2*46,-155-I/2*32,3),FVector(38,26,6),Concrete);
    } else if(Is({TEXT("stockyards"),TEXT("general_store"),TEXT("freight_warehouse"),TEXT("salvage_yard"),TEXT("smuggler_s_landing"),TEXT("bounty_office")})) {
        const FVector P(-160,-145,0);Bench(P,Wood);Crate(P+FVector(0,0,79),Teal);
        for(int I=0;I<3;++I){Drum(FVector(147+I*24,-135,33),19,66,I%2?Copper:Steel);}
        for(int I=0;I<4;++I)Crate(FVector(150+(I%2)*12,-60+(I%2)*58,(I/2)*50),I%2?Wood:Steel);
        LampPost(FVector(-230,-95,0),185);
    } else if(Is({TEXT("livery_barn"),TEXT("breaking_pen"),TEXT("railroad_depot"),TEXT("post_office"),TEXT("free_homestead"),TEXT("wanted_poster_board"),TEXT("dance_hall")})) {
        const FVector P(-175,-130,0);Bench(P,Wood);
        for(int I=0;I<3;++I){Drum(P+FVector(-29+I*27,0,91),12,22,Zinc);}
        for(int S:{-1,1}){Drum(P+FVector(S*72,-5,40),37,8,Wood);Pipe(P+FVector(S*72,-5,0),P+FVector(S*72,-5,38),5,Steel);}
        Box(FVector(180,-140,65),FVector(70,8,72),Wood);Box(FVector(180,-145,65),FVector(58,2,60),Canvas);
        for(int I=0;I<5;++I)Box(FVector(174,-147,85-I*10),FVector(38-I%2*12,2,2),Steel);
        for(int S:{-1,1})Box(FVector(180+S*27,-140,22),FVector(5,8,44),Wood);
    } else {
        UE_LOG(LogTemp,Error,TEXT("OLDWEST_CAMP_VISUAL_ERROR: missing static dressing for %s"),*DesignId);
    }
}

void UOldWestCampVisuals::SetCondition(int32 Damage, bool Destroyed, bool Portrait)
{
    GroundFitPortrait = Portrait;
    UpdateHoldingGroundFit();
    CurrentDamage = FMath::Max(0, Damage);
    Ruined = Destroyed;
    const auto* Expansion = OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId));
    const bool Geological = Expansion && Expansion->GeologicalConditions;
    const bool CompleteAuthoredRuin = HoldingRuinPart != INDEX_NONE && Expansion && Expansion->RuinIncludesDebris;
    if (Ruined && AshParts.IsEmpty() && !CompleteAuthoredRuin)
    {
        FRandomStream Random(GetTypeHash(DesignId));
        TArray<int32> Anchors;
        const int32 OriginalParts = Parts.Num();
        for (int32 I = 0; I < OriginalParts; ++I)
        {
            if (!IsValid(Parts[I]) || !Parts[I]->GetStaticMesh() || FlameParts.Contains(I) || FoliageParts.Contains(I) || I == HoldingRuinPart) continue;
            const FBox Bounds = Parts[I]->GetStaticMesh()->GetBoundingBox().TransformBy(RestTransforms[I]);
            const FVector Size = Bounds.GetSize();
            if (Size.GetMax() > 65.f) Anchors.Add(I);
            const FString Name = Parts[I]->GetStaticMesh()->GetName();
            // Intact roof/wall panels become shattered debris, not merely
            // tilted versions of the healthy building's large flat shapes.
            if (Bounds.GetCenter().Z > 55.f && Size.GetMax() > 140.f &&
                (Name.Contains(TEXT("Roof")) || Name.Contains(TEXT("Cladding")) ||
                 (Name == TEXT("Cube") && Size.GetMin() < 22.f && Size.GetMax() > 200.f)))
                RuinConsumedParts.Add(I);
        }
        const int32 Clusters = FMath::Clamp(Anchors.Num() / 5, 7, 14);
        for (int32 I = 0; I < Clusters && !Anchors.IsEmpty(); ++I)
        {
            const int32 Anchor = Anchors[Random.RandRange(0, Anchors.Num()-1)];
            const FBox Bounds = Parts[Anchor]->GetStaticMesh()->GetBoundingBox().TransformBy(RestTransforms[Anchor]);
            FVector Position = Bounds.GetCenter();
            Position.X += Random.FRandRange(-65.f,65.f);
            Position.Y += Random.FRandRange(-65.f,65.f);
            if (Anchor == HoldingPart)
            {
                // A charred holding keeps its footprint; fallen timber lies at
                // its front and sides where the battlefield camera sees it.
                const int32 Edge = I % 3;
                Position.X = Edge == 0 ? Random.FRandRange(Bounds.Min.X, Bounds.Max.X) : (Edge == 1 ? Bounds.Min.X - 25.f : Bounds.Max.X + 25.f);
                Position.Y = Edge == 0 ? Bounds.Min.Y - 30.f : Random.FRandRange(Bounds.Min.Y, Bounds.GetCenter().Y);
            }
            const FString& Substrate = RestMaterials[Anchor];
            const bool Timber = Anchor == HoldingPart || Substrate.Contains(TEXT("Wood")) || Substrate.Contains(TEXT("Tree")) || DesignId == TEXT("logging_camp") || DesignId == TEXT("trading_post");
            const TCHAR* Kind = Timber ? TEXT("Timber") : (I % 3 == 0 ? TEXT("Metal") : TEXT("Concrete"));
            const FString Name = FString::Printf(TEXT("SM_Ruin_%s_%d"),Kind,I % 4);
            const FString Path = TEXT("/Game/Art/Camps/Ruins/Meshes/") + Name + TEXT(".") + Name;
            const float Height = Random.FRandRange(12.f,28.f);
            const int32 Debris = Part(*Path,FVector(Position.X,Position.Y,Height*.5f),
                FVector(Random.FRandRange(100.f,170.f),Random.FRandRange(65.f,130.f),Height),nullptr,
                FRotator(0,Random.FRandRange(-180.f,180.f),0));
            if (Debris != INDEX_NONE)
            {
                AshParts.Add(Debris);
                Parts[Debris]->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            }
            // Ash gathers under fragments and trails downwind in disconnected,
            // uneven strips. There is no camp-wide circular ground overlay.
            for (int32 Drift = 0; Drift < 2; ++Drift)
            {
                const FString AshName = FString::Printf(TEXT("SM_Ruin_AshDrift_%d"),(I+Drift)%4);
                const FString AshPath = TEXT("/Game/Art/Camps/Ruins/Meshes/")+AshName+TEXT(".")+AshName;
                const float Depth = Random.FRandRange(.6f,1.6f);
                const int32 Ash = Part(*AshPath,FVector(Position.X + Drift*45.f,Position.Y + Random.FRandRange(-35.f,35.f),Depth*.5f),
                    FVector(Random.FRandRange(100.f,210.f),Random.FRandRange(35.f,75.f),Depth),nullptr,
                    FRotator(0,Random.FRandRange(-25.f,35.f),0));
                if (Ash != INDEX_NONE)
                {
                    AshParts.Add(Ash);
                    Parts[Ash]->SetCollisionEnabled(ECollisionEnabled::NoCollision);
                    Parts[Ash]->SetCastShadow(false);
                }
            }
        }
    }
    if(Ruined&&!Geological&&!IsValid(RuinSmoke)) {
        RuinSmoke=NewObject<UOldWestFireVisuals>(GetOwner());
        GetOwner()->AddInstanceComponent(RuinSmoke);
        RuinSmoke->SetupAttachment(this);RuinSmoke->SetRelativeLocation(FVector(0,0,20));
        RuinSmoke->RegisterComponent();RuinSmoke->Build(300.f,Portrait ? 260.f : 360.f,float(GetTypeHash(DesignId) % 997) / 997.f,0.f,true,true);
        RuinSmoke->SetEmissionScale(0.f,350.f);RuinSmoke->SetSmokeOnly(true, Portrait ? .38f : .55f);
    }
    if(IsValid(RuinSmoke))RuinSmoke->SetExtinguished(!Ruined || Geological);

    if (CurrentDamage > 0 && !Ruined && !Geological && DamageFires.IsEmpty())
    {
        // Start at an exposed surface rather than inside a shelter's opaque
        // walls. Camp roofs vary considerably; derive the fuel height from
        // the actual authored geometry at each ignition point.
        for (int32 I = 0; I < 2; ++I)
        {
            FVector Base(I == 0 ? -95.f : 95.f, I == 0 ? -35.f : 35.f, 30.f);
            if (Parts.IsValidIndex(HoldingPart) && IsValid(Parts[HoldingPart]) && Parts[HoldingPart]->GetStaticMesh())
            {
                UStaticMeshComponent* Holding = Parts[HoldingPart];
                const FBox Local = Holding->GetStaticMesh()->GetBoundingBox().TransformBy(RestTransforms[HoldingPart]);
                Base.X = FMath::Clamp(Base.X, Local.Min.X * .6f, Local.Max.X * .6f);
                Base.Y = FMath::Clamp(Base.Y, Local.Min.Y * .6f, Local.Max.Y * .6f);
                const FTransform World = GetComponentTransform();
                FHitResult Hit;
                FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestHoldingFire), true);
                const auto* Entry = OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId));
                if (Entry && Entry->DamageFirePoints[I][2] > 0.f)
                {
                    // Preview worlds may have no queryable physics scene.
                    // Use archived exact-mesh support measurements there and
                    // in gameplay, transformed with the healthy holding.
                    const float* Point = Entry->DamageFirePoints[I];
                    Base = RestTransforms[HoldingPart].TransformPosition(FVector(Point[0], Point[1], Point[2]));
                }
                else Base.Z = Holding->LineTraceComponent(Hit, World.TransformPosition(FVector(Base.X, Base.Y, Local.Max.Z + 50.f)),
                    World.TransformPosition(FVector(Base.X, Base.Y, -10.f)), Query) ?
                    static_cast<float>(World.InverseTransformPosition(Hit.ImpactPoint).Z) : 30.f;
            }
            else for (int32 P = 0; P < Parts.Num(); ++P)
            {
                const UStaticMeshComponent* Part = Parts[P];
                if (!IsValid(Part) || !Part->GetStaticMesh() || FlameParts.Contains(P)) continue;
                const FBox Bounds = Part->GetStaticMesh()->GetBoundingBox().TransformBy(RestTransforms[P]);
                const FVector Size = Bounds.GetSize();
                if (Size.X * Size.Y >= 2500.f && Base.X >= Bounds.Min.X && Base.X <= Bounds.Max.X
                    && Base.Y >= Bounds.Min.Y && Base.Y <= Bounds.Max.Y)
                    Base.Z = FMath::Max(Base.Z, Bounds.Max.Z);
            }
            auto* Fire = NewObject<UOldWestFireVisuals>(GetOwner());
            GetOwner()->AddInstanceComponent(Fire);
            Fire->SetupAttachment(this);
            Fire->SetRelativeLocation(Base - FVector(0, 0, 8));
            Fire->RegisterComponent();
            Fire->Build(160.f, 300.f, I * .37f, 350.f, true);
            Fire->SetEmissionScale(1800.f, 350.f);
            DamageFires.Add(Fire);
        }
    }
    for (UOldWestFireVisuals* Fire : DamageFires) if (IsValid(Fire))
        Fire->SetExtinguished(Ruined || CurrentDamage == 0 || Geological);
    for (UOldWestFireVisuals* Fire : Fires) if (IsValid(Fire)) Fire->SetExtinguished(Ruined);
    for (int32 I = 0; I < Parts.Num(); ++I)
    {
        UStaticMeshComponent* Component = Parts[I];
        if (!IsValid(Component)) continue;
        if (Geological && (I == HoldingPart || I == HoldingDamagedPart || I == HoldingRuinPart))
        {
            const int32 VisiblePart = Ruined ? HoldingRuinPart :
                (CurrentDamage > 0 && HoldingDamagedPart != INDEX_NONE ? HoldingDamagedPart : HoldingPart);
            const bool Show = I == VisiblePart;
            Component->SetVisibility(Show && IsVisible());
            Component->SetCollisionEnabled(Show ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
            Component->SetRelativeTransform(RestTransforms[I]);
            for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot)
                Component->SetMaterial(Slot, RestSlotMaterials[RestSlotOffsets[I] + Slot].Get());
            continue;
        }
        if (I == HoldingRuinPart || (I == HoldingPart && HoldingRuinPart != INDEX_NONE))
        {
            const bool Show = I == HoldingRuinPart ? Ruined : !Ruined;
            Component->SetVisibility(Show && IsVisible());
            Component->SetCollisionEnabled(Show ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
            Component->SetRelativeTransform(RestTransforms[I]);
            // The dedicated ruin already has its char material and collapsed
            // geometry. Repair restores the healthy source's original slots.
            if (I == HoldingRuinPart || Ruined) continue;
        }
        if (AshParts.Contains(I))
        {
            Component->SetVisibility(Ruined && IsVisible());
            continue;
        }
        if (RuinConsumedParts.Contains(I))
        {
            Component->SetVisibility(!Ruined && IsVisible());
            Component->SetCollisionEnabled(Ruined ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryOnly);
            if (Ruined) continue;
        }
        FTransform Pose = RestTransforms[I];
        const int32 ConditionIndex = ConditionIndices[I];
        const bool IsFlame = FlameParts.Contains(I);
        const bool IsFoliage = FoliageParts.Contains(I);
        const bool IsRootedTree = RestMaterials[I] == TEXT("TreeBark");
        const bool GroundPivot = IsRootedTree || (I == HoldingPart &&
            OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId)) != nullptr);
        // Tree meshes share a ground-level root pivot. Collapse them according
        // to their actual geometry elevation, while retaining the old behavior
        // for all other camp pieces.
        const FVector Position = GroundPivot && Component->GetStaticMesh() ?
            Component->GetStaticMesh()->GetBoundingBox().TransformBy(Pose).GetCenter() : Pose.GetLocation();
        const bool Scorched = !IsFlame && (Ruined || (CurrentDamage > 0 && (ConditionIndex % 5 == 1 || ConditionIndex % 7 == 2)));
        // Fire is extinguished and leaves are consumed in ruin. Keeping these
        // transient surfaces out of rubble avoids rigid flame planes and
        // floating canopy fragments; repair restores their original surfaces.
        if (IsFlame || IsFoliage)
        {
            Component->SetVisibility(!Ruined && IsVisible());
            if (IsFoliage) Component->SetCollisionEnabled(Ruined ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryOnly);
        }
        if (Ruined && Position.Z > 36)
        {
            // Retain the landmark's footprint, collapse elevated elements into rubble.
            FVector Fallen = Position;
            Fallen.Z = 24 + (Position.Z - 24) * .32;
            Fallen.X += (ConditionIndex % 3 - 1) * 14;
            Fallen.Y += (ConditionIndex % 5 - 2) * 9;
            Pose.SetLocation(GroundPivot ? Pose.GetLocation() + Fallen - Position : Fallen);
            Pose.SetRotation(FRotator((ConditionIndex % 3 - 1) * 24, ConditionIndex % 2 ? 11 : -13, (ConditionIndex % 5 - 2) * 17).Quaternion() * Pose.GetRotation());
            // Tall walls, railings and posts fall onto their side. A small
            // random tilt alone left complete upright facades in the debris.
            if (Component->GetStaticMesh())
            {
                const FVector Extent = Component->GetStaticMesh()->GetBoundingBox().TransformBy(RestTransforms[I]).GetSize();
                if (Extent.Z > 75.f && FMath::Min(Extent.X, Extent.Y) < Extent.Z * .35f)
                {
                    const FVector Axis = Extent.X < Extent.Y ? FVector::RightVector : FVector::ForwardVector;
                    Pose.SetRotation(FQuat(Axis, FMath::DegreesToRadians(62.f + ConditionIndex % 4 * 5.f)) * RestTransforms[I].GetRotation());
                }
            }
            FVector Scale = Pose.GetScale3D(); Scale.Z *= .48; Pose.SetScale3D(Scale);
        }
        else if (CurrentDamage > 0 && !IsRootedTree && !IsFoliage && ConditionIndex % 9 == 3 && Position.Z > 80)
        {
            Pose.AddToTranslation(FVector(7, -5, -12));
            Pose.SetRotation(FRotator(0, 0, 8).Quaternion() * Pose.GetRotation());
        }
        if (Ruined && Component->IsVisible() && Component->GetStaticMesh())
        {
            // Settle every remaining fragment on the camp's local ground,
            // accounting for pivots, rotation and scale. Clamping only buried
            // pieces left small cloth, coils and canopy remnants in midair.
            const FBox FallenBounds = Component->GetStaticMesh()->GetBoundingBox().TransformBy(Pose);
            if (FallenBounds.IsValid)
                Pose.AddToTranslation(FVector(0, 0, -FallenBounds.Min.Z));
        }
        Component->SetRelativeTransform(Pose);
        // Condition affects the material already assigned to each slot. Its
        // grain, normal and substrate remain distinct; repair restores the
        // exact source pointers, including imported bark/wood/metal mixtures.
        for (int32 Slot = 0; Slot < Component->GetNumMaterials(); ++Slot)
        {
            const int32 RestIndex = RestSlotOffsets[I] + Slot;
            UMaterialInterface* Source = RestSlotMaterials[RestIndex].Get();
            Component->SetMaterial(Slot, Scorched ?
                (IsFoliage ? Material(TEXT("DryLeaf")) : ScorchedMaterial(Source)) : Source);
        }
    }
    if(Ruined&&IsValid(RuinSmoke)) {
        float Top=0.f;
        for(const UStaticMeshComponent* Part:Parts)if(IsValid(Part)&&Part->IsVisible()&&Part->GetStaticMesh())
            Top=FMath::Max(Top,float(Part->GetStaticMesh()->GetBoundingBox().TransformBy(Part->GetRelativeTransform()).Max.Z));
        // Smoke-only sheets start at their component origin. Let the lower
        // wisps intersect the rubble while the taller plume clears its top.
        RuinSmoke->SetRelativeLocation(FVector(0,0,FMath::Max(4.f,Top * (Portrait ? .30f : .65f))));
    }
    // Ground parameters also need the region selected after camp construction,
    // including a static ruin; this introduces no time-driven geometry motion.
    SetComponentTickEnabled(GroundFitMaterial ||
        (DesignId == TEXT("smuggler_s_landing") && GroundParts.Num() > 0 && !Portrait) ||
        (!Ruined && Motions.Num() > 0));
}

void UOldWestCampVisuals::AppendPortraitFramingPoints(const FVector& CameraLocation,
    TArray<FVector>& SolidPoints, TArray<FVector>& FlamePoints) const
{
    // Actual current visible part bounds preserve damage, ruin and repair.
    // Keep disjoint corners: an aggregate box invents empty high corners.
    auto AppendBounds = [&SolidPoints](const UStaticMeshComponent* Component)
    {
        if (!IsValid(Component) || !Component->IsVisible()) return;
        const FBox Bounds = Component->Bounds.GetBox();
        if (!Bounds.IsValid) return;
        for (int32 Corner = 0; Corner < 8; ++Corner)
            SolidPoints.Add(FVector((Corner & 1) ? Bounds.Max.X : Bounds.Min.X,
                (Corner & 2) ? Bounds.Max.Y : Bounds.Min.Y, (Corner & 4) ? Bounds.Max.Z : Bounds.Min.Z));
    };
    for (const UStaticMeshComponent* Component : Parts) AppendBounds(Component);
    const auto* Expansion = OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId));
    if (Expansion && Expansion->PortraitIncludesBase)
        for (const UStaticMeshComponent* Component : GroundParts) AppendBounds(Component);
    for (const UOldWestFireVisuals* Fire : Fires)
        if (IsValid(Fire)) Fire->AppendPortraitFlamePoints(CameraLocation, FlamePoints);
    for (const UOldWestFireVisuals* Fire : DamageFires)
        if (IsValid(Fire)) Fire->AppendPortraitFlamePoints(CameraLocation, FlamePoints);
}

FBox UOldWestCampVisuals::GetPortraitBounds() const
{
    FBox Result = GetVisualBounds();
    const auto* Expansion = OldWestExpansionHoldings::ForCamp(TCHAR_TO_UTF8(*DesignId));
    if (Expansion && Expansion->PortraitIncludesBase)
        for (const UStaticMeshComponent* Component : GroundParts)
            if (IsValid(Component) && Component->IsVisible()) Result += Component->Bounds.GetBox();
    return Result;
}

FBox UOldWestCampVisuals::GetVisualBounds() const
{
    FBox Result(ForceInit);
    for (const UStaticMeshComponent* Component : Parts)
        if (IsValid(Component) && Component->IsVisible()) Result += Component->Bounds.GetBox();
    for (const UOldWestFireVisuals* Fire : Fires)
        if (IsValid(Fire) && Fire->GetVisualBounds().IsValid) Result += Fire->GetVisualBounds();
    for (const UOldWestFireVisuals* Fire : DamageFires)
        if (IsValid(Fire) && Fire->GetVisualBounds().IsValid) Result += Fire->GetVisualBounds();
    return Result.IsValid ? Result : FBox(GetComponentLocation() - FVector(50), GetComponentLocation() + FVector(50));
}

int32 UOldWestCampVisuals::GetPartCount() const
{
    // Condition dressing is transient, like damage fire and ruin smoke.
    int32 Count = Parts.Num() - AshParts.Num();
    for (const UOldWestFireVisuals* Fire : Fires) if (IsValid(Fire)) Count += Fire->GetPartCount();
    return Count;
}

FVector UOldWestCampVisuals::GetRuinSmokeSample() const
{
    return IsValid(RuinSmoke) ? RuinSmoke->GetSmokeSample() : FVector::ZeroVector;
}

int32 UOldWestCampVisuals::GetVisibleRuinSmokeParts() const
{
    return IsValid(RuinSmoke)?RuinSmoke->GetVisiblePartCount():0;
}

int32 UOldWestCampVisuals::GetVisibleDamageFireParts() const
{
    int32 Count = 0;
    for (const UOldWestFireVisuals* Fire : DamageFires)
        if (IsValid(Fire)) Count += Fire->GetVisiblePartCount();
    return Count;
}

int32 UOldWestCampVisuals::GetAnimatedPartCount() const
{
    int32 Count = Motions.Num();
    for (const UOldWestFireVisuals* Fire : Fires) if (IsValid(Fire)) Count += Fire->GetPartCount();
    return Count;
}

void UOldWestCampVisuals::GetVisibleGroundingDebug(int32& Count, float& MaxAbsMinZ) const
{
    // Count all visible sheets for composition accounting, but only solid
    // rubble participates in the ruined-part ground-contact measurement.
    Count = GetVisibleDamageFireParts()+GetVisibleRuinSmokeParts();
    MaxAbsMinZ = 0.f;
    for (const UOldWestFireVisuals* Fire : Fires)
    {
        if (!IsValid(Fire) || !Fire->GetVisiblePartCount()) continue;
        Count += Fire->GetVisiblePartCount();
        const FBox Local = Fire->GetVisualBounds().TransformBy(GetComponentTransform().Inverse());
        if (Local.IsValid) MaxAbsMinZ = FMath::Max(MaxAbsMinZ, static_cast<float>(FMath::Abs(Local.Min.Z)));
    }
    for (const UStaticMeshComponent* Component : Parts)
    {
        if (!IsValid(Component) || !Component->IsVisible() || !Component->GetStaticMesh()) continue;
        const FBox LocalBounds = Component->GetStaticMesh()->GetBoundingBox().TransformBy(Component->GetRelativeTransform());
        if (!LocalBounds.IsValid) continue;
        ++Count;
        MaxAbsMinZ = FMath::Max(MaxAbsMinZ, static_cast<float>(FMath::Abs(LocalBounds.Min.Z)));
    }
}

void UOldWestCampVisuals::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    UpdateHoldingGroundFit();
    if (Ruined || !IsVisible()) return;
    Clock += FMath::Min(DeltaTime, .1f);
    for (const FMotion& Motion : Motions)
    {
        UStaticMeshComponent* Component = Parts.IsValidIndex(Motion.Part) ? Parts[Motion.Part].Get() : nullptr;
        if (!IsValid(Component)) continue;
        FTransform Pose = RestTransforms[Motion.Part];
        const float Phase = Clock * Motion.Speed + Motion.Phase;
        const float Intensity = CurrentDamage > 0 ? .45f : 1.f;
        if (Motion.Kind == EMotion::Rotate || Motion.Kind == EMotion::Sway)
        {
            const float Degrees = Motion.Kind == EMotion::Rotate ? Clock * Motion.Speed * Intensity + Motion.Phase * 57.29578f : FMath::Sin(Phase) * Motion.Amplitude * Intensity;
            const FQuat Q(Motion.Axis, FMath::DegreesToRadians(Degrees));
            Pose.SetLocation(Motion.Pivot + Q.RotateVector(Pose.GetLocation() - Motion.Pivot));
            Pose.SetRotation(Q * Pose.GetRotation());
        }
        else if (Motion.Kind == EMotion::Translate)
            Pose.AddToTranslation(Motion.Axis * FMath::Sin(Phase) * Motion.Amplitude * Intensity);
        else
        {
            const float S = FMath::Sin(Phase) * Motion.Amplitude * Intensity;
            Pose.SetScale3D(Pose.GetScale3D() * (FVector::OneVector + Motion.Axis.GetAbs() * S));
        }
        if (CurrentDamage > 0 && Motion.Part % 9 == 3 && Pose.GetLocation().Z > 80)
        {
            Pose.AddToTranslation(FVector(7, -5, -12));
            Pose.SetRotation(FRotator(0, 0, 8).Quaternion() * Pose.GetRotation());
        }
        Component->SetRelativeTransform(Pose);
    }
}
