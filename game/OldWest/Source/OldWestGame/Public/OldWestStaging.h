#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OldWestStaging.generated.h"

class AOldWestUnit;
class AOldWestRegion;
class UStaticMeshComponent;
class UTextRenderComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

// Per-view presentation only. Never replicated: private models are created only
// from the local player's already-redacted hand snapshot.
UCLASS()
class OLDWESTGAME_API AOldWestStaging : public AActor
{
    GENERATED_BODY()
public:
    struct FFieldLabel { FString Text; FVector Position; int32 Side; };
    const TArray<FFieldLabel>& GetFieldLabels() const { return FieldLabels; }
    AOldWestStaging();
    void SetTextVisible(bool Visible);
    void ApplySnapshot(const FString& Payload);
    virtual void Tick(float DeltaSeconds) override;
    FString GetFuseDebug() const;
    FString GetRegionDebug() const;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    static FVector HandPosition(int32 Side, bool Event, int32 Index);
    static FVector UtilityPosition(int32 Side, int32 Index);
private:
    void BuildGround(int32 Seat);
    void BuildFuseGround(int32 Side);
    void Mark(const FVector& Position, const FVector& Size, const TCHAR* Material);
    void Sign(const FString& Text, const FVector& Position, int32 Side, FColor Color, float Size=90.f);
    UPROPERTY(Transient) TMap<int32,TObjectPtr<AOldWestUnit>> Hand;
    UPROPERTY(Transient) TArray<TObjectPtr<AOldWestUnit>> Utilities;
    UPROPERTY(Transient) TArray<TObjectPtr<AOldWestUnit>> WaterBundles;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> GroundParts;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> FuseSegments;
    UPROPERTY(Transient) TMap<int32,TObjectPtr<UStaticMeshComponent>> FuseEmbers;
    UPROPERTY(Transient) TMap<int32,TObjectPtr<UMaterialInstanceDynamic>> FuseGlow;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> FuseCordMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> FuseAshMaterial;
    TArray<int32> FuseSegmentSides;
    TArray<float> FuseSegmentDistances;
    TArray<FFieldLabel> FieldLabels;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Unknowns;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextRenderComponent>> UnknownLabels;
    int32 SeenSeat=-1;
    FString SeenMatch;
    UPROPERTY(Transient) TObjectPtr<AOldWestRegion> Region;
};
