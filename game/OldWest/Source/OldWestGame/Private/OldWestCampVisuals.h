#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "OldWestCampVisuals.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInterface;
class UOldWestFireVisuals;
class UMaterialInstanceDynamic;
class AOldWestRegion;

/** Card-specific environmental vignettes. Coordinates and dimensions are centimetres. */
UCLASS()
class OLDWESTGAME_API UOldWestCampVisuals : public USceneComponent
{
    GENERATED_BODY()
public:
    UOldWestCampVisuals();
    void Build(const FString& CardId);
    void SetCondition(int32 Damage, bool Destroyed, bool Portrait = false);
    FBox GetVisualBounds() const;
    FBox GetPortraitBounds() const;
    void AppendPortraitFramingPoints(const FVector& CameraLocation,
        TArray<FVector>& SolidPoints, TArray<FVector>& FlamePoints) const;
    void GetVisibleGroundingDebug(int32& Count, float& MaxAbsMinZ) const;
    const FString& GetDesignId() const { return DesignId; }
    int32 GetPartCount() const;
    int32 GetGroundPartCount() const { return GroundParts.Num(); }
    void AppendHoldingDebugComponents(TArray<UStaticMeshComponent*>& Out) const;
    int32 GetAnimatedPartCount() const;
    int32 GetVisibleDamageFireParts() const;
    int32 GetVisibleRuinSmokeParts() const;
    FVector GetRuinSmokeSample() const;
    static TArray<FString> GetSupportedCampIds();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void OnComponentDestroyed(bool DestroyingHierarchy) override;

private:
    void DressIdentity();
    /** Static Western holding skin for a base camp; false when its asset is missing. */
    bool BuildHolding(const FString& Asset, bool Expansion = false, float PresentationScale = 1.f);
    void BuildHoldingGround(const FString& Asset, float HoldingScale, bool Expansion = false);
    void UpdateHoldingGroundFit();
    enum class EMotion : uint8 { Rotate, Sway, Translate, Breathe };
    struct FMotion
    {
        int32 Part = INDEX_NONE;
        EMotion Kind = EMotion::Sway;
        FVector Axis = FVector::UpVector;
        FVector Pivot = FVector::ZeroVector;
        float Speed = 1.f;
        float Amplitude = 1.f;
        float Phase = 0.f;
    };
    int32 Part(const TCHAR* Mesh, const FVector& Position, const FVector& Dimensions,
               const TCHAR* Material, const FRotator& Rotation = FRotator::ZeroRotator);
    int32 Box(const FVector& P, const FVector& D, const TCHAR* M, const FRotator& R = FRotator::ZeroRotator);
    int32 Drum(const FVector& P, float Diameter, float Height, const TCHAR* M, const FRotator& R = FRotator::ZeroRotator);
    int32 Orb(const FVector& P, const FVector& D, const TCHAR* M);
    int32 Cone(const FVector& P, float Diameter, float Height, const TCHAR* M);
    void Beam(const FVector& A, const FVector& B, float Width, const TCHAR* M);
    void Pipe(const FVector& A, const FVector& B, float Diameter, const TCHAR* M);
    void Move(int32 Index, EMotion Kind, const FVector& Axis, float Speed, float Amplitude,
              const FVector& Pivot = FVector::ZeroVector, float Phase = 0.f);
    void Frame(const FVector& P, const FVector& Size, const TCHAR* Cladding, bool Roof = true);
    void Tank(const FVector& P, float Diameter, float Height, const TCHAR* M);
    void Wheel(const FVector& P, float Diameter, bool Spin = false);
    void Fan(const FVector& P, float Diameter, float Speed, const FRotator& R = FRotator::ZeroRotator);
    void Flag(const FVector& P, float Height, const TCHAR* M);
    void Fire(const FVector& P, float Size, bool IncludePrimitiveFuel = true);
    void Antenna(const FVector& P, float Height, bool Scan);
    void Crates(const FVector& P, int32 Count);
    void Fence(const FVector& A, const FVector& B, float Height);
    void Cross(const FVector& P, float Size);
    void Tree(const FVector& P, float Height, const TCHAR* Foliage);
    void Vehicle(const FVector& P, bool Armoured);
    void Bed(const FVector& P, const TCHAR* M);
    void Torus(const FVector& P, float Diameter, float Tube, const TCHAR* M, const FRotator& R = FRotator::ZeroRotator);
    UMaterialInterface* Material(const TCHAR* Name);
    UMaterialInterface* ScorchedMaterial(UMaterialInterface* Source);
    UPROPERTY(Transient) TObjectPtr<UOldWestFireVisuals> RuinSmoke;
    FString DesignId;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    // Setting base (ground, scatter, river water) under a holding. Separate from
    // Parts so damage and ruin never char the water or scatter debris over it.
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> GroundParts;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> GroundFitMaterial;
    TWeakObjectPtr<AOldWestRegion> GroundRegion;
    bool GroundFitPortrait = false;
    UPROPERTY(Transient) TMap<FString, TObjectPtr<UStaticMesh>> Meshes;
    UPROPERTY(Transient) TMap<FString, TObjectPtr<UMaterialInterface>> Materials;
    TArray<FTransform> RestTransforms;
    // Logical legacy ordering keeps existing landmark damage assignments stable
    // when one detailed mesh consolidates several old shelter primitives.
    TArray<int32> ConditionIndices;
    int32 NextConditionIndex = 0;
    TArray<FString> RestMaterials;
    // Store every actual source slot, including imported multi-material meshes.
    // Flattening the arrays keeps their material references visible to GC.
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInterface>> RestSlotMaterials;
    TArray<int32> RestSlotOffsets;
    UPROPERTY(Transient) TMap<FString, TObjectPtr<UMaterialInterface>> ScorchedMaterials;
    TArray<FMotion> Motions;
    UPROPERTY(Transient) TArray<TObjectPtr<UOldWestFireVisuals>> Fires;
    // Damage fires are distinct from a camp's ordinary lamps and hearths.
    UPROPERTY(Transient) TArray<TObjectPtr<UOldWestFireVisuals>> DamageFires;
    TSet<int32> AshParts;
    TSet<int32> RuinConsumedParts;
    TSet<int32> FlameParts;
    TSet<int32> FoliageParts;
    float Clock = 0.f;
    int32 CurrentDamage = 0;
    // Index of the single static holding part, or INDEX_NONE for authored scenes.
    int32 HoldingPart = INDEX_NONE;
    // Optional separately reviewed condition geometry; healthy assets stay intact.
    int32 HoldingRuinPart = INDEX_NONE;
    int32 HoldingDamagedPart = INDEX_NONE;
    bool Ruined = false;
};
