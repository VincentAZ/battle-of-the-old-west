#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "OldWestFireVisuals.generated.h"

class UMaterialInstanceDynamic;

/** A plane with conservative bounds for per-view material billboarding. */
UCLASS()
class OLDWESTGAME_API UOldWestFireSheet : public UStaticMeshComponent
{
    GENERATED_BODY()
public:
    bool Smoke = false;
    virtual FBoxSphereBounds CalcBounds(const FTransform& LocalToWorld) const override;
};

/** Fire flipbooks and individually advected, expanding ruin smoke particles. */
UCLASS()
class OLDWESTGAME_API UOldWestFireVisuals : public USceneComponent
{
    GENERATED_BODY()
public:
    UOldWestFireVisuals();
    void Build(float WidthCm, float HeightCm, float Phase = 0.f,
        float EmissionScale = 350.f, bool IncludeSmoke = true, bool RuinPlume = false);
    void SetExtinguished(bool Extinguished);
    void SetSmokeOnly(bool Enabled, float Opacity = -1.f);
    // Negative SmokeScale keeps the existing all-layer adaptation contract.
    void SetEmissionScale(float Scale, float SmokeScale = -1.f);
    int32 GetPartCount() const { return Sheets.Num(); }
    int32 GetVisiblePartCount() const;
    uint32 GetAnimationSignature() const;
    FBox GetVisualBounds() const;
    FVector GetSmokeSample() const;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    // Composition only: full flame sheets across all phases for this camera.
    // Renderer/world bounds and the rendered smoke remain unchanged.
    void AppendPortraitFlamePoints(const FVector& CameraLocation, TArray<FVector>& Points) const;
    virtual void OnComponentDestroyed(bool bDestroyingHierarchy) override;
    virtual void OnVisibilityChanged() override;

private:
    void ClearSheets();
    void UpdateSmokeParticles(float DeltaTime);
    UPROPERTY(Transient) TArray<TObjectPtr<UOldWestFireSheet>> Sheets;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> Instances;
    TArray<float> Phases;
    TArray<float> Rates;
    bool IsExtinguished = false;
    bool SmokeOnly = false;
    bool IsRuinPlume = false;
    TArray<FVector> SmokeOrigins;
    float SmokeClock = 0.f;
    float SmokeWidth = 300.f;
    float SmokeRise = 360.f;
    FVector SmokeSample = FVector::ZeroVector;
};
