#pragma once
#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "OldWestStampedeVisuals.generated.h"
class USkeletalMeshComponent;
class UAnimSequence;

// Presentation only: three copies, fixed formation, no rules/AI/collision.
UCLASS()
class UOldWestStampedeVisuals : public USceneComponent
{
    GENERATED_BODY()
public:
    UOldWestStampedeVisuals();
    void Build(int32 Side);
    void Clear();
    void RecordMovement(const FVector& Delta);
    FBox GetVisualBounds() const;
    FString GetDebug() const;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Function) override;
private:
    UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> Animals;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Idle;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Run;
    FVector Movement = FVector::ZeroVector;
    double IdleSeconds = 0., RunSeconds = 0., TravelCm = 0.;
    float BlendSeconds = 1.f, Speed = 0.f, HomeYaw = 0.f;
    bool Running = false;
};
