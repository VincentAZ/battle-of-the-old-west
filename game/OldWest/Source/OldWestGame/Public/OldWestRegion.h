#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OldWestRegion.generated.h"

class UStaticMeshComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

// A local cosmetic scene. Selection uses only the already-public match ID;
// it never changes a rules snapshot, replicated object or terrain collider.
// Decorative map rocks are excluded from the cosmetic Trouble routes only.
UCLASS()
class OLDWESTGAME_API AOldWestRegion : public AActor
{
    GENERATED_BODY()
public:
    AOldWestRegion();
    void ApplyMatch(const FString& Match);
    FString GetDebug() const;
    static FString GetRouteSceneryDebug(UWorld* World);
    bool IsWinter() const { return Region==0; }
    int32 GetRegionIndex() const { return Region; }
    void SetLandingFoundation(UObject* Key, const FVector& Origin, const FVector& Frame, bool Enabled);
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    void Clear();
    void ClearTroubleRoutes();
    void UpdateLandingFoundations();
    struct FRouteRockState { bool Hidden; bool Collision; };
    TMap<TWeakObjectPtr<AActor>, FRouteRockState> RouteRocks;
    struct FLandingFoundation { FVector Origin; FVector Frame; };
    TMap<TWeakObjectPtr<UObject>, FLandingFoundation> LandingFoundations;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> LandingMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> LandingOriginalMaterial;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> LandingTerrain;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Terrain;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> OriginalMaterial;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    UPROPERTY(Transient) TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> Trees;
    FString SeenMatch;
    int32 Region=-1;
    int32 TreeCount=0;
    bool OriginalVisible=true;
};
