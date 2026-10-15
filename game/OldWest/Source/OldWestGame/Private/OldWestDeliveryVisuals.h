#pragma once
#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "OldWestDeliveryVisuals.generated.h"
class UStaticMeshComponent;
class USkeletalMeshComponent;
class UAnimSequence;

// Sourced trail wagon and four-ox team. Cosmetic only; no collision or rules.
UCLASS()
class UOldWestDeliveryVisuals : public USceneComponent
{
    GENERATED_BODY()
public:
    static constexpr float DioramaScale = .4f;
    static constexpr float AnimalScale = .9f;
    static constexpr float WalkSpeed = 59.5238095f * AnimalScale * DioramaScale;
    static constexpr float RouteLength = WalkSpeed * 2.4f;
    static void Preload(TArray<TObjectPtr<UObject>>& Assets);
    bool Build(const FVector& From, const FVector& To, int32 Count, bool Whiskey, bool Medical);
    void Clear();
    void Advance(float DeltaSeconds);
    float GetDuration() const { return MoveSeconds + .65f; }
    FBox GetVisualBounds() const;
    TArray<FVector> GetVisibilityPoints() const;
    FString GetDebug() const;
private:
    UStaticMeshComponent* Part(const FString& Path, const FVector& Offset = FVector::ZeroVector);
    void Pose();
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Wheels;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Yokes;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Chains;
    UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> Animals;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Idle;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Walk;
    FVector Start = FVector::ZeroVector, Finish = FVector::ZeroVector;
    float Age = 0.f, Distance = 0.f, Travel = 0.f, MoveSeconds = 0.f;
    int32 CargoCount = 0;
    bool Walking = true, HasWhiskey = false;
};
